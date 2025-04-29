import logging
import os
from typing import Any, Dict, List, Optional, Callable, Type

# Import Phase 0 components
from src.handler.file_access import FileAccessManager
from src.handler import command_executor
from src.handler.file_context_manager import FileContextManager
from src.handler.llm_interaction_manager import LLMInteractionManager

# Import shared types
from src.system.models import TaskResult, TaskError # Assuming TaskResult is defined here

# Forward declarations for type hinting cycles
# from src.task_system.task_system import TaskSystem
# from src.memory.memory_system import MemorySystem


class BaseHandler:
    """
    Base class for handlers, providing core functionalities.

    Implements the contract defined in src/handler/base_handler_IDL.md.
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
        )  # Stores {"role": "user/assistant", "content": ...} dicts
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
        # This remains complex. Tools might need to be passed per-call via _execute_llm_call
        # using the stored specs/executors, or the agent might need re-initialization.
        # Check more safely if llm_manager and its agent attribute exist
        if hasattr(self, 'llm_manager') and self.llm_manager and hasattr(self.llm_manager, 'agent') and self.llm_manager.agent:
            logging.warning(
                f"Tool '{tool_name}' spec/executor stored. Dynamic registration with the live "
                "pydantic-ai Agent is complex. Tools may need to be passed explicitly during LLM calls."
            )
        else:
            logging.warning(
                f"Tool '{tool_name}' spec/executor stored, but LLMInteractionManager or its agent is not available."
            )

        return True

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
            # Ensure paths are absolute relative to the execution CWD
            abs_paths = [os.path.abspath(os.path.join(cwd or os.getcwd(), p)) for p in file_paths]
            # Filter for existence using FileAccessManager's resolved path logic
            existing_paths = []
            for p in abs_paths:
                try:
                    # Use file_manager's internal logic to check existence within its scope
                    resolved = self.file_manager._resolve_path(p) # Use internal method carefully
                    if os.path.exists(resolved): # Check existence of resolved path
                         existing_paths.append(resolved) # Return the resolved, absolute path
                    elif self.debug_mode:
                         self.log_debug(f"Path '{p}' (resolved to '{resolved}') does not exist or is outside base path.")
                except ValueError: # Path outside base path
                     if self.debug_mode:
                         self.log_debug(f"Path '{p}' is outside the allowed base path.")
                except Exception as e: # Other errors
                     logging.warning(f"Error checking path existence for '{p}': {e}")

            if self.debug_mode:
                self.log_debug(f"Filtered existing absolute file paths: {existing_paths}")
            return existing_paths
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
        # LLMInteractionManager is stateless per call, no reset needed there.

    def log_debug(self, message: str) -> None:
        """
        Logs a debug message if debug mode is enabled.

        Args:
            message: The message string to log.
        """
        if self.debug_mode:
            logging.debug(f"[DEBUG] {message}")

    def set_debug_mode(self, enabled: bool) -> None:
        """
        Enables or disables the internal debug logging flag.

        Args:
            enabled: Boolean value to enable/disable debug mode.
        """
        self.debug_mode = enabled
        status = "enabled" if enabled else "disabled"
        logging.info(f"Debug mode {status}.")
        self.log_debug(
            "Debug logging is now active."
        )

        # Pass debug state to LLMInteractionManager
        if self.llm_manager:
            self.llm_manager.set_debug_mode(enabled)

    def _execute_llm_call(
        self,
        prompt: str,
        system_prompt_override: Optional[str] = None,
        tools_override: Optional[List[Callable]] = None, # Or tool specs? Check pydantic-ai
        output_type_override: Optional[Type] = None,
    ) -> TaskResult:
        """
        Internal method to execute a call via the LLMInteractionManager and update history.

        Args:
            prompt: The user's input prompt.
            system_prompt_override: Optional override for the system prompt.
            tools_override: Optional override for tools available to the LLM.
            output_type_override: Optional override for the expected output structure.

        Returns:
            A TaskResult object representing the outcome.
        """
        self.log_debug(f"Executing LLM call for prompt: '{prompt[:100]}...'")
        if not self.llm_manager:
            logging.error("LLMInteractionManager not initialized, cannot execute LLM call.")
            error_details: TaskError = { # type: ignore # Trusting dict structure matches TaskError union
                "type": "TASK_FAILURE",
                "reason": "dependency_error",
                "message": "LLMInteractionManager not available.",
            }
            return TaskResult(status="FAILED", content="LLM Manager not initialized.", notes={"error": error_details})

        # --- Prepare tools for the call if needed ---
        # This is where dynamic tool provision could happen.
        # If tools_override is not provided, maybe pass self.registered_tools?
        # The format needed by pydantic-ai (specs vs functions) is crucial here.
        # For now, we pass tools_override directly as received.
        current_tools = tools_override
        # Example: If pydantic-ai needs functions, map registered specs to executors
        # if not tools_override and self.registered_tools:
        #     current_tools = list(self.tool_executors.values()) # Simplistic example

        # Store history *before* the call for accurate logging/debugging if needed
        history_before_call = list(self.conversation_history)

        # Delegate the call to the manager
        manager_result = self.llm_manager.execute_call(
            prompt=prompt,
            conversation_history=history_before_call, # Pass current history
            system_prompt_override=system_prompt_override,
            tools_override=current_tools, # Pass potentially prepared tools
            output_type_override=output_type_override,
        )

        # Process the result from the manager
        if manager_result["success"]:
            assistant_content = manager_result.get("content", "")
            usage_data = manager_result.get("usage")
            tool_calls = manager_result.get("tool_calls") # TODO: Handle tool calls if needed

            self.log_debug(f"LLM call successful. Response: '{str(assistant_content)[:100]}...'")

            # Update conversation history *after* successful call
            self.conversation_history.append({"role": "user", "content": prompt})
            # Ensure assistant content is stored as string
            self.conversation_history.append({"role": "assistant", "content": str(assistant_content)})
            self.log_debug(f"Conversation history updated. New length: {len(self.conversation_history)}")

            # TODO: Process tool_calls if the agent returned any. This might involve
            # calling _execute_tool and potentially making another LLM call with the results.
            # This simple implementation assumes no tool calls or handles them elsewhere.
            if tool_calls:
                 logging.warning(f"LLM agent returned tool calls, but handling is not implemented in _execute_llm_call: {tool_calls}")


            # Return success TaskResult
            return TaskResult(
                status="COMPLETE",
                content=str(assistant_content), # Ensure content is string
                notes={"usage": usage_data} if usage_data else {}
            )
        else:
            # Handle failure
            error_message = manager_result.get("error", "Unknown LLM interaction error.")
            logging.error(f"LLM call failed: {error_message}")
            # Do NOT update history on failure
            error_details: TaskError = { # type: ignore
                "type": "TASK_FAILURE",
                "reason": "llm_error",
                "message": error_message,
            }
            return TaskResult(
                status="FAILED",
                content=error_message,
                notes={"error": error_details}
            )

    def _build_system_prompt(
        self, template: Optional[str] = None, file_context: Optional[str] = None
    ) -> str:
        """
        Builds the complete system prompt for an LLM call.

        Args:
            template: Optional string containing template-specific instructions.
            file_context: Optional string containing context from relevant files.

        Returns:
            The final system prompt string.
        """
        final_prompt_parts = [self.base_system_prompt]

        if template:
            final_prompt_parts.append(template)

        if file_context:
            # **Fix 3: Append context block without leading newline**
            final_prompt_parts.append(f"Relevant File Context:\n```\n{file_context}\n```")

        final_prompt = "\n\n".join(final_prompt_parts).strip()
        self.log_debug(f"Built system prompt (length {len(final_prompt)}): '{final_prompt[:200]}...'")
        return final_prompt

    def _get_relevant_files(self, query: str) -> List[str]:
        """Gets relevant files based on query (Delegated to FileContextManager)."""
        self.log_debug(f"Getting relevant files for query: '{query[:100]}...'")
        return self.file_context_manager.get_relevant_files(query)

    def _create_file_context(self, file_paths: List[str]) -> str:
        """Creates context string from file paths (Delegated to FileContextManager)."""
        self.log_debug(f"Creating file context for paths: {file_paths}")
        return self.file_context_manager.create_file_context(file_paths)

    def _execute_tool(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> TaskResult:
        """
        Executes a registered tool directly by name.

        Args:
            tool_name: The name of the tool to execute.
            tool_input: Dictionary containing the arguments for the tool.

        Returns:
            A TaskResult object representing the outcome of the tool execution.
        """
        self.log_debug(f"Executing tool '{tool_name}' with input: {tool_input}")
        executor_func = self.tool_executors.get(tool_name)

        if not executor_func:
            error_message = f"Tool '{tool_name}' not found in registered executors."
            logging.error(error_message)
            error_details: TaskError = { # type: ignore
                "type": "TASK_FAILURE",
                "reason": "template_not_found", # Closest reason? Or add 'tool_not_found'?
                "message": error_message,
            }
            return TaskResult(status="FAILED", content=error_message, notes={"error": error_details})

        try:
            # Execute the tool function
            result = executor_func(tool_input)
            self.log_debug(f"Tool '{tool_name}' executed successfully. Result: {result}")

            # Check if the result is already a TaskResult dictionary
            # (More robust check might be needed depending on TaskResult structure)
            if isinstance(result, TaskResult):
                 # If it's already a TaskResult object, return it directly
                 return result
            elif isinstance(result, dict) and "status" in result and "content" in result:
                # Attempt to reconstruct TaskResult if it looks like one
                try:
                    # Ensure notes is a dict, handle potential missing keys gracefully
                    notes = result.get("notes", {})
                    if not isinstance(notes, dict):
                        notes = {"original_notes": notes} # Wrap if not a dict

                    # Reconstruct TaskResult, handling potential missing optional fields
                    return TaskResult(
                        status=result.get("status", "COMPLETE"), # Default status if missing
                        content=result.get("content", ""), # Default content if missing
                        criteria=result.get("criteria"),
                        parsedContent=result.get("parsedContent"),
                        notes=notes
                    )
                except Exception as parse_exc:
                     logging.warning(f"Tool '{tool_name}' returned a dict, but failed to parse as TaskResult: {parse_exc}. Wrapping raw result.")
                     # Fallback to wrapping raw result if parsing fails
                     return TaskResult(status="COMPLETE", content=str(result), notes={"tool_output": result})

            else:
                # Wrap raw result in a TaskResult
                return TaskResult(status="COMPLETE", content=str(result), notes={"tool_output": result})

        except Exception as e:
            error_message = f"Error executing tool '{tool_name}': {e}"
            logging.error(error_message, exc_info=True)
            error_details: TaskError = { # type: ignore
                "type": "TASK_FAILURE",
                "reason": "tool_execution_error",
                "message": error_message,
                "details": {"tool_name": tool_name, "input": tool_input}
            }
            return TaskResult(status="FAILED", content=error_message, notes={"error": error_details})
