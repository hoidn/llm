import pytest
import json
from unittest.mock import MagicMock, patch, ANY

from src.dispatcher import execute_programmatic_task
from src.system.models import (
    TaskResult, SubtaskRequest, ContextManagement, TaskFailureError, TaskError,
    TaskFailureReason, TaskFailureDetails # Import TaskFailureDetails
)
from src.system.errors import SexpSyntaxError, SexpEvaluationError
from src.sexp_evaluator.sexp_evaluator import SexpEvaluator

# --- Fixtures ---
# (Fixtures remain the same)
@pytest.fixture
def mock_handler():
    mock = MagicMock(name="MockHandler")
    mock.tool_executors = {}
    mock._execute_tool.return_value = TaskResult(status="COMPLETE", content="Tool Executed", notes={})
    return mock

@pytest.fixture
def mock_task_system():
    mock = MagicMock(name="MockTaskSystem")
    mock.find_template.return_value = None
    mock.execute_atomic_template.return_value = TaskResult(status="COMPLETE", content="Task Executed", notes={})
    return mock

@pytest.fixture
def mock_memory_system():
    return MagicMock(name="MockMemorySystem")

@pytest.fixture
def mock_sexp_evaluator_instance():
    mock = MagicMock(spec=SexpEvaluator)
    mock.evaluate_string.return_value = "Sexp Result"
    return mock

# --- Test Cases ---

# (test_dispatch_s_expression_routing remains the same)
@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_s_expression_routing(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system, mock_sexp_evaluator_instance):
    MockSexpEvaluatorClass.return_value = mock_sexp_evaluator_instance
    identifier = "(list 1 2)"
    params, flags = {}, {}
    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)
    MockSexpEvaluatorClass.assert_called_once_with(mock_task_system, mock_handler, mock_memory_system)
    mock_sexp_evaluator_instance.evaluate_string.assert_called_once_with(identifier)
    assert result['status'] == "COMPLETE"
    assert result['content'] == "Sexp Result"
    assert result['notes']['execution_path'] == "s_expression"

# (test_dispatch_atomic_task_routing remains the same)
@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_atomic_task_routing(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    identifier = "atomic:standard:test_task"
    params = {"input": "value"}
    flags = {}
    template_def = {"name": identifier, "type": "atomic", "subtype": "standard", "params": {"input":{}}}
    mock_task_system.find_template.return_value = template_def
    mock_task_system.execute_atomic_template.return_value = TaskResult(status="COMPLETE", content="Task Done", notes={"original": "note"})
    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)
    mock_task_system.find_template.assert_called_once_with(identifier)
    mock_handler._execute_tool.assert_not_called()
    mock_task_system.execute_atomic_template.assert_called_once()
    call_args = mock_task_system.execute_atomic_template.call_args[0][0]
    assert isinstance(call_args, SubtaskRequest)
    assert call_args.name == identifier
    assert call_args.type == "atomic"
    assert call_args.inputs == params
    assert call_args.file_paths is None
    assert result['status'] == "COMPLETE"
    assert result['content'] == "Task Done"
    assert result['notes']['execution_path'] == "subtask_template"
    assert result['notes']['original'] == "note"

# (test_dispatch_direct_tool_routing remains the same)
@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_direct_tool_routing(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    identifier = "handler:tool:test_tool"
    params = {"arg": "data"}
    flags = {}
    mock_handler.tool_executors = {identifier: MagicMock()}
    mock_handler._execute_tool.return_value = TaskResult(status="COMPLETE", content="Tool Result", notes={"tool_note": "abc"})
    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)
    mock_task_system.find_template.assert_called_once_with(identifier)
    mock_handler._execute_tool.assert_called_once_with(identifier, params)
    mock_task_system.execute_atomic_template.assert_not_called()
    assert result['status'] == "COMPLETE"
    assert result['content'] == "Tool Result"
    assert result['notes']['execution_path'] == "direct_tool"
    assert result['notes']['tool_note'] == "abc"

