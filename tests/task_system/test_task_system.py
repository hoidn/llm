"""
Unit tests for the TaskSystem class.
Focuses on logic implemented in Phase 1, Set B and Phase 2c.
"""

import pytest
import logging
import json
from unittest.mock import patch, MagicMock, ANY

# Assuming TaskSystem is importable
from src.task_system.task_system import TaskSystem, MATCH_THRESHOLD

# Import necessary types and dependencies for testing
from src.memory.memory_system import MemorySystem # For type hint/mocking
from src.handler.base_handler import BaseHandler # For type hint/mocking
from src.system.models import (
    SubtaskRequest, TaskResult, ContextManagement,
    ContextGenerationInput, AssociativeMatchResult, MatchTuple, # Added MatchTuple, AssociativeMatchResult
    SUBTASK_CONTEXT_DEFAULTS, TaskError, TaskFailureError, # Added TaskFailureError
    # Import new models for integration tests
    DevelopmentPlan, FeedbackResult
)
from pydantic import ValidationError as PydanticValidationError # Renamed import
# Import the executor and its error for testing
from src.executors.atomic_executor import AtomicTaskExecutor, ParameterMismatchError
# Import templates defined in main for registration
from src.main import GENERATE_PLAN_TEMPLATE, ANALYZE_AIDER_RESULT_TEMPLATE

# Example valid template structure
VALID_ATOMIC_TEMPLATE = {
    "name": "test_atomic_task",
    "type": "atomic",
    "subtype": "standard", # Changed to standard for default context test
    "description": "A test task",
    "instructions": "Do the test task with {{input1}}.", # Added instruction for substitution test
    "system": "System prompt for {{input1}}.", # Added system prompt for substitution test
    "params": {"param1": "string"}, # Kept for legacy validation, not used by executor directly
    "context_management": {"inheritContext": "none", "freshContext": "enabled"}, # Example settings
    "inputs": {"input1": "desc"}, # Added inputs to match test
    "file_paths_source": {"type": "literal", "path": []} # Added default empty file source
}

VALID_COMPOSITE_TEMPLATE = {
    "name": "test_composite_task",
    "type": "composite",  # Non-atomic type
    "subtype": "test_composite_subtype",
    "description": "A composite task",
    "params": {},
}

# Mock AtomicTaskExecutor removed - now patching the imported class

# --- Fixtures ---

@pytest.fixture
def mock_memory_system():
    """Provides a mock MemorySystem."""
    # Add spec for better mocking if MemorySystem class is available
    mock = MagicMock(spec=MemorySystem)
    # Mock methods used by TaskSystem
    # Default return for general context calls
    mock.get_relevant_context_for.return_value = AssociativeMatchResult(context_summary="Mock context", matches=[], error=None)
    # Default return for description-based calls (can be overridden in tests)
    mock.get_relevant_context_with_description.return_value = AssociativeMatchResult(context_summary="Mock desc context", matches=[], error=None)
    return mock

@pytest.fixture
def mock_handler():
    """Provides a mock BaseHandler."""
    # Add spec for better mocking if BaseHandler class is available
    handler = MagicMock(spec=BaseHandler)
    # Mock the command execution method used by resolve_file_paths
    handler.execute_file_path_command.return_value = ["/mock/command/path.py"] # Default return
    # Mock the methods used by AtomicTaskExecutor
    handler._build_system_prompt.side_effect = lambda template, file_context: f"BaseSysPrompt+{template or ''}+{file_context or ''}"
    # Mock _execute_llm_call to return a TaskResult-like dictionary
    # Ensure the mock returns a valid TaskResult object or dict that passes validation
    handler._execute_llm_call.return_value = TaskResult(content="LLM Result", status="COMPLETE", notes={}) # Return TaskResult obj
    return handler


@pytest.fixture
def task_system_instance(mock_memory_system, mock_handler):
    """Provides a TaskSystem instance with mock dependencies."""
    ts = TaskSystem(memory_system=mock_memory_system)
    # Inject mock handler using the public setter method
    ts.set_handler(mock_handler)
    return ts


# --- Test __init__ ---


