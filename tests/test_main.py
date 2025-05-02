import pytest
from unittest.mock import patch, MagicMock, call, ANY # Import ANY
import os
import sys
from typing import Callable, List, Dict, Any # Add necessary types

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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
# Import the module containing the functions to patch
from src.tools import anthropic_tools

# Mock Aider components as well
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


# Define dummy tool specs used in Application init
# Aider specs removed as Aider integration is deferred
DUMMY_SYS_GET_CONTEXT_SPEC = {"name": "system:get_context", "description": "Sys Get Context", "input_schema": {}}
DUMMY_SYS_READ_FILES_SPEC = {"name": "system:read_files", "description": "Sys Read Files", "input_schema": {}}


# --- Fixture (Refined for clarity and autospec) ---
@pytest.fixture
def app_components(tmp_path):
    """Provides mocked components for Application testing using autospec."""
    # Use a dictionary to store registered tools for assertion
    registered_tools_storage = {}
    tool_executors_storage = {} # Store executors separately

    # Mock register_tool to store spec and executor
    def mock_register_tool(self, tool_spec, executor_func):
        tool_name = tool_spec.get("name")
        if tool_name:
            registered_tools_storage[tool_name] = {"spec": tool_spec, "executor": executor_func}
            tool_executors_storage[tool_name] = executor_func # Store executor
            return True
        return False

    # Patch necessary classes AND the anthropic tool functions
    with patch('src.main.FileAccessManager', autospec=True) as MockFM, \
         patch('src.main.MemorySystem', autospec=True) as MockMemory, \
         patch('src.main.TaskSystem', autospec=True) as MockTask, \
         patch('src.main.PassthroughHandler', autospec=True) as MockHandler, \
         patch('src.main.GitRepositoryIndexer', autospec=True) as MockIndexer, \
         patch('src.main.SystemExecutorFunctions', autospec=True) as MockSysExecCls, \
         patch('src.handler.llm_interaction_manager.Agent', autospec=True) as MockPydanticAgent, \
         patch('src.main.AiderBridge', autospec=True) as MockAiderBridge, \
         patch('src.main.AiderExecutors', autospec=True) as MockAiderExec, \
         patch('src.main.anthropic_tools.view', autospec=True) as mock_anthropic_view_func, \
         patch('src.main.anthropic_tools.create', autospec=True) as mock_anthropic_create_func, \
         patch('src.main.anthropic_tools.str_replace', autospec=True) as mock_anthropic_replace_func, \
         patch('src.main.anthropic_tools.insert', autospec=True) as mock_anthropic_insert_func: # Patch anthropic functions

        # Configure mocks for instances returned by constructors
        mock_handler_instance = MockHandler.return_value
        mock_task_system_instance = MockTask.return_value
        mock_memory_system_instance = MockMemory.return_value
        mock_fm_instance = MockFM.return_value
        mock_aider_bridge_instance = MockAiderBridge.return_value

        # Mock methods called during init
        mock_fm_instance.base_path = str(tmp_path / "mock_base") # Set base_path on instance
        mock_handler_instance.get_provider_identifier.return_value = "mock:provider" # Default
        # Attach the mocked register_tool to the handler instance mock
        mock_handler_instance.register_tool = MagicMock(side_effect=lambda spec, exec_func: mock_register_tool(mock_handler_instance, spec, exec_func))
        # Mock get_tools_for_agent to return based on current tool_executors_storage
        mock_handler_instance.get_tools_for_agent.side_effect = lambda: list(tool_executors_storage.values())
        mock_handler_instance.set_active_tool_definitions = MagicMock(return_value=True) # Ensure method exists
        mock_handler_instance.llm_manager = MagicMock(spec=LLMInteractionManager)
        mock_handler_instance.llm_manager.initialize_agent = MagicMock()
        mock_handler_instance.file_manager = mock_fm_instance # Ensure file_manager is set

        # Mock TaskSystem methods if needed
        mock_task_system_instance.set_handler = MagicMock() # Ensure set_handler exists

        # Mock static methods on the SystemExecutorFunctions CLASS mock
        mock_exec_get_context = MagicMock(name="mock_execute_get_context")
        mock_exec_read_files = MagicMock(name="mock_execute_read_files")
        MockSysExecCls.execute_get_context = mock_exec_get_context
        MockSysExecCls.execute_read_files = mock_exec_read_files

        # Mock static methods on the AiderExecutors CLASS mock
        mock_aider_auto_func = MagicMock(spec=Callable, name="mock_execute_aider_automatic")
        mock_aider_inter_func = MagicMock(spec=Callable, name="mock_execute_aider_interactive")
        MockAiderExec.execute_aider_automatic = mock_aider_auto_func
        MockAiderExec.execute_aider_interactive = mock_aider_inter_func

        # Configure Anthropic tools mock module specs (used by Application init)
        MockAnthropicToolsModule.ANTHROPIC_VIEW_SPEC = {"name": "anthropic:view", "description":"View", "input_schema":{}}
        MockAnthropicToolsModule.ANTHROPIC_CREATE_SPEC = {"name": "anthropic:create", "description":"Create", "input_schema":{}}
        MockAnthropicToolsModule.ANTHROPIC_STR_REPLACE_SPEC = {"name": "anthropic:str_replace", "description":"Replace", "input_schema":{}}
        MockAnthropicToolsModule.ANTHROPIC_INSERT_SPEC = {"name": "anthropic:insert", "description":"Insert", "input_schema":{}}

        # Yield dictionary including the function mocks
        yield {
            "MockFM": MockFM,
            "MockMemory": MockMemory,
            "MockTask": MockTask,
            "MockHandler": MockHandler,
            "MockIndexer": MockIndexer,
            "MockSysExecCls": MockSysExecCls,
            "MockAnthropicToolsModule": MockAnthropicToolsModule, # Yield the module mock
            "MockPydanticAgent": MockPydanticAgent,
            "MockAiderBridge": MockAiderBridge,
            "MockAiderExec": MockAiderExec,
            # Instances returned by the mock constructors
            "mock_fm_instance": mock_fm_instance,
            "mock_memory_instance": mock_memory_system_instance,
            "mock_task_instance": mock_task_system_instance,
            "mock_handler_instance": mock_handler_instance,
            "mock_aider_bridge_instance": mock_aider_bridge_instance,
            # Specific tool function mocks (static methods on class mocks)
            "mock_exec_get_context": mock_exec_get_context,
            "mock_exec_read_files": mock_exec_read_files,
            "mock_aider_auto_func": mock_aider_auto_func,
            "mock_aider_inter_func": mock_aider_inter_func,
            # Add the function mocks needed for assertions
            "mock_anthropic_view_func": mock_anthropic_view_func,
            "mock_anthropic_create_func": mock_anthropic_create_func,
            "mock_anthropic_replace_func": mock_anthropic_replace_func,
            "mock_anthropic_insert_func": mock_anthropic_insert_func,
            # Add the storage dictionary
            "registered_tools_storage": registered_tools_storage,
            "tool_executors_storage": tool_executors_storage, # Yield executor storage
        }

