"""
Dispatcher module responsible for routing programmatic task requests.
"""

import json # For parsing file_context
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

# Configure logging for this module
logger = logging.getLogger(__name__)

# Import necessary models and error types
from src.system.models import (
    SubtaskRequest, TaskResult, TaskError, TaskFailureError, TaskFailureReason,
    ContextManagement, TaskFailureDetails # Import TaskFailureDetails
)
from src.system.errors import SexpSyntaxError, SexpEvaluationError
from src.sexp_evaluator.sexp_evaluator import SexpEvaluator # Import SexpEvaluator
from src.sexp_evaluator.sexp_environment import SexpEnvironment # ADDED for S-expression execution

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from src.handler.base_handler import BaseHandler
    from src.task_system.task_system import TaskSystem
    from src.memory.memory_system import MemorySystem

# Helper function to create a standard FAILED TaskResult dictionary
# FIX 1: Accept TaskFailureDetails object for details
def _create_failed_result_dict(
    reason: TaskFailureReason,
    message: str,
    details_obj: Optional[TaskFailureDetails] = None
) -> Dict[str, Any]:
    """
    Creates a dictionary representing a FAILED TaskResult.
    """
    # Pass the details_obj directly to TaskFailureError
    error_obj = TaskFailureError(type="TASK_FAILURE", reason=reason, message=message, details=details_obj)
    # Use .model_dump() for Pydantic v2 compatibility
    # Error details are now nested within the error_obj
    return TaskResult(status="FAILED", content=message, notes={"error": error_obj.model_dump(exclude_none=True)}).model_dump(exclude_none=True)


