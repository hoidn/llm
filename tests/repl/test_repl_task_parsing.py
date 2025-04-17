import pytest
import sys
import io
from unittest.mock import patch, MagicMock, call # <-- Ensure 'call' is imported
import logging
import json # <-- Ensure 'json' is imported
# Import Repl class directly
from src.repl.repl import Repl

# --- MockApplication Class (Keep as is) ---
class MockApplication:
    def __init__(self):
        self.task_system = MagicMock(spec=['find_template']) # Mock only needed methods
        self.passthrough_handler = MagicMock(spec=['registered_tools', 'direct_tool_executors'])
        # Initialize mocked attributes to avoid AttributeErrors in tests
        self.task_system.find_template.return_value = None
        self.passthrough_handler.registered_tools = {}
        self.passthrough_handler.direct_tool_executors = {}
        self.aider_bridge = None # Add if needed by Repl init or methods
        self.indexed_repositories = ["dummy_repo"] # Assume repo indexed for most tests

    def index_repository(self, repo_path):
        # Mock indexing behavior if needed by tests
        logging.info(f"Mock indexing repository: {repo_path}")
        self.indexed_repositories.append(repo_path)
        return True

    def reset_conversation(self):
        # Mock reset behavior if needed
        logging.info("Mock resetting conversation")
        pass

    def handle_query(self, query):
         # Mock query handling if needed
         logging.info(f"Mock handling query: {query}")
         return {"status": "COMPLETE", "content": f"Mock response to {query}", "notes": {}}

@pytest.fixture
def mock_app():
    """Provides a mocked Application instance."""
    return MockApplication()
# --- End MockApplication ---


# --- CORRECTED FIXTURE ---
@pytest.fixture
def repl_instance(mock_app):
    """Creates a Repl instance and mocks its dispatcher_func."""
    # Initialize with a dummy stream first to avoid capsys conflicts
    dummy_stream = io.StringIO()
    repl = Repl(mock_app, output_stream=dummy_stream)
    
    # Create a mock function to replace the dispatcher call target
    mock_dispatcher = MagicMock(name="mock_execute_programmatic_task")
    # Set default return value for the mock
    mock_dispatcher.return_value = {"status": "COMPLETE", "content": "Mock Result", "notes": {}}
    
    # Patch the dispatcher_func on the instance
    repl.dispatcher_func = mock_dispatcher
    # Store mock for tests to access easily
    repl.mock_dispatcher_for_test = mock_dispatcher
    
    return repl
# --- END CORRECTED FIXTURE ---

# --- CORRECTED TEST FUNCTIONS ---

def test_cmd_task_no_args(repl_instance, capsys):
    """Test that calling /task with no arguments prints usage."""
    # Set output to sys.stdout for capsys to capture
    repl_instance.output = sys.stdout
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

def test_cmd_task_invalid_json_param(repl_instance, capsys):
    """Test calling /task with invalid JSON - should pass as string and print warning."""
    # Set output to sys.stdout for capsys to capture
    repl_instance.output = sys.stdout
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

def test_cmd_task_help_flag_template_found(repl_instance, capsys):
    """Test --help when a matching template is found."""
    # Set output to sys.stdout for capsys to capture
    repl_instance.output = sys.stdout
    
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

    repl_instance._handle_task_help("test:help")
    captured = capsys.readouterr()

    assert "Fetching help for task: test:help..." in captured.out
    assert "* Task Template Details:" in captured.out # Check correct section header
    assert "Description: Test Help Template" in captured.out
    assert "param1 (type: string): First param (required)" in captured.out
    assert 'param2 (type: integer) (default: 10): Second param' in captured.out

def test_cmd_task_help_flag_direct_tool_found(repl_instance, capsys):
    """Test --help when no template but a direct tool spec is found."""
    # Set output to sys.stdout for capsys to capture
    repl_instance.output = sys.stdout
    
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

