import pytest
from unittest.mock import patch, MagicMock, ANY, call, AsyncMock # Ensure call is imported
import os # Import os for path manipulation
import sys
from typing import Callable, List, Dict, Any # Add necessary types

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Assume these are the actual classes/modules being mocked
from src.main import Application
from src.system.models import TaskResult, TaskFailureError # Added TaskFailureError
from src.memory.memory_system import MemorySystem
from src.task_system.task_system import TaskSystem
from src.handler.passthrough_handler import PassthroughHandler
from src.handler.file_access import FileAccessManager
from src.handler.llm_interaction_manager import LLMInteractionManager
from src.memory.indexers.git_repository_indexer import GitRepositoryIndexer
from src import dispatcher
# Import modules for patching targets
# No longer needed for spec, but keep for potential type hints if desired
# from src.executors import system_executors as system_executors_module
# from src.tools import anthropic_tools as anthropic_tools_module
# from src.executors import aider_executors as aider_executors_module

# Import Aider components conditionally
try:
    from src.aider_bridge.bridge import AiderBridge
    # No longer need AiderExecutors class directly for patching
    AIDER_IMPORT_SUCCESS = True
    AIDER_AVAILABLE_IMPORT_PATH = 'src.main.AIDER_AVAILABLE' # Path used in Application
except ImportError:
    AiderBridge = None
    AIDER_IMPORT_SUCCESS = False
    AIDER_AVAILABLE_IMPORT_PATH = 'src.main.AIDER_AVAILABLE' # Path still exists even if False

# Import the class needed for the spec fix (if still needed for other mocks)
# from src.executors.aider_executors import AiderExecutorFunctions # No longer needed for patching

# Import Anthropic tool specs directly for registration check
from src.tools.anthropic_tools import (
    ANTHROPIC_VIEW_SPEC,
    ANTHROPIC_CREATE_SPEC,
    ANTHROPIC_STR_REPLACE_SPEC,
    ANTHROPIC_INSERT_SPEC
)


# Define dummy tool specs used in Application init
# Aider specs removed as Aider integration is deferred
DUMMY_SYS_GET_CONTEXT_SPEC = {"name": "system:get_context", "description": "Sys Get Context", "input_schema": {}}
DUMMY_SYS_READ_FILES_SPEC = {"name": "system:read_files", "description": "Sys Read Files", "input_schema": {}}


