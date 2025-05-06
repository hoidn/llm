import json
import logging
import os
import warnings # Ensure imported
from typing import Any, Callable, Dict, List, Optional, Type, Union

# Import pydantic-ai directly
import pydantic_ai

from src.handler import command_executor

# Import Phase 0 components
from src.handler.file_access import FileAccessManager
from src.handler.file_context_manager import FileContextManager
from src.handler.llm_interaction_manager import LLMInteractionManager

# Import shared types
from src.system.models import (
    TaskError,
    TaskResult,
)  # Import TaskResult for type hints

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
        self.active_tools: List[str] = []  # List of tool names to use in LLM calls (DEPRECATED)
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

    def get_tools_for_agent(self) -> List[Callable]:
        """
        Retrieves the registered tool executor functions required by the Agent constructor.
        """
        logging.debug(f"Retrieving tool executors for Agent initialization: {list(self.tool_executors.keys())}")
        return list(self.tool_executors.values())

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
        ) # ADDED WARNING
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
        tools_override: Optional[List[Callable]] = None, # Explicitly list of callables
        output_type_override: Optional[Type] = None,
        model_override: Optional[str] = None, # ADDED PARAMETER
    ) -> TaskResult:
        """
        Internal method to execute a call via the LLMInteractionManager and update history.
        """
        # Import specific message types for pydantic-ai
        try:
            # Import the specific class needed for assistant messages, not the Union alias
            from pydantic_ai.messages import ModelResponse
            PydanticMessagesAvailable = True
            logging.info("Successfully imported ModelResponse from pydantic_ai.messages.")
        except ImportError:
            logging.error("Failed to import ModelResponse from pydantic_ai.messages.", exc_info=True)
            PydanticMessagesAvailable = False
            # Create a placeholder if import fails
            class ModelResponse:
                def __init__(self, content=""):
                    logging.error("!!! Using Dummy ModelResponse fallback class !!!")
                    self.content = content

        self.log_debug(f"Executing LLM call for prompt: '{prompt[:100]}...'")
        if model_override:
            self.log_debug(f"  with model override: {model_override}")

        # Log full LLM payload for debugging
        try:
            payload_log = {
                "prompt": prompt,
                "system_prompt_override": system_prompt_override,
                "tools_override": [t.__name__ if hasattr(t, '__name__') else str(t) for t in tools_override] if tools_override else None, # Log names
                "output_type_override": str(output_type_override),
                "conversation_history": self.conversation_history,
                "active_tool_definitions": self.active_tool_definitions, # Log active defs
                "model_override": model_override, # Log override
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

        # --- Prepare tools correctly ---
        executors_for_agent: Optional[List[Callable]] = None
        definitions_for_agent: Optional[List[Dict[str, Any]]] = None

        if tools_override is not None:
            # Highest precedence: Explicit tools_override (must be callables)
            self.log_debug("Using explicitly provided tools_override (executors) for LLM call")
            executors_for_agent = tools_override
            definitions_for_agent = None # Assume manager doesn't need specs if executors are passed
        elif self.active_tool_definitions:
            # Second precedence: Use active_tool_definitions
            self.log_debug(f"Using active tool definitions ({len(self.active_tool_definitions)}) for LLM call")
            definitions_for_agent = self.active_tool_definitions
            # Look up the corresponding executors
            executors_found: List[Callable] = []
            missing_executors = []
            for spec in definitions_for_agent:
                tool_name = spec.get("name")
                executor = self.tool_executors.get(tool_name) if tool_name else None
                if executor:
                    executors_found.append(executor)
                elif tool_name:
                    missing_executors.append(tool_name)

            if missing_executors:
                logging.warning(
                    f"Executor(s) not found for active tool definition(s): {missing_executors}. "
                    "These tools will not be passed to the agent."
                )
            executors_for_agent = executors_found # Pass only the executors found
        else:
            # Lowest precedence: No tools active or specified
            self.log_debug("No tools_override or active_tool_definitions provided. No tools passed to agent.")
            executors_for_agent = None # Explicitly None
            definitions_for_agent = None # Explicitly None

        if executors_for_agent:
            self.log_debug(f"Passing {len(executors_for_agent)} tool executors to LLM manager")
        if definitions_for_agent:
             self.log_debug(f"Passing {len(definitions_for_agent)} tool definitions to LLM manager")
        # --- End Prepare tools ---

        # Store history *before* the call
        history_dicts_before_call = list(self.conversation_history)

        # --- START DIAGNOSTIC PRINT STATEMENTS ---
        print("\n--- DEBUG MARKER: ENTERING _execute_llm_call ---", flush=True)
        print(f"--- DEBUG MARKER: Prompt (start): {prompt[:100]}...", flush=True)
        print(f"--- DEBUG MARKER: History length before loop: {len(self.conversation_history)}", flush=True) # Check history passed in effectively

        # Check the crucial variable right before the loop where it's used
        print(f"--- DEBUG MARKER: PydanticMessagesAvailable = {PydanticMessagesAvailable}", flush=True)
        print(f"--- DEBUG MARKER: Type of ModelResponse = {type(ModelResponse)}", flush=True)
        print(f"--- DEBUG MARKER: Value of ModelResponse = {ModelResponse!r}", flush=True)
        from typing import Union
        is_union = ModelResponse is Union
        print(f"--- DEBUG MARKER: Is ModelResponse typing.Union? {is_union}", flush=True)
        print("--- DEBUG MARKER: BEFORE History Conversion Loop ---", flush=True)
        # --- END DIAGNOSTIC PRINT STATEMENTS ---

        # --- START MOVED INTROSPECTION LOGGING ---
        logging.debug(f"--- Before History Conversion Loop ---")
        logging.debug(f"ModelResponse points to: {ModelResponse!r}")
        logging.debug(f"Type of ModelResponse: {type(ModelResponse)}")
        # Union already imported above
        logging.debug(f"Is 'ModelResponse' the same object as typing.Union? {is_union}")
        
        # Check module origin
        if hasattr(ModelResponse, '__module__'):
            logging.debug(f"Module of 'ModelResponse': {ModelResponse.__module__}")
        
        # Try to get more info about the object
        logging.debug(f"Dir of 'ModelResponse': {dir(ModelResponse)[:10]}...")
        
        # Check if we can access the original ModelMessage directly
        try:
            import pydantic_ai.messages
            logging.debug(f"Direct import of pydantic_ai.messages.ModelMessage: {pydantic_ai.messages.ModelMessage!r}")
            logging.debug(f"Is ModelResponse same as ModelMessage? {pydantic_ai.messages.ModelMessage is ModelResponse}")
        except (ImportError, AttributeError) as e:
            logging.debug(f"Error accessing direct import: {e}")
        # --- END MOVED INTROSPECTION LOGGING ---

        # --- Convert History to Objects ---
        message_objects_for_agent = [] # Will hold PydanticModelMessage objects
        
        if PydanticMessagesAvailable:
            for msg_dict in history_dicts_before_call:
                role = msg_dict.get("role")
                content = msg_dict.get("content", "") # Default to empty string if missing

                # --- START: Ensure content is always string for ModelMessage ---
                # Convert potential Pydantic models/JSON strings in history to simple strings
                # before creating the ModelMessage object.
                if role == "assistant" and not isinstance(content, str):
                    # Example: If content might be a Pydantic model or dict
                    if hasattr(content, 'model_dump_json'):
                        try:
                            content_str = content.model_dump_json()
                        except Exception:
                            content_str = str(content) # Fallback
                    elif isinstance(content, dict):
                        try:
                            content_str = json.dumps(content)
                        except Exception:
                             content_str = str(content) # Fallback
                    else:
                        content_str = str(content) # General fallback
                    content = content_str # Update content variable
                # --- END: Ensure content is always string for ModelMessage ---

                # Only include assistant messages in the history objects
                # User messages are handled by the prompt parameter
                if role == "assistant":
                    # Use the directly imported concrete class instead of the Union alias
                    message_objects_for_agent.append(ModelResponse(content=content)) # content is now guaranteed string
                elif role == "user":
                    # Skip user messages - they're handled by the prompt parameter
                    pass
                else:
                    logging.warning(f"Unsupported role '{role}' found in history, skipping.")
                    continue # Skip unknown roles

            logging.debug(f"Converted history to {len(message_objects_for_agent)} pydantic-ai message objects.")
        else:
            logging.error("Cannot convert history to ModelMessage objects: pydantic_ai.messages not available")
            # Create empty list - the LLM manager will need to handle this case
        # --- End History Conversion ---
        
        # Delegate the call to the manager
        call_kwargs = {
            "prompt": prompt,
            "conversation_history": message_objects_for_agent, # Pass the CONVERTED list of objects
            "system_prompt_override": system_prompt_override,
            "tools_override": executors_for_agent, # Pass resolved executors
            "output_type_override": output_type_override,
            "active_tools": definitions_for_agent, # Pass resolved definitions
            "model_override": model_override, # PASS THE OVERRIDE
        }

        # --- Add the detailed logging right before the call ---
        logging.debug(f"------->>> Preparing to call run_sync for model: {self.llm_manager.get_provider_identifier() or model_override}") # Use actual model if possible
        logging.debug(f"------->>> Prompt Type: {type(prompt)}")
        logging.debug(f"------->>> Prompt Content (first 500 chars): {prompt[:500]}")
        # Log the OBJECTS this time
        history_repr = "\n".join([repr(msg) for msg in message_objects_for_agent])
        logging.debug(f"------->>> Run Kwargs History (Objects):\n{history_repr}")
        logging.debug(f"------->>> Run Kwargs System Prompt: {call_kwargs.get('system_prompt_override')}")
        logging.debug(f"------->>> Run Kwargs Tools: {call_kwargs.get('tools_override')}") 
        logging.debug(f"------->>> Run Kwargs Output Type: {call_kwargs.get('output_type_override')}")
        logging.debug(f"------->>> Full Run Kwargs (excluding history objects): { {k: v for k, v in call_kwargs.items() if k != 'conversation_history'} }")
        # --- End detailed logging ---

        manager_result = self.llm_manager.execute_call(**call_kwargs)

        # Process the result from the manager
        logging.debug(f"LLM Manager Raw Result: {manager_result}")

        # Fix: Use .get() for safer access
        if isinstance(manager_result, dict) and manager_result.get(
            "success"
        ):  # Check type and use get()
            logging.debug("  Processing LLM call as SUCCESS.")
            assistant_content = manager_result.get("content", "")
            usage_data = manager_result.get("usage")
            tool_calls = manager_result.get("tool_calls")
            parsed_content = manager_result.get("parsed_content") # Get parsed content if available

            self.log_debug(
                f"LLM call successful. Response: '{str(assistant_content)[:100]}...'"
            )
            # Update history correctly - ADD DICTIONARIES
            self.conversation_history.append({"role": "user", "content": prompt})
            # Ensure assistant content added is a string
            assistant_content_str = str(assistant_content) if assistant_content is not None else ""
            # Store as dictionary in the conversation history
            self.conversation_history.append(
                {"role": "assistant", "content": assistant_content_str}
            )
            self.log_debug(
                f"Conversation history updated. New length: {len(self.conversation_history)}"
            )
            if tool_calls:
                logging.warning(
                    f"LLM agent returned tool calls, but handling is not implemented: {tool_calls}"
                )
            # Create TaskResult object, including parsedContent
            return TaskResult(
                status="COMPLETE",
                content=assistant_content_str,
                parsedContent=parsed_content, # Add parsed content here
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
