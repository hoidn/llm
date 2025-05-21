"""
Passthrough Handler implementation.
Handles raw text queries, orchestrates context retrieval, LLM calls,
and tool registration using BaseHandler functionalities.
"""

import logging
import os
import shlex
from typing import Any, Dict, List, Optional

# Base class and dependencies
from src.handler.base_handler import BaseHandler
from src.task_system.task_system import TaskSystem
from src.memory.memory_system import MemorySystem
from src.handler import command_executor # Import the module itself
from src.system.models import TaskResult, TaskFailureError, TaskFailureReason

class PassthroughHandler(BaseHandler):
    """
    Handles raw text queries in passthrough mode.

    Inherits from BaseHandler and utilizes its core functionalities for
    LLM interaction, file context management, and tool registration.

    Implements the contract defined in src/handler/passthrough_handler_IDL.md.
    """

    def __init__(
        self,
        task_system: TaskSystem,
        memory_system: MemorySystem,
        default_model_identifier: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initializes the PassthroughHandler.

        Args:
            task_system: A valid TaskSystem instance.
            memory_system: A valid MemorySystem instance.
            default_model_identifier: Optional string identifying the pydantic-ai model.
            config: Optional configuration dictionary (e.g., base_system_prompt).
        """
        super().__init__(
            task_system=task_system,
            memory_system=memory_system,
            default_model_identifier=default_model_identifier,
            config=config
        )
        logging.info("PassthroughHandler initialized.")

        # Append passthrough-specific instructions if needed (or handle in config)
        # self.base_system_prompt += "\nYou are in passthrough mode."
        # logging.debug(f"PassthroughHandler base system prompt: {self.base_system_prompt}")

        # Initialize passthrough-specific state
        self.active_subtask_id: Optional[str] = None # As per IDL

        # Register built-in tools required for passthrough mode
        if not self.register_command_execution_tool():
             # Log a warning or raise if registration fails? Log for now.
             logging.warning("Failed to register built-in command execution tool for PassthroughHandler.")


    def register_command_execution_tool(self) -> bool:
        """
        Registers the built-in 'executeFilePathCommand' tool.

        Defines the tool specification and a wrapper function that calls
        the command_executor functions safely.

        Returns:
            True if registration was successful, False otherwise.
        """
        tool_name = "executeFilePathCommand"
        tool_spec = {
            "name": tool_name,
            "description": "Executes a shell command expected to output file paths and returns the list of existing, absolute file paths found.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute."
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Optional working directory for command execution."
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Optional timeout in seconds for command execution."
                    }
                },
                "required": ["command"]
            }
            # Pydantic-ai might prefer Pydantic models for schema, adapt if necessary
        }

        def _execute_command_wrapper(tool_input: Dict[str, Any]) -> Dict[str, Any]:
            """Wrapper function for the command execution tool."""
            command = tool_input.get("command")
            if not command:
                error_details = TaskFailureError(type="TASK_FAILURE", reason="input_validation_failure", message="Missing 'command' input for executeFilePathCommand.")
                return TaskResult(status="FAILED", content="Missing 'command' input.", notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)

            # Get optional parameters
            cwd = tool_input.get("cwd")
            timeout = tool_input.get("timeout")
            
            # Validate base path if cwd is provided
            if cwd and not os.path.isdir(cwd):
                error_details = TaskFailureError(type="TASK_FAILURE", reason="input_validation_failure", message=f"Invalid working directory: {cwd}")
                return TaskResult(status="FAILED", content=f"Invalid working directory: {cwd}", notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)
            
            # Use file_manager's base path as default cwd if not specified
            if not cwd and hasattr(self, 'file_manager') and hasattr(self.file_manager, 'base_path'):
                cwd = self.file_manager.base_path

            logging.info(f"Executing command via tool: {command}")
            try:
                # Call the safe executor function from the command_executor module
                exec_result = command_executor.execute_command_safely(command, cwd=cwd, timeout=timeout)

                if exec_result.get("success"):
                    # Parse file paths if command succeeded
                    stdout_content = exec_result.get("stdout", "") # Use stdout
                    file_paths = command_executor.parse_file_paths_from_output(stdout_content, base_dir=cwd)
                    logging.info(f"Command succeeded. Parsed paths: {file_paths}")
                    # Return successful TaskResult with the list of paths as content
                    return TaskResult(status="COMPLETE", content=str(file_paths), notes={"file_paths": file_paths}).model_dump(exclude_none=True)
                else:
                    # Command failed or was unsafe
                    # Prioritize error_message, then stderr, then default
                    error_msg = exec_result.get("error_message") or exec_result.get("stderr") or "Command execution failed."
                    logging.warning(f"Command execution failed or unsafe: {error_msg}")
                    # Determine reason based on error message content
                    reason: TaskFailureReason = "tool_execution_error"
                    if "UnsafeCommandDetected" in error_msg:
                        reason = "input_validation_failure"
                    elif "TimeoutExpired" in error_msg:
                        reason = "execution_timeout"
                    elif "Command not found" in error_msg:
                        reason = "tool_execution_error" # Or a more specific one if desired

                    error_details = TaskFailureError(type="TASK_FAILURE", reason=reason, message=error_msg)
                    # Include full exec_result in notes for debugging
                    notes = {"error": error_details.model_dump(exclude_none=True), "command_result": exec_result}
                    return TaskResult(status="FAILED", content=error_msg, notes=notes).model_dump(exclude_none=True)

            except Exception as e:
                logging.exception(f"Unexpected error in command execution wrapper: {e}")
                error_details = TaskFailureError(type="TASK_FAILURE", reason="unexpected_error", message=f"Unexpected error executing command: {e}")
                return TaskResult(status="FAILED", content=f"Unexpected error: {e}", notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)

        # Register using the BaseHandler's method
        logging.debug(f"Registering tool: {tool_name}")
        result = self.register_tool(tool_spec, _execute_command_wrapper)
        
        # Also register the list files tool
        if result:
            return self.register_list_files_tool()
        return result


    async def handle_query(self, query: str) -> TaskResult:
        """
        Handles a raw text query from the user in passthrough mode.

        Orchestrates context priming via BaseHandler, (placeholder) Aider command checks,
        subtask creation or continuation, and LLM interaction.

        Args:
            query: The user's input string.

        Returns:
            A TaskResult object containing the outcome.
            Returns a FAILED TaskResult if context priming fails.
        """
        logging.info(f"Handling passthrough query: {query[:50]}...")

        try:
            # 1. Prime Data Context
            logging.debug(f"Priming data context for query: {query[:50]}...")
            priming_successful = await self.prime_data_context(query=query) # BaseHandler method

            if not priming_successful:
                logging.warning(f"Data context priming failed for query: {query[:50]}. Returning FAILED TaskResult.")
                error_details = TaskFailureError(
                    type="TASK_FAILURE",
                    reason="context_priming_failure",
                    message="Failed to prepare necessary data context to handle the query."
                )
                # Note: User query is not added to history if priming fails.
                return TaskResult(
                    status="FAILED",
                    content="Error preparing data context for the query.",
                    notes={"error": error_details.model_dump(exclude_none=True)}
                )
            logging.debug("Data context primed successfully.")

            # 2. Aider Command Checks (Placeholder for this phase)
            #    For this phase, no explicit Aider command parsing here.
            #    Subtask logic might select an Aider task template based on query/config.
            #    Example:
            #    if query.startswith("/aider"):
            #        # Potentially set a flag or task_name hint for _create_new_subtask
            #        pass


            # 3. Subtask Logic
            #    PassthroughHandler is single-turn for now, so active_subtask_id won't persist across calls.
            #    It's reset in reset_conversation and not set by _create_new_subtask.
            #    Thus, we will primarily call _create_new_subtask.
            #    If active_subtask_id was somehow set, _continue_subtask would be called.

            current_active_subtask_id = self.active_subtask_id # Store before potential modification by helpers
            
            if current_active_subtask_id is None:
                logging.debug("No active subtask. Creating a new one.")
                result = await self._create_new_subtask(query=query)
            else:
                # This branch is less likely to be hit with current single-turn design
                logging.debug(f"Continuing active subtask: {current_active_subtask_id}")
                result = await self._continue_subtask(query=query) # Will reset active_subtask_id

            logging.info(f"Passthrough query handled. Result status: {result.status}")

            # Populate notes with relevant files from context
            if self.data_context and self.data_context.items:
                # Ensure item.id exists and is not None before accessing
                relevant_ids = [
                    item.id for item in self.data_context.items 
                    if hasattr(item, 'id') and item.id is not None # <<< MODIFIED CONDITION
                ]
                result.notes["relevant_files_from_context"] = relevant_ids
            else:
                result.notes["relevant_files_from_context"] = []
            
            return result

        except Exception as e:
            logging.exception(f"Unexpected error during handle_query: {e}")
            error_details = TaskFailureError(
                type="TASK_FAILURE",
                reason="unexpected_error",
                message=f"Failed to handle passthrough query: {str(e)}" # Use str(e)
            )
            return TaskResult(
                status="FAILED",
                content=f"Error handling query: {str(e)}", # Use str(e)
                notes={"error": error_details.model_dump(exclude_none=True)}
            )

    async def _create_new_subtask(self, query: str) -> TaskResult:
        """
        Creates and executes a new subtask based on the user query.

        Finds a suitable template, builds the system prompt using the
        already primed data_context, and invokes the LLM.

        Args:
            query: The user's input string for the new subtask.

        Returns:
            A TaskResult from the LLM call.
        """
        logging.debug(f"Creating new subtask for query: {query[:50]}...")

        # 1. Template Finding (Simplified for Passthrough)
        #    Uses a configurable default template name.
        template_name = self.config.get("passthrough_default_template_name", "generic_llm_task")
        logging.debug(f"Attempting to find template: '{template_name}'")
        template = self.task_system.find_template(template_name)

        if not template:
            logging.error(f"Template '{template_name}' not found for new subtask.")
            error_details = TaskFailureError(
                type="TASK_FAILURE",
                reason="template_not_found",
                message=f"Required template '{template_name}' not found."
            )
            return TaskResult(
                status="FAILED",
                content=f"Configuration error: Template {template_name} not found.",
                notes={"error": error_details.model_dump(exclude_none=True)}
            )
        logging.debug(f"Using template: '{template_name}'")
        
        template_specific_instructions: Optional[str] = template.get("instructions") # Or "system_prompt_template", "body", etc.

        # 2. Build final system prompt (BaseHandler._build_system_prompt uses self.data_context)
        final_system_prompt = self._build_system_prompt(
            template_specific_instructions=template_specific_instructions 
        )
        logging.debug(f"System prompt for new subtask (length: {len(final_system_prompt)}). Preview: {final_system_prompt[:200]}...")

        # 3. Execute LLM call
        logging.debug("Executing LLM call for new subtask...")
        result = await self._execute_llm_call( # BaseHandler method
            prompt=query,
            system_prompt_override=final_system_prompt
            # Tools are implicitly available via BaseHandler's registered tools
        )
        
        # 4. Active Subtask ID Management (Single-turn: not setting it)
        # self.active_subtask_id = new_id_if_multi_turn

        return result

    async def _continue_subtask(self, query: str) -> TaskResult:
        """
        Continues an existing active subtask with the new user query.
        For current single-turn PassthroughHandler, this behaves like creating a new task
        and ensures active_subtask_id is cleared.

        Args:
            query: The user's input string to continue the subtask.

        Returns:
            A TaskResult from the LLM call.
        """
        logging.debug(f"Continuing subtask {self.active_subtask_id} with query: {query[:50]}...")
        logging.warning("PassthroughHandler is single-turn; _continue_subtask called, will behave like a new task and clear active_subtask_id.")

        # For single-turn, effectively same as _create_new_subtask logic
        template_name = self.config.get("passthrough_default_template_name", "generic_llm_task")
        logging.debug(f"Attempting to find template: '{template_name}' for continuation (as new task).")
        template = self.task_system.find_template(template_name)

        if not template:
            logging.error(f"Template '{template_name}' not found for continuation.")
            error_details = TaskFailureError(
                type="TASK_FAILURE",
                reason="template_not_found",
                message=f"Required template '{template_name}' not found."
            )
            return TaskResult(
                status="FAILED",
                content=f"Configuration error: Template {template_name} not found.",
                notes={"error": error_details.model_dump(exclude_none=True)}
            )
        logging.debug(f"Using template: '{template_name}' for continuation.")

        template_specific_instructions: Optional[str] = template.get("instructions")

        final_system_prompt = self._build_system_prompt(
            template_specific_instructions=template_specific_instructions
        )
        logging.debug(f"System prompt for continuing subtask (length: {len(final_system_prompt)}). Preview: {final_system_prompt[:200]}...")

        result = await self._execute_llm_call( # BaseHandler method
            prompt=query,
            system_prompt_override=final_system_prompt
        )
        
        # Ensure active_subtask_id is cleared as it's single-turn.
        self.active_subtask_id = None 
        logging.debug("Active subtask ID cleared after continuation.")

        return result

    def reset_conversation(self) -> None:
        """
        Resets the conversation state.

        Delegates to BaseHandler.reset_conversation() to clear conversation history
        and data context, and resets PassthroughHandler-specific state like
        the active subtask ID.
        """
        logging.info("Resetting PassthroughHandler conversation state.")
        super().reset_conversation() # This now calls BaseHandler's version
        self.active_subtask_id = None
        logging.debug("PassthroughHandler state reset.")

    # Inherited methods used:
    # - _create_file_context (delegates to FileContextManager)
    # - _build_system_prompt
    # - _execute_llm_call (delegates to LLMInteractionManager, handles history)
    # - register_tool
    # - add_message_to_history (used by _execute_llm_call)
    def register_list_files_tool(self) -> bool:
        """
        Registers the built-in 'listFiles' tool for securely listing files.
        
        Returns:
            True if registration was successful, False otherwise.
        """
        tool_name = "listFiles"
        tool_spec = {
            "name": tool_name,
            "description": "Securely lists files in a directory using safe commands like 'ls' or 'find'.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "The directory to list files from. Defaults to current directory if not specified."
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Optional pattern to filter files (e.g., '*.py' for Python files)."
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list files recursively. Defaults to false."
                    }
                }
            }
        }
        
        def _list_files_wrapper(tool_input: Dict[str, Any]) -> Dict[str, Any]:
            """Wrapper function for the list files tool."""
            directory = tool_input.get("directory", ".")
            pattern = tool_input.get("pattern", "")
            recursive = tool_input.get("recursive", False)
            
            # Validate and resolve the directory path
            try:
                if hasattr(self, 'file_manager') and hasattr(self.file_manager, '_resolve_path'):
                    # Use file_manager to resolve and validate the path
                    resolved_dir = self.file_manager._resolve_path(directory)
                    if not os.path.isdir(resolved_dir):
                        raise ValueError(f"Not a valid directory: {directory}")
                else:
                    # Fallback if file_manager not available
                    resolved_dir = os.path.abspath(directory)
                    if not os.path.isdir(resolved_dir):
                        raise ValueError(f"Not a valid directory: {directory}")
            except ValueError as e:
                error_details = TaskFailureError(type="TASK_FAILURE", reason="input_validation_failure", message=str(e))
                return TaskResult(status="FAILED", content=str(e), notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)
            
            # Construct a safe list command based on inputs
            command = ""
            if recursive:
                if pattern:
                    # Use find with pattern
                    command = f"find {shlex.quote(resolved_dir)} -type f -name {shlex.quote(pattern)}"
                else:
                    # Use find without pattern
                    command = f"find {shlex.quote(resolved_dir)} -type f"
            else:
                if pattern:
                    # Use ls with pattern
                    command = f"ls -1 {shlex.quote(resolved_dir)}/{shlex.quote(pattern)}"
                else:
                    # Simple ls
                    command = f"ls -1 {shlex.quote(resolved_dir)}"
            
            # Verify this is a safe list command
            if not command_executor.is_safe_list_command(command):
                error_details = TaskFailureError(type="TASK_FAILURE", reason="security_violation", message="Unsafe list command detected.")
                return TaskResult(status="FAILED", content="Unsafe list command detected.", notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)
            
            logging.info(f"Executing list files command: {command}")
            try:
                # Execute the command
                exec_result = command_executor.execute_command_safely(command, cwd=None, timeout=None)
                
                if exec_result.get("success"):
                    # Parse file paths from output
                    output = exec_result.get("output", "")
                    file_paths = command_executor.parse_file_paths_from_output(output, base_dir=resolved_dir)
                    
                    # Filter paths to ensure they're within the base directory
                    safe_paths = []
                    for path in file_paths:
                        try:
                            if hasattr(self, 'file_manager') and hasattr(self.file_manager, '_is_path_safe'):
                                if self.file_manager._is_path_safe(path):
                                    safe_paths.append(path)
                            else:
                                # Simple check if file_manager not available
                                if os.path.commonpath([resolved_dir, path]) == resolved_dir:
                                    safe_paths.append(path)
                        except ValueError:
                            # commonpath raises ValueError if paths are on different drives
                            continue
                    
                    return TaskResult(
                        status="COMPLETE", 
                        content=str(safe_paths), 
                        notes={
                            "file_paths": safe_paths,
                            "directory": resolved_dir,
                            "pattern": pattern,
                            "recursive": recursive
                        }
                    ).model_dump(exclude_none=True)
                else:
                    # Command failed
                    error_msg = exec_result.get("error", "List files command failed.")
                    logging.warning(f"List files command failed: {error_msg}")
                    error_details = TaskFailureError(type="TASK_FAILURE", reason="tool_execution_error", message=f"List files command failed: {error_msg}")
                    return TaskResult(status="FAILED", content=error_msg, notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)
                    
            except Exception as e:
                logging.exception(f"Unexpected error in list files wrapper: {e}")
                error_details = TaskFailureError(type="TASK_FAILURE", reason="unexpected_error", message=f"Unexpected error listing files: {e}")
                return TaskResult(status="FAILED", content=f"Unexpected error: {e}", notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)
        
        # Register using the BaseHandler's method
        logging.debug(f"Registering tool: {tool_name}")
        return self.register_tool(tool_spec, _list_files_wrapper)