# (test_dispatch_identifier_not_found remains the same)
@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_identifier_not_found(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    identifier = "unknown:target"
    params, flags = {}, {}
    mock_task_system.find_template.return_value = None
    mock_handler.tool_executors = {}
    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)
    assert result['status'] == "FAILED"
    assert "not found" in result['content'].lower()
    assert result['notes']['error']['type'] == "TASK_FAILURE"
    assert result['notes']['error']['reason'] == "template_not_found"

# --- Test Error Handling (Updated Assertions) ---

@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_s_expression_eval_error(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system, mock_sexp_evaluator_instance):
    """Verify SexpEvaluationError is handled."""
    MockSexpEvaluatorClass.return_value = mock_sexp_evaluator_instance
    identifier = "(problem)"
    params, flags = {}, {}
    error_message = "Test eval error"
    error_details_str = "Symbol 'problem' not found"
    eval_exception = SexpEvaluationError(error_message, expression=identifier, error_details=error_details_str)
    mock_sexp_evaluator_instance.evaluate_string.side_effect = eval_exception

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    assert result['status'] == "FAILED"
    assert error_message in result['content']
    assert result['notes']['error']['type'] == "TASK_FAILURE"
    assert result['notes']['error']['reason'] == "subtask_failure"
    # FIX 1: Check the message generated by the helper
    # Construct the expected full message as generated by SexpEvaluationError's __init__
    expected_full_message = f"{error_message}\nExpression: '{identifier}'\nDetails: {error_details_str}"
    assert result['notes']['error']['message'] == f"S-expression Evaluation Error: {expected_full_message}"
    # FIX 1 & 2: Check the structure within details (now TaskFailureDetails)
    assert result['notes']['error']['details']['failing_expression'] == identifier
    assert result['notes']['error']['details']['notes'] == {"raw_error_details": error_details_str}
    assert result['notes']['execution_path'] == "s_expression" # Check note added before error

@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_s_expression_syntax_error(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system, mock_sexp_evaluator_instance):
    """Verify SexpSyntaxError is handled."""
    MockSexpEvaluatorClass.return_value = mock_sexp_evaluator_instance
    identifier = "(missing paren"
    params, flags = {}, {}
    error_message = "Unbalanced parentheses"
    error_details_str = "EOF found"
    syntax_exception = SexpSyntaxError(error_message, sexp_string=identifier, error_details=error_details_str)
    mock_sexp_evaluator_instance.evaluate_string.side_effect = syntax_exception

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    assert result['status'] == "FAILED"
    assert error_message in result['content']
    assert result['notes']['error']['type'] == "TASK_FAILURE"
    assert result['notes']['error']['reason'] == "input_validation_failure"
    # FIX 2: Assert the message generated by the helper matches exactly
    # Construct the expected full message as generated by SexpSyntaxError's __init__
    expected_full_message = f"{error_message}\nInput: '{identifier}'\nDetails: {error_details_str}"
    assert result['notes']['error']['message'] == f"S-expression Syntax Error: {expected_full_message}"
    # FIX 1 & 2: Check details structure
    assert result['notes']['error']['details']['failing_expression'] == identifier
    assert result['notes']['error']['details']['notes'] == {"raw_error_details": error_details_str}
    assert result['notes']['execution_path'] == "s_expression"


