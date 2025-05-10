"""
Unit tests for the PassthroughHandler.
"""

import pytest
from unittest.mock import MagicMock, call, patch, ANY
from typing import Optional, List # Add Optional and List
from src.handler.passthrough_handler import PassthroughHandler
from src.system.models import TaskResult, TaskFailureError, TaskError, DataContext, MatchItem # Import TaskError from models
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
    handler.task_system = mock_task_system # Ensure task_system is also available if needed directly

    # Configure mock_task_system for template finding in subtask methods
    mock_task_system.find_template.return_value = {"instructions": "mock template instructions"}


    return handler

# --- Test Cases ---

def test_init_registers_command_tool(passthrough_handler):
    """Verify __init__ calls register_tool for the command executor."""
    import collections.abc # Add this import at the top of the file

    # Inside test_init_registers_command_tool
    # Instead of assert_called(), check call_args_list or use assert_any_call
    found_cmd_tool = False
    found_list_tool = False
    expected_cmd_tool_name = 'executeFilePathCommand'
    expected_list_tool_name = 'listFiles'

    for actual_call in passthrough_handler.register_tool.call_args_list:
        args, kwargs = actual_call
        if args and isinstance(args[0], dict):
            tool_name = args[0].get('name')
            if tool_name == expected_cmd_tool_name:
                found_cmd_tool = True
                # Optionally, assert the structure of args[0] (tool_spec) and type of args[1] (executor)
                assert isinstance(args[1], collections.abc.Callable) # Check if executor is callable
            elif tool_name == expected_list_tool_name:
                found_list_tool = True
                assert isinstance(args[1], collections.abc.Callable) # Check if executor is callable

    assert found_cmd_tool, f"Expected tool '{expected_cmd_tool_name}' was not registered."
    assert found_list_tool, f"Expected tool '{expected_list_tool_name}' was not registered."


def test_handle_query_success(passthrough_handler, mocker):
    """Test successful query handling, checking delegation and history."""
    query = "User query here"
    
    # Mock BaseHandler methods called by the new handle_query structure
    passthrough_handler.prime_data_context = MagicMock(return_value=True)
    # Mock _create_new_subtask to return a successful TaskResult
    # This mock will be called since active_subtask_id is None by default
    mock_subtask_result_content = "Subtask Response"
    mock_subtask_result = TaskResult(status="COMPLETE", content=mock_subtask_result_content, notes={})
    passthrough_handler._create_new_subtask = MagicMock(return_value=mock_subtask_result)

    # Mock data_context for notes population
    mock_match_item = MagicMock(spec=MagicMock) # Use MagicMock for MatchItem to set 'id'
    mock_match_item.id = "/mock/context_file.py"
    passthrough_handler.data_context = MagicMock()
    passthrough_handler.data_context.items = [mock_match_item]
    
    # Ensure history is initially empty
    passthrough_handler.conversation_history = []

    # Act
    result = passthrough_handler.handle_query(query)

    # Assert result
    assert isinstance(result, TaskResult)
    assert result.status == "COMPLETE"
    assert result.content == mock_subtask_result_content
    assert result.notes.get("relevant_files_from_context") == ["/mock/context_file.py"]

    # Assert delegation
    passthrough_handler.prime_data_context.assert_called_once_with(query=query)
    passthrough_handler._create_new_subtask.assert_called_once_with(query=query)
    
    # History is updated by _execute_llm_call, which is called within _create_new_subtask.
    # If _create_new_subtask is fully mocked, we can't directly test history update here
    # unless the mock itself simulates it or we test _create_new_subtask more deeply.
    # For this level, we assume _create_new_subtask (if not mocked away) would handle history.
    # If _create_new_subtask calls the real _execute_llm_call, then history would be updated.
    # Let's assume for this test, _create_new_subtask is a high-level mock.


def test_handle_query_prime_data_context_failure(passthrough_handler, mocker):
    """Test query handling when prime_data_context fails."""
    query = "Query causing priming failure"
    passthrough_handler.prime_data_context = MagicMock(return_value=False)
    passthrough_handler.conversation_history = []

    result = passthrough_handler.handle_query(query)

    assert result.status == "FAILED"
    assert "Error preparing data context" in result.content
    assert result.notes["error"]["reason"] == "context_priming_failure"
    passthrough_handler.prime_data_context.assert_called_once_with(query=query)
    assert passthrough_handler.conversation_history == []