# Define PROJECT_ROOT for use in the test if needed
# Adjust the path based on the actual location of test_main.py relative to the project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# --- Test Fixture ---
@pytest.fixture
def app_components(mocker, tmp_path): # Add tmp_path
    """Fixture to mock all major dependencies of Application."""
    # Mock the core component classes themselves
    mock_memory_system_cls = mocker.patch('src.main.MemorySystem', spec=MemorySystem)
    mock_task_system_cls = mocker.patch('src.main.TaskSystem', spec=TaskSystem)
    mock_handler_cls = mocker.patch('src.main.PassthroughHandler', spec=PassthroughHandler)
    mock_fm_cls = mocker.patch('src.main.FileAccessManager', spec=FileAccessManager)
    # Mock the LLMInteractionManager *inside* the handler module where it's likely used
    mock_llm_manager_cls = mocker.patch('src.handler.base_handler.LLMInteractionManager', spec=LLMInteractionManager)
    # Mock AiderBridge conditionally based on environment or keep it simple
    mock_aider_bridge_cls = mocker.patch('src.main.AiderBridge', spec=AiderBridge)
    # Mock GitRepositoryIndexer
    mock_indexer_cls = mocker.patch('src.main.GitRepositoryIndexer', spec=GitRepositoryIndexer)

    # --- START FIX: Patch specific functions/static methods directly ---
    # Patch SystemExecutorFunctions methods
    mock_exec_get_context = mocker.patch('src.main.SystemExecutorFunctions.execute_get_context', name="mock_execute_get_context")
    mock_exec_read_files = mocker.patch('src.main.SystemExecutorFunctions.execute_read_files', name="mock_execute_read_files")

    # Patch AiderExecutorFunctions methods
    mock_aider_auto_func = mocker.patch('src.main.AiderExecutors.execute_aider_automatic', new_callable=AsyncMock, name="mock_execute_aider_automatic")
    mock_aider_inter_func = mocker.patch('src.main.AiderExecutors.execute_aider_interactive', new_callable=AsyncMock, name="mock_execute_aider_interactive")

    # Patch Anthropic tool functions
    mock_anthropic_view_func = mocker.patch('src.main.anthropic_tools.view', name="mock_anthropic_view")
    mock_anthropic_create_func = mocker.patch('src.main.anthropic_tools.create', name="mock_anthropic_create")
    mock_anthropic_replace_func = mocker.patch('src.main.anthropic_tools.str_replace', name="mock_anthropic_replace")
    mock_anthropic_insert_func = mocker.patch('src.main.anthropic_tools.insert', name="mock_anthropic_insert")
    # --- END FIX ---

    # Create mock instances that the mocked classes will return
    mock_memory_system_instance = MagicMock(spec=MemorySystem)
    mock_task_system_instance = MagicMock(spec=TaskSystem)
    mock_handler_instance = MagicMock(spec=PassthroughHandler)
    mock_fm_instance = MagicMock(spec=FileAccessManager)
    mock_llm_manager_instance = MagicMock(spec=LLMInteractionManager)
    mock_aider_bridge_instance = MagicMock(spec=AiderBridge)
    mock_indexer_instance = MagicMock(spec=GitRepositoryIndexer) # Instance for indexer

    # Configure mock instances with attributes accessed during Application.__init__
    mock_fm_instance.base_path = "/mocked/base/path" # For logging
    # Add the memory_system attribute so hasattr checks pass in Application.__init__
    mock_handler_instance.memory_system = None
    mock_task_system_instance.memory_system = None

    # Configure the mocked classes to return the mock instances
    mock_memory_system_cls.return_value = mock_memory_system_instance
    mock_task_system_cls.return_value = mock_task_system_instance
    mock_handler_cls.return_value = mock_handler_instance
    mock_fm_cls.return_value = mock_fm_instance
    mock_llm_manager_cls.return_value = mock_llm_manager_instance # LLMManager instance mock
    mock_aider_bridge_cls.return_value = mock_aider_bridge_instance
    mock_indexer_cls.return_value = mock_indexer_instance # Indexer instance mock

    # Configure mocks attached TO the handler instance, as they are instantiated within BaseHandler init
    mock_handler_instance.file_manager = mock_fm_instance # Simulate internal assignment
    mock_handler_instance.llm_manager = mock_llm_manager_instance # Simulate internal assignment
    mock_handler_instance.get_provider_identifier.return_value = "mock:provider"
    registered_tools_storage = {} # Use a real dict to capture registrations
    tool_executors_storage = {}
    def mock_register_tool_side_effect(spec, executor):
        name = spec.get("name")
        if name:
            registered_tools_storage[name] = {"spec": spec, "executor": executor}
            tool_executors_storage[name] = executor
            return True
        return False
    mock_handler_instance.register_tool = MagicMock(side_effect=mock_register_tool_side_effect)
    mock_handler_instance.registered_tools = registered_tools_storage # Point to the dict
    mock_handler_instance.tool_executors = tool_executors_storage # Point to the dict
    mock_handler_instance.get_tools_for_agent.side_effect = lambda: list(tool_executors_storage.values()) # Return current executors

    # No need to configure static methods on class mocks anymore

    return {
        # Core Component Class Mocks
        "MockMemorySystem": mock_memory_system_cls,
        "MockTaskSystem": mock_task_system_cls,
        "MockPassthroughHandler": mock_handler_cls,
        "MockFileAccessManager": mock_fm_cls,
        "MockLLMInteractionManager": mock_llm_manager_cls,
        "MockAiderBridge": mock_aider_bridge_cls,
        "MockGitRepositoryIndexer": mock_indexer_cls,

        # Core Component Instance Mocks
        "mock_memory_system_instance": mock_memory_system_instance,
        "mock_task_system_instance": mock_task_system_instance,
        "mock_handler_instance": mock_handler_instance,
        "mock_fm_instance": mock_fm_instance,
        "mock_llm_manager_instance": mock_llm_manager_instance,
        "mock_aider_bridge_instance": mock_aider_bridge_instance,
        "mock_indexer_instance": mock_indexer_instance,

        # Expose storage for assertions
        "registered_tools_storage": registered_tools_storage,
        "tool_executors_storage": tool_executors_storage,

        # Expose specific function/method mocks
        "mock_exec_get_context": mock_exec_get_context,
        "mock_exec_read_files": mock_exec_read_files,
        "mock_aider_auto_func": mock_aider_auto_func,
        "mock_aider_inter_func": mock_aider_inter_func,
        "mock_anthropic_view_func": mock_anthropic_view_func,
        "mock_anthropic_create_func": mock_anthropic_create_func,
        "mock_anthropic_replace_func": mock_anthropic_replace_func,
        "mock_anthropic_insert_func": mock_anthropic_insert_func,
    }