def test_init(mock_memory_system):
    """Test initialization sets defaults correctly."""
    ts = TaskSystem(memory_system=mock_memory_system)
    assert ts.memory_system == mock_memory_system
    assert hasattr(ts, '_registry')
    assert ts._registry.templates == {}
    assert ts._registry.template_index == {}
    assert ts._test_mode is False
    assert hasattr(ts, '_handler') # Check for the new attribute name
    assert ts._handler is None     # Assert it's None if not passed during init


# --- Test set_test_mode ---


def test_set_test_mode(task_system_instance):
    """Test enabling and disabling test mode."""
    assert task_system_instance._test_mode is False
    # _handler_cache attribute no longer exists, remove assertions about it

    task_system_instance.set_test_mode(True)
    assert task_system_instance._test_mode is True

    task_system_instance.set_test_mode(False)
    assert task_system_instance._test_mode is False


# --- Test register_template ---


@patch('src.task_system.template_registry.TemplateRegistry.register')
def test_task_system_register_delegates(mock_register, task_system_instance):
    """Test that TaskSystem.register_template delegates to TemplateRegistry.register."""
    template = {"some": "template"}
    task_system_instance.register_template(template)
    mock_register.assert_called_once_with(template)

@patch('src.task_system.template_registry.TemplateRegistry.find')
def test_task_system_find_delegates(mock_find, task_system_instance):
    """Test that TaskSystem.find_template delegates to TemplateRegistry.find."""
    identifier = "test_id"
    expected_template = {"found": "template"}
    mock_find.return_value = expected_template
    result = task_system_instance.find_template(identifier)
    mock_find.assert_called_once_with(identifier)
    assert result == expected_template


# --- Tests for execute_atomic_template (Phase 2c) ---

@patch.object(TaskSystem, 'find_template')
# @patch.object(MemorySystem, 'get_relevant_context_for') # No longer needed directly here
@patch.object(TaskSystem, 'resolve_file_paths') # Mock file path resolution
@patch.object(AtomicTaskExecutor, 'execute_body')
def test_execute_atomic_template_success_flow(
    mock_execute_body, # Renamed from MockExecutorClass
    mock_resolve_files, mock_find_template, # Order might change based on decorator stack
    task_system_instance, mock_memory_system, mock_handler # Fixtures
):
    """Verify the successful execution flow of an atomic template."""
    # Arrange
    template_name = "test_atomic_task"
    # Use the VALID_ATOMIC_TEMPLATE defined above
    mock_template_def = VALID_ATOMIC_TEMPLATE.copy()
    mock_find_template.return_value = mock_template_def

    # Ensure the mock returns a dict that passes TaskResult validation
    mock_execute_body.return_value = TaskResult(
        content=f"Executed {template_name}", status="COMPLETE", notes={}
    ).model_dump() # Executor returns dict

    resolved_paths = ["/resolved/path.txt"]
    mock_resolve_files.return_value = (resolved_paths, None) # Simulate file path resolution

    request = SubtaskRequest(
        task_id="exec-success-1",
        type="atomic", name=template_name, description="Do test", # Added name, type, desc
        inputs={"input1": "value1"},
        context_management=None, # Use template/defaults
        file_paths=None # Let template/resolution handle files
    )

    # Act
    final_result = task_system_instance.execute_atomic_template(request) # Returns TaskResult object

    # Assert
    mock_find_template.assert_called_once_with(template_name)
    # Check if resolve_file_paths was called because request.file_paths is None and template has freshContext enabled
    mock_resolve_files.assert_called_once_with(mock_template_def, mock_memory_system, mock_handler)

    # Verify call signature matches the IDL
    mock_execute_body.assert_called_once_with(
        atomic_task_def=mock_template_def,
        params=request.inputs,
        handler=mock_handler # Check handler was passed
    )

    # Check final result (TaskResult object)
    assert isinstance(final_result, TaskResult)
    assert final_result.status == "COMPLETE"
    assert final_result.content == f"Executed {template_name}"
    assert final_result.notes.get("template_used") == template_name
    # Check context source note based on resolve_file_paths call
    # Use get() with default for safer access
    file_paths_source_dict = mock_template_def.get("file_paths_source", {})
    expected_context_source = file_paths_source_dict.get("type", "template_literal")
    assert final_result.notes.get("context_source") == expected_context_source
    assert final_result.notes.get("file_count") == len(resolved_paths)


