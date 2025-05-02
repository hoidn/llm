import pytest
from unittest.mock import patch, MagicMock, call, ANY # Import ANY
import os
import sys
from typing import Callable # Add Callable to imports

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
from src.executors import aider_executors as aider_executors_module # Import aider executors
from src.tools import anthropic_tools as anthropic_tools_module
# Define the correct path where Application looks up AIDER_AVAILABLE
AIDER_AVAILABLE_IMPORT_PATH = 'src.main.AIDER_AVAILABLE'


# Define dummy tool specs used in Application init
# Aider specs removed as Aider integration is deferred
DUMMY_SYS_GET_CONTEXT_SPEC = {"name": "system:get_context", "description": "Sys Get Context", "input_schema": {}}
DUMMY_SYS_READ_FILES_SPEC = {"name": "system:read_files", "description": "Sys Read Files", "input_schema": {}}


# --- Fixture (Ensure this matches the one generated previously or adapt) ---
@pytest.fixture
def app_components(tmp_path):
    """Provides mocked components for Application testing."""
    # Patch constructors/functions where they are looked up (in src.main)
    with patch('src.main.FileAccessManager', spec=True) as MockFM, \
         patch('src.main.MemorySystem', spec=True) as MockMemory, \
         patch('src.main.TaskSystem', spec=True) as MockTask, \
         patch('src.main.PassthroughHandler', spec=True) as MockHandler, \
         patch('src.main.GitRepositoryIndexer', spec=True) as MockIndexer, \
         patch('src.main.SystemExecutorFunctions') as MockSysExecCls, \
         patch('src.main.anthropic_tools', MagicMock(spec=anthropic_tools_module)) as MockAnthropicTools, \
         patch('src.handler.llm_interaction_manager.Agent') as MockPydanticAgent, \
         patch('src.main.AiderBridge') as MockAiderBridge, \
         patch('src.main.AiderExecutors', spec=True) as MockAiderExec: # Corrected Patch Target (using alias from src/main.py)

        # Configure mocks BEFORE Application instantiation
        mock_fm_instance = MockFM.return_value
        # --- ADD base_path ATTRIBUTE ---
        mock_fm_instance.base_path = str(tmp_path / "mock_base") # Example path
        # --- END ADDITION ---
        mock_memory_instance = MockMemory.return_value
        mock_task_instance = MockTask.return_value
        mock_handler_instance = MockHandler.return_value
        mock_handler_instance.file_manager = mock_fm_instance
        mock_handler_instance.register_tool.return_value = True
        mock_handler_instance.get_provider_identifier.return_value = "default:fixture_provider" # Default for fixture
        mock_handler_instance.set_active_tool_definitions = MagicMock(return_value=True) # Ensure method exists
        mock_llm_manager_instance = MagicMock(spec=LLMInteractionManager)
        mock_llm_manager_instance.initialize_agent = MagicMock() # Mock the init agent call
        mock_handler_instance.llm_manager = mock_llm_manager_instance
        # Store registered tools and executors on the mock handler instance
        # These will be populated by the side_effect below
        mock_handler_instance.tool_executors = {}
        mock_handler_instance.registered_tools = {}

        # --- CONFIGURE MOCKED STATIC METHODS ---
        # Create mock functions for the static methods
        mock_exec_get_context = MagicMock(name="mock_execute_get_context")
        mock_exec_read_files = MagicMock(name="mock_execute_read_files")
        # Attach them to the *mock class*
        MockSysExecCls.execute_get_context = mock_exec_get_context
        MockSysExecCls.execute_read_files = mock_exec_read_files
        # --- END CONFIGURATION ---

        # Simulate register_tool by adding to the mock dictionaries
        registered_tools_storage = {}
        tool_executors_storage = {}
        def mock_register_tool_impl(spec, executor):
            tool_name = spec.get('name')
            if tool_name:
                registered_tools_storage[tool_name] = {'spec': spec, 'executor': executor}
                tool_executors_storage[tool_name] = executor
                # print(f"DEBUG: Mock register_tool called for {tool_name}") # Debug print
                return True
            return False
        mock_handler_instance.register_tool.side_effect = mock_register_tool_impl
        # Allow access to the storage for assertion
        mock_handler_instance.registered_tools = registered_tools_storage
        mock_handler_instance.tool_executors = tool_executors_storage


        # Mock get_tools_for_agent to return based on current tool_executors
        mock_handler_instance.get_tools_for_agent.side_effect = lambda: list(tool_executors_storage.values())


        # Configure the Anthropic tools mock module with dummy functions/specs
        mock_anthropic_view_func = MagicMock(name="anthropic_view_func")
        mock_anthropic_create_func = MagicMock(name="anthropic_create_func")
        mock_anthropic_replace_func = MagicMock(name="anthropic_str_replace_func")
        mock_anthropic_insert_func = MagicMock(name="anthropic_insert_func")
        MockAnthropicTools.view = mock_anthropic_view_func
        MockAnthropicTools.create = mock_anthropic_create_func
        MockAnthropicTools.str_replace = mock_anthropic_replace_func
        MockAnthropicTools.insert = mock_anthropic_insert_func
        MockAnthropicTools.ANTHROPIC_VIEW_SPEC = {"name": "anthropic:view", "description":"View", "input_schema":{}}
        MockAnthropicTools.ANTHROPIC_CREATE_SPEC = {"name": "anthropic:create", "description":"Create", "input_schema":{}}
        MockAnthropicTools.ANTHROPIC_STR_REPLACE_SPEC = {"name": "anthropic:str_replace", "description":"Replace", "input_schema":{}}
        MockAnthropicTools.ANTHROPIC_INSERT_SPEC = {"name": "anthropic:insert", "description":"Insert", "input_schema":{}}

        # Configure Aider executor mocks (needed by Application.initialize_aider)
        # Make them identifiable for assertion
        mock_aider_auto_func = MagicMock(spec=Callable, name="mock_execute_aider_automatic")
        mock_aider_inter_func = MagicMock(spec=Callable, name="mock_execute_aider_interactive")
        MockAiderExec.execute_aider_automatic = mock_aider_auto_func
        MockAiderExec.execute_aider_interactive = mock_aider_inter_func

        # Yield a dictionary containing the key mocks needed for tests
        yield {
            "MockFM": MockFM,
            "MockMemory": MockMemory,
            "MockTask": MockTask,
            "MockHandler": MockHandler,
            "MockIndexer": MockIndexer,
            "MockSysExecCls": MockSysExecCls, # Yield the mock class
            "MockAnthropicTools": MockAnthropicTools,
            "MockPydanticAgent": MockPydanticAgent,
            "MockAiderBridge": MockAiderBridge, # Include AiderBridge mock
            "MockAiderExec": MockAiderExec, # Include AiderExec mock
            # Instances that might be useful
            "mock_handler_instance": mock_handler_instance,
            "mock_llm_manager_instance": mock_llm_manager_instance,
            # Specific tool function mocks
            "mock_exec_get_context": mock_exec_get_context, # Yield mock methods
            "mock_exec_read_files": mock_exec_read_files,
            "mock_anthropic_view_func": mock_anthropic_view_func,
            "mock_anthropic_create_func": mock_anthropic_create_func,
            "mock_anthropic_replace_func": mock_anthropic_replace_func,
            "mock_anthropic_insert_func": mock_anthropic_insert_func,
            "mock_aider_auto_func": mock_aider_auto_func, # Include Aider func mocks
            "mock_aider_inter_func": mock_aider_inter_func,
            "registered_tools_storage": registered_tools_storage, # Yield storage
        }

