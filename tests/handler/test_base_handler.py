import os
from unittest.mock import MagicMock, patch
import warnings

import pytest

# Import the class under test
from src.handler.base_handler import BaseHandler

# Import real classes for spec verification if needed
from src.handler.file_access import FileAccessManager
from src.handler.file_context_manager import FileContextManager
from src.handler.llm_interaction_manager import LLMInteractionManager

# Import TaskResult properly now that it's potentially patched or available
from src.system.models import TaskResult

# --- Fixtures ---


@pytest.fixture
def mock_dependencies():
    """Provides fresh mock instances for dependencies."""
    # Create instance mocks
    mocks = {
        "task_system": MagicMock(name="MockTaskSystemInstance"),
        "memory_system": MagicMock(name="MockMemorySystemInstance"),
        "file_manager": MagicMock(
            spec=FileAccessManager, name="MockFileManagerInstance"
        ),
        "file_context_manager": MagicMock(
            spec=FileContextManager, name="MockFileContextManagerInstance"
        ),
        "llm_manager": MagicMock(
            spec=LLMInteractionManager, name="MockLLMManagerInstance"
        ),
        # Mock the command_executor module itself if needed, or specific functions
        "command_executor": MagicMock(name="MockCommandExecutorModule"),
    }
    # Configure file manager base path if needed by tests
    mocks["file_manager"].base_path = "/test/base"
    # **Fix 1: Add the 'agent' attribute to the llm_manager mock**
    mocks["llm_manager"].agent = MagicMock(name="MockAgentInstance")
    return mocks


@pytest.fixture
def base_handler_instance(mock_dependencies):
    """Provides a BaseHandler instance with mocked internal managers."""
    config = {
        "base_system_prompt": "Test Handler Prompt",
        "file_manager_base_path": "/test/base",  # Ensure this matches mock if needed
        "command_executor_timeout": 10,
    }

    # Patch the manager classes during BaseHandler init
    with (
        patch("src.handler.base_handler.FileAccessManager") as MockFM,
        patch("src.handler.base_handler.FileContextManager") as MockFCM,
        patch("src.handler.base_handler.LLMInteractionManager") as MockLLM,
    ):

        # Configure the mock instances returned by the class mocks
        MockFM.return_value = mock_dependencies["file_manager"]
        MockFCM.return_value = mock_dependencies["file_context_manager"]
        # Return the pre-configured mock LLM manager (which now has .agent)
        MockLLM.return_value = mock_dependencies["llm_manager"]

        handler = BaseHandler(
            task_system=mock_dependencies["task_system"],
            memory_system=mock_dependencies["memory_system"],
            default_model_identifier="handler:model",
            config=config,
        )
        # Verify internal managers were set to our mocks
        assert handler.file_manager == mock_dependencies["file_manager"]
        assert handler.file_context_manager == mock_dependencies["file_context_manager"]
        assert handler.llm_manager == mock_dependencies["llm_manager"]
        # Verify the llm_manager mock instance has the agent attribute
        assert hasattr(handler.llm_manager, "agent")
        assert handler.llm_manager.agent is not None
        return handler


# --- Test Cases ---


