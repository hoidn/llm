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
from src.executors import system_executors as system_executors_module
# Import the REAL module containing the functions to patch for spec
import src.tools.anthropic_tools
# Import Aider components conditionally
try:
    from src.aider_bridge.bridge import AiderBridge
    from src.executors.aider_executors import AiderExecutorFunctions as AiderExecutors
    AIDER_IMPORT_SUCCESS = True
    AIDER_AVAILABLE_IMPORT_PATH = 'src.main.AIDER_AVAILABLE' # Path used in Application
except ImportError:
    AiderBridge = None
    AiderExecutors = None
    AIDER_IMPORT_SUCCESS = False
    AIDER_AVAILABLE_IMPORT_PATH = 'src.main.AIDER_AVAILABLE' # Path still exists even if False

# Import the class needed for the spec fix
from src.executors.aider_executors import AiderExecutorFunctions


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
    # Mock the classes themselves
    mock_memory_system_cls = mocker.patch('src.main.MemorySystem', spec=MemorySystem)
    mock_task_system_cls = mocker.patch('src.main.TaskSystem', spec=TaskSystem)
    mock_handler_cls = mocker.patch('src.main.PassthroughHandler', spec=PassthroughHandler)
    mock_fm_cls = mocker.patch('src.main.FileAccessManager', spec=FileAccessManager)
    # Mock the LLMInteractionManager *inside* the handler module where it's likely used
    # Adjust path if BaseHandler imports it differently
    mock_llm_manager_cls = mocker.patch('src.handler.base_handler.LLMInteractionManager', spec=LLMInteractionManager)

    # Mock AiderBridge conditionally based on environment or keep it simple
    mock_aider_bridge_cls = mocker.patch('src.main.AiderBridge', spec=AiderBridge)
    # Mock AiderExecutors if needed
    mock_aider_exec_cls = mocker.patch('src.main.AiderExecutors', spec=AiderExecutors) # FIX: Use imported name
    # Mock Anthropic tools module if needed for registration verification
    mock_anthropic_tools = mocker.patch('src.main.anthropic_tools', spec=src.tools.anthropic_tools) # FIX: Use full module path
    # Mock GitRepositoryIndexer
    mock_indexer_cls = mocker.patch('src.main.GitRepositoryIndexer', spec=GitRepositoryIndexer)
    # Mock SystemExecutorFunctions
    mock_sys_exec_cls = mocker.patch('src.main.SystemExecutorFunctions', spec=system_executors_module.SystemExecutorFunctions)


    # Create mock instances that the mocked classes will return
    mock_memory_system_instance = MagicMock(spec=MemorySystem)
    mock_task_system_instance = MagicMock(spec=TaskSystem)
    mock_handler_instance = MagicMock(spec=PassthroughHandler)
    mock_fm_instance = MagicMock(spec=FileAccessManager)
    # --- START FIX ---
    # Configure the mock instance with the attribute needed by Application.__init__
    mock_fm_instance.base_path = "/mocked/base/path"
    # --- END FIX ---
    mock_llm_manager_instance = MagicMock(spec=LLMInteractionManager)
    mock_aider_bridge_instance = MagicMock(spec=AiderBridge)
    mock_indexer_instance = MagicMock(spec=GitRepositoryIndexer) # Instance for indexer

    # Configure the mocked classes to return the mock instances
    mock_memory_system_cls.return_value = mock_memory_system_instance
    mock_task_system_cls.return_value = mock_task_system_instance
    mock_handler_cls.return_value = mock_handler_instance
    mock_fm_cls.return_value = mock_fm_instance
    mock_llm_manager_cls.return_value = mock_llm_manager_instance # LLMManager instance mock
    mock_aider_bridge_cls.return_value = mock_aider_bridge_instance
    mock_indexer_cls.return_value = mock_indexer_instance # Indexer instance mock

    # Configure mocks attached TO the handler instance, as they are instantiated within BaseHandler init
    # We need to configure the mock_handler_instance that is returned by mock_handler_cls
    mock_handler_instance.file_manager = mock_fm_instance # Simulate internal assignment
    mock_handler_instance.llm_manager = mock_llm_manager_instance # Simulate internal assignment
    # Make get_provider_identifier return something default for tool determination
    mock_handler_instance.get_provider_identifier.return_value = "mock:provider"
    # Mock tool registration dicts/methods if needed by _determine_active_tools or agent init
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

    # Configure mock system executor static methods
    mock_exec_get_context = MagicMock(name="mock_execute_get_context")
    mock_exec_read_files = MagicMock(name="mock_execute_read_files")
    mock_sys_exec_cls.execute_get_context = mock_exec_get_context
    mock_sys_exec_cls.execute_read_files = mock_exec_read_files

    # Configure mock Aider executor static methods
    mock_aider_auto_func = AsyncMock(spec=Callable, name="mock_execute_aider_automatic")
    mock_aider_inter_func = AsyncMock(spec=Callable, name="mock_execute_aider_interactive")
    mock_aider_exec_cls.execute_aider_automatic = mock_aider_auto_func
    mock_aider_exec_cls.execute_aider_interactive = mock_aider_inter_func

    # Configure mock Anthropic tool functions and specs
    mock_anthropic_view_func = MagicMock(spec=src.tools.anthropic_tools.view)
    mock_anthropic_create_func = MagicMock(spec=src.tools.anthropic_tools.create)
    mock_anthropic_replace_func = MagicMock(spec=src.tools.anthropic_tools.str_replace)
    mock_anthropic_insert_func = MagicMock(spec=src.tools.anthropic_tools.insert)
    mock_anthropic_tools.view = mock_anthropic_view_func
    mock_anthropic_tools.create = mock_anthropic_create_func
    mock_anthropic_tools.str_replace = mock_anthropic_replace_func
    mock_anthropic_tools.insert = mock_anthropic_insert_func
    mock_anthropic_tools.ANTHROPIC_VIEW_SPEC = src.tools.anthropic_tools.ANTHROPIC_VIEW_SPEC
    mock_anthropic_tools.ANTHROPIC_CREATE_SPEC = src.tools.anthropic_tools.ANTHROPIC_CREATE_SPEC
    mock_anthropic_tools.ANTHROPIC_STR_REPLACE_SPEC = src.tools.anthropic_tools.ANTHROPIC_STR_REPLACE_SPEC
    mock_anthropic_tools.ANTHROPIC_INSERT_SPEC = src.tools.anthropic_tools.ANTHROPIC_INSERT_SPEC


    return {
        "MockMemorySystem": mock_memory_system_cls,
        "MockTaskSystem": mock_task_system_cls,
        "MockPassthroughHandler": mock_handler_cls,
        "MockFileAccessManager": mock_fm_cls,
        "MockLLMInteractionManager": mock_llm_manager_cls, # LLM Manager Class Mock
        "MockAiderBridge": mock_aider_bridge_cls,
        "MockAiderExec": mock_aider_exec_cls,
        "MockAnthropicTools": mock_anthropic_tools,
        "MockGitRepositoryIndexer": mock_indexer_cls, # Indexer Class Mock
        "MockSystemExecutorFunctions": mock_sys_exec_cls, # System Executor Class Mock

        "mock_memory_system_instance": mock_memory_system_instance,
        "mock_task_system_instance": mock_task_system_instance,
        "mock_handler_instance": mock_handler_instance,
        "mock_fm_instance": mock_fm_instance,
        "mock_llm_manager_instance": mock_llm_manager_instance, # LLM Manager Instance Mock
        "mock_aider_bridge_instance": mock_aider_bridge_instance,
        "mock_indexer_instance": mock_indexer_instance, # Indexer Instance Mock

        # Expose storage for assertions
        "registered_tools_storage": registered_tools_storage,
        "tool_executors_storage": tool_executors_storage,

        # Expose specific function mocks if needed
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
    # Check that the instance held by Application is the one returned by the Mock constructor
    assert app.memory_system == app_components['mock_memory_system_instance']
    assert app.task_system == app_components['mock_task_system_instance']
    assert app.passthrough_handler == app_components['mock_handler_instance']
    assert app.file_access_manager == app_components['mock_fm_instance']

    # Assert wiring calls were made (using the instances returned by the mocks)
    app_components['mock_task_system_instance'].set_handler.assert_called_once_with(app.passthrough_handler)

    # --- START MODIFICATION: Verify attribute assignments ---
    # Check that the memory_system attribute was assigned to the correct mock instance
    # Accessing the attribute directly on the mock should work after assignment
    assert app.passthrough_handler.memory_system == app_components['mock_memory_system_instance']
    assert app.task_system.memory_system == app_components['mock_memory_system_instance']
    # --- END MODIFICATION ---

    # Assert tool registration calls (at least system tools should be registered)
    app_components['mock_handler_instance'].register_tool.assert_called() # Check if called at least once
    # Example: Check for a specific system tool registration (adjust name/executor check as needed)
    # Find the call where the first arg (spec dict) has name 'system:get_context'
    system_context_call = next((c for c in app_components['mock_handler_instance'].register_tool.call_args_list if c.args[0].get('name') == 'system:get_context'), None)
    assert system_context_call is not None, "system:get_context tool was not registered"
    # Check the executor passed (it will be a lambda, checking existence is usually enough)
    assert callable(system_context_call.args[1])

    # Assert agent initialization call
    app_components['mock_handler_instance'].get_tools_for_agent.assert_called_once()
    # Check the call to initialize_agent on the LLM Manager mock instance
    app_components['mock_llm_manager_instance'].initialize_agent.assert_called_once_with(tools=mock_executors)

# ... other tests (test_index_repository_success, test_handle_query_success, etc.) ...
# Ensure these tests use app_components fixture and assert calls on the mock instances within it.

def test_index_repository_success(app_components, tmp_path):
    """Test successful repository indexing."""
    # Arrange
    # Create a dummy .git directory to simulate a repo root
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    repo_path = str(tmp_path)

    # Mock the GitRepositoryIndexer instantiation and its method
    # Patch *within* the main module where Application uses it
    # Use the mocks provided by the fixture
    MockIndexerClass = app_components["MockGitRepositoryIndexer"]
    mock_indexer_instance = app_components["mock_indexer_instance"]
    mock_indexer_instance.index_repository.return_value = {"file1.py": "metadata1"}

    app = Application() # Uses mocked dependencies from app_components

    # Act
    options = {"include_patterns": ["*.py"]}
    success = app.index_repository(repo_path, options=options)

    # Assert
    assert success is True
    MockIndexerClass.assert_called_once_with(repo_path=repo_path)
    # Check configuration calls on the indexer instance
    assert mock_indexer_instance.include_patterns == ["*.py"] # Check attribute directly or use setter mock
    mock_indexer_instance.index_repository.assert_called_once_with(memory_system=app.memory_system)
    assert repo_path in app.indexed_repositories

# ... (other tests like test_index_repository_invalid_path, etc.)

def test_handle_query_success(app_components):
    """Test successful query handling delegation."""
    # Arrange
    app = Application() # Uses mocked dependencies
    mock_handler = app_components['mock_handler_instance']
    expected_result = TaskResult(status="COMPLETE", content="Query response")
    # Configure the mock handler's handle_query method
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
    app = Application() # Uses mocked dependencies
    mock_handler = app_components['mock_handler_instance']
    # Configure the mock handler's handle_query to raise an exception
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
            # optional_history_str potentially needed here if dispatcher uses it
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
        mock_dispatch.assert_called_once() # Check it was called
        assert result.get("status") == "FAILED"
        assert "Unexpected error during task command execution" in result.get("content", "")
        assert "Dispatcher failed" in result.get("content", "")
        assert result.get("notes", {}).get("error", {}).get("reason") == "unexpected_error"

# Add test for conditional Aider initialization and tool registration
# Need to mock AIDER_AVAILABLE
@patch('src.main.AIDER_AVAILABLE', True) # Simulate Aider being available
def test_application_init_with_aider(app_components): # Removed mock_aider_available_flag
    """Verify AiderBridge is initialized and tools registered when available."""
    # Arrange
    # Mock the AiderExecutors methods if needed for registration check
    mock_aider_exec_auto = app_components['mock_aider_auto_func']
    mock_aider_exec_interactive = app_components['mock_aider_inter_func']
    # No need to re-patch, fixture already did

    # Act
    app = Application(config={"aider_config": {"mcp_stdio_command": "aider_server"}})

    # Assert AiderBridge was instantiated
    app_components['MockAiderBridge'].assert_called_once_with(
        memory_system=app.memory_system,
        file_access_manager=app.file_access_manager,
        config={"mcp_stdio_command": "aider_server"}
    )
    assert app.aider_bridge == app_components['mock_aider_bridge_instance']

    # Assert Aider tools were registered with the handler using the storage dict
    registered_tools = app_components['registered_tools_storage']
    assert 'aider:automatic' in registered_tools
    assert 'aider:interactive' in registered_tools
    # Check that the executor passed is a callable (the lambda wrapper)
    assert callable(registered_tools['aider:automatic']['executor'])
    assert callable(registered_tools['aider:interactive']['executor'])

@patch('src.main.AIDER_AVAILABLE', False) # Simulate Aider being unavailable
def test_application_init_without_aider(app_components): # Removed mock_aider_unavailable_flag
    """Verify AiderBridge is NOT initialized and tools NOT registered when unavailable."""
     # Act
    app = Application()

    # Assert AiderBridge was NOT instantiated
    app_components['MockAiderBridge'].assert_not_called()
    assert app.aider_bridge is None

    # Assert Aider tools were NOT registered using the storage dict
    registered_tools = app_components['registered_tools_storage']
    assert 'aider:automatic' not in registered_tools
    assert 'aider:interactive' not in registered_tools


# Add test for conditional Anthropic tool registration
@patch('src.main.AIDER_AVAILABLE', False) # Disable Aider for this test
def test_application_init_with_anthropic(app_components):
    """Verify Anthropic tools are registered for Anthropic provider."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "anthropic:claude-3-5-sonnet-latest"
    # Mocks for functions and specs are already configured in the fixture

    # Act
    app = Application()

    # Assert Anthropic tools were registered using the storage dict
    registered_tools = app_components['registered_tools_storage']
    assert 'anthropic:view' in registered_tools
    assert 'anthropic:create' in registered_tools
    assert 'anthropic:str_replace' in registered_tools
    assert 'anthropic:insert' in registered_tools

    # Check specs and executors
    assert registered_tools['anthropic:view']['spec'] == app_components['MockAnthropicTools'].ANTHROPIC_VIEW_SPEC
    assert callable(registered_tools['anthropic:view']['executor'])
    assert registered_tools['anthropic:create']['spec'] == app_components['MockAnthropicTools'].ANTHROPIC_CREATE_SPEC
    assert callable(registered_tools['anthropic:create']['executor'])
    # ... check others ...

@patch('src.main.AIDER_AVAILABLE', False) # Disable Aider
def test_application_init_without_anthropic(app_components):
    """Verify Anthropic tools are NOT registered for non-Anthropic provider."""
     # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "openai:gpt-4o"

    # Act
    app = Application()

    # Assert Anthropic tools were NOT registered using the storage dict
    registered_tools = app_components['registered_tools_storage']
    assert 'anthropic:view' not in registered_tools
    assert 'anthropic:create' not in registered_tools
    assert 'anthropic:str_replace' not in registered_tools
    assert 'anthropic:insert' not in registered_tools