@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_task_system_execution_error(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    """Verify TaskError from TaskSystem is handled."""
    identifier = "atomic:standard:failing_task"
    params, flags = {}, {}
    template_def = {"name": identifier, "type": "atomic", "subtype": "standard", "params": {}}
    mock_task_system.find_template.return_value = template_def

    # Simulate execute_atomic_template returning a FAILED TaskResult object
    fail_reason: TaskFailureReason = "subtask_failure"
    # FIX 3 & 4: Create TaskFailureDetails object/dict
    details_obj = TaskFailureDetails(script_exit_code=123)
    fail_error_obj = TaskFailureError(type="TASK_FAILURE", reason=fail_reason, message="Subtask failed", details=details_obj)
    # Put the TaskFailureError *object* in notes - model_dump should handle nesting
    failed_task_result = TaskResult(status="FAILED", content="Subtask failed", notes={"error": fail_error_obj, "original_note": "abc"})
    mock_task_system.execute_atomic_template.return_value = failed_task_result

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    assert result['status'] == "FAILED"
    assert result['content'] == "Subtask failed"
    assert result['notes']['error']['type'] == "TASK_FAILURE"
    assert result['notes']['error']['reason'] == fail_reason
    assert result['notes']['error']['message'] == "Subtask failed"
    # FIX 3 & 4: Assert details are now present and match TaskFailureDetails structure
    assert result['notes']['error']['details']['script_exit_code'] == 123
    assert result['notes']['original_note'] == "abc"
    assert result['notes']['execution_path'] == "subtask_template"


@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_handler_tool_execution_error(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    """Verify TaskError from Handler tool execution is handled."""
    identifier = "handler:tool:failing_tool"
    params, flags = {}, {}
    mock_handler.tool_executors = {identifier: MagicMock()}

    # Simulate _execute_tool returning a FAILED TaskResult object
    fail_reason: TaskFailureReason = "tool_execution_error"
    # FIX 3 & 4: Create TaskFailureDetails object/dict
    details_obj = TaskFailureDetails(notes={"trace": "..."}) # Store arbitrary data in notes field
    fail_error_obj = TaskFailureError(type="TASK_FAILURE", reason=fail_reason, message="Tool crashed", details=details_obj)
    # Put the TaskFailureError *object* in notes
    failed_tool_result = TaskResult(status="FAILED", content="Tool crashed", notes={"error": fail_error_obj, "tool_debug": "xyz"})
    mock_handler._execute_tool.return_value = failed_tool_result

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    assert result['status'] == "FAILED"
    assert result['content'] == "Tool crashed"
    assert result['notes']['error']['type'] == "TASK_FAILURE"
    assert result['notes']['error']['reason'] == fail_reason
    assert result['notes']['error']['message'] == "Tool crashed"
    # FIX 3 & 4: Assert details are now present and match TaskFailureDetails structure
    assert result['notes']['error']['details']['notes'] == {"trace": "..."}
    assert result['notes']['tool_debug'] == "xyz"
    assert result['notes']['execution_path'] == "direct_tool"

# (Other tests remain the same)
@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_direct_tool_continuation_is_failure(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    identifier = "handler:tool:continuing_tool"
    params, flags = {}, {}
    mock_handler.tool_executors = {identifier: MagicMock()}
    continue_result = TaskResult(status="CONTINUATION", content="Needs more info", notes={})
    mock_handler._execute_tool.return_value = continue_result
    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)
    assert result['status'] == "FAILED"
    assert "cannot return continuation status" in result['content'].lower()
    assert result['notes']['error']['type'] == "TASK_FAILURE"
    assert result['notes']['error']['reason'] == "tool_execution_error"

@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_file_context_parsing_list(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    identifier = "atomic:standard:task_with_context"
    files = ["file1.txt", "file2.py"]
    params = {"input": "value", "file_context": files}
    flags = {}
    template_def = {"name": identifier, "type": "atomic", "subtype": "standard", "params": {"input":{}, "file_context":{}}}
    mock_task_system.find_template.return_value = template_def
    execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)
    mock_task_system.execute_atomic_template.assert_called_once()
    call_args = mock_task_system.execute_atomic_template.call_args[0][0]
    assert isinstance(call_args, SubtaskRequest)
    assert call_args.file_paths == files
    assert "file_context" not in call_args.inputs
    assert call_args.inputs["input"] == "value"

@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_file_context_parsing_json_string(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    identifier = "atomic:standard:task_with_context"
    files = ["file3.md", "subdir/file4.js"]
    params = {"input": "value", "file_context": json.dumps(files)}
    flags = {}
    template_def = {"name": identifier, "type": "atomic", "subtype": "standard", "params": {"input":{}, "file_context":{}}}
    mock_task_system.find_template.return_value = template_def
    execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)
    mock_task_system.execute_atomic_template.assert_called_once()
    call_args = mock_task_system.execute_atomic_template.call_args[0][0]
    assert isinstance(call_args, SubtaskRequest)
    assert call_args.file_paths == files
    assert "file_context" not in call_args.inputs

@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_file_context_parsing_invalid_json(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    identifier = "atomic:standard:task_with_context"
    params = {"input": "value", "file_context": '["file3.md", "subdir/file4.js"'}
    flags = {}
    template_def = {"name": identifier, "type": "atomic", "subtype": "standard", "params": {"input":{}, "file_context":{}}}
    # Don't need to mock find_template as it shouldn't be called
    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)
    assert result['status'] == "FAILED"
    assert "invalid json" in result['content'].lower() or "failed to parse json" in result['content'].lower()
    assert result['notes']['error']['reason'] == "input_validation_failure"
    mock_task_system.find_template.assert_not_called() # Should fail before lookup


@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_file_context_parsing_not_list_of_strings(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    identifier = "atomic:standard:task_with_context"
    params = {"input": "value", "file_context": ["file1.txt", 123]}
    flags = {}
    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)
    assert result['status'] == "FAILED"
    assert result['content'] == "Invalid 'file_context': list must contain only strings."
    assert result['notes']['error']['reason'] == "input_validation_failure"
    mock_task_system.find_template.assert_not_called()

@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_result_notes_population(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    """Verify standard notes are added to the TaskResult and merged correctly."""
    # Path 1: Tool
    identifier_tool = "handler:tool:simple_tool"
    params_tool = {"file_context": '["f1.txt"]'} # Include context for note check
    flags_tool = {}
    mock_handler.tool_executors = {identifier_tool: MagicMock()}
    mock_handler._execute_tool.return_value = TaskResult(status="COMPLETE", content="Tool Done", notes={"extra_tool_note": 1})

    result_tool = execute_programmatic_task(identifier_tool, params_tool, flags_tool, mock_handler, mock_task_system, mock_memory_system)

    assert result_tool['status'] == "COMPLETE"
    assert result_tool['notes']['execution_path'] == "direct_tool"
    assert result_tool['notes']['context_source'] == "explicit_request"
    assert result_tool['notes']['context_files_count'] == 1
    assert result_tool['notes']['extra_tool_note'] == 1 # Check original notes preserved


    # Path 2: Task
    identifier_task = "atomic:standard:simple_task"
    params_task = {} # No explicit context
    flags_task = {}
    template_def = {"name": identifier_task, "type": "atomic", "subtype": "standard", "params": {}}
    mock_task_system.find_template.return_value = template_def
    # Simulate TaskSystem adding notes
    # Note: TaskSystem's execute_atomic_template now returns TaskResult object
    task_sys_result = TaskResult(status="COMPLETE", content="Task Done", notes={"context_source": "template_literal", "file_count": 0, "extra_task_note": 2})
    mock_task_system.execute_atomic_template.return_value = task_sys_result

    result_task = execute_programmatic_task(identifier_task, params_task, flags_task, mock_handler, mock_task_system, mock_memory_system)

    assert result_task['status'] == "COMPLETE"
    assert result_task['notes']['execution_path'] == "subtask_template"
    # Context source should be from task system result if available, else default 'none'
    assert result_task['notes']['context_source'] == "template_literal" # Overwritten by task result
    # Ensure context_files_count is present (even if 0)
    assert result_task['notes']['context_files_count'] == 0 # Should be merged from dispatcher notes
    assert result_task['notes']['extra_task_note'] == 2 # Check original notes preserved
    # Check if 'file_count' from task system result is preserved (it might be overwritten or merged depending on implementation)
    # Based on current dispatcher logic, it should be preserved if TaskSystem adds it.
    assert result_task['notes']['file_count'] == 0
