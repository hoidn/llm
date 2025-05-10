import pytest
import json
from unittest.mock import MagicMock, patch
from src.orchestration.coding_workflow_orchestrator import CodingWorkflowOrchestrator
from src.system.models import DevelopmentPlan, TaskResult, CombinedAnalysisResult # Added CombinedAnalysisResult
from src.main import Application # Added Application for spec

# Mock Application for basic instantiation tests
@pytest.fixture
def mock_app():
    app = MagicMock(spec=Application) # Use spec for better mocking
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

def test_orchestrator_run_completes_with_stub_logic(mock_app): # Renamed for clarity
    """
    Test that the run() method completes using mocked phase methods
    to simulate the original stub logic.
    """
    orchestrator = CodingWorkflowOrchestrator(
        app=mock_app,
        initial_goal="Test Goal",
        initial_context="Test Context",
        test_command="pytest tests",
        max_retries=1
    )

    # Mock the internal phase methods to behave like the original stubs
    with patch.object(orchestrator, '_generate_plan', return_value=True) as mock_gen_plan, \
         patch.object(orchestrator, '_execute_code', return_value=TaskResult(status="COMPLETE", content="Simulated Aider diff", notes={"success": True})) as mock_exec_code, \
         patch.object(orchestrator, '_validate_code', return_value=TaskResult(status="COMPLETE", content="Simulated test output", notes={"exit_code": 0})) as mock_validate_code, \
         patch.object(orchestrator, '_analyze_iteration', return_value=CombinedAnalysisResult(verdict="SUCCESS", message="Simulated successful analysis")) as mock_analyze:

        # To simulate _generate_plan setting self.current_plan:
        orchestrator.current_plan = DevelopmentPlan(instructions="Dummy plan", files=["dummy.py"], test_command="dummy_cmd")

        result = orchestrator.run()

        assert result is not None
        assert orchestrator.overall_success is True
        assert result.get("status") == "COMPLETE"
        assert result.get("content") == "Simulated Aider diff" # This should now pass

        mock_gen_plan.assert_called_once()
        # If _generate_plan returns True and sets current_plan, these should be called
        mock_exec_code.assert_called_once()
        mock_validate_code.assert_called_once()
        mock_analyze.assert_called_once()

def test_generate_plan_success(mock_app):
    orchestrator = CodingWorkflowOrchestrator(
        app=mock_app,
        initial_goal="Test Goal Plan",
        initial_context="Test Context Plan",
        test_command="pytest tests", # test_command for orchestrator init
        max_retries=1
    )

    # mock_plan_data for this test should not include test_command if it's not expected from the LLM
    # The DevelopmentPlan model has test_command as optional.
    # If the LLM is not prompted to return it, it won't be in parsedContent.
    # The orchestrator's self.test_command is used by _validate_code, not set by _generate_plan.
    mock_plan_data = {"instructions": "Generated plan instructions", "files": ["file1.py", "file2.py"]}
    
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
    # The DevelopmentPlan's test_command will be None if not in mock_plan_data,
    # or it will take a default from the model if one is set.
    # Let's assert it's None if not provided by the LLM mock.
    assert orchestrator.current_plan.test_command is None


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
        "aider_automatic",
        params={"prompt": "Implement function foo", "editable_files": ["src/foo.py"]}
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
        "system_execute_shell_command",
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

# Tests for _analyze_iteration (Phase 5)

@pytest.fixture
def mock_aider_result_success(): # Removed self
    return TaskResult(status="COMPLETE", content="Aider diff good", notes={"success": True})

@pytest.fixture
def mock_aider_result_failure(): # Removed self
    return TaskResult(status="FAILED", content="Aider execution error", notes={})

@pytest.fixture
def mock_test_result_pass(): # Removed self
    return TaskResult(status="COMPLETE", content="Tests passed!", notes={"exit_code": 0, "stdout": "PASSED", "stderr": ""})

@pytest.fixture
def mock_test_result_fail(): # Removed self
    return TaskResult(status="COMPLETE", content="Tests failed!", notes={"exit_code": 1, "stdout": "FAILED", "stderr": "AssertionError"})

def test_analyze_iteration_suggests_success(mock_app, mock_aider_result_success, mock_test_result_pass):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "test_cmd", 3)
    orchestrator.iteration = 1
    orchestrator.current_plan = DevelopmentPlan(instructions="Plan A", files=["a.py"], test_command="test_cmd")

    mock_analysis_data = {"verdict": "SUCCESS", "message": "All good!"}
    mock_app.handle_task_command.return_value = {
        "status": "COMPLETE", 
        "parsedContent": mock_analysis_data
    }

    analysis_decision = orchestrator._analyze_iteration(mock_aider_result_success, mock_test_result_pass)

    assert analysis_decision is not None
    assert analysis_decision.verdict == "SUCCESS"
    mock_app.handle_task_command.assert_called_once()
    
    # Corrected access to call arguments
    called_identifier = mock_app.handle_task_command.call_args[0][0]
    called_params_dict = mock_app.handle_task_command.call_args[1]['params']
    
    assert called_identifier == "user:evaluate-and-retry-analysis"
    assert called_params_dict["aider_status"] == "COMPLETE"
    assert called_params_dict["test_exit_code"] == 0

