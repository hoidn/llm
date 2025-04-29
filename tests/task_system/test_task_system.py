"""
Unit tests for the TaskSystem class.
Focuses on logic implemented in Phase 1, Set B and Phase 2c.
"""

import pytest
import logging
import json
from unittest.mock import patch, MagicMock, ANY

# Assuming TaskSystem is importable
from src.task_system.task_system import TaskSystem

# Import necessary types and dependencies for testing
from src.memory.memory_system import MemorySystem # For type hint/mocking
from src.handler.base_handler import BaseHandler # For type hint/mocking
from src.system.models import (
    SubtaskRequest, TaskResult, ContextManagement,
    ContextGenerationInput, AssociativeMatchResult, MatchTuple, # Added MatchTuple, AssociativeMatchResult
    SUBTASK_CONTEXT_DEFAULTS, TaskError, TaskFailureError # Added TaskFailureError
)
from pydantic import ValidationError as PydanticValidationError # Renamed import
# Import the executor error for testing
from src.executors.atomic_executor import ParameterMismatchError

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
    # Inject mock handler into cache for _get_handler placeholder
    ts._handler_cache["default_handler"] = mock_handler
    return ts


# --- Test __init__ ---


def test_init(mock_memory_system):
    """Test initialization sets defaults correctly."""
    ts = TaskSystem(memory_system=mock_memory_system)
    assert ts.memory_system == mock_memory_system
    assert ts.templates == {}
    assert ts.template_index == {}
    assert ts._test_mode is False
    assert ts._handler_cache == {}


# --- Test set_test_mode ---


def test_set_test_mode(task_system_instance):
    """Test enabling and disabling test mode."""
    assert task_system_instance._test_mode is False
    # Check handler cache is initially populated by fixture
    assert task_system_instance._handler_cache != {}

    task_system_instance.set_test_mode(True)
    assert task_system_instance._test_mode is True
    # Check handler cache is cleared when mode changes
    assert task_system_instance._handler_cache == {}

    task_system_instance.set_test_mode(False)
    assert task_system_instance._test_mode is False
    assert task_system_instance._handler_cache == {}  # Should remain cleared


# --- Test register_template ---


def test_register_template_success(task_system_instance):
    """Test registering a valid atomic template."""
    template = VALID_ATOMIC_TEMPLATE.copy()
    task_system_instance.register_template(template)

    assert "test_atomic_task" in task_system_instance.templates
    assert task_system_instance.templates["test_atomic_task"] == template
    assert f"atomic:{template['subtype']}" in task_system_instance.template_index
    assert task_system_instance.template_index[f"atomic:{template['subtype']}"] == "test_atomic_task"


def test_register_template_missing_required_fields(task_system_instance, caplog):
    """Test registration fails if name or subtype is missing for an atomic template."""
    template_no_name = VALID_ATOMIC_TEMPLATE.copy()
    del template_no_name["name"]
    template_no_subtype = VALID_ATOMIC_TEMPLATE.copy()
    del template_no_subtype["subtype"]

    with caplog.at_level(logging.ERROR):
        # Test missing name (type is atomic)
        task_system_instance.register_template(template_no_name)
        assert (
            "Atomic template registration failed: Missing 'name' or 'subtype'"
            in caplog.text
        )
        assert "test_atomic_task" not in task_system_instance.templates # Check name wasn't registered partially
        caplog.clear()

        # Test missing subtype (type is atomic)
        task_system_instance.register_template(template_no_subtype)
        assert (
            "Atomic template registration failed: Missing 'name' or 'subtype'"
            in caplog.text
        )
        assert "test_atomic_task" not in task_system_instance.templates
        caplog.clear()


def test_register_template_non_atomic_warns(task_system_instance, caplog):
    """Test registering a non-atomic template logs a warning and is ignored."""
    template = VALID_COMPOSITE_TEMPLATE.copy()
    with caplog.at_level(logging.WARNING):
        task_system_instance.register_template(template)
        assert (
            f"Ignoring registration attempt for non-atomic template '{template['name']}'"
            in caplog.text
        )
        # Check it wasn't actually registered
        assert template["name"] not in task_system_instance.templates
        type_subtype_key = f"{template['type']}:{template['subtype']}"
        assert type_subtype_key not in task_system_instance.template_index


