import pytest
from unittest.mock import patch, MagicMock, ANY, call
import os

# Mock dependencies before importing BaseHandler
MockTaskSystem = MagicMock()
MockMemorySystem = MagicMock()
MockFileAccessManager = MagicMock()
MockFileContextManager = MagicMock()
MockLLMInteractionManager = MagicMock()
MockCommandExecutor = MagicMock()

# Apply patches globally for the test module
patchers = [
    patch('src.handler.base_handler.TaskSystem', MockTaskSystem),
    patch('src.handler.base_handler.MemorySystem', MockMemorySystem),
    patch('src.handler.base_handler.FileAccessManager', MockFileAccessManager),
    patch('src.handler.base_handler.FileContextManager', MockFileContextManager),
    patch('src.handler.base_handler.LLMInteractionManager', MockLLMInteractionManager),
    patch('src.handler.base_handler.command_executor', MockCommandExecutor),
    # Patch TaskResult if it's used for type hinting or instantiation
    patch('src.handler.base_handler.TaskResult', MagicMock())
]

@pytest.fixture(autouse=True)
def apply_patches():
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()

# Now import the class under test
from src.handler.base_handler import BaseHandler
# Import TaskResult properly now that it's potentially patched or available
from src.system.models import TaskResult


# --- Fixtures ---

@pytest.fixture
def mock_dependencies():
    """Provides fresh mocks for each test."""
    # Reset mocks to clear previous calls and configurations
    MockTaskSystem.reset_mock()
    MockMemorySystem.reset_mock()
    MockFileAccessManager.reset_mock()
    MockFileContextManager.reset_mock()
    MockLLMInteractionManager.reset_mock()
    MockCommandExecutor.reset_mock()

    # Return instances of the mocks
    return {
        "task_system": MockTaskSystem(),
        "memory_system": MockMemorySystem(),
        "file_manager": MockFileAccessManager(),
        "file_context_manager": MockFileContextManager(),
        "llm_manager": MockLLMInteractionManager(),
        "command_executor": MockCommandExecutor, # Module-level functions
    }

@pytest.fixture
def base_handler_instance(mock_dependencies):
    """Provides a BaseHandler instance with mocked dependencies."""
    # Configure mocks before handler instantiation if needed
    MockFileAccessManager.return_value = mock_dependencies["file_manager"]
    MockFileContextManager.return_value = mock_dependencies["file_context_manager"]
    MockLLMInteractionManager.return_value = mock_dependencies["llm_manager"]

    config = {
        "base_system_prompt": "Test Handler Prompt",
        "file_manager_base_path": "/test/base",
        "command_executor_timeout": 10,
    }
    handler = BaseHandler(
        task_system=mock_dependencies["task_system"],
        memory_system=mock_dependencies["memory_system"],
        default_model_identifier="handler:model",
        config=config,
    )
    # Ensure the handler uses the correct mock instances (should happen via patch)
    assert handler.file_manager == mock_dependencies["file_manager"]
    assert handler.file_context_manager == mock_dependencies["file_context_manager"]
    assert handler.llm_manager == mock_dependencies["llm_manager"]
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

    MockFileAccessManager.return_value = mock_file_manager
    MockFileContextManager.return_value = mock_file_context_manager
    MockLLMInteractionManager.return_value = mock_llm_manager

    config = {"base_system_prompt": "Config Prompt", "file_manager_base_path": "/config/path"}
    model_id = "config:model"

    # Act
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

    # Verify dependencies were instantiated correctly
    MockFileAccessManager.assert_called_once_with(base_path="/config/path")
    assert handler.file_manager == mock_file_manager

    MockFileContextManager.assert_called_once_with(
        memory_system=mock_memory_system, file_manager=mock_file_manager
    )
    assert handler.file_context_manager == mock_file_context_manager

    MockLLMInteractionManager.assert_called_once_with(
        default_model_identifier=model_id, config=config
    )
    assert handler.llm_manager == mock_llm_manager

def test_register_tool_success(base_handler_instance):
    """Test successful tool registration."""
    tool_spec = {"name": "my_tool", "description": "Does something", "input_schema": {}}
    def executor_func(inp): return f"Executed with {inp}"

    result = base_handler_instance.register_tool(tool_spec, executor_func)

    assert result is True
    assert "my_tool" in base_handler_instance.tool_executors
    assert base_handler_instance.tool_executors["my_tool"] == executor_func
    assert "my_tool" in base_handler_instance.registered_tools
    assert base_handler_instance.registered_tools["my_tool"] == tool_spec
    # TODO: Add assertion for LLM manager interaction if/when implemented

def test_register_tool_fail_no_name(base_handler_instance):
    """Test tool registration failure when name is missing."""
    tool_spec = {"description": "Missing name"}
    def executor_func(inp): pass
    result = base_handler_instance.register_tool(tool_spec, executor_func)
    assert result is False
    assert not base_handler_instance.tool_executors
    assert not base_handler_instance.registered_tools

