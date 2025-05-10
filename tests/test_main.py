import pytest
import json
from unittest.mock import patch, MagicMock, ANY, call, AsyncMock, mock_open # Add json and mock_open imports
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
# Import the class being patched for autospec
from src.executors.system_executors import SystemExecutorFunctions
# Import AiderExecutors for autospec
try:
    from src.executors.aider_executors import AiderExecutorFunctions
except ImportError:
    AiderExecutorFunctions = object # type: ignore
# Import Agent for autospec if pydantic-ai is installed
try:
    from pydantic_ai import Agent as RealPydanticAgent
except ImportError:
    RealPydanticAgent = object # type: ignore
# Import Anthropic tool functions for autospec
from src.tools import anthropic_tools as anthropic_tools_module

from src import dispatcher
# Import modules for patching targets
# No longer needed for spec, but keep for potential type hints if desired
# from src.executors import system_executors as system_executors_module
# from src.tools import anthropic_tools as anthropic_tools_module # Keep for spec import below
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

# Import the new template definitions from main to check against
from src.main import GENERATE_PLAN_TEMPLATE, ANALYZE_AIDER_RESULT_TEMPLATE


# Define dummy tool specs used in Application init
# Aider specs removed as Aider integration is deferred
DUMMY_SYS_GET_CONTEXT_SPEC = {"name": "system:get_context", "description": "Sys Get Context", "input_schema": {}}
DUMMY_SYS_READ_FILES_SPEC = {"name": "system:read_files", "description": "Sys Read Files", "input_schema": {}}
# Add spec for shell command
DUMMY_SYS_SHELL_SPEC = {"name": "system:execute_shell_command", "description": "Executes a shell command safely.", "input_schema": {}}


