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
from src.handler.base_handler import BaseHandler, PYDANTIC_AI_AVAILABLE
from src.handler.file_access import FileAccessManager

# Import the module itself to mock its functions
from src.handler import command_executor


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

    # Patch the lookup location within base_handler module specifically
    # This is more robust than sys.modules patching if imports are complex
    with (
        patch("src.handler.base_handler.Agent", mock_agent_class),
        patch("src.handler.base_handler.OpenAIModel", mock_openai_model),
        patch("src.handler.base_handler.AnthropicModel", mock_anthropic_model),
        patch("src.handler.base_handler.PYDANTIC_AI_AVAILABLE", True),
    ):  # Assume available for most tests
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


@pytest.fixture
@patch(
    "src.handler.base_handler.FileAccessManager"
)  # Mock FileAccessManager instantiation
def base_handler(
    mock_fm_class,
    mock_task_system,
    mock_memory_system,
    base_handler_config,
    mock_file_manager,
):
    """Provides a BaseHandler instance with mocked dependencies and agent."""
    # Configure the mock FileAccessManager instance returned by the class mock
    # Use the mock_file_manager fixture which already has base_path set
    mock_fm_class.return_value = mock_file_manager

    # Instantiate BaseHandler - this will trigger __init__ and agent initialization
    handler = BaseHandler(
        task_system=mock_task_system,
        memory_system=mock_memory_system,
        default_model_identifier="openai:gpt-mock",  # Use a mock identifier
        config=base_handler_config.copy(),  # Use a copy to avoid test interference
    )
    return handler


# --- Test __init__ ---


# Test is implicitly covered by the base_handler fixture setup, but add explicit checks
@patch("src.handler.base_handler.FileAccessManager")
def test_init_initializes_components(
    mock_fm_class,
    mock_task_system,
    mock_memory_system,
    base_handler_config,
    mock_file_manager,
):
    """Test __init__ stores dependencies and initializes state."""
    mock_fm_class.return_value = mock_file_manager  # Use the configured mock instance

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
    # Check FileAccessManager was called with path from config
    mock_fm_class.assert_called_once_with(
        base_path=base_handler_config["file_manager_base_path"]
    )

    assert handler.tool_executors == {}
    assert handler.registered_tools == {}
    assert handler.conversation_history == []
    assert handler.debug_mode is False
    assert handler.base_system_prompt == base_handler_config["base_system_prompt"]

    # Check pydantic-ai agent initialization (using mocks)
    assert handler.agent == mock_agent_instance
    mock_openai_model.assert_called_once_with(
        api_key=base_handler_config["openai_api_key"], model="gpt-mock"
    )
    mock_agent_class.assert_called_once_with(
        model=mock_openai_model.return_value,
        system_prompt=base_handler_config["base_system_prompt"],
    )


@patch("src.handler.base_handler.FileAccessManager")
def test_init_anthropic_model(
    mock_fm_class,
    mock_task_system,
    mock_memory_system,
    base_handler_config,
    mock_file_manager,
):
    """Test __init__ selects Anthropic model correctly."""
    mock_fm_class.return_value = mock_file_manager

    BaseHandler(
        task_system=mock_task_system,
        memory_system=mock_memory_system,
        default_model_identifier="anthropic:claude-mock",
        config=base_handler_config,
    )
    mock_anthropic_model.assert_called_once_with(
        api_key=base_handler_config["anthropic_api_key"], model="claude-mock"
    )
    mock_agent_class.assert_called_once_with(
        model=mock_anthropic_model.return_value,
        system_prompt=base_handler_config["base_system_prompt"],
    )


@patch("src.handler.base_handler.FileAccessManager")
def test_init_no_model_identifier(
    mock_fm_class,
    mock_task_system,
    mock_memory_system,
    base_handler_config,
    mock_file_manager,
    caplog,
):
    """Test __init__ handles missing model identifier."""
    mock_fm_class.return_value = mock_file_manager

    with caplog.at_level(logging.WARNING):
        handler = BaseHandler(
            task_system=mock_task_system,
            memory_system=mock_memory_system,
            default_model_identifier=None,  # No identifier
            config=base_handler_config,
        )
        assert "No default_model_identifier provided" in caplog.text
    assert handler.agent is None
    mock_agent_class.assert_not_called()


