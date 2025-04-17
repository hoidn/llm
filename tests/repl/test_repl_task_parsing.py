import pytest
import io
import sys
import json
import logging
from unittest.mock import MagicMock, patch, ANY

# Import the Repl class (adjust path as needed)
from src.repl.repl import Repl

# Mock Application structure needed by Repl
class MockApplication:
    def __init__(self):
        self.passthrough_handler = MagicMock()
        self.task_system = MagicMock()
        # Mock necessary methods/attributes used in _cmd_task
        self.passthrough_handler.direct_tool_executors = {}
        self.passthrough_handler.registered_tools = {} # For help fallback
        self.task_system.find_template = MagicMock(return_value=None)

@pytest.fixture
def mock_app():
    return MockApplication()

@pytest.fixture
def repl_instance(mock_app):
    """Creates a Repl instance with mocked dependencies."""
    patch_target = 'src.dispatcher.execute_programmatic_task' # Correct source path
    logging.debug(f"Applying patch to: {patch_target}")
    with patch(patch_target, new_callable=MagicMock) as mock_dispatcher:
        logging.debug("PATCH ACTIVE: Before importing Repl.")
        # Import Repl AFTER the patch is active
        from src.repl.repl import Repl
        logging.debug("PATCH ACTIVE: Imported Repl.")
        repl = Repl(mock_app)
        # Store the mock on the instance for easy access in tests
        repl.mock_dispatcher_for_test = mock_dispatcher
        logging.debug(f"REPL INSTANCE: dispatcher_func ID is {id(repl.dispatcher_func)}, Type is {type(repl.dispatcher_func)}")
        logging.debug(f"MOCK DISPATCHER: ID is {id(mock_dispatcher)}, Type is {type(mock_dispatcher)}")
        # DO NOT assert repl.dispatcher_func is mock_dispatcher here
        yield repl # Use yield for fixtures

# --- CORRECTED TEST FUNCTIONS ---

def test_cmd_task_no_args(repl_instance, capsys): # Keep capsys
    """Test that calling /task with no arguments prints usage."""
    repl_instance._cmd_task("")
    captured = capsys.readouterr()
    # This test *should* check output because it doesn't call the dispatcher
    assert "Usage: /task <identifier>" in captured.out
    assert repl_instance.mock_dispatcher_for_test.call_count == 0 # Verify dispatcher wasn't called

def test_cmd_task_identifier_only(repl_instance):
    """Test calling /task with only an identifier."""
    repl_instance._cmd_task("my:task")
    repl_instance.mock_dispatcher_for_test.assert_called_once_with(
        identifier="my:task",
        params={},
        flags={},
        handler_instance=repl_instance.application.passthrough_handler,
        task_system_instance=repl_instance.application.task_system,
        optional_history_str=None
    )

def test_cmd_task_simple_param(repl_instance):
    """Test calling /task with one simple key=value parameter."""
    repl_instance._cmd_task("my:task key=value")
    repl_instance.mock_dispatcher_for_test.assert_called_once_with(
        identifier="my:task",
        params={"key": "value"},
        flags={},
        handler_instance=repl_instance.application.passthrough_handler,
        task_system_instance=repl_instance.application.task_system,
        optional_history_str=None
    )

def test_cmd_task_quoted_param(repl_instance):
    """Test calling /task with a parameter value containing spaces (quoted)."""
    repl_instance._cmd_task("my:task message='Hello world!'")
    repl_instance.mock_dispatcher_for_test.assert_called_once_with(
        identifier="my:task",
        params={"message": "Hello world!"},
        flags={},
        handler_instance=repl_instance.application.passthrough_handler,
        task_system_instance=repl_instance.application.task_system,
        optional_history_str=None
    )

def test_cmd_task_param_with_equals(repl_instance):
    """Test calling /task with a parameter value containing an equals sign."""
    repl_instance._cmd_task("my:task filter='status=active'")
    repl_instance.mock_dispatcher_for_test.assert_called_once_with(
        identifier="my:task",
        params={"filter": "status=active"}, # Value includes equals
        flags={},
        handler_instance=repl_instance.application.passthrough_handler,
        task_system_instance=repl_instance.application.task_system,
        optional_history_str=None
    )

def test_cmd_task_json_list_param(repl_instance):
    """Test calling /task with a parameter value that is a JSON list."""
    repl_instance._cmd_task('my:task files=\'["file1.py", "file2.py"]\'')
    repl_instance.mock_dispatcher_for_test.assert_called_once_with(
        identifier="my:task",
        params={"files": ["file1.py", "file2.py"]}, # Expect parsed list
        flags={},
        handler_instance=repl_instance.application.passthrough_handler,
        task_system_instance=repl_instance.application.task_system,
        optional_history_str=None
    )