def test_base_handler_init(mock_dependencies):
    """Test BaseHandler initialization and dependency setup."""
    # Arrange
    mock_file_manager = mock_dependencies["file_manager"]
    mock_file_context_manager = mock_dependencies["file_context_manager"]
    mock_llm_manager = mock_dependencies["llm_manager"]
    mock_task_system = mock_dependencies["task_system"]
    mock_memory_system = mock_dependencies["memory_system"]

    config = {
        "base_system_prompt": "Config Prompt",
        "file_manager_base_path": "/config/path",
    }
    model_id = "config:model"

    # Act
    # Patch the manager classes during BaseHandler init for this specific test
    with (
        patch("src.handler.base_handler.FileAccessManager") as MockFM,
        patch("src.handler.base_handler.FileContextManager") as MockFCM,
        patch("src.handler.base_handler.LLMInteractionManager") as MockLLM,
    ):

        # Configure the mock instances returned by the class mocks
        MockFM.return_value = mock_file_manager
        MockFCM.return_value = mock_file_context_manager
        MockLLM.return_value = mock_llm_manager  # Use the pre-configured mock

        handler = BaseHandler(
            task_system=mock_task_system,
            memory_system=mock_memory_system,
            default_model_identifier=model_id,
            config=config,
        )

        # Assert
        assert handler.task_system == mock_task_system
        assert handler.memory_system == mock_memory_system
        assert handler.config == config
        assert handler.default_model_identifier == model_id
        assert handler.base_system_prompt == "Config Prompt"
        assert handler.debug_mode is False
        assert handler.conversation_history == []
        assert handler.tool_executors == {}
        assert handler.registered_tools == {}
        assert handler.active_tool_definitions == [] # Check new attribute

        # Verify dependencies were instantiated correctly within BaseHandler's __init__
        MockFM.assert_called_once_with(base_path="/config/path")
        assert handler.file_manager == mock_file_manager

        MockFCM.assert_called_once_with(
            memory_system=mock_memory_system, file_manager=mock_file_manager
        )
        assert handler.file_context_manager == mock_file_context_manager

        MockLLM.assert_called_once_with(
            default_model_identifier=model_id, config=config
        )
        assert handler.llm_manager == mock_llm_manager


def test_register_tool_success(base_handler_instance):
    """Test successful tool registration."""
    tool_spec = {"name": "my_tool", "description": "Does something", "input_schema": {}}

    def executor_func(inp):
        return f"Executed with {inp}"

    # Ensure the llm_manager and its agent are mocked correctly by the fixture
    assert base_handler_instance.llm_manager is not None
    assert hasattr(base_handler_instance.llm_manager, "agent")
    assert base_handler_instance.llm_manager.agent is not None

    result = base_handler_instance.register_tool(tool_spec, executor_func)

    assert result is True
    assert "my_tool" in base_handler_instance.tool_executors
    assert base_handler_instance.tool_executors["my_tool"] == executor_func
    assert "my_tool" in base_handler_instance.registered_tools
    # Check the structure stored in registered_tools
    assert base_handler_instance.registered_tools["my_tool"] == {
        "spec": tool_spec,
        "executor": executor_func
    }


def test_register_tool_fail_no_name(base_handler_instance):
    """Test tool registration failure when name is missing."""
    tool_spec = {"description": "Missing name"}

    def executor_func(inp):
        pass

    result = base_handler_instance.register_tool(tool_spec, executor_func)
    assert result is False
    assert not base_handler_instance.tool_executors
    assert not base_handler_instance.registered_tools


def test_register_tool_fail_not_callable(base_handler_instance):
    """Test tool registration failure when executor is not callable."""
    tool_spec = {"name": "bad_executor"}
    executor_func = "not a function"
    result = base_handler_instance.register_tool(tool_spec, executor_func)  # type: ignore
    assert result is False
    assert "bad_executor" not in base_handler_instance.tool_executors