def test_analyze_iteration_suggests_retry(mock_app, mock_aider_result_success, mock_test_result_fail):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "test_cmd", 3)
    orchestrator.iteration = 1
    orchestrator.current_plan = DevelopmentPlan(instructions="Plan A", files=["a.py"], test_command="test_cmd")

    mock_analysis_data = {
        "verdict": "RETRY", 
        "next_prompt": "Try fixing X", 
        "next_files": ["a.py", "b.py"],
        "message": "Tests failed, suggest retry."
    }
    mock_app.handle_task_command.return_value = {
        "status": "COMPLETE",
        "parsedContent": mock_analysis_data
    }
    
    analysis_decision = orchestrator._analyze_iteration(mock_aider_result_success, mock_test_result_fail)

    assert analysis_decision is not None
    assert analysis_decision.verdict == "RETRY"
    assert analysis_decision.next_prompt == "Try fixing X"
    assert analysis_decision.next_files == ["a.py", "b.py"]
    mock_app.handle_task_command.assert_called_once()
    
    # Corrected access to call arguments
    called_params_dict = mock_app.handle_task_command.call_args[1]['params']
    assert called_params_dict["test_exit_code"] == 1


def test_analyze_iteration_suggests_failure(mock_app, mock_aider_result_failure, mock_test_result_fail):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "test_cmd", 3)
    orchestrator.iteration = 3 # Simulate max retries
    orchestrator.current_plan = DevelopmentPlan(instructions="Plan A", files=["a.py"], test_command="test_cmd")

    mock_analysis_data = {"verdict": "FAILURE", "message": "Too many retries or unfixable."}
    mock_app.handle_task_command.return_value = {
        "status": "COMPLETE",
        "parsedContent": mock_analysis_data
    }
    
    analysis_decision = orchestrator._analyze_iteration(mock_aider_result_failure, mock_test_result_fail)

    assert analysis_decision is not None
    assert analysis_decision.verdict == "FAILURE"
    mock_app.handle_task_command.assert_called_once()

    # Corrected access to call arguments
    called_params_dict = mock_app.handle_task_command.call_args[1]['params']
    assert called_params_dict["aider_status"] == "FAILED"

def test_analyze_iteration_llm_task_fails(mock_app, mock_aider_result_success, mock_test_result_pass):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "test_cmd", 3)
    orchestrator.iteration = 1
    orchestrator.current_plan = DevelopmentPlan(instructions="Plan A", files=["a.py"], test_command="test_cmd")

    mock_app.handle_task_command.return_value = {
        "status": "FAILED",
        "content": "Analysis LLM unavailable",
        "parsedContent": None
    }
    
    analysis_decision = orchestrator._analyze_iteration(mock_aider_result_success, mock_test_result_pass)
    
    assert analysis_decision is None
    assert orchestrator.final_loop_result is not None
    assert orchestrator.final_loop_result["reason"] == "Analysis task failed"

def test_analyze_iteration_llm_returns_invalid_verdict_structure(mock_app, mock_aider_result_success, mock_test_result_pass):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "test_cmd", 3)
    orchestrator.iteration = 1
    orchestrator.current_plan = DevelopmentPlan(instructions="Plan A", files=["a.py"], test_command="test_cmd")

    mock_invalid_analysis_data = {"bad_key": "WRONG_VERDICT", "message": "LLM misunderstood schema"}
    mock_app.handle_task_command.return_value = {
        "status": "COMPLETE",
        "parsedContent": mock_invalid_analysis_data 
    }
    
    analysis_decision = orchestrator._analyze_iteration(mock_aider_result_success, mock_test_result_pass)
    
    assert analysis_decision is None # Parsing CombinedAnalysisResult will fail
    assert orchestrator.final_loop_result is not None
    assert orchestrator.final_loop_result["reason"] == "Analysis task call/parsing failed" # Due to Pydantic validation

# Tests for run() method (Phase 6)

def test_run_success_first_iteration(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "test_cmd", 3)

    with patch.object(orchestrator, '_generate_plan', return_value=True) as mock_gen_plan, \
         patch.object(orchestrator, '_execute_code') as mock_exec_code, \
         patch.object(orchestrator, '_validate_code') as mock_validate_code, \
         patch.object(orchestrator, '_analyze_iteration') as mock_analyze:
        
        orchestrator.current_plan = DevelopmentPlan(instructions="Initial", files=["f.py"], test_command="cmd")

        mock_exec_code.return_value = TaskResult(status="COMPLETE", content="Aider V1", notes={})
        mock_validate_code.return_value = TaskResult(status="COMPLETE", content="Tests Pass V1", notes={"exit_code": 0})
        mock_analyze.return_value = CombinedAnalysisResult(verdict="SUCCESS", message="Great success!")

        result = orchestrator.run()

        assert result.get("status") == "COMPLETE"
        assert result.get("content") == "Aider V1"
        assert orchestrator.overall_success is True
        assert orchestrator.iteration == 1
        mock_gen_plan.assert_called_once()
        mock_exec_code.assert_called_once()
        mock_validate_code.assert_called_once()
        mock_analyze.assert_called_once()

