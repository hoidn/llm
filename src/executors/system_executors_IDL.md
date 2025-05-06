// == !! BEGIN IDL TEMPLATE !! ===
// Note: While this IDL defines static functions, the implementation is now an instantiable class
// that receives its dependencies (MemorySystem, FileAccessManager, command_executor) via constructor.
module src.executors.system_executors {

    # @depends_on(src.memory.memory_system.MemorySystem) // For context retrieval
    # @depends_on(src.handler.file_access.FileAccessManager) // For reading/writing/listing files
    # @depends_on(src.handler.command_executor.CommandExecutorFunctions) // For executing shell commands

    // Interface aggregating system-level Direct Tool executor functions.
    // These functions are typically registered with a handler (e.g., PassthroughHandler)
    // and invoked programmatically, often via the Dispatcher.
    interface SystemExecutorFunctions {

        // Executor logic for the 'system:get_context' Direct Tool.
        // Retrieves relevant file paths from the MemorySystem.
        // Preconditions:
        // - params is a dictionary containing:
        //   - 'query': string (required) - The search query.
        //   - 'history': string (optional) - Conversation history for context.
        //   - 'target_files': list<string> (optional) - Hint for target files.
        // - memory_system is a valid instance implementing MemorySystem.
        // Postconditions:
        // - Returns a TaskResult dictionary.
        // - On success ('status'='COMPLETE'):
        //   - 'content' contains a JSON string representation of the list of relevant file paths.
        //   - 'notes' contains 'file_paths' (the list itself) and 'context_summary'.
        // - On failure ('status'='FAILED'):
        //   - 'content' contains an error message.
        //   - 'notes' contains error details (TaskFailureError structure).
        // Behavior:
        // - Validates that 'query' parameter is present and non-empty.
        // - Constructs a ContextGenerationInput object from params.
        // - Calls `memory_system.get_relevant_context_for`.
        // - Extracts file paths from the AssociativeMatchResult.
        // - Formats the success or error result as a TaskResult dictionary.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult if 'query' is missing or empty.")
        // @raises_error(condition="CONTEXT_RETRIEVAL_FAILURE", description="Returned via FAILED TaskResult if MemorySystem call fails.")
        // Expected JSON format for params: { "query": "string", "history": "string" (optional), "target_files": list<string> (optional) }
        // Expected JSON format for success return value: TaskResult structure, content is JSON string array.
        // Expected JSON format for failure return value: TaskResult structure.
        dict<string, Any> execute_get_context(dict<string, Any> params, object memory_system); // Second arg represents MemorySystem

        // Executor logic for the 'system:read_files' Direct Tool.
        // Reads the content of specified files using FileAccessManager.
        // Preconditions:
        // - params is a dictionary containing:
        //   - 'file_paths': list<string> (required) - List of file paths to read.
        // - file_manager is a valid instance implementing FileAccessManager.
        // Postconditions:
        // - Returns a TaskResult dictionary.
        // - On success ('status'='COMPLETE'):
        //   - 'content' contains the concatenated content of successfully read files, formatted with delimiters.
        //   - 'notes' contains 'files_read_count' and 'skipped_files' (list of paths that couldn't be read). May contain 'errors' list if non-fatal errors occurred.
        // - On failure ('status'='FAILED'):
        //   - 'content' contains an error message.
        //   - 'notes' contains error details (TaskFailureError structure).
        // Behavior:
        // - Validates that 'file_paths' is a list.
        // - Iterates through the list, calling `file_manager.read_file` for each path.
        // - Handles None return from `read_file` (file not found, read error) by skipping and logging.
        // - Concatenates the content of successfully read files.
        // - Formats the success or error result as a TaskResult dictionary.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult if 'file_paths' is missing or not a list.")
        // @raises_error(condition="FileReadError", description="Handled internally by skipping files, full failure only on unexpected exceptions.")
        // Expected JSON format for params: { "file_paths": list<string> }
        // Expected JSON format for success return value: TaskResult structure.
        // Expected JSON format for failure return value: TaskResult structure.
        dict<string, Any> execute_read_files(dict<string, Any> params, object file_manager); // Second arg represents FileAccessManager