# --- Tests ---

def test_application_init_minimal(app_components):
    """Test minimal Application initialization."""
    app = Application()
    assert isinstance(app, Application)
    # Check components were instantiated (mocks were called)
    app_components["MockFileAccessManager"].assert_called_once()
    app_components["MockTaskSystem"].assert_called_once()
    app_components["MockPassthroughHandler"].assert_called_once()
    app_components["MockMemorySystem"].assert_called_once()
    # Check internal instances are set
    assert app.file_access_manager is not None
    assert app.task_system is not None
    assert app.passthrough_handler is not None
    assert app.memory_system is not None

def test_application_init_wiring(app_components):
    """Verify components are instantiated and wired correctly during __init__."""
    # Arrange: Set a default provider ID
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"
    # Arrange: Mock the return value for get_tools_for_agent
    mock_executors = [lambda x: x] # Dummy executor list
    app_components["mock_handler_instance"].get_tools_for_agent.return_value = mock_executors

    # Act: Instantiate Application
    app = Application(config={}) # Pass empty config

    # Assert component instances were created by the Mocks
    assert app.memory_system == app_components['mock_memory_system_instance']
    assert app.task_system == app_components['mock_task_system_instance']
    assert app.passthrough_handler == app_components['mock_handler_instance']
    assert app.file_access_manager == app_components['mock_fm_instance']

    # Assert wiring calls were made (using the instances returned by the mocks)
    app_components['mock_task_system_instance'].set_handler.assert_called_once_with(app.passthrough_handler)

    # Verify attribute assignments
    assert app.passthrough_handler.memory_system == app_components['mock_memory_system_instance']
    assert app.task_system.memory_system == app_components['mock_memory_system_instance']

    # Assert tool registration calls (at least system tools should be registered)
    app_components['mock_handler_instance'].register_tool.assert_called()
    system_context_call = next((c for c in app_components['mock_handler_instance'].register_tool.call_args_list if c.args[0].get('name') == 'system:get_context'), None)
    assert system_context_call is not None, "system:get_context tool was not registered"
    assert callable(system_context_call.args[1])

    # Assert agent initialization call
    app_components['mock_handler_instance'].get_tools_for_agent.assert_called_once()
    app_components['mock_llm_manager_instance'].initialize_agent.assert_called_once_with(tools=mock_executors)


