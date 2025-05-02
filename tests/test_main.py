import pytest
import os
import sys
from unittest.mock import MagicMock, patch, call, ANY
from typing import Callable # Add Callable to imports

# Ensure src is in path for imports if running tests directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# Assume Application class is importable
from src.main import Application
# Import system models and component classes from their correct locations
from src.system.models import TaskResult, TaskFailureError
from src.memory.memory_system import MemorySystem
from src.task_system.task_system import TaskSystem
from src.handler.passthrough_handler import PassthroughHandler
from src.handler.file_access import FileAccessManager # Add import
from src.memory.indexers.git_repository_indexer import GitRepositoryIndexer
# Import dispatcher for patching
from src import dispatcher
# Import SystemExecutorFunctions for patching target
from src.executors import system_executors as system_executors_module


# Define dummy tool specs used in Application init
# Aider specs removed as Aider integration is deferred
DUMMY_AIDER_AUTO_SPEC = {"name": "aiderAutomatic", "description": "Aider Auto", "input_schema": {}}
DUMMY_AIDER_INTERACTIVE_SPEC = {"name": "aiderInteractive", "description": "Aider Interactive", "input_schema": {}}
DUMMY_SYS_GET_CONTEXT_SPEC = {"name": "system:get_context", "description": "Sys Get Context", "input_schema": {}}
DUMMY_SYS_READ_FILES_SPEC = {"name": "system:read_files", "description": "Sys Read Files", "input_schema": {}}


# --- Fixture ---
@pytest.fixture
def app_instance(tmp_path):
    """Provides a default Application instance with mocked dependencies."""
    # Patch constructors/functions where they are looked up (in src.main)
    # Patch constructors/functions where they are looked up (in src.main)
    # Remove patches related to Aider
    with patch('src.main.FileAccessManager', MagicMock(spec=FileAccessManager)) as MockFM, \
         patch('src.main.MemorySystem', MagicMock(spec=MemorySystem)) as MockMemory, \
         patch('src.main.TaskSystem', MagicMock(spec=TaskSystem)) as MockTask, \
         patch('src.main.PassthroughHandler', MagicMock(spec=PassthroughHandler)) as MockHandler, \
         patch('src.main.GitRepositoryIndexer', MagicMock(spec=GitRepositoryIndexer)) as MockIndexer, \
         patch('src.main.SystemExecutorFunctions', MagicMock(spec=system_executors_module.SystemExecutorFunctions)) as MockSysExec, \
         patch('src.handler.llm_interaction_manager.Agent') as MockPydanticAgent: # Mock Agent used by manager

        # Configure mocks BEFORE Application instantiation
        mock_fm_instance = MockFM.return_value # Get FM instance
        mock_memory_instance = MockMemory.return_value
        mock_task_instance = MockTask.return_value
        mock_handler_instance = MockHandler.return_value
        mock_handler_instance.file_manager = mock_fm_instance # Handler uses FM
        mock_handler_instance.register_tool.return_value = True
        # Add mock for get_provider_identifier
        mock_handler_instance.get_provider_identifier.return_value = "anthropic:claude-3-5-sonnet-latest"
        # Add mock for set_active_tool_definitions
        mock_handler_instance.set_active_tool_definitions.return_value = True
        # Mock the LLM manager instance on the handler
        mock_llm_manager_instance = MagicMock()
        mock_handler_instance.llm_manager = mock_llm_manager_instance
        # Mock get_tools_for_agent to return a list of callables
        def dummy_tool_exec(): pass
        mock_handler_instance.get_tools_for_agent.return_value = [dummy_tool_exec]


        # Register at least one system tool so _determine_active_tools returns something
        mock_handler_instance.registered_tools = {
            "system:test_tool": {"name": "system:test_tool", "description": "Test Tool"}
        }

        # Instantiate Application - this will call __init__
        # __init__ should no longer call initialize_aider()
        app = Application(config={"handler_config": {"some_key": "val"}}) # Pass some dummy config

        # Store mocks on the app instance for easy access in tests
        app.mock_fm = mock_fm_instance # Store FM mock
        app.mock_memory = mock_memory_instance
        app.mock_task = mock_task_instance
        app.mock_handler = mock_handler_instance
        app.mock_indexer_cls = MockIndexer # Store the class mock
        app.mock_sys_exec = MockSysExec
        app.mock_pydantic_agent_cls = MockPydanticAgent # Store Agent class mock


        yield app # Provide the configured app instance to the test