# Define PROJECT_ROOT for use in the test if needed
# Adjust the path based on the actual location of test_main.py relative to the project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# --- Test Fixture ---
@pytest.fixture
def app_components(mocker, tmp_path):
    """Provides mocked components for Application testing using autospec."""
    
    # For classes that will be instantiated, we want the patch to replace the class
    # with a MagicMock that is callable (like a constructor) and returns our instance mock.
    with patch('src.main.MemorySystem', new_callable=MagicMock) as MockMemory, \
         patch('src.main.TaskSystem', new_callable=MagicMock) as MockTask, \
         patch('src.main.PassthroughHandler', new_callable=MagicMock) as MockHandler, \
         patch('src.main.FileAccessManager', new_callable=MagicMock) as MockFileAccessManager, \
         patch('src.handler.base_handler.LLMInteractionManager', new_callable=MagicMock) as MockLLMInteractionManager, \
         patch('src.main.AiderBridge', new_callable=MagicMock) as MockAiderBridge, \
         patch('src.main.GitRepositoryIndexer', new_callable=MagicMock) as MockIndexer, \
         patch('src.main.SystemExecutorFunctions', new_callable=MagicMock) as MockSysExecCls, \
         patch('src.main.AiderExecutors', autospec=True) as MockAiderExec, \
         patch('src.handler.llm_interaction_manager.Agent', autospec=True) as MockPydanticAgent, \
         patch('src.tools.anthropic_tools.view', autospec=True) as mock_anthropic_view_func, \
         patch('src.tools.anthropic_tools.create', autospec=True) as mock_anthropic_create_func, \
         patch('src.tools.anthropic_tools.str_replace', autospec=True) as mock_anthropic_replace_func, \
         patch('src.tools.anthropic_tools.insert', autospec=True) as mock_anthropic_insert_func:

        # --- Create Mock Instances that the Class Mocks will return ---
        mock_memory_instance = MagicMock(spec=MemorySystem)
        mock_task_instance = MagicMock(spec=TaskSystem)
        # MockHandler.return_value is used directly below, so we configure mock_handler_instance from that
        mock_fm_instance = MagicMock(spec=FileAccessManager)
        mock_llm_manager_instance = MagicMock(spec=LLMInteractionManager) # Spec for instance
        mock_aider_bridge_instance = MagicMock(spec=AiderBridge)     # Instance for AiderBridge
        mock_indexer_instance = MagicMock(spec=GitRepositoryIndexer) # Instance for Indexer
        mock_sys_exec_instance = MagicMock(spec=SystemExecutorFunctions) # Instance for SystemExecutorFunctions

        # --- Configure Class Mocks to return these instances when called ---
        MockMemory.return_value = mock_memory_instance
        MockTask.return_value = mock_task_instance
        # MockHandler is used to get mock_handler_instance, then configured
        MockFileAccessManager.return_value = mock_fm_instance
        MockLLMInteractionManager.return_value = mock_llm_manager_instance
        MockAiderBridge.return_value = mock_aider_bridge_instance # Crucial: MockAiderBridge() will now return this
        MockIndexer.return_value = mock_indexer_instance
        MockSysExecCls.return_value = mock_sys_exec_instance # Crucial: MockSysExecCls() will now return this
        # MockAiderExec does not need a return_value if only its static/class methods are patched/used
        # MockPydanticAgent does not need a return_value as LLMInteractionManager is mocked

        # --- Configure Mock Instances ---
        # mock_memory_instance is configured by MockMemory.return_value implicitly
        # mock_task_instance is configured by MockTask.return_value implicitly
        mock_task_instance.set_handler = MagicMock() 
        mock_task_instance.register_template = MagicMock() 
        mock_task_instance.memory_system = None # As per existing fixture

        mock_handler_instance = MockHandler.return_value # Get the instance from the class mock
        mock_handler_instance.memory_system = None
        mock_handler_instance.file_manager = mock_fm_instance 
        mock_handler_instance.llm_manager = mock_llm_manager_instance
        mock_handler_instance.get_provider_identifier.return_value = "mock_provider:default"
        
        registered_tools_storage = {}
        tool_executors_storage = {}
        def mock_register_tool_side_effect(tool_spec, executor_func):
            tool_name = tool_spec.get("name")
            if tool_name:
                registered_tools_storage[tool_name] = tool_spec 
                tool_executors_storage[tool_name] = executor_func
                return True
            return False
        
        mock_handler_instance.register_tool = MagicMock(side_effect=mock_register_tool_side_effect)
        mock_handler_instance.registered_tools = registered_tools_storage
        mock_handler_instance.tool_executors = tool_executors_storage
        
        def mock_get_tools_for_agent():
            return list(tool_executors_storage.values())

        mock_handler_instance.get_tools_for_agent = MagicMock(side_effect=mock_get_tools_for_agent)
        mock_handler_instance.set_active_tool_definitions = MagicMock()
        mock_llm_manager_instance.initialize_agent = MagicMock() 
        
        # Configure other instance attributes if needed by Application.__init__
        mock_fm_instance.base_path = "/mocked/base/path"

        mocks = {
            "MockMemorySystem": MockMemory,
            "MockTaskSystem": MockTask,
            "MockHandler": MockHandler,
            "MockFM": MockFileAccessManager,
            "MockLLMInteractionManager": MockLLMInteractionManager,
            "MockAiderBridge": MockAiderBridge, # This is the mock for the AiderBridge CLASS
            "MockIndexer": MockIndexer,
            "MockSysExecCls": MockSysExecCls, # This is the mock for the SystemExecutorFunctions CLASS
            "MockAiderExec": MockAiderExec,
            "MockPydanticAgent": MockPydanticAgent,

            "mock_memory_system_instance": mock_memory_instance,
            "mock_task_system_instance": mock_task_instance,
            "mock_handler_instance": mock_handler_instance,
            "mock_fm_instance": mock_fm_instance,
            "mock_llm_manager_instance": mock_llm_manager_instance,
            "mock_aider_bridge_instance": mock_aider_bridge_instance, # This is the INSTANCE mock
            "mock_indexer_instance": mock_indexer_instance,
            "mock_sys_exec_instance": mock_sys_exec_instance, # This is the INSTANCE mock

            "registered_tools_storage": registered_tools_storage,
            "tool_executors_storage": tool_executors_storage,

            "mock_anthropic_view_func": mock_anthropic_view_func,
            "mock_anthropic_create_func": mock_anthropic_create_func,
            "mock_anthropic_replace_func": mock_anthropic_replace_func,
            "mock_anthropic_insert_func": mock_anthropic_insert_func,
        }
        
        if hasattr(MockAiderExec, 'execute_aider_automatic'):
            MockAiderExec.execute_aider_automatic.__qualname__ = 'AiderExecutorFunctions.execute_aider_automatic'
            if not hasattr(MockAiderExec.execute_aider_automatic, '__name__'):
                MockAiderExec.execute_aider_automatic.__name__ = 'execute_aider_automatic_mock'
                
        if hasattr(MockAiderExec, 'execute_aider_interactive'):
            MockAiderExec.execute_aider_interactive.__qualname__ = 'AiderExecutorFunctions.execute_aider_interactive'
            if not hasattr(MockAiderExec.execute_aider_interactive, '__name__'):
                MockAiderExec.execute_aider_interactive.__name__ = 'execute_aider_interactive_mock'
                
        yield mocks