# --- Test Cases ---

def test_application_init_wiring(app_components):
    """Verify components are instantiated and wired correctly during __init__."""
    # Arrange: Set a default provider ID
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"

    # Act: Instantiate Application
    app = Application(config={})

    # Assert component instances were created by the Mocks
    # Check that the instance held by Application is the one returned by the Mock constructor
    assert app.memory_system == app_components['MockMemory'].return_value
    assert app.task_system == app_components['MockTask'].return_value
    assert app.passthrough_handler == app_components['MockHandler'].return_value
    assert app.file_access_manager == app_components['MockFM'].return_value

    # Assert wiring calls were made (using the instances returned by the mocks)
    # Example: Check if set_handler was called on the TaskSystem instance
    # Note: Use the mock instance from the fixture dictionary for assertions
    # Need to ensure the mock instances are correctly configured in the fixture
    app_components['mock_task_instance'].set_handler.assert_called_once_with(app.passthrough_handler)
    # Add similar assertions for other wiring calls if needed, accessing the instances
    # from app_components dictionary. For example, check memory_system assignment:
    # assert app_components['mock_task_instance'].memory_system == app.memory_system # If attribute is directly set
    # assert app_components['mock_handler_instance'].memory_system == app.memory_system # If attribute is directly set

    # Assert tool registration calls
    # Check that register_tool was called on the handler instance
    # Count specific calls if needed (e.g., for system tools)
    assert app_components['mock_handler_instance'].register_tool.call_count > 0 # Check it was called at least once

    # Assert Agent initialization was triggered
    app_components['mock_handler_instance'].get_tools_for_agent.assert_called_once()
    app_components['mock_handler_instance'].llm_manager.initialize_agent.assert_called_once()
    # Check the tools passed to initialize_agent if necessary
    # initialize_agent_call_args = app_components['mock_handler_instance'].llm_manager.initialize_agent.call_args
    # assert initialize_agent_call_args[1]['tools'] == [] # Assuming empty tools from get_tools_for_agent mock