def test_index_repository_success(app_components, tmp_path):
    """Test successful repository indexing."""
    # Arrange
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    repo_path = str(tmp_path)

    MockIndexerClass = app_components["MockGitRepositoryIndexer"]
    mock_indexer_instance = app_components["mock_indexer_instance"]
    mock_indexer_instance.index_repository.return_value = {"file1.py": "metadata1"}

    app = Application()

    # Act
    options = {"include_patterns": ["*.py"]}
    success = app.index_repository(repo_path, options=options)

    # Assert
    assert success is True
    MockIndexerClass.assert_called_once_with(repo_path=repo_path)
    assert mock_indexer_instance.include_patterns == ["*.py"]
    mock_indexer_instance.index_repository.assert_called_once_with(memory_system=app.memory_system)
    assert repo_path in app.indexed_repositories


def test_handle_query_success(app_components):
    """Test successful query handling delegation."""
    # Arrange
    app = Application()
    mock_handler = app_components['mock_handler_instance']
    expected_result = TaskResult(status="COMPLETE", content="Query response")
    mock_handler.handle_query.return_value = expected_result

    # Act
    query = "Hello assistant"
    result_dict = app.handle_query(query)

    # Assert
    mock_handler.handle_query.assert_called_once_with(query)
    assert result_dict == expected_result.model_dump(exclude_none=True)

def test_handle_query_handler_error(app_components):
    """Test handling of errors raised by the handler."""
     # Arrange
    app = Application()
    mock_handler = app_components['mock_handler_instance']
    mock_handler.handle_query.side_effect = ValueError("Handler internal error")

    # Act
    query = "Problematic query"
    result_dict = app.handle_query(query)

    # Assert
    mock_handler.handle_query.assert_called_once_with(query)
    assert result_dict.get("status") == "FAILED"
    assert "Unexpected error during query handling" in result_dict.get("content", "")
    assert "Handler internal error" in result_dict.get("content", "")
    assert result_dict.get("notes", {}).get("error", {}).get("reason") == "unexpected_error"


def test_reset_conversation(app_components):
    """Test conversation reset delegation."""
    app = Application()
    mock_handler = app_components['mock_handler_instance']

    app.reset_conversation()

    mock_handler.reset_conversation.assert_called_once()

def test_handle_task_command_success(app_components):
    """Test successful task command delegation to dispatcher."""
     # Arrange
    app = Application()
    expected_result_dict = {"status": "COMPLETE", "content": "Task done", "notes": {}}
    # Patch the dispatcher function *where it's imported* in main.py
    with patch('src.main.dispatcher.execute_programmatic_task') as mock_dispatch:
        mock_dispatch.return_value = expected_result_dict

        # Act
        identifier = "some_task"
        params = {"p1": "v1"}
        flags = {"f1": True}
        result = app.handle_task_command(identifier, params, flags)

        # Assert
        mock_dispatch.assert_called_once_with(
            identifier=identifier,
            params=params,
            flags=flags,
            handler_instance=app.passthrough_handler,
            task_system_instance=app.task_system,
            memory_system=app.memory_system
        )
        assert result == expected_result_dict

def test_handle_task_command_dispatcher_error(app_components):
    """Test handling errors raised by the dispatcher."""
    # Arrange
    app = Application()
    # Patch the dispatcher function to raise an error
    with patch('src.main.dispatcher.execute_programmatic_task') as mock_dispatch:
        mock_dispatch.side_effect = Exception("Dispatcher failed")

        # Act
        identifier = "failing_task"
        result = app.handle_task_command(identifier)

        # Assert
        mock_dispatch.assert_called_once()
        assert result.get("status") == "FAILED"
        assert "Unexpected error during task command execution" in result.get("content", "")
        assert "Dispatcher failed" in result.get("content", "")
        assert result.get("notes", {}).get("error", {}).get("reason") == "unexpected_error"


