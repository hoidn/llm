"""
Dispatcher module responsible for routing programmatic task requests.
"""

import json # For parsing file_context
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

# Import necessary models and error types
from src.system.models import (
    SubtaskRequest, TaskResult, TaskError, TaskFailureError, TaskFailureReason,
    ContextManagement, TaskFailureDetails # Import TaskFailureDetails
)
from src.system.errors import SexpSyntaxError, SexpEvaluationError
from src.sexp_evaluator.sexp_evaluator import SexpEvaluator # Import SexpEvaluator

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
    flags: Dict[str, bool], # Changed type hint to bool
    handler_instance: 'BaseHandler',
    task_system_instance: 'TaskSystem',
    memory_system: 'MemorySystem', # Added memory_system dependency
    params: Dict[str, Any],
    flags: Dict[str, Any], # Keep flags for future use, though not used in this phase
    handler_instance: BaseHandler,
    task_system_instance: TaskSystem,
    memory_system: MemorySystem, # Added as per instructions
    optional_history_str: Optional[str] = None # Keep for potential future SexpEvaluator use
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
    notes: Dict[str, Any] = {}
    resolved_files: Optional[List[str]] = None

    # 1. Handle S-expression routing first
    if identifier.startswith('('):
        notes['execution_path'] = "s_expression"
        try:
            # Option A: Instantiate SexpEvaluator directly here
            sexp_evaluator = SexpEvaluator(task_system_instance, handler_instance, memory_system)
            # TODO: Consider passing optional_history_str if evaluator needs it
            result_obj = sexp_evaluator.evaluate_string(identifier) # Assuming default initial_env=None

            # Format the result into TaskResult dictionary
            if isinstance(result_obj, TaskResult):
                task_result_dict = result_obj.model_dump(exclude_none=True)
            elif isinstance(result_obj, dict) and 'status' in result_obj:
                # Basic check if it looks like a TaskResult dict already
                # Ideally, validate against TaskResult model here if needed
                task_result_dict = result_obj
            else:
                # Wrap raw result
                task_result = TaskResult(status="COMPLETE", content=str(result_obj))
                task_result_dict = task_result.model_dump(exclude_none=True)

            # Merge notes
            task_result_dict['notes'] = {**notes, **task_result_dict.get('notes', {})}
            return task_result_dict

        except SexpSyntaxError as e:
            logging.warning(f"S-expression syntax error for '{identifier}': {e}", exc_info=True)
            # Extract first line of message for content
            error_message = e.args[0] if e.args else str(e)
            # Ensure details include the expression string
            details = {"expression": e.sexp_string, "error_details": e.error_details}
            return _create_failed_result_dict(
                "input_validation_failure",
                f"S-expression Syntax Error: {error_message}",
                details=details,
                existing_notes=notes # Pass notes for merging
            )
        except SexpEvaluationError as e:
            logging.warning(f"S-expression evaluation error for '{identifier}': {e}", exc_info=True)
            # Use args[0] for the primary message from the exception
            error_message = e.args[0] if e.args else str(e)
            # Ensure details are captured correctly
            details = {"expression": e.expression, "error_details": e.error_details}
            return _create_failed_result_dict(
                "subtask_failure",
                f"S-expression Evaluation Error: {error_message}",
                details=details,
                existing_notes=notes # Pass notes for merging
            )
        except Exception as e:
            logging.exception(f"Unexpected error evaluating S-expression '{identifier}': {e}")
            # Pass notes for merging in unexpected errors too
            return _create_failed_result_dict(
                "unexpected_error",
                f"Unexpected error during S-expression evaluation: {e}",
                existing_notes=notes
            )

    # 2. Parse file_context if present (for non-Sexp paths)
    file_context_param = params.pop('file_context', None) # Remove from params
    if file_context_param is not None:
        if isinstance(file_context_param, list):
            if all(isinstance(item, str) for item in file_context_param):
                resolved_files = file_context_param
                notes['context_source'] = "explicit_request"
                notes['context_files_count'] = len(resolved_files)
            else:
                msg = "Invalid 'file_context': must be a list of strings."
                logging.warning(msg)
                return _create_failed_result_dict("input_validation_failure", msg)
        elif isinstance(file_context_param, str):
            try:
                parsed_list = json.loads(file_context_param)
                if isinstance(parsed_list, list) and all(isinstance(item, str) for item in parsed_list):
                    resolved_files = parsed_list
                    notes['context_source'] = "explicit_request"
                    notes['context_files_count'] = len(resolved_files)
                else:
                    msg = "Invalid 'file_context': JSON string must decode to a list of strings."
                    logging.warning(msg)
                    return _create_failed_result_dict("input_validation_failure", msg)
            except json.JSONDecodeError as e:
                msg = f"Invalid 'file_context': Failed to parse JSON string - {e}"
                logging.warning(msg)
                return _create_failed_result_dict("input_validation_failure", msg)
        else:
            msg = "Invalid 'file_context': Must be a list of strings or a valid JSON string array."
            logging.warning(msg)
            return _create_failed_result_dict("input_validation_failure", msg)
    else:
        notes['context_source'] = "none"
        notes['context_files_count'] = 0

    # 3. Try TaskSystem routing
    try:
        template_def = task_system_instance.find_template(identifier)
    except Exception as e:
        logging.exception(f"Error finding template '{identifier}': {e}")
        return _create_failed_result_dict("unexpected_error", f"Error looking up task/tool '{identifier}': {e}")

    if template_def:
        notes['execution_path'] = "subtask_template"
        try:
            # Generate a unique task ID (simple approach for now)
            import uuid
            task_id = str(uuid.uuid4())

            # Construct SubtaskRequest
            request = SubtaskRequest(
                task_id=task_id,
                name=identifier,
                type=template_def.get('type', 'atomic'), # Default to atomic if missing?
                subtype=template_def.get('subtype'),
                inputs=params, # Pass remaining params
                file_paths=resolved_files,
                # context_management=ContextManagement(...) # Use defaults or load from template?
            )

            task_result_obj = task_system_instance.execute_atomic_template(request)

            # If the task system already returned a FAILED result, return it directly
            if task_result_obj.status == "FAILED":
                task_result_dict = task_result_obj.model_dump(exclude_none=True)
                # Merge dispatcher notes into the existing notes
                task_result_dict['notes'] = {**notes, **task_result_dict.get('notes', {})}
                return task_result_dict

            # Otherwise, process the successful result
            task_result_dict = task_result_obj.model_dump(exclude_none=True)
            # Merge notes, prioritizing notes from the task execution
            task_result_dict['notes'] = {**notes, **task_result_dict.get('notes', {})}
            return task_result_dict

        except TaskError as e: # Catch specific TaskErrors if TaskSystem raises them directly (should be less common now)
             logging.warning(f"TaskError executing atomic template '{identifier}': {e}", exc_info=True)
             # Propagate the error details if available
             fail_reason = e.reason if hasattr(e, 'reason') else "subtask_failure"
             fail_msg = e.message if hasattr(e, 'message') else str(e)
             fail_details = e.details if hasattr(e, 'details') else None
             return _create_failed_result_dict(fail_reason, f"Task Execution Error: {fail_msg}", fail_details)
        except Exception as e:
            logging.exception(f"Unexpected error executing atomic template '{identifier}': {e}")
            return _create_failed_result_dict("unexpected_error", f"Unexpected error during task execution: {e}")

    # 4. Try Handler Tool routing
    if identifier in handler_instance.tool_executors:
        notes['execution_path'] = "direct_tool"
        try:
            # Note: _execute_tool might need adjustment if it doesn't accept raw params dict
            task_result_obj = handler_instance._execute_tool(identifier, params)

            if task_result_obj.status == "CONTINUATION":
                 msg = "Direct tool calls cannot return CONTINUATION status."
                 logging.warning(f"{msg} Tool: {identifier}")
                 # Pass existing notes to the error helper
                 return _create_failed_result_dict(
                     "tool_execution_error",
                     msg,
                     details={"tool_identifier": identifier},
                     existing_notes=notes # Pass the notes collected so far
                 )

            # If the tool already returned a FAILED result, return it directly
            if task_result_obj.status == "FAILED":
                task_result_dict = task_result_obj.model_dump(exclude_none=True)
                # Merge dispatcher notes into the existing notes
                task_result_dict['notes'] = {**notes, **task_result_dict.get('notes', {})}
                return task_result_dict

            # Otherwise, process the successful result
            task_result_dict = task_result_obj.model_dump(exclude_none=True)
            # Merge notes, prioritizing notes from the tool execution
            task_result_dict['notes'] = {**notes, **task_result_dict.get('notes', {})}
            return task_result_dict

        except TaskError as e: # Catch specific TaskErrors if Handler raises them (should be less common now)
             logging.warning(f"TaskError executing direct tool '{identifier}': {e}", exc_info=True)
             fail_reason = e.reason if hasattr(e, 'reason') else "tool_execution_error"
             fail_msg = e.message if hasattr(e, 'message') else str(e)
             fail_details = e.details if hasattr(e, 'details') else None
             return _create_failed_result_dict(fail_reason, f"Tool Execution Error: {fail_msg}", fail_details)
        except Exception as e:
            logging.exception(f"Unexpected error executing direct tool '{identifier}': {e}")
            return _create_failed_result_dict("unexpected_error", f"Unexpected error during tool execution: {e}")

    # 5. Not Found
    logging.warning(f"Identifier '{identifier}' not found as S-expression, atomic task, or direct tool.")
    # Pass existing notes (like context_source) to the error helper
    return _create_failed_result_dict(
        "template_not_found",
        f"Task or tool identifier '{identifier}' not found.",
        existing_notes=notes
    )
