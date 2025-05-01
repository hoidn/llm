import pytest
import json
from unittest.mock import MagicMock, patch, ANY

# Assume dispatcher function is importable
from src.dispatcher import execute_programmatic_task
# Assume models are importable
from src.system.models import TaskResult, SubtaskRequest, ContextManagement, TaskFailureError, TaskError, TaskFailureReason # Added TaskFailureReason
from src.system.errors import SexpSyntaxError, SexpEvaluationError
from src.sexp_evaluator.sexp_evaluator import SexpEvaluator # Import for patching target
# Import base classes for spec/isinstance checks if needed
from src.handler.base_handler import BaseHandler
from src.task_system.task_system import TaskSystem
from src.memory.memory_system import MemorySystem


# --- Fixtures ---
@pytest.fixture
def mock_handler():
    mock = MagicMock(spec=BaseHandler, name="MockHandler") # Use spec
    mock.tool_executors = {}
    # Simulate _execute_tool returning a TaskResult object
    mock._execute_tool.return_value = TaskResult(status="COMPLETE", content="Tool Executed", notes={})
    return mock

@pytest.fixture
def mock_task_system():
    mock = MagicMock(spec=TaskSystem, name="MockTaskSystem") # Use spec
    mock.find_template.return_value = None # Default: template not found
    # Simulate execute_atomic_template returning a TaskResult object
    mock.execute_atomic_template.return_value = TaskResult(status="COMPLETE", content="Task Executed", notes={})
    return mock

@pytest.fixture
def mock_memory_system():
    # Needed for SexpEvaluator instantiation if done inside dispatcher
    return MagicMock(spec=MemorySystem, name="MockMemorySystem") # Use spec

@pytest.fixture
def mock_sexp_evaluator_instance():
    # Mock the instance that would be created/used
    mock = MagicMock(spec=SexpEvaluator)
    mock.evaluate_string.return_value = "Sexp Result" # Default result
    return mock

# --- Test Cases ---

# Patch the SexpEvaluator *class* where it's looked up (in the dispatcher module)
@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_s_expression_routing(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system, mock_sexp_evaluator_instance):
    """Verify S-expressions are routed to SexpEvaluator."""
    # Configure the class mock to return our instance mock
    MockSexpEvaluatorClass.return_value = mock_sexp_evaluator_instance

    identifier = "(list 1 2)"
    params = {}
    flags = {}

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    # Assert SexpEvaluator was instantiated correctly
    MockSexpEvaluatorClass.assert_called_once_with(mock_task_system, mock_handler, mock_memory_system)
    # Assert evaluate_string was called on the instance
    mock_sexp_evaluator_instance.evaluate_string.assert_called_once_with(identifier) # Removed initial_env=None assumption
    # Assert result is formatted correctly
    assert result['status'] == "COMPLETE"
    assert result['content'] == "Sexp Result" # Wrapped raw result
    assert result['notes']['execution_path'] == "s_expression"