def test_cmd_task_help_flag_direct_tool_no_spec(repl_instance, capsys):
    """Test --help when only a direct tool executor (no spec) is found."""
    # Set output to sys.stdout for capsys to capture
    repl_instance.output = sys.stdout
    
    repl_instance.application.task_system.find_template.return_value = None
    repl_instance.application.passthrough_handler.registered_tools = {} # No spec
    repl_instance.application.passthrough_handler.direct_tool_executors = {'test:direct_only': lambda x: x} # Executor exists

    repl_instance._cmd_task("test:direct_only --help")
    captured = capsys.readouterr()
    assert "Fetching help for task: test:direct_only..." in captured.out
    assert "* Found Direct Tool registration for 'test:direct_only'" in captured.out # Check fallback message
    repl_instance.mock_dispatcher_for_test.assert_not_called()


def test_cmd_task_help_flag_not_found(repl_instance, capsys):
    """Test --help when neither template nor tool is found."""
    # Set output to sys.stdout for capsys to capture
    repl_instance.output = sys.stdout
    
    repl_instance.application.task_system.find_template.return_value = None
    repl_instance.application.passthrough_handler.registered_tools = {}
    repl_instance.application.passthrough_handler.direct_tool_executors = {}

    repl_instance._cmd_task("unknown:task --help")
    captured = capsys.readouterr()

    assert "Fetching help for task: unknown:task..." in captured.out
    assert "No help found for identifier: unknown:task." in captured.out
    repl_instance.mock_dispatcher_for_test.assert_not_called()

# --- Tests for _parse_task_args ---

def test_parse_task_args_empty(repl_instance):
    """Test parsing empty argument list."""
    params, flags, error = repl_instance._parse_task_args([])
    assert params == {}
    assert flags == {}
    assert error is None

def test_parse_task_args_only_flags(repl_instance):
    """Test parsing only flags."""
    params, flags, error = repl_instance._parse_task_args(["--flag1", "--flag2"])
    assert params == {}
    assert flags == {"flag1": True, "flag2": True}
    assert error is None

def test_parse_task_args_only_params(repl_instance):
    """Test parsing only parameters."""
    params, flags, error = repl_instance._parse_task_args(["key1=value1", "key2=value2"])
    assert params == {"key1": "value1", "key2": "value2"}
    assert flags == {}
    assert error is None

def test_parse_task_args_json_values(repl_instance):
    """Test parsing JSON parameter values."""
    params, flags, error = repl_instance._parse_task_args([
        'list=["a", "b", "c"]',
        'obj={"key": 42}'
    ])
    assert params["list"] == ["a", "b", "c"]
    assert params["obj"] == {"key": 42}
    assert flags == {}
    assert error is None

def test_parse_task_args_invalid_json(repl_instance):
    """Test parsing invalid JSON parameter values."""
    params, flags, error = repl_instance._parse_task_args(['invalid={"key": missing_quotes}'])
    assert params["invalid"] == '{"key": missing_quotes}'  # Stored as string
    assert flags == {}
    assert "Could not parse value for 'invalid' as JSON" in error

def test_parse_task_args_mixed(repl_instance):
    """Test parsing mixed flags and parameters."""
    params, flags, error = repl_instance._parse_task_args([
        "--flag1", 
        "key1=value1", 
        "--flag2", 
        'key2={"nested": true}'
    ])
    assert params == {"key1": "value1", "key2": {"nested": True}}
    assert flags == {"flag1": True, "flag2": True}
    assert error is None

def test_parse_task_args_invalid_format(repl_instance):
    """Test parsing invalid format."""
    params, flags, error = repl_instance._parse_task_args(["not_a_param_or_flag"])
    assert params == {}
    assert flags == {}
    assert "Ignoring invalid parameter format" in error

# --- Tests for _display_task_result ---

def test_display_task_result_simple(repl_instance, capsys):
    """Test displaying a simple task result."""
    repl_instance.output = sys.stdout
    result = {
        "status": "COMPLETE",
        "content": "Simple result text"
    }
    repl_instance._display_task_result(result)
    captured = capsys.readouterr()
    
    assert "Status: COMPLETE" in captured.out
    assert "Content:" in captured.out
    assert "Simple result text" in captured.out
    assert "Notes:" not in captured.out  # No notes section