@patch(AIDER_AVAILABLE_IMPORT_PATH, True) # Simulate Aider being available
def test_application_init_with_aider(app_components):
    """Verify AiderBridge is initialized and tools registered when available."""
    # Arrange (Mocks are already configured in the fixture)
    mock_aider_auto_func = app_components['mock_aider_auto_func']
    mock_aider_inter_func = app_components['mock_aider_inter_func']

    # Act
    app = Application(config={"aider_config": {"mcp_stdio_command": "aider_server"}})

    # Assert AiderBridge was instantiated
    app_components['MockAiderBridge'].assert_called_once_with(
        memory_system=app.memory_system,
        file_access_manager=app.file_access_manager,
        config={"mcp_stdio_command": "aider_server"}
    )
    assert app.aider_bridge == app_components['mock_aider_bridge_instance']

    # Assert Aider tools were registered with the handler
    registered_tools = app_components['registered_tools_storage']
    assert 'aider:automatic' in registered_tools
    assert 'aider:interactive' in registered_tools
    assert callable(registered_tools['aider:automatic']['executor'])
    assert callable(registered_tools['aider:interactive']['executor'])
    # Check that the executor wrapper correctly points to the mocked function
    # This requires calling the lambda, which might be complex to set up here.
    # Rely on the fact that the correct function was patched and passed during registration.

@patch(AIDER_AVAILABLE_IMPORT_PATH, False) # Simulate Aider being unavailable
def test_application_init_without_aider(app_components):
    """Verify AiderBridge is NOT initialized and tools NOT registered when unavailable."""
     # Act
    app = Application()

    # Assert AiderBridge was NOT instantiated
    app_components['MockAiderBridge'].assert_not_called()
    assert app.aider_bridge is None

    # Assert Aider tools were NOT registered
    registered_tools = app_components['registered_tools_storage']
    assert 'aider:automatic' not in registered_tools
    assert 'aider:interactive' not in registered_tools


@patch(AIDER_AVAILABLE_IMPORT_PATH, False) # Disable Aider for this test
def test_application_init_with_anthropic(app_components):
    """Verify Anthropic tools are registered for Anthropic provider."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "anthropic:claude-3-5-sonnet-latest"
    # Mocks for functions are already configured in the fixture

    # Act
    app = Application()

    # Assert Anthropic tools were registered
    registered_tools = app_components['registered_tools_storage']
    assert 'anthropic:view' in registered_tools
    assert 'anthropic:create' in registered_tools
    assert 'anthropic:str_replace' in registered_tools
    assert 'anthropic:insert' in registered_tools

    # Check specs and executors
    assert registered_tools['anthropic:view']['spec'] == ANTHROPIC_VIEW_SPEC
    assert callable(registered_tools['anthropic:view']['executor'])
    assert registered_tools['anthropic:create']['spec'] == ANTHROPIC_CREATE_SPEC
    assert callable(registered_tools['anthropic:create']['executor'])
    assert registered_tools['anthropic:str_replace']['spec'] == ANTHROPIC_STR_REPLACE_SPEC
    assert callable(registered_tools['anthropic:str_replace']['executor'])
    assert registered_tools['anthropic:insert']['spec'] == ANTHROPIC_INSERT_SPEC
    assert callable(registered_tools['anthropic:insert']['executor'])
    # Check that the executor wrapper correctly points to the mocked function
    # Similar to Aider, this requires calling the lambda. Rely on patching.

@patch(AIDER_AVAILABLE_IMPORT_PATH, False) # Disable Aider
def test_application_init_without_anthropic(app_components):
    """Verify Anthropic tools are NOT registered for non-Anthropic provider."""
     # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "openai:gpt-4o"

    # Act
    app = Application()

    # Assert Anthropic tools were NOT registered
    registered_tools = app_components['registered_tools_storage']
    assert 'anthropic:view' not in registered_tools
    assert 'anthropic:create' not in registered_tools
    assert 'anthropic:str_replace' not in registered_tools
    assert 'anthropic:insert' not in registered_tools
