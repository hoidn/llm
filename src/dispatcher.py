from typing import Dict, List, Any, Optional
import logging

# Import necessary components and types (adjust paths if needed)
# Use BaseHandler for type hinting, actual instance will be passed in
from handler.base_handler import BaseHandler
from task_system.task_system import TaskSystem
from task_system.ast_nodes import SubtaskRequest # Ensure this type exists or create it
from system.errors import TaskError, create_task_failure, format_error_result, UNEXPECTED_ERROR, INPUT_VALIDATION_FAILURE

# Define TaskResult type hint (or import if defined elsewhere)
TaskResult = Dict[str, Any]


def execute_programmatic_task(
    identifier: str,
    params: Dict[str, Any],
    flags: Dict[str, bool], # For future flags like --use-history
    handler_instance: BaseHandler, # Pass the actual Handler instance
    task_system_instance: TaskSystem, # Pass the actual TaskSystem instance
    optional_history_str: Optional[str] = None # For Phase 3
) -> TaskResult:
    """
    Routes a programmatic task request to the appropriate executor.

    Args:
        identifier: The task identifier string (e.g., "type:subtype" or "tool_name").
        params: Dictionary of parameters provided for the task.
        flags: Dictionary of boolean flags provided (e.g., {"use_history": True}).
        handler_instance: The instantiated Handler component.
        task_system_instance: The instantiated TaskSystem component.
        optional_history_str: Formatted string of recent chat history (Phase 3).

    Returns:
        A TaskResult dictionary representing the outcome.
    """
    logging.info(f"Dispatcher received request for identifier: {identifier}")
    logging.debug(f"Params: {params}, Flags: {flags}")

    try:
        # --- Routing Logic ---
        target_executor = None
        is_direct_tool = False

        # 1. Check Handler's Direct Tools first
        #    These are Python functions registered for programmatic execution.
        if hasattr(handler_instance, 'direct_tool_executors') and identifier in handler_instance.direct_tool_executors:
            target_executor = handler_instance.direct_tool_executors.get(identifier)
            if target_executor:
                is_direct_tool = True
                logging.info(f"Identifier '{identifier}' maps to a Direct Tool (Python function).")
        # TODO: Phase 3 - Consider checking LLM-registered tools (self.registered_tools) here too?

        # 2. If not a Direct Tool, check TaskSystem Templates
        if not is_direct_tool:
            # Identifiers for TaskSystem are expected to be "type:subtype"
            if ':' not in identifier:
                 logging.warning(f"Identifier '{identifier}' is not a Direct Tool and lacks ':' for TaskSystem lookup.")
                 # Fall through to the "Not Found" case below
            else:
                template_definition = task_system_instance.find_template(identifier)
                if template_definition:
                    target_executor = task_system_instance # Target the TaskSystem itself
                    logging.info(f"Identifier '{identifier}' maps to a TaskSystem Template.")

        # 3. Handle "Not Found" if no target was identified
        if target_executor is None:
            logging.warning(f"Identifier '{identifier}' not found in Handler tools or TaskSystem templates.")
            raise create_task_failure(
                message=f"Task identifier '{identifier}' not found.",
                reason=INPUT_VALIDATION_FAILURE,
                details={"identifier": identifier}
            )

        # --- Execution Logic (Steps 5 & 6) ---
        if is_direct_tool:
            # Step 5: Call Direct Tool Path
            logging.debug(f"Executing Direct Tool: {identifier}")
            # Note: The executor function itself is responsible for detailed param validation
            # Direct tools might expect specific argument structures, not just a dict.
            # This needs refinement based on how tools are registered/called.
            # For now, assume they accept a dictionary.
            raw_result = target_executor(params) # Assuming tool takes params dict

            # Wrap raw result into TaskResult
            result: TaskResult
            # If the tool returns a dict that looks like a TaskResult, use it directly
            if isinstance(raw_result, dict) and "status" in raw_result and "content" in raw_result:
                result = raw_result
                # Ensure notes exist
                if "notes" not in result:
                    result["notes"] = {}
            else:
                 # Basic string conversion for other types
                result = {
                    "status": "COMPLETE", # Assume success unless executor raises error
                    "content": str(raw_result),
                    "notes": {}
                }
            # Add execution path note
            result["notes"]["execution_path"] = "direct_tool"

        else:
            # Step 6: Call Subtask Template Path
            logging.debug(f"Executing Subtask Template via TaskSystem: {identifier}")
            # Create SubtaskRequest
            # Ensure SubtaskRequest class is defined/imported correctly
            # NOTE: History context is deferred to Phase 3
            task_type, task_subtype = identifier.split(':', 1)
            subtask_request = SubtaskRequest(
                type=task_type,
                subtype=task_subtype,
                inputs=params,
                # Pass file_paths if 'file_context' is in params, otherwise empty list
                file_paths=params.get("file_context") if isinstance(params.get("file_context"), list) else []
            )
            # Call the new TaskSystem method
            result = task_system_instance.execute_subtask_directly(subtask_request)
            # Add execution path note
            if "notes" not in result: result["notes"] = {}
            result["notes"]["execution_path"] = "subtask_template"


        logging.info(f"Execution complete for '{identifier}'. Status: {result.get('status')}")
        return result

    except TaskError as e:
        # Catch known TaskErrors and format them
        logging.error(f"TaskError during execution of '{identifier}': {e.message}", exc_info=False)
        return format_error_result(e)
    except Exception as e:
        # Catch unexpected Python exceptions and format them
        logging.exception(f"Unexpected error during execution of '{identifier}':") # Log full traceback
        error = create_task_failure(
            message=f"An unexpected error occurred: {str(e)}",
            reason=UNEXPECTED_ERROR,
            details={"exception_type": type(e).__name__}
        )
        return format_error_result(error)