# Patch the specific command_executor functions used by the method under test
@patch("src.handler.base_handler.command_executor.parse_file_paths_from_output")
@patch("src.handler.base_handler.command_executor.execute_command_safely")
def test_execute_file_path_command_success(
    mock_exec_safe, mock_parse_paths, base_handler_instance
):
    """Test successful execution of a file path command."""
    # Arrange
    command = "find . -name '*.py'"
    # Configure the patched function mocks directly
    mock_exec_safe.return_value = {
        "success": True,
        "exit_code": 0,
        "output": "file1.py\n./subdir/file2.py\nnonexistent.py",
        "error": "",
    }
    mock_parse_paths.return_value = ["file1.py", "subdir/file2.py", "nonexistent.py"]

    # Mock os.path.exists used indirectly via file_manager._resolve_path check
    # We need to mock the check within the handler's logic now
    def mock_resolve_path(path):
        # Simulate resolving relative to the configured base path
        # Use the file_manager instance attached to the handler instance
        abs_path = os.path.abspath(
            os.path.join(base_handler_instance.file_manager.base_path, path)
        )
        # Only allow paths starting with the base path
        if abs_path.startswith(
            os.path.abspath(base_handler_instance.file_manager.base_path)
        ):
            return abs_path
        else:
            # Simulate FileAccessManager raising ValueError for paths outside base
            raise ValueError("Path outside base directory")

    # Mock os.path.exists called by the handler after resolving
    def mock_exists(path):
        # Only file1.py and subdir/file2.py exist in our mock scenario
        return "file1.py" in path or "file2.py" in path

    # Attach the mock resolve_path to the mocked file_manager instance
    base_handler_instance.file_manager._resolve_path = MagicMock(
        side_effect=mock_resolve_path
    )

    with patch("os.path.exists", side_effect=mock_exists):
        # Act
        result = base_handler_instance.execute_file_path_command(command)

    # Assert
    mock_exec_safe.assert_called_once_with(command, cwd="/test/base", timeout=10)
    mock_parse_paths.assert_called_once_with(
        "file1.py\n./subdir/file2.py\nnonexistent.py"
    )
    # Check that the returned paths are absolute and exist
    expected_paths = [
        os.path.abspath("/test/base/file1.py"),
        os.path.abspath("/test/base/subdir/file2.py"),
    ]
    assert sorted(result) == sorted(expected_paths)
    # Verify resolve was called for each parsed path
    assert base_handler_instance.file_manager._resolve_path.call_count == 3


# Patch the specific command_executor functions used by the method under test
@patch("src.handler.base_handler.command_executor.parse_file_paths_from_output")
@patch("src.handler.base_handler.command_executor.execute_command_safely")
def test_execute_file_path_command_failure(
    mock_exec_safe, mock_parse_paths, base_handler_instance
):
    """Test failed execution of a file path command."""
    # Arrange
    command = "bad command"
    mock_exec_safe.return_value = {
        "success": False,
        "exit_code": 1,
        "output": "",
        "error": "Command failed",
    }

    # Act
    result = base_handler_instance.execute_file_path_command(command)

    # Assert
    assert result == []
    mock_exec_safe.assert_called_once_with(command, cwd="/test/base", timeout=10)
    mock_parse_paths.assert_not_called()  # Ensure parse isn't called on failure


def test_reset_conversation(base_handler_instance):
    """Test resetting the conversation history."""
    base_handler_instance.conversation_history = [{"role": "user", "content": "test"}]
    base_handler_instance.reset_conversation()
    assert base_handler_instance.conversation_history == []


def test_set_debug_mode(base_handler_instance):
    """Test enabling and disabling debug mode."""
    # Access the mocked llm_manager via the handler instance
    mock_llm_manager = base_handler_instance.llm_manager
    assert base_handler_instance.debug_mode is False

    base_handler_instance.set_debug_mode(True)
    assert base_handler_instance.debug_mode is True
    mock_llm_manager.set_debug_mode.assert_called_once_with(True)

    base_handler_instance.set_debug_mode(False)
    assert base_handler_instance.debug_mode is False
    mock_llm_manager.set_debug_mode.assert_called_with(False)  # Called again


def test_log_debug(base_handler_instance):
    """Test debug logging respects the debug_mode flag."""
    with patch("logging.debug") as mock_logging_debug:
        # Debug off
        base_handler_instance.debug_mode = False
        base_handler_instance.log_debug("Test message 1")
        mock_logging_debug.assert_not_called()

        # Debug on
        base_handler_instance.debug_mode = True
        base_handler_instance.log_debug("Test message 2")
        mock_logging_debug.assert_called_once_with("[DEBUG] Test message 2")


# --- Tests for Phase 2b Implementation ---