def execute_programmatic_task(
    identifier: str,
    params: Dict[str, Any],
    flags: Dict[str, bool], # Corrected type hint
    handler_instance: 'BaseHandler',
    task_system_instance: 'TaskSystem',
    memory_system: 'MemorySystem', # Ensure this is passed in
    optional_history_str: Optional[str] = None # Added optional history
) -> Dict[str, Any]:
    """
    Executes a programmatic task based on the identifier and parameters.

    Routes the request to SexpEvaluator, TaskSystem, or Handler tools.

    Args:
        identifier: The task identifier (S-expression string, atomic task ID, or tool ID).
        params: Dictionary of parameters for the task/tool. May include 'file_context'.
        flags: Dictionary of flags (currently unused).
        handler_instance: Instance of the handler (e.g., PassthroughHandler).
        task_system_instance: Instance of the TaskSystem.
        memory_system: Instance of the MemorySystem.
        optional_history_str: Optional string representation of conversation history.

    Returns:
        A dictionary representing the TaskResult.
    """
    logging.info(f"Dispatcher received task: identifier='{identifier[:50]}...', params={list(params.keys())}, flags={flags}")
    notes: Dict[str, Any] = {} # Initialize notes for this dispatch call
    task_result_dict: Optional[Dict[str, Any]] = None # To hold the final result dictionary

    # --- S-expression Handling ---
    if identifier.strip().startswith('('):
        notes['execution_path'] = "s_expression"
        logging.info("Identifier detected as S-expression. Executing via SexpEvaluator.")
        try:
            # <<< ADD LOGGING >>>
            logger.debug(f"*** Dispatcher (S-exp path): TaskSystem instance ID = {id(task_system_instance)}")
            # <<< END LOGGING >>>
            # Ensure SexpEvaluator gets all its dependencies
            sexp_evaluator = SexpEvaluator(task_system_instance, handler_instance, memory_system)

            # --- START MODIFICATION ---
            # Use the 'params' argument directly as the initial bindings dictionary
            initial_bindings_from_params = params if isinstance(params, dict) else {}
            env_to_pass: Optional[SexpEnvironment] = None

            if initial_bindings_from_params:
                logger.debug(f"*** Dispatcher (S-exp path): Using received 'params' dict for initial bindings: {list(initial_bindings_from_params.keys())}")
                env_to_pass = SexpEnvironment(bindings=initial_bindings_from_params)
                logger.debug(f"*** Dispatcher (S-exp path): Created initial SexpEnvironment object ID: {id(env_to_pass)}")
            else:
                 # Handle case where params might be None or empty if called differently
                 logger.debug("*** Dispatcher (S-exp path): Received empty or no 'params'. SexpEvaluator will create a new empty environment.")
                 # env_to_pass remains None

            # REMOVE or COMMENT OUT the previous logic checking flags['initial_env'] here:
            # initial_bindings_from_flags = flags.get("initial_env") if flags else None
            # ... (logic using initial_bindings_from_flags) ...

            # Pass the potentially created SexpEnvironment object (or None) to evaluate_string
            raw_result = sexp_evaluator.evaluate_string(identifier, initial_env=env_to_pass)
            # --- END MODIFICATION ---

            # Convert raw result to TaskResult object/dict
            if isinstance(raw_result, TaskResult):
                task_result_obj = raw_result
            elif isinstance(raw_result, dict) and "status" in raw_result and "content" in raw_result:
                try:
                    task_result_obj = TaskResult.model_validate(raw_result)
                except Exception as val_err:
                    logging.warning(f"Sexp result looked like TaskResult dict but failed validation: {val_err}. Wrapping.")
                    task_result_obj = TaskResult(status="COMPLETE", content=str(raw_result), notes={"sexp_raw_result": raw_result})
            else: # Wrap any other type of result
                task_result_obj = TaskResult(status="COMPLETE", content=str(raw_result), notes={"sexp_raw_result": raw_result})
            
            if task_result_obj.notes is None: task_result_obj.notes = {} # Ensure notes dict exists
            task_result_obj.notes.update(notes) # Merge dispatcher notes
            task_result_dict = task_result_obj.model_dump(exclude_none=True)

        except SexpSyntaxError as e:
            logging.warning(f"S-expression syntax error for '{identifier[:50]}...': {e}")
            details_obj = TaskFailureDetails(failing_expression=e.sexp_string, notes={"raw_error_details": e.error_details})
            task_result_dict = _create_failed_result_dict("input_validation_failure", f"S-expression Syntax Error: {e.args[0]}", details_obj)
            if 'notes' not in task_result_dict: task_result_dict['notes'] = {}
            task_result_dict['notes'].update(notes)

        except SexpEvaluationError as e:
            logging.warning(f"S-expression evaluation error for '{identifier[:50]}...': {e}")
            details_obj = TaskFailureDetails(failing_expression=e.expression, notes={"raw_error_details": e.error_details})
            task_result_dict = _create_failed_result_dict("subtask_failure", f"S-expression Evaluation Error: {e.args[0]}", details_obj)
            if 'notes' not in task_result_dict: task_result_dict['notes'] = {}
            task_result_dict['notes'].update(notes)
        except Exception as e:
            logging.exception(f"Unexpected error during S-expression evaluation: {e}")
            task_result_dict = _create_failed_result_dict("unexpected_error", f"Unexpected S-expression evaluation error: {e}")
            if 'notes' not in task_result_dict: task_result_dict['notes'] = {}
            task_result_dict['notes'].update(notes)
        return task_result_dict # RETURN HERE for S-expressions

    # --- Named Target Handling (Task or Tool) ---
    resolved_files: Optional[List[str]] = None
    notes['context_source'] = "none"
    notes['context_files_count'] = 0
    fc = params.get('file_context')
    if fc is not None:
        if isinstance(fc, list):
            if all(isinstance(item, str) for item in fc): resolved_files = fc
            else:
                # Use CORRECTED helper signature
                task_result_dict = _create_failed_result_dict("input_validation_failure", "Invalid 'file_context': list must contain only strings.")
                if 'notes' not in task_result_dict: task_result_dict['notes'] = {}
                task_result_dict['notes'].update(notes) # Add context notes even on failure
                return task_result_dict
        elif isinstance(fc, str):
            try:
                parsed_fc = json.loads(fc)
                if isinstance(parsed_fc, list) and all(isinstance(item, str) for item in parsed_fc): resolved_files = parsed_fc
                else:
                    # Use CORRECTED helper signature
                    task_result_dict = _create_failed_result_dict("input_validation_failure", "Invalid 'file_context': JSON string did not decode to a list of strings.")
                    if 'notes' not in task_result_dict: task_result_dict['notes'] = {}
                    task_result_dict['notes'].update(notes)
                    return task_result_dict
            except json.JSONDecodeError as e:
                # Use CORRECTED helper signature
                task_result_dict = _create_failed_result_dict("input_validation_failure", f"Invalid 'file_context': Failed to parse JSON string - {e}")
                if 'notes' not in task_result_dict: task_result_dict['notes'] = {}
                task_result_dict['notes'].update(notes)
                return task_result_dict
        else:
            # Use CORRECTED helper signature
            task_result_dict = _create_failed_result_dict("input_validation_failure", "Invalid 'file_context': Must be a list of strings or a JSON string array.")
            if 'notes' not in task_result_dict: task_result_dict['notes'] = {}
            task_result_dict['notes'].update(notes)
            return task_result_dict

        if resolved_files is not None:
            notes['context_source'] = "explicit_request"
            notes['context_files_count'] = len(resolved_files)

    # Remove file_context from params passed to execution
    execution_params = {k: v for k, v in params.items() if k != 'file_context'}

    # Check Task System
    logging.debug(f"Checking TaskSystem for identifier: '{identifier}'")
    try:
        template = task_system_instance.find_template(identifier)
    except Exception as e:
        logging.exception(f"Error finding template '{identifier}': {e}")
        # Use CORRECTED helper signature
        task_result_dict = _create_failed_result_dict("unexpected_error", f"Error looking up task/tool '{identifier}': {e}")
        if 'notes' not in task_result_dict: task_result_dict['notes'] = {}
        task_result_dict['notes'].update(notes)
        return task_result_dict

    if template and template.get("type") == "atomic":
        logging.info(f"Identifier '{identifier}' found as atomic task. Executing...")
        notes['execution_path'] = "subtask_template"
        try:
            # Generate a unique task ID (simple approach for now)
            import uuid
            task_id = str(uuid.uuid4())
            request = SubtaskRequest(
                task_id=task_id,
                type="atomic",
                name=identifier,
                inputs=execution_params,
                file_paths=resolved_files
                # context_management=... # Use defaults from TaskSystem
            )
            task_result_obj = task_system_instance.execute_atomic_template(request)
            # Merge dispatcher notes into the result notes (reversed order)
            # --- START MODIFICATION ---
            final_notes = notes.copy() # Start with dispatcher notes
            if task_result_obj.notes:
                final_notes.update(task_result_obj.notes) # Update with task notes (task notes overwrite dispatcher notes on conflict)
            task_result_obj.notes = final_notes # Assign merged notes back
            task_result_dict = task_result_obj.model_dump(exclude_none=True)
            # --- END MODIFICATION ---

        except TaskError as e: # Should be less common if TaskSystem returns TaskResult on failure
             logging.warning(f"TaskSystem execution failed for '{identifier}': {e}")
             # Create a FAILED TaskResult if TaskSystem raised instead of returning one
             # Extract details correctly from TaskError object
             fail_reason = e.reason if hasattr(e, 'reason') else "subtask_failure"
             fail_msg = e.message if hasattr(e, 'message') else str(e)
             fail_details_obj = e.details if hasattr(e, 'details') else None
             # Use CORRECTED helper signature
             task_result_dict = _create_failed_result_dict(fail_reason, f"Task Execution Error: {fail_msg}", fail_details_obj)
             # Merge notes
             if 'notes' not in task_result_dict: task_result_dict['notes'] = {}
             task_result_dict['notes'].update(notes)

        except Exception as e:
            logging.exception(f"Unexpected error during TaskSystem execution for '{identifier}': {e}")
            # Use CORRECTED helper signature
            task_result_dict = _create_failed_result_dict("unexpected_error", f"Task execution failed: {e}")
            if 'notes' not in task_result_dict: task_result_dict['notes'] = {}
            task_result_dict['notes'].update(notes)

        return task_result_dict

    # Check Handler Tools
    logging.debug(f"Checking Handler tools for identifier: '{identifier}'")
    if identifier in handler_instance.tool_executors:
        logging.info(f"Identifier '{identifier}' found as direct tool. Executing...")
        notes['execution_path'] = "direct_tool"
        try:
            # Pass original params (including file_context if tool needs it)
            tool_result_obj: TaskResult = handler_instance._execute_tool(identifier, params) # Ensure type hint

            # --- START MODIFICATION ---
            if tool_result_obj.status == "FAILED":
                logging.warning(f"Handler tool '{identifier}' returned FAILED status.")
                # Extract original error details if present
                error_obj_or_dict = tool_result_obj.notes.get("error") # Could be object or dict

                # --- START REVISED EXTRACTION ---
                fail_reason: TaskFailureReason = "tool_execution_error" # Default reason
                fail_msg = tool_result_obj.content # Use content as message fallback
                fail_details_obj: Optional[TaskFailureDetails] = None # Initialize details as None

                if isinstance(error_obj_or_dict, TaskFailureError):
                    # If it's the actual error object, extract attributes directly
                    logging.debug("Extracting details from TaskFailureError object.")
                    fail_reason = error_obj_or_dict.reason
                    fail_msg = error_obj_or_dict.message
                    fail_details_obj = error_obj_or_dict.details # Get the details object

                elif isinstance(error_obj_or_dict, dict):
                    # If it's a dictionary (fallback or different serialization)
                    logging.debug("Attempting to extract details from error dictionary.")
                    fail_reason = error_obj_or_dict.get("reason", fail_reason)
                    fail_msg = error_obj_or_dict.get("message", fail_msg)
                    details_dict = error_obj_or_dict.get("details")
                    if isinstance(details_dict, dict):
                        # Try to validate the details dict into the TaskFailureDetails model
                        try:
                            fail_details_obj = TaskFailureDetails.model_validate(details_dict)
                        except Exception as parse_err:
                            logging.warning(f"Could not parse 'details' dict from tool error notes: {parse_err}")
                    elif isinstance(details_dict, TaskFailureDetails): # Handle if details is already object
                         fail_details_obj = details_dict


                # Use the helper to create the error structure with the ORIGINAL message and extracted details
                error_structure = _create_failed_result_dict(
                    reason=fail_reason,
                    message=fail_msg, # Pass the ORIGINAL fail_msg here
                    details_obj=fail_details_obj # Pass the extracted details object
                )

                # Create the final TaskResult dictionary
                task_result_dict = {
                    "status": "FAILED",
                    # Set the top-level content with the PREFIXED message
                    "content": f"Tool Execution Error: {fail_msg}",
                    # Notes merging logic
                    "notes": notes.copy() # Start with dispatcher notes
                }

                # Merge original notes from the tool result (excluding the 'error' key itself)
                original_notes_without_error = {k: v for k, v in tool_result_obj.notes.items() if k != 'error'}
                task_result_dict['notes'].update(original_notes_without_error)

                # Add the correctly formatted error structure (from the helper) into notes
                task_result_dict['notes']['error'] = error_structure['notes']['error'] # Extract the error dict from helper result
                # --- END REVISED EXTRACTION ---


            elif tool_result_obj.status == "CONTINUATION":
                logging.error(f"Direct tool call '{identifier}' returned CONTINUATION status, which is not allowed.")
                task_result_dict = _create_failed_result_dict("tool_execution_error", "Direct tool calls cannot return CONTINUATION status.")
                # Merge notes
                final_notes = notes.copy() # Start with dispatcher notes
                # If tool result had other notes, merge them (excluding error)
                original_notes_without_error = {k: v for k, v in tool_result_obj.notes.items() if k != 'error'}
                final_notes.update(original_notes_without_error)
                task_result_dict['notes'] = final_notes
                # Add the error structure back
                task_result_dict['notes']['error'] = _create_failed_result_dict("tool_execution_error", "Direct tool calls cannot return CONTINUATION status.")['notes']['error']


            else: # COMPLETE status
                # Merge dispatcher notes into the result notes (reversed order)
                final_notes = notes.copy() # Start with dispatcher notes
                if tool_result_obj.notes:
                    final_notes.update(tool_result_obj.notes) # Update with tool notes (tool notes overwrite dispatcher notes on conflict)
                tool_result_obj.notes = final_notes # Assign merged notes back
                task_result_dict = tool_result_obj.model_dump(exclude_none=True)
            # --- END MODIFICATION ---

        except TaskError as e: # Should be less common if Handler returns TaskResult on failure
             logging.warning(f"Handler tool execution failed for '{identifier}': {e}")
             # Create a FAILED TaskResult if Handler raised instead of returning one
             # Extract details correctly from TaskError object
             fail_reason = e.reason if hasattr(e, 'reason') else "tool_execution_error"
             fail_msg = e.message if hasattr(e, 'message') else str(e)
             fail_details_obj = e.details if hasattr(e, 'details') else None
             # Use CORRECTED helper signature
             task_result_dict = _create_failed_result_dict(fail_reason, f"Tool Execution Error: {fail_msg}", fail_details_obj)
             # Merge notes
             if 'notes' not in task_result_dict: task_result_dict['notes'] = {}
             task_result_dict['notes'].update(notes)

        except Exception as e:
            logging.exception(f"Unexpected error during Handler tool execution for '{identifier}': {e}")
            # Use CORRECTED helper signature
            task_result_dict = _create_failed_result_dict("unexpected_error", f"Tool execution failed: {e}")
            if 'notes' not in task_result_dict: task_result_dict['notes'] = {}
            task_result_dict['notes'].update(notes)

        return task_result_dict

    # Identifier Not Found
    logging.warning(f"Identifier '{identifier}' not found as atomic task or direct tool.")
    # Use CORRECTED helper signature
    task_result_dict = _create_failed_result_dict("template_not_found", f"Identifier not found: {identifier}")
    if 'notes' not in task_result_dict: task_result_dict['notes'] = {}
    task_result_dict['notes'].update(notes)
    return task_result_dict
