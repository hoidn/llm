from typing import Dict, List, Any, Optional
import logging
import json

# Import necessary components and types (adjust paths based on final structure)
from handler.base_handler import BaseHandler # Use BaseHandler type hint
from task_system.task_system import TaskSystem
from task_system.ast_nodes import SubtaskRequest
from task_system.template_utils import Environment # Needed for execute_subtask_directly call
from system.errors import TaskError, create_task_failure, format_error_result, INPUT_VALIDATION_FAILURE, UNEXPECTED_ERROR

# Define TaskResult type hint
TaskResult = Dict[str, Any]

logger = logging.getLogger(__name__)


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
        explicit_file_paths = None
        if "file_context" in params and isinstance(params["file_context"], str):
            try:
                params["file_context"] = json.loads(params["file_context"])
                logging.debug(f"Parsed file_context JSON: {len(params['file_context'])} files")
                if isinstance(params["file_context"], list) and all(isinstance(p, str) for p in params["file_context"]):
                    explicit_file_paths = params["file_context"]
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON in file_context parameter: {e}")
                return format_error_result(create_task_failure(
                    message=f"Invalid JSON format in file_context parameter: {e}",
                    reason=INPUT_VALIDATION_FAILURE,
                    details={"parameter": "file_context", "error": str(e)}
                ))
        elif "file_context" in params and isinstance(params["file_context"], list) and all(isinstance(p, str) for p in params["file_context"]):
            explicit_file_paths = params["file_context"]

        # --- Routing Logic ---
        target_executor = None
        is_direct_tool = False
        template_definition = None
        handler_tools = getattr(handler_instance, 'direct_tool_executors', {}) # Get tools once

        # 1. Check TaskSystem Templates FIRST
        if hasattr(task_system_instance, 'find_template'):
            template_definition = task_system_instance.find_template(identifier)
            if template_definition:
                logger.info(f"Identifier '{identifier}' maps to a TaskSystem Template.")
                target_executor = task_system_instance # Target is TaskSystem
                is_direct_tool = False # Not a direct tool call
            else:
                 logger.debug(f"Identifier '{identifier}' not found as a TaskSystem Template.")
                 # Proceed to check direct tools only if not found as template

        # 2. Check Handler Direct Tools ONLY IF NOT found as a template
        if not template_definition and identifier in handler_tools:
            logger.info(f"Identifier '{identifier}' found as a Handler Direct Tool.")
            target_executor = handler_tools[identifier]
            is_direct_tool = True

        # 3. Handle Execution or Not Found
        if target_executor:
            if is_direct_tool:
                # --- Direct Tool Execution ---
                logger.debug(f"Executing Direct Tool: {identifier}")
                raw_result = target_executor(params) # Pass original params

                # Basic result wrapping
                if isinstance(raw_result, dict) and "status" in raw_result:
                     result = raw_result
                     if "notes" not in result: result["notes"] = {}
                else:
                     result = {"status": "COMPLETE", "content": str(raw_result), "notes": {}}

                # ---> ENSURE NOTES POPULATION FOR DIRECT TOOLS <---
                # Only add these if they don't already exist (executor might have added them)
                if "execution_path" not in result["notes"]:
                    result["notes"]["execution_path"] = "direct_tool"
                if "context_source" not in result["notes"]:
                    if explicit_file_paths is not None:
                        result["notes"]["context_source"] = "explicit_request"
                    else:
                        result["notes"]["context_source"] = "none"
                if "context_file_count" not in result["notes"] and "context_files_count" not in result["notes"]:
                    count = len(explicit_file_paths) if explicit_file_paths is not None else 0
                    result["notes"]["context_file_count"] = count
                    # Also add the standard key for consistency
                    result["notes"]["context_files_count"] = count
                # ---> END ENSURE NOTES <---

                logger.debug(f"Dispatcher (Direct Tool Path): Returning notes: {result.get('notes', {})}")
                logger.info(f"Direct Tool execution complete. Status: {result.get('status')}")
                return result
            else:
                # --- Template Execution via TaskSystem ---
                logger.debug(f"Executing Subtask Template via TaskSystem: {identifier}")
            
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
from typing import Dict, List, Any, Optional
import logging
import json

# Import necessary components and types (adjust paths based on final structure)
# Assuming standard project structure where dispatcher is at the top level src/
from handler.base_handler import BaseHandler # Use BaseHandler type hint
from task_system.task_system import TaskSystem
from task_system.ast_nodes import SubtaskRequest
from task_system.template_utils import Environment # Needed for execute_subtask_directly call
from system.errors import TaskError, create_task_failure, format_error_result, INPUT_VALIDATION_FAILURE, UNEXPECTED_ERROR

# Define TaskResult type hint
TaskResult = Dict[str, Any]

