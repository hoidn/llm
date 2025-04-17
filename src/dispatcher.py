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

        # 1. Check Handler's *specific* Direct Tool registry first
        if hasattr(handler_instance, 'direct_tool_executors') and identifier in handler_instance.direct_tool_executors:
            target_executor = handler_instance.direct_tool_executors.get(identifier)
            if target_executor:
                is_direct_tool = True
                logging.info(f"Identifier '{identifier}' maps to a registered Direct Tool.")

        # 2. If not found as a Direct Tool, check TaskSystem Templates
        if not is_direct_tool:
            template_definition = task_system_instance.find_template(identifier)
            if template_definition:
                target_executor = task_system_instance  # Target the TaskSystem itself
                # is_direct_tool remains False
                logging.info(f"Identifier '{identifier}' maps to a TaskSystem Template.")
            else:
                # 3. Handle "Not Found" - wasn't in direct tools OR templates
                logging.warning(f"Identifier '{identifier}' not found as Direct Tool or TaskSystem Template.")
                return format_error_result(create_task_failure(
                    message=f"Task identifier '{identifier}' not found",
                    reason=INPUT_VALIDATION_FAILURE,
                    details={"identifier": identifier}
                ))

        # --- Context Determination ---
        # This section handles automatic context lookup if needed
        # Context precedence: explicit file_context > template file_paths > automatic lookup
        determined_file_paths = []
        context_source = "none"
        
        # Check for explicit file_context in params (highest precedence)
        if "file_context" in params and params["file_context"]:
            determined_file_paths = params["file_context"]
            context_source = "explicit"
            logging.debug(f"Using explicit file_context: {len(determined_file_paths)} files")
        
        # If no explicit context and we're using a template, check template file_paths
        elif not is_direct_tool and template_definition and template_definition.get("file_paths"):
            determined_file_paths = template_definition["file_paths"]
            context_source = "template"
            logging.debug(f"Using template file_paths: {len(determined_file_paths)} files")
        
        # If still no context and template allows fresh context, do automatic lookup
        elif (not is_direct_tool and template_definition and 
              template_definition.get("context_management", {}).get("fresh_context") != "disabled"):
            # We need to do automatic context lookup
            try:
                # Get memory system from task_system_instance
                memory_system = getattr(task_system_instance, "memory_system", None)
                if memory_system:
                    # Create context generation input
                    context_input = ContextGenerationInput(
                        template_description=template_definition.get("description", ""),
                        template_type=template_definition.get("type", ""),
                        template_subtype=template_definition.get("subtype", ""),
                        inputs=params,
                        history_context=optional_history_str if flags.get("use-history") else None
                    )
                    
                    # Get relevant context
                    logging.debug("Performing automatic context lookup via MemorySystem")
                    context_result = memory_system.get_relevant_context_for(context_input)
                    
                    # Extract file paths from matches
                    if hasattr(context_result, 'matches'):
                        determined_file_paths = [match[0] for match in context_result.matches]
                        context_source = "automatic"
                        logging.debug(f"Automatic context lookup found {len(determined_file_paths)} files")
                else:
                    logging.warning("Cannot perform automatic context lookup: memory_system not available")
            except Exception as e:
                # Log but continue - we'll just use empty context
                logging.error(f"Error during automatic context lookup: {e}", exc_info=True)
                # We don't fail the task, just proceed with empty context
        
        # --- Execution Logic ---
        if is_direct_tool:
            # Call Direct Tool Path
            logging.debug(f"Executing Direct Tool: {identifier} with {len(determined_file_paths)} context files")
            
            # If the tool expects file_context, ensure it's in the right format
            if "file_context" not in params and determined_file_paths:
                params["file_context"] = determined_file_paths
            
            # Execute the tool
            raw_result = target_executor(params)

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
            result["notes"]["context_source"] = context_source
            result["notes"]["context_file_count"] = len(determined_file_paths)

        else:
            # Call Subtask Template Path
            logging.debug(f"Executing Subtask Template via TaskSystem: {identifier} with {len(determined_file_paths)} context files")
            
            # Split identifier into type and subtype
            if ":" in identifier:
                task_type, task_subtype = identifier.split(':', 1)
            else:
                # Handle case where identifier doesn't have a colon
                task_type = identifier
                task_subtype = ""
                logging.warning(f"Identifier '{identifier}' doesn't follow type:subtype format, using '{task_type}' as type and empty subtype")
            
            # Create SubtaskRequest
            subtask_request = SubtaskRequest(
                type=task_type,
                subtype=task_subtype,
                inputs=params,
                file_paths=determined_file_paths
            )
            
            # Call the TaskSystem method
            result = task_system_instance.execute_subtask_directly(subtask_request)
            
            # Add execution path and context info
            if "notes" not in result: 
                result["notes"] = {}
            result["notes"]["execution_path"] = "subtask_template"
            result["notes"]["context_source"] = context_source
            result["notes"]["context_file_count"] = len(determined_file_paths)

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
