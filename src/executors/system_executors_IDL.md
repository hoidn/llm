// == !! BEGIN IDL TEMPLATE !! ===
// Note: While this IDL defines static functions, the implementation is now an instantiable class
// that receives its dependencies (MemorySystem, FileAccessManager, command_executor) via constructor.
module src.executors.system_executors {

    # @depends_on(src.memory.memory_system.MemorySystem) // For context retrieval
    # @depends_on(src.handler.file_access.FileAccessManager) // For reading/writing/listing files
    # @depends_on(src.handler.command_executor.CommandExecutorFunctions) // For executing shell commands
    # @depends_on(src.handler.base_handler.BaseHandler) // For accessing handler's context methods
    # @depends_on(src.handler.base_handler.BaseHandler) // For accessing handler's context methods

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
        // - memory_system is a valid instance implementing MemorySystem (injected via constructor).
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
        // - Calls `self.memory_system.get_relevant_context_for`.
        // - Extracts file paths from the AssociativeMatchResult.
        // - Formats the success or error result as a TaskResult dictionary.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult if 'query' is missing or empty.")
        // @raises_error(condition="CONTEXT_RETRIEVAL_FAILURE", description="Returned via FAILED TaskResult if MemorySystem call fails.")
        // Expected JSON format for params: { "query": "string", "history": "string" (optional), "target_files": list<string> (optional) }
        // Expected JSON format for success return value: TaskResult structure, content is JSON string array.
        // Expected JSON format for failure return value: TaskResult structure.
        dict<string, Any> execute_get_context(dict<string, Any> params); // Dependency injected via constructor

        // Executor logic for the 'system:read_files' Direct Tool.
        // Reads the content of specified files using FileAccessManager.
        // Preconditions:
        // - params is a dictionary containing:
        //   - 'file_paths': list<string> (required) - List of file paths to read.
        // - file_manager is a valid instance implementing FileAccessManager (injected via constructor).
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
        // - Iterates through the list, calling `self.file_manager.read_file` for each path.
        // - Handles None return from `read_file` (file not found, read error) by skipping and logging.
        // - Concatenates the content of successfully read files.
        // - Formats the success or error result as a TaskResult dictionary.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult if 'file_paths' is missing or not a list.")
        // @raises_error(condition="FileReadError", description="Handled internally by skipping files, full failure only on unexpected exceptions.")
        // Expected JSON format for params: { "file_paths": list<string> }
        // Expected JSON format for success return value: TaskResult structure.
        // Expected JSON format for failure return value: TaskResult structure.
        dict<string, Any> execute_read_files(dict<string, Any> params); // Dependency injected via constructor

        // Executor logic for the 'system:list_directory' Direct Tool.
        // Lists the contents of a specified directory using FileAccessManager.
        // Preconditions:
        // - params is a dictionary containing:
        //   - 'directory_path': string (required) - Path to the directory.
        // - file_manager is a valid instance implementing FileAccessManager (injected via constructor).
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
        // - Calls `self.file_manager.list_directory`.
        // - If `list_directory` returns a list, formats a COMPLETE TaskResult.
        // - If `list_directory` returns an error dictionary, formats a FAILED TaskResult with reason 'tool_execution_error'.
        // - Handles unexpected exceptions during execution.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult if 'directory_path' is missing or invalid.")
        // @raises_error(condition="TOOL_EXECUTION_ERROR", description="Returned via FAILED TaskResult if file_manager.list_directory returns an error.")
        // @raises_error(condition="UNEXPECTED_ERROR", description="Returned via FAILED TaskResult for other unexpected errors.")
        // Expected JSON format for params: { "directory_path": "string" }
        // Expected JSON format for success return value: TaskResult structure, content is JSON string array.
        // Expected JSON format for failure return value: TaskResult structure.
        dict<string, Any> execute_list_directory(dict<string, Any> params); // Dependency injected via constructor

        // Executor logic for the 'system:write_file' Direct Tool.
        // Writes content to a specified file using FileAccessManager.
        // Preconditions:
        // - params is a dictionary containing:
        //   - 'file_path': string (required) - Path to the file.
        //   - 'content': string (required) - Content to write.
        //   - 'overwrite': boolean (optional, default=False) - Whether to overwrite if file exists.
        // - file_manager is a valid instance implementing FileAccessManager (injected via constructor).
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
        // - Calls `self.file_manager.write_file`.
        // - If `write_file` returns true, formats a COMPLETE TaskResult.
        // - If `write_file` returns false, formats a FAILED TaskResult with reason 'tool_execution_error'.
        // - Handles unexpected exceptions during execution.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult if required params are missing/invalid.")
        // @raises_error(condition="TOOL_EXECUTION_ERROR", description="Returned via FAILED TaskResult if file_manager.write_file returns false.")
        // @raises_error(condition="UNEXPECTED_ERROR", description="Returned via FAILED TaskResult for other unexpected errors.")
        // Expected JSON format for params: { "file_path": "string", "content": "string", "overwrite?": boolean }
        // Expected JSON format for success return value: TaskResult structure.
        // Expected JSON format for failure return value: TaskResult structure.
        dict<string, Any> execute_write_file(dict<string, Any> params); // Dependency injected via constructor

