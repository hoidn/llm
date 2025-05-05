Okay, let's break down the refactoring required to eliminate the patching that's causing issues in these specific failing tests, focusing on Dependency Injection (DI).

**1. Refactoring for `tests/aider_bridge/test_bridge.py`**

*   **Problem:** `AiderBridge` directly imports and uses `mcp.py` components (`stdio_client`, `ClientSession`, `StdioServerParameters`) based on the `MCP_AVAILABLE` flag. Patching these after the module import is problematic.
*   **Refactoring Goal:** Inject the dependency responsible for creating and managing the MCP client session into `AiderBridge`.

**Steps:**

1.  **Define an Interface/Provider:** Create a mechanism (could be a class or even a factory function) that provides an MCP session. Let's imagine a simple provider class.
    ```python
    # Potentially in a new file, e.g., src/mcp_providers.py
    # Or defined near AiderBridge if specific to it
    import asyncio
    from abc import ABC, abstractmethod
    from typing import AsyncContextManager

    # --- Define an interface for the session the provider yields ---
    # This avoids depending directly on the concrete mcp.py ClientSession type
    # You can use typing.Protocol as well
    class McpClientSessionInterface(ABC):
        @abstractmethod
        async def initialize(self) -> None:
            pass

        @abstractmethod
        async def call_tool(self, name: str, arguments: dict) -> list: # Assuming list of content blocks
            pass

    # --- Define the Provider Interface ---
    class McpSessionProviderInterface(ABC):
        @abstractmethod
        def get_session(self) -> AsyncContextManager[McpClientSessionInterface]:
            """Returns an async context manager yielding an active session."""
            pass

    # --- Example Real Implementation (using actual mcp.py) ---
    # This would live where your production dependencies are managed
    try:
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from mcp.client.session import ClientSession as RealMcpClientSession
        MCP_AVAILABLE = True

        class StdioMcpSessionProvider(McpSessionProviderInterface):
            def __init__(self, config):
                self.mcp_config = config # e.g., {"mcp_stdio_command": "...", "mcp_stdio_args": [...]}
                if not self.mcp_config.get("mcp_stdio_command"):
                   raise ValueError("MCP stdio command missing in config")

            def get_session(self) -> AsyncContextManager[McpClientSessionInterface]:
                params = StdioServerParameters(
                    command=self.mcp_config["mcp_stdio_command"],
                    args=self.mcp_config.get("mcp_stdio_args", []),
                    env=self.mcp_config.get("mcp_stdio_env", {})
                )
                # Need to wrap the actual stdio_client and ClientSession context managers
                # to return an object conforming to McpClientSessionInterface
                # This requires careful handling of the nested async context managers.
                # A simplified way is to return the real session directly if its interface matches.
                # Assuming RealMcpClientSession happens to match McpClientSessionInterface:

                # This is tricky because stdio_client itself is an async context manager
                # returning reader/writer, which ClientSession then uses.
                # A better pattern might be for the provider to manage the process
                # and yield the session.

                # --- Revised Provider Approach (Manages connection internally) ---
                # This provider becomes stateful, holding the connection.
                # Simpler approach for DI: inject the already connected session factory/client

                # Let's stick to the initial idea: Injecting a provider that *yields* a session CM
                # The complexity lies in wrapping the nested CMs. For simplicity in this example,
                # let's assume mcp.py provides a single high-level client CM.
                # If not, this provider becomes more complex.

                # --- Simplest DI: Inject a factory function ---
                # This might be the easiest refactor initially.

                # --> Let's revert to injecting a provider, assuming we can make it work.
                # The provider needs to return something like this:
                class ManagedSessionContext:
                    def __init__(self, params):
                        self._params = params
                        self._stdio_cm = None
                        self._session_cm = None
                        self._session = None

                    async def __aenter__(self):
                        self._stdio_cm = stdio_client(self._params)
                        reader, writer = await self._stdio_cm.__aenter__()
                        self._session_cm = RealMcpClientSession(reader, writer)
                        self._session = await self._session_cm.__aenter__()
                        # Add initialize call here if needed upon entering session context
                        await self._session.initialize()
                        return self._session # Yield the session instance

                    async def __aexit__(self, exc_type, exc_val, exc_tb):
                        session_exit_ok = True
                        stdio_exit_ok = True
                        try:
                            if self._session_cm:
                                await self._session_cm.__aexit__(exc_type, exc_val, exc_tb)
                        except Exception:
                            session_exit_ok = False # Log error?
                        finally:
                            try:
                                if self._stdio_cm:
                                    await self._stdio_cm.__aexit__(exc_type, exc_val, exc_tb)
                            except Exception:
                                stdio_exit_ok = False # Log error?
                        # Potentially raise if errors occurred during exit
                        if not session_exit_ok or not stdio_exit_ok:
                             # Decide error handling strategy
                             pass

                return ManagedSessionContext(params)


    except ImportError:
        MCP_AVAILABLE = False
        # Define dummy provider for code that runs if MCP isn't installed
        class DummyMcpSessionProvider(McpSessionProviderInterface):
             def get_session(self):
                 raise NotImplementedError("MCP not available")

    ```