def test_application_register_system_tools(app_components):
    """Verify system tools are registered with the handler during init."""
    # Arrange: Set a default provider ID
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"

    # Act: Instantiate Application
    # Patch AIDER_AVAILABLE to False for this test
    with patch(AIDER_AVAILABLE_IMPORT_PATH, False):
        app = Application(config={})

    # Assert: Check the registered_tools dictionary captured by the mock side effect
    registered_tools = app_components["registered_tools_storage"] # Check the storage directly
    assert "system:get_context" in registered_tools
    assert "system:read_files" in registered_tools

    # Check the spec and executor type
    get_context_data = registered_tools["system:get_context"]
    assert isinstance(get_context_data['spec'], dict)
    assert callable(get_context_data['executor'])

    read_files_data = registered_tools["system:read_files"]
    assert isinstance(read_files_data['spec'], dict)
    assert callable(read_files_data['executor'])

    # Test the lambda wrappers by executing them
    get_context_lambda = get_context_data['executor']
    get_context_params = {"query": "test"}
    get_context_lambda(get_context_params) # Execute lambda
    # Assert the underlying SystemExecutorFunctions method was called correctly
    # Access the mock function via the fixture dictionary
    app_components["mock_exec_get_context"].assert_called_once_with(get_context_params, app.memory_system)

    read_files_lambda = read_files_data['executor']
    read_files_params = {"file_paths": ["a.txt"]}
    read_files_lambda(read_files_params) # Execute lambda
    app_components["mock_exec_read_files"].assert_called_once_with(read_files_params, app.passthrough_handler.file_manager)


@patch('src.main.os.path.isdir')
@patch('src.main.os.path.abspath')
def test_application_index_repository_success(mock_abspath, mock_isdir, app_components, tmp_path):
    """Verify successful repository indexing delegates correctly."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"
    app = Application(config={}) # Instantiate app

    repo_path_str = str(tmp_path / "repo") # Use tmp_path for realistic path
    git_dir_path = os.path.join(repo_path_str, ".git")
    # Configure abspath mock to return the final path when called with repo_path_str
    # Allow other calls (like the one from init)
    mock_abspath.side_effect = lambda p: repo_path_str if p == repo_path_str else os.path.normpath(p)
    mock_isdir.side_effect = lambda p: p in [repo_path_str, git_dir_path]
    mock_indexer_instance = app_components["MockIndexer"].return_value
    mock_indexer_instance.index_repository.return_value = {f"{repo_path_str}/file.py": "metadata"}

    # Act
    result = app.index_repository(repo_path_str)

    # Assert
    assert result is True
    # Fix: Assert that abspath was called with the repo_path_str at least once
    mock_abspath.assert_any_call(repo_path_str)
    # Fix: Assert isdir was called for the repo path and the .git dir
    mock_isdir.assert_any_call(repo_path_str)
    mock_isdir.assert_any_call(git_dir_path)
    # Assert indexer was instantiated and called
    app_components["MockIndexer"].assert_called_once_with(repo_path=repo_path_str)
    mock_indexer_instance.index_repository.assert_called_once_with(memory_system=app.memory_system)
    assert repo_path_str in app.indexed_repositories

@patch('src.main.os.path.isdir')
@patch('src.main.os.path.abspath')
def test_application_index_repository_invalid_path(mock_abspath, mock_isdir, app_components):
    """Verify indexing fails if path is invalid (not a directory)."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"
    app = Application(config={})
    repo_path = "/invalid/path"
    # Configure abspath mock
    mock_abspath.side_effect = lambda p: repo_path if p == repo_path else os.path.normpath(p)
    mock_isdir.return_value = False # Simulate path is not a directory

    # Act
    result = app.index_repository(repo_path)

    # Assert
    assert result is False
    # Fix: Assert abspath was called with the repo_path
    mock_abspath.assert_any_call(repo_path)
    # Fix: Assert isdir was called for the repo path
    mock_isdir.assert_any_call(repo_path)
    # Ensure indexer was NOT called
    app_components["MockIndexer"].assert_not_called()
    assert repo_path not in app.indexed_repositories