def test_base_handler_execute_llm_call_success(base_handler_instance):
    """Test successful LLM call delegation and history update."""
    # Arrange
    # Access the mocked llm_manager via the handler instance
    mock_llm_manager = base_handler_instance.llm_manager
    mock_llm_manager.execute_call.return_value = {
        "success": True,
        "content": "Assistant response",
        "usage": {"tokens": 50},
        "tool_calls": None,
    }
    user_prompt = "User query"
    base_handler_instance.conversation_history = [
        {"role": "user", "content": "Previous"}
    ]
    # **Fix 2: Store history *before* the call**
    history_before_call = list(base_handler_instance.conversation_history)
    initial_history_len = len(history_before_call)

    # Act
    result = base_handler_instance._execute_llm_call(user_prompt)

    # Assert
    assert isinstance(result, TaskResult)
    assert result.status == "COMPLETE"
    assert result.content == "Assistant response"
    assert result.notes == {"usage": {"tokens": 50}}

    # Verify manager call using the history *before* the call
    mock_llm_manager.execute_call.assert_called_once_with(
        prompt=user_prompt,
        # **Fix 2: Use the stored history for assertion**
        conversation_history=history_before_call,
        system_prompt_override=None,
        tools_override=None, # Check tools_override is None by default
        output_type_override=None,
        active_tools=[] # Check active_tools is empty list by default
    )

    # Verify history update
    assert len(base_handler_instance.conversation_history) == initial_history_len + 2
    assert base_handler_instance.conversation_history[-2] == {
        "role": "user",
        "content": user_prompt,
    }
    assert base_handler_instance.conversation_history[-1] == {
        "role": "assistant",
        "content": "Assistant response",
    }


def test_base_handler_execute_llm_call_failure(base_handler_instance):
    """Test failed LLM call delegation."""
    # Arrange
    # Access the mocked llm_manager via the handler instance
    mock_llm_manager = base_handler_instance.llm_manager
    mock_llm_manager.execute_call.return_value = {
        "success": False,
        "error": "LLM API error",
    }
    user_prompt = "This will fail"
    initial_history = list(base_handler_instance.conversation_history)  # Copy

    # Act
    result = base_handler_instance._execute_llm_call(user_prompt)

    # Assert
    assert isinstance(result, TaskResult)
    assert result.status == "FAILED"
    assert "LLM API error" in result.content
    assert result.notes["error"]["type"] == "TASK_FAILURE"  # type: ignore
    assert result.notes["error"]["reason"] == "llm_error"  # type: ignore
    assert result.notes["error"]["message"] == "LLM API error"  # type: ignore

    # Verify manager call
    mock_llm_manager.execute_call.assert_called_once_with(
        prompt=user_prompt,
        conversation_history=initial_history,  # History passed
        system_prompt_override=None,
        tools_override=None,
        output_type_override=None,
        active_tools=[]
    )

    # Verify history NOT updated
    assert base_handler_instance.conversation_history == initial_history


def test_base_handler_execute_llm_call_no_manager(base_handler_instance):
    """Test LLM call when manager is not available."""
    base_handler_instance.llm_manager = None  # Manually remove manager after setup
    result = base_handler_instance._execute_llm_call("Test")

    assert isinstance(result, TaskResult)
    assert result.status == "FAILED"
    assert "LLM Manager not initialized" in result.content
    assert result.notes["error"]["reason"] == "dependency_error"  # type: ignore