def test_register_tool_fail_not_callable(base_handler_instance):
    """Test tool registration failure when executor is not callable."""
    tool_spec = {"name": "bad_executor"}
    executor_func = "not a function"
    result = base_handler_instance.register_tool(tool_spec, executor_func) # type: ignore
    assert result is False
    assert "bad_executor" not in base_handler_instance.tool_executors

def test_execute_file_path_command_success(base_handler_instance, mock_dependencies):
    """Test successful execution of a file path command."""
    # Arrange
    command = "find . -name '*.py'"
    mock_executor = mock_dependencies["command_executor"]
    mock_executor.execute_command_safely.return_value = {
        "success": True, "exit_code": 0, "output": "file1.py\n./subdir/file2.py\nnonexistent.py", "error": ""
    }
    # Mock parse_file_paths_from_output to return relative paths
    mock_executor.parse_file_paths_from_output.return_value = ["file1.py", "subdir/file2.py", "nonexistent.py"]

    # Mock os.path.exists used indirectly via file_manager._resolve_path check
    # We need to mock the check within the handler's logic now
    def mock_resolve_path(path):
        # Simulate resolving relative to the configured base path
        abs_path = os.path.abspath(os.path.join(base_handler_instance.file_manager.base_path, path))
        # Only allow paths starting with the base path
        if abs_path.startswith(os.path.abspath(base_handler_instance.file_manager.base_path)):
            return abs_path
        else:
            # Simulate FileAccessManager raising ValueError for paths outside base
            raise ValueError("Path outside base directory")

    # Mock os.path.exists called by the handler after resolving
    def mock_exists(path):
        # Only file1.py and subdir/file2.py exist in our mock scenario
        return "file1.py" in path or "file2.py" in path

    base_handler_instance.file_manager._resolve_path = MagicMock(side_effect=mock_resolve_path)
    with patch('os.path.exists', side_effect=mock_exists):
        # Act
        result = base_handler_instance.execute_file_path_command(command)

    # Assert
    mock_executor.execute_command_safely.assert_called_once_with(
        command, cwd="/test/base", timeout=10
    )
    mock_executor.parse_file_paths_from_output.assert_called_once_with("file1.py\n./subdir/file2.py\nnonexistent.py")
    # Check that the returned paths are absolute and exist
    expected_paths = [
        os.path.abspath("/test/base/file1.py"),
        os.path.abspath("/test/base/subdir/file2.py")
    ]
    assert sorted(result) == sorted(expected_paths)
    # Verify resolve was called for each parsed path
    assert base_handler_instance.file_manager._resolve_path.call_count == 3


def test_execute_file_path_command_failure(base_handler_instance, mock_dependencies):
    """Test failed execution of a file path command."""
    command = "bad command"
    mock_executor = mock_dependencies["command_executor"]
    mock_executor.execute_command_safely.return_value = {
        "success": False, "exit_code": 1, "output": "", "error": "Command failed"
    }

    result = base_handler_instance.execute_file_path_command(command)

    assert result == []
    mock_executor.execute_command_safely.assert_called_once_with(
        command, cwd="/test/base", timeout=10
    )
    mock_executor.parse_file_paths_from_output.assert_not_called()

def test_reset_conversation(base_handler_instance):
    """Test resetting the conversation history."""
    base_handler_instance.conversation_history = [{"role": "user", "content": "test"}]
    base_handler_instance.reset_conversation()
    assert base_handler_instance.conversation_history == []

def test_set_debug_mode(base_handler_instance, mock_dependencies):
    """Test enabling and disabling debug mode."""
    mock_llm_manager = mock_dependencies["llm_manager"]
    assert base_handler_instance.debug_mode is False

    base_handler_instance.set_debug_mode(True)
    assert base_handler_instance.debug_mode is True
    mock_llm_manager.set_debug_mode.assert_called_once_with(True)

    base_handler_instance.set_debug_mode(False)
    assert base_handler_instance.debug_mode is False
    mock_llm_manager.set_debug_mode.assert_called_with(False) # Called again

def test_log_debug(base_handler_instance):
    """Test debug logging respects the debug_mode flag."""
    with patch('logging.debug') as mock_logging_debug:
        # Debug off
        base_handler_instance.debug_mode = False
        base_handler_instance.log_debug("Test message 1")
        mock_logging_debug.assert_not_called()

        # Debug on
        base_handler_instance.debug_mode = True
        base_handler_instance.log_debug("Test message 2")
        mock_logging_debug.assert_called_once_with("[DEBUG] Test message 2")

# --- Tests for Phase 2b Implementation ---

