import logging
import os
from typing import Any, Dict, List, Optional, Callable

# Import Phase 0 components
from src.handler.file_access import FileAccessManager
from src.handler import command_executor
from src.handler.file_context_manager import FileContextManager # Added import

# Import pydantic-ai (assuming it's installed)
try:
    from pydantic_ai import Agent
    from pydantic_ai.models import (
        OpenAIModel,
        AnthropicModel,
    )  # Add other models as needed

    # Add other potential model providers here if supported by pydantic-ai
    PYDANTIC_AI_AVAILABLE = True
except ImportError:
    # Define dummy types if import fails to satisfy type hints without crashing
    Agent = type("Agent", (object,), {})
    OpenAIModel = type("OpenAIModel", (object,), {})
    AnthropicModel = type("AnthropicModel", (object,), {})
    PYDANTIC_AI_AVAILABLE = False
    logging.warning(
        "pydantic-ai library not found. BaseHandler LLM features will be unavailable."
    )


# Forward declarations for type hinting cycles
# from src.task_system.task_system import TaskSystem
# from src.memory.memory_system import MemorySystem
# from src.system.models import TaskResult # Assuming TaskResult is defined


class BaseHandler:
    """
    Base class for handlers, providing core functionalities.
    """

    def __init__(
        self,
        task_system: Any,  # TaskSystem
        memory_system: Any,  # MemorySystem
        default_model_identifier: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initializes the base handler.

        Args:
            task_system: A valid TaskSystem instance.
            memory_system: A valid MemorySystem instance.
            default_model_identifier: Optional string identifying the pydantic-ai model (e.g., "openai:gpt-4o", "anthropic:claude-3-5-sonnet-latest").
            config: Optional dictionary for configuration settings (e.g., base_system_prompt, API keys).
        """
        self.task_system = task_system
        self.memory_system = memory_system
        self.config = config or {}
        self.default_model_identifier = default_model_identifier

        # Initialize Phase 0 dependencies
        # Assuming base_path for FileAccessManager comes from config or defaults to cwd
        self.file_manager = FileAccessManager(
            base_path=self.config.get("file_manager_base_path")
        )
        # Initialize FileContextManager
        self.file_context_manager = FileContextManager(
            memory_system=self.memory_system, file_manager=self.file_manager
        )

        # Initialize internal state
        self.tool_executors: Dict[str, Callable] = (
            {}
        )  # Key: tool name, Value: executor function
        self.registered_tools: Dict[str, Dict[str, Any]] = (
            {}
        )  # Key: tool name, Value: tool spec
        self.conversation_history: List[Dict[str, Any]] = (
            []
        )  # Placeholder for history management
        self.debug_mode: bool = False
        self.base_system_prompt: str = self.config.get(
            "base_system_prompt", "You are a helpful assistant."
        )

        # Initialize pydantic-ai Agent
        self.agent: Optional[Agent] = None
        if PYDANTIC_AI_AVAILABLE and self.default_model_identifier:
            try:
                self.agent = self._initialize_pydantic_ai_agent()
                logging.info(
                    f"pydantic-ai Agent initialized with model: {self.default_model_identifier}"
                )
            except Exception as e:
                logging.error(
                    f"Failed to initialize pydantic-ai Agent: {e}", exc_info=True
                )
                # Proceed without agent, core functionalities might still work
        elif not PYDANTIC_AI_AVAILABLE:
            logging.warning(
                "Cannot initialize pydantic-ai Agent: Library not installed."
            )
        elif not self.default_model_identifier:
            logging.warning(
                "Cannot initialize pydantic-ai Agent: No default_model_identifier provided."
            )

        logging.info("BaseHandler initialized.")

    def _initialize_pydantic_ai_agent(self) -> Optional[Agent]:
        """Helper to instantiate the pydantic-ai agent based on config."""
        if not PYDANTIC_AI_AVAILABLE or not self.default_model_identifier:
            return None

        model_provider, model_name = self.default_model_identifier.split(":", 1)
        api_key = None
        model_instance = None

        # Extract API keys from config or environment variables
        # Example: Prefers config['openai_api_key'] over OPENAI_API_KEY env var
        if model_provider == "openai":
            api_key = self.config.get(
                "openai_api_key", os.environ.get("OPENAI_API_KEY")
            )
            if not api_key:
                raise ValueError(
                    "OpenAI API key not found in config or environment variables."
                )
            if OpenAIModel:
                model_instance = OpenAIModel(api_key=api_key, model=model_name)
        elif model_provider == "anthropic":
            api_key = self.config.get(
                "anthropic_api_key", os.environ.get("ANTHROPIC_API_KEY")
            )
            if not api_key:
                raise ValueError(
                    "Anthropic API key not found in config or environment variables."
                )
            if AnthropicModel:
                model_instance = AnthropicModel(api_key=api_key, model=model_name)
        # Add other providers here (e.g., 'google', 'azure', etc.)
        else:
            raise ValueError(
                f"Unsupported pydantic-ai model provider: {model_provider}"
            )

        if not model_instance:
            raise ValueError(
                f"Could not create model instance for {self.default_model_identifier}. Check provider support and pydantic-ai installation."
            )

        # Instantiate Agent - tools will be added via register_tool later if needed dynamically,
        # or potentially the agent needs re-initialization if tools change.
        # For now, initialize without tools.
        # TODO: Clarify how tools are best managed with pydantic-ai Agent lifecycle.
        agent = Agent(model=model_instance, system_prompt=self.base_system_prompt)
        return agent

    def register_tool(self, tool_spec: Dict[str, Any], executor_func: Callable) -> bool:
        """
        Registers a tool specification and its executor function for LLM use.

        Args:
            tool_spec: Dictionary containing 'name', 'description', 'input_schema'.
            executor_func: Callable function implementing the tool's logic.

        Returns:
            True if registration is successful, False otherwise.
        """
        tool_name = tool_spec.get("name")
        if not tool_name:
            logging.error("Tool registration failed: 'name' missing in tool_spec.")
            return False

        if not callable(executor_func):
            logging.error(
                f"Tool registration failed for '{tool_name}': executor_func is not callable."
            )
            return False

        # Store for direct programmatic access (e.g., by SexpEvaluator)
        self.tool_executors[tool_name] = executor_func
        # Store spec for reference / potential agent re-initialization
        self.registered_tools[tool_name] = tool_spec
        logging.info(f"Stored executor and spec for tool: '{tool_name}'")

        # --- Deferred/Complex Part: Registering with the live pydantic-ai Agent ---
        # Dynamically registering tools with an already instantiated pydantic-ai Agent
        # can be complex. The typical pattern is to define tools with decorators
        # *before* Agent instantiation, or pass a list of tools during init.
        # For now, we log a warning and acknowledge this step is needed but complex.
        if self.agent:
            logging.warning(
                f"Tool '{tool_name}' spec/executor stored, but dynamic registration with the "
                "live pydantic-ai Agent instance is complex and currently NOT implemented. "
                "Agent may need re-initialization with all tools, or a dynamic registration "
                "mechanism needs to be developed."
            )
            # Placeholder: If pydantic-ai adds a dynamic registration method, call it here.
            # try:
            #     # Hypothetical future method:
            #     # adapted_tool = self._adapt_tool_for_pydantic_ai(tool_spec, executor_func)
            #     # self.agent.register_dynamic_tool(adapted_tool)
            #     # logging.info(f"Successfully registered '{tool_name}' with pydantic-ai agent (hypothetical).")
            #     pass # No actual registration call for now
            # except Exception as e:
            #     logging.error(f"Failed to dynamically register tool '{tool_name}' with pydantic-ai agent: {e}")
            #     # Decide if failure here should return False overall
        else:
            logging.warning(
                f"Tool '{tool_name}' spec/executor stored, but pydantic-ai agent is not available for registration."
            )

        return True  # Return True as we stored the spec/executor successfully

    def execute_file_path_command(self, command: str) -> List[str]:
        """
        Executes a shell command expected to output file paths and parses the result.

        Args:
            command: The shell command to execute.

        Returns:
            A list of absolute file paths extracted from the command's output.
        """
        if self.debug_mode:
            self.log_debug(f"Executing file path command: {command}")

        # Use default timeout from command_executor unless overridden in config
        timeout = self.config.get(
            "command_executor_timeout", command_executor.DEFAULT_TIMEOUT
        )
        # Use base_path from file_manager as cwd unless overridden in config
        cwd = self.config.get("command_executor_cwd", self.file_manager.base_path)

        result = command_executor.execute_command_safely(
            command, cwd=cwd, timeout=timeout
        )

        if self.debug_mode:
            self.log_debug(
                f"Command result: Success={result['success']}, ExitCode={result['exit_code']}, Output='{result['output'][:100]}...', Error='{result['error'][:100]}...'"
            )

        if result["success"]:
            file_paths = command_executor.parse_file_paths_from_output(result["output"])
            if self.debug_mode:
                self.log_debug(f"Parsed file paths: {file_paths}")
            return file_paths
        else:
            logging.error(
                f"Command execution failed (Exit Code: {result['exit_code']}): {command}. Error: {result['error']}"
            )
            return []

    def reset_conversation(self) -> None:
        """
        Resets the internal conversation history.
        """
        self.conversation_history = []
        logging.info("Conversation history reset.")
        # TODO: Check if the specific pydantic-ai Agent implementation requires explicit state reset.
        # Some agents might be stateless per call, others might maintain internal state.
        if self.agent:
            # Example: if self.agent has a reset method
            # self.agent.reset()
            logging.info(
                "pydantic-ai agent state reset (if applicable) needs verification."
            )

    def log_debug(self, message: str) -> None:
        """
        Logs a debug message if debug mode is enabled.

        Args:
            message: The message string to log.
        """
        if self.debug_mode:
            # Using standard logging for consistency, could also just print
            logging.debug(f"[DEBUG] {message}")

    def set_debug_mode(self, enabled: bool) -> None:
        """
        Enables or disables the internal debug logging flag.

        Args:
            enabled: Boolean value to enable/disable debug mode.
        """
        self.debug_mode = enabled
        status = "enabled" if enabled else "disabled"
        # Log the change using the logger itself
        logging.info(f"Debug mode {status}.")
        self.log_debug(
            "Debug logging is now active."
        )  # Log a message using the new state

        # TODO: Configure pydantic-ai agent instrumentation if debug mode is enabled
        if self.agent and PYDANTIC_AI_AVAILABLE:
            try:
                # Example: Check if agent has instrumentation methods
                if enabled:
                    # self.agent.instrument() # Hypothetical method
                    logging.debug(
                        "pydantic-ai agent instrumentation enabled (if applicable)."
                    )
                else:
                    # self.agent.remove_instrumentation() # Hypothetical method
                    logging.debug(
                        "pydantic-ai agent instrumentation disabled (if applicable)."
                    )
            except AttributeError:
                logging.warning(
                    "pydantic-ai agent does not support instrumentation methods."
                )
            except Exception as e:
                logging.error(
                    f"Error configuring pydantic-ai agent instrumentation: {e}"
                )

    # --- Start Phase 2, Set A: Behavior Structure ---
    # Placeholder for the core LLM interaction logic using the pydantic-ai agent
    def _execute_llm_call(
        self,
        prompt: str,
        system_prompt_override: Optional[str] = None,
        tools_override: Optional[List[Callable]] = None,
        output_type_override: Optional[type] = None,
    ) -> Any: # Should return TaskResult or similar structure
        """
        Internal method to execute a call to the configured pydantic-ai agent.
        (Implementation deferred to Phase 2, Set B)
        """
        logging.warning("_execute_llm_call called, but implementation is deferred.")
        # 1. Check if self.agent is available. If not, return error TaskResult.
        # 2. Prepare message history:
        #    - Get relevant messages from self.conversation_history.
        #    - Add the current `prompt` as the latest user message.
        # 3. Determine System Prompt:
        #    - Use `system_prompt_override` if provided, else use `self.base_system_prompt`.
        # 4. Determine Tools:
        #    - Use `tools_override` if provided.
        #    - Else, potentially adapt tools from `self.registered_tools` (complex part, see register_tool warning).
        # 5. Determine Output Type:
        #    - Use `output_type_override` if provided.
        #    - Else, default might be plain text or based on agent config.
        # 6. Build arguments for agent call:
        #    - `messages = prepared_message_history`
        #    - `system_prompt = determined_system_prompt`
        #    - `tools = determined_tools` (if any)
        #    - `output_type = determined_output_type` (if not default)
        # 7. Execute Agent Call:
        #    - Try:
        #        - `pydantic_ai_result = self.agent.run_sync(messages=messages, system_prompt=system_prompt, tools=tools, output_type=output_type)`
        #        - (Or use `run` for async if BaseHandler becomes async)
        #    - Catch exceptions from the agent (API errors, validation errors, etc.). Format into error TaskResult.
        # 8. Process Result:
        #    - Extract the main output (`pydantic_ai_result.output`).
        #    - Extract tool calls and results if handled by the agent.
        #    - Extract token usage, cost, etc. if provided by the result object.
        # 9. Update Conversation History:
        #    - Append the user prompt and the agent's final response (and potentially tool interactions) to `self.conversation_history`.
        # 10. Format and Return Result:
        #     - Create a TaskResult object.
        #     - Set `status` (COMPLETE or FAILED).
        #     - Set `content` to the agent's main output.
        #     - Add relevant details (token usage, tool calls) to `notes`.
        #     - Return the TaskResult.
        raise NotImplementedError("_execute_llm_call implementation deferred to Phase 2")
    # --- End Phase 2, Set A ---


    # Placeholder for potential private methods identified in Phase 1 clarification
    # These would likely be implemented in subclasses or later refactoring.
    def _build_system_prompt(
        self, template: Optional[str] = None, file_context: Optional[str] = None
    ) -> str:
        """Builds the system prompt (TBD - Phase 2)."""
        # Implementation deferred to Phase 2
        logging.warning("_build_system_prompt called, but implementation is deferred.")
        # --- Start Phase 2, Set A: Behavior Structure ---
        # 1. Start with `final_prompt = self.base_system_prompt`.
        # 2. If `template` (representing a template-specific system prompt part) is provided:
        #    - Append or prepend the `template` content to `final_prompt` (e.g., `final_prompt += "\n" + template`).
        # 3. If `file_context` is provided:
        #    - Append or prepend the `file_context` to `final_prompt` (e.g., `final_prompt += "\n\nFile Context:\n" + file_context`).
        # 4. Return `final_prompt`.
        # --- End Phase 2, Set A ---
        raise NotImplementedError(
            "_build_system_prompt implementation deferred to Phase 2"
        )

    def _get_relevant_files(self, query: str) -> List[str]:
        """Gets relevant files based on query (TBD - Phase 2)."""
        # Implementation deferred to Phase 2
        logging.warning("_get_relevant_files called, but implementation is deferred.")
        """Gets relevant files based on query (Delegated to FileContextManager)."""
        # Implementation deferred to Phase 2 - Now delegated
        logging.warning("_get_relevant_files called, delegating to FileContextManager.")
        return self.file_context_manager.get_relevant_files(query)

    def _create_file_context(self, file_paths: List[str]) -> str:
        """Creates context string from file paths (TBD - Phase 2)."""
        # Implementation deferred to Phase 2
        logging.warning("_create_file_context called, but implementation is deferred.")
        """Creates context string from file paths (Delegated to FileContextManager)."""
        # Implementation deferred to Phase 2 - Now delegated
        logging.warning("_create_file_context called, delegating to FileContextManager.")
        return self.file_context_manager.create_file_context(file_paths)

    def _execute_tool(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]: # Should return TaskResult
        """Executes a registered tool directly (TBD - Phase 2)."""
        # Implementation deferred to Phase 2
        logging.warning("_execute_tool called, but implementation is deferred.")
        # --- Start Phase 2, Set A: Behavior Structure ---
        # 1. Look up the executor function in `self.tool_executors`:
        #    - `executor_func = self.tool_executors.get(tool_name)`
        # 2. If `executor_func` is not found:
        #    - Log an error.
        #    - Return a FAILED TaskResult indicating the tool is not registered or found.
        # 3. Try to execute the function:
        #    - `result = executor_func(tool_input)` # Assuming executor takes input dict
        #    - (Note: Executor might return a TaskResult directly, or raw data that needs formatting)
        # 4. Catch exceptions during execution:
        #    - Log the error.
        #    - Return a FAILED TaskResult detailing the execution error.
        # 5. Format the result:
        #    - If the executor returned a raw value, wrap it in a COMPLETE TaskResult.
        #    - If it returned a TaskResult, return it directly.
        # 6. Return the TaskResult.
        # --- End Phase 2, Set A ---
        raise NotImplementedError("_execute_tool implementation deferred to Phase 2")