# --- Test Cases ---

def test_application_init_wiring(app_instance):
    """Verify components are instantiated and wired correctly during __init__."""
    # Access the *class* mocks via the fixture's patch context managers if needed,
    # or re-patch here if easier. Let's assume the fixture holds the class mocks implicitly.
    # We need to assert calls on the *class* mocks, not the instance mocks stored on app_instance.

    # Re-accessing the mocks might be tricky without modifying the fixture.
    # A simpler way for this test is to check the *result* of the instantiation.
    assert isinstance(app_instance.memory_system, MagicMock)
    assert isinstance(app_instance.task_system, MagicMock)
    assert isinstance(app_instance.passthrough_handler, MagicMock)

    # Check that the correct arguments were passed during instantiation
    # Re-patching here for clarity on call assertions
    with patch('src.main.FileAccessManager') as MockFM_test, \
         patch('src.main.MemorySystem') as MockMemory_test, \
         patch('src.main.TaskSystem') as MockTask_test, \
         patch('src.main.PassthroughHandler') as MockHandler_test, \
         patch('src.handler.llm_interaction_manager.Agent') as MockPydanticAgent_test: # Mock Agent used by manager

        # Configure mocks for this specific test run
        mock_handler_instance_test = MockHandler_test.return_value
        mock_llm_manager_instance_test = MagicMock()
        mock_handler_instance_test.llm_manager = mock_llm_manager_instance_test
        mock_handler_instance_test.get_provider_identifier.return_value = "test:provider"
        def dummy_tool_exec_test(): pass
        mock_handler_instance_test.get_tools_for_agent.return_value = [dummy_tool_exec_test]
        mock_handler_instance_test.registered_tools = {"system:test_tool": {"name": "system:test_tool"}}


        # Re-instantiate within this test's patch context
        app_test = Application(config={"handler_config": {"some_key": "val"}})

        # Assert FileAccessManager was called (assuming patch)
        MockFM_test.assert_called_once() # Check FM instantiation with default base_path=None
        mock_fm_instance_test = MockFM_test.return_value

        # Assert MemorySystem received FileAccessManager instance
        MockMemory_test.assert_called_once()
        mem_call_args, mem_call_kwargs = MockMemory_test.call_args
        assert 'file_access_manager' in mem_call_kwargs
        assert mem_call_kwargs['file_access_manager'] == mock_fm_instance_test # Check FM passed

        # Assert TaskSystem was called (no arguments expected in the new flow)
        MockTask_test.assert_called_once()
        # No arguments expected for TaskSystem in the new flow
        task_call_args, task_call_kwargs = MockTask_test.call_args
        assert len(task_call_kwargs) == 0

        # Assert Handler received TaskSystem (MemorySystem is set later in the new flow)
        MockHandler_test.assert_called_once()
        handler_call_args, handler_call_kwargs = MockHandler_test.call_args
        assert 'task_system' in handler_call_kwargs
        assert handler_call_kwargs['task_system'] == MockTask_test.return_value
        # In the new flow, memory_system is None initially and set later
        assert 'memory_system' in handler_call_kwargs
        assert handler_call_kwargs['memory_system'] is None

        # Assert LLM Manager's initialize_agent was called
        # Check keyword arguments used in the call
        mock_llm_manager_instance_test.initialize_agent.assert_called_once()
        init_call_args, init_call_kwargs = mock_llm_manager_instance_test.initialize_agent.call_args
        assert not init_call_args # No positional args expected
        assert 'tools' in init_call_kwargs
        assert init_call_kwargs['tools'] == [dummy_tool_exec_test]


        # Assert the underlying Pydantic Agent was initialized by the manager
        # MockPydanticAgent_test.assert_called_once() # REMOVED: Manager is mocked, doesn't call Agent constructor here.


    # Check wiring using the fixture instance (already done in __init__)
    assert app_instance.memory_system == app_instance.mock_memory
    assert app_instance.task_system == app_instance.mock_task
    assert app_instance.passthrough_handler == app_instance.mock_handler
    assert app_instance.file_access_manager == app_instance.mock_fm # Check FM stored

    # Check task system has handler set
    app_instance.mock_task.set_handler.assert_called_once_with(app_instance.mock_handler)

    # Check active tool definitions were set
    app_instance.mock_handler.get_provider_identifier.assert_called_once()
    app_instance.mock_handler.set_active_tool_definitions.assert_called_once()

    # Check Aider initialization was NOT called in __init__
    # (Assuming initialize_aider is now commented out or removed from __init__)
    # If initialize_aider is still present but empty, this check might need adjustment
    # For now, we check that AiderBridge constructor wasn't called during app init.
    # Note: The fixture patches AiderBridge, so we access the class mock via app_instance
    # This assertion might fail if the fixture setup itself triggers the patch,
    # so we rely on checking tool registration below.

    # Check tool registration calls (System tools ONLY)
    tool_register_calls = app_instance.mock_handler.register_tool.call_args_list
    registered_tool_names = [c.args[0]['name'] for c in tool_register_calls]
    assert "system:get_context" in registered_tool_names
    assert "system:read_files" in registered_tool_names
    # Assert Aider tools were NOT registered
    assert "aiderAutomatic" not in registered_tool_names
    assert "aiderInteractive" not in registered_tool_names

    # Check core template registration
    register_calls = app_instance.mock_task.register_template.call_args_list
    registered_template_names = [c.args[0]['name'] for c in register_calls]
    assert "internal:associative_matching_content" in registered_template_names
    assert "internal:associative_matching_metadata" in registered_template_names
    # Optionally, add more detailed checks on the template dict structure passed
    content_template_call = next(c for c in register_calls if c.args[0]['name'] == "internal:associative_matching_content")
    metadata_template_call = next(c for c in register_calls if c.args[0]['name'] == "internal:associative_matching_metadata")
    assert "file_contents" in content_template_call.args[0]['params']
    assert "metadata_snippet" in metadata_template_call.args[0]['params']