@patch.object(TaskSystem, 'find_template')
def test_execute_atomic_template_not_found(mock_find_template, task_system_instance):
    """Test execute_atomic_template when template is not found."""
    # Arrange
    mock_find_template.return_value = None
    request = SubtaskRequest(task_id="not-found-1", type="atomic", name="not_a_task", description="", inputs={})

    # Act
    result = task_system_instance.execute_atomic_template(request)

    # Assert
    assert result.status == "FAILED"
    assert result.notes and result.notes.get("error")
    assert isinstance(result.notes["error"], TaskError) # Check it's a TaskError object
    assert result.notes["error"].reason == "template_not_found"
    assert "Template not found" in result.content


def test_execute_atomic_template_invalid_context_config(task_system_instance):
    """Test execute_atomic_template with conflicting context settings."""
    # Arrange
    template_name = "conflict_task"
    mock_template_def = {
        "name": template_name, "type": "atomic", "subtype": "standard", "description": "Test",
        "context_management": {"inheritContext": "full", "freshContext": "enabled"}, # Conflicting
        "params": {}, "inputs": {}
    }
    task_system_instance.register_template(mock_template_def) # Register directly

    request = SubtaskRequest(task_id="conflict-1", type="atomic", name=template_name, description="", inputs={})

    # Act
    result = task_system_instance.execute_atomic_template(request)

    # Assert
    assert result.status == "FAILED"
    assert result.notes and result.notes.get("error")
    assert isinstance(result.notes["error"], TaskError)
    assert result.notes["error"].reason == "input_validation_failure"
    assert "Context validation failed" in result.notes["error"].message


@patch.object(TaskSystem, 'find_template')
# @patch.object(MemorySystem, 'get_relevant_context_for') # No longer needed
@patch.object(TaskSystem, 'resolve_file_paths')
@patch.object(AtomicTaskExecutor, 'execute_body')
def test_execute_atomic_template_executor_fails(
    mock_execute_body, # Renamed from MockExecutorClass
    mock_resolve_files, mock_find_template, # Order might change
    task_system_instance, mock_memory_system, mock_handler
):
    """Test execute_atomic_template when the executor raises an exception."""
    # Arrange
    template_name = "fail_exec_task"
    mock_template_def = VALID_ATOMIC_TEMPLATE.copy()
    mock_template_def["name"] = template_name
    mock_find_template.return_value = mock_template_def

    # Simulate executor raising an exception (NOT ParameterMismatchError)
    mock_execute_body.side_effect = ValueError("Executor boom!")

    mock_resolve_files.return_value = ([], None)

    request = SubtaskRequest(task_id="exec-fail-1", type="atomic", name=template_name, description="", inputs={"input1": "dummy_value"}) # Add dummy input

    # Act
    result = task_system_instance.execute_atomic_template(request)

    # Assert
    assert result.status == "FAILED"
    assert result.notes and result.notes.get("error")
    assert result.notes["error"]["type"] == "TASK_FAILURE"
    assert result.notes["error"]["reason"] == "unexpected_error" # As the side_effect is ValueError
    assert "Executor boom!" in result.notes["error"]["message"]
    # Check that the error message includes the exception from the executor
    assert "Execution failed: Executor boom!" in result.content


@patch('src.task_system.task_system.AtomicTaskExecutor', new_callable=MagicMock)
@patch.object(TaskSystem, 'find_template')
# @patch.object(MemorySystem, 'get_relevant_context_for') # No longer needed
@patch.object(TaskSystem, 'resolve_file_paths')
def test_execute_atomic_template_executor_param_mismatch(
    mock_resolve_files, mock_find_template, MockExecutorClass,
    task_system_instance, mock_memory_system, mock_handler
):
    """Test execute_atomic_template when the executor raises ParameterMismatchError."""
    # Arrange
    template_name = "param_mismatch_task"
    mock_template_def = VALID_ATOMIC_TEMPLATE.copy()
    mock_template_def["name"] = template_name
    mock_find_template.return_value = mock_template_def

    mock_executor_instance = MockExecutorClass.return_value
    # Simulate executor raising ParameterMismatchError
    mismatch_error_msg = "Missing parameter for substitution: input1"
    # Set the side effect on the *instance*
    mock_executor_instance.execute_body.side_effect = ParameterMismatchError(mismatch_error_msg)

    mock_resolve_files.return_value = ([], None)

    # Request *without* the required 'input1'
    request = SubtaskRequest(task_id="param-mismatch-1", type="atomic", name=template_name, description="", inputs={})

    # Act
    result = task_system_instance.execute_atomic_template(request)

    # Assert
    assert result.status == "FAILED"
    assert result.notes and result.notes.get("error")
    error_details = TaskFailureError.model_validate(result.notes["error"]) # Validate error structure
    assert error_details.type == "TASK_FAILURE"
    assert error_details.reason == "input_validation_failure" # Check reason set by executor
    # Check that the wrapped error message contains the original error
    assert "Missing parameter(s) or access error for substitution: input1" in result.content
    # Remove the check for "Unexpected substitution error" as it's not the primary message anymore
    # assert "Unexpected substitution error" in result.content