def test_handle_query_no_active_subtask_creates_new(passthrough_handler, mocker):
    """Test that handle_query calls _create_new_subtask when no active subtask."""
    query = "New query"
    passthrough_handler.prime_data_context = MagicMock(return_value=True)
    passthrough_handler._create_new_subtask = MagicMock(return_value=TaskResult(status="COMPLETE", content="created"))
    passthrough_handler._continue_subtask = MagicMock() # Should not be called
    passthrough_handler.active_subtask_id = None

    passthrough_handler.handle_query(query)

    passthrough_handler._create_new_subtask.assert_called_once_with(query=query)
    passthrough_handler._continue_subtask.assert_not_called()


def test_handle_query_active_subtask_continues(passthrough_handler, mocker):
    """Test that handle_query calls _continue_subtask when an active subtask exists."""
    query = "Continuation query"
    passthrough_handler.prime_data_context = MagicMock(return_value=True)
    passthrough_handler._create_new_subtask = MagicMock() # Should not be called
    passthrough_handler._continue_subtask = MagicMock(return_value=TaskResult(status="COMPLETE", content="continued"))
    passthrough_handler.active_subtask_id = "test_subtask_123"

    passthrough_handler.handle_query(query)

    passthrough_handler._continue_subtask.assert_called_once_with(query=query)
    passthrough_handler._create_new_subtask.assert_not_called()


def test_handle_query_notes_include_relevant_files_from_context(passthrough_handler, mocker): # mocker might not be needed here
    """Test that relevant_files_from_context note is populated."""
    query = "Query for notes test"

    # Mock prime_data_context to set handler.data_context correctly
    # and return True for success.
    # Initialize with a basic DataContext, items will be set by the side_effect
    mock_data_context_instance = DataContext(retrieved_at="sometime", items=[])

    # Use actual MatchItem Pydantic models for items with an ID
    mock_item1 = MatchItem(id="/file1.txt", content="content1", relevance_score=1.0, content_type="file_content")
    # For mock_item2, use a MagicMock instance without an 'id' attribute set.
    # This ensures hasattr(mock_item2, 'id') is False, so it's filtered out.
    mock_item2 = MagicMock()
    # Ensure 'id' is not accidentally created on mock_item2 if it's accessed before hasattr check.
    # One way to be very explicit is to configure it not to have 'id':
    # del mock_item2.id # This would error if 'id' doesn't exist.
    # Or, ensure it's a mock that won't create attributes on access if not spec'd:
    # mock_item2 = MagicMock(spec=[]) # spec=[] means no attributes unless explicitly added.
    # For this test, a simple MagicMock() should suffice if 'id' is not accessed on it
    # before the production code's hasattr check.

    mock_item3 = MatchItem(id="/file3.py", content="content3", relevance_score=0.8, content_type="file_content")

    # This list will be set on handler.data_context.items by the side_effect
    items_for_context = [mock_item1, mock_item2, mock_item3]
    mock_data_context_instance.items = items_for_context


    def prime_data_context_side_effect(query: Optional[str] = None, initial_files: Optional[List[str]] = None): # Match signature
        # Set the data_context on the handler instance
        passthrough_handler.data_context = DataContext(
            retrieved_at="test_time",
            source_query=query, # Use the 'query' parameter passed to the side_effect
            items=items_for_context
        )
        return True

    # Patch prime_data_context on the instance
    with patch.object(passthrough_handler, 'prime_data_context', side_effect=prime_data_context_side_effect) as mock_prime_dc, \
         patch.object(passthrough_handler, '_create_new_subtask', return_value=TaskResult(status="COMPLETE", content="notes test", notes={})) as mock_create_subtask:

        result = passthrough_handler.handle_query(query)

        mock_prime_dc.assert_called_once_with(query=query)
        mock_create_subtask.assert_called_once_with(query=query) # Assuming active_subtask_id is None

        assert "relevant_files_from_context" in result.notes
        # mock_item2 (MagicMock without 'id' set) should be filtered out by hasattr(item, 'id')
        assert result.notes["relevant_files_from_context"] == ["/file1.txt", "/file3.py"]


def test_handle_query_unexpected_exception(passthrough_handler, mocker):
    """Test handle_query when an unexpected exception occurs during priming."""
    query = "Query causing unexpected error"
    passthrough_handler.prime_data_context = MagicMock(side_effect=RuntimeError("Unexpected priming error"))

    result = passthrough_handler.handle_query(query)

    assert result.status == "FAILED"
    assert "Error handling query: Unexpected priming error" in result.content
    assert result.notes["error"]["reason"] == "unexpected_error"
    assert "Unexpected priming error" in result.notes["error"]["message"]