def test_register_template_missing_description_warns(task_system_instance, caplog):
    """Test registering an atomic template without 'description' logs a warning."""
    template = VALID_ATOMIC_TEMPLATE.copy()
    name = template["name"]
    del template["description"] # Remove description
    with caplog.at_level(logging.WARNING):
        task_system_instance.register_template(template)
        # --- Start Change: Assert exact log message ---
        assert f"Atomic template '{name}' registered without a 'description'." in caplog.text
        # --- End Change ---
    assert template["name"] in task_system_instance.templates  # Still registered


def test_register_template_overwrites(task_system_instance):
    """Test registering a template with the same name overwrites the previous one."""
    template1 = VALID_ATOMIC_TEMPLATE.copy()
    template1_subtype = template1["subtype"]
    template2 = VALID_ATOMIC_TEMPLATE.copy()
    template2["description"] = "Updated description"
    template2["subtype"] = "new_subtype"  # Change subtype to check index update

    task_system_instance.register_template(template1)
    assert task_system_instance.templates["test_atomic_task"]["description"] == "A test task"
    assert task_system_instance.template_index[f"atomic:{template1_subtype}"] == "test_atomic_task"
    assert "atomic:new_subtype" not in task_system_instance.template_index

    task_system_instance.register_template(template2)
    assert (
        task_system_instance.templates["test_atomic_task"]["description"]
        == "Updated description"
    )
    # Index should be updated to the new subtype for that name
    assert task_system_instance.template_index["atomic:new_subtype"] == "test_atomic_task"
    # --- Start Change: Assert old index key is removed ---
    assert f"atomic:{template1_subtype}" not in task_system_instance.template_index
    # --- End Change ---


# --- Test find_template ---


def test_find_template_by_name(task_system_instance):
    """Test finding an atomic template by its name."""
    template = VALID_ATOMIC_TEMPLATE.copy()
    task_system_instance.register_template(template)
    found = task_system_instance.find_template("test_atomic_task")
    assert found == template


def test_find_template_by_type_subtype(task_system_instance):
    """Test finding an atomic template by its type:subtype."""
    template = VALID_ATOMIC_TEMPLATE.copy()
    task_system_instance.register_template(template)
    found = task_system_instance.find_template(f"atomic:{template['subtype']}")
    assert found == template


def test_find_template_not_found(task_system_instance):
    """Test finding a non-existent template returns None."""
    assert task_system_instance.find_template("non_existent_task") is None
    assert task_system_instance.find_template("atomic:non_existent") is None


def test_find_template_ignores_non_atomic_by_name(task_system_instance):
    """Test find_template ignores non-atomic templates when searching by name."""
    atomic_template = VALID_ATOMIC_TEMPLATE.copy()
    composite_template = VALID_COMPOSITE_TEMPLATE.copy()
    # Give them the same name (unlikely but possible)
    composite_template["name"] = atomic_template["name"]

    task_system_instance.register_template(atomic_template)
    task_system_instance.register_template(composite_template)  # Attempt to register composite - should be ignored

    # Should find the atomic one when searching by name
    found = task_system_instance.find_template(atomic_template["name"])
    assert found is not None
    assert found["type"] == "atomic"
    assert found == atomic_template


def test_find_template_ignores_non_atomic_by_type_subtype(task_system_instance):
    """Test find_template ignores non-atomic templates when searching by type:subtype."""
    atomic_template = VALID_ATOMIC_TEMPLATE.copy()
    composite_template = VALID_COMPOSITE_TEMPLATE.copy()

    task_system_instance.register_template(atomic_template)
    task_system_instance.register_template(composite_template) # Attempt to register composite - should be ignored

    # Search for the composite type:subtype - should not be found by find_template
    # because register_template ignored it
    found = task_system_instance.find_template(
        f"{composite_template['type']}:{composite_template['subtype']}"
    )
    assert found is None

    # Search for the atomic type:subtype - should be found
    found = task_system_instance.find_template(
        f"atomic:{atomic_template['subtype']}"
    )
    assert found is not None
    assert found == atomic_template


# --- Tests for execute_atomic_template (Phase 2c) ---

