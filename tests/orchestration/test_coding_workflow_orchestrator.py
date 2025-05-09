import pytest
import json
from unittest.mock import MagicMock, patch
from src.orchestration.coding_workflow_orchestrator import CodingWorkflowOrchestrator
from src.system.models import DevelopmentPlan, TaskResult # Add TaskResult for _execute_code mock if needed later

# Mock Application for basic instantiation tests
@pytest.fixture
def mock_app():
    app = MagicMock()
    # If Application methods are called in __init__ or early, mock them here
    # For now, a simple MagicMock should suffice for instantiation.
    return app

def test_orchestrator_instantiation(mock_app):
    """Test that the orchestrator can be instantiated."""
    orchestrator = CodingWorkflowOrchestrator(
        app=mock_app,
        initial_goal="Test Goal",
        initial_context="Test Context",
        test_command="pytest tests",
        max_retries=2
    )
    assert orchestrator is not None
    assert orchestrator.initial_goal == "Test Goal"
    assert orchestrator.app == mock_app
    assert orchestrator.max_retries == 2

def test_orchestrator_run_completes_with_stubs(mock_app):
    """Test that the run() method completes using the stubbed phase methods."""
    orchestrator = CodingWorkflowOrchestrator(
        app=mock_app,
        initial_goal="Test Goal",
        initial_context="Test Context",
        test_command="pytest tests",
        max_retries=1 # Limit retries for this stub test
    )

    # Setup mock_app for _generate_plan (Phase 2 version) to succeed
    mock_plan_data = {"instructions": "Dummy plan instructions", "files": ["dummy.py"], "test_command": "pytest tests"}
    mock_app.handle_task_command.return_value = {
        "status": "COMPLETE",
        "content": json.dumps(mock_plan_data),
        "parsedContent": mock_plan_data
    }
    
    # With current stubs for _execute_code, _validate_code, _analyze_iteration,
    # and a successful _generate_plan, it should complete in 1 iteration.
    result = orchestrator.run()
    
    assert result is not None
    assert orchestrator.overall_success is True
    assert result.get("status") == "COMPLETE" # Based on current _analyze_iteration stub
    assert result.get("content") == "Simulated Aider diff" # Based on current _execute_code stub
    
    # Check that _generate_plan was called
    mock_app.handle_task_command.assert_called_once_with(
        "user:generate-plan-from-goal",
        params={"goal": "Test Goal", "context_string": "Test Context"}
    )


def test_generate_plan_success(mock_app):
    orchestrator = CodingWorkflowOrchestrator(
        app=mock_app,
        initial_goal="Test Goal Plan",
        initial_context="Test Context Plan",
        test_command="pytest tests", # test_command for orchestrator init
        max_retries=1
    )

    mock_plan_data = {"instructions": "Generated plan instructions", "files": ["file1.py", "file2.py"], "test_command": "pytest tests"}
    # Note: DevelopmentPlan.test_command is optional. If the LLM doesn't provide it,
    # it will default to None or the value from orchestrator.test_command if logic is added.
    # For this test, we assume the LLM provides it or it's handled.
    # The current DevelopmentPlan model has test_command as optional.

    mock_app.handle_task_command.return_value = {
        "status": "COMPLETE",
        "content": json.dumps(mock_plan_data), 
        "parsedContent": mock_plan_data 
    }

    success = orchestrator._generate_plan()

    assert success is True
    assert orchestrator.current_plan is not None
    assert isinstance(orchestrator.current_plan, DevelopmentPlan)
    assert orchestrator.current_plan.instructions == "Generated plan instructions"
    assert orchestrator.current_plan.files == ["file1.py", "file2.py"]
    assert orchestrator.current_plan.test_command == "pytest tests"


    mock_app.handle_task_command.assert_called_once_with(
        "user:generate-plan-from-goal",
        params={"goal": "Test Goal Plan", "context_string": "Test Context Plan"}
    )

def test_generate_plan_task_fails(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "t")
    mock_app.handle_task_command.return_value = {
        "status": "FAILED",
        "content": "LLM plan generation error",
        "parsedContent": None
    }
    success = orchestrator._generate_plan()
    assert success is False
    assert orchestrator.current_plan is None
    assert orchestrator.final_loop_result is not None
    assert orchestrator.final_loop_result["reason"] == "Plan generation task failed"

def test_generate_plan_parsing_fails(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "t")
    mock_app.handle_task_command.return_value = {
        "status": "COMPLETE",
        "content": "Some content",
        "parsedContent": {"wrong_key": "some_value"} 
    }
    success = orchestrator._generate_plan()
    assert success is False
    assert orchestrator.current_plan is None
    assert orchestrator.final_loop_result is not None
    assert orchestrator.final_loop_result["reason"] == "Plan parsing failed"

def test_generate_plan_app_call_exception(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "t")
    mock_app.handle_task_command.side_effect = Exception("Network error")

    success = orchestrator._generate_plan()

    assert success is False
    assert orchestrator.current_plan is None
    assert orchestrator.final_loop_result is not None
    assert orchestrator.final_loop_result["reason"] == "Plan generation task call failed"
    assert "Network error" in orchestrator.final_loop_result.get("details", "")

# Tests for _execute_code (Phase 3)