def test_run_one_retry_then_success(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "test_cmd", 3)

    with patch.object(orchestrator, '_generate_plan', return_value=True) as mock_gen_plan, \
         patch.object(orchestrator, '_execute_code') as mock_exec_code, \
         patch.object(orchestrator, '_validate_code') as mock_validate_code, \
         patch.object(orchestrator, '_analyze_iteration') as mock_analyze:

        orchestrator.current_plan = DevelopmentPlan(instructions="Initial Plan", files=["f.py"], test_command="cmd")

        mock_exec_code.side_effect = [
            TaskResult(status="COMPLETE", content="Aider V1 Output", notes={}), 
            TaskResult(status="COMPLETE", content="Aider V2 Output", notes={})
        ]
        mock_validate_code.side_effect = [
            TaskResult(status="COMPLETE", content="Tests Fail V1", notes={"exit_code": 1, "stderr": "Fail"}),
            TaskResult(status="COMPLETE", content="Tests Pass V2", notes={"exit_code": 0})
        ]
        mock_analyze.side_effect = [
            CombinedAnalysisResult(verdict="RETRY", next_prompt="Revised Plan", next_files=["f_rev.py"], message="Try again"),
            CombinedAnalysisResult(verdict="SUCCESS", message="Now it works!")
        ]
        
        result = orchestrator.run()

        assert result.get("status") == "COMPLETE"
        assert result.get("content") == "Aider V2 Output"
        assert orchestrator.overall_success is True
        assert orchestrator.iteration == 2
        assert mock_exec_code.call_count == 2
        assert mock_validate_code.call_count == 2
        assert mock_analyze.call_count == 2
        assert orchestrator.current_plan.instructions == "Revised Plan"
        assert orchestrator.current_plan.files == ["f_rev.py"]


def test_run_max_retries_then_fail(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "test_cmd", max_retries=2)

    with patch.object(orchestrator, '_generate_plan', return_value=True) as mock_gen_plan, \
         patch.object(orchestrator, '_execute_code', return_value=TaskResult(status="COMPLETE", content="Aider Output", notes={})) as mock_exec_code, \
         patch.object(orchestrator, '_validate_code', return_value=TaskResult(status="COMPLETE", content="Tests Fail", notes={"exit_code": 1})) as mock_validate_code, \
         patch.object(orchestrator, '_analyze_iteration') as mock_analyze:
        
        orchestrator.current_plan = DevelopmentPlan(instructions="Initial", files=["f.py"], test_command="cmd")
        
        mock_analyze.return_value = CombinedAnalysisResult(verdict="RETRY", next_prompt="Revised Plan", next_files=["f.py"], message="Try again")
        
        result = orchestrator.run()

        assert result.get("status") == "FAILED"
        assert result.get("reason") == "Max retries reached"
        assert orchestrator.overall_success is False
        assert orchestrator.iteration == 2 
        assert mock_exec_code.call_count == 2
        assert mock_validate_code.call_count == 2
        assert mock_analyze.call_count == 2

def test_run_initial_plan_generation_fails(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "test_cmd", 3)
    with patch.object(orchestrator, '_generate_plan', return_value=False) as mock_gen_plan, \
         patch.object(orchestrator, '_execute_code') as mock_exec_code: # Also mock other phases to check not called
        
        orchestrator.final_loop_result = {"status": "FAILED", "reason": "Initial planning failed (mocked)"}
        
        result = orchestrator.run()
        
        assert result.get("status") == "FAILED"
        assert "Initial planning failed" in result.get("reason", "")
        mock_gen_plan.assert_called_once()
        mock_exec_code.assert_not_called()

def test_run_analysis_suggests_direct_failure(mock_app):
    orchestrator = CodingWorkflowOrchestrator(mock_app, "g", "c", "test_cmd", 3)
    with patch.object(orchestrator, '_generate_plan', return_value=True) as mock_gen_plan, \
         patch.object(orchestrator, '_execute_code', return_value=TaskResult(status="COMPLETE", content="Aider V1", notes={})) as mock_exec_code, \
         patch.object(orchestrator, '_validate_code', return_value=TaskResult(status="COMPLETE", content="Tests Fail V1", notes={"exit_code": 1})) as mock_validate_code, \
         patch.object(orchestrator, '_analyze_iteration') as mock_analyze:

        orchestrator.current_plan = DevelopmentPlan(instructions="Initial", files=["f.py"], test_command="cmd")
        analysis_failure_data = CombinedAnalysisResult(verdict="FAILURE", message="Cannot proceed, fundamental issue.")
        mock_analyze.return_value = analysis_failure_data
        
        result = orchestrator.run()

        assert result.get("status") == "FAILED"
        assert result.get("reason") == "Analysis verdict: FAILURE"
        assert result.get("details") == "Cannot proceed, fundamental issue."
        assert result.get("analysis_data") == analysis_failure_data.model_dump()
        assert orchestrator.iteration == 1
        mock_analyze.assert_called_once()