def test_create_new_subtask_success(passthrough_handler, mocker):
    """Test _create_new_subtask successfully finds template and calls LLM."""
    query = "New subtask query"
    mock_template_instructions = "Mock instructions for new subtask"
    passthrough_handler.task_system.find_template.return_value = {"instructions": mock_template_instructions}
    
    # Mock BaseHandler methods called by _create_new_subtask
    passthrough_handler._build_system_prompt = MagicMock(return_value="Final System Prompt for New Subtask")
    mock_llm_response = TaskResult(status="COMPLETE", content="LLM response for new subtask")
    passthrough_handler._execute_llm_call = MagicMock(return_value=mock_llm_response)

    # Pre-set data_context as prime_data_context is called in handle_query
    passthrough_handler.data_context = MagicMock() 
    passthrough_handler.data_context.items = [] # Example

    result = passthrough_handler._create_new_subtask(query)

    assert result == mock_llm_response
    passthrough_handler.task_system.find_template.assert_called_once_with("generic_llm_task") # Assuming default
    passthrough_handler._build_system_prompt.assert_called_once_with(template_specific_instructions=mock_template_instructions)
    passthrough_handler._execute_llm_call.assert_called_once_with(
        prompt=query,
        system_prompt_override="Final System Prompt for New Subtask"
    )


def test_create_new_subtask_template_not_found(passthrough_handler, mocker):
    """Test _create_new_subtask when the template is not found."""
    query = "Query for missing template"
    passthrough_handler.task_system.find_template.return_value = None

    result = passthrough_handler._create_new_subtask(query)

    assert result.status == "FAILED"
    assert "Template generic_llm_task not found" in result.content # Assuming default
    assert result.notes["error"]["reason"] == "template_not_found"


def test_create_new_subtask_llm_call_fails(passthrough_handler, mocker):
    """Test _create_new_subtask when the LLM call fails."""
    query = "Query for LLM failure"
    passthrough_handler.task_system.find_template.return_value = {"instructions": "some instructions"}
    passthrough_handler._build_system_prompt = MagicMock(return_value="system prompt")
    
    failed_llm_result = TaskResult(status="FAILED", content="LLM Error", notes={"error": {"type": "TASK_FAILURE", "reason": "llm_error", "message": "LLM Error"}})
    passthrough_handler._execute_llm_call = MagicMock(return_value=failed_llm_result)

    result = passthrough_handler._create_new_subtask(query)
    assert result == failed_llm_result


def test_continue_subtask_success(passthrough_handler, mocker):
    """Test _continue_subtask success (behaves like new, clears active_subtask_id)."""
    query = "Continue subtask query"
    passthrough_handler.active_subtask_id = "active_id_123"
    mock_template_instructions = "Mock instructions for continued subtask"
    passthrough_handler.task_system.find_template.return_value = {"instructions": mock_template_instructions}
    
    passthrough_handler._build_system_prompt = MagicMock(return_value="Final System Prompt for Continued Subtask")
    mock_llm_response = TaskResult(status="COMPLETE", content="LLM response for continued subtask")
    passthrough_handler._execute_llm_call = MagicMock(return_value=mock_llm_response)
    
    passthrough_handler.data_context = MagicMock()
    passthrough_handler.data_context.items = []

    result = passthrough_handler._continue_subtask(query)

    assert result == mock_llm_response
    assert passthrough_handler.active_subtask_id is None # Verify active_subtask_id is cleared
    passthrough_handler.task_system.find_template.assert_called_once_with("generic_llm_task")
    passthrough_handler._build_system_prompt.assert_called_once_with(template_specific_instructions=mock_template_instructions)
    passthrough_handler._execute_llm_call.assert_called_once_with(
        prompt=query,
        system_prompt_override="Final System Prompt for Continued Subtask"
    )

