from typing import Dict, List, Any, Optional
import logging
import json
from memory.context_generation import ContextGenerationInput, AssociativeMatchResult

# Import necessary components and types
from handler.base_handler import BaseHandler
from task_system.task_system import TaskSystem
from task_system.ast_nodes import SubtaskRequest
from system.errors import TaskError, create_task_failure, format_error_result, UNEXPECTED_ERROR, INPUT_VALIDATION_FAILURE

# Define TaskResult type hint
TaskResult = Dict[str, Any]


def execute_programmatic_task(
    identifier: str,
    params: Dict[str, Any],
    flags: Dict[str, bool],  # For flags like --use-history
    handler_instance: BaseHandler,  # Pass the actual Handler instance
    task_system_instance: TaskSystem,  # Pass the actual TaskSystem instance
    optional_history_str: Optional[str] = None  # Recent conversation history
) -> TaskResult:
    """
    Routes a programmatic task request to the appropriate executor.

    Args:
        identifier: The task identifier string (e.g., "type:subtype" or "tool_name").
        params: Dictionary of parameters provided for the task.
        flags: Dictionary of boolean flags provided (e.g., {"use-history": True}).
        handler_instance: The instantiated Handler component.
        task_system_instance: The instantiated TaskSystem instance.
        optional_history_str: Formatted string of recent chat history.

    Returns:
        A TaskResult dictionary representing the outcome.
    """
    logging.info(f"Dispatcher received request for identifier: {identifier}")
    logging.debug(f"Params: {params}, Flags: {flags}")
    
    if optional_history_str and flags.get("use-history"):
        logging.debug("History context will be used for context generation")
    
    try:
        # --- Parameter Processing ---
        # Handle file_context parameter if it's a JSON string
        if "file_context" in params and isinstance(params["file_context"], str):
            try:
                params["file_context"] = json.loads(params["file_context"])
                logging.debug(f"Parsed file_context JSON: {len(params['file_context'])} files")
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON in file_context parameter: {e}")
                return format_error_result(create_task_failure(
                    message=f"Invalid JSON format in file_context parameter: {e}",
                    reason=INPUT_VALIDATION_FAILURE,
                    details={"parameter": "file_context", "error": str(e)}
                ))

        # --- Routing Logic ---
        target_executor = None
        is_direct_tool = False
        template_definition = None  # Initialize template_definition

        # 1. Check Handler's Direct Tool registry first
        if hasattr(handler_instance, 'direct_tool_executors') and identifier in handler_instance.direct_tool_executors:
            target_executor = handler_instance.direct_tool_executors.get(identifier)
            if target_executor:
                is_direct_tool = True  # Tentatively direct
                logging.info(f"Identifier '{identifier}' found in Handler Direct Tool registry")

        # 2. Check TaskSystem Templates (Templates take precedence)
        template_definition = task_system_instance.find_template(identifier)
        if template_definition:
            target_executor = task_system_instance
            is_direct_tool = False  # Override: It's a template
            logging.info(f"Identifier '{identifier}' maps to a TaskSystem Template (overrides Direct Tool match if any).")
        elif is_direct_tool:
            logging.info(f"Identifier '{identifier}' confirmed as Direct Tool (not a template).")
        else:
            # Not found in either registry
            logging.warning(f"Identifier '{identifier}' not found as Direct Tool or TaskSystem Template.")
            return format_error_result(create_task_failure(
                message=f"Task identifier '{identifier}' not found",
                reason=INPUT_VALIDATION_FAILURE,
                details={"identifier": identifier}
            ))

        # --- Context Determination for Direct Tools Only ---
        # For Template execution, context determination is now fully handled by TaskSystem
        
        # --- Execution Logic ---
        if is_direct_tool:
            # Call Direct Tool Path
            logging.debug(f"Executing Direct Tool: {identifier}")
            
            # Direct tools rely solely on their explicit parameters
            # We DO NOT inject template or automatic context into direct tools
            params_for_tool = params.copy()  # Avoid modifying original params
            
            # Execute the tool
            raw_result = target_executor(params_for_tool)

            # Wrap raw result into TaskResult
            result: TaskResult
            if isinstance(raw_result, dict) and "status" in raw_result and "content" in raw_result:
                result = raw_result
                # Ensure notes exist
                if "notes" not in result:
                    result["notes"] = {}
            else:
                # Basic string conversion for other types
                result = {
                    "status": "COMPLETE",  # Assume success unless executor raises error
                    "content": str(raw_result),
                    "notes": {}
                }
            
            # Add execution path and context info
            result["notes"]["execution_path"] = "direct_tool"
            result["notes"]["context_source"] = "explicit_request" if "file_context" in params else "none"
            result["notes"]["context_file_count"] = len(params.get("file_context", [])) if isinstance(params.get("file_context"), list) else 0

        else:
            # Call Subtask Template Path
            logging.debug(f"Executing Subtask Template via TaskSystem: {identifier}")
            
            # Split identifier into type and subtype
            if ":" in identifier:
                task_type, task_subtype = identifier.split(':', 1)
            else:
                # Handle case where identifier doesn't have a colon
                task_type = identifier
                task_subtype = ""
                logging.warning(f"Identifier '{identifier}' doesn't follow type:subtype format, using '{task_type}' as type and empty subtype")
            
            # Check for explicit file_context ONLY from the original params
            explicit_file_context = None
            if "file_context" in params and isinstance(params["file_context"], list):
                explicit_file_context = params["file_context"]  # Already parsed list
            
            # Create SubtaskRequest, passing original params, history, and ONLY explicit files.
            # Let TaskSystem handle context determination based on template/params.
            subtask_request = SubtaskRequest(
                type=task_type,
                subtype=task_subtype,
                inputs=params,
                # Pass explicit files ONLY if they came from the original params['file_context']
                file_paths=explicit_file_context,
                history_context=optional_history_str if flags.get("use-history") else None  # Pass history if flag is set
            )
            
            # Call the TaskSystem method
            result = task_system_instance.execute_subtask_directly(subtask_request)
            
            # Ensure notes dictionary exists
            if "notes" not in result:
                result["notes"] = {}

            # Always add/update execution_path (Dispatcher's responsibility)
            result["notes"]["execution_path"] = "subtask_template"

            # Log warnings if TaskSystem didn't report context notes, but don't add fallbacks
            if "context_source" not in result["notes"]:
                logging.warning("TaskSystem did not report context_source.")
            if "context_files_count" not in result["notes"]:
                logging.warning("TaskSystem did not report context_files_count.")

        logging.info(f"Execution complete for '{identifier}'. Status: {result.get('status')}")
        return result

    except TaskError as e:
        # Catch known TaskErrors and format them
        logging.error(f"TaskError during execution of '{identifier}': {e.message}")
        return format_error_result(e)
    except Exception as e:
        # Catch unexpected Python exceptions and format them
        logging.exception(f"Unexpected error during execution of '{identifier}':")  # Log full traceback
        error = create_task_failure(
            message=f"An unexpected error occurred: {str(e)}",
            reason=UNEXPECTED_ERROR,
            details={"exception_type": type(e).__name__}
        )
        return format_error_result(error)
