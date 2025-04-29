"""
Unit tests for the PassthroughHandler.
"""

import pytest
from unittest.mock import MagicMock, call, patch, ANY
from src.handler.passthrough_handler import PassthroughHandler
from src.system.models import TaskResult, TaskFailureError, TaskError # Import TaskError from models
# Import dependencies for mocking
from src.task_system.task_system import TaskSystem
from src.memory.memory_system import MemorySystem
# Import managers if mocking them directly (Option 2)
from src.handler.file_context_manager import FileContextManager
from src.handler.llm_interaction_manager import LLMInteractionManager

# Fixture for mocked dependencies (TaskSystem, MemorySystem)
@pytest.fixture
def mock_task_system(mocker):
    """Mock TaskSystem instance."""
    return MagicMock(spec=TaskSystem)

@pytest.fixture
def mock_memory_system(mocker):
    """Mock MemorySystem instance."""
    return MagicMock(spec=MemorySystem)

@pytest.fixture
def passthrough_handler(mock_task_system, mock_memory_system, mocker):
    """Fixture for PassthroughHandler instance with mocked managers."""

    # --- Mock Managers (Option 2 from guidance) ---
    # Mock FileContextManager methods used by BaseHandler._get_relevant_files/_create_file_context
    mock_file_context_manager = MagicMock(spec=FileContextManager)
    mock_file_context_manager.get_relevant_files.return_value = ['/mock/file.py']
    mock_file_context_manager.create_file_context.return_value = "Mock file context content."

    # Mock LLMInteractionManager methods used by BaseHandler._execute_llm_call
    mock_llm_manager = MagicMock(spec=LLMInteractionManager)
    # Simulate successful LLM call returning a dictionary indicating success
    mock_llm_manager.execute_call.return_value = {
        "success": True,
        "content": "Passthrough Response", # Keep content consistent with test assertion
        "usage": {"prompt_tokens": 10, "completion_tokens": 20}, # Example usage
        "tool_calls": None
    }
    # Add the 'agent' attribute to the mock manager BEFORE patching/instantiation
    mock_llm_manager.agent = None # Or MagicMock() if needed elsewhere

    # --- Patch Manager Instantiation in BaseHandler ---
    # Patch the __init__ methods of the managers where BaseHandler creates them
    with patch('src.handler.base_handler.FileContextManager', return_value=mock_file_context_manager), \
         patch('src.handler.base_handler.LLMInteractionManager', return_value=mock_llm_manager), \
         patch('src.handler.base_handler.FileAccessManager'): # Patch FileAccessManager too

        # --- Mock command_executor functions used by the registered tool's wrapper ---
        # Patch these globally for the test session using mocker
        mocker.patch('src.handler.command_executor.execute_command_safely', return_value={'success': True, 'output': '/path/from/cmd', 'error': '', 'exit_code': 0})
        mocker.patch('src.handler.command_executor.parse_file_paths_from_output', return_value=['/path/from/cmd'])

        # --- Instantiate the Handler ---
        # BaseHandler.__init__ will now use the mocked managers
        handler = PassthroughHandler(
             task_system=mock_task_system,
             memory_system=mock_memory_system,
             config={"base_system_prompt": "Base Prompt."} # Example config
        )

        # --- Mock register_tool AFTER instantiation ---
        # We need to mock register_tool on the *instance* because the command tool
        # registration happens within PassthroughHandler's __init__ AFTER super().__init__
        # has potentially already called the real register_tool (if BaseHandler did).
        # Mocking it on the instance ensures we capture the call from PassthroughHandler.
        handler.register_tool = MagicMock(return_value=True)

        # Re-run the command tool registration manually on the mocked method
        # to simulate what happens in __init__
        handler.register_command_execution_tool()


    # Store mocks on the handler instance for easy access in tests
    handler._mock_file_context_manager = mock_file_context_manager
    handler._mock_llm_manager = mock_llm_manager

    return handler

# --- Test Cases ---

def test_init_registers_command_tool(passthrough_handler):
    """Verify __init__ calls register_tool for the command executor."""
    # The registration happens during fixture setup now
    passthrough_handler.register_tool.assert_called()
    # Check the arguments of the call made by register_command_execution_tool
    args, kwargs = passthrough_handler.register_tool.call_args
    tool_spec = args[0]
    executor_func = args[1]
    assert tool_spec['name'] == 'executeFilePathCommand'
    assert 'Executes a shell command' in tool_spec['description']
    assert 'command' in tool_spec['input_schema']['required']
    assert callable(executor_func)