def test_execute_code_success(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "t")
    orchestrator.current_plan = DevelopmentPlan(
        instructions="Implement function foo", 
        files=["src/foo.py"],
        test_command="pytest" # Will be ignored by _execute_code
    )
    
    mock_aider_result_dict = {"status": "COMPLETE", "content": "```diff\n+ def foo(): pass\n```", "notes": {"success": True}}
    mock_app.handle_task_command.return_value = mock_aider_result_dict

    task_result_obj = orchestrator._execute_code()

    assert task_result_obj is not None
    assert task_result_obj.status == "COMPLETE"
    assert "def foo()" in task_result_obj.content
    assert task_result_obj.notes.get("success") is True
    
    mock_app.handle_task_command.assert_called_once_with(
        "aider:automatic",
        params={"prompt": "Implement function foo", "relative_editable_files": ["src/foo.py"]}
    )

def test_execute_code_aider_fails(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "t")
    orchestrator.current_plan = DevelopmentPlan(instructions="Bad plan", files=["bad.py"], test_command="cmd")
    
    mock_aider_failure_dict = {"status": "FAILED", "content": "Aider tool error", "notes": {"error": {"message": "Aider tool error"}}}
    mock_app.handle_task_command.return_value = mock_aider_failure_dict

    task_result_obj = orchestrator._execute_code()

    assert task_result_obj is not None
    assert task_result_obj.status == "FAILED"
    assert task_result_obj.content == "Aider tool error"
    mock_app.handle_task_command.assert_called_once()

def test_execute_code_no_plan(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "t")
    orchestrator.current_plan = None # Simulate no plan being set

    task_result_obj = orchestrator._execute_code()
    
    assert task_result_obj is not None
    assert task_result_obj.status == "FAILED"
    assert "No current plan available" in task_result_obj.content
    mock_app.handle_task_command.assert_not_called()

def test_execute_code_plan_missing_instructions(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "t")
    # Plan is missing instructions
    orchestrator.current_plan = DevelopmentPlan(instructions="", files=["src/foo.py"], test_command="cmd") 

    task_result_obj = orchestrator._execute_code()

    assert task_result_obj is not None
    assert task_result_obj.status == "FAILED"
    assert "Plan missing instructions or files" in task_result_obj.content
    mock_app.handle_task_command.assert_not_called() # Should not call if plan is invalid

def test_execute_code_app_call_exception(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "t")
    orchestrator.current_plan = DevelopmentPlan(instructions="Valid plan", files=["f.py"], test_command="cmd")
    mock_app.handle_task_command.side_effect = Exception("Network error during Aider call")

    task_result_obj = orchestrator._execute_code()

    assert task_result_obj is not None
    assert task_result_obj.status == "FAILED"
    assert "Aider execution task call failed: Network error during Aider call" in task_result_obj.content
    assert task_result_obj.notes["error"]["type"] == "ORCHESTRATOR_EXCEPTION"

# Tests for _validate_code (Phase 4)

def test_validate_code_tests_pass(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "pytest my_tests")
    
    mock_shell_result_dict = {
        "status": "COMPLETE", 
        "content": "All tests passed!", 
        "notes": {"exit_code": 0, "stdout": "All tests passed!", "stderr": ""}
    }
    mock_app.handle_task_command.return_value = mock_shell_result_dict

    task_result_obj = orchestrator._validate_code()

    assert task_result_obj is not None
    assert task_result_obj.status == "COMPLETE"
    assert task_result_obj.notes.get("exit_code") == 0
    assert "All tests passed!" in task_result_obj.content
    
    mock_app.handle_task_command.assert_called_once_with(
        "system:execute_shell_command",
        params={"command": "pytest my_tests"}
    )

def test_validate_code_tests_fail(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "pytest my_tests_fail")

    mock_shell_failure_dict = {
        "status": "COMPLETE", # The command itself completed
        "content": "1 test failed", 
        "notes": {"exit_code": 1, "stdout": "...", "stderr": "AssertionError: ..."}
    }
    mock_app.handle_task_command.return_value = mock_shell_failure_dict

    task_result_obj = orchestrator._validate_code()

    assert task_result_obj is not None
    assert task_result_obj.status == "COMPLETE" # Command ran, but tests failed
    assert task_result_obj.notes.get("exit_code") == 1
    assert "AssertionError" in task_result_obj.notes.get("stderr", "")
    mock_app.handle_task_command.assert_called_once()

def test_validate_code_shell_command_execution_fails(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "invalid_command")
    
    mock_shell_error_dict = {
        "status": "FAILED", 
        "content": "Command not found", 
        "notes": {"error": {"message": "Command not found"}}
    }
    mock_app.handle_task_command.return_value = mock_shell_error_dict
    
    task_result_obj = orchestrator._validate_code()

    assert task_result_obj is not None
    assert task_result_obj.status == "FAILED"
    assert "Command not found" in task_result_obj.content
    mock_app.handle_task_command.assert_called_once()

def test_validate_code_no_test_command(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", test_command="") # Empty test command
    
    task_result_obj = orchestrator._validate_code()
    
    assert task_result_obj is not None
    assert task_result_obj.status == "COMPLETE" # Phase completes by skipping
    assert "Validation skipped" in task_result_obj.content
    assert task_result_obj.notes.get("skipped_validation") is True
    mock_app.handle_task_command.assert_not_called()

def test_validate_code_app_call_exception(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "valid_test_cmd")
    mock_app.handle_task_command.side_effect = Exception("Shell task execution error")

    task_result_obj = orchestrator._validate_code()

    assert task_result_obj is not None
    assert task_result_obj.status == "FAILED"
    assert "Shell command execution task call failed: Shell task execution error" in task_result_obj.content
    assert task_result_obj.notes["error"]["type"] == "ORCHESTRATOR_EXCEPTION"
