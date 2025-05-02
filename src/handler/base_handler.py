import json
import logging
import os
import warnings
from typing import Any, Callable, Dict, List, Optional, Type

from src.handler import command_executor

# Import Phase 0 components
from src.handler.file_access import FileAccessManager
from src.handler.file_context_manager import FileContextManager
from src.handler.llm_interaction_manager import LLMInteractionManager

# Import shared types
from src.system.models import (
    TaskError,
    TaskResult,
)  # Import TaskFailureError for type hints

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
        self.active_tools: List[str] = []  # List of tool names to use in LLM calls
        self.active_tool_definitions: List[Dict[str, Any]] = []  # List of tool specs to pass to LLM calls
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
        if (
            hasattr(self, "llm_manager")
            and self.llm_manager
            and hasattr(self.llm_manager, "agent")
            and self.llm_manager.agent
        ):
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
            abs_paths = [
                os.path.abspath(os.path.join(cwd or os.getcwd(), p)) for p in file_paths
            ]
            # Filter for existence using FileAccessManager's resolved path logic
            existing_paths = []
            for p in abs_paths:
                try:
                    # Use file_manager's internal logic to check existence within its scope
                    resolved = self.file_manager._resolve_path(
                        p
                    )  # Use internal method carefully
                    if os.path.exists(resolved):  # Check existence of resolved path
                        existing_paths.append(
                            resolved
                        )  # Return the resolved, absolute path
                    elif self.debug_mode:
                        self.log_debug(
                            f"Path '{p}' (resolved to '{resolved}') does not exist or is outside base path."
                        )
                except ValueError:  # Path outside base path
                    if self.debug_mode:
                        self.log_debug(f"Path '{p}' is outside the allowed base path.")
                except Exception as e:  # Other errors
                    logging.warning(f"Error checking path existence for '{p}': {e}")

            if self.debug_mode:
                self.log_debug(
                    f"Filtered existing absolute file paths: {existing_paths}"
                )
            return existing_paths
        else:
            logging.error(
                f"Command execution failed (Exit Code: {result['exit_code']}): {command}. Error: {result['error']}"
            )
            return []

    def set_active_tool_definitions(self, tool_definitions: List[Dict[str, Any]]) -> bool:
        """
        Sets the list of active tool definitions to be passed directly to the LLM.
        
        Args:
            tool_definitions: List of tool specification dictionaries.
            
        Returns:
            True if successful, False otherwise.
        """
        self.log_debug(f"Setting active tool definitions: {[t.get('name', 'unnamed') for t in tool_definitions]}")
        
        # Store tool definitions
        self.active_tool_definitions = tool_definitions.copy()
        self.log_debug(f"Active tool definitions set to: {[t.get('name', 'unnamed') for t in self.active_tool_definitions]}")
        return True
    
    def set_active_tools(self, tool_names: List[str]) -> bool:
        """
        Sets the list of active tools to be used in LLM calls.
        
        DEPRECATED: Use set_active_tool_definitions() instead.

        Args:
            tool_names: List of tool names to activate. Must be previously registered.

        Returns:
            True if all tools were found and activated, False otherwise.
        """
        warnings.warn(
            "set_active_tools is deprecated. Use set_active_tool_definitions() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        self.log_debug(f"Setting active tools: {tool_names}")

        # Validate that all tool names are registered
        unknown_tools = [
            name for name in tool_names if name not in self.registered_tools
        ]
        if unknown_tools:
            logging.error(f"Cannot activate unknown tools: {unknown_tools}")
            return False

        # Set the active tools list
        self.active_tools = (
            tool_names.copy()
        )  # Create a copy to avoid external modifications
        self.log_debug(f"Active tools set to: {self.active_tools}")
        return True

    def get_provider_identifier(self) -> Optional[str]:
        """
        Returns the identifier of the current LLM provider.

        Returns:
            Optional string identifying the provider (e.g., "openai:gpt-4o") or None if not available.
        """
        if not self.llm_manager:
            logging.warning(
                "LLMInteractionManager is not available - cannot get provider identifier."
            )
            return None

        return self.llm_manager.get_provider_identifier()

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
        self.log_debug("Debug logging is now active.")

        # Pass debug state to LLMInteractionManager
        if self.llm_manager:
            self.llm_manager.set_debug_mode(enabled)

    def _execute_llm_call(
        self,
        prompt: str,
        system_prompt_override: Optional[str] = None,
        tools_override: Optional[
            List[Callable]
        ] = None,  # Or tool specs? Check pydantic-ai
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

        # Log full LLM payload for debugging
        try:
            payload_log = {
                "prompt": prompt,
                "system_prompt_override": system_prompt_override,
                "tools_override": tools_override,
                "output_type_override": str(output_type_override),
                "conversation_history": self.conversation_history,
            }
            with open("basehandler_llm_payload.log", "w") as _f:
                _f.write(json.dumps(payload_log, indent=2))
            logging.info(
                "BaseHandler: full LLM payload written to basehandler_llm_payload.log"
            )
        except Exception as _e:
            logging.error(f"BaseHandler: Failed to write LLM payload log: {_e}")
        if not self.llm_manager:
            logging.error(
                "LLMInteractionManager not initialized, cannot execute LLM call."
            )
            error_details: TaskError = {  # type: ignore # Trusting dict structure matches TaskError union
                "type": "TASK_FAILURE",
                "reason": "dependency_error",
                "message": "LLMInteractionManager not available.",
            }
            return TaskResult(
                status="FAILED",
                content="LLM Manager not initialized.",
                notes={"error": error_details},
            )

        # --- Prepare tools for the call with precedence logic ---
        current_tools = None

        # 1. Highest precedence: Explicit tools_override passed to this call
        if tools_override is not None:
            self.log_debug("Using explicitly provided tools_override for LLM call")
            current_tools = tools_override

        # 2. Second precedence: Active tools list if it's not empty
        elif self.active_tools:
            self.log_debug(f"Using active tools list for LLM call: {self.active_tools}")
            # Map tool names to executor functions
            tool_functions = []
            for tool_name in self.active_tools:
                executor = self.tool_executors.get(tool_name)
                if executor:
                    tool_functions.append(executor)
                else:
                    logging.warning(
                        f"Tool {tool_name} in active_tools but no executor found"
                    )
            current_tools = tool_functions

        # 3. Lowest precedence: No tools passed if neither above condition is met
        # (current_tools remains None)

        if current_tools:
            self.log_debug(f"Passing {len(current_tools)} tools to LLM call")
        else:
            self.log_debug("No tools will be passed to LLM call")

        # Store history *before* the call for accurate logging/debugging if needed
        history_before_call = list(self.conversation_history)

        # Delegate the call to the manager
        # Prepare kwargs for execute_call
        call_kwargs = {
            "prompt": prompt,
            "conversation_history": history_before_call,
            "system_prompt_override": system_prompt_override,
            "tools_override": current_tools,  # Always pass tools_override for compatibility with existing tests
            "output_type_override": output_type_override,
        }
            
        # Pass active tool definitions if available and tools_override is not specified
        if tools_override is None and self.active_tool_definitions:
            call_kwargs["active_tools"] = self.active_tool_definitions
            self.log_debug(f"Passing {len(self.active_tool_definitions)} active tool definitions to LLM call")
            
        # Execute the call
        manager_result = self.llm_manager.execute_call(**call_kwargs)

        logging.debug(f"LLM Manager Raw Result: {manager_result}")

        # Process the result from the manager
        # Fix: Use .get() for safer access
        if isinstance(manager_result, dict) and manager_result.get(
            "success"
        ):  # Check type and use get()
            logging.debug("  Processing LLM call as SUCCESS.")
            assistant_content = manager_result.get("content", "")
            usage_data = manager_result.get("usage")
            tool_calls = manager_result.get("tool_calls")

            # ... (rest of success path: logging, history update, tool call check, return TaskResult) ...
            self.log_debug(
                f"LLM call successful. Response: '{str(assistant_content)[:100]}...'"
            )
            self.conversation_history.append({"role": "user", "content": prompt})
            self.conversation_history.append(
                {"role": "assistant", "content": str(assistant_content)}
            )
            self.log_debug(
                f"Conversation history updated. New length: {len(self.conversation_history)}"
            )
            if tool_calls:
                logging.warning(
                    f"LLM agent returned tool calls, but handling is not implemented: {tool_calls}"
                )
            return TaskResult(
                status="COMPLETE",
                content=str(assistant_content),
                notes={"usage": usage_data} if usage_data else {},
            )

        else:
            # Handle failure or unexpected result structure
            logging.debug("  Processing LLM call as FAILURE.")
            error_message = "Unknown LLM interaction error."  # Default

            # Robust Error Message Extraction
            if isinstance(manager_result, dict):
                # 1. Check 'error' key (could be string or dict)
                extracted_error = manager_result.get("error")
                if extracted_error:
                    if (
                        isinstance(extracted_error, dict)
                        and "message" in extracted_error
                    ):
                        error_message = extracted_error["message"]
                    elif isinstance(extracted_error, str):
                        error_message = extracted_error
                # 2. If no message from 'error', check 'content' key
                elif "content" in manager_result and isinstance(
                    manager_result["content"], str
                ):
                    error_message = manager_result["content"]
                # 3. If still no message, check 'notes.error.message'
                elif "notes" in manager_result and isinstance(
                    manager_result["notes"], dict
                ):
                    notes_error = manager_result["notes"].get("error")
                    if isinstance(notes_error, dict) and "message" in notes_error:
                        error_message = notes_error["message"]
                    # Also check error_details in notes
                    elif "error_details" in manager_result["notes"] and isinstance(
                        manager_result["notes"]["error_details"], dict
                    ):
                        error_details_dict = manager_result["notes"]["error_details"]
                        if "message" in error_details_dict:
                            error_message = error_details_dict["message"]
            elif (
                hasattr(manager_result, "error") and manager_result.error
            ):  # Check object attribute
                error_message = str(manager_result.error)

            logging.error(
                f"LLM call failed or returned unexpected result: {error_message}"
            )
            # Use the extracted error_message when creating the TaskResult
            error_details: Dict[str, Any] = {
                "type": "TASK_FAILURE",
                "reason": "llm_error",
                "message": error_message,
            }
            return TaskResult(
                status="FAILED", content=error_message, notes={"error": error_details}
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
            final_prompt_parts.append(
                f"Relevant File Context:\n```\n{file_context}\n```"
            )

        final_prompt = "\n\n".join(final_prompt_parts).strip()
        self.log_debug(
            f"Built system prompt (length {len(final_prompt)}): '{final_prompt[:200]}...'"
        )
        return final_prompt

    def _get_relevant_files(self, query: str) -> List[str]:
        """Gets relevant files based on query (Delegated to FileContextManager)."""
        self.log_debug(f"Getting relevant files for query: '{query[:100]}...'")
        return self.file_context_manager.get_relevant_files(query)

    def _create_file_context(self, file_paths: List[str]) -> str:
        """Creates context string from file paths (Delegated to FileContextManager)."""
        self.log_debug(f"Creating file context for paths: {file_paths}")
        return self.file_context_manager.create_file_context(file_paths)

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> TaskResult:
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
            error_details: TaskError = {  # type: ignore
                "type": "TASK_FAILURE",
                "reason": "template_not_found",  # Closest reason? Or add 'tool_not_found'?
                "message": error_message,
            }
            return TaskResult(
                status="FAILED", content=error_message, notes={"error": error_details}
            )

        try:
            # Execute the tool function
            result = executor_func(tool_input)
            self.log_debug(
                f"Tool '{tool_name}' executed successfully. Result: {result}"
            )

            # Check if the result is already a TaskResult dictionary
            # (More robust check might be needed depending on TaskResult structure)
            if isinstance(result, TaskResult):
                # If it's already a TaskResult object, return it directly
                return result
            elif (
                isinstance(result, dict) and "status" in result and "content" in result
            ):
                # Attempt to reconstruct TaskResult if it looks like one
                try:
                    # Ensure notes is a dict, handle potential missing keys gracefully
                    notes = result.get("notes", {})
                    if not isinstance(notes, dict):
                        notes = {"original_notes": notes}  # Wrap if not a dict

                    # Reconstruct TaskResult, handling potential missing optional fields
                    return TaskResult(
                        status=result.get(
                            "status", "COMPLETE"
                        ),  # Default status if missing
                        content=result.get("content", ""),  # Default content if missing
                        criteria=result.get("criteria"),
                        parsedContent=result.get("parsedContent"),
                        notes=notes,
                    )
                except Exception as parse_exc:
                    logging.warning(
                        f"Tool '{tool_name}' returned a dict, but failed to parse as TaskResult: {parse_exc}. Wrapping raw result."
                    )
                    # Fallback to wrapping raw result if parsing fails
                    return TaskResult(
                        status="COMPLETE",
                        content=str(result),
                        notes={"tool_output": result},
                    )

            else:
                # Wrap raw result in a TaskResult
                return TaskResult(
                    status="COMPLETE",
                    content=str(result),
                    notes={"tool_output": result},
                )

        except Exception as e:
            error_message = f"Error executing tool '{tool_name}': {e}"
            logging.error(error_message, exc_info=True)
            error_details: TaskError = {  # type: ignore
                "type": "TASK_FAILURE",
                "reason": "tool_execution_error",
                "message": error_message,
                "details": {"tool_name": tool_name, "input": tool_input},
            }
            return TaskResult(
                status="FAILED", content=error_message, notes={"error": error_details}
            )
