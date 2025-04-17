import json
import logging
from typing import Dict, Any, List, Optional

# Assuming AiderBridge is importable
try:
    from aider_bridge.bridge import AiderBridge
except ImportError:
    # Allow tests to run even if aider isn't fully installed
    class AiderBridge:
        def execute_automatic_task(self, prompt: str, file_paths: Optional[List[str]] = None):
            raise NotImplementedError("AiderBridge mock used")
        def start_interactive_session(self, query: str, file_paths: Optional[List[str]] = None):
            raise NotImplementedError("AiderBridge mock used")

from system.errors import create_task_failure, format_error_result, INPUT_VALIDATION_FAILURE, UNEXPECTED_ERROR

# Define TaskResult type hint
TaskResult = Dict[str, Any]

def execute_aider_automatic(params: Dict[str, Any], aider_bridge: AiderBridge) -> TaskResult:
    """Executor for the aider:automatic task."""
    logging.info("Executing Aider Automatic task")
    prompt = params.get("prompt")

    if not prompt:
        return format_error_result(create_task_failure(
            "Missing required parameter: prompt", INPUT_VALIDATION_FAILURE
        ))

    file_context_param = params.get("file_context") # Get the param value
    file_paths: Optional[List[str]] = None

    if isinstance(file_context_param, list):
        # Already parsed list by REPL or dispatcher
        if all(isinstance(p, str) for p in file_context_param):
            file_paths = file_context_param
            logging.debug("Using pre-parsed list for file context: %s", file_paths)
        else:
            # List contains non-strings, which is invalid
            return format_error_result(create_task_failure(
                "Invalid file_context: list must contain only strings.", INPUT_VALIDATION_FAILURE
            ))
    elif isinstance(file_context_param, str) and file_context_param.strip():
        # It's a string, attempt to parse as JSON (fallback or direct API call case)
        try:
            loaded_paths = json.loads(file_context_param)
            if not isinstance(loaded_paths, list) or not all(isinstance(p, str) for p in loaded_paths):
                raise ValueError("file_context string must represent a JSON array of file paths.")
            file_paths = loaded_paths
            logging.debug(f"Parsed file_context JSON string: {file_paths}")
        except json.JSONDecodeError:
             return format_error_result(create_task_failure(
                "Invalid JSON format for file_context parameter string.", INPUT_VALIDATION_FAILURE
             ))
        except ValueError as e:
             return format_error_result(create_task_failure(str(e), INPUT_VALIDATION_FAILURE))
    elif file_context_param is not None:
         # It's some other type, which is invalid
         return format_error_result(create_task_failure(
             f"Invalid type for file_context parameter: {type(file_context_param).__name__}", INPUT_VALIDATION_FAILURE
         ))
    # else: file_context_param was None or empty string, file_paths remains None

    # Call the AiderBridge method (this part remains the same)
    try:
        result = aider_bridge.execute_automatic_task(prompt, file_paths)
        return result # AiderBridge methods should already return TaskResult format
    except Exception as e:
        logging.exception("Error during Aider automatic execution:")
        return format_error_result(create_task_failure(f"Aider execution failed: {str(e)}", UNEXPECTED_ERROR))


def execute_aider_interactive(params: Dict[str, Any], aider_bridge: AiderBridge) -> TaskResult:
    """Executor for the aider:interactive task."""
    logging.info("Executing Aider Interactive task")
    query = params.get("query")

    if not query:
        return format_error_result(create_task_failure(
            "Missing required parameter: query", INPUT_VALIDATION_FAILURE
        ))

    file_context_param = params.get("file_context") # Get the param value
    file_paths: Optional[List[str]] = None

    if isinstance(file_context_param, list):
        # Already parsed list by REPL or dispatcher
        if all(isinstance(p, str) for p in file_context_param):
            file_paths = file_context_param
            logging.debug("Using pre-parsed list for file context: %s", file_paths)
        else:
            # List contains non-strings, which is invalid
            return format_error_result(create_task_failure(
                "Invalid file_context: list must contain only strings.", INPUT_VALIDATION_FAILURE
            ))
    elif isinstance(file_context_param, str) and file_context_param.strip():
        # It's a string, attempt to parse as JSON (fallback or direct API call case)
        try:
            loaded_paths = json.loads(file_context_param)
            if not isinstance(loaded_paths, list) or not all(isinstance(p, str) for p in loaded_paths):
                raise ValueError("file_context string must represent a JSON array of file paths.")
            file_paths = loaded_paths
            logging.debug(f"Parsed file_context JSON string: {file_paths}")
        except json.JSONDecodeError:
             return format_error_result(create_task_failure(
                "Invalid JSON format for file_context parameter string.", INPUT_VALIDATION_FAILURE
             ))
        except ValueError as e:
             return format_error_result(create_task_failure(str(e), INPUT_VALIDATION_FAILURE))
    elif file_context_param is not None:
         # It's some other type, which is invalid
         return format_error_result(create_task_failure(
             f"Invalid type for file_context parameter: {type(file_context_param).__name__}", INPUT_VALIDATION_FAILURE
         ))
    # else: file_context_param was None or empty string, file_paths remains None

    # Call the AiderBridge method (this part remains the same)
    try:
        result = aider_bridge.start_interactive_session(query, file_paths)
        return result # AiderBridge methods should already return TaskResult format
    except Exception as e:
        logging.exception("Error during Aider interactive session start:")
        return format_error_result(create_task_failure(f"Aider session failed: {str(e)}", UNEXPECTED_ERROR))