@patch("src.handler.base_handler.FileAccessManager")
@patch.dict(os.environ, {}, clear=True)  # Ensure no env vars interfere
def test_init_missing_api_key(
    mock_fm_class,
    mock_task_system,
    mock_memory_system,
    base_handler_config,
    mock_file_manager,
    caplog,
):
    """Test __init__ handles missing API key."""
    mock_fm_class.return_value = mock_file_manager
    config_no_key = base_handler_config.copy()
    del config_no_key["openai_api_key"]  # Remove key from config

    with caplog.at_level(logging.ERROR):
        handler = BaseHandler(
            task_system=mock_task_system,
            memory_system=mock_memory_system,
            default_model_identifier="openai:gpt-mock",
            config=config_no_key,  # Use config without key
        )
        assert "Failed to initialize pydantic-ai Agent" in caplog.text
        assert "OpenAI API key not found" in caplog.text
    assert handler.agent is None
    mock_agent_class.assert_not_called()  # Agent init should fail before class call


@patch("src.handler.base_handler.FileAccessManager")
def test_init_unsupported_provider(
    mock_fm_class,
    mock_task_system,
    mock_memory_system,
    base_handler_config,
    mock_file_manager,
    caplog,
):
    """Test __init__ handles unsupported model provider."""
    mock_fm_class.return_value = mock_file_manager

    with caplog.at_level(logging.ERROR):
        handler = BaseHandler(
            task_system=mock_task_system,
            memory_system=mock_memory_system,
            default_model_identifier="unsupported:model-x",  # Unsupported
            config=base_handler_config,
        )
        assert "Failed to initialize pydantic-ai Agent" in caplog.text
        assert "Unsupported pydantic-ai model provider: unsupported" in caplog.text
    assert handler.agent is None
    mock_agent_class.assert_not_called()


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
    # Check debug log about agent reset verification
    assert (
        "pydantic-ai agent state reset (if applicable) needs verification."
        in caplog.text
    )
    # Add assertion for agent reset mock call if implemented e.g. mock_agent_instance.reset.assert_called_once()


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
    # Check logs
    assert any(
        record.levelname == "INFO" and "Debug mode enabled." in record.message
        for record in caplog.records
    )
    assert any(
        record.levelname == "DEBUG"
        and "[DEBUG] Debug logging is now active." in record.message
        for record in caplog.records
    )
    # Add assertions for agent instrumentation mock calls if implemented


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
    # Ensure the debug message is NOT logged after disabling
    assert not any(
        record.levelname == "DEBUG"
        and "[DEBUG] Debug logging is now active." in record.message
        for record in caplog.records
    )
    # Add assertions for agent instrumentation mock calls if implemented


# --- Test Deferred Methods (Placeholders) ---


def test_build_system_prompt_deferred(base_handler):
    """Verify deferred method raises NotImplementedError."""
    with pytest.raises(
        NotImplementedError, match="_build_system_prompt implementation deferred"
    ):
        base_handler._build_system_prompt()


def test_get_relevant_files_deferred(base_handler):
    """Verify deferred method raises NotImplementedError."""
    with pytest.raises(
        NotImplementedError, match="_get_relevant_files implementation deferred"
    ):
        base_handler._get_relevant_files("query")


def test_create_file_context_deferred(base_handler):
    """Verify deferred method raises NotImplementedError."""
    with pytest.raises(
        NotImplementedError, match="_create_file_context implementation deferred"
    ):
        base_handler._create_file_context([])


def test_execute_tool_deferred(base_handler):
    """Verify deferred method raises NotImplementedError."""
    with pytest.raises(
        NotImplementedError, match="_execute_tool implementation deferred"
    ):
        base_handler._execute_tool("tool_name", {})