# --- Tests ---

def test_application_init_minimal(app_components):
    """Test minimal Application initialization."""
    app = Application()
    assert isinstance(app, Application)
    # Check components were instantiated (mocks were called)
    app_components["MockFM"].assert_called_once()
    app_components["MockTaskSystem"].assert_called_once()
    app_components["MockHandler"].assert_called_once()
    app_components["MockMemorySystem"].assert_called_once()
    # Check internal instances are set
    assert app.file_access_manager is not None
    assert app.task_system is not None
    assert app.passthrough_handler is not None
    assert app.memory_system is not None
    # Check system_executors is the correct type
    from src.executors.system_executors import SystemExecutorFunctions
    assert isinstance(app.system_executors, SystemExecutorFunctions)

def test_application_init_wiring(app_components):
    """Verify components are instantiated and wired correctly during __init__."""
    # Arrange: Set a default provider ID
    # The fixture now sets it to "mock_provider:default"
    # Arrange: No need to mock get_tools_for_agent return value explicitly anymore.
    # Let the real registration populate the mock handler's tool_executors.

    # Act: Instantiate Application
    app = Application(config={}) # Pass empty config

    # Assert component instances were created by the Mocks
    assert app.memory_system == app_components['mock_memory_system_instance']
    assert app.task_system == app_components['mock_task_system_instance']
    # The app.passthrough_handler will be the return_value of the Patched PassthroughHandler class
    assert app.passthrough_handler == app_components['MockHandler'].return_value
    assert app.file_access_manager == app_components['mock_fm_instance']
    # Note: system_executors is a real instance, not a mock

    # Ensure the mock_handler_instance from the fixture is the one used by the app
    assert app.passthrough_handler == app_components['mock_handler_instance']
    # Assert wiring calls were made (using the instances returned by the mocks)
    app_components['mock_task_system_instance'].set_handler.assert_called_once_with(app.passthrough_handler)

    # Assert SystemExecutorFunctions instantiation call
    # Assuming app_components["MockSysExecCls"] is the patch object for SystemExecutorFunctions class
    # And app_components['mock_handler_instance'] is the mock for PassthroughHandler
    app_components["MockSysExecCls"].assert_called_once_with(
        memory_system=app.memory_system, # Or ANY if comparing instance is tricky
        file_manager=app.file_access_manager, # Or ANY
        command_executor_module=ANY, # Or a specific mock for command_executor module
        handler_instance=app.passthrough_handler # Pass the actual handler instance from app
    )

    # Verify attribute assignments
    assert app.passthrough_handler.memory_system == app_components['mock_memory_system_instance']
    assert app.task_system.memory_system == app_components['mock_memory_system_instance']

    # Assert tool registration calls (at least system tools should be registered)
    app_components['mock_handler_instance'].register_tool.assert_called()
    system_context_call = next((c for c in app_components['mock_handler_instance'].register_tool.call_args_list if c.args[0].get('name') == 'system_get_context'), None)
    assert system_context_call is not None, "system_get_context tool was not registered"
    # Assert the executor is the instance method from the real instance
    assert system_context_call.args[1] == app.system_executors.execute_get_context

    # Assert agent initialization call
    app_components['mock_handler_instance'].get_tools_for_agent.assert_called_once()
    app_components['mock_llm_manager_instance'].initialize_agent.assert_called_once()

    # Get the actual tools passed
    actual_call_args, actual_call_kwargs = app_components['mock_llm_manager_instance'].initialize_agent.call_args
    actual_tools_passed = actual_call_kwargs.get('tools', []) # Use get with default

    # Assert that the expected system tool *executors* are present
    # Assumes app.system_executors holds the real instance used during init
    assert isinstance(actual_tools_passed, list)
    expected_system_executors = [
        app.system_executors.execute_get_context,
        app.system_executors.execute_read_files,
        app.system_executors.execute_list_directory,
        app.system_executors.execute_write_file,
        app.system_executors.execute_shell_command,
    ]
    for executor in expected_system_executors:
        assert executor in actual_tools_passed, f"Expected system executor {executor.__name__} not found in tools passed to initialize_agent"

    # Check for shell command tool registration
    shell_command_call = next((c for c in app_components['mock_handler_instance'].register_tool.call_args_list if c.args[0].get('name') == 'system_execute_shell_command'), None)
    assert shell_command_call is not None, "system_execute_shell_command tool was not registered"
    assert callable(shell_command_call.args[1])
    # Assert the executor is the instance method from the real instance
    assert shell_command_call.args[1] == app.system_executors.execute_shell_command

    # Check for new context management tools
    mock_register_tool_calls = app_components['mock_handler_instance'].register_tool.call_args_list
    
    clear_context_tool_call = next((c for c in mock_register_tool_calls if c.args[0].get('name') == 'system_clear_handler_data_context'), None)
    assert clear_context_tool_call is not None, "system_clear_handler_data_context tool was not registered"
    assert clear_context_tool_call.args[0]["description"] == "Clears the active data context in the handler."
    # Assuming app.system_executors is the real instance, its methods are directly passed
    assert clear_context_tool_call.args[1] == app.system_executors.execute_clear_handler_data_context

    prime_context_tool_call = next((c for c in mock_register_tool_calls if c.args[0].get('name') == 'system_prime_handler_data_context'), None)
    assert prime_context_tool_call is not None, "system_prime_handler_data_context tool was not registered"
    assert prime_context_tool_call.args[0]["description"] == "Primes the data context in the handler using a query or initial files."
    assert prime_context_tool_call.args[0]["input_schema"]["properties"]["query"]["type"] == ["string", "null"]
    assert prime_context_tool_call.args[1] == app.system_executors.execute_prime_handler_data_context