# --- Test Cases ---

def test_application_init_wiring(app_components):
    """Verify components are instantiated and wired correctly during __init__."""
    # Arrange: Set a default provider ID
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "test:provider"

    # Act: Instantiate Application
    app = Application(config={"handler_config": {"some_key": "val"}})

    # Assert component instances
    assert isinstance(app.memory_system, MagicMock)
    assert isinstance(app.task_system, MagicMock)
    assert isinstance(app.passthrough_handler, MagicMock)
    assert isinstance(app.file_access_manager, MagicMock)

    # Assert instantiation calls (using the mocks from the fixture context)
    app_components["MockFM"].assert_called_once()
    app_components["MockTask"].assert_called_once() # No args expected
    app_components["MockHandler"].assert_called_once()
    app_components["MockMemory"].assert_called_once()

    # Assert wiring
    # Check TaskSystem wiring
    mock_task_instance = app_components["MockTask"].return_value
    mock_task_instance.set_handler.assert_called_once_with(app.passthrough_handler)
    assert mock_task_instance.memory_system == app.memory_system

    # Check Handler wiring
    assert app.passthrough_handler.memory_system == app.memory_system

    # Assert LLM Manager's initialize_agent was called
    app.passthrough_handler.llm_manager.initialize_agent.assert_called_once()
    args, kwargs = app.passthrough_handler.llm_manager.initialize_agent.call_args
    assert 'tools' in kwargs
    # Check that the tools passed are callables (lambdas)
    assert all(callable(t) for t in kwargs['tools'])

    # Check active tool definitions were set
    app.passthrough_handler.set_active_tool_definitions.assert_called_once()
    args, kwargs = app.passthrough_handler.set_active_tool_definitions.call_args
    assert isinstance(args[0], list) # Should be called with a list of specs

    # Check core template registration
    register_calls = mock_task_instance.register_template.call_args_list
    registered_template_names = [c.args[0]['name'] for c in register_calls]
    assert "internal:associative_matching_content" in registered_template_names
    assert "internal:associative_matching_metadata" in registered_template_names


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
    MockAnthropicToolsModule = app_components["MockAnthropicTools"]

    # Act: Instantiate Application
    with patch(AIDER_AVAILABLE_IMPORT_PATH, False):
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
    app.passthrough_handler.llm_manager.initialize_agent.assert_called_once()
    args, kwargs = app.passthrough_handler.llm_manager.initialize_agent.call_args
    assert 'tools' in kwargs
    initialized_tools_list = kwargs['tools'] # Contains wrapper lambdas

    # Verify the list contains BOTH system and Anthropic tool executor wrappers
    assert len(initialized_tools_list) == 6 # Expecting 2 system + 4 Anthropic tools
    # Check that the executors are callables (lambdas)
    assert all(callable(t) for t in initialized_tools_list)

    # --- Test the Anthropic Lambda Wrappers ---
    # Get one of the registered Anthropic executors (the lambda)
    anthropic_view_executor = registered_tools["anthropic:view"]["executor"]
    view_params = {"file_path": "view.txt"}

    # Execute the lambda
    anthropic_view_executor(view_params)

    # Assert that the underlying *mocked* anthropic_tools.view function was called
    # with the file_manager as the first arg and unpacked params
    # Access the mock function via the fixture dictionary
    app_components["mock_anthropic_view_func"].assert_called_once_with(
        app.passthrough_handler.file_manager, # Check fm was passed
        **view_params # Check params were unpacked
    )

    # Repeat for another tool, e.g., create
    anthropic_create_executor = registered_tools["anthropic:create"]["executor"]
    create_params = {"file_path": "create.txt", "content": "hello", "overwrite": True}
    anthropic_create_executor(create_params)
    app_components["mock_anthropic_create_func"].assert_called_once_with(
        app.passthrough_handler.file_manager,
        **create_params
    )

