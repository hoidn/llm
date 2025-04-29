"""
Unit tests for the BaseHandler class.
Focuses on logic implemented in Phase 1, Set B.
Mocks pydantic-ai Agent interactions.
"""

import pytest
import os
import logging
from unittest.mock import MagicMock, patch, ANY

# Mock pydantic-ai before importing BaseHandler
# This prevents BaseHandler from failing if pydantic-ai isn't installed during test collection
mock_agent_instance = MagicMock(name="MockAgentInstance")
mock_agent_class = MagicMock(name="MockAgentClass", return_value=mock_agent_instance)
mock_openai_model = MagicMock(name="MockOpenAIModel")
mock_anthropic_model = MagicMock(name="MockAnthropicModel")


# Use patch context manager or decorator for modules
# Patching the *lookup* location, not the source location
@patch.dict(
    "sys.modules",
    {
        "pydantic_ai": MagicMock(Agent=mock_agent_class, __version__="mock"),
        "pydantic_ai.models": MagicMock(
            OpenAIModel=mock_openai_model, AnthropicModel=mock_anthropic_model
        ),
    },
)
def test_module_import_works_with_mock():
    # This test just ensures our mocking allows the module to be imported
    from src.handler.base_handler import BaseHandler, PYDANTIC_AI_AVAILABLE

    assert PYDANTIC_AI_AVAILABLE is True  # Mock makes it seem available


# Now import BaseHandler after potentially mocking pydantic_ai
# Note: If tests run in parallel or order changes, this might need adjustment.
# Consider placing mocks in conftest.py for broader scope if needed.
from src.handler.base_handler import BaseHandler # Removed PYDANTIC_AI_AVAILABLE import here
from src.handler.file_access import FileAccessManager
from src.handler.file_context_manager import FileContextManager
from src.handler.llm_interaction_manager import LLMInteractionManager # Added import

# Import the module itself to mock its functions
from src.handler import command_executor


# Import the module itself to mock its functions
from src.handler import command_executor
# Import the module containing the class to be mocked
from src.handler import llm_interaction_manager as llm_manager_module


# --- Fixtures ---


@pytest.fixture
def mock_task_system():
    """Provides a mock TaskSystem."""
    return MagicMock(name="MockTaskSystem")


@pytest.fixture
def mock_memory_system():
    """Provides a mock MemorySystem."""
    return MagicMock(name="MockMemorySystem")


@pytest.fixture
def mock_file_manager():
    """Provides a mock FileAccessManager instance."""
    fm = MagicMock(spec=FileAccessManager)
    fm.base_path = "/mock/base"  # Set a base path for the mock
    return fm


@pytest.fixture
def mock_command_executor_module():
    """Mocks the command_executor module functions"""
    with patch("src.handler.base_handler.command_executor") as mock_module:
        # Configure the mock functions within the module mock
        mock_module.execute_command_safely = MagicMock(name="execute_command_safely")
        mock_module.parse_file_paths_from_output = MagicMock(
            name="parse_file_paths_from_output"
        )
        # Make default timeout accessible if needed by the code under test
        mock_module.DEFAULT_TIMEOUT = 5
        yield mock_module


@pytest.fixture(autouse=True)  # Apply mock agent to all tests in this file
def apply_mock_pydantic_ai():
    """Ensure pydantic_ai is mocked for all tests."""
    # Reset mocks before each test
    mock_agent_instance.reset_mock()
    # Reset the class mock itself and its return value
    mock_agent_class.reset_mock()
    mock_agent_class.return_value = mock_agent_instance
    mock_openai_model.reset_mock()
    mock_anthropic_model.reset_mock()

    # Patch the lookup location within base_handler module specifically (REMOVED - no longer needed)
    # This is more robust than sys.modules patching if imports are complex
    with (
        # Patches for Agent, OpenAIModel, AnthropicModel, PYDANTIC_AI_AVAILABLE in base_handler removed
        # as base_handler no longer directly uses them after refactoring.

        # Patch the PYDANTIC_AI_AVAILABLE constant within the llm_interaction_manager module,
        # as LLMInteractionManager *does* use it.
        patch("src.handler.llm_interaction_manager.PYDANTIC_AI_AVAILABLE", True),
    ):
        yield  # Run the test with mocks active