        // Executor logic for the 'system:list_directory' Direct Tool.
        // Lists the contents of a specified directory using FileAccessManager.
        // Preconditions:
        // - params is a dictionary containing:
        //   - 'directory_path': string (required) - Path to the directory.
        // - file_manager is a valid instance implementing FileAccessManager.
        // Postconditions:
        // - Returns a TaskResult dictionary.
        // - On success ('status'='COMPLETE'):
        //   - 'content' contains a JSON string representation of the list of directory contents (file/subdir names).
        //   - 'notes' contains 'directory_contents' (the list itself).
        // - On failure ('status'='FAILED'):
        //   - 'content' contains an error message (e.g., path not found, not a directory, permission denied, validation failure).
        //   - 'notes' contains error details (TaskFailureError structure).
        // Behavior:
        // - Validates that 'directory_path' parameter is present and valid.
        // - Calls `file_manager.list_directory`.
        // - If `list_directory` returns a list, formats a COMPLETE TaskResult.
        // - If `list_directory` returns an error dictionary, formats a FAILED TaskResult with reason 'tool_execution_error'.
        // - Handles unexpected exceptions during execution.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult if 'directory_path' is missing or invalid.")
        // @raises_error(condition="TOOL_EXECUTION_ERROR", description="Returned via FAILED TaskResult if file_manager.list_directory returns an error.")
        // @raises_error(condition="UNEXPECTED_ERROR", description="Returned via FAILED TaskResult for other unexpected errors.")
        // Expected JSON format for params: { "directory_path": "string" }
        // Expected JSON format for success return value: TaskResult structure, content is JSON string array.
        // Expected JSON format for failure return value: TaskResult structure.
        dict<string, Any> execute_list_directory(dict<string, Any> params, object file_manager); // Second arg represents FileAccessManager

        // Executor logic for the 'system:write_file' Direct Tool.
        // Writes content to a specified file using FileAccessManager.
        // Preconditions:
        // - params is a dictionary containing:
        //   - 'file_path': string (required) - Path to the file.
        //   - 'content': string (required) - Content to write.
        //   - 'overwrite': boolean (optional, default=False) - Whether to overwrite if file exists.
        // - file_manager is a valid instance implementing FileAccessManager.
        // Postconditions:
        // - Returns a TaskResult dictionary.
        // - On success ('status'='COMPLETE'):
        //   - 'content' indicates success.
        // - On failure ('status'='FAILED'):
        //   - 'content' contains an error message (e.g., validation failure, write failure).
        //   - 'notes' contains error details (TaskFailureError structure).
        // Behavior:
        // - Validates that 'file_path' and 'content' parameters are present and valid.
        // - Validates 'overwrite' parameter type.
        // - Calls `file_manager.write_file`.
        // - If `write_file` returns true, formats a COMPLETE TaskResult.
        // - If `write_file` returns false, formats a FAILED TaskResult with reason 'tool_execution_error'.
        // - Handles unexpected exceptions during execution.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult if required params are missing/invalid.")
        // @raises_error(condition="TOOL_EXECUTION_ERROR", description="Returned via FAILED TaskResult if file_manager.write_file returns false.")
        // @raises_error(condition="UNEXPECTED_ERROR", description="Returned via FAILED TaskResult for other unexpected errors.")
        // Expected JSON format for params: { "file_path": "string", "content": "string", "overwrite?": boolean }
        // Expected JSON format for success return value: TaskResult structure.
        // Expected JSON format for failure return value: TaskResult structure.
        dict<string, Any> execute_write_file(dict<string, Any> params, object file_manager); // Second arg represents FileAccessManager

        // Executor logic for the 'system:execute_shell_command' Direct Tool.
        // Executes a shell command safely using CommandExecutorFunctions.
        // Preconditions:
        // - params is a dictionary containing:
        //   - 'command': string (required) - The shell command to execute.
        //   - 'cwd': string (optional) - The working directory for the command.
        //   - 'timeout': int (optional) - Timeout in seconds.
        // - command_executor is a valid instance or module providing CommandExecutorFunctions.
        // Postconditions:
        // - Returns a TaskResult dictionary.
        // - On success ('status'='COMPLETE'):
        //   - 'content' contains the standard output of the command (truncated).
        //   - 'notes' contains 'success' (boolean, true), 'exit_code' (int, 0), 'stdout' (string), 'stderr' (string).
        // - On failure ('status'='FAILED'):
        //   - 'content' contains the standard error or an error message.
        //   - 'notes' contains 'success' (boolean, false), 'exit_code' (int or null), 'stdout', 'stderr', and error details.
        // Behavior:
        // - Validates that 'command' parameter is present.
        // - Calls `command_executor.execute_command_safely` with the provided parameters.
        // - Formats the success or error result from `execute_command_safely` into a TaskResult dictionary.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult if 'command' is missing.")
        // @raises_error(condition="COMMAND_EXECUTION_FAILURE", description="Returned via FAILED TaskResult if command execution fails, times out, or is deemed unsafe by the executor.")
        // Expected JSON format for params: { "command": "string", "cwd?": "string", "timeout?": "int" }
        // Expected JSON format for return value: TaskResult structure.
        dict<string, Any> execute_shell_command(dict<string, Any> params, object command_executor); // Second arg represents CommandExecutorFunctions provider
    };
};
// == !! END IDL TEMPLATE !! ===
