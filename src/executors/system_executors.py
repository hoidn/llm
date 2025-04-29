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
# Import FileAccessManager and MemorySystem for type hinting if available/desired
# from src.handler.file_access import FileAccessManager
# from src.memory.memory_system import MemorySystem


class SystemExecutorFunctions:
    """
    Interface aggregating system-level Direct Tool executor functions.

    These functions are typically registered with a handler (e.g., PassthroughHandler)
    and invoked programmatically, often via the Dispatcher.
    """

    @staticmethod
    def execute_get_context(params: Dict[str, Any], memory_system: Any) -> Dict[str, Any]:
        """
        Executor logic for the 'system:get_context' Direct Tool.
        Retrieves relevant file paths from the MemorySystem.

        Args:
            params: Dictionary containing:
                - 'query': string (required) - The search query.
                - 'history': string (optional) - Conversation history for context.
                - 'target_files': list<string> (optional) - Hint for target files.
            memory_system: A valid instance implementing MemorySystem.

        Returns:
            A TaskResult dictionary with:
            - On success: {'status': 'COMPLETE', 'content': JSON string of file paths, 'notes': {...}}
            - On failure: {'status': 'FAILED', 'content': error message, 'notes': {...}}
        """
        # 1. Validate input parameters
        if 'query' not in params:
            error_msg = "Missing required parameter: 'query'"
            logging.error(f"execute_get_context: {error_msg}")
            error_details = TaskFailureError(
                type="TASK_FAILURE",
                # FIX: Use string literal for reason
                reason="input_validation_failure",
                message=error_msg
            )
            # Use .model_dump() for Pydantic v2
            return TaskResult(
                status="FAILED",
                content=error_msg,
                notes={"error": error_details.model_dump(exclude_none=True)}
            ).model_dump(exclude_none=True)

        query = params['query']
        # Check if query is None or empty string
        if not query:
            error_msg = "The 'query' parameter cannot be empty or null"
            logging.error(f"execute_get_context: {error_msg}")
            error_details = TaskFailureError(
                type="TASK_FAILURE",
                # FIX: Use string literal for reason
                reason="input_validation_failure",
                message=error_msg
            )
            return TaskResult(
                status="FAILED",
                content=error_msg,
                notes={"error": error_details.model_dump(exclude_none=True)}
            ).model_dump(exclude_none=True)

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
            error_details = TaskFailureError(
                type="TASK_FAILURE",
                # FIX: Use string literal for reason
                reason="input_validation_failure",
                message=error_msg
            )
            return TaskResult(
                status="FAILED",
                content=error_msg,
                notes={"error": error_details.model_dump(exclude_none=True)}
            ).model_dump(exclude_none=True)


        # 3. Call memory_system to get context
        try:
            logging.debug(f"execute_get_context: Calling memory_system with query: '{query}'")
            # Assuming memory_system.get_relevant_context_for returns AssociativeMatchResult model
            result: AssociativeMatchResult = memory_system.get_relevant_context_for(context_input)

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
            error_details = TaskFailureError(
                type="TASK_FAILURE",
                # FIX: Use string literal for reason
                reason="context_retrieval_failure",
                message=error_msg
            )
            return TaskResult(
                status="FAILED",
                content=error_msg,
                notes={"error": error_details.model_dump(exclude_none=True)}
            ).model_dump(exclude_none=True)

    @staticmethod
    def execute_read_files(params: Dict[str, Any], file_manager: Any) -> Dict[str, Any]:
        """
        Executor logic for the 'system:read_files' Direct Tool.
        Reads the content of specified files using FileAccessManager.

        Args:
            params: Dictionary containing:
                - 'file_paths': list<string> (required) - List of file paths to read.
            file_manager: A valid instance implementing FileAccessManager.

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
            error_details = TaskFailureError(
                type="TASK_FAILURE",
                # FIX: Use string literal for reason
                reason="input_validation_failure",
                message=error_msg
            )
            # Use .model_dump() for Pydantic v2
            return TaskResult(
                status="FAILED",
                content=error_msg,
                notes={"error": error_details.model_dump(exclude_none=True)}
            ).model_dump(exclude_none=True)

        file_paths = params['file_paths']
        if not isinstance(file_paths, list):
            error_msg = "The 'file_paths' parameter must be a list of strings"
            logging.error(f"execute_read_files: {error_msg}")
            error_details = TaskFailureError(
                type="TASK_FAILURE",
                # FIX: Use string literal for reason
                reason="input_validation_failure",
                message=error_msg
            )
            return TaskResult(
                status="FAILED",
                content=error_msg,
                notes={"error": error_details.model_dump(exclude_none=True)}
            ).model_dump(exclude_none=True)

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
                file_content: Optional[str] = file_manager.read_file(file_path, max_size=None)
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

