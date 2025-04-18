"""System-level executors for Direct Tools."""

import logging
import json
from typing import Dict, Any, List, Optional

# Adjust import paths based on actual project structure
from ..memory.memory_system import MemorySystem
from ..handler.file_access import FileAccessManager
from ..handler.command_executor import execute_command_safely
# Assuming TaskResult is defined centrally or importable
# from task_system.spec.types import TaskResult
TaskResult = Dict[str, Any]  # Placeholder if direct import fails
from ..system.errors import create_task_failure, format_error_result, INPUT_VALIDATION_FAILURE, UNEXPECTED_ERROR
from ..memory.context_generation import ContextGenerationInput, AssociativeMatchResult

logger = logging.getLogger(__name__)


def execute_get_context(params: Dict[str, Any], memory_system: MemorySystem) -> TaskResult:
    """
    Executor logic for the 'system:get_context' Direct Tool.
    Retrieves relevant file paths from the MemorySystem based on query, history, and hints.
    
    Args:
        params: Dictionary containing parameters:
            - query: The search query string (required)
            - history: Optional history string for context
            - target_files: Optional list of target files hint
        memory_system: MemorySystem instance to use for context retrieval
        
    Returns:
        TaskResult dictionary with status, content, and notes
    """
    logger.info("Executing system:get_context tool")
    logger.debug(f"Received params: {params}")
    try:
        query = params.get("query")
        history = params.get("history")  # Optional history string
        target_files = params.get("target_files")  # Optional list of target files hint

        if not query:
            # Return a FAILED TaskResult using error utilities
            err = create_task_failure("Missing required parameter: query", INPUT_VALIDATION_FAILURE)
            return format_error_result(err)

        # Construct ContextGenerationInput
        context_input = ContextGenerationInput(
            template_description=query,
            inputs={"query": query, "target_files_hint": target_files},  # Pass hints if MemorySystem uses them
            history_context=history
            # Defaults for other fields like fresh_context are likely fine here
        )

        logger.debug(f"Calling memory_system.get_relevant_context_for with query='{query[:50]}...', history_present={bool(history)}")
        context_result: AssociativeMatchResult = memory_system.get_relevant_context_for(context_input)

        # Extract file paths (result.matches is List[Tuple[str, str, Optional[float]]])
        file_paths = [match[0] for match in context_result.matches if isinstance(match, (list, tuple)) and len(match) > 0]
        logger.info(f"Found {len(file_paths)} relevant files via MemorySystem.")

        # Return paths as JSON string in content for easy parsing by LLM/templates
        # Also include the list in notes for programmatic access if needed later
        return {
            "status": "COMPLETE",
            "content": json.dumps(file_paths),
            "notes": {
                "file_paths": file_paths,
                "context_summary": context_result.context
            }
        }

    except Exception as e:
        logger.exception("Error in execute_get_context:")
        error = create_task_failure(f"Failed to get context: {str(e)}", UNEXPECTED_ERROR)
        return format_error_result(error)


