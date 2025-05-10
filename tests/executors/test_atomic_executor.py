"""
Unit tests for the AtomicTaskExecutor.
"""

import pytest
import logging # Add import
from unittest.mock import MagicMock, call, patch, ANY # Use MagicMock for flexibility, add ANY
from src.executors.atomic_executor import AtomicTaskExecutor, ParameterMismatchError
from src.system.models import TaskResult, TaskFailureError, ModelNotFoundError, HistoryConfigSettings # Assuming TaskResult model, add HistoryConfigSettings
from pydantic import BaseModel # For testing output_type_override

# If BaseHandler is importable and stable, use spec for better mocking
# from src.handler.base_handler import BaseHandler

# Define a test Pydantic model (prefixed with underscore to avoid collection)
class _SampleOutputModel(BaseModel):
    name: str
    value: int

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
        prompt="Do something with test_value.",
        system_prompt_override="Mocked System Prompt", # Ensure this matches what _build_system_prompt returns
        tools_override=None,
        output_type_override=None,
        model_override=task_def.get("model"), # Will be None if not in task_def
        history_config=None 
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
    expected_error_content = "Missing parameter(s) or access error for substitution: missing_param"
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
        model_override=task_def.get("model"), # Will be None if not in task_def
        history_config=None 
    )

def test_substitute_large_dict_param(executor, mock_handler, caplog):
    """Test substitution with a dictionary parameter, check logging."""
    task_def = {"instructions": "Data: {{big_dict}}"}
    large_dict = {f"key_{i}": f"value_{i}" for i in range(5)}
    params = {"big_dict": large_dict}

    with caplog.at_level(logging.DEBUG):
        executor.execute_body(task_def, params, mock_handler)

    # Assert substitution happened (handler called with stringified dict)
    mock_handler._execute_llm_call.assert_called_once()
    call_args, call_kwargs = mock_handler._execute_llm_call.call_args
    assert str(large_dict) in call_kwargs['prompt']
    # Assert log message was generated
    assert f"Substituting 'big_dict': Type=<class 'dict'>, Size/Len={len(large_dict)}" in caplog.text

def test_substitute_large_string_param(executor, mock_handler, caplog):
    """Test substitution with a long string parameter, check logging."""
    task_def = {"instructions": "Metadata: {{long_meta}}"}
    long_string = "metadata " * 100
    params = {"long_meta": long_string}

    with caplog.at_level(logging.DEBUG):
        executor.execute_body(task_def, params, mock_handler)

    # Assert substitution happened
    mock_handler._execute_llm_call.assert_called_once()
    call_args, call_kwargs = mock_handler._execute_llm_call.call_args
    assert long_string in call_kwargs['prompt']
    # Assert log message was generated
    assert f"Substituting 'long_meta': Type=<class 'str'>, Size/Len={len(long_string)}" in caplog.text

# ----- New Tests for Pydantic Schema Output -----

@patch('src.executors.atomic_executor.resolve_model_class')
def test_execute_body_without_output_format_schema(mock_resolve_model_class, executor, mock_handler):
    """Test execute_body with template that has no output_format.schema."""
    # Arrange
    task_def = {
        "name": "test_no_schema",
        "instructions": "Just a basic task",
        "output_format": {"type": "json"}  # No schema defined
    }
    params = {}

    # Act
    executor.execute_body(task_def, params, mock_handler)

    # Assert
    # Verify resolve_model_class was NOT called (no schema to resolve)
    mock_resolve_model_class.assert_not_called()
    # Verify handler was called with output_type_override=None
    mock_handler._execute_llm_call.assert_called_once()
    _, kwargs = mock_handler._execute_llm_call.call_args
    assert kwargs.get('output_type_override') is None

@patch('src.executors.atomic_executor.resolve_model_class')
def test_execute_body_with_valid_output_format_schema(mock_resolve_model_class, executor, mock_handler):
    """Test execute_body with template that has a valid output_format.schema."""
    # Arrange
    task_def = {
        "name": "test_valid_schema",
        "instructions": "Return structured data",
        "output_format": {"type": "json", "schema": "_SampleOutputModel"} # Use renamed model
    }
    params = {}

    # Mock resolve_model_class to return our test model
    mock_resolve_model_class.return_value = _SampleOutputModel # Use renamed model

    # Act
    executor.execute_body(task_def, params, mock_handler)

    # Assert
    # Verify resolve_model_class was called with correct schema name
    mock_resolve_model_class.assert_called_once_with("_SampleOutputModel") # Use renamed model
    # Verify handler was called with output_type_override=_SampleOutputModel
    mock_handler._execute_llm_call.assert_called_once()
    _, kwargs = mock_handler._execute_llm_call.call_args
    assert kwargs.get('output_type_override') == _SampleOutputModel # Use renamed model