def test_build_system_prompt(base_handler_instance):
    """Test building the system prompt with different components."""
    base_prompt = base_handler_instance.base_system_prompt
    template_instr = "Use JSON format."
    file_ctx = "path/to/file.py:\ncontent"

    # Base only
    prompt1 = base_handler_instance._build_system_prompt()
    assert prompt1 == base_prompt

    # Base + Template
    prompt2 = base_handler_instance._build_system_prompt(template=template_instr)
    assert prompt2 == f"{base_prompt}\n\n{template_instr}"

    # Base + File Context
    prompt3 = base_handler_instance._build_system_prompt(file_context=file_ctx)
    # **Fix 3: Assertion matches the corrected code output (double newline)**
    expected_prompt3 = f"{base_prompt}\n\nRelevant File Context:\n```\n{file_ctx}\n```"
    assert prompt3 == expected_prompt3

    # Base + Template + File Context
    prompt4 = base_handler_instance._build_system_prompt(
        template=template_instr, file_context=file_ctx
    )
    expected4 = f"{base_prompt}\n\n{template_instr}\n\nRelevant File Context:\n```\n{file_ctx}\n```"
    assert prompt4 == expected4


def test_execute_tool_success_raw_result(base_handler_instance):
    """Test executing a tool that returns a raw value."""
    tool_name = "simple_tool"
    tool_input = {"value": 5}
    mock_executor = MagicMock(return_value="Tool Result: 5")
    base_handler_instance.tool_executors[tool_name] = mock_executor

    result = base_handler_instance._execute_tool(tool_name, tool_input)

    assert isinstance(result, TaskResult)
    assert result.status == "COMPLETE"
    assert result.content == "Tool Result: 5"
    assert result.notes == {"tool_output": "Tool Result: 5"}
    mock_executor.assert_called_once_with(tool_input)


def test_execute_tool_success_taskresult_object(base_handler_instance):
    """Test executing a tool that returns a TaskResult object."""
    tool_name = "taskresult_tool"
    tool_input = {}
    expected_result = TaskResult(
        status="COMPLETE", content="Already TaskResult", notes={"detail": 1}
    )
    mock_executor = MagicMock(return_value=expected_result)
    base_handler_instance.tool_executors[tool_name] = mock_executor

    result = base_handler_instance._execute_tool(tool_name, tool_input)

    assert result == expected_result  # Should return the object directly
    mock_executor.assert_called_once_with(tool_input)


def test_execute_tool_success_taskresult_dict(base_handler_instance):
    """Test executing a tool that returns a dict resembling TaskResult."""
    tool_name = "taskresult_dict_tool"
    tool_input = {}
    # Simulate a dict returned by the tool
    tool_return_dict = {
        "status": "COMPLETE",
        "content": "From Dict",
        "notes": {"source": "dict"},
    }
    mock_executor = MagicMock(return_value=tool_return_dict)
    base_handler_instance.tool_executors[tool_name] = mock_executor

    result = base_handler_instance._execute_tool(tool_name, tool_input)

    # Verify it's reconstructed into a TaskResult object
    assert isinstance(result, TaskResult)
    assert result.status == "COMPLETE"
    assert result.content == "From Dict"
    assert result.notes == {"source": "dict"}
    mock_executor.assert_called_once_with(tool_input)


def test_execute_tool_not_found(base_handler_instance):
    """Test executing a tool that is not registered."""
    tool_name = "unknown_tool"
    tool_input = {}

    result = base_handler_instance._execute_tool(tool_name, tool_input)

    assert isinstance(result, TaskResult)
    assert result.status == "FAILED"
    assert f"Tool '{tool_name}' not found" in result.content
    assert result.notes["error"]["type"] == "TASK_FAILURE"  # type: ignore
    assert result.notes["error"]["reason"] == "template_not_found"  # type: ignore


def test_execute_tool_execution_error(base_handler_instance):
    """Test executing a tool that raises an exception."""
    tool_name = "error_tool"
    tool_input = {}
    test_exception = ValueError("Tool failed internally")
    mock_executor = MagicMock(side_effect=test_exception)
    base_handler_instance.tool_executors[tool_name] = mock_executor

    result = base_handler_instance._execute_tool(tool_name, tool_input)

    assert isinstance(result, TaskResult)
    assert result.status == "FAILED"
    assert f"Error executing tool '{tool_name}': {test_exception}" in result.content
    assert result.notes["error"]["type"] == "TASK_FAILURE"  # type: ignore
    assert result.notes["error"]["reason"] == "tool_execution_error"  # type: ignore
    assert str(test_exception) in result.notes["error"]["message"]  # type: ignore
    mock_executor.assert_called_once_with(tool_input)


