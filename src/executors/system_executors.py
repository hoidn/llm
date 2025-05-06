"""
System-level Direct Tool executor functions.
These functions are typically registered with a handler and
invoked programmatically, often via the Dispatcher.

Implements the functions defined in src/executors/system_executors_IDL.md.
"""

import json
import logging
import os # Needed for basename in read_files delimiter
from typing import Any, Dict, List, Optional, Union

# Import models
from src.system.models import (
    ContextGenerationInput, TaskResult, TaskFailureError,
    TaskFailureReason, AssociativeMatchResult
)
# Import dependencies for type hinting
from src.handler.file_access import FileAccessManager
from src.memory.memory_system import MemorySystem
from src.handler import command_executor

# Define logger for this module
logger = logging.getLogger(__name__)

# Helper function to create a standard FAILED TaskResult dictionary
# Copied from main.py for self-containment, consider moving to a shared utils module later
def _create_failed_result_dict(reason: TaskFailureReason, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Creates a dictionary representing a FAILED TaskResult."""
    error_obj = TaskFailureError(type="TASK_FAILURE", reason=reason, message=message, details=details or {})
    task_result = TaskResult(status="FAILED", content=message, notes={"error": error_obj})
    # Use exclude_none=True to avoid sending null fields if not set
    return task_result.model_dump(exclude_none=True)


class SystemExecutorFunctions:
    """
    Class providing system-level Direct Tool executor functions.
    
    These functions are registered with a handler (e.g., PassthroughHandler)
    and invoked programmatically, often via the Dispatcher.
    
    Requires dependencies to be injected via constructor.
    """
    
    def __init__(self, memory_system: MemorySystem, file_manager: FileAccessManager, command_executor_module: Any):
        """
        Initializes the SystemExecutorFunctions instance with dependencies.
        
        Args:
            memory_system: MemorySystem instance for context retrieval
            file_manager: FileAccessManager instance for file operations
            command_executor_module: Module containing command execution functions
        """
        if not memory_system:
            raise ValueError("MemorySystem dependency is required.")
        if not file_manager:
            raise ValueError("FileAccessManager dependency is required.")
        if not command_executor_module:
            raise ValueError("command_executor module dependency is required.")
            
        self.memory_system = memory_system
        self.file_manager = file_manager
        self.command_executor = command_executor_module
        logger.info("SystemExecutorFunctions instance created with dependencies.")
    
    def execute_get_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executor logic for the 'system:get_context' Direct Tool.
        Retrieves relevant file paths from the MemorySystem.

        Args:
            params: Dictionary containing:
                - 'query': string (required) - The search query.
                - 'history': string (optional) - Conversation history for context.
                - 'target_files': list<string> (optional) - Hint for target files.

        Returns:
            A TaskResult dictionary with:
            - On success: {'status': 'COMPLETE', 'content': JSON string of file paths, 'notes': {...}}
            - On failure: {'status': 'FAILED', 'content': error message, 'notes': {...}}
        """
        # 1. Validate input parameters
        if 'query' not in params:
            error_msg = "Missing required parameter: 'query'"
            logging.error(f"execute_get_context: {error_msg}")
            # Use local helper
            return _create_failed_result_dict("input_validation_failure", error_msg)

        query = params['query']
        # Check if query is None or empty string
        if not query:
            error_msg = "The 'query' parameter cannot be empty or null"
            logging.error(f"execute_get_context: {error_msg}")
            # Use local helper
            return _create_failed_result_dict("input_validation_failure", error_msg)

        # 2. Prepare context input object
        # Use Pydantic model for validation and clarity if desired, but IDL implies dict input
        # For now, construct ContextGenerationInput directly
        context_input_data: Dict[str, Any] = {"query": query}

        # Add optional parameters
        if 'history' in params and params['history']:
            # Assuming history maps to inheritedContext based on ContextGenerationInput v4.0
            context_input_data['inheritedContext'] = params['history']

        if 'target_files' in params and isinstance(params['target_files'], list):
            # How target_files gets used depends on MemorySystem implementation
            # Storing it in 'inputs' seems reasonable based on ContextGenerationInput v4.0
            if 'inputs' not in context_input_data:
                context_input_data['inputs'] = {}
            context_input_data['inputs']['target_files'] = params['target_files']
        elif 'target_files' in params:
             logging.warning("execute_get_context: 'target_files' parameter provided but is not a list. Ignoring.")


        try:
            # Validate the constructed dict against the Pydantic model before passing
            context_input = ContextGenerationInput.model_validate(context_input_data)
        except Exception as validation_err: # Catch Pydantic validation error specifically if possible
            error_msg = f"Input validation failed for ContextGenerationInput: {validation_err}"
            logging.error(f"execute_get_context: {error_msg}")
            # Use local helper
            return _create_failed_result_dict("input_validation_failure", error_msg)


        # 3. Call memory_system to get context
        try:
            logging.debug(f"execute_get_context: Calling memory_system with query: '{query}'")
            # Assuming memory_system.get_relevant_context_for returns AssociativeMatchResult model
            result: AssociativeMatchResult = self.memory_system.get_relevant_context_for(context_input)

            # 4. Extract file paths from the result
            file_paths = []
            if result.matches: # Check if matches list is not None and not empty
                file_paths = [match.path for match in result.matches]

            # 5. Format the successful result
            content = json.dumps(file_paths) # Content is JSON string of paths list
            notes = {
                "file_paths": file_paths, # Notes contain the actual list
                "context_summary": result.context_summary
            }

            # Include error in notes if present in result (as per AssociativeMatchResult model)
            if result.error:
                notes["error"] = result.error
                logging.warning(f"execute_get_context: Memory system reported an error during context retrieval: {result.error}")

            logging.info(f"execute_get_context: Found {len(file_paths)} relevant file(s)")
            # Use .model_dump() for Pydantic v2
            return TaskResult(
                status="COMPLETE",
                content=content,
                notes=notes
            ).model_dump(exclude_none=True)

        except Exception as e:
            # Handle errors from memory system call itself
            error_msg = f"Context retrieval failed: {type(e).__name__}: {e}"
            logging.exception(f"execute_get_context: {error_msg}") # Use logging.exception to include traceback
            # Use local helper
            return _create_failed_result_dict("context_retrieval_failure", error_msg)

    def execute_read_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executor logic for the 'system:read_files' Direct Tool.
        Reads the content of specified files using FileAccessManager.

        Args:
            params: Dictionary containing:
                - 'file_paths': list<string> (required) - List of file paths to read.

        Returns:
            A TaskResult dictionary with:
            - On success: {'status': 'COMPLETE', 'content': concatenated file contents,
                          'notes': {'files_read_count': int, 'skipped_files': List[str]}}
            - On failure: {'status': 'FAILED', 'content': error message,
                          'notes': {'error': error_details}}
        """
        # 1. Validate input parameters
        if 'file_paths' not in params:
            error_msg = "Missing required parameter: 'file_paths'"
            logging.error(f"execute_read_files: {error_msg}")
            # Use local helper
            return _create_failed_result_dict("input_validation_failure", error_msg)

        file_paths = params['file_paths']
        if not isinstance(file_paths, list):
            error_msg = "The 'file_paths' parameter must be a list of strings"
            logging.error(f"execute_read_files: {error_msg}")
            # Use local helper
            return _create_failed_result_dict("input_validation_failure", error_msg)

        # 2. Handle empty file_paths list
        if not file_paths:
            logging.info("execute_read_files: Received empty file_paths list.")
            # Use .model_dump() for Pydantic v2
            return TaskResult(
                status="COMPLETE",
                content="No files specified for reading.",
                notes={
                    "files_read_count": 0,
                    "skipped_files": []
                }
            ).model_dump(exclude_none=True)

        # 3. Process each file
        content_parts = []
        skipped_files = []
        # Use a list to store error messages for consistency
        errors_list: List[str] = []

        for file_path in file_paths:
            if not isinstance(file_path, str) or not file_path:
                 logging.warning(f"execute_read_files: Skipping invalid file path entry: {file_path}")
                 skipped_files.append(str(file_path)) # Add even invalid entries to skipped
                 errors_list.append(f"Invalid path entry skipped: {file_path}")
                 continue

            try:
                # Assuming file_manager.read_file returns Optional[str]
                # FIX: Explicitly pass max_size=None
                file_content: Optional[str] = self.file_manager.read_file(file_path, max_size=None)
                if file_content is not None:
                    # Add a delimiter before the file content, using basename for readability
                    # Use os.path.basename for cross-platform compatibility
                    file_basename = os.path.basename(file_path)
                    delimiter = f"\n--- File: {file_path} ---\n" # Keep full path in delimiter for clarity
                    content_parts.append(f"{delimiter}{file_content}")
                    logging.debug(f"execute_read_files: Successfully read '{file_path}'")
                else:
                    logging.warning(f"execute_read_files: Could not read file (not found or access denied): '{file_path}'")
                    skipped_files.append(file_path)
            except Exception as e:
                # Log unexpected errors from file_manager.read_file but continue processing files
                error_msg = f"Unexpected error reading '{file_path}': {type(e).__name__}: {e}"
                logging.exception(f"execute_read_files: {error_msg}") # Use logging.exception
                skipped_files.append(file_path)
                errors_list.append(error_msg) # Add detailed error message to list

        # 4. Format the result
        files_read = len(file_paths) - len(skipped_files)

        notes = {
            "files_read_count": files_read,
            "skipped_files": skipped_files
        }

        if errors_list:
            # Store errors as a list of strings in notes
            notes["errors"] = errors_list

        if not content_parts:
            # No files were read successfully
            content = "No readable files found or content generated from the specified paths."
            if errors_list:
                 content += f" Errors encountered: {len(errors_list)}"
            logging.warning(f"execute_read_files: No content generated. Files requested: {len(file_paths)}, Skipped: {len(skipped_files)}")
        else:
            # Concatenate all file contents with their delimiters
            # Start with the first delimiter/content without a leading newline
            content = "".join(content_parts).lstrip() # Remove potential leading newline from first delimiter
            content += "\n--- End of Files ---"

        logging.info(f"execute_read_files: Read {files_read} file(s), skipped {len(skipped_files)}")
        # Use .model_dump() for Pydantic v2
        return TaskResult(
            status="COMPLETE", # Still COMPLETE even if some files failed, as the operation itself finished
            content=content,
            notes=notes
        ).model_dump(exclude_none=True)

    def execute_list_directory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executor logic for the 'system:list_directory' Direct Tool.
        Lists the contents of a specified directory using FileAccessManager.

        Args:
            params: Dictionary containing:
                - 'directory_path': string (required) - Path to the directory.

        Returns:
            A TaskResult dictionary.
        """
        # 1. Validate input parameters
        directory_path = params.get('directory_path')
        if not directory_path or not isinstance(directory_path, str):
            error_msg = "Missing or invalid required parameter: 'directory_path' (must be a non-empty string)"
            logger.error(f"execute_list_directory: {error_msg}")
            return _create_failed_result_dict("input_validation_failure", error_msg)

        # 2. Call file_manager method
        try:
            result = self.file_manager.list_directory(directory_path)

            # 3. Process result
            if isinstance(result, list):
                # Success case
                content = json.dumps(result)
                notes = {"directory_contents": result}
                logger.info(f"execute_list_directory: Successfully listed directory '{directory_path}'. Found {len(result)} items.")
                return TaskResult(
                    status="COMPLETE",
                    content=content,
                    notes=notes
                ).model_dump(exclude_none=True)
            elif isinstance(result, dict) and 'error' in result:
                # Failure case reported by file_manager
                error_msg = result.get('error', 'Unknown error listing directory.')
                logger.error(f"execute_list_directory: File manager failed for '{directory_path}': {error_msg}")
                return _create_failed_result_dict("tool_execution_error", error_msg)
            else:
                # Unexpected return type from file_manager
                error_msg = f"Unexpected return type from file_manager.list_directory for '{directory_path}'"
                logger.error(f"execute_list_directory: {error_msg}")
                return _create_failed_result_dict("unexpected_error", error_msg)

        except Exception as e:
            # Handle unexpected errors during the call
            error_msg = f"Unexpected error executing list_directory for '{directory_path}': {type(e).__name__}: {e}"
            logger.exception(f"execute_list_directory: {error_msg}")
            return _create_failed_result_dict("unexpected_error", error_msg)
            
    def execute_shell_command(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executor logic for the 'system:execute_shell_command' Direct Tool.
        Executes a shell command safely using CommandExecutorFunctions.

        Args:
            params: Dictionary containing:
                - 'command': string (required) - The shell command to execute.
                - 'cwd': string (optional) - The working directory for the command.
                - 'timeout': int (optional) - Timeout in seconds.

        Returns:
            A TaskResult dictionary with command execution results or error details.
        """
        # 1. Validate input parameters
        command = params.get('command')
        if not command or not isinstance(command, str):
            error_msg = "Missing or invalid required parameter: 'command' (must be a non-empty string)"
            logger.error(f"execute_shell_command: {error_msg}")
            return _create_failed_result_dict("input_validation_failure", error_msg)
            
        # Extract optional parameters
        cwd = params.get('cwd')
        timeout = params.get('timeout')
        
        # Validate optional parameter types if present
        if cwd is not None and not isinstance(cwd, str):
            error_msg = "Invalid parameter type: 'cwd' must be a string if provided."
            logger.error(f"execute_shell_command: {error_msg}")
            return _create_failed_result_dict("input_validation_failure", error_msg)
        if timeout is not None:
            if not isinstance(timeout, int) or timeout <= 0:
                error_msg = "Invalid parameter type or value: 'timeout' must be a positive integer if provided."
                logger.error(f"execute_shell_command: {error_msg}")
                return _create_failed_result_dict("input_validation_failure", error_msg)
        
        # 2. Call command_executor method
        try:
            # Call the execute_command_safely function from the injected module
            result_dict = self.command_executor.execute_command_safely(
                command=command,
                cwd=cwd,
                timeout=timeout
            )
            
            # 3. Process result
            if result_dict.get('success', False):
                # Command executed successfully
                logger.info(f"Shell command executed successfully: '{command}'")
                return TaskResult(
                    status="COMPLETE",
                    content=result_dict.get('stdout', ''),
                    notes={
                        'success': True,
                        'exit_code': result_dict.get('exit_code', 0),
                        'stdout': result_dict.get('stdout', ''),
                        'stderr': result_dict.get('stderr', '')
                    }
                ).model_dump(exclude_none=True)
            else:
                # Command execution failed
                error_msg = result_dict.get('stderr', '') or result_dict.get('error', 'Unknown command execution error')
                logger.warning(f"Shell command failed: '{command}'. Error: {error_msg}")
                
                # Determine failure reason
                # Check if the error message indicates an unsafe command (based on command_executor logic)
                # This requires knowledge of command_executor's error messages. Assume "Unsafe command" substring for now.
                reason: TaskFailureReason = "tool_execution_error"
                if "Unsafe command" in error_msg:
                    reason = "input_validation_failure"
                # Check for timeout indicators in the error message
                elif "Timeout" in error_msg or "timed out" in error_msg.lower() or "TimeoutExpired" in error_msg:
                    reason = "execution_timeout"
                    
                return TaskResult(
                    status="FAILED",
                    content=error_msg,
                    notes={
                        'success': False,
                        'exit_code': result_dict.get('exit_code'),
                        'stdout': result_dict.get('stdout', ''),
                        'stderr': result_dict.get('stderr', ''),
                        'error': TaskFailureError(
                            type="TASK_FAILURE",
                            reason=reason,
                            message=error_msg
                        ).model_dump(exclude_none=True) # Dump the error model too
                    }
                ).model_dump(exclude_none=True)
                
        except Exception as e:
            # Handle unexpected errors during the call
            error_msg = f"Unexpected error executing command '{command}': {type(e).__name__}: {e}"
            logger.exception(f"execute_shell_command: {error_msg}")
            return _create_failed_result_dict("unexpected_error", error_msg)

    def execute_write_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executor logic for the 'system:write_file' Direct Tool.
        Writes content to a specified file using FileAccessManager.

        Args:
            params: Dictionary containing:
                - 'file_path': string (required) - Path to the file.
                - 'content': string (required) - Content to write.
                - 'overwrite': boolean (optional, default=False) - Whether to overwrite.

        Returns:
            A TaskResult dictionary.
        """
        # 1. Validate input parameters
        file_path = params.get('file_path')
        content = params.get('content') # Content can be empty string, so check for presence
        overwrite = params.get('overwrite', False) # Default to False

        if not file_path or not isinstance(file_path, str):
            error_msg = "Missing or invalid required parameter: 'file_path' (must be a non-empty string)"
            logger.error(f"execute_write_file: {error_msg}")
            return _create_failed_result_dict("input_validation_failure", error_msg)

        if content is None or not isinstance(content, str):
            # Allow empty string, but not None or other types
            error_msg = "Missing or invalid required parameter: 'content' (must be a string)"
            logger.error(f"execute_write_file: {error_msg}")
            return _create_failed_result_dict("input_validation_failure", error_msg)

        if not isinstance(overwrite, bool):
            error_msg = "Invalid parameter type: 'overwrite' must be a boolean"
            logger.error(f"execute_write_file: {error_msg}")
            return _create_failed_result_dict("input_validation_failure", error_msg)

        # 2. Call file_manager method
        try:
            success = self.file_manager.write_file(file_path, content, overwrite=overwrite)

            # 3. Process result
            if success:
                logger.info(f"execute_write_file: Successfully wrote to file '{file_path}'.")
                return TaskResult(
                    status="COMPLETE",
                    content=f"File '{file_path}' written successfully."
                ).model_dump(exclude_none=True)
            else:
                # Failure reported by file_manager (reason should be logged there)
                error_msg = f"Failed to write file '{file_path}'. Check logs for details (e.g., permissions, path safety, overwrite=False)."
                logger.error(f"execute_write_file: {error_msg}")
                # Use tool_execution_error as the reason
                return _create_failed_result_dict("tool_execution_error", error_msg)

        except Exception as e:
            # Handle unexpected errors during the call
            error_msg = f"Unexpected error executing write_file for '{file_path}': {type(e).__name__}: {e}"
            logger.exception(f"execute_write_file: {error_msg}")
            return _create_failed_result_dict("unexpected_error", error_msg)