def test_base_handler_execute_llm_call_success(base_handler_instance, mock_dependencies):
    """Test successful LLM call delegation and history update."""
    # Arrange
    mock_llm_manager = mock_dependencies["llm_manager"]
    mock_llm_manager.execute_call.return_value = {
        "success": True,
        "content": "Assistant response",
        "usage": {"tokens": 50},
        "tool_calls": None
    }
    user_prompt = "User query"
    base_handler_instance.conversation_history = [{"role": "user", "content": "Previous"}]
    initial_history_len = len(base_handler_instance.conversation_history)

    # Act
    result = base_handler_instance._execute_llm_call(user_prompt)

    # Assert
    assert isinstance(result, TaskResult)
    assert result.status == "COMPLETE"
    assert result.content == "Assistant response"
    assert result.notes == {"usage": {"tokens": 50}}

    # Verify manager call
    mock_llm_manager.execute_call.assert_called_once_with(
        prompt=user_prompt,
        conversation_history=base_handler_instance.conversation_history[:-2], # Original history passed
        system_prompt_override=None,
        tools_override=None,
        output_type_override=None
    )

    # Verify history update
    assert len(base_handler_instance.conversation_history) == initial_history_len + 2
    assert base_handler_instance.conversation_history[-2] == {"role": "user", "content": user_prompt}
    assert base_handler_instance.conversation_history[-1] == {"role": "assistant", "content": "Assistant response"}

def test_base_handler_execute_llm_call_failure(base_handler_instance, mock_dependencies):
    """Test failed LLM call delegation."""
    # Arrange
    mock_llm_manager = mock_dependencies["llm_manager"]
    mock_llm_manager.execute_call.return_value = {
        "success": False,
        "error": "LLM API error"
    }
    user_prompt = "This will fail"
    initial_history = list(base_handler_instance.conversation_history) # Copy

    # Act
    result = base_handler_instance._execute_llm_call(user_prompt)

    # Assert
    assert isinstance(result, TaskResult)
    assert result.status == "FAILED"
    assert "LLM API error" in result.content
    assert result.notes["error"]["type"] == "TASK_FAILURE" # type: ignore
    assert result.notes["error"]["reason"] == "llm_error" # type: ignore
    assert result.notes["error"]["message"] == "LLM API error" # type: ignore

    # Verify manager call
    mock_llm_manager.execute_call.assert_called_once_with(
        prompt=user_prompt,
        conversation_history=initial_history, # History passed
        system_prompt_override=None,
        tools_override=None,
        output_type_override=None
    )

    # Verify history NOT updated
    assert base_handler_instance.conversation_history == initial_history

def test_base_handler_execute_llm_call_no_manager(base_handler_instance):
    """Test LLM call when manager is not available."""
    base_handler_instance.llm_manager = None
    result = base_handler_instance._execute_llm_call("Test")

    assert isinstance(result, TaskResult)
    assert result.status == "FAILED"
    assert "LLM Manager not initialized" in result.content
    assert result.notes["error"]["reason"] == "dependency_error" # type: ignore

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
    assert prompt3 == f"{base_prompt}\n\nRelevant File Context:\n```\n{file_ctx}\n```"

    # Base + Template + File Context
    prompt4 = base_handler_instance._build_system_prompt(template=template_instr, file_context=file_ctx)
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
    expected_result = TaskResult(status="COMPLETE", content="Already TaskResult", notes={"detail": 1})
    mock_executor = MagicMock(return_value=expected_result)
    base_handler_instance.tool_executors[tool_name] = mock_executor

    result = base_handler_instance._execute_tool(tool_name, tool_input)

    assert result == expected_result # Should return the object directly
    mock_executor.assert_called_once_with(tool_input)

def test_execute_tool_success_taskresult_dict(base_handler_instance):
    """Test executing a tool that returns a dict resembling TaskResult."""
    tool_name = "taskresult_dict_tool"
    tool_input = {}
    # Simulate a dict returned by the tool
    tool_return_dict = {"status": "COMPLETE", "content": "From Dict", "notes": {"source": "dict"}}
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
    assert result.notes["error"]["type"] == "TASK_FAILURE" # type: ignore
    assert result.notes["error"]["reason"] == "template_not_found" # type: ignore

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
    assert result.notes["error"]["type"] == "TASK_FAILURE" # type: ignore
    assert result.notes["error"]["reason"] == "tool_execution_error" # type: ignore
    assert str(test_exception) in result.notes["error"]["message"] # type: ignore
    mock_executor.assert_called_once_with(tool_input)

def test_get_relevant_files_delegation(base_handler_instance, mock_dependencies):
    """Verify _get_relevant_files delegates to FileContextManager."""
    mock_fcm = mock_dependencies["file_context_manager"]
    mock_fcm.get_relevant_files.return_value = ["file1.txt", "file2.py"]
    query = "search query"

    result = base_handler_instance._get_relevant_files(query)

    assert result == ["file1.txt", "file2.py"]
    mock_fcm.get_relevant_files.assert_called_once_with(query)

def test_create_file_context_delegation(base_handler_instance, mock_dependencies):
    """Verify _create_file_context delegates to FileContextManager."""
    mock_fcm = mock_dependencies["file_context_manager"]
    mock_fcm.create_file_context.return_value = "File Context String"
    paths = ["file1.txt", "file2.py"]

    result = base_handler_instance._create_file_context(paths)

    assert result == "File Context String"
    mock_fcm.create_file_context.assert_called_once_with(paths)