# --- Tests for resolve_file_paths (Phase 2c) ---

@patch('src.task_system.task_system.resolve_paths_from_template')
def test_task_system_resolve_file_paths_delegates(mock_resolve_utility, task_system_instance, mock_memory_system, mock_handler):
    """Verify TaskSystem.resolve_file_paths delegates to the utility function."""
    template = {"name": "test_delegate"}
    expected_result = (["/delegated/path"], None)
    mock_resolve_utility.return_value = expected_result

    result = task_system_instance.resolve_file_paths(template, mock_memory_system, mock_handler)

    mock_resolve_utility.assert_called_once_with(template, mock_memory_system, mock_handler)
    assert result == expected_result


# --- Tests for find_matching_tasks (Phase 2c) ---

def test_find_matching_tasks_simple(task_system_instance):
    """Test basic matching and scoring (Adapt setup)."""
    # Arrange
    template1 = {"name": "task1", "type": "atomic", "subtype": "a", "description": "analyze python code", "params": {}}
    template4 = {"name": "task4", "type": "atomic", "subtype": "d", "description": "find python examples", "params": {}}
    # Mock the registry method used by find_matching_tasks
    with patch.object(task_system_instance._registry, 'get_all_atomic_templates', return_value=[template1, template4]) as mock_get_all:
        input_text = "analyze python script"
        # Act
        matches = task_system_instance.find_matching_tasks(input_text, None)
        # Assert
        mock_get_all.assert_called_once() # Verify registry was called
        assert len(matches) == 1 # Threshold is 0.6
        assert matches[0]["task"]["name"] == "task1"


def test_find_matching_tasks_no_match(task_system_instance):
    """Test when no templates match above the threshold."""
    template1 = {"name": "task1", "type": "atomic", "subtype": "a", "description": "analyze python code", "params": {}}
    # Mock the registry method
    with patch.object(task_system_instance._registry, 'get_all_atomic_templates', return_value=[template1]) as mock_get_all:
        input_text = "generate report for sales data" # Low similarity
        matches = task_system_instance.find_matching_tasks(input_text, None)
        mock_get_all.assert_called_once()
        assert len(matches) == 0 # Score should be below threshold


def test_find_matching_tasks_empty_input(task_system_instance):
    """Test with empty input text."""
    # No need to mock registry since empty input returns early
    matches = task_system_instance.find_matching_tasks("", None)
    assert len(matches) == 0


def test_find_matching_tasks_sorting(task_system_instance):
    """Test that results are sorted by score (Adapt setup)."""
    # Arrange
    template1 = {"name": "task1", "type": "atomic", "subtype": "a", "description": "short", "params": {}}
    template2 = {"name": "task2", "type": "atomic", "subtype": "b", "description": "medium length description", "params": {}}
    template3 = {"name": "task3", "type": "atomic", "subtype": "c", "description": "very long and detailed description", "params": {}}
    # Mock the registry method
    with patch.object(task_system_instance._registry, 'get_all_atomic_templates', return_value=[template1, template2, template3]) as mock_get_all:
        input_text = "a very long and detailed description query"
        # Act
        matches = task_system_instance.find_matching_tasks(input_text, None)
        # Assert
        mock_get_all.assert_called_once()
        assert len(matches) == 1 # Expecting only task3 with threshold 0.6
        assert matches[0]["task"]["name"] == "task3"