2.  **Refactor `AiderBridge`:**
    *   Remove the `MCP_AVAILABLE` import-time check and associated dummy classes.
    *   Modify `__init__` to accept the `McpSessionProviderInterface`.
    *   Modify `call_aider_tool` to use the injected provider.

    ```python
    # src/aider_bridge/bridge.py
    import json
    import logging
    # Remove mcp imports from here!
    from src.system_prompts.schemas import TaskResult # Assuming this is your result format
    # Import the NEW provider interface
    from ..mcp_providers import McpSessionProviderInterface, McpClientSessionInterface # Adjust import path

    log = logging.getLogger(__name__)

    # Helper to create consistent failure results
    def _create_failed_result_dict(reason: str, message: str, details: dict = None) -> TaskResult:
        return {"status": "FAILED", "content": message, "notes": {"error": {"reason": reason, "details": details or {}}}}


    class AiderBridge:
        # Inject the provider instead of config for MCP parts
        def __init__(self, memory_system, file_access_manager, mcp_session_provider: McpSessionProviderInterface):
            self.memory = memory_system
            self.file_manager = file_access_manager
            self._mcp_session_provider = mcp_session_provider # Store the provider
            self.context_files = set()
            # Config might still be needed for non-MCP things, pass if necessary

        # ... (set_file_context, get_file_context remain the same) ...

        async def call_aider_tool(self, tool_name: str, params: dict) -> TaskResult:
            """Calls a tool on the external Aider MCP server."""
            log.debug(f"Attempting MCP call to tool '{tool_name}' with params: {params}")
            try:
                # Use the injected provider to get a session context manager
                async with self._mcp_session_provider.get_session() as session:
                    # Session should already be initialized by the provider's context manager
                    log.debug(f"MCP Session acquired. Calling tool: {tool_name}")
                    response_blocks = await session.call_tool(name=tool_name, arguments=params)
                    log.debug(f"MCP tool '{tool_name}' returned {len(response_blocks)} blocks.")

                    # Process response (assuming single TextContent block for simplicity)
                    if not response_blocks or not hasattr(response_blocks[0], 'text'):
                         log.error(f"Unexpected response format from MCP tool '{tool_name}': {response_blocks}")
                         return _create_failed_result_dict("output_format_failure", "Invalid response format from MCP server.")

                    raw_response = response_blocks[0].text
                    return self._parse_mcp_response(raw_response, tool_name)

            except NotImplementedError: # If using DummyMcpSessionProvider
                log.error("MCP session provider is not available (MCP components likely not installed).")
                return _create_failed_result_dict("dependency_error", "MCP session provider not available.")
            except json.JSONDecodeError as e:
                log.exception(f"Failed to parse JSON response from MCP tool '{tool_name}'. Raw: {raw_response}")
                return _create_failed_result_dict("output_format_failure", f"Failed to parse JSON response: {e}", {"raw_response": raw_response})
            except Exception as e: # Catch potential communication errors from call_tool or session mgmt
                log.exception(f"MCP communication error calling tool '{tool_name}'")
                return _create_failed_result_dict("connection_error", f"MCP communication error: {e}")

        def _parse_mcp_response(self, raw_response: str, tool_name: str) -> TaskResult:
             """Parses the JSON response string from an MCP tool call."""
             try:
                 data = json.loads(raw_response)
                 log.debug(f"Parsed MCP response for '{tool_name}': {data}")

                 # Specific handling based on tool might be needed, but general structure:
                 if data.get("success") is True: # Success case for aider_ai_code
                     content = data.get("diff", "") # Assuming diff is the main content
                     notes = {"success": True, **data} # Include full response in notes
                     return {"status": "COMPLETE", "content": content, "notes": notes}
                 elif "models" in data: # Success case for list_models (example)
                     content = json.dumps(data["models"]) # Return JSON string as content
                     notes = {"models": data["models"]} # Put list in notes
                     return {"status": "COMPLETE", "content": content, "notes": notes}
                 elif data.get("success") is False and "error" in data: # Explicit failure from tool
                     error_msg = data.get("error", "Unknown tool execution error")
                     log.warning(f"MCP tool '{tool_name}' indicated failure: {error_msg}. Details: {data}")
                     return _create_failed_result_dict("tool_execution_error", error_msg, data)
                 else: # Unknown response structure
                     log.error(f"Unknown MCP response structure for tool '{tool_name}': {data}")
                     return _create_failed_result_dict("output_format_failure", "Unknown response structure from MCP tool.", {"raw_response": data})

             except json.JSONDecodeError as e: # Should be caught earlier, but as safety
                 log.exception(f"Retry: Failed to parse JSON response from MCP tool '{tool_name}'. Raw: {raw_response}")
                 return _create_failed_result_dict("output_format_failure", f"Failed to parse JSON response: {e}", {"raw_response": raw_response})
             except Exception as e: # Catch unexpected errors during parsing
                 log.exception(f"Unexpected error parsing MCP response for tool '{tool_name}'. Data: {data if 'data' in locals() else 'N/A'}")
                 return _create_failed_result_dict("internal_error", f"Error processing MCP response: {e}")

        # ... (get_context_for_query remains the same) ...

    ```