@patch('src.main.os.path.isdir')
@patch('src.main.os.path.abspath')
def test_application_index_repository_not_git(mock_abspath, mock_isdir, app_components, tmp_path):
    """Verify indexing fails if path is not a git repo (no .git dir)."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"
    app = Application(config={})
    repo_path_str = str(tmp_path / "not_a_repo")
    git_dir_path = os.path.join(repo_path_str, ".git")
    # Configure abspath mock
    mock_abspath.side_effect = lambda p: repo_path_str if p == repo_path_str else os.path.normpath(p)
    # Simulate only the main path is a dir, but .git is not
    mock_isdir.side_effect = lambda p: p == repo_path_str

    # Act
    result = app.index_repository(repo_path_str)

    # Assert
    assert result is False
    # Fix: Assert abspath was called with the repo_path
    mock_abspath.assert_any_call(repo_path_str)
    # Fix: Assert isdir was called for the repo path AND the .git dir check
    mock_isdir.assert_any_call(repo_path_str)
    mock_isdir.assert_any_call(git_dir_path)
    # Ensure indexer was NOT called
    app_components["MockIndexer"].assert_not_called()
    assert repo_path_str not in app.indexed_repositories


@patch('src.main.os.path.isdir')
@patch('src.main.os.path.abspath')
def test_application_index_repository_indexer_error(mock_abspath, mock_isdir, app_components, tmp_path):
    """Verify indexing fails if indexer raises an exception."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"
    app = Application(config={})
    repo_path_str = str(tmp_path / "repo_fail")
    git_dir_path = os.path.join(repo_path_str, ".git")
    mock_abspath.return_value = repo_path_str
    mock_isdir.side_effect = lambda p: p in [repo_path_str, git_dir_path]
    mock_indexer_instance = app_components["MockIndexer"].return_value
    mock_indexer_instance.index_repository.side_effect = Exception("Indexing failed!")

    # Act
    result = app.index_repository(repo_path_str)

    # Assert
    assert result is False
    app_components["MockIndexer"].assert_called_once_with(repo_path=repo_path_str)
    mock_indexer_instance.index_repository.assert_called_once()
    assert repo_path_str not in app.indexed_repositories


def test_application_handle_query_delegation(app_components):
    """Verify handle_query delegates to the handler."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"
    app = Application(config={})
    query = "test query"
    mock_response_obj = TaskResult(status="COMPLETE", content="Handler Response", notes={})
    app.passthrough_handler.handle_query.return_value = mock_response_obj

    # Act
    result_dict = app.handle_query(query)

    # Assert
    app.passthrough_handler.handle_query.assert_called_once_with(query)
    assert result_dict == mock_response_obj.model_dump(exclude_none=True)

def test_application_handle_query_exception(app_components):
    """Verify handle_query handles exceptions from the handler."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"
    app = Application(config={})
    query = "query causing error"
    app.passthrough_handler.handle_query.side_effect = Exception("Handler crashed")

    # Act
    result_dict = app.handle_query(query)

    # Assert
    assert result_dict['status'] == "FAILED"
    assert "Handler crashed" in result_dict['content']
    assert result_dict['notes']['error']['reason'] == "unexpected_error"