# --- Integration Tests for New Atomic Tasks ---

@patch.object(TaskSystem, 'find_template')
@patch.object(AtomicTaskExecutor, 'execute_body')
def test_execute_generate_plan_task(mock_execute_body, mock_find_template, task_system_instance, mock_handler):
    """Integration test for executing user:generate-plan task."""
    # Arrange
    # Mock find_template to return the template directly instead of relying on registration
    mock_find_template.return_value = GENERATE_PLAN_TEMPLATE

    # Mock the executor's behavior (which internally calls the handler)
    # Simulate the executor returning a dict representing the TaskResult
    expected_plan_data = {
        "instructions": "1. Refactor X.\n2. Add test.",
        "files": ["file1.py", "test_file1.py"],
        "test_command": "pytest tests/"
    }
    # Executor returns a dict, TaskSystem wraps it in TaskResult object
    mock_execute_body.return_value = TaskResult(
        content=json.dumps(expected_plan_data), # LLM raw output
        status="COMPLETE",
        parsedContent=expected_plan_data, # Simulate successful parsing by executor/handler
        notes={}
    ).model_dump() # Executor returns dict

    request = SubtaskRequest(
        task_id="plan-test-1",
        type="atomic",
        name="user:generate-plan",
        inputs={
            "user_prompts": "Refactor X and add tests.",
            "initial_context": "Context about X..."
        }
    )

    # Act
    result = task_system_instance.execute_atomic_template(request)

    # Assert
    mock_find_template.assert_called_once_with("user:generate-plan")
    mock_execute_body.assert_called_once()
    # Access kwargs instead of positional args
    call_kwargs = mock_execute_body.call_args.kwargs
    assert call_kwargs['atomic_task_def']['name'] == "user:generate-plan" # Check template passed
    assert call_kwargs['params'] == request.inputs # Check params passed
    assert call_kwargs['handler'] == mock_handler # Check handler passed

    assert result.status == "COMPLETE"
    # MODIFIED: Validate the dictionary against the Pydantic model
    assert isinstance(result.parsedContent, dict) # First check it's a dict
    try:
        plan = DevelopmentPlan.model_validate(result.parsedContent) # Validate structure
        assert plan.instructions == expected_plan_data["instructions"]
        assert plan.files == expected_plan_data["files"]
        assert plan.test_command == expected_plan_data["test_command"]
    except Exception as e:
        assert False, f"parsedContent failed DevelopmentPlan validation: {e}"
    assert result.notes.get("template_used") == "user:generate-plan"

@patch.object(TaskSystem, 'find_template')
@patch.object(AtomicTaskExecutor, 'execute_body')
def test_execute_analyze_aider_result_task(mock_execute_body, mock_find_template, task_system_instance, mock_handler):
    """Integration test for executing user:analyze-aider-result task."""
    # Arrange
    # Mock find_template to return the template directly instead of relying on registration
    mock_find_template.return_value = ANALYZE_AIDER_RESULT_TEMPLATE

    expected_feedback_data = {
        "status": "REVISE",
        "next_prompt": "Please handle the edge case where input is None.",
        "explanation": "Aider implementation missed a null check."
    }
    mock_execute_body.return_value = TaskResult(
        content=json.dumps(expected_feedback_data),
        status="COMPLETE",
        parsedContent=expected_feedback_data,
        notes={}
    ).model_dump()

    request = SubtaskRequest(
        task_id="analyze-test-1",
        type="atomic",
        name="user:analyze-aider-result",
        inputs={
            "aider_result_content": "Code generated, but missed null check.",
            "aider_result_status": "COMPLETE",
            "original_prompt": "Implement the function.",
            "iteration": 1,
            "max_retries": 3
        }
    )

    # Act
    result = task_system_instance.execute_atomic_template(request)

    # Assert
    mock_find_template.assert_called_once_with("user:analyze-aider-result")
    mock_execute_body.assert_called_once()
    # Access kwargs instead of positional args
    call_kwargs = mock_execute_body.call_args.kwargs
    assert call_kwargs['atomic_task_def']['name'] == "user:analyze-aider-result" # Check template passed
    assert call_kwargs['params'] == request.inputs # Check params passed
    assert call_kwargs['handler'] == mock_handler # Check handler passed

    assert result.status == "COMPLETE"
    # MODIFIED: Validate the dictionary against the Pydantic model
    assert isinstance(result.parsedContent, dict) # First check it's a dict
    try:
        feedback = FeedbackResult.model_validate(result.parsedContent) # Validate structure
        assert feedback.status == expected_feedback_data["status"]
        assert feedback.next_prompt == expected_feedback_data["next_prompt"]
        assert feedback.explanation == expected_feedback_data["explanation"]
    except Exception as e:
        assert False, f"parsedContent failed FeedbackResult validation: {e}"
    assert result.notes.get("template_used") == "user:analyze-aider-result"