3.  **Update `tests/aider_bridge/test_bridge.py`:**
    *   Remove all `@patch` decorators related to `MCP_AVAILABLE`, `stdio_client`, `ClientSession`, `StdioServerParameters`.
    *   Create mock objects for the `McpSessionProviderInterface` and the `McpClientSessionInterface`.
    *   Inject the mock provider into `AiderBridge` during setup.
    *   Configure the mock provider's `get_session` method to return a context manager yielding the mock session.
    *   Configure the mock session's `call_tool` method (return value, side effect).
    *   Assert calls on the mock provider and mock session.

    ```python
    # tests/aider_bridge/test_bridge.py
    import pytest
    import json
    from unittest.mock import MagicMock, AsyncMock
    from src.aider_bridge.bridge import AiderBridge # Import the refactored bridge
    # Import the interfaces (adjust path as needed)
    from src.mcp_providers import McpSessionProviderInterface, McpClientSessionInterface
    from src.system_prompts.schemas import TaskResult # Your result type

    # Your existing fixtures for memory/file manager mocks

    @pytest.fixture
    def mock_mcp_session():
        """Provides a mock MCP session instance."""
        # Use spec=McpClientSessionInterface for type safety if defined
        mock = AsyncMock(spec=McpClientSessionInterface)
        # Default: successful initialize and empty list from call_tool
        mock.initialize = AsyncMock()
        mock.call_tool = AsyncMock(return_value=[]) # Needs spec for TextContent if used
        return mock

    @pytest.fixture
    def mock_mcp_provider(mock_mcp_session):
        """Provides a mock MCP session provider."""
        mock = MagicMock(spec=McpSessionProviderInterface)
        # Configure get_session to return an async context manager yielding the mock session
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_mcp_session # Yield the session mock
        mock.get_session.return_value = mock_cm
        return mock

    @pytest.fixture
    def aider_bridge_instance(mock_memory_system_bridge, mock_file_access_manager_bridge, mock_mcp_provider):
        # Inject the MOCK provider
        return AiderBridge(mock_memory_system_bridge, mock_file_access_manager_bridge, mock_mcp_provider)

    # Helper to mock TextContent if needed (if _parse_mcp_response expects it)
    # Or adjust _parse_mcp_response to just take the string
    class MockTextContent:
        def __init__(self, text): self.text = text

    class TestAiderBridge:

        @pytest.mark.asyncio
        async def test_call_aider_tool_ai_code_success(self, aider_bridge_instance, mock_mcp_provider, mock_mcp_session):
            """Verify call_aider_tool uses provider/session and maps success."""
            # Arrange
            tool_name = "aider_ai_code"
            params = {"ai_coding_prompt": "Implement fibonacci", ...}
            mock_diff = "--- a/math.py\n..."
            server_response_json = json.dumps({"success": True, "diff": mock_diff})
            # Configure the mock session's call_tool return value
            mock_mcp_session.call_tool.return_value = [MockTextContent(server_response_json)]

            # Act
            result = await aider_bridge_instance.call_aider_tool(tool_name, params)

            # Assert
            mock_mcp_provider.get_session.assert_called_once() # Check provider was used
            # Check session methods were awaited
            mock_mcp_session.call_tool.assert_awaited_once_with(name=tool_name, arguments=params)

            assert result.get("status") == "COMPLETE"
            assert result.get("content") == mock_diff
            assert result.get("notes", {}).get("success") is True

        @pytest.mark.asyncio
        async def test_call_aider_tool_ai_code_failure(self, aider_bridge_instance, mock_mcp_provider, mock_mcp_session):
            """Verify call_aider_tool handles application error from tool."""
            # Arrange
            tool_name = "aider_ai_code"
            params = {"ai_coding_prompt": "Bad prompt", ...}
            error_msg = "Aider execution failed..."
            server_payload = {"success": False, "error": error_msg, "diff": "partial diff..."}
            server_response_json = json.dumps(server_payload)
            mock_mcp_session.call_tool.return_value = [MockTextContent(server_response_json)]

            # Act
            result = await aider_bridge_instance.call_aider_tool(tool_name, params)

            # Assert
            mock_mcp_provider.get_session.assert_called_once()
            mock_mcp_session.call_tool.assert_awaited_once_with(name=tool_name, arguments=params)

            assert result.get("status") == "FAILED"
            assert error_msg in result.get("content", "")
            assert result.get("notes", {}).get("error", {}).get("reason") == "tool_execution_error"
            assert result.get("notes", {}).get("error", {}).get("details", {}).get("error") == error_msg

        @pytest.mark.asyncio
        async def test_call_aider_tool_mcp_exception(self, aider_bridge_instance, mock_mcp_provider, mock_mcp_session):
            """Verify call_aider_tool handles communication exceptions."""
            # Arrange
            tool_name = "aider_ai_code"
            params = {...}
            mcp_exception = TimeoutError("MCP call timed out") # Simulate error from call_tool
            mock_mcp_session.call_tool.side_effect = mcp_exception

            # Act
            result = await aider_bridge_instance.call_aider_tool(tool_name, params)

            # Assert
            mock_mcp_provider.get_session.assert_called_once()
            mock_mcp_session.call_tool.assert_awaited_once_with(name=tool_name, arguments=params)

            assert result.get("status") == "FAILED"
            assert "MCP communication error" in result.get("content", "")
            assert "MCP call timed out" in result.get("content", "")
            assert result.get("notes", {}).get("error", {}).get("reason") == "connection_error"

        # ... Add tests for list_models, json_parse_error (by setting call_tool return value) ...
        # ... Tests for set_file_context, get_file_context, get_context_for_query remain unchanged ...

    ```

