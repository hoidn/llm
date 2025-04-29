import logging
import os
from typing import Any, Dict, List, Optional, Callable

# Import Phase 0 components
from src.handler.file_access import FileAccessManager
from src.handler import command_executor
from src.handler.file_context_manager import FileContextManager
from src.handler.llm_interaction_manager import LLMInteractionManager # Added import


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

        # Initialize LLMInteractionManager
        self.llm_manager = LLMInteractionManager(
            default_model_identifier=self.default_model_identifier,
            config=self.config,
        )

        logging.info("BaseHandler initialized.")

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
        # TODO: Determine how tool registration interacts with LLMInteractionManager.
        # Does the manager need to be re-initialized or have a registration method?
        if self.llm_manager and self.llm_manager.agent:
            logging.warning(
                f"Tool '{tool_name}' spec/executor stored, but dynamic registration with the "
                "LLMInteractionManager's agent instance is complex and currently NOT implemented. "
                "Manager/Agent may need re-initialization or a dynamic registration mechanism."
            )
        else:
            logging.warning(
                f"Tool '{tool_name}' spec/executor stored, but LLMInteractionManager or its agent is not available for registration."
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
        # LLMInteractionManager currently appears stateless per call, no reset needed there.
        # If manager becomes stateful, add: self.llm_manager.reset_state()

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

        # Pass debug state to LLMInteractionManager
        if self.llm_manager:
            self.llm_manager.set_debug_mode(enabled)

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
        Internal method to execute a call via the LLMInteractionManager.
        (Implementation deferred to Phase 2, Set B - Now Delegated)
        """
        logging.debug("Delegating LLM call to LLMInteractionManager.")
        if not self.llm_manager:
            logging.error("LLMInteractionManager not initialized, cannot execute LLM call.")
            # Return error TaskResult
            raise NotImplementedError("LLM Manager not available - error TaskResult return needed")

        # Delegate the call, passing necessary context
        # Note: The manager executes the call, but BaseHandler updates history
        try:
            result = self.llm_manager.execute_call(
                prompt=prompt,
                conversation_history=self.conversation_history, # Pass current history
                system_prompt_override=system_prompt_override,
                tools_override=tools_override,
                output_type_override=output_type_override,
            )

            # TODO: Process the result from the manager (which should be TaskResult-like)
            # TODO: Update self.conversation_history based on the interaction (prompt + result.content)
            # Example (needs refinement based on actual result structure):
            # if result and result.status == "COMPLETE": # Assuming TaskResult structure
            #     self.conversation_history.append({"role": "user", "content": prompt})
            #     self.conversation_history.append({"role": "assistant", "content": result.content})
            #     logging.debug("Conversation history updated after successful LLM call.")

            return result # Return the result from the manager

        except NotImplementedError as nie:
             # Re-raise deferred implementation errors from the manager for now
             logging.error(f"LLM call execution deferred in LLMInteractionManager: {nie}")
             raise nie
        except Exception as e:
            logging.error(f"Error executing LLM call via manager: {e}", exc_info=True)
            # Return error TaskResult
            raise NotImplementedError("LLM call error handling - error TaskResult return needed")

    # --- End Phase 2, Set B ---


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