def test_handle_query_success(passthrough_handler):
    """Test successful query handling, checking delegation and history."""
    query = "User query here"
    # Access mocks stored on the handler instance
    mock_fcm = passthrough_handler._mock_file_context_manager
    mock_llm = passthrough_handler._mock_llm_manager

    # Ensure history is initially empty (reset by fixture setup if needed)
    passthrough_handler.conversation_history = []
    initial_history_len = 0

    # Act
    result = passthrough_handler.handle_query(query)

    # Assert result
    assert isinstance(result, TaskResult)
    assert result.status == "COMPLETE"
    assert result.content == "Passthrough Response"
    assert result.notes.get("relevant_files") == ['/mock/file.py'] # Check added note

    # Assert delegation
    # Check calls to mocked managers via BaseHandler methods
    # _get_relevant_files -> FileContextManager.get_relevant_files
    mock_fcm.get_relevant_files.assert_called_once_with(query)
    # _create_file_context -> FileContextManager.create_file_context
    mock_fcm.create_file_context.assert_called_once_with(['/mock/file.py'])
    # _execute_llm_call -> LLMInteractionManager.execute_call
    mock_llm.execute_call.assert_called_once()
    call_args, call_kwargs = mock_llm.execute_call.call_args
    # Check arguments passed to LLMInteractionManager
    assert call_kwargs['prompt'] == query
    assert "Base Prompt." in call_kwargs['system_prompt_override']
    assert "Mock file context content." in call_kwargs['system_prompt_override']
    # Check history PASSED TO the manager call (should be empty initially)
    assert call_kwargs['conversation_history'] == []
    
    # Assert history update (BaseHandler._execute_llm_call should update it)
    assert len(passthrough_handler.conversation_history) == initial_history_len + 2
    assert passthrough_handler.conversation_history[0] == {"role": "user", "content": query}
    assert passthrough_handler.conversation_history[1] == {"role": "assistant", "content": "Passthrough Response"}


def test_handle_query_llm_failure(passthrough_handler):
    """Test query handling when the LLM call fails."""
    query = "Query that causes failure"
    mock_llm = passthrough_handler._mock_llm_manager
    # Configure LLM Manager mock to return a failure dictionary
    mock_llm.execute_call.return_value = {
        "status": "FAILED",
        "content": "LLM Error Occurred",
        "notes": {
            "error": {
                "type": "TASK_FAILURE",
                "reason": "llm_error",
                "message": "LLM Error Occurred"
            }
        }
    }
    # Remove any side_effect that might interfere
    mock_llm.execute_call.side_effect = None

    passthrough_handler.conversation_history = []
    initial_history_len = 0

    # Act
    result = passthrough_handler.handle_query(query)

    # Assert result
    assert isinstance(result, TaskResult)
    assert result.status == "FAILED"
    # Assert that the specific error message was extracted
    assert result.content == "LLM Error Occurred"
    assert result.notes is not None
    assert "error" in result.notes
    error_details = TaskFailureError.model_validate(result.notes["error"])
    assert error_details.type == "TASK_FAILURE"
    assert error_details.reason == "llm_error"
    assert error_details.message == "LLM Error Occurred"

    # Assert history wasn't updated on failure (BaseHandler logic)
    assert passthrough_handler.conversation_history == []


def test_reset_conversation(passthrough_handler):
    """Test resetting the conversation state."""
    mock_llm = passthrough_handler._mock_llm_manager
    # Add some history first
    passthrough_handler.conversation_history = [{"role": "user", "content": "test"}]
    passthrough_handler.active_subtask_id = "some_id"

    # Act
    passthrough_handler.reset_conversation()

    # Assert
    assert passthrough_handler.conversation_history == []
    assert passthrough_handler.active_subtask_id is None
    # LLMInteractionManager doesn't have reset_conversation method


def test_command_execution_tool_wrapper_success(passthrough_handler, mocker):
    """Test the internal wrapper for the command execution tool (success case)."""
    # Find the registered wrapper function
    reg_call = passthrough_handler.register_tool.call_args
    wrapper_func = reg_call[0][1] # Second argument of the call

    # Mock the underlying command_executor functions
    mock_safe_exec = mocker.patch('src.handler.command_executor.execute_command_safely', return_value={'success': True, 'output': '/path/one\n/path/two', 'error': '', 'exit_code': 0})
    mock_parse_paths = mocker.patch('src.handler.command_executor.parse_file_paths_from_output', return_value=['/path/one', '/path/two'])

    tool_input = {"command": "ls *.py"}
    result_dict = wrapper_func(tool_input)
    result = TaskResult.model_validate(result_dict)

    assert result.status == "COMPLETE"
    assert result.notes.get("file_paths") == ['/path/one', '/path/two']
    # Content might be the string representation of the list
    assert "['/path/one', '/path/two']" in result.content
    mock_safe_exec.assert_called_once_with("ls *.py")
    mock_parse_paths.assert_called_once_with('/path/one\n/path/two')

def test_command_execution_tool_wrapper_failure(passthrough_handler, mocker):
    """Test the internal wrapper for the command execution tool (failure case)."""
    reg_call = passthrough_handler.register_tool.call_args
    wrapper_func = reg_call[0][1]

    mock_safe_exec = mocker.patch('src.handler.command_executor.execute_command_safely', return_value={'success': False, 'output': '', 'error': 'Command not found', 'exit_code': 127})
    mock_parse_paths = mocker.patch('src.handler.command_executor.parse_file_paths_from_output') # Should not be called

    tool_input = {"command": "invalid-cmd"}
    result_dict = wrapper_func(tool_input)
    result = TaskResult.model_validate(result_dict)

    assert result.status == "FAILED"
    assert "Command not found" in result.content
    assert result.notes["error"]["reason"] == "tool_execution_error"
    mock_safe_exec.assert_called_once_with("invalid-cmd")
    mock_parse_paths.assert_not_called()