**2. Refactoring for `tests/test_main.py` (Anthropic Tools)**

*   **Problem:** Patching individual `anthropic_tools` functions (either at definition or usage) conflicts with other patches in the `app_components` fixture, causing `InvalidSpecError`.
*   **Refactoring Goal:** Stop `Application` from directly accessing `anthropic_tools` functions. Inject an object that provides these functionalities.

**Steps:**

1.  **Define Executor Class:** Create a class responsible for executing Anthropic-specific tools.
    ```python
    # src/tools/anthropic_executors.py (or similar location)
    from . import anthropic_tools # Import the original functions
    from ..handler.file_access import FileAccessManager # Dependency

    class AnthropicToolExecutors:
        def __init__(self, file_manager: FileAccessManager):
            self._file_manager = file_manager

        # Define methods that match the expected signature for tool registration
        # Option 1: Take params dict (simpler registration)
        def view(self, params: dict):
            # Delegate to the original function, passing the needed file_manager
            return anthropic_tools.view(self._file_manager, **params)

        def create(self, params: dict):
            return anthropic_tools.create(self._file_manager, **params)

        def str_replace(self, params: dict):
            return anthropic_tools.str_replace(self._file_manager, **params)

        def insert(self, params: dict):
            return anthropic_tools.insert(self._file_manager, **params)

        # Option 2: Keep original signature (more complex registration lambda)
        # def view(self, file_manager: FileAccessManager, **params):
        #     return anthropic_tools.view(file_manager, **params)
    ```

