"""
Unit tests for the AtomicTaskExecutor.
"""

import pytest
from unittest.mock import MagicMock, call # Use MagicMock for flexibility
from src.executors.atomic_executor import AtomicTaskExecutor, ParameterMismatchError
from src.system.models import TaskResult, TaskFailureError # Assuming TaskResult model

# If BaseHandler is importable and stable, use spec for better mocking
# from src.handler.base_handler import BaseHandler

@pytest.fixture
def mock_handler(mocker):
    """Fixture for a mocked BaseHandler."""
    # mock = mocker.MagicMock(spec=BaseHandler) # Use spec if BaseHandler is available
    mock = MagicMock() # Use basic MagicMock otherwise
    # Configure mock methods used by the executor
    mock._build_system_prompt.return_value = "Mocked System Prompt"
    # Configure _execute_llm_call to return a TaskResult object by default
    mock._execute_llm_call.return_value = TaskResult(status="COMPLETE", content="Mock LLM Response", notes={})
    return mock

@pytest.fixture
def executor():
    """Fixture for the AtomicTaskExecutor instance."""
    return AtomicTaskExecutor()

# --- Test Cases ---

def test_execute_body_success(executor, mock_handler):
    """Verify successful execution with parameter substitution."""
    task_def = {
        "name": "test_task",
        "type": "atomic",
        "subtype": "standard",
        "instructions": "Do something with {{input_val}}.",
        "system": "System prompt for {{input_val}}",
        # "params" key in task_def is for definition, not used by executor directly
        # Add model or output_format if needed for the test
    }
    params = {"input_val": "test_value"} # These are the runtime values

    # Act
    result_dict = executor.execute_body(task_def, params, mock_handler)
    result = TaskResult.model_validate(result_dict) # Validate dict against model

    # Assert
    assert result.status == "COMPLETE"
    assert result.content == "Mock LLM Response"
    # Check that handler methods were called with substituted values
    mock_handler._build_system_prompt.assert_called_once_with(
        template="System prompt for test_value", # Check substituted system template
        file_context=None # Executor passes None for file_context
    )
    mock_handler._execute_llm_call.assert_called_once_with(
        prompt="Do something with test_value.", # Check substituted main prompt
        system_prompt_override="Mocked System Prompt", # Result from _build_system_prompt
        tools_override=None, # Executor doesn't pass tools
        output_type_override=None, # Adjust if task_def specifies output
        # Add checks for model_override if applicable and supported by handler
    )

def test_execute_body_missing_param(executor, mock_handler):
    """Verify failure when a required parameter is missing during substitution."""
    task_def = {
        "name": "test_task_fail",
        "type": "atomic",
        "subtype": "standard",
        "instructions": "Requires {{missing_param}} and {{input_val}}.",
    }
    params = {"input_val": "value"} # Does not contain 'missing_param'

    # Act
    result_dict = executor.execute_body(task_def, params, mock_handler)
    result = TaskResult.model_validate(result_dict) # Validate dict against model

    # Assert
    assert result.status == "FAILED"
    # Check content and error details
    expected_error_content = "Unexpected substitution error: Missing parameter(s) or access error for substitution: missing_param"
    assert result.content == expected_error_content # Check exact content
    assert result.notes is not None
    assert "error" in result.notes
    error_details = TaskFailureError.model_validate(result.notes["error"])
    assert error_details.type == "TASK_FAILURE"
    assert error_details.reason == "input_validation_failure"
    # Check the message within the error notes structure
    assert error_details.message == expected_error_content
    # Ensure handler was NOT called
    mock_handler._build_system_prompt.assert_not_called()
    mock_handler._execute_llm_call.assert_not_called()

def test_execute_body_handler_fails(executor, mock_handler):
    """Verify failure propagation when the handler's LLM call fails."""
    # Configure mock handler to return a FAILED TaskResult object
    failed_error_details = TaskFailureError(type="TASK_FAILURE", reason="llm_error", message="LLM API Error")
    mock_handler._execute_llm_call.return_value = TaskResult(
        status="FAILED",
        content="LLM API Error",
        notes={"error": failed_error_details.model_dump(exclude_none=True)}
    )

    task_def = {"name": "test_task", "instructions": "Run this."}
    params = {}

    # Act
    result_dict = executor.execute_body(task_def, params, mock_handler)
    result = TaskResult.model_validate(result_dict) # Validate dict

    # Assert
    assert result.status == "FAILED"
    assert result.content == "LLM API Error"
    assert result.notes is not None
    assert "error" in result.notes
    error_details = TaskFailureError.model_validate(result.notes["error"])
    assert error_details.reason == "llm_error" # Propagated error

def test_execute_body_json_parsing_success(executor, mock_handler):
    """Verify successful JSON parsing when specified and output is valid JSON."""
    # Configure handler to return valid JSON string content
    mock_handler._execute_llm_call.return_value = TaskResult(
        status="COMPLETE", content='{"key": "value", "num": 123}', notes={}
    )
    task_def = {
        "name": "test_json",
        "instructions": "Output JSON.",
        "output_format": {"type": "json"} # Specify JSON output
    }
    params = {}

    # Act
    result_dict = executor.execute_body(task_def, params, mock_handler)
    result = TaskResult.model_validate(result_dict) # Validate dict

    # Assert
    assert result.status == "COMPLETE"
    assert result.content == '{"key": "value", "num": 123}' # Original content remains
    assert result.parsedContent == {"key": "value", "num": 123} # Parsed content added
    assert "parseError" not in result.notes

def test_execute_body_json_parsing_failure(executor, mock_handler):
    """Verify parseError note when JSON parsing fails due to invalid content."""
    # Configure handler to return non-JSON string content
    mock_handler._execute_llm_call.return_value = TaskResult(
        status="COMPLETE", content='This is not JSON', notes={}
    )
    task_def = {
        "name": "test_bad_json",
        "instructions": "Output bad JSON.",
        "output_format": {"type": "json"}
    }
    params = {}

    # Act
    result_dict = executor.execute_body(task_def, params, mock_handler)
    result = TaskResult.model_validate(result_dict) # Validate dict

    # Assert
    assert result.status == "COMPLETE" # Still COMPLETE as LLM finished
    assert result.content == 'This is not JSON'
    assert result.parsedContent is None
    assert "parseError" in result.notes
    assert "JSONDecodeError" in result.notes["parseError"]

def test_execute_body_no_instructions(executor, mock_handler):
    """Verify execution proceeds with empty prompt if instructions are missing/empty."""
    task_def = {
        "name": "test_no_instructions",
        "instructions": None, # Or ""
        "system": "System prompt."
    }
    params = {}

    # Act
    result_dict = executor.execute_body(task_def, params, mock_handler)
    result = TaskResult.model_validate(result_dict)

    # Assert
    assert result.status == "COMPLETE"
    mock_handler._build_system_prompt.assert_called_once_with(
        template="System prompt.", file_context=None
    )
    mock_handler._execute_llm_call.assert_called_once_with(
        prompt="", # Check that prompt is empty string
        system_prompt_override="Mocked System Prompt",
        tools_override=None,
        output_type_override=None,
    )