def test_application_reset_conversation_delegation(app_components):
    """Verify reset_conversation delegates to the handler."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"
    app = Application(config={})

    # Act
    app.reset_conversation()

    # Assert
    app.passthrough_handler.reset_conversation.assert_called_once()

# Patch the dispatcher function where it's imported in main.py
@patch('src.main.dispatcher.execute_programmatic_task')
def test_application_handle_task_command_delegation(mock_dispatcher_func, app_components):
    """Verify handle_task_command delegates to the dispatcher function."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"
    app = Application(config={})
    identifier = "task:id"
    params = {"p": 1}
    flags = {"f": True}
    mock_dispatch_result = TaskResult(status="COMPLETE", content="Dispatch Result", notes={}).model_dump(exclude_none=True)
    mock_dispatcher_func.return_value = mock_dispatch_result

    # Act
    result = app.handle_task_command(identifier, params, flags)

    # Assert
    mock_dispatcher_func.assert_called_once_with(
        identifier=identifier,
        params=params,
        flags=flags,
        handler_instance=app.passthrough_handler,
        task_system_instance=app.task_system,
        memory_system=app.memory_system
    )
    assert result == mock_dispatch_result

@patch('src.main.dispatcher.execute_programmatic_task')
def test_application_handle_task_command_exception(mock_dispatcher_func, app_components):
    """Verify handle_task_command handles exceptions from the dispatcher."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"
    app = Application(config={})
    identifier = "task:id"
    params = {"p": 1}
    flags = {"f": True}
    mock_dispatcher_func.side_effect = Exception("Dispatcher error")

    # Act
    result = app.handle_task_command(identifier, params, flags)

    # Assert
    assert result['status'] == "FAILED"
    assert "Dispatcher error" in result['content']
    assert result['notes']['error']['reason'] == "unexpected_error"

# --- Test for Deferred Aider Initialization ---

def test_application_initialize_aider_deferred(app_components):
    """Verify initialize_aider is a placeholder and does not register tools."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"
    # Patch AIDER_AVAILABLE to False where Application looks it up
    with patch(AIDER_AVAILABLE_IMPORT_PATH, False):
        app = Application(config={})
    # Reset mock calls made during init
    app.passthrough_handler.register_tool.reset_mock()
    register_call_count_before = app.passthrough_handler.register_tool.call_count

    # Act
    app.initialize_aider() # This should now do nothing if AIDER_AVAILABLE is False

    # Assert
    assert app.aider_bridge is None # Check bridge instance is None
    register_call_count_after = app.passthrough_handler.register_tool.call_count
    assert register_call_count_after == register_call_count_before


# --- Test case for Application init failure ---
def test_application_init_failure():
    """Verify Application __init__ handles component instantiation failure."""
    with patch('src.main.MemorySystem', side_effect=Exception("Memory init failed")):
        with pytest.raises(Exception, match="Memory init failed"):
            Application() # Instantiation should fail and raise

# --- Test case for Tool Format ---
def test_application_init_passes_correct_tool_format_to_agent(app_components):
    """
    Verify the correct tool format (list[Callable]) is passed to LLMInteractionManager.initialize_agent.
    """
    # Arrange: Set provider ID
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"
    # The fixture now correctly sets up the mocks and handler state after Application init

    # Act: Instantiate Application to trigger the sequence
    # Patch AIDER_AVAILABLE to False for this test
    with patch(AIDER_AVAILABLE_IMPORT_PATH, False):
        app = Application()

    # Assert: Check the arguments passed to the *mocked* initialize_agent
    # This assertion happens implicitly during the fixture setup when Application is created
    app.passthrough_handler.llm_manager.initialize_agent.assert_called_once()
    call_args, call_kwargs = app.passthrough_handler.llm_manager.initialize_agent.call_args

    assert not call_args # Should have no positional args
    assert 'tools' in call_kwargs
    passed_tools = call_kwargs['tools']
    assert isinstance(passed_tools, list)
    # Fix: Expect 2 system tools based on _register_system_tools implementation
    assert len(passed_tools) == 2
    # Check that elements are callable (lambdas)
    assert all(callable(t) for t in passed_tools)