        // Executor logic for the 'system:execute_shell_command' Direct Tool.
        // Executes a shell command safely using CommandExecutorFunctions.
        // Preconditions:
        // - params is a dictionary containing:
        //   - 'command': string (required) - The shell command to execute.
        //   - 'cwd': string (optional) - The working directory for the command.
        //   - 'timeout': int (optional, positive) - Timeout in seconds.
        // - command_executor is a valid instance or module providing CommandExecutorFunctions (injected via constructor).
        // Postconditions:
        // - Returns a TaskResult dictionary.
        // - On success ('status'='COMPLETE'):
        //   - 'content' contains the standard output of the command (truncated).
        //   - 'notes' contains 'success' (boolean, true), 'exit_code' (int, 0), 'stdout' (string), 'stderr' (string).
        // - On failure ('status'='FAILED'):
        //   - 'content' contains the standard error or an error message.
        //   - 'notes' contains 'success' (boolean, false), 'exit_code' (int or null), 'stdout', 'stderr', and structured error details (TaskFailureError).
        // Behavior:
        // - Validates that 'command' parameter is present and valid.
        // - Validates optional 'cwd' and 'timeout' parameters if present.
        // - Calls `self.command_executor.execute_command_safely` with the provided parameters.
        // - Formats the success or error result from `execute_command_safely` into a TaskResult dictionary.
        // - Determines appropriate TaskFailureReason (e.g., 'tool_execution_error', 'input_validation_failure', 'execution_timeout') based on the result from `execute_command_safely`.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult if 'command' is missing or invalid, or optional params have wrong type/value.")
        // @raises_error(condition="TOOL_EXECUTION_ERROR", description="Returned via FAILED TaskResult if command execution fails (non-zero exit code).")
        // @raises_error(condition="EXECUTION_TIMEOUT", description="Returned via FAILED TaskResult if command execution times out.")
        // @raises_error(condition="UNEXPECTED_ERROR", description="Returned via FAILED TaskResult for other unexpected errors during execution.")
        // Expected JSON format for params: { "command": "string", "cwd?": "string", "timeout?": "int" }
        // Expected JSON format for return value: TaskResult structure.
        dict<string, Any> execute_shell_command(dict<string, Any> params); // Dependency injected via constructor

        // Executor logic for the 'system:clear_handler_data_context' Direct Tool.
        // Clears the data context within the currently active BaseHandler instance.
        // Preconditions:
        // - `params` is an empty dictionary (no parameters required).
        // - `handler_instance` (injected or available to the executor) is a valid BaseHandler.
        // Postconditions:
        // - Returns a TaskResult dictionary.
        // - On success ('status'='COMPLETE'): 'content' indicates context cleared.
        // - The BaseHandler's internal `data_context` is cleared.
        // Behavior:
        // - Calls `self.handler_instance.clear_data_context()`.
        // - Formats a TaskResult indicating success.
        // @raises_error(None) // Errors from handler call would be caught by Dispatcher
        // Expected JSON format for params: {}
        // Expected JSON format for return value: TaskResult structure.
        dict<string, Any> execute_clear_handler_data_context(dict<string, Any> params);

        // Executor logic for the 'system:prime_handler_data_context' Direct Tool.
        // Primes the data context within the currently active BaseHandler instance.
        // Preconditions:
        // - `params` is a dictionary containing:
        //   - 'query': string (optional) - The search query for associative matching.
        //   - 'initial_files': list<string> (optional) - List of file paths to seed the context.
        // - `handler_instance` (injected or available) is a valid BaseHandler.
        // Postconditions:
        // - Returns a TaskResult dictionary.
        // - On success ('status'='COMPLETE'): 'content' indicates context primed, 'notes' may contain summary or count of items.
        // - On failure ('status'='FAILED'): 'content' contains an error message.
        // - The BaseHandler's internal `data_context` is populated.
        // Behavior:
        // - Extracts 'query' and 'initial_files' from `params`.
        // - Calls `self.handler_instance.prime_data_context(query=query, initial_files=initial_files)`.
        // - Formats a TaskResult based on the success/failure of the priming operation.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult if params are invalid.")
        // Expected JSON format for params: { "query?": "string", "initial_files?": list<string> }
        // Expected JSON format for return value: TaskResult structure.
        dict<string, Any> execute_prime_handler_data_context(dict<string, Any> params);
        // Note: execute_get_context's behavior description might need minor adjustment if its output
        // (AssociativeMatchResult) now contains MatchItems instead of just file paths.
        // The 'content' of its TaskResult would be a JSON string of list<MatchItem>.
    };
};
// == !! END IDL TEMPLATE !! ===