def test_index_repository_success(app_components, tmp_path):
    """Test successful repository indexing."""
    # Arrange
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    repo_path = str(tmp_path)

    MockIndexerClass = app_components["MockIndexer"]
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


def test_application_init_with_aider(app_components):
    """Verify AiderBridge is initialized and tools registered when available."""
    # Arrange (Mocks are already configured in the fixture)
    # Access the mocked class methods
    mock_aider_auto_func = app_components['MockAiderExec'].execute_aider_automatic
    mock_aider_inter_func = app_components['MockAiderExec'].execute_aider_interactive

    # Define the expected Aider config that should be passed to AiderBridge
    expected_aider_config = {
        "transport": "stdio",
        "command": "aider_server_command_from_test",
        "args": ["--test-arg"],
        "env": {"TEST_VAR": "true"}
    }

    # Prepare the JSON structure expected by _load_mcp_config
    mock_config_data = {"mcpServers": {"aider-mcp-server": expected_aider_config}}
    mock_json_string = json.dumps(mock_config_data)

    # Use patch.dict for environment variable and patch file operations
    with patch.dict(os.environ, {'AIDER_ENABLED': 'true'}, clear=False), \
         patch('src.main.os.path.exists') as mock_exists, \
         patch('src.main.open', mock_open(read_data=mock_json_string)), \
         patch('src.main.json.load') as mock_json_load:

        # Configure mocks for file loading
        mock_exists.return_value = True  # Simulate .mcp.json exists
        mock_json_load.return_value = mock_config_data  # Simulate json.load returning our data

        # Act
        app = Application(config={"aider": {"enabled": True}})

    # Assert AiderBridge was instantiated with the expected config
    app_components['MockAiderBridge'].assert_called_once_with(
        memory_system=app.memory_system,
        file_access_manager=app.file_access_manager,
        config=expected_aider_config
    )
    assert app.aider_bridge == app_components['mock_aider_bridge_instance']

    # Assert Aider tools were registered with the handler
    registered_tools = app_components['registered_tools_storage']
    assert 'aider_automatic' in registered_tools
    assert 'aider_interactive' in registered_tools
    assert callable(registered_tools['aider_automatic']['executor'])
    assert callable(registered_tools['aider_interactive']['executor'])

    # Check that register_tool was called for aider tools
    mock_handler = app_components['mock_handler_instance']
    aider_auto_call = next((c for c in mock_handler.register_tool.call_args_list if c.args[0].get('name') == 'aider_automatic'), None)
    aider_inter_call = next((c for c in mock_handler.register_tool.call_args_list if c.args[0].get('name') == 'aider_interactive'), None)
    assert aider_auto_call is not None, "aider_automatic tool was not registered"
    assert aider_inter_call is not None, "aider_interactive tool was not registered"
    assert callable(aider_auto_call.args[1]), "Executor for aider_automatic is not callable"
    assert callable(aider_inter_call.args[1]), "Executor for aider_interactive is not callable"

def test_application_init_without_aider(app_components):
    """Verify AiderBridge is NOT initialized and tools NOT registered when unavailable."""
    # Use patch.dict to set the environment variable for the duration of the test
    with patch.dict(os.environ, {'AIDER_ENABLED': 'false'}, clear=False):
        # Act
        app = Application()

    # Assert AiderBridge was NOT instantiated
    app_components['MockAiderBridge'].assert_not_called()
    assert app.aider_bridge is None

    # Assert Aider tools were NOT registered
    registered_tools = app_components['registered_tools_storage']
    assert 'aider_automatic' not in registered_tools
    assert 'aider_interactive' not in registered_tools