def execute_read_files(params: Dict[str, Any], file_manager: FileAccessManager) -> TaskResult:
    """
    Executor logic for the 'system:read_files' Direct Tool.
    Reads content of specified files using the FileAccessManager.
    
    Args:
        params: Dictionary containing parameters:
            - file_paths: List of file paths to read (required)
        file_manager: FileAccessManager instance to use for file reading
        
    Returns:
        TaskResult dictionary with status, content, and notes
    """
    logger.info("Executing system:read_files tool")
    logger.debug(f"Received params: {params}")
    try:
        file_paths = params.get("file_paths")

        if not isinstance(file_paths, list):
            # Return a FAILED TaskResult
            err = create_task_failure("Missing or invalid parameter: file_paths (must be a list)", INPUT_VALIDATION_FAILURE)
            return format_error_result(err)

        content_snippets = []
        skipped_files = []
        read_count = 0

        for path in file_paths:
            if not isinstance(path, str):
                logger.warning(f"Skipping invalid path type in list: {type(path)}")
                skipped_files.append(f"<invalid_type: {type(path).__name__}>")
                continue

            logger.debug(f"Attempting to read file: {path}")
            # Use the passed file_manager instance
            content = file_manager.read_file(path)  # Assumes read_file handles its own errors/None return

            if content is not None:
                # Format content clearly for the LLM context
                snippet = f"--- START FILE: {path} ---\n{content}\n--- END FILE: {path} ---"
                content_snippets.append(snippet)
                read_count += 1
            else:
                logger.warning(f"Could not read file or file empty, skipping: {path}")
                skipped_files.append(path)  # Record skipped file

        logger.info(f"Read {read_count} files, skipped {len(skipped_files)}.")
        concatenated_content = "\n\n".join(content_snippets)

        return {
            "status": "COMPLETE",
            "content": concatenated_content,
            "notes": {
                "files_read_count": read_count,
                "skipped_files": skipped_files
            }
        }

    except Exception as e:
        logger.exception("Error in execute_read_files:")
        error = create_task_failure(f"Failed to read files: {str(e)}", UNEXPECTED_ERROR)
        return format_error_result(error)


def execute_run_script(params: Dict[str, Any]) -> TaskResult:
    """
    Executor logic for the 'system:run_script' Direct Tool.
    Executes a shell command safely and returns its output.

    Args:
        params: Dictionary containing parameters:
            - command: The shell command string to execute (required).
            - cwd: Optional current working directory for the command.
            - timeout: Optional timeout in seconds.

    Returns:
        TaskResult dictionary with status, content, and notes containing scriptOutput.
    """
    logger.info("Executing system:run_script tool")
    logger.debug(f"Received params: {params}")
    try:
        command = params.get("command")
        cwd = params.get("cwd") # Optional
        timeout = params.get("timeout") # Optional

        if not command or not isinstance(command, str):
            err = create_task_failure("Missing or invalid required parameter: command (must be a string)", INPUT_VALIDATION_FAILURE)
            return format_error_result(err)

        # Optional timeout validation
        if timeout is not None:
            try:
                timeout = int(timeout)
                if timeout <= 0:
                    raise ValueError("Timeout must be positive.")
            except (ValueError, TypeError):
                 err = create_task_failure("Invalid parameter: timeout (must be a positive integer)", INPUT_VALIDATION_FAILURE)
                 return format_error_result(err)

        logger.debug(f"Running command: '{command}' with timeout={timeout}, cwd={cwd}")

        # Use the safe command execution utility
        # Pass timeout only if it was provided and validated
        exec_kwargs = {}
        if cwd: exec_kwargs["cwd"] = cwd
        if timeout: exec_kwargs["timeout"] = timeout
        safe_result = execute_command_safely(command, **exec_kwargs)

        # Format the result into TaskResult standard, embedding safe_result in notes
        # NOTE: This structure is crucial for the debug:loop template's evaluator step
        script_output = {
            "stdout": safe_result.get("output", ""),
            "stderr": safe_result.get("error", ""),
            "exit_code": safe_result.get("exit_code", -1)
        }
        
        if safe_result["success"]:
             logger.info("system:run_script executed successfully.")
             status = "COMPLETE"
             # Content can be stdout or a summary message
             content = f"Command executed. Exit code: {script_output['exit_code']}."
        else:
             logger.warning(f"system:run_script failed. Exit code: {script_output['exit_code']}, Error: {script_output['stderr'][:100]}...")
             status = "FAILED"
             content = f"Command failed. Exit code: {script_output['exit_code']}. Error: {script_output['stderr']}"

        return {
            "status": status,
            "content": content,
            "notes": {
                "scriptOutput": script_output # Key expected by debug:loop evaluator
            }
        }

    except Exception as e:
        logger.exception("Error in execute_run_script:")
        error = create_task_failure(f"Failed to run script: {str(e)}", UNEXPECTED_ERROR)
        return format_error_result(error)