def test_application_register_system_tools(app_instance):
    """Verify system tools are registered with the handler during init."""
    # Get all calls made to register_tool
    calls = app_instance.mock_handler.register_tool.call_args_list

    # Check system:get_context registration
    get_context_call = next((c for c in calls if c.args[0]['name'] == 'system:get_context'), None)
    assert get_context_call is not None
    assert get_context_call.args[0]['description'] is not None # Check spec details populated
    assert callable(get_context_call.args[1]) # Check executor is callable (lambda)

    # Check system:read_files registration
    read_files_call = next((c for c in calls if c.args[0]['name'] == 'system:read_files'), None)
    assert read_files_call is not None
    assert read_files_call.args[0]['description'] is not None
    assert callable(read_files_call.args[1])

    # Test the lambda wrappers by executing them
    # Get context lambda
    get_context_lambda = get_context_call.args[1]
    get_context_params = {"query": "test"}
    get_context_lambda(get_context_params) # Execute lambda
    # Assert the underlying SystemExecutorFunctions method was called correctly
    app_instance.mock_sys_exec.execute_get_context.assert_called_once_with(get_context_params, app_instance.mock_memory)

    # Read files lambda
    read_files_lambda = read_files_call.args[1]
    read_files_params = {"file_paths": ["a.txt"]}
    read_files_lambda(read_files_params) # Execute lambda
    # Assert the underlying SystemExecutorFunctions method was called correctly
    app_instance.mock_sys_exec.execute_read_files.assert_called_once_with(read_files_params, app_instance.mock_handler.file_manager)


