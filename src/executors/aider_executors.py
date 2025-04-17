import json
import logging
from typing import Dict, Any, List, Optional, Tuple

# Import AiderBridge safely for type hinting and execution
try:
    # Adjust path relative to src/ directory if needed
    from aider_bridge.bridge import AiderBridge
except ImportError:
    # Define a placeholder if AiderBridge isn't installed/available
    # This allows type checking and basic structure even without the dependency
    logging.warning("AiderBridge not found. Using placeholder.")
    class AiderBridge:
        def execute_automatic_task(self, prompt: str, file_context: Optional[List[str]] = None) -> Dict[str, Any]:
            return {"status": "ERROR", "content": "AiderBridge not available"}
        def start_interactive_session(self, query: str, file_context: Optional[List[str]] = None) -> Dict[str, Any]:
             return {"status": "ERROR", "content": "AiderBridge not available"}

# Import error utilities (adjust path if needed based on project structure)
from system.errors import create_task_failure, format_error_result, INPUT_VALIDATION_FAILURE, UNEXPECTED_ERROR

# Define TaskResult type hint
TaskResult = Dict[str, Any]

def _parse_file_context(file_context_param: Optional[Any]) -> Tuple[Optional[List[str]], Optional[TaskResult]]:
    """Helper to parse and validate the file_context parameter."""
    if file_context_param is None:
        return None, None # No context provided is valid

    if isinstance(file_context_param, list):
        if all(isinstance(p, str) for p in file_context_param):
            return file_context_param, None # Already a valid list
        else:
            msg = "Invalid file_context: list must contain only strings."
            return None, format_error_result(create_task_failure(msg, INPUT_VALIDATION_FAILURE))

    if isinstance(file_context_param, str) and file_context_param.strip():
        try:
            loaded_paths = json.loads(file_context_param)
            if not isinstance(loaded_paths, list) or not all(isinstance(p, str) for p in loaded_paths):
                raise ValueError("JSON must be an array of strings.")
            return loaded_paths, None # Parsed successfully
        except (json.JSONDecodeError, ValueError) as e:
            msg = f"Invalid file_context: must be a valid JSON string array. Error: {e}"
            return None, format_error_result(create_task_failure(msg, INPUT_VALIDATION_FAILURE))
    elif isinstance(file_context_param, str) and not file_context_param.strip():
         return None, None # Empty string means no context provided

    # If it's not None, not list, not string -> invalid type
    msg = f"Invalid type for file_context parameter: {type(file_context_param).__name__}. Expected list or JSON string array."
    return None, format_error_result(create_task_failure(msg, INPUT_VALIDATION_FAILURE))

def execute_aider_automatic(params: Dict[str, Any], aider_bridge: AiderBridge) -> TaskResult:
    """Executor for the aider:automatic task."""
    logging.info("Executing Aider Automatic task")
    logging.debug(f"Executor received params: {params}")
    prompt = params.get("prompt", "")

    if not prompt:
        return format_error_result(create_task_failure(
            "Missing required parameter: prompt", INPUT_VALIDATION_FAILURE
        ))

    file_context_param = params.get("file_context")
    file_paths, error_result = _parse_file_context(file_context_param)
    if error_result:
        return error_result

    logging.debug(f"Calling Aider Automatic with prompt='{prompt[:50]}...', file_paths={file_paths}")
    try:
        # Call the AiderBridge method - IT should return TaskResult format directly
        result = aider_bridge.execute_automatic_task(prompt=prompt, file_context=file_paths)
        
        # Return the bridge result directly without adding notes
        return result
    except Exception as e:
        logging.exception("Error during Aider automatic execution:")
        return format_error_result(create_task_failure(f"Aider execution failed: {str(e)}", UNEXPECTED_ERROR))

def execute_aider_interactive(params: Dict[str, Any], aider_bridge: AiderBridge) -> TaskResult:
    """Executor for the aider:interactive task."""
    logging.info("Executing Aider Interactive task")
    logging.debug(f"Executor received params: {params}")
    
    # Check for query parameter first, then fall back to prompt
    query = params.get("query", "")
    if not query:
        query = params.get("prompt", "")  # Fall back to prompt parameter
    
    if not query:
        return format_error_result(create_task_failure(
            "Missing required parameter: query or prompt", INPUT_VALIDATION_FAILURE
        ))

    file_context_param = params.get("file_context")
    file_paths, error_result = _parse_file_context(file_context_param)
    if error_result:
        return error_result

    logging.debug(f"Calling Aider Interactive with query='{query[:50]}...', file_paths={file_paths}")
    try:
        # Call the AiderBridge method - IT should return TaskResult format directly
        result = aider_bridge.start_interactive_session(query=query, file_context=file_paths)
        
        # Return the bridge result directly without adding notes
        return result
    except Exception as e:
        logging.exception("Error during Aider interactive session start:")
        return format_error_result(create_task_failure(f"Aider session failed: {str(e)}", UNEXPECTED_ERROR))
