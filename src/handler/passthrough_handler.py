"""
Passthrough Handler implementation.
Handles raw text queries, orchestrates context retrieval, LLM calls,
and tool registration using BaseHandler functionalities.
"""

import logging
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
                    # Optional: Add 'cwd' or 'timeout' if needed by the tool interface
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

            logging.info(f"Executing command via tool: {command}")
            try:
                # Call the safe executor function from the command_executor module
                exec_result = command_executor.execute_command_safely(command)

                if exec_result.get("success"):
                    # Parse file paths if command succeeded
                    output = exec_result.get("output", "")
                    file_paths = command_executor.parse_file_paths_from_output(output)
                    logging.info(f"Command succeeded. Parsed paths: {file_paths}")
                    # Return successful TaskResult with the list of paths as content
                    return TaskResult(status="COMPLETE", content=str(file_paths), notes={"file_paths": file_paths}).model_dump(exclude_none=True) # Content could be JSON list?
                else:
                    # Command failed or was unsafe
                    error_msg = exec_result.get("error", "Command execution failed.")
                    logging.warning(f"Command execution failed or unsafe: {error_msg}")
                    error_details = TaskFailureError(type="TASK_FAILURE", reason="tool_execution_error", message=f"Command execution failed: {error_msg}")
                    return TaskResult(status="FAILED", content=error_msg, notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)

            except Exception as e:
                logging.exception(f"Unexpected error in command execution wrapper: {e}")
                error_details = TaskFailureError(type="TASK_FAILURE", reason="unexpected_error", message=f"Unexpected error executing command: {e}")
                return TaskResult(status="FAILED", content=f"Unexpected error: {e}", notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)

        # Register using the BaseHandler's method
        logging.debug(f"Registering tool: {tool_name}")
        return self.register_tool(tool_spec, _execute_command_wrapper)


    def handle_query(self, query: str) -> TaskResult:
        """
        Handles a raw text query from the user in passthrough mode.

        Retrieves context, builds prompts, invokes the LLM via BaseHandler,
        and updates conversation history.

        Args:
            query: The user's input string.

        Returns:
            A TaskResult object containing the outcome.
        """
        logging.info(f"Handling passthrough query: {query[:50]}...")

        # 1. Update History (User Turn) - Do this early
        # BaseHandler._execute_llm_call handles history internally now.
        # self.add_message_to_history("user", query) # No longer needed here

        try:
            # 2. Retrieve Relevant Files & Create Context String
            # Delegates to FileContextManager via BaseHandler methods
            logging.debug("Getting relevant files...")
            relevant_files = self._get_relevant_files(query) # Method inherited/delegated
            logging.debug(f"Relevant files found: {relevant_files}")

            logging.debug("Creating file context string...")
            file_context_str = self._create_file_context(relevant_files) # Method inherited/delegated
            if file_context_str:
                 logging.debug(f"File context string created (length: {len(file_context_str)}).")
            else:
                 logging.debug("No file context string created.")

            # 3. Build System Prompt
            # Uses BaseHandler method, incorporating base prompt and file context
            final_system_prompt = self._build_system_prompt(file_context=file_context_str)
            logging.debug(f"Final system prompt generated (length: {len(final_system_prompt)}).")

            # 4. Execute LLM Call (Delegates to LLMInteractionManager via BaseHandler)
            # This method now handles adding user query and assistant response to history on success.
            logging.debug("Executing LLM call via BaseHandler...")
            result: TaskResult = self._execute_llm_call(
                prompt=query,
                system_prompt_override=final_system_prompt
                # Tools are implicitly available via registration if LLM manager handles it
            )
            logging.info(f"Passthrough query handled. Result status: {result.status}")
            # Add relevant files to notes for transparency
            result.notes["relevant_files"] = relevant_files
            return result

        except Exception as e:
            # Catch unexpected errors during context retrieval or LLM call preparation
            logging.exception(f"Unexpected error during handle_query: {e}")
            # Create a FAILED TaskResult
            error_details = TaskFailureError(
                type="TASK_FAILURE",
                reason="unexpected_error",
                message=f"Failed to handle passthrough query: {e}"
            )
            # Manually add user query to history if LLM call wasn't reached/failed early
            # Check if history already contains the user query before adding
            if not self.conversation_history or self.conversation_history[-1].get("content") != query:
                 self.add_message_to_history("user", query)

            return TaskResult(
                status="FAILED",
                content=f"Error handling query: {e}",
                notes={"error": error_details.model_dump(exclude_none=True)}
            )

    def reset_conversation(self) -> None:
        """
        Resets the conversation state, including history and active subtask ID.
        """
        logging.info("Resetting PassthroughHandler conversation state.")
        super().reset_conversation() # Calls BaseHandler reset (clears history, resets LLM manager state)
        self.active_subtask_id = None
        logging.debug("PassthroughHandler state reset.")

    # Inherited methods used:
    # - _get_relevant_files (delegates to FileContextManager)
    # - _create_file_context (delegates to FileContextManager)
    # - _build_system_prompt
    # - _execute_llm_call (delegates to LLMInteractionManager, handles history)
    # - register_tool
    # - add_message_to_history (used by _execute_llm_call)