# --- NEW Test for Aider Tool Registration ---

# Fixture specifically for the Aider registration test
@pytest.fixture
def mock_app_dependencies_for_aider(tmp_path):
    """Provides mocked dependencies for Application testing, focusing on Aider."""
    with patch('src.main.FileAccessManager', spec=True) as MockFM, \
         patch('src.main.MemorySystem', spec=True) as MockMemory, \
         patch('src.main.TaskSystem', spec=True) as MockTask, \
         patch('src.main.PassthroughHandler', spec=True) as MockHandler, \
         patch('src.main.GitRepositoryIndexer', spec=True) as MockIndexer, \
         patch('src.main.SystemExecutorFunctions') as MockSysExecCls, \
         patch('src.main.anthropic_tools', spec=True) as MockAnthropicTools, \
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
        mock_handler_instance.register_tool.return_value = True
        mock_handler_instance.get_provider_identifier.return_value = "default:fixture_provider"
        mock_handler_instance.set_active_tool_definitions.return_value = True
        mock_llm_manager_instance = MagicMock(spec=LLMInteractionManager)
        mock_llm_manager_instance.initialize_agent = MagicMock()
        mock_handler_instance.llm_manager = mock_llm_manager_instance
        mock_handler_instance.tool_executors = {}
        mock_handler_instance.registered_tools = {}

        # Configure mock system executor static methods
        mock_exec_get_context = MagicMock(name="mock_execute_get_context")
        mock_exec_read_files = MagicMock(name="mock_execute_read_files")
        MockSysExecCls.execute_get_context = mock_exec_get_context
        MockSysExecCls.execute_read_files = mock_exec_read_files

        registered_tools_storage = {}
        tool_executors_storage = {}
        def mock_register_tool_impl(spec, executor):
            tool_name = spec.get('name')
            if tool_name:
                registered_tools_storage[tool_name] = {'spec': spec, 'executor': executor}
                tool_executors_storage[tool_name] = executor
                return True
            return False
        mock_handler_instance.register_tool.side_effect = mock_register_tool_impl
        # Allow access to storage
        mock_handler_instance.registered_tools = registered_tools_storage
        mock_handler_instance.tool_executors = tool_executors_storage

        mock_handler_instance.get_tools_for_agent.side_effect = lambda: list(tool_executors_storage.values())

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