@pytest.fixture
def base_handler_config():
    """Provides a sample config dictionary."""
    return {
        "base_system_prompt": "Test Prompt",
        "openai_api_key": "fake_openai_key",
        "anthropic_api_key": "fake_anthropic_key",
        "file_manager_base_path": "/test/base",
        "command_executor_timeout": 10,
        "command_executor_cwd": "/test/cmd/cwd",  # Add specific cwd for testing
    }


# Mock the LLMInteractionManager class at the location where BaseHandler looks for it
@pytest.fixture
@patch("src.handler.base_handler.LLMInteractionManager")
@patch("src.handler.base_handler.FileContextManager")
@patch("src.handler.base_handler.FileAccessManager")
def base_handler(
    mock_fm_class,      # Mock for FileAccessManager class
    mock_fcm_class,     # Mock for FileContextManager class
    mock_llm_manager_class, # Mock for LLMInteractionManager class
    mock_task_system,
    mock_memory_system,
    base_handler_config,
    mock_file_manager, # Instance mock for FileAccessManager
):
    """Provides a BaseHandler instance with mocked dependencies and agent."""
    # Configure the mock instances returned by the class mocks
    mock_fm_class.return_value = mock_file_manager
    # Create mock instances for FileContextManager and LLMInteractionManager
    mock_fcm_instance = MagicMock(spec=FileContextManager)
    mock_fcm_class.return_value = mock_fcm_instance
    mock_llm_manager_instance = MagicMock(spec=LLMInteractionManager)
    # Add a mock agent attribute to the mock manager instance if tests need it
    mock_llm_manager_instance.agent = MagicMock(name="MockAgentOnManager")
    mock_llm_manager_class.return_value = mock_llm_manager_instance

    # Instantiate BaseHandler - this will trigger __init__
    # It will now receive the mock instances via the class mocks
    handler = BaseHandler(
        task_system=mock_task_system,
        memory_system=mock_memory_system,
        default_model_identifier="openai:gpt-mock",  # Use a mock identifier
        config=base_handler_config.copy(),  # Use a copy to avoid test interference
    )
    # The handler instance will have:
    # handler.file_context_manager = mock_fcm_instance
    # handler.llm_manager = mock_llm_manager_instance
    return handler


# --- Test __init__ ---


# Test __init__
@patch("src.handler.base_handler.LLMInteractionManager")
@patch("src.handler.base_handler.FileContextManager")
@patch("src.handler.base_handler.FileAccessManager")
def test_init_initializes_components(
    mock_fm_class,      # Mock for FileAccessManager class
    mock_fcm_class,     # Mock for FileContextManager class
    mock_llm_manager_class, # Mock for LLMInteractionManager class
    mock_task_system,
    mock_memory_system,
    base_handler_config,
    mock_file_manager,
):
    """Test __init__ stores dependencies and initializes state."""
    # Configure mock instances returned by class mocks for this specific test
    mock_fm_class.return_value = mock_file_manager
    mock_fcm_instance = MagicMock(spec=FileContextManager)
    mock_fcm_class.return_value = mock_fcm_instance
    mock_llm_manager_instance = MagicMock(spec=LLMInteractionManager)
    mock_llm_manager_class.return_value = mock_llm_manager_instance

    handler = BaseHandler(
        task_system=mock_task_system,
        memory_system=mock_memory_system,
        default_model_identifier="openai:gpt-mock",
        config=base_handler_config,
    )

    assert handler.task_system == mock_task_system
    assert handler.memory_system == mock_memory_system
    assert handler.config == base_handler_config
    assert handler.default_model_identifier == "openai:gpt-mock"
    assert handler.file_manager == mock_file_manager
    assert handler.file_context_manager == mock_fcm_instance # Check FCM instance
    assert handler.llm_manager == mock_llm_manager_instance # Check LLM Manager instance

    # Check managers were initialized correctly
    mock_fm_class.assert_called_once_with(
        base_path=base_handler_config["file_manager_base_path"]
    )
    mock_fcm_class.assert_called_once_with(
        memory_system=mock_memory_system, file_manager=mock_file_manager
    )
    mock_llm_manager_class.assert_called_once_with(
        default_model_identifier="openai:gpt-mock", config=base_handler_config
    )

    # Check other state
    assert handler.tool_executors == {}
    assert handler.registered_tools == {}
    assert handler.conversation_history == []
    assert handler.debug_mode is False
    assert handler.base_system_prompt == base_handler_config["base_system_prompt"]

    # Agent initialization is now handled by LLMInteractionManager,
    # so we just check that the manager was initialized correctly above.
    # Old checks for direct agent init are removed.