def test_cmd_task_json_dict_param(repl_instance):
    """Test calling /task with a parameter value that is a JSON object."""
    repl_instance._cmd_task('my:task config=\'{"retries": 3, "active": true}\'')
    repl_instance.mock_dispatcher_for_test.assert_called_once_with(
        identifier="my:task",
        params={"config": {"retries": 3, "active": True}}, # Expect parsed dict
        flags={},
        handler_instance=repl_instance.application.passthrough_handler,
        task_system_instance=repl_instance.application.task_system,
        optional_history_str=None
    )

def test_cmd_task_invalid_json_param(repl_instance, capsys): # Keep capsys
    """Test calling /task with invalid JSON - should pass as string and print warning."""
    repl_instance._cmd_task('my:task data=\'{"key": invalid}\'') # Invalid JSON syntax
    # Assert dispatcher was called with the *string* value
    repl_instance.mock_dispatcher_for_test.assert_called_once_with(
        identifier="my:task",
        params={"data": '{"key": invalid}'}, # Expect raw string
        flags={},
        handler_instance=repl_instance.application.passthrough_handler,
        task_system_instance=repl_instance.application.task_system,
        optional_history_str=None
    )
    # Assert warning was printed
    captured = capsys.readouterr()
    assert "Warning: Could not parse value for 'data' as JSON" in captured.out

def test_cmd_task_simple_flag(repl_instance):
    """Test calling /task with a simple boolean flag."""
    repl_instance._cmd_task("my:task --force")
    repl_instance.mock_dispatcher_for_test.assert_called_once_with(
        identifier="my:task",
        params={},
        flags={"force": True}, # Expect flag set to True
        handler_instance=repl_instance.application.passthrough_handler,
        task_system_instance=repl_instance.application.task_system,
        optional_history_str=None
    )

def test_cmd_task_multiple_params_and_flags(repl_instance):
    """Test calling /task with a mix of parameters and flags."""
    repl_instance._cmd_task("my:task p1=v1 --flag1 p2='v 2' --flag2 p3='{\"a\":1}'")
    repl_instance.mock_dispatcher_for_test.assert_called_once_with(
        identifier="my:task",
        params={"p1": "v1", "p2": "v 2", "p3": {"a": 1}},
        flags={"flag1": True, "flag2": True},
        handler_instance=repl_instance.application.passthrough_handler,
        task_system_instance=repl_instance.application.task_system,
        optional_history_str=None
    )

# --- Help Flag Tests (Check Output) ---

def test_cmd_task_help_flag_template_found(repl_instance, capsys): # Keep capsys
    """Test --help when a matching template is found."""
    mock_template = {
        "name": "test:help", "description": "Test Help Template",
        "parameters": {
            "param1": {"type": "string", "description": "First param", "required": True},
            "param2": {"type": "integer", "description": "Second param", "default": 10}
        }
    }
    # Configure the *mock* application's TaskSystem mock
    repl_instance.application.task_system.find_template.return_value = mock_template
    repl_instance.application.passthrough_handler.registered_tools = {} # Ensure no tool conflict

    repl_instance._cmd_task("test:help --help")
    captured = capsys.readouterr()

    assert "Fetching help for task: test:help..." in captured.out
    assert "* Task Template Details:" in captured.out # Check correct section header
    assert "Description: Test Help Template" in captured.out
    assert "param1 (type: string): First param (required)" in captured.out
    assert 'param2 (type: integer) (default: 10): Second param' in captured.out
    repl_instance.mock_dispatcher_for_test.assert_not_called() # Dispatcher shouldn't be called for help

def test_cmd_task_help_flag_direct_tool_found(repl_instance, capsys): # Keep capsys
    """Test --help when no template but a direct tool spec is found."""
    # No template found
    repl_instance.application.task_system.find_template.return_value = None
    # Direct tool *spec* exists in registered_tools
    mock_tool_spec = {
        "name": "test:direct", "description": "Direct Tool Help",
        "input_schema": {"type":"object", "properties": {"arg1": {"type": "string", "description": "Tool Arg"}}, "required":["arg1"]}
    }
    repl_instance.application.passthrough_handler.registered_tools = {'test:direct': mock_tool_spec}
    repl_instance.application.passthrough_handler.direct_tool_executors = {'test:direct': lambda x: x} # Executor also exists

    repl_instance._cmd_task("test:direct --help")
    captured = capsys.readouterr()

    assert "Fetching help for task: test:direct..." in captured.out
    assert "* Direct Tool Specification:" in captured.out # Check correct section header
    assert "Description: Direct Tool Help" in captured.out
    assert "arg1 (type: string): Tool Arg (required)" in captured.out # Check formatting
    repl_instance.mock_dispatcher_for_test.assert_not_called()