def test_get_relevant_files_delegation(base_handler_instance):
    """Verify _get_relevant_files delegates to FileContextManager."""
    # Access the mocked file_context_manager via the handler instance
    mock_fcm = base_handler_instance.file_context_manager
    mock_fcm.get_relevant_files.return_value = ["file1.txt", "file2.py"]
    query = "search query"

    result = base_handler_instance._get_relevant_files(query)

    assert result == ["file1.txt", "file2.py"]
    mock_fcm.get_relevant_files.assert_called_once_with(query)


def test_create_file_context_delegation(base_handler_instance):
    """Verify _create_file_context delegates to FileContextManager."""
    # Access the mocked file_context_manager via the handler instance
    mock_fcm = base_handler_instance.file_context_manager
    mock_fcm.create_file_context.return_value = "File Context String"
    paths = ["file1.txt", "file2.py"]

    result = base_handler_instance._create_file_context(paths)

    assert result == "File Context String"
    mock_fcm.create_file_context.assert_called_once_with(paths)


def test_get_provider_identifier_success(base_handler_instance):
    """Test get_provider_identifier when LLM manager returns a provider identifier."""
    # Configure the mock LLM manager to return a provider identifier
    mock_llm_manager = base_handler_instance.llm_manager
    mock_llm_manager.get_provider_identifier.return_value = "openai:gpt-4"

    # Call the method under test
    result = base_handler_instance.get_provider_identifier()

    # Verify the result is passed through from the LLM manager
    assert result == "openai:gpt-4"
    mock_llm_manager.get_provider_identifier.assert_called_once()


def test_get_provider_identifier_none(base_handler_instance):
    """Test get_provider_identifier when LLM manager returns None."""
    # Configure the mock LLM manager to return None
    mock_llm_manager = base_handler_instance.llm_manager
    mock_llm_manager.get_provider_identifier.return_value = None

    # Call the method under test
    result = base_handler_instance.get_provider_identifier()

    # Verify the result is None
    assert result is None
    mock_llm_manager.get_provider_identifier.assert_called_once()


def test_get_provider_identifier_no_llm_manager(base_handler_instance):
    """Test get_provider_identifier when llm_manager is None."""
    # Set llm_manager to None after initialization
    base_handler_instance.llm_manager = None

    # Call the method under test
    with patch("logging.warning") as mock_warning:
        result = base_handler_instance.get_provider_identifier()

    # Verify the result is None and a warning was logged
    assert result is None
    mock_warning.assert_called_once()
    assert "LLMInteractionManager is not available" in mock_warning.call_args[0][0]


# --- Tests for set_active_tool_definitions ---

def test_set_active_tool_definitions_success(base_handler_instance):
    """Test setting active tool definitions."""
    # Create tool definitions
    tool_def1 = {"name": "tool1", "description": "Tool 1", "input_schema": {}}
    tool_def2 = {"name": "tool2", "description": "Tool 2", "input_schema": {}}
    tool_definitions_to_set = [tool_def1, tool_def2]

    # Set active tool definitions
    result = base_handler_instance.set_active_tool_definitions(tool_definitions_to_set)

    # Verify the result and the stored definitions
    assert result is True
    assert hasattr(base_handler_instance, 'active_tool_definitions')
    assert base_handler_instance.active_tool_definitions == tool_definitions_to_set


def test_set_active_tool_definitions_empty_list(base_handler_instance):
    """Test setting an empty list of active tool definitions."""
    # Set some initial definitions to verify they get cleared
    base_handler_instance.active_tool_definitions = [{"name": "initial"}]

    # Test setting empty active tools list
    result = base_handler_instance.set_active_tool_definitions([])

    # Assert
    assert result is True
    assert base_handler_instance.active_tool_definitions == []