# --- NEW Integration Tests for Conditional Tool Registration ---

def test_application_init_registers_system_tools_only_for_non_anthropic_provider(app_components):
    """
    Verify only system tools are registered and passed to agent init
    when the provider is not Anthropic.
    """
    # Arrange: Set provider ID on the handler mock *before* Application init
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "openai:gpt-4"

    # Act: Instantiate Application - this triggers the __init__ logic
    # Patch AIDER_AVAILABLE to False for this test
    with patch(AIDER_AVAILABLE_IMPORT_PATH, False):
        app = Application(config={})

    # Assert Handler Tool Registration
    # Check the registered_tools dictionary captured by the mock side effect
    registered_tools = app_components["registered_tools_storage"] # Check the storage directly
    registered_tool_names = set(registered_tools.keys())

    # Check system tools WERE registered (assert based on names)
    assert "system:get_context" in registered_tool_names
    assert "system:read_files" in registered_tool_names
    # Check Anthropic tools WERE NOT registered
    assert not any(name.startswith("anthropic:") for name in registered_tool_names)
    # Check Aider tools WERE NOT registered
    assert not any(name.startswith("aider:") for name in registered_tool_names)


    # Assert Agent Initialization Call
    # Check the call made to the *mocked* initialize_agent
    app.passthrough_handler.llm_manager.initialize_agent.assert_called_once()
    args, kwargs = app.passthrough_handler.llm_manager.initialize_agent.call_args
    assert 'tools' in kwargs
    initialized_tools_list = kwargs['tools'] # This list contains the wrapper lambdas

    # Verify the list contains ONLY the system tool executor wrappers
    assert len(initialized_tools_list) == 2 # Expecting 2 system tools
    # Check that the executors are callables (lambdas)
    assert all(callable(t) for t in initialized_tools_list)


def test_application_init_registers_anthropic_and_system_tools_for_anthropic_provider(app_components):
    """
    Verify system AND Anthropic tools are registered and passed to agent init
    when the provider IS Anthropic.
    """
    # Arrange: Set provider ID on the handler mock *before* Application init
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "anthropic:claude-3-5-sonnet-latest"

    # Mock the anthropic tools module used by Application
    # Use the mock provided by the fixture
    MockAnthropicToolsModule = app_components["MockAnthropicToolsModule"]

    # Act: Instantiate Application
    with patch(AIDER_AVAILABLE_IMPORT_PATH, False): # Ensure Aider is disabled for this test
        app = Application(config={})

    # Assert Handler Tool Registration
    registered_tools = app_components["registered_tools_storage"] # Check storage
    registered_tool_names = set(registered_tools.keys())

    # Check system tools WERE registered
    assert "system:get_context" in registered_tool_names
    assert "system:read_files" in registered_tool_names
    # Check Anthropic tools WERE registered
    assert "anthropic:view" in registered_tool_names
    assert "anthropic:create" in registered_tool_names
    assert "anthropic:str_replace" in registered_tool_names
    assert "anthropic:insert" in registered_tool_names
    # Check Aider tools WERE NOT registered
    assert not any(name.startswith("aider:") for name in registered_tool_names)

    # Assert Agent Initialization Call
    # Access the handler instance created by the Application
    handler_instance_in_app = app.passthrough_handler
    handler_instance_in_app.llm_manager.initialize_agent.assert_called_once()
    args, kwargs = handler_instance_in_app.llm_manager.initialize_agent.call_args
    assert 'tools' in kwargs
    initialized_tools_list = kwargs['tools'] # Contains wrapper lambdas

    # Verify the list contains BOTH system and Anthropic tool executor wrappers
    assert len(initialized_tools_list) == 6 # Expecting 2 system + 4 Anthropic tools
    # Check that the executors are callables (lambdas)
    assert all(callable(t) for t in initialized_tools_list)

    # --- Test the Anthropic Lambda Wrappers ---
    # Get one of the registered Anthropic executors (the lambda)
    anthropic_view_executor_lambda = registered_tools["anthropic:view"]["executor"]
    view_params = {"file_path": "view.txt"} # Params the lambda expects

    # Execute the lambda wrapper
    anthropic_view_executor_lambda(view_params)

    # Assert that the underlying *mocked* anthropic_tools.view function was called
    # with the file_manager as the first arg and unpacked params
    # Access the mock function via the fixture dictionary
    app_components["mock_anthropic_view_func"].assert_called_once_with(
        app.passthrough_handler.file_manager, # Check fm was passed
        **view_params # Check params were unpacked
    )

    # Repeat for another tool, e.g., create
    anthropic_create_executor_lambda = registered_tools["anthropic:create"]["executor"]
    create_params = {"file_path": "create.txt", "content": "hello", "overwrite": True}
    anthropic_create_executor_lambda(create_params)
    app_components["mock_anthropic_create_func"].assert_called_once_with(
        app.passthrough_handler.file_manager,
        **create_params
    )