@patch('src.dispatcher.SexpEvaluator') # Still need to patch even if not used
def test_dispatch_atomic_task_routing(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    """Verify known atomic tasks are routed to TaskSystem."""
    identifier = "atomic:standard:test_task"
    params = {"input": "value"}
    flags = {}
    template_def = {"name": identifier, "type": "atomic", "subtype": "standard", "params": {"input":{}}}
    mock_task_system.find_template.return_value = template_def
    mock_task_system.execute_atomic_template.return_value = TaskResult(status="COMPLETE", content="Task Done", notes={"original": "note"})

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    mock_task_system.find_template.assert_called_once_with(identifier)
    mock_handler._execute_tool.assert_not_called()
    # Assert execute_atomic_template called with a SubtaskRequest object
    mock_task_system.execute_atomic_template.assert_called_once()
    call_args = mock_task_system.execute_atomic_template.call_args[0][0] # Get the first positional arg
    assert isinstance(call_args, SubtaskRequest)
    assert call_args.name == identifier
    assert call_args.type == "atomic"
    assert call_args.inputs == params
    assert call_args.file_paths is None # No file_context param provided
    assert call_args.task_id is not None # Check task_id was generated

    assert result['status'] == "COMPLETE"
    assert result['content'] == "Task Done"
    assert result['notes']['execution_path'] == "subtask_template"
    assert result['notes']['original'] == "note" # Check original notes preserved
    assert result['notes']['context_source'] == "none" # Check default context note
    assert result['notes']['context_files_count'] == 0

@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_direct_tool_routing(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    """Verify known direct tools are routed to Handler."""
    identifier = "handler:tool:test_tool"
    params = {"arg": "data"}
    flags = {}
    # Configure mock_handler to have the tool
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
    assert result['notes']['context_source'] == "none"
    assert result['notes']['context_files_count'] == 0

@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_identifier_not_found(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    """Verify failure when identifier matches neither TaskSystem nor Handler."""
    identifier = "unknown:target"
    params = {}
    flags = {}
    # Ensure mocks are configured to not find the identifier
    mock_task_system.find_template.return_value = None
    mock_handler.tool_executors = {}

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    assert result['status'] == "FAILED"
    assert "not found" in result['content'].lower()
    assert result['notes']['error']['type'] == "TASK_FAILURE"
    assert result['notes']['error']['reason'] == "template_not_found"
    # Context notes should still be present even on failure
    assert result['notes']['context_source'] == "none"
    assert result['notes']['context_files_count'] == 0


@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_s_expression_eval_error(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system, mock_sexp_evaluator_instance):
    """Verify SexpEvaluationError is handled."""
    MockSexpEvaluatorClass.return_value = mock_sexp_evaluator_instance
    identifier = "(problem)"
    params = {}
    flags = {}
    eval_exception = SexpEvaluationError("Test eval error", expression=identifier, error_details="Symbol 'problem' not found")
    mock_sexp_evaluator_instance.evaluate_string.side_effect = eval_exception

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    assert result['status'] == "FAILED"
    assert "Test eval error" in result['content']
    assert result['notes']['error']['type'] == "TASK_FAILURE"
    assert result['notes']['error']['reason'] == "subtask_failure" # Mapping decision
    assert result['notes']['error']['message'] == eval_exception.message # Check message propagation
    assert result['notes']['error']['details']['expression'] == identifier
    assert result['notes']['error']['details']['error_details'] == "Symbol 'problem' not found"
    assert result['notes']['execution_path'] == "s_expression" # Check note added before error

@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_s_expression_syntax_error(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system, mock_sexp_evaluator_instance):
    """Verify SexpSyntaxError is handled."""
    MockSexpEvaluatorClass.return_value = mock_sexp_evaluator_instance
    identifier = "(missing paren"
    params = {}
    flags = {}
    syntax_exception = SexpSyntaxError("Unbalanced parentheses", sexp_string=identifier, error_details="EOF found")
    # Configure the *parser* used by the evaluator mock, or the evaluator mock itself
    mock_sexp_evaluator_instance.evaluate_string.side_effect = syntax_exception

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    assert result['status'] == "FAILED"
    assert "Unbalanced parentheses" in result['content']
    assert result['notes']['error']['type'] == "TASK_FAILURE"
    assert result['notes']['error']['reason'] == "input_validation_failure" # Mapping decision
    assert result['notes']['error']['message'] == str(syntax_exception).split('\n')[0] # Get first line of message
    assert result['notes']['error']['details']['expression'] == identifier
    assert result['notes']['error']['details']['error_details'] == "EOF found"
    assert result['notes']['execution_path'] == "s_expression"


@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_task_system_execution_error(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    """Verify TaskError from TaskSystem is handled."""
    identifier = "atomic:standard:failing_task"
    params = {}
    flags = {}
    template_def = {"name": identifier, "type": "atomic", "subtype": "standard", "params": {}}
    mock_task_system.find_template.return_value = template_def
    # Simulate execute_atomic_template returning a FAILED TaskResult object
    fail_reason: TaskFailureReason = "subtask_failure"
    fail_error = TaskFailureError(type="TASK_FAILURE", reason=fail_reason, message="Subtask failed", details={"code": 123})
    failed_task_result = TaskResult(status="FAILED", content="Subtask failed", notes={"error": fail_error, "original_note": "abc"})
    mock_task_system.execute_atomic_template.return_value = failed_task_result

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    assert result['status'] == "FAILED"
    assert result['content'] == "Subtask failed"
    # Verify the error object is correctly nested in notes
    assert result['notes']['error']['type'] == "TASK_FAILURE"
    assert result['notes']['error']['reason'] == fail_reason
    assert result['notes']['error']['message'] == "Subtask failed"
    assert result['notes']['error']['details'] == {"code": 123}
    # Verify other notes are preserved
    assert result['notes']['execution_path'] == "subtask_template"
    assert result['notes']['context_source'] == "none"
    assert result['notes']['original_note'] == "abc"


@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_handler_tool_execution_error(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    """Verify TaskError from Handler tool execution is handled."""
    identifier = "handler:tool:failing_tool"
    params = {}
    flags = {}
    mock_handler.tool_executors = {identifier: MagicMock()}
    # Simulate _execute_tool returning a FAILED TaskResult object
    fail_reason: TaskFailureReason = "tool_execution_error"
    fail_error = TaskFailureError(type="TASK_FAILURE", reason=fail_reason, message="Tool crashed", details={"trace": "..."})
    failed_tool_result = TaskResult(status="FAILED", content="Tool crashed", notes={"error": fail_error, "tool_debug": "xyz"})
    mock_handler._execute_tool.return_value = failed_tool_result

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    assert result['status'] == "FAILED"
    assert result['content'] == "Tool crashed"
    assert result['notes']['error']['type'] == "TASK_FAILURE"
    assert result['notes']['error']['reason'] == fail_reason
    assert result['notes']['error']['message'] == "Tool crashed"
    assert result['notes']['error']['details'] == {"trace": "..."}
    # Verify other notes are preserved
    assert result['notes']['execution_path'] == "direct_tool"
    assert result['notes']['context_source'] == "none"
    assert result['notes']['tool_debug'] == "xyz"


@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_direct_tool_continuation_is_failure(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    """Verify CONTINUATION status from a direct tool is treated as FAILED."""
    identifier = "handler:tool:continuing_tool"
    params = {}
    flags = {}
    mock_handler.tool_executors = {identifier: MagicMock()}
    # Simulate _execute_tool returning a CONTINUATION TaskResult object
    continue_result = TaskResult(status="CONTINUATION", content="Needs more info", notes={})
    mock_handler._execute_tool.return_value = continue_result

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    assert result['status'] == "FAILED"
    assert "cannot return continuation status" in result['content'].lower()
    assert result['notes']['error']['type'] == "TASK_FAILURE"
    assert result['notes']['error']['reason'] == "tool_execution_error"
    assert result['notes']['execution_path'] == "direct_tool" # Check note added before error


@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_file_context_parsing_list(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    """Verify 'file_context' list parameter is parsed correctly."""
    identifier = "atomic:standard:task_with_context"
    files = ["file1.txt", "file2.py"]
    params = {"input": "value", "file_context": files}
    flags = {}
    template_def = {"name": identifier, "type": "atomic", "subtype": "standard", "params": {"input":{}, "file_context":{}}}
    mock_task_system.find_template.return_value = template_def
    # Configure task system to return a simple result
    mock_task_system.execute_atomic_template.return_value = TaskResult(status="COMPLETE", content="Context Task Done", notes={})


    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    mock_task_system.execute_atomic_template.assert_called_once()
    call_args = mock_task_system.execute_atomic_template.call_args[0][0]
    assert isinstance(call_args, SubtaskRequest)
    assert call_args.file_paths == files
    # Ensure original params dict passed to inputs doesn't contain file_context
    assert "file_context" not in call_args.inputs
    assert call_args.inputs["input"] == "value"

    # Check notes in the final result
    assert result['status'] == "COMPLETE"
    assert result['notes']['execution_path'] == "subtask_template"
    assert result['notes']['context_source'] == "explicit_request"
    assert result['notes']['context_files_count'] == 2


@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_file_context_parsing_json_string(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    """Verify 'file_context' JSON string parameter is parsed correctly."""
    identifier = "atomic:standard:task_with_context"
    files = ["file3.md", "subdir/file4.js"]
    params = {"input": "value", "file_context": json.dumps(files)}
    flags = {}
    template_def = {"name": identifier, "type": "atomic", "subtype": "standard", "params": {"input":{}, "file_context":{}}}
    mock_task_system.find_template.return_value = template_def
    mock_task_system.execute_atomic_template.return_value = TaskResult(status="COMPLETE", content="Context Task Done", notes={})


    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    mock_task_system.execute_atomic_template.assert_called_once()
    call_args = mock_task_system.execute_atomic_template.call_args[0][0]
    assert isinstance(call_args, SubtaskRequest)
    assert call_args.file_paths == files
    assert "file_context" not in call_args.inputs

    assert result['status'] == "COMPLETE"
    assert result['notes']['execution_path'] == "subtask_template"
    assert result['notes']['context_source'] == "explicit_request"
    assert result['notes']['context_files_count'] == 2


@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_file_context_parsing_invalid_json(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    """Verify invalid 'file_context' JSON string results in failure."""
    identifier = "atomic:standard:task_with_context"
    params = {"input": "value", "file_context": '["file3.md", "subdir/file4.js"'} # Invalid JSON
    flags = {}
    template_def = {"name": identifier, "type": "atomic", "subtype": "standard", "params": {"input":{}, "file_context":{}}}
    # Don't need to mock find_template as it shouldn't be called

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    assert result['status'] == "FAILED"
    assert "invalid json" in result['content'].lower() or "failed to parse json" in result['content'].lower()
    assert result['notes']['error']['reason'] == "input_validation_failure"
    mock_task_system.find_template.assert_not_called() # Should fail before lookup
    mock_handler._execute_tool.assert_not_called()


@patch('src.dispatcher.SexpEvaluator')
def test_dispatch_file_context_parsing_not_list_of_strings(MockSexpEvaluatorClass, mock_handler, mock_task_system, mock_memory_system):
    """Verify 'file_context' list containing non-strings results in failure."""
    identifier = "atomic:standard:task_with_context"
    params = {"input": "value", "file_context": ["file1.txt", 123]} # Invalid list content
    flags = {}

    result = execute_programmatic_task(identifier, params, flags, mock_handler, mock_task_system, mock_memory_system)

    assert result['status'] == "FAILED"
    assert "must be a list of strings" in result['content'].lower()
    assert result['notes']['error']['reason'] == "input_validation_failure"
    mock_task_system.find_template.assert_not_called()
    mock_handler._execute_tool.assert_not_called()

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
    task_sys_result = TaskResult(status="COMPLETE", content="Task Done", notes={"context_source": "template_literal", "context_files_count": 0, "extra_task_note": 2})
    mock_task_system.execute_atomic_template.return_value = task_sys_result

    result_task = execute_programmatic_task(identifier_task, params_task, flags_task, mock_handler, mock_task_system, mock_memory_system)

    assert result_task['status'] == "COMPLETE"
    assert result_task['notes']['execution_path'] == "subtask_template"
    # Context source should be from task system result if available, else default 'none'
    assert result_task['notes']['context_source'] == "template_literal" # Overwritten by task result
    assert result_task['notes']['context_files_count'] == 0 # Overwritten by task result
    assert result_task['notes']['extra_task_note'] == 2 # Check original notes preserved