def test_display_task_result_json_content(repl_instance, capsys):
    """Test displaying a result with JSON content."""
    repl_instance.output = sys.stdout
    result = {
        "status": "COMPLETE",
        "content": '{"key": [1, 2, 3]}'
    }
    repl_instance._display_task_result(result)
    captured = capsys.readouterr()
    
    assert "Status: COMPLETE" in captured.out
    assert "Content:" in captured.out
    assert '"key": [' in captured.out
    assert "1," in captured.out  # Check indentation
    assert "Notes:" not in captured.out

def test_display_task_result_with_notes(repl_instance, capsys):
    """Test displaying a result with notes."""
    repl_instance.output = sys.stdout
    result = {
        "status": "COMPLETE",
        "content": "Result with notes",
        "notes": {
            "execution_path": "test_path",
            "files_modified": ["file1.py", "file2.py"]
        }
    }
    repl_instance._display_task_result(result)
    captured = capsys.readouterr()
    
    assert "Status: COMPLETE" in captured.out
    assert "Content:" in captured.out
    assert "Result with notes" in captured.out
    assert "Notes:" in captured.out
    assert '"execution_path": "test_path"' in captured.out
    assert '"files_modified": [' in captured.out
    assert '"file1.py"' in captured.out

# --- Error Handling Tests (Check Output) ---

def test_cmd_task_dispatcher_error(repl_instance, capsys):
    """Test REPL handling when the dispatcher call raises an unexpected error."""
    # Set output to sys.stdout for capsys to capture
    repl_instance.output = sys.stdout
    
    # Configure the mock dispatcher to raise an exception
    repl_instance.mock_dispatcher_for_test.side_effect = Exception("Dispatcher boom!")

    repl_instance._cmd_task("my:task") # Attempt to call the failing dispatcher
    captured = capsys.readouterr()

    # Check that the REPL printed the error message
    assert "Error calling dispatcher: Dispatcher boom!" in captured.out
    # Verify dispatcher was called (even though it failed)
    repl_instance.mock_dispatcher_for_test.assert_called_once() # Check call was made

def test_cmd_task_shlex_error(repl_instance, capsys):
    """Test REPL handling of shlex parsing errors."""
    # Set output to sys.stdout for capsys to capture
    repl_instance.output = sys.stdout
    
    repl_instance._cmd_task("my:task param='unclosed quote") # Input that causes shlex error
    captured = capsys.readouterr()
    assert "Error parsing command: No closing quotation" in captured.out
    repl_instance.mock_dispatcher_for_test.assert_not_called() # Dispatcher not called

# --- Result Display Tests (Check Output) ---

def test_cmd_task_result_display_simple(repl_instance, capsys):
    """Test REPL displays simple string content correctly."""
    # Set output to sys.stdout for capsys to capture
    repl_instance.output = sys.stdout
    
    repl_instance.mock_dispatcher_for_test.return_value = {"status": "COMPLETE", "content": "Simple result"}
    repl_instance._cmd_task("my:task") # Call dispatcher via REPL command
    captured = capsys.readouterr()
    # Check the final printed output
    assert "\nResult:" in captured.out
    assert "Status: COMPLETE" in captured.out
    assert "Content:\nSimple result" in captured.out # Check content formatting
    assert "\nNotes:" not in captured.out # No notes to display

def test_cmd_task_result_display_json_content(repl_instance, capsys):
    """Test REPL pretty-prints JSON content."""
    # Set output to sys.stdout for capsys to capture
    repl_instance.output = sys.stdout
    
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

def test_cmd_task_result_display_with_notes(repl_instance, capsys):
    """Test REPL displays notes correctly."""
    # Set output to sys.stdout for capsys to capture
    repl_instance.output = sys.stdout
    
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