@patch('src.main.os.path.isdir')
@patch('src.main.os.path.abspath')
def test_application_index_repository_success(mock_abspath, mock_isdir, app_instance, tmp_path):
    """Verify successful repository indexing delegates correctly."""
    repo_path_str = str(tmp_path / "repo") # Use tmp_path for realistic path
    git_dir_path = os.path.join(repo_path_str, ".git")

    # Configure mocks
    mock_abspath.return_value = repo_path_str
    # isdir needs to return True for both the repo path and the .git path within it
    mock_isdir.side_effect = lambda p: p in [repo_path_str, git_dir_path]

    # Mock the indexer instance returned by the class mock
    mock_indexer_instance = app_instance.mock_indexer_cls.return_value
    mock_indexer_instance.index_repository.return_value = {f"{repo_path_str}/file.py": "metadata"}

    # Act
    result = app_instance.index_repository(repo_path_str)

    # Assert
    assert result is True
    mock_abspath.assert_called_once_with(repo_path_str)
    # Check os.path.isdir calls
    assert call(repo_path_str) in mock_isdir.call_args_list
    assert call(git_dir_path) in mock_isdir.call_args_list

    app_instance.mock_indexer_cls.assert_called_once_with(repo_path=repo_path_str)
    # TODO: Add assertions for indexer configuration if Application sets options
    mock_indexer_instance.index_repository.assert_called_once_with(memory_system=app_instance.mock_memory)
    assert repo_path_str in app_instance.indexed_repositories

@patch('src.main.os.path.isdir')
@patch('src.main.os.path.abspath')
def test_application_index_repository_invalid_path(mock_abspath, mock_isdir, app_instance):
    """Verify indexing fails if path is invalid (not a directory)."""
    repo_path = "/invalid/path"
    mock_abspath.return_value = repo_path
    mock_isdir.return_value = False # Simulate path not being a directory

    result = app_instance.index_repository(repo_path)

    assert result is False
    mock_abspath.assert_called_once_with(repo_path)
    mock_isdir.assert_called_once_with(repo_path) # Only checks the main path
    app_instance.mock_indexer_cls.assert_not_called()
    assert repo_path not in app_instance.indexed_repositories


@patch('src.main.os.path.isdir')
@patch('src.main.os.path.abspath')
def test_application_index_repository_not_git(mock_abspath, mock_isdir, app_instance, tmp_path):
    """Verify indexing fails if path is not a git repo (no .git dir)."""
    repo_path_str = str(tmp_path / "not_a_repo")
    git_dir_path = os.path.join(repo_path_str, ".git")

    mock_abspath.return_value = repo_path_str
    # Simulate only the repo path being a directory, not the .git path
    mock_isdir.side_effect = lambda p: p == repo_path_str

    result = app_instance.index_repository(repo_path_str)

    assert result is False
    mock_abspath.assert_called_once_with(repo_path_str)
    # Check isdir calls
    assert call(repo_path_str) in mock_isdir.call_args_list
    assert call(git_dir_path) in mock_isdir.call_args_list
    app_instance.mock_indexer_cls.assert_not_called() # Should fail before indexer instantiation
    assert repo_path_str not in app_instance.indexed_repositories


@patch('src.main.os.path.isdir')
@patch('src.main.os.path.abspath')
def test_application_index_repository_indexer_error(mock_abspath, mock_isdir, app_instance, tmp_path):
    """Verify indexing fails if indexer raises an exception."""
    repo_path_str = str(tmp_path / "repo_fail")
    git_dir_path = os.path.join(repo_path_str, ".git")

    mock_abspath.return_value = repo_path_str
    mock_isdir.side_effect = lambda p: p in [repo_path_str, git_dir_path]
    mock_indexer_instance = app_instance.mock_indexer_cls.return_value
    mock_indexer_instance.index_repository.side_effect = Exception("Indexing failed!")

    result = app_instance.index_repository(repo_path_str)

    assert result is False
    app_instance.mock_indexer_cls.assert_called_once_with(repo_path=repo_path_str)
    mock_indexer_instance.index_repository.assert_called_once()
    assert repo_path_str not in app_instance.indexed_repositories