# Remove tests that checked specific agent model selection logic within BaseHandler.__init__
# as that logic is now inside LLMInteractionManager.
# We only need to test that BaseHandler passes the correct identifier and config.

# Keep tests for BaseHandler's handling of config, dependencies, and internal state.


# --- Test register_tool ---


def test_register_tool_success(base_handler, caplog):
    """Test successful tool registration stores spec and executor."""
    tool_spec = {"name": "my_tool", "description": "Does stuff", "input_schema": {}}

    def executor_func(inputs):
        pass

    with caplog.at_level(logging.WARNING):
        result = base_handler.register_tool(tool_spec, executor_func)
        # Check warning about dynamic registration is logged
        assert (
            "dynamic registration with the live pydantic-ai Agent instance is complex"
            in caplog.text
        )

    assert result is True
    assert "my_tool" in base_handler.tool_executors
    assert base_handler.tool_executors["my_tool"] == executor_func
    assert "my_tool" in base_handler.registered_tools
    assert base_handler.registered_tools["my_tool"] == tool_spec


def test_register_tool_missing_name(base_handler, caplog):
    """Test tool registration fails if name is missing."""
    tool_spec = {"description": "Does stuff", "input_schema": {}}

    def executor_func(inputs):
        pass

    with caplog.at_level(logging.ERROR):
        result = base_handler.register_tool(tool_spec, executor_func)
        assert "'name' missing in tool_spec" in caplog.text

    assert result is False
    assert "my_tool" not in base_handler.tool_executors
    assert "my_tool" not in base_handler.registered_tools


def test_register_tool_non_callable_executor(base_handler, caplog):
    """Test tool registration fails if executor is not callable."""
    tool_spec = {"name": "my_tool", "description": "Does stuff", "input_schema": {}}
    executor_func = "not a function"

    with caplog.at_level(logging.ERROR):
        result = base_handler.register_tool(tool_spec, executor_func)
        assert "executor_func is not callable" in caplog.text

    assert result is False
    assert "my_tool" not in base_handler.tool_executors
    assert "my_tool" not in base_handler.registered_tools
    # Check warning about agent registration complexity
    assert base_handler.llm_manager is not None # Ensure manager exists
    # Assuming the mock llm_manager has a mock agent attribute for this check
    if base_handler.llm_manager and base_handler.llm_manager.agent:
         assert "LLMInteractionManager's agent instance is complex" in caplog.text
    else:
         assert "LLMInteractionManager or its agent is not available" in caplog.text


# --- Test execute_file_path_command ---


def test_execute_file_path_command_success(
    base_handler, mock_command_executor_module, base_handler_config
):
    """Test successful command execution and parsing."""
    command = "find . -name '*.py'"
    mock_output = "/test/base/file1.py\n/test/base/subdir/file2.py\n"
    mock_parsed_paths = ["/test/base/file1.py", "/test/base/subdir/file2.py"]

    # Configure mocks on the module mock
    mock_command_executor_module.execute_command_safely.return_value = {
        "success": True,
        "output": mock_output,
        "error": "",
        "exit_code": 0,
    }
    mock_command_executor_module.parse_file_paths_from_output.return_value = (
        mock_parsed_paths
    )

    result = base_handler.execute_file_path_command(command)

    assert result == mock_parsed_paths
    # Check execute_command_safely was called with correct args from config
    mock_command_executor_module.execute_command_safely.assert_called_once_with(
        command,
        cwd=base_handler_config["command_executor_cwd"],  # Specific CWD from config
        timeout=base_handler_config[
            "command_executor_timeout"
        ],  # Specific timeout from config
    )
    mock_command_executor_module.parse_file_paths_from_output.assert_called_once_with(
        mock_output
    )