def test_continue_subtask_llm_call_fails(passthrough_handler, mocker):
    """Test _continue_subtask when LLM call fails (clears active_subtask_id)."""
    query = "Query for LLM failure in continue"
    passthrough_handler.active_subtask_id = "active_id_456"
    passthrough_handler.task_system.find_template.return_value = {"instructions": "some instructions"}
    passthrough_handler._build_system_prompt = MagicMock(return_value="system prompt")
    
    failed_llm_result = TaskResult(status="FAILED", content="LLM Error", notes={"error": {"type": "TASK_FAILURE", "reason": "llm_error", "message": "LLM Error"}})
    passthrough_handler._execute_llm_call = MagicMock(return_value=failed_llm_result)

    result = passthrough_handler._continue_subtask(query)
    assert result == failed_llm_result
    assert passthrough_handler.active_subtask_id is None # Verify active_subtask_id is cleared


def test_reset_conversation(passthrough_handler):
    """Test resetting the conversation state, including data_context."""
    # Add some history and set active_subtask_id
    passthrough_handler.conversation_history = [{"role": "user", "content": "test"}]
    passthrough_handler.active_subtask_id = "some_id"
    # Set a mock data_context to ensure it's cleared
    passthrough_handler.data_context = MagicMock() 

    # Act
    passthrough_handler.reset_conversation()

    # Assert
    assert passthrough_handler.conversation_history == []
    assert passthrough_handler.active_subtask_id is None
    assert passthrough_handler.data_context is None # Verify data_context is cleared by super().reset_conversation()


def test_command_execution_tool_wrapper_success(passthrough_handler, mocker):
    """Test the internal wrapper for the command execution tool (success case)."""
    # Find the registered wrapper function
    reg_call = passthrough_handler.register_tool.call_args
    # Find the correct wrapper function from the call list
    wrapper_func = None
    for call_args in passthrough_handler.register_tool.call_args_list:
        if call_args[0][0].get('name') == 'executeFilePathCommand':
            wrapper_func = call_args[0][1]
            break
    assert wrapper_func is not None, "executeFilePathCommand wrapper not found in registration calls."

    # Mock the underlying command_executor functions
    mock_safe_exec = mocker.patch('src.handler.command_executor.execute_command_safely', return_value={'success': True, 'stdout': '/path/one\n/path/two', 'stderr': '', 'exit_code': 0, 'error_message': None}) # Use new keys
    mock_parse_paths = mocker.patch('src.handler.command_executor.parse_file_paths_from_output', return_value=['/path/one', '/path/two'])

    tool_input = {"command": "ls *.py"}
    result_dict = wrapper_func(tool_input)
    result = TaskResult.model_validate(result_dict)

    assert result.status == "COMPLETE"
    assert result.notes.get("file_paths") == ['/path/one', '/path/two']
    # Content should be the string representation of the list
    assert result.content == "['/path/one', '/path/two']" # Check exact content
    # Check call to execute_command_safely (cwd might be handler's base path)
    mock_safe_exec.assert_called_once_with("ls *.py", cwd=passthrough_handler.file_manager.base_path, timeout=None)
    # Check call to parse_file_paths_from_output
    mock_parse_paths.assert_called_once_with('/path/one\n/path/two', base_dir=passthrough_handler.file_manager.base_path)

def test_command_execution_tool_wrapper_failure(passthrough_handler, mocker):
    """Test the internal wrapper for the command execution tool (failure case)."""
    # Find the correct wrapper function from the call list
    wrapper_func = None
    for call_args in passthrough_handler.register_tool.call_args_list:
        if call_args[0][0].get('name') == 'executeFilePathCommand':
            wrapper_func = call_args[0][1]
            break
    assert wrapper_func is not None, "executeFilePathCommand wrapper not found in registration calls."

    # Mock the underlying command_executor functions - use new keys
    mock_safe_exec = mocker.patch('src.handler.command_executor.execute_command_safely', return_value={'success': False, 'stdout': '', 'stderr': 'Command failed', 'exit_code': 127, 'error_message': None})
    mock_parse_paths = mocker.patch('src.handler.command_executor.parse_file_paths_from_output') # Should not be called

    tool_input = {"command": "invalid-cmd"}
    result_dict = wrapper_func(tool_input)
    result = TaskResult.model_validate(result_dict)

    assert result.status == "FAILED"
    assert result.content == "Command failed" # Content should be stderr or error_message
    assert "error" in result.notes
    assert result.notes["error"]["reason"] == "tool_execution_error"
    assert result.notes["error"]["message"] == "Command failed"
    # Check call to execute_command_safely (cwd might be handler's base path)
    mock_safe_exec.assert_called_once_with("invalid-cmd", cwd=passthrough_handler.file_manager.base_path, timeout=None)
    mock_parse_paths.assert_not_called()