@patch('src.executors.atomic_executor.resolve_model_class')
def test_execute_body_with_handler_returning_parsed_content(mock_resolve_model_class, executor, mock_handler):
    """Test execute_body when handler returns parsed_content from pydantic-ai."""
    # Arrange
    task_def = {
        "name": "test_parsed_content",
        "instructions": "Return structured data",
        "output_format": {"type": "json", "schema": "_SampleOutputModel"} # Use renamed model
    }
    params = {}

    # Mock resolve_model_class to return our test model
    mock_resolve_model_class.return_value = _SampleOutputModel # Use renamed model

    # Create a parsed Pydantic model instance that handler would return
    model_instance = _SampleOutputModel(name="test", value=42) # Use renamed model

    # Configure mock handler to return both raw content and parsed_content
    # Note: The mock handler's _execute_llm_call needs to return a dict, not a TaskResult object directly
    # because the executor expects a dict from the handler call.
    mock_handler._execute_llm_call.return_value = {
        "success": True,
        "status": "COMPLETE",
        "content": '{"name": "test", "value": 42}',
        "parsed_content": model_instance,  # This would come from pydantic-ai
        "notes": {}
    }

    # Act
    result_dict = executor.execute_body(task_def, params, mock_handler)

    # Assert
    # Verify the parsed_content was moved to parsedContent in the result
    assert "parsedContent" in result_dict
    assert result_dict["parsedContent"] == model_instance
    # Verify parsed_content is removed from the result
    assert "parsed_content" not in result_dict

@patch('src.executors.atomic_executor.resolve_model_class')
def test_execute_body_with_model_not_found_error(mock_resolve_model_class, executor, mock_handler):
    """Test execute_body when resolve_model_class raises ModelNotFoundError."""
    # Arrange
    task_def = {
        "name": "test_model_not_found",
        "instructions": "Return structured data",
        "output_format": {"type": "json", "schema": "NonExistentModel"}
    }
    params = {}

    # Mock resolve_model_class to raise ModelNotFoundError
    error_msg = "Model class NonExistentModel not found in module src.system.models"
    mock_resolve_model_class.side_effect = ModelNotFoundError(error_msg)

    # Configure mock handler to return a basic success response (as a dict)
    mock_handler._execute_llm_call.return_value = {
        "success": True,
        "status": "COMPLETE",
        "content": "Some content",
        "notes": {}
    }

    # Act
    result_dict = executor.execute_body(task_def, params, mock_handler)

    # Assert
    # Verify handler was still called with output_type_override=None
    mock_handler._execute_llm_call.assert_called_once()
    _, kwargs = mock_handler._execute_llm_call.call_args
    assert kwargs.get('output_type_override') is None

    # Verify the task completed successfully despite the schema resolution error
    assert result_dict["status"] == "COMPLETE"
    # Verify a warning note was added to the result
    assert "schema_warning" in result_dict["notes"]
    assert error_msg in result_dict["notes"]["schema_warning"]

@patch('src.executors.atomic_executor.resolve_model_class')
def test_execute_body_with_handler_failure(mock_resolve_model_class, executor, mock_handler):
    """Test execute_body when handler returns a failure response."""
    # Arrange
    task_def = {
        "name": "test_handler_failure",
        "instructions": "This will fail",
        "output_format": {"type": "json", "schema": "_SampleOutputModel"} # Use renamed model
    }
    params = {}

    # Mock resolve_model_class to return our test model
    mock_resolve_model_class.return_value = _SampleOutputModel # Use renamed model

    # Configure mock handler to return a failure response (as a dict)
    error_details = TaskFailureError(type="TASK_FAILURE", reason="llm_error", message="LLM call failed")
    mock_handler._execute_llm_call.return_value = {
        "success": False, # Indicate failure
        "status": "FAILED",
        "content": "Error: LLM call failed",
        "notes": {"error": error_details.model_dump()}
    }

    # Act
    result_dict = executor.execute_body(task_def, params, mock_handler)

    # Assert
    # Verify result has FAILED status
    assert result_dict["status"] == "FAILED"
    # Verify error details were preserved
    assert "error" in result_dict["notes"]
    assert result_dict["notes"]["error"]["reason"] == "llm_error"
    assert "LLM call failed" in result_dict["notes"]["error"]["message"]

def test_execute_body_with_history_config(executor, mock_handler):
    """Verify history_config is passed to handler._execute_llm_call."""
    task_def = {
        "name": "test_history_task",
        "instructions": "Process with history config.",
    }
    params = {}
    custom_history_config = HistoryConfigSettings(
        use_session_history=False,
        history_turns_to_include=3,
        record_in_session_history=False
    )

    # Act
    executor.execute_body(task_def, params, mock_handler, history_config=custom_history_config)

    # Assert
    mock_handler._execute_llm_call.assert_called_once_with(
        prompt="Process with history config.",
        system_prompt_override="Mocked System Prompt",
        tools_override=None,
        output_type_override=None,
        model_override=None,
        history_config=custom_history_config # Check the custom config was passed
    )

def test_execute_body_default_history_config_is_none(executor, mock_handler):
    """Verify default history_config passed to handler is None if not provided to execute_body."""
    task_def = {
        "name": "test_default_history_task",
        "instructions": "Process with default history.",
    }
    params = {}

    # Act
    # Call execute_body without history_config argument
    executor.execute_body(task_def, params, mock_handler)

    # Assert
    mock_handler._execute_llm_call.assert_called_once_with(
        prompt="Process with default history.",
        system_prompt_override="Mocked System Prompt",
        tools_override=None,
        output_type_override=None,
        model_override=None,
        history_config=None # Expect None to be passed to handler
    )