# Note: The test for setting unknown tools is removed because
# set_active_tool_definitions does not perform validation against registered tools.


# --- Tests for tools precedence logic in _execute_llm_call ---

def test_execute_llm_call_tools_override_precedence(base_handler_instance):
    """Test that explicit tools_override takes precedence over active_tool_definitions."""
    # Access the mocked llm_manager via the handler instance
    mock_llm_manager = base_handler_instance.llm_manager
    mock_llm_manager.execute_call.return_value = {
        "success": True,
        "content": "Response with override tools",
    }

    # Register a tool and set active definitions
    tool_spec1 = {"name": "active_tool", "description": "Active Tool", "input_schema": {}}
    def executor1(inp): return f"Active Tool: {inp}"
    base_handler_instance.register_tool(tool_spec1, executor1)
    base_handler_instance.set_active_tool_definitions([tool_spec1])

    # Create override tool (callable)
    def override_tool(inp): return f"Override Tool: {inp}"
    override_tools_list = [override_tool]

    # Call with tools_override
    base_handler_instance._execute_llm_call(
        "Test prompt", tools_override=override_tools_list
    )

    # Assert that llm_manager was called with tools_override
    mock_llm_manager.execute_call.assert_called_once()
    call_kwargs = mock_llm_manager.execute_call.call_args.kwargs

    # The tools_override param should be passed, not derived from active_tool_definitions
    assert call_kwargs["tools_override"] == override_tools_list
    # active_tools (definitions) should still be passed based on the handler's state
    assert call_kwargs["active_tools"] == [tool_spec1]


def test_execute_llm_call_active_definitions_used(base_handler_instance):
    """Test that active_tool_definitions are used when no tools_override is provided."""
    # Access the mocked llm_manager via the handler instance
    mock_llm_manager = base_handler_instance.llm_manager
    mock_llm_manager.execute_call.return_value = {
        "success": True,
        "content": "Response with active tools",
    }

    # Register tools and set active definitions
    tool_spec1 = {"name": "active_tool1", "description": "Active Tool 1", "input_schema": {}}
    tool_spec2 = {"name": "active_tool2", "description": "Active Tool 2", "input_schema": {}}
    def executor1(inp): return f"Active Tool 1: {inp}"
    def executor2(inp): return f"Active Tool 2: {inp}"
    base_handler_instance.register_tool(tool_spec1, executor1)
    base_handler_instance.register_tool(tool_spec2, executor2)
    active_definitions = [tool_spec1, tool_spec2]
    base_handler_instance.set_active_tool_definitions(active_definitions)

    # Call without tools_override
    base_handler_instance._execute_llm_call("Test prompt")

    # Assert that llm_manager was called with active_tool_definitions
    mock_llm_manager.execute_call.assert_called_once()
    call_kwargs = mock_llm_manager.execute_call.call_args.kwargs

    # The tools_override param should contain the active tool executors
    assert "tools_override" in call_kwargs
    assert len(call_kwargs["tools_override"]) == 2
    # Order might not be guaranteed, check set equality
    assert set(call_kwargs["tools_override"]) == {executor1, executor2}

    # The active_tools param should contain the definitions
    assert "active_tools" in call_kwargs
    assert call_kwargs["active_tools"] == active_definitions


def test_execute_llm_call_no_tools(base_handler_instance):
    """Test that no tools are passed when neither tools_override nor active_definitions are set."""
    # Access the mocked llm_manager via the handler instance
    mock_llm_manager = base_handler_instance.llm_manager
    mock_llm_manager.execute_call.return_value = {
        "success": True,
        "content": "Response with no tools",
    }

    # Ensure no active definitions are set
    base_handler_instance.active_tool_definitions = []

    # Call without tools_override
    base_handler_instance._execute_llm_call("Test prompt")

    # Assert that llm_manager was called with None for tools_override and empty list for active_tools
    mock_llm_manager.execute_call.assert_called_once()
    call_kwargs = mock_llm_manager.execute_call.call_args.kwargs

    # The tools_override param should be None
    assert call_kwargs["tools_override"] is None
    # The active_tools param should be an empty list
    assert call_kwargs["active_tools"] == []