def test_application_init_with_anthropic(app_components):
    """Verify Anthropic tools are registered for Anthropic provider."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "anthropic:claude-3-5-sonnet-latest"
    # Mocks for functions are already configured in the fixture

    # Use patch.dict to set the environment variable for the duration of the test
    with patch.dict(os.environ, {'AIDER_ENABLED': 'false'}, clear=False):
        # Act
        app = Application()

    # Assert Anthropic tools were registered
    # Tools are registered on the handler instance.
    # Assuming app.passthrough_handler is the mock_handler_instance from app_components
    mock_handler = app_components['mock_handler_instance']
    registered_tools = mock_handler.registered_tools

    assert 'anthropic_view' in registered_tools
    assert 'anthropic_create' in registered_tools
    assert 'anthropic_str_replace' in registered_tools
    assert 'anthropic_insert' in registered_tools

    # Check specs and executors
    assert registered_tools['anthropic_view'] == ANTHROPIC_VIEW_SPEC
    assert callable(app_components['tool_executors_storage']['anthropic_view'])
    assert registered_tools['anthropic_create'] == ANTHROPIC_CREATE_SPEC
    assert callable(app_components['tool_executors_storage']['anthropic_create'])
    assert registered_tools['anthropic_str_replace'] == ANTHROPIC_STR_REPLACE_SPEC
    assert callable(app_components['tool_executors_storage']['anthropic_str_replace'])
    assert registered_tools['anthropic_insert'] == ANTHROPIC_INSERT_SPEC
    assert callable(app_components['tool_executors_storage']['anthropic_insert'])
    # Check that the executor wrapper correctly points to the mocked function
    # Similar to Aider, this requires calling the lambda. Rely on patching.

def test_application_init_without_anthropic(app_components):
    """Verify Anthropic tools are NOT registered for non-Anthropic provider."""
    # Arrange
    app_components["mock_handler_instance"].get_provider_identifier.return_value = "openai:gpt-4o"

    # Use patch.dict to set the environment variable for the duration of the test
    with patch.dict(os.environ, {'AIDER_ENABLED': 'false'}, clear=False):
        # Act
        app = Application()

    # Assert Anthropic tools were NOT registered
    registered_tools = app_components['registered_tools_storage']
    assert 'anthropic_view' not in registered_tools
    assert 'anthropic_create' not in registered_tools
    assert 'anthropic_str_replace' not in registered_tools
    assert 'anthropic_insert' not in registered_tools

def test_application_init_registers_user_tasks(app_components):
    """Verify that user:generate-plan and user:analyze-aider-result templates are registered."""
    # Arrange
    mock_task_system_instance = app_components['mock_task_system_instance']

    # Act
    app = Application() # Initialization triggers registration

    # Assert
    # Check that register_template was called with the correct template structures
    calls = mock_task_system_instance.register_template.call_args_list

    # Check for generate-plan template
    generate_plan_call = next((c for c in calls if c.args[0].get('name') == 'user:generate-plan'), None)
    assert generate_plan_call is not None, "'user:generate-plan' template was not registered"
    # Verify key fields match the definition in main.py
    registered_gen_plan = generate_plan_call.args[0]
    assert registered_gen_plan['name'] == GENERATE_PLAN_TEMPLATE['name']
    assert registered_gen_plan['type'] == 'atomic'
    assert 'user_prompts' in registered_gen_plan['params']
    assert 'initial_context' in registered_gen_plan['params']
    assert registered_gen_plan['output_format']['schema'] == 'src.system.models.DevelopmentPlan'

    # Check for analyze-aider-result template
    analyze_result_call = next((c for c in calls if c.args[0].get('name') == 'user:analyze-aider-result'), None)
    assert analyze_result_call is not None, "'user:analyze-aider-result' template was not registered"
    # Verify key fields match the definition in main.py
    registered_analyze = analyze_result_call.args[0]
    assert registered_analyze['name'] == ANALYZE_AIDER_RESULT_TEMPLATE['name']
    assert registered_analyze['type'] == 'atomic'
    assert 'aider_result_content' in registered_analyze['params']
    assert 'aider_result_status' in registered_analyze['params']
    assert 'original_prompt' in registered_analyze['params']
    assert 'iteration' in registered_analyze['params']
    assert 'max_retries' in registered_analyze['params']
    assert registered_analyze['output_format']['schema'] == 'src.system.models.FeedbackResult'