# --- NEW Test for Aider Tool Registration ---

# Fixture specifically for the Aider registration test
@pytest.fixture
def mock_app_dependencies_for_aider(tmp_path):
    """Provides mocked dependencies for Application testing, focusing on Aider."""
    registered_tools_storage = {}
    tool_executors_storage = {} # Store executors separately

    def mock_register_tool(self, tool_spec, executor_func):
        tool_name = tool_spec.get("name")
        if tool_name:
            registered_tools_storage[tool_name] = {"spec": tool_spec, "executor": executor_func}
            tool_executors_storage[tool_name] = executor_func # Store executor
            return True
        return False

    with patch('src.main.FileAccessManager', spec=True) as MockFM, \
         patch('src.main.MemorySystem', spec=True) as MockMemory, \
         patch('src.main.TaskSystem', spec=True) as MockTask, \
         patch('src.main.PassthroughHandler', spec=True) as MockHandler, \
         patch('src.main.GitRepositoryIndexer', spec=True) as MockIndexer, \
         patch('src.main.SystemExecutorFunctions') as MockSysExecCls, \
         patch('src.main.anthropic_tools', spec=True) as MockAnthropicToolsModule, \
         patch('src.handler.llm_interaction_manager.Agent') as MockPydanticAgent, \
         patch('src.main.AiderBridge') as MockAiderBridge, \
         patch('src.main.AiderExecutors', spec=True) as MockAiderExec: # Corrected Patch Target

        mock_fm_instance = MockFM.return_value
        # --- ADD base_path ATTRIBUTE ---
        mock_fm_instance.base_path = str(tmp_path / "mock_base_aider") # Example path
        # --- END ADDITION ---
        mock_memory_instance = MockMemory.return_value
        mock_task_instance = MockTask.return_value
        mock_handler_instance = MockHandler.return_value
        mock_handler_instance.file_manager = mock_fm_instance
        # Attach the mocked register_tool to the handler instance mock
        mock_handler_instance.register_tool = MagicMock(side_effect=lambda spec, exec_func: mock_register_tool(mock_handler_instance, spec, exec_func))
        mock_handler_instance.get_provider_identifier.return_value = "default:fixture_provider"
        mock_handler_instance.set_active_tool_definitions.return_value = True
        mock_llm_manager_instance = MagicMock(spec=LLMInteractionManager)
        mock_llm_manager_instance.initialize_agent = MagicMock()
        mock_handler_instance.llm_manager = mock_llm_manager_instance
        # Mock get_tools_for_agent to return based on current tool_executors_storage
        mock_handler_instance.get_tools_for_agent.side_effect = lambda: list(tool_executors_storage.values())

        # Configure mock system executor static methods
        mock_exec_get_context = MagicMock(name="mock_execute_get_context")
        mock_exec_read_files = MagicMock(name="mock_execute_read_files")
        MockSysExecCls.execute_get_context = mock_exec_get_context
        MockSysExecCls.execute_read_files = mock_exec_read_files

        # Configure Anthropic tools mock module specs (used by Application init)
        MockAnthropicToolsModule.ANTHROPIC_VIEW_SPEC = {"name": "anthropic:view", "description":"View", "input_schema":{}}
        MockAnthropicToolsModule.ANTHROPIC_CREATE_SPEC = {"name": "anthropic:create", "description":"Create", "input_schema":{}}
        MockAnthropicToolsModule.ANTHROPIC_STR_REPLACE_SPEC = {"name": "anthropic:str_replace", "description":"Replace", "input_schema":{}}
        MockAnthropicToolsModule.ANTHROPIC_INSERT_SPEC = {"name": "anthropic:insert", "description":"Insert", "input_schema":{}}

        mock_aider_auto_func = MagicMock(spec=Callable, name="mock_execute_aider_automatic")
        mock_aider_inter_func = MagicMock(spec=Callable, name="mock_execute_aider_interactive")
        MockAiderExec.execute_aider_automatic = mock_aider_auto_func
        MockAiderExec.execute_aider_interactive = mock_aider_inter_func

        yield {
            "MockHandler": MockHandler,
            "mock_handler_instance": mock_handler_instance,
            "MockAiderExec": MockAiderExec,
            "mock_aider_auto_func": mock_aider_auto_func,
            "mock_aider_inter_func": mock_aider_inter_func,
            "registered_tools_storage": registered_tools_storage, # Expose storage for assertion
            "tool_executors_storage": tool_executors_storage, # Expose executor storage
        }