def test_execute_file_path_command_failure(
    base_handler, mock_command_executor_module, base_handler_config, caplog
):
    """Test command execution failure returns empty list and logs error."""
    command = "badcommand"
    # Configure mocks
    mock_command_executor_module.execute_command_safely.return_value = {
        "success": False,
        "output": "",
        "error": "Command not found",
        "exit_code": 127,
    }

    with caplog.at_level(logging.ERROR):
        result = base_handler.execute_file_path_command(command)
        assert "Command execution failed" in caplog.text
        assert "(Exit Code: 127)" in caplog.text
        assert "badcommand" in caplog.text
        assert "Error: Command not found" in caplog.text

    assert result == []
    mock_command_executor_module.execute_command_safely.assert_called_once_with(
        command,
        cwd=base_handler_config["command_executor_cwd"],
        timeout=base_handler_config["command_executor_timeout"],
    )
    mock_command_executor_module.parse_file_paths_from_output.assert_not_called()


def test_execute_file_path_command_debug_logging(
    base_handler, mock_command_executor_module, base_handler_config, caplog
):
    """Test debug logging during command execution."""
    base_handler.set_debug_mode(True)  # Enable debug
    command = "echo 'debug_test.txt'"
    mock_output = "debug_test.txt\n"
    mock_parsed = [
        "/test/cmd/cwd/debug_test.txt"
    ]  # Assuming relative path resolved in cwd

    mock_command_executor_module.execute_command_safely.return_value = {
        "success": True,
        "output": mock_output,
        "error": "",
        "exit_code": 0,
    }
    mock_command_executor_module.parse_file_paths_from_output.return_value = mock_parsed

    with caplog.at_level(logging.DEBUG):
        result = base_handler.execute_file_path_command(command)

    assert result == mock_parsed
    # Check for specific debug messages
    assert f"[DEBUG] Executing file path command: {command}" in caplog.text
    assert "[DEBUG] Command result: Success=True, ExitCode=0" in caplog.text
    assert f"[DEBUG] Parsed file paths: {mock_parsed}" in caplog.text


# --- Test reset_conversation ---


def test_reset_conversation(base_handler, caplog):
    """Test resetting conversation clears history and logs."""
    base_handler.conversation_history = [{"role": "user", "content": "hello"}]
    assert len(base_handler.conversation_history) == 1

    with caplog.at_level(logging.INFO):
        base_handler.reset_conversation()

    assert base_handler.conversation_history == []
    assert "Conversation history reset." in caplog.text
    # Agent reset logic is removed from BaseHandler


# --- Test log_debug ---


def test_log_debug_disabled(base_handler, caplog):
    """Test log_debug does nothing when debug mode is off."""
    base_handler.debug_mode = False
    with caplog.at_level(logging.DEBUG):
        base_handler.log_debug("Test message")
    assert len(caplog.records) == 0  # No messages logged at DEBUG level


def test_log_debug_enabled(base_handler, caplog):
    """Test log_debug logs message when debug mode is on."""
    base_handler.debug_mode = True
    with caplog.at_level(logging.DEBUG):
        base_handler.log_debug("Test message")
    # Check logger name and level if using standard logging
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "DEBUG"
    assert "[DEBUG] Test message" in caplog.text  # Check formatted output


# --- Test set_debug_mode ---


def test_set_debug_mode_enables(base_handler, caplog):
    """Test enabling debug mode sets flag, logs info and debug messages."""
    base_handler.debug_mode = False
    with caplog.at_level(logging.DEBUG):  # Capture DEBUG level to see both messages
        base_handler.set_debug_mode(True)
    assert base_handler.debug_mode is True
    # Check logs from BaseHandler
    assert any(
        record.levelname == "INFO" and "Debug mode enabled." in record.message
        for record in caplog.records
    )
    assert any(
        record.levelname == "DEBUG"
        and "[DEBUG] Debug logging is now active." in record.message
        for record in caplog.records
    )
    # Check that LLMInteractionManager's set_debug_mode was called
    base_handler.llm_manager.set_debug_mode.assert_called_once_with(True)