logger = logging.getLogger(__name__)
def execute_programmatic_task(
    identifier: str,
    params: Dict[str, Any],
    flags: Dict[str, bool],
    handler_instance: BaseHandler, # Use BaseHandler type hint
    task_system_instance: TaskSystem,
    optional_history_str: Optional[str] = None
) -> TaskResult:
    """
    Routes a programmatic task request (/task) to the appropriate executor.
    Handles Direct Tools and TaskSystem template routing with correct precedence.
    Populates result notes for direct tool execution path.
    """
    logger.debug(f"Dispatcher executing: identifier='{identifier}'")
    logger.debug(f"Dispatcher Params: {params}, Flags: {flags}")

    try:
        # --- Parameter Pre-processing ---
        explicit_file_paths: Optional[List[str]] = None
        if "file_context" in params:
            fc_param = params["file_context"]
            if isinstance(fc_param, list) and all(isinstance(p, str) for p in fc_param):
                explicit_file_paths = fc_param
                logger.debug("Using pre-parsed list for file_context.")
            elif isinstance(fc_param, str):
                if fc_param.strip():
                    try:
                        loaded_paths = json.loads(fc_param)
                        if isinstance(loaded_paths, list) and all(isinstance(p, str) for p in loaded_paths):
                            explicit_file_paths = loaded_paths
                            logger.debug("Successfully parsed file_context JSON string.")
                        else:
                            raise ValueError("Parsed JSON is not a list of strings.")
                    except (json.JSONDecodeError, ValueError) as e:
                        msg = f"Invalid file_context parameter: must be a JSON string array or already a list of strings. Error: {e}"
                        logger.error(msg)
                        return format_error_result(create_task_failure(msg, INPUT_VALIDATION_FAILURE))
                else:
                    logger.debug("Empty string provided for file_context, treating as no explicit paths.")
            elif fc_param is not None:
                 msg = f"Invalid type for file_context parameter: {type(fc_param).__name__}"
                 logger.error(msg)
                 return format_error_result(create_task_failure(msg, INPUT_VALIDATION_FAILURE))
                # Keep original file_context in params for potential use by target
                # Note: If it was parsed, it remains parsed in params for the target.

        # --- Routing Logic ---
        logger.debug("Dispatcher: Routing logic started.")
        target_executor = None
        is_direct_tool = False
        template_definition = None

        # 1. Check TaskSystem Templates FIRST (Corrected Precedence)
        logger.debug("Dispatcher: Checking for template...")
        if hasattr(task_system_instance, 'find_template'):
            template_definition = task_system_instance.find_template(identifier)
            logger.debug(f"Dispatcher: Template found: {bool(template_definition)}")
            if template_definition:
                logger.info(f"Identifier '{identifier}' maps to a TaskSystem Template.")
                target_executor = task_system_instance # Target is TaskSystem
                is_direct_tool = False # Not a direct tool call
            else:
                 logger.debug(f"Dispatcher: Identifier '{identifier}' not found as template.")

        # 2. Check Handler Direct Tools ONLY IF NOT found as a template (Corrected Logic)
        if not template_definition:
            logger.debug("Dispatcher: Checking for direct tool (template not found)...")
            handler_tools = getattr(handler_instance, 'direct_tool_executors', {})
            if identifier in handler_tools:
                logger.info(f"Identifier '{identifier}' found as a Handler Direct Tool.")
                target_executor = handler_tools[identifier]
                is_direct_tool = True
            else:
                logger.debug(f"Dispatcher: Direct tool '{identifier}' not found.")

        # 3. Handle Execution or Not Found
        if target_executor:
            if is_direct_tool:
                # --- Direct Tool Execution ---
                logger.debug("Dispatcher: Routing to Direct Tool.")
                # Direct tools receive the raw params dictionary
                raw_result = target_executor(params)

                # Basic result wrapping
                if isinstance(raw_result, dict) and "status" in raw_result:
                     result = raw_result
                     if "notes" not in result: result["notes"] = {}
                else:
                     result = {"status": "COMPLETE", "content": str(raw_result), "notes": {}}

                # ---> CORRECTED NOTES POPULATION FOR DIRECT TOOLS <---
                result["notes"]["execution_path"] = "direct_tool"
                if explicit_file_paths is not None: # Check the variable from pre-processing
                     result["notes"]["context_source"] = "explicit_request"
                     result["notes"]["context_files_count"] = len(explicit_file_paths)
                else:
                     result["notes"]["context_source"] = "none"
                     result["notes"]["context_files_count"] = 0
                # ---> END CORRECTION <---

                logger.debug(f"Dispatcher (Direct Tool Path): Returning notes: {result.get('notes', {})}")
                logger.info(f"Direct Tool execution complete. Status: {result.get('status')}")
                return result
            else:
                # --- Template Execution via TaskSystem ---
                logger.debug("Dispatcher: Routing to TaskSystem Template.")
                # Determine type/subtype for SubtaskRequest
                if ":" in identifier:
                    task_type, task_subtype = identifier.split(':', 1)
                else:
                    task_type = identifier
                    task_subtype = template_definition.get("subtype") # Get from template

                # Create SubtaskRequest
                subtask_request = SubtaskRequest(
                    type=task_type,
                    subtype=task_subtype,
                    inputs=params, # Pass original params
                    file_paths=explicit_file_paths, # Pass only explicitly provided paths
                    history_context=optional_history_str if flags.get("use-history") else None
                )

                # Call TaskSystem method
                base_env = Environment({}) # Create base env for direct call
                result = task_system_instance.execute_subtask_directly(subtask_request, base_env)

                # Before returning the result for the template path
                logger.debug(f"Dispatcher (Template Path): Returning TaskSystem result with notes: {result.get('notes', {})}")
                logger.info(f"TaskSystem template execution complete. Status: {result.get('status')}")
                return result
        else:
            # --- Identifier Not Found ---
            logger.warning(f"Identifier '{identifier}' not found as Direct Tool or TaskSystem Template.")
            return format_error_result(create_task_failure(
                message=f"Task identifier '{identifier}' not found",
                reason=INPUT_VALIDATION_FAILURE,
                details={"identifier": identifier}
            ))

    except TaskError as e:
        logger.error(f"TaskError during dispatch: {e.message}")
        return format_error_result(e)
    except Exception as e:
        logger.exception("Unexpected error during dispatch:") # Log traceback
        error = create_task_failure(
            message=f"An unexpected error occurred during dispatch: {str(e)}",
            reason=UNEXPECTED_ERROR,
            details={"exception_type": type(e).__name__}
        )
        return format_error_result(error)