# Patch the executor class where it's imported in the task_system module
@patch('src.task_system.task_system.AtomicTaskExecutor', new_callable=MagicMock)
@patch.object(TaskSystem, 'find_template')
# @patch.object(MemorySystem, 'get_relevant_context_for') # No longer needed directly here
@patch.object(TaskSystem, 'resolve_file_paths') # Mock file path resolution
def test_execute_atomic_template_success_flow(
    mock_resolve_files, mock_find_template, MockExecutorClass, # Patched executor class
    task_system_instance, mock_memory_system, mock_handler # Fixtures
):
    """Verify the successful execution flow of an atomic template."""
    # Arrange
    template_name = "test_atomic_task"
    # Use the VALID_ATOMIC_TEMPLATE defined above
    mock_template_def = VALID_ATOMIC_TEMPLATE.copy()
    mock_find_template.return_value = mock_template_def

    # Mock the executor instance and its method to return a dict
    mock_executor_instance = MockExecutorClass.return_value
    # Ensure the mock returns a dict that passes TaskResult validation
    mock_executor_instance.execute_body.return_value = TaskResult(
        content=f"Executed {template_name}", status="COMPLETE", notes={}
    ).model_dump() # Executor now returns dict

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

    # Check executor instantiation and call
    # MockExecutorClass.assert_called_once() # Check instantiation
    # Verify call signature matches the IDL on the *instance*
    mock_executor_instance.execute_body.assert_called_once_with(
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


@patch('src.task_system.task_system.AtomicTaskExecutor', new_callable=MagicMock)
@patch.object(TaskSystem, 'find_template')
# @patch.object(MemorySystem, 'get_relevant_context_for') # No longer needed
@patch.object(TaskSystem, 'resolve_file_paths')
def test_execute_atomic_template_executor_fails(
    mock_resolve_files, mock_find_template, MockExecutorClass,
    task_system_instance, mock_memory_system, mock_handler
):
    """Test execute_atomic_template when the executor raises an exception."""
    # Arrange
    template_name = "fail_exec_task"
    mock_template_def = VALID_ATOMIC_TEMPLATE.copy()
    mock_template_def["name"] = template_name
    mock_find_template.return_value = mock_template_def

    mock_executor_instance = MockExecutorClass.return_value
    # Simulate executor raising an exception (NOT ParameterMismatchError)
    mock_executor_instance.execute_body.side_effect = ValueError("Executor boom!")

    mock_resolve_files.return_value = ([], None)

    request = SubtaskRequest(task_id="exec-fail-1", type="atomic", name=template_name, description="", inputs={})

    # Act
    result = task_system_instance.execute_atomic_template(request)

    # Assert
    assert result.status == "FAILED"
    assert result.notes and result.notes.get("error")
    assert isinstance(result.notes["error"], TaskError)
    assert result.notes["error"].reason == "unexpected_error" # Caught by TaskSystem's generic handler
    # Check that the error message includes the exception from the executor
    assert "Execution failed: Executor boom!" in result.notes["error"].message # Check message from TaskSystem's except block
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
    assert isinstance(result.notes["error"], TaskError)
    # This error is now caught and handled directly by AtomicTaskExecutor
    assert result.notes["error"].reason == "input_validation_failure"
    assert mismatch_error_msg in result.notes["error"].message
    assert mismatch_error_msg in result.content


# --- Tests for generate_context_for_memory_system (Phase 2c) ---

@patch.object(TaskSystem, 'execute_atomic_template')
@patch.object(TaskSystem, 'find_template')
def test_generate_context_for_memory_system_success(
    mock_find_template, mock_execute_atomic, task_system_instance
):
    """Test successful context generation mediation."""
    # Arrange
    matching_template_name = "internal_matcher"
    mock_matching_template = {"name": matching_template_name, "type": "atomic", "subtype": "associative_matching"}
    mock_find_template.return_value = mock_matching_template

    # Use MatchTuple from models, remove score if not present
    mock_match_list = [MatchTuple(path="/path/file.py", relevance=0.8)]
    mock_assoc_result = AssociativeMatchResult(context_summary="Summary", matches=mock_match_list)
    # Simulate execute_atomic_template returning a TaskResult object
    mock_task_result_obj = TaskResult(
        content=mock_assoc_result.model_dump_json(), # Simulate JSON output
        status="COMPLETE",
        notes={}
    )
    mock_execute_atomic.return_value = mock_task_result_obj

    context_input = ContextGenerationInput(query="test query")
    global_index = {"/path/file.py": "py details"}

    # Act
    result = task_system_instance.generate_context_for_memory_system(context_input, global_index)

    # Assert
    mock_find_template.assert_called_once_with("atomic:associative_matching")
    mock_execute_atomic.assert_called_once()
    # Check the request passed to the internal execute call
    call_args, call_kwargs = mock_execute_atomic.call_args
    assert isinstance(call_args[0], SubtaskRequest)
    inner_request: SubtaskRequest = call_args[0]
    assert inner_request.name == matching_template_name # Check name attribute
    assert inner_request.type == "atomic" # Check type attribute
    # Check that context_input was dumped to dict
    assert inner_request.inputs["context_input"] == context_input.model_dump(exclude_none=True)
    assert inner_request.inputs["global_index"] == global_index
    assert inner_request.context_management.freshContext == "disabled" # Check override

    # Check the final result
    assert isinstance(result, AssociativeMatchResult)
    assert result.matches == mock_match_list
    assert result.error is None


@patch.object(TaskSystem, 'execute_atomic_template')
@patch.object(TaskSystem, 'find_template')
def test_generate_context_for_memory_system_parsing_error(
    mock_find_template, mock_execute_atomic, task_system_instance
):
    """Test context generation mediation when result parsing fails."""
    # Arrange
    mock_matching_template = {"name": "internal_matcher", "type": "atomic", "subtype": "associative_matching"}
    mock_find_template.return_value = mock_matching_template
    # Simulate execute_atomic_template returning a TaskResult object
    mock_task_result_obj = TaskResult(content="<Invalid JSON>", status="COMPLETE", notes={}) # Malformed content
    mock_execute_atomic.return_value = mock_task_result_obj
    context_input = ContextGenerationInput(query="test query")

    # Act
    result = task_system_instance.generate_context_for_memory_system(context_input, {})

    # Assert
    assert isinstance(result, AssociativeMatchResult)
    assert result.matches == []
    assert result.error is not None
    assert "Failed to parse AssociativeMatchResult" in result.error


@patch.object(TaskSystem, 'execute_atomic_template')
@patch.object(TaskSystem, 'find_template')
def test_generate_context_for_memory_system_execution_fails(
    mock_find_template, mock_execute_atomic, task_system_instance
):
    """Test context generation mediation when the internal task execution fails."""
    # Arrange
    mock_matching_template = {"name": "internal_matcher", "type": "atomic", "subtype": "associative_matching"}
    mock_find_template.return_value = mock_matching_template
    # Simulate execute_atomic_template returning a TaskResult object with a structured error
    mock_error = TaskFailureError(type="TASK_FAILURE", reason="unexpected_error", message="Internal Boom")
    mock_task_result_obj = TaskResult(
        content="Internal execution failed",
        status="FAILED",
        notes={"error": mock_error} # Embed the error object
    )
    mock_execute_atomic.return_value = mock_task_result_obj
    context_input = ContextGenerationInput(query="test query")

    # Act
    result = task_system_instance.generate_context_for_memory_system(context_input, {})

    # Assert
    assert isinstance(result, AssociativeMatchResult)
    assert result.matches == []
    assert result.error is not None
    # Check the corrected error message format
    assert result.error == "Associative matching task failed: Internal Boom"


@patch.object(TaskSystem, 'find_template')
def test_generate_context_for_memory_system_template_not_found(
    mock_find_template, task_system_instance
):
    """Test context generation mediation when the matching template isn't registered."""
    # Arrange
    mock_find_template.return_value = None # Simulate template not found
    context_input = ContextGenerationInput(query="test query")

    # Act
    result = task_system_instance.generate_context_for_memory_system(context_input, {})

    # Assert
    assert isinstance(result, AssociativeMatchResult)
    assert result.matches == []
    assert result.error is not None
    assert "Associative matching template 'atomic:associative_matching' not found" in result.error


# --- Tests for resolve_file_paths (Phase 2c) ---

# Removed patch decorator as we configure the mock instance directly
def test_resolve_file_paths_command(task_system_instance, mock_handler):
    """Test resolving file paths using a command."""
    # Arrange
    expected_paths = ["/path/a.py", "/path/b.py"]
    # Configure the mock handler instance directly
    mock_handler.execute_file_path_command.return_value = expected_paths
    template = {
        "file_paths_source": {
            "type": "command",
            "command": "find . -name '*.py'"
        }
    }
    # Act
    paths, error = task_system_instance.resolve_file_paths(template, None, mock_handler) # Memory not needed here

    # Assert
    assert error is None
    assert paths == expected_paths
    # Verify the call on the mock handler instance
    mock_handler.execute_file_path_command.assert_called_once_with("find . -name '*.py'")


@patch.object(MemorySystem, 'get_relevant_context_with_description')
def test_resolve_file_paths_description(mock_get_context_desc, task_system_instance, mock_memory_system):
    """Test resolving file paths using a description."""
    # Arrange
    expected_path = "/matched/desc.go"
    # Correct the mock return value structure
    mock_get_context_desc.return_value = AssociativeMatchResult(
        context_summary="Desc match",
        matches=[MatchTuple(path=expected_path, relevance=0.9)], # Use correct MatchTuple structure
        error=None
    )
    template = {
        "description": "Find Go files", # Used if specific desc missing
        "file_paths_source": {
            "type": "description",
            "description": "Relevant Go source files" # Specific description
        }
    }
    # Act
    paths, error = task_system_instance.resolve_file_paths(template, mock_memory_system, None) # Handler not needed

    # Assert
    assert error is None
    assert paths == [expected_path]
    # Called with specific description
    mock_get_context_desc.assert_called_once_with("Relevant Go source files", "Relevant Go source files")


@patch.object(MemorySystem, 'get_relevant_context_for')
def test_resolve_file_paths_context_description(mock_get_context, task_system_instance, mock_memory_system):
    """Test resolving file paths using context_description."""
    # Arrange
    expected_path = "/matched/context.rs"
    # Correct the mock return value structure
    mock_get_context.return_value = AssociativeMatchResult(
        context_summary="Context match",
        matches=[MatchTuple(path=expected_path, relevance=0.85)], # Use correct MatchTuple structure
        error=None
    )
    template = {
        "file_paths_source": {
            "type": "context_description",
            "context_query": "Find Rust files about parsing"
        }
    }
    # Act
    paths, error = task_system_instance.resolve_file_paths(template, mock_memory_system, None) # Handler not needed

    # Assert
    assert error is None
    assert paths == [expected_path]
    mock_get_context.assert_called_once()
    call_args, call_kwargs = mock_get_context.call_args
    assert isinstance(call_args[0], ContextGenerationInput)
    assert call_args[0].query == "Find Rust files about parsing"


def test_resolve_file_paths_literal(task_system_instance):
    """Test resolving file paths using literal paths."""
    # Arrange
    expected_paths = ["/literal/a.txt", "/literal/b.txt"]
    template = {
        "file_paths": expected_paths # Literal paths at top level
    }
    # Act
    paths, error = task_system_instance.resolve_file_paths(template, None, None)

    # Assert
    assert error is None
    assert paths == expected_paths

    # Arrange - Literal paths inside source element
    template_in_source = {
        "file_paths_source": {
            "type": "literal",
            "path": expected_paths # Changed key to 'path'
        }
    }
    # Act
    paths_in_source, error_in_source = task_system_instance.resolve_file_paths(template_in_source, None, None)

    # Assert
    assert error_in_source is None
    assert paths_in_source == expected_paths

    # Arrange - Literal paths specified via file_paths_source with type literal but no path key
    template_literal_no_path = {
        "file_paths_source": { "type": "literal" }
    }
    # Act
    paths_no_path, error_no_path = task_system_instance.resolve_file_paths(template_literal_no_path, None, None)
    # Assert
    assert error_no_path is None
    assert paths_no_path == [] # Should default to empty list


def test_resolve_file_paths_missing_info(task_system_instance, mock_handler):
    """Test error handling for missing information in resolve_file_paths."""
    # Command missing
    template_cmd = {"file_paths_source": {"type": "command"}}
    paths, error = task_system_instance.resolve_file_paths(template_cmd, None, mock_handler)
    assert error == "Missing command in file_paths_source type 'command'"
    assert paths == []

    # Description missing
    template_desc = {"file_paths_source": {"type": "description"}}
    paths, error = task_system_instance.resolve_file_paths(template_desc, MagicMock(), None)
    assert error == "Missing description for file_paths_source type 'description'"
    assert paths == []

    # Context query missing
    template_ctx = {"file_paths_source": {"type": "context_description"}}
    paths, error = task_system_instance.resolve_file_paths(template_ctx, MagicMock(), None)
    assert error == "Missing context_query for file_paths_source type 'context_description'"
    assert paths == []


def test_resolve_file_paths_unknown_type(task_system_instance):
    """Test handling of unknown source type."""
    template = {"file_paths_source": {"type": "magic"}}
    paths, error = task_system_instance.resolve_file_paths(template, None, None)
    assert error == "Unknown file_paths_source type: magic"
    assert paths == []


# --- Tests for find_matching_tasks (Phase 2c) ---

def test_find_matching_tasks_simple(task_system_instance):
    """Test basic matching and scoring."""
    # Arrange
    template1 = {"name": "task1", "type": "atomic", "subtype": "a", "description": "analyze python code"}
    template2 = {"name": "task2", "type": "atomic", "subtype": "b", "description": "summarize text document"}
    template3 = {"name": "task3", "type": "composite", "subtype": "c", "description": "analyze python data"} # Non-atomic
    template4 = {"name": "task4", "type": "atomic", "subtype": "d", "description": "find python examples"}
    task_system_instance.register_template(template1)
    task_system_instance.register_template(template2)
    task_system_instance.register_template(template3) # Should be ignored
    task_system_instance.register_template(template4)

    input_text = "analyze python script"

    # Act
    matches = task_system_instance.find_matching_tasks(input_text, None)

    # Assert
    # With MATCH_THRESHOLD = 0.2, only task1 should match well enough
    assert len(matches) == 1 # task1 should match, task4 score likely < 0.2
    assert matches[0]['task']['name'] == 'task1'
    assert all(m['taskType'] == 'atomic' for m in matches)
    assert matches[0]['subtype'] == 'a'


def test_find_matching_tasks_no_match(task_system_instance):
    """Test when no templates match above the threshold."""
    template1 = {"name": "task1", "type": "atomic", "subtype": "a", "description": "analyze python code"}
    task_system_instance.register_template(template1)
    input_text = "generate report for sales data" # Low similarity
    matches = task_system_instance.find_matching_tasks(input_text, None)
    assert len(matches) == 0 # Score should be below 0.2


def test_find_matching_tasks_empty_input(task_system_instance):
    """Test with empty input text."""
    template1 = {"name": "task1", "type": "atomic", "subtype": "a", "description": "analyze python code"}
    task_system_instance.register_template(template1)
    matches = task_system_instance.find_matching_tasks("", None)
    assert len(matches) == 0


def test_find_matching_tasks_sorting(task_system_instance):
    """Test that results are sorted by score."""
    template1 = {"name": "task1", "type": "atomic", "subtype": "a", "description": "short"} # Low overlap
    template2 = {"name": "task2", "type": "atomic", "subtype": "b", "description": "medium length description"} # Medium overlap
    template3 = {"name": "task3", "type": "atomic", "subtype": "c", "description": "very long and detailed description"} # High overlap
    task_system_instance.register_template(template1)
    task_system_instance.register_template(template2)
    task_system_instance.register_template(template3)

    input_text = "a very long and detailed description query"
    matches = task_system_instance.find_matching_tasks(input_text, None)

    # With MATCH_THRESHOLD = 0.2, task3 and task2 should match, task1 might not
    assert len(matches) == 2 # Expecting task3 and task2
    assert matches[0]['task']['name'] == 'task3'
    assert matches[1]['task']['name'] == 'task2'
    assert matches[0]['score'] >= matches[1]['score']


# --- Remove Deferred Method Tests ---

# Remove or comment out tests like these if they existed:
# def test_execute_atomic_template_deferred(task_system_instance): ...
# def test_find_matching_tasks_deferred(task_system_instance, mock_memory_system): ...
# def test_generate_context_for_memory_system_deferred(task_system_instance): ...
# def test_resolve_file_paths_deferred(task_system_instance, mock_memory_system): ...
