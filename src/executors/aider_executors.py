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
    file_context_str = params.get("file_context")
    file_paths: Optional[List[str]] = None

    if not prompt:
        return format_error_result(create_task_failure(
            "Missing required parameter: prompt", INPUT_VALIDATION_FAILURE
        ))

    if file_context_str:
        try:
            loaded_paths = json.loads(file_context_str)
            if not isinstance(loaded_paths, list) or not all(isinstance(p, str) for p in loaded_paths):
                raise ValueError("file_context must be a JSON string array of file paths.")
            file_paths = loaded_paths
            logging.debug(f"Using explicit file context: {file_paths}")
        except json.JSONDecodeError:
             return format_error_result(create_task_failure(
                "Invalid JSON format for file_context parameter.", INPUT_VALIDATION_FAILURE
             ))
        except ValueError as e:
             return format_error_result(create_task_failure(str(e), INPUT_VALIDATION_FAILURE))

    try:
        # Call the AiderBridge method
        # Pass file_paths=None if not provided, bridge handles finding context then
        result = aider_bridge.execute_automatic_task(prompt, file_paths)
        return result # AiderBridge methods should already return TaskResult format
    except Exception as e:
        logging.exception("Error during Aider automatic execution:")
        return format_error_result(create_task_failure(f"Aider execution failed: {str(e)}", UNEXPECTED_ERROR))


def execute_aider_interactive(params: Dict[str, Any], aider_bridge: AiderBridge) -> TaskResult:
    """Executor for the aider:interactive task."""
    logging.info("Executing Aider Interactive task")
    query = params.get("query")
    file_context_str = params.get("file_context")
    file_paths: Optional[List[str]] = None

    if not query:
        return format_error_result(create_task_failure(
            "Missing required parameter: query", INPUT_VALIDATION_FAILURE
        ))

    if file_context_str:
        try:
            loaded_paths = json.loads(file_context_str)
            if not isinstance(loaded_paths, list) or not all(isinstance(p, str) for p in loaded_paths):
                raise ValueError("file_context must be a JSON string array of file paths.")
            file_paths = loaded_paths
            logging.debug(f"Using explicit file context for interactive session: {file_paths}")
        except json.JSONDecodeError:
             return format_error_result(create_task_failure(
                "Invalid JSON format for file_context parameter.", INPUT_VALIDATION_FAILURE
             ))
        except ValueError as e:
             return format_error_result(create_task_failure(str(e), INPUT_VALIDATION_FAILURE))

    try:
        # Call the AiderBridge method
        # Pass file_paths=None if not provided, bridge handles finding context then
        result = aider_bridge.start_interactive_session(query, file_paths)
        return result # AiderBridge methods should already return TaskResult format
    except Exception as e:
        logging.exception("Error during Aider interactive session start:")
        return format_error_result(create_task_failure(f"Aider session failed: {str(e)}", UNEXPECTED_ERROR))