def test_application_handle_query_delegation(app_instance):
    """Verify handle_query delegates to the handler."""
    query = "test query"
    # Handler returns a TaskResult object
    mock_response_obj = TaskResult(status="COMPLETE", content="Handler Response", notes={})
    app_instance.mock_handler.handle_query.return_value = mock_response_obj

    result_dict = app_instance.handle_query(query)

    app_instance.mock_handler.handle_query.assert_called_once_with(query)
    # Check that the returned dict matches the model dump of the object
    assert result_dict == mock_response_obj.model_dump(exclude_none=True)

def test_application_handle_query_exception(app_instance):
    """Verify handle_query handles exceptions from the handler."""
    query = "query causing error"
    app_instance.mock_handler.handle_query.side_effect = Exception("Handler crashed")

    result_dict = app_instance.handle_query(query)

    assert result_dict['status'] == "FAILED"
    assert "Handler crashed" in result_dict['content']
    assert result_dict['notes']['error']['reason'] == "unexpected_error"

def test_application_reset_conversation_delegation(app_instance):
    """Verify reset_conversation delegates to the handler."""
    app_instance.reset_conversation()
    app_instance.mock_handler.reset_conversation.assert_called_once()

# Patch the dispatcher function where it's imported in main.py
@patch('src.main.dispatcher.execute_programmatic_task')
def test_application_handle_task_command_delegation(mock_dispatcher_func, app_instance):
    """Verify handle_task_command delegates to the dispatcher function."""
    identifier = "task:id"
    params = {"p": 1}
    flags = {"f": True}
    # Dispatcher returns a dict directly
    mock_dispatch_result = TaskResult(status="COMPLETE", content="Dispatch Result", notes={}).model_dump(exclude_none=True)
    mock_dispatcher_func.return_value = mock_dispatch_result

    result = app_instance.handle_task_command(identifier, params, flags)

    mock_dispatcher_func.assert_called_once_with(
        identifier=identifier,
        params=params,
        flags=flags,
        handler_instance=app_instance.mock_handler,
        task_system_instance=app_instance.mock_task,
        memory_system=app_instance.mock_memory # Ensure memory system is passed
        # optional_history_str=None # Check if history needs passing
    )
    assert result == mock_dispatch_result

@patch('src.main.dispatcher.execute_programmatic_task')
def test_application_handle_task_command_exception(mock_dispatcher_func, app_instance):
    """Verify handle_task_command handles exceptions from the dispatcher."""
    identifier = "task:id"
    params = {"p": 1}
    flags = {"f": True}
    mock_dispatcher_func.side_effect = Exception("Dispatcher error")

    result = app_instance.handle_task_command(identifier, params, flags)

    assert result['status'] == "FAILED"
    assert "Dispatcher error" in result['content']
    assert result['notes']['error']['reason'] == "unexpected_error"

# --- Test for Deferred Aider Initialization ---

def test_application_initialize_aider_deferred(app_instance):
    """Verify initialize_aider is a placeholder and does not register tools."""
    # Reset mock calls before calling the method
    app_instance.mock_handler.register_tool.reset_mock()
    register_call_count_before = app_instance.mock_handler.register_tool.call_count

    # Call the placeholder method
    app_instance.initialize_aider()

    # Assert the bridge remains None
    assert app_instance.aider_bridge is None

    # Assert no new tools were registered
    register_call_count_after = app_instance.mock_handler.register_tool.call_count
    assert register_call_count_after == register_call_count_before