def test_application_init_registers_aider_tools(mock_app_dependencies_for_aider):
    """Verify Application.__init__ registers aider tools with the handler when AIDER_AVAILABLE is True."""
    # Arrange
    mock_handler_instance = mock_app_dependencies_for_aider["mock_handler_instance"]
    # Get the mock class from the fixture, not the instance
    mock_aider_exec_class = mock_app_dependencies_for_aider["MockAiderExec"]
    expected_auto_executor = mock_app_dependencies_for_aider["mock_aider_auto_func"]
    expected_inter_executor = mock_app_dependencies_for_aider["mock_aider_inter_func"]
    registered_tools_storage = mock_app_dependencies_for_aider["registered_tools_storage"]

    # Act
    # Initialize Application. Patch AIDER_AVAILABLE where Application looks it up.
    with patch(AIDER_AVAILABLE_IMPORT_PATH, True):
         app = Application()

    # Assert
    # Check the storage populated by the mock register_tool side effect
    assert "aider:automatic" in registered_tools_storage
    assert "aider:interactive" in registered_tools_storage

    # Verify the executor functions stored are the mocked ones from the class
    # The lambda wrapper in initialize_aider calls the static methods on the class
    # So we check if the stored executor, when called, calls the correct mock static method.
    aider_auto_lambda = registered_tools_storage["aider:automatic"]["executor"]
    aider_inter_lambda = registered_tools_storage["aider:interactive"]["executor"]

    # Test the lambda wrapper for automatic
    test_params_auto = {"prompt": "auto test"}
    aider_auto_lambda(test_params_auto)
    expected_auto_executor.assert_called_once_with(test_params_auto, app.aider_bridge)

    # Test the lambda wrapper for interactive
    test_params_inter = {"query": "inter test"}
    aider_inter_lambda(test_params_inter)
    expected_inter_executor.assert_called_once_with(test_params_inter, app.aider_bridge)


    # Verify the specs passed (basic check)
    assert isinstance(registered_tools_storage["aider:automatic"]["spec"], dict)
    assert registered_tools_storage["aider:automatic"]["spec"].get('name') == 'aider:automatic'
    assert isinstance(registered_tools_storage["aider:interactive"]["spec"], dict)
    assert registered_tools_storage["aider:interactive"]["spec"].get('name') == 'aider:interactive'

    # Check agent initialization includes these tools
    app.passthrough_handler.llm_manager.initialize_agent.assert_called_once()
    args, kwargs = app.passthrough_handler.llm_manager.initialize_agent.call_args
    assert 'tools' in kwargs
    initialized_tools_list = kwargs['tools']
    # Expect 2 system tools + 2 aider tools = 4 total
    assert len(initialized_tools_list) == 4
    # Check that the aider executor lambdas are present in the list passed to the agent
    assert aider_auto_lambda in initialized_tools_list
    assert aider_inter_lambda in initialized_tools_list