2.  **Refactor `Application`:**
    *   Import the new `AnthropicToolExecutors`.
    *   Instantiate it in `__init__`, passing the `FileAccessManager`.
    *   Modify `_register_anthropic_tools` to use methods from the `anthropic_executors` instance.

    ```python
    # src/main.py
    # ... other imports ...
    from .tools.anthropic_executors import AnthropicToolExecutors # Import the new class
    # REMOVE import src.tools.anthropic_tools if no longer directly needed

    class Application:
        def __init__(self, config: dict):
            # ... setup logging, base_path ...
            try:
                # Instantiate core components
                self.file_manager = FileAccessManager(base_path=self.base_path)
                self.memory_system = MemorySystem(config.get("memory_config", {}), self.file_manager)
                # Instantiate the NEW executor class
                self.anthropic_executors = AnthropicToolExecutors(self.file_manager)
                self.task_system = TaskSystem(config.get("task_config", {}), self.file_manager)
                self.system_executors = SystemExecutorFunctions(self.memory_system, self.file_manager)

                # Instantiate handler (might need file_manager, task_system etc.)
                self.passthrough_handler = PassthroughHandler(
                    config.get("handler_config", {}),
                    llm_config=config.get("llm_config", {}),
                    file_manager=self.file_manager,
                    task_system=self.task_system,
                    command_executor=CommandExecutor(base_path=self.base_path) # Example dependency
                )
                # ... more handler setup if needed ...

                # Dependency wiring
                self.memory_system.set_task_system(self.task_system) # If needed
                # self.memory_system.set_handler(self.passthrough_handler) # If needed
                self.task_system.set_handler(self.passthrough_handler) # Example wiring
                # Set memory system on handler/task_system if they need it
                if hasattr(self.passthrough_handler, 'set_memory_system'):
                    self.passthrough_handler.set_memory_system(self.memory_system)
                if hasattr(self.task_system, 'set_memory_system'):
                    self.task_system.set_memory_system(self.memory_system)


                # Initialize Aider components (using refactored bridge if done)
                self.aider_bridge = None
                self.aider_executors = None
                self._initialize_aider(config) # Defer aider init

                # Register tools
                self._register_system_tools()
                self._register_anthropic_tools() # Uses the new instance members
                self._register_aider_tools() # If aider init is successful

                # Finalize handler setup (e.g., determining active tools)
                active_tools = self._determine_active_tools()
                self.passthrough_handler.set_active_tool_definitions(active_tools)

                # Initialize agent last, passing tools from handler
                # The handler should now provide the correct registered executors
                self.passthrough_handler.initialize_agent()

            except Exception as e:
                log.exception("Error during Application initialization")
                raise ApplicationInitializationError(f"Failed to initialize Application: {e}") from e


        def _register_anthropic_tools(self):
            """Registers Anthropic-specific tools if the provider matches."""
            # Check provider AFTER handler is initialized
            if self.passthrough_handler.get_provider_identifier().startswith("anthropic:"):
                log.info("Registering Anthropic tools...")
                try:
                    # Define tool specs (should match function param names in AnthropicToolExecutors)
                    view_spec = {"name": "anthropic:view", "description": "View file content", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}, "line_start": {"type": "integer", "optional": True}, "line_end": {"type": "integer", "optional": True}}, "required": ["file_path"]}}
                    create_spec = {"name": "anthropic:create", "description": "Create or overwrite a file", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}, "overwrite": {"type": "boolean", "default": False}}, "required": ["file_path", "content"]}}
                    replace_spec = {"name": "anthropic:str_replace", "description": "Replace text in a file", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["file_path", "old_text", "new_text"]}}
                    insert_spec = {"name": "anthropic:insert", "description": "Insert text into a file", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}, "line": {"type": "integer", "optional": True}, "before_line": {"type": "integer", "optional": True}, "after_line": {"type": "integer", "optional": True}, "position": {"type": "integer", "optional": True}}, "required": ["file_path", "content"]}}

                    # Register methods directly from the instance
                    self.passthrough_handler.register_tool(view_spec, self.anthropic_executors.view)
                    self.passthrough_handler.register_tool(create_spec, self.anthropic_executors.create)
                    self.passthrough_handler.register_tool(replace_spec, self.anthropic_executors.str_replace)
                    self.passthrough_handler.register_tool(insert_spec, self.anthropic_executors.insert)
                except Exception as e:
                    log.exception("Failed to register Anthropic tools")
                    # Decide if this is a fatal error for init

        # ... rest of Application class (_register_system_tools, _initialize_aider etc.)
    ```

