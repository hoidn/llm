// == !! BEGIN IDL TEMPLATE !! ===
module src.executors.system_executors {

    # @depends_on(src.memory.memory_system.MemorySystem) // For context retrieval
    # @depends_on(src.handler.file_access.FileAccessManager) // For reading files

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
        //   - 'notes' contains error details.
        // Behavior:
        // - Validates that 'query' parameter is present.
        // - Constructs a ContextGenerationInput object from params.
        // - Calls `memory_system.get_relevant_context_for`.
        // - Extracts file paths from the AssociativeMatchResult.
        // - Formats the success or error result as a TaskResult dictionary.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult if 'query' is missing.")
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
        //   - 'notes' contains 'files_read_count' and 'skipped_files' (list of paths that couldn't be read).
        // - On failure ('status'='FAILED'):
        //   - 'content' contains an error message.
        //   - 'notes' contains error details.
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
    };
};
// == !! END IDL TEMPLATE !! ===