def test_execute_llm_call_missing_executor_in_active_definitions(base_handler_instance):
    """Test handling when an active tool definition has no corresponding executor."""
    # Register one tool outside the warning patch
    tool_spec = {"name": "real_tool", "description": "Real Tool", "input_schema": {}}
    def executor(inp): return f"Real Tool: {inp}"
    base_handler_instance.register_tool(tool_spec, executor)

    # Setup logging capture only for the tool execution part
    with patch("logging.warning") as mock_warning:
        # Access the mocked llm_manager via the handler instance
        mock_llm_manager = base_handler_instance.llm_manager
        mock_llm_manager.execute_call.return_value = {
            "success": True,
            "content": "Response with partial tools",
        }

        # Manually set active_tool_definitions to include a missing tool spec
        missing_tool_spec = {"name": "missing_tool", "description": "Missing"}
        base_handler_instance.active_tool_definitions = [tool_spec, missing_tool_spec]

        # Call without tools_override
        base_handler_instance._execute_llm_call("Test prompt")

        # Assert that llm_manager was called with only the valid tool executor
        mock_llm_manager.execute_call.assert_called_once()
        call_kwargs = mock_llm_manager.execute_call.call_args.kwargs

        # The tools_override param should contain only the valid tool executor
        assert "tools_override" in call_kwargs
        assert len(call_kwargs["tools_override"]) == 1
        assert call_kwargs["tools_override"] == [executor]

        # The active_tools param should contain both definitions
        assert "active_tools" in call_kwargs
        assert call_kwargs["active_tools"] == [tool_spec, missing_tool_spec]

        # Check that a warning was logged about the missing tool executor
        assert any(
            "missing_tool" in str(args) for args, _ in mock_warning.call_args_list
        )


# --- Tests for set_active_tool_definitions and passing active tool definitions ---

def test__execute_llm_call_passes_active_tools(base_handler_instance):
    """Test that active tool definitions are correctly passed to LLMInteractionManager.execute_call."""
    # Register two tools with specifications and executor functions
    tool_spec1 = {"name": "tool1", "description": "Tool 1", "input_schema": {}}
    tool_spec2 = {"name": "tool2", "description": "Tool 2", "input_schema": {}}

    def executor1(inp):
        return f"Tool 1: {inp}"

    def executor2(inp):
        return f"Tool 2: {inp}"

    base_handler_instance.register_tool(tool_spec1, executor1)
    base_handler_instance.register_tool(tool_spec2, executor2)

    # Set active tool definitions
    active_definitions = [tool_spec1, tool_spec2]
    base_handler_instance.set_active_tool_definitions(active_definitions)

    # Configure mock LLMInteractionManager
    mock_llm_manager = base_handler_instance.llm_manager
    mock_llm_manager.execute_call.return_value = {
        "success": True,
        "content": "Response with active tool definitions",
    }

    # Call _execute_llm_call without tools_override
    base_handler_instance._execute_llm_call("Test prompt")

    # Assert LLMInteractionManager.execute_call was called with the active tool definitions
    mock_llm_manager.execute_call.assert_called_once()
    call_kwargs = mock_llm_manager.execute_call.call_args.kwargs

    # Verify active_tools parameter contains both tool definitions
    assert "active_tools" in call_kwargs
    assert call_kwargs["active_tools"] == active_definitions

    # Verify tools_override parameter contains the corresponding executors
    assert "tools_override" in call_kwargs
    assert len(call_kwargs["tools_override"]) == 2
    assert set(call_kwargs["tools_override"]) == {executor1, executor2}