3.  **Update `tests/test_main.py`'s `app_components` fixture:**
    *   Remove the patches for `src.tools.anthropic_tools.<func>`.
    *   Add a patch for `src.main.AnthropicToolExecutors`.
    *   Yield the *methods* of the mocked `AnthropicToolExecutors` instance for tests to assert on.

    ```python
    # tests/test_main.py
    import pytest
    from unittest.mock import patch, MagicMock, AsyncMock
    # Don't need to import src.tools.anthropic_tools here anymore for patching

    AIDER_AVAILABLE_IMPORT_PATH = 'src.main.AIDER_AVAILABLE' # Ensure this is correct

    @pytest.fixture
    def app_components(tmp_path):
        """Provides mocked components for Application testing using autospec."""
        registered_tools_storage = {}
        tool_executors_storage = {}

        def mock_register_tool(self, tool_spec, executor_func):
            # ... (same as before) ...
            tool_name = tool_spec.get("name")
            if tool_name:
                registered_tools_storage[tool_name] = {"spec": tool_spec, "executor": executor_func}
                tool_executors_storage[tool_name] = executor_func
                return True
            return False

        # Patch classes, including the NEW AnthropicToolExecutors
        with patch('src.main.FileAccessManager', autospec=True) as MockFM, \
             patch('src.main.MemorySystem', autospec=True) as MockMemory, \
             patch('src.main.TaskSystem', autospec=True) as MockTask, \
             patch('src.main.PassthroughHandler', autospec=True) as MockHandler, \
             patch('src.main.GitRepositoryIndexer', autospec=True) as MockIndexer, \
             patch('src.main.SystemExecutorFunctions', autospec=True) as MockSysExecCls, \
             patch('src.handler.llm_interaction_manager.Agent', autospec=True) as MockPydanticAgent, \
             patch('src.main.AiderBridge', autospec=True) as MockAiderBridge, \
             patch('src.main.AiderExecutors', autospec=True) as MockAiderExec, \
             patch('src.main.AnthropicToolExecutors', autospec=True) as MockAnthropicExecCls: # Patch the executor CLASS

            # Get the mock instance that Application will create
            mock_anthropic_exec_instance = MockAnthropicExecCls.return_value

            # Configure mock handler instance
            mock_handler_instance = MockHandler.return_value
            mock_handler_instance.register_tool = MagicMock(side_effect=lambda spec, func: mock_register_tool(mock_handler_instance, spec, func))
            mock_handler_instance.get_provider_identifier.return_value = "mock_provider:default"
            mock_handler_instance.get_tools_for_agent.side_effect = lambda: list(tool_executors_storage.values())
            mock_handler_instance.set_active_tool_definitions = MagicMock()
            mock_handler_instance.file_manager = MockFM.return_value # Ensure handler has mock file manager

            # Configure mock LLM manager
            mock_llm_manager_instance = MagicMock()
            mock_llm_manager_instance.initialize_agent = MagicMock()
            mock_handler_instance.llm_manager = mock_llm_manager_instance

            # Configure MockTask instance methods
            mock_task_instance = MockTask.return_value
            mock_task_instance.set_handler = MagicMock()
            mock_task_instance.register_template = MagicMock()

            # Yield mocks, including the METHODS from the mocked Anthropic executor INSTANCE
            mocks = {
                "MockFM": MockFM, "MockMemory": MockMemory, "MockTask": MockTask,
                "MockHandler": MockHandler, "MockIndexer": MockIndexer,
                "MockSysExecCls": MockSysExecCls,
                # Provide the mock methods from the Anthropic executor instance:
                "mock_anthropic_view_func": mock_anthropic_exec_instance.view,
                "mock_anthropic_create_func": mock_anthropic_exec_instance.create,
                "mock_anthropic_replace_func": mock_anthropic_exec_instance.str_replace,
                "mock_anthropic_insert_func": mock_anthropic_exec_instance.insert,
                "MockPydanticAgent": MockPydanticAgent,
                "MockAiderBridge": MockAiderBridge,
                "MockAiderExec": MockAiderExec,
                "registered_tools_storage": registered_tools_storage,
                "tool_executors_storage": tool_executors_storage,
                "mock_handler_instance": mock_handler_instance,
                "mock_task_system_instance": mock_task_instance,
                "mock_memory_system_instance": MockMemory.return_value,
                "mock_llm_manager_instance": mock_llm_manager_instance,
                # Also provide the mock executor instance/class if needed
                "MockAnthropicExecCls": MockAnthropicExecCls,
                "mock_anthropic_exec_instance": mock_anthropic_exec_instance,
            }
            yield mocks
    ```
4.  **Update `tests/test_main.py` Tests:**
    *   Tests like `test_application_init_registers_anthropic_and_system_tools_for_anthropic_provider` should now assert calls on the yielded mock methods (e.g., `app_components["mock_anthropic_view_func"].assert_called_once_with(...)`). The crucial part is that the `InvalidSpecError` during *fixture setup* should be gone.

This DI approach fundamentally changes how dependencies are managed, making the code more modular and eliminating the need for the problematic patches that were causing test failures.