# --- Test case for Application init failure ---
def test_application_init_failure():
    """Verify Application __init__ handles component instantiation failure."""
    with patch('src.main.MemorySystem', side_effect=Exception("Memory init failed")):
        with pytest.raises(Exception, match="Memory init failed"):
            Application() # Instantiation should fail and raise

# --- NEW Test for Tool Format ---
def test_application_init_passes_correct_tool_format_to_agent(tmp_path):
    """
    Verify the correct tool format (list[Callable]) is passed to LLMInteractionManager.initialize_agent.
    IDL Quotes:
    - Application.__init__: Trigger agent initialization: Call `handler.llm_manager.initialize_agent(tools=agent_tools)`.
    - BaseHandler.get_tools_for_agent: Retrieves the registered tool executor functions... Returns a list of callables...
    - LLMInteractionManager.initialize_agent: Instantiates the `pydantic-ai Agent`, passing the provided `tools` list.
    """
    # Arrange: Patch dependencies thoroughly for init sequence
    with patch('src.main.FileAccessManager', MagicMock(spec=FileAccessManager)) as MockFM, \
         patch('src.main.MemorySystem', MagicMock(spec=MemorySystem)) as MockMemory, \
         patch('src.main.TaskSystem', MagicMock(spec=TaskSystem)) as MockTask, \
         patch('src.main.PassthroughHandler', MagicMock(spec=PassthroughHandler)) as MockHandler, \
         patch('src.main.GitRepositoryIndexer', MagicMock(spec=GitRepositoryIndexer)), \
         patch('src.main.SystemExecutorFunctions', MagicMock(spec=system_executors_module.SystemExecutorFunctions)), \
         patch('src.handler.llm_interaction_manager.Agent') as MockPydanticAgent: # Mock the actual Agent class used by manager

        # Configure handler mock specifically for this test
        mock_handler_instance = MockHandler.return_value
        mock_llm_manager_instance = MagicMock() # Mock the manager instance itself
        mock_handler_instance.llm_manager = mock_llm_manager_instance
        mock_handler_instance.get_provider_identifier.return_value = "test:provider"

        # Define dummy executor functions to be returned by get_tools_for_agent
        def sys_tool_exec(): pass
        def provider_tool_exec(): pass
        mock_handler_instance.get_tools_for_agent.return_value = [sys_tool_exec, provider_tool_exec]
        # Ensure registered_tools has something for _determine_active_tools
        mock_handler_instance.registered_tools = {"system:test": {"name": "system:test"}}


        # Act: Instantiate Application to trigger the sequence
        app = Application()

        # Assert: Check the arguments passed to the *mocked* initialize_agent
        # This mock is on the handler's manager instance
        app.passthrough_handler.llm_manager.initialize_agent.assert_called_once()
        call_args, call_kwargs = app.passthrough_handler.llm_manager.initialize_agent.call_args

        # Check the 'tools' keyword argument passed to initialize_agent
        # Check kwargs as the call uses tools=...
        assert not call_args # Should have no positional args
        assert 'tools' in call_kwargs
        passed_tools = call_kwargs['tools']
        assert isinstance(passed_tools, list)
        assert len(passed_tools) == 2
        # Verify it's the list of callables we configured get_tools_for_agent to return
        assert passed_tools[0] is sys_tool_exec
        assert passed_tools[1] is provider_tool_exec
        assert all(callable(t) for t in passed_tools)

        # Also assert that the underlying pydantic Agent constructor (MockPydanticAgent)
        # was called *by initialize_agent* with this list.
        # This requires initialize_agent to actually call Agent(tools=...)
        # Assuming initialize_agent implementation calls Agent correctly:
        MockPydanticAgent.assert_called_once()
        agent_call_args, agent_call_kwargs = MockPydanticAgent.call_args
        assert 'tools' in agent_call_kwargs
        assert agent_call_kwargs['tools'] == [sys_tool_exec, provider_tool_exec]