def test_cmd_task_help_flag_direct_tool_no_spec(repl_instance, capsys): # Keep capsys
    """Test --help when only a direct tool executor (no spec) is found."""
    repl_instance.application.task_system.find_template.return_value = None
    repl_instance.application.passthrough_handler.registered_tools = {} # No spec
    repl_instance.application.passthrough_handler.direct_tool_executors = {'test:direct_only': lambda x: x} # Executor exists

    repl_instance._cmd_task("test:direct_only --help")
    captured = capsys.readouterr()
    assert "Fetching help for task: test:direct_only..." in captured.out
    assert "* Found Direct Tool registration for 'test:direct_only'" in captured.out # Check fallback message
    repl_instance.mock_dispatcher_for_test.assert_not_called()


def test_cmd_task_help_flag_not_found(repl_instance, capsys): # Keep capsys
    """Test --help when neither template nor tool is found."""
    repl_instance.application.task_system.find_template.return_value = None
    repl_instance.application.passthrough_handler.registered_tools = {}
    repl_instance.application.passthrough_handler.direct_tool_executors = {}

    repl_instance._cmd_task("unknown:task --help")
    captured = capsys.readouterr()

    assert "Fetching help for task: unknown:task..." in captured.out
    assert "No help found for identifier: unknown:task." in captured.out
    repl_instance.mock_dispatcher_for_test.assert_not_called()

# --- Error Handling Tests (Check Output) ---

def test_cmd_task_dispatcher_error(repl_instance, capsys): # Keep capsys
    """Test REPL handling when the dispatcher call raises an unexpected error."""
    # Configure the mock dispatcher to raise an exception
    repl_instance.mock_dispatcher_for_test.side_effect = Exception("Dispatcher boom!")

    repl_instance._cmd_task("my:task") # Attempt to call the failing dispatcher
    captured = capsys.readouterr()

    # Check that the REPL printed the error message
    assert "Error calling dispatcher: Dispatcher boom!" in captured.out
    # Verify dispatcher was called (even though it failed)
    repl_instance.mock_dispatcher_for_test.assert_called_once() # Check call was made

def test_cmd_task_shlex_error(repl_instance, capsys): # Keep capsys
    """Test REPL handling of shlex parsing errors."""
    repl_instance._cmd_task("my:task param='unclosed quote") # Input that causes shlex error
    captured = capsys.readouterr()
    assert "Error parsing command: No closing quotation" in captured.out
    repl_instance.mock_dispatcher_for_test.assert_not_called() # Dispatcher not called

# --- Result Display Tests (Check Output) ---

def test_cmd_task_result_display_simple(repl_instance, capsys): # Keep capsys
    """Test REPL displays simple string content correctly."""
    repl_instance.mock_dispatcher_for_test.return_value = {"status": "COMPLETE", "content": "Simple result"}
    repl_instance._cmd_task("my:task") # Call dispatcher via REPL command
    captured = capsys.readouterr()
    # Check the final printed output
    assert "\nResult:" in captured.out
    assert "Status: COMPLETE" in captured.out
    assert "Content:\nSimple result" in captured.out # Check content formatting
    assert "\nNotes:" not in captured.out # No notes to display

def test_cmd_task_result_display_json_content(repl_instance, capsys): # Keep capsys
    """Test REPL pretty-prints JSON content."""
    json_content_str = json.dumps({"data": [1, 2], "valid": True})
    repl_instance.mock_dispatcher_for_test.return_value = {"status": "COMPLETE", "content": json_content_str}
    repl_instance._cmd_task("my:task")
    captured = capsys.readouterr()
    assert "\nResult:" in captured.out
    assert "Status: COMPLETE" in captured.out
    # Check for indented JSON output
    assert '"data": [\n    1,\n    2\n  ]' in captured.out
    assert '"valid": true' in captured.out
    assert "\nNotes:" not in captured.out

def test_cmd_task_result_display_with_notes(repl_instance, capsys): # Keep capsys
    """Test REPL displays notes correctly."""
    notes_content = {"info": "some details", "files": ["a.txt"], "nested": {"key": 1}}
    repl_instance.mock_dispatcher_for_test.return_value = {
        "status": "COMPLETE",
        "content": "Result with notes",
        "notes": notes_content
    }
    repl_instance._cmd_task("my:task")
    captured = capsys.readouterr()
    assert "\nResult:" in captured.out
    assert "Status: COMPLETE" in captured.out
    assert "Content:\nResult with notes" in captured.out
    assert "\nNotes:" in captured.out
    # Check for indented JSON output of notes
    assert '"info": "some details"' in captured.out
    assert '"files": [\n    "a.txt"\n  ]' in captured.out
    assert '"nested": {\n    "key": 1\n  }' in captured.out