@patch.object(AtomicTaskExecutor, 'execute_body')
def test_execute_task_llm_fails(mock_execute_body, task_system_instance, mock_handler):
    """Test task execution when the underlying LLM call (mocked via executor) fails."""
    # Arrange
    task_system_instance.register_template(GENERATE_PLAN_TEMPLATE)

    # Simulate executor returning a FAILED TaskResult dict
    fail_reason = "llm_error"
    fail_message = "LLM API connection timeout"
    error_obj = TaskFailureError(type="TASK_FAILURE", reason=fail_reason, message=fail_message)
    mock_execute_body.return_value = TaskResult(
        content=fail_message,
        status="FAILED",
        notes={"error": error_obj.model_dump()} # Pass error as dict
    ).model_dump() # Executor returns dict

    request = SubtaskRequest(
        task_id="plan-fail-1",
        type="atomic",
        name="user:generate-plan",
        inputs={"user_prompts": "...", "initial_context": "..."}
    )

    # Act
    result = task_system_instance.execute_atomic_template(request)

    # Assert
    mock_execute_body.assert_called_once()
    assert result.status == "FAILED"
    assert result.content == fail_message
    assert result.notes.get("template_used") == "user:generate-plan"
    assert result.notes.get("error") is not None
    # Validate the error structure returned by TaskSystem
    assert result.notes["error"]["type"] == "TASK_FAILURE"
    assert result.notes["error"]["reason"] == fail_reason
    assert result.notes["error"]["message"] == fail_message

@patch.object(AtomicTaskExecutor, 'execute_body')
def test_execute_task_invalid_json_output(mock_execute_body, task_system_instance, mock_handler):
    """Test task execution when LLM returns invalid JSON for a structured output task."""
    # Arrange
    task_system_instance.register_template(GENERATE_PLAN_TEMPLATE) # Expects DevelopmentPlan JSON

    # Simulate executor returning a TaskResult dict where parsing failed
    invalid_json_content = '{"instructions": "...", "files": [}' # Malformed JSON
    mock_execute_body.return_value = TaskResult(
        content=invalid_json_content,
        status="COMPLETE", # LLM call itself might complete
        parsedContent=None, # Parsing failed
        notes={"parseError": "JSONDecodeError: Expecting ']' delimiter..."} # Note indicating parse failure
    ).model_dump() # Executor returns dict

    request = SubtaskRequest(
        task_id="plan-json-fail-1",
        type="atomic",
        name="user:generate-plan",
        inputs={"user_prompts": "...", "initial_context": "..."}
    )

    # Act
    result = task_system_instance.execute_atomic_template(request)

    # Assert
    # TaskSystem currently passes through the result from the executor.
    # If the executor indicates parsing failed, the TaskResult reflects that.
    # Depending on desired behavior, TaskSystem *could* change status to FAILED here.
    # Current assertion reflects pass-through behavior:
    mock_execute_body.assert_called_once()
    assert result.status == "COMPLETE" # Status from executor is passed through
    assert result.content == invalid_json_content
    assert result.parsedContent is None
    assert result.notes.get("template_used") == "user:generate-plan"
    assert "parseError" in result.notes # Check the parse error note is present


# --- Remove Deferred Method Tests ---

# Remove or comment out tests like these if they existed:
# def test_execute_atomic_template_deferred(task_system_instance): ...
# def test_find_matching_tasks_deferred(task_system_instance, mock_memory_system): ...
# def test_generate_context_for_memory_system_deferred(task_system_instance): ...
# def test_resolve_file_paths_deferred(task_system_instance, mock_memory_system): ...