def test_set_debug_mode_disables(base_handler, caplog):
    """Test disabling debug mode sets flag and logs info message."""
    base_handler.debug_mode = True
    with caplog.at_level(logging.INFO):  # Capture INFO level
        base_handler.set_debug_mode(False)
    assert base_handler.debug_mode is False
    # Check logs
    assert any(
        record.levelname == "INFO" and "Debug mode disabled." in record.message
        for record in caplog.records
    )
    # Ensure the BaseHandler debug message is NOT logged after disabling
    # (because log_debug checks the flag *before* logging)
    # Note: The INFO message "Debug mode disabled" is still logged.

    # Check that LLMInteractionManager's set_debug_mode was called
    base_handler.llm_manager.set_debug_mode.assert_called_once_with(False)


# --- Test Deferred Methods (Placeholders) ---


def test_build_system_prompt_deferred(base_handler):
    """Verify deferred method raises NotImplementedError."""
    with pytest.raises(
        NotImplementedError, match="_build_system_prompt implementation deferred"
    ):
        base_handler._build_system_prompt()


# Renamed from test_get_relevant_files_deferred
def test_get_relevant_files_delegates(base_handler):
    """Verify _get_relevant_files delegates to FileContextManager."""
    query = "test query"
    base_handler._get_relevant_files(query)
    # BaseHandler.__init__ creates self.file_context_manager using the mocked class
    # So, base_handler.file_context_manager is the mock instance
    base_handler.file_context_manager.get_relevant_files.assert_called_once_with(query)


# Renamed from test_create_file_context_deferred
def test_create_file_context_delegates(base_handler):
    """Verify _create_file_context delegates to FileContextManager."""
    file_paths = ["path/a.py", "path/b.py"]
    base_handler._create_file_context(file_paths)
    base_handler.file_context_manager.create_file_context.assert_called_once_with(file_paths)


def test_execute_tool_deferred(base_handler):
    """Verify deferred method raises NotImplementedError."""
    with pytest.raises(
        NotImplementedError, match="_execute_tool implementation deferred"
    ):
        base_handler._execute_tool("tool_name", {})


# --- Test _execute_llm_call ---

def test_execute_llm_call_delegates(base_handler):
    """Verify _execute_llm_call delegates to LLMInteractionManager."""
    prompt = "test llm prompt"
    # Set some history to test it's passed
    base_handler.conversation_history = [{"role": "user", "content": "previous"}]
    # Mock the manager's execute_call method to avoid NotImplementedError
    base_handler.llm_manager.execute_call = MagicMock(name="execute_call")
    # Define expected return value from the mock manager call
    mock_result = {"status": "COMPLETE", "content": "Mock LLM Response"}
    base_handler.llm_manager.execute_call.return_value = mock_result

    # Call the method on BaseHandler
    result = base_handler._execute_llm_call(prompt)

    # Assert the manager's method was called with correct args
    base_handler.llm_manager.execute_call.assert_called_once_with(
        prompt=prompt,
        conversation_history=base_handler.conversation_history, # Check history is passed
        system_prompt_override=None, # Default
        tools_override=None,         # Default
        output_type_override=None,   # Default
    )
    # Assert the result from the manager is returned by BaseHandler
    assert result == mock_result
    # TODO: Add test for history update once implemented in BaseHandler


def test_execute_llm_call_delegates_with_overrides(base_handler):
    """Verify _execute_llm_call delegates overrides to LLMInteractionManager."""
    prompt = "test llm prompt"
    system_override = "System Override"
    tools_override = [lambda x: x] # Dummy tool list
    output_override = str # Dummy output type

    base_handler.llm_manager.execute_call = MagicMock(name="execute_call")
    mock_result = {"status": "COMPLETE", "content": "Mock LLM Response Override"}
    base_handler.llm_manager.execute_call.return_value = mock_result

    result = base_handler._execute_llm_call(
        prompt,
        system_prompt_override=system_override,
        tools_override=tools_override,
        output_type_override=output_override,
    )

    base_handler.llm_manager.execute_call.assert_called_once_with(
        prompt=prompt,
        conversation_history=base_handler.conversation_history, # Should be empty by default here
        system_prompt_override=system_override,
        tools_override=tools_override,
        output_type_override=output_override,
    )
    assert result == mock_result
