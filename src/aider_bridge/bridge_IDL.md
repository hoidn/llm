// == !! BEGIN IDL TEMPLATE !! ===
module src.aider_bridge.bridge {

    # @depends_on(src.memory.memory_system.MemorySystem) // For context retrieval
    # @depends_on(src.handler.file_access.FileAccessManager) // For validating file paths
    // Note: Dependencies on AiderInteractiveSession/AiderAutomaticHandler are factory methods, not direct structural dependencies.
    # @depends_on_resource(type="AiderTool", purpose="Running code editing tasks via aider")
    # @depends_on_resource(type="FileSystem", purpose="Checking file existence")
    # @depends_on_resource(type="Shell", purpose="Checking aider availability via 'which' command")
    interface AiderBridge {

        // Constructor: Initializes the Aider Bridge.
        // Preconditions:
        // - memory_system is a valid MemorySystem instance.
        // - file_access_manager is an optional FileAccessManager instance; a new one is created if None.
        // Postconditions:
        // - Bridge is initialized with MemorySystem and FileAccessManager references.
        // - Internal file context set (`file_context`) and source (`context_source`) are initialized.
        // - Checks for Aider availability (via `which aider` command or Python import) and sets the internal `aider_available` flag. Prints a warning if Aider is not found.
        void __init__(object memory_system, optional object file_access_manager); // Args represent MemorySystem, FileAccessManager

        // Sets the file context explicitly for subsequent Aider operations.
        // Preconditions:
        // - file_paths is a list of strings representing file paths.
        // - source is an optional string indicating the origin ('explicit_specification' or 'associative_matching').
        // Postconditions:
        // - Updates the internal `file_context` set with only the paths that correspond to existing files.
        // - Updates the internal `context_source` string.
        // - Returns a dictionary indicating 'status' ('success' or 'error'), 'file_count' (number of valid files set), and 'context_source'. Includes 'message' on error.
        // Behavior:
        // - Iterates through `file_paths`, checks if each path is a file using `os.path.isfile`.
        // - Logs warnings for non-existent files.
        // - Stores the set of valid, existing file paths internally.
        // Expected JSON format for return value: { "status": "success|error", "file_count": "int", "context_source": "string", "message?": "string" }
        dict<string, Any> set_file_context(list<string> file_paths, optional string source);

        // Retrieves the current file context managed by the bridge.
        // Preconditions: None.
        // Postconditions:
        // - Returns a dictionary containing 'file_paths' (list of strings), 'file_count' (int), and 'context_source' (string or None).
        // Behavior:
        // - Reads the internal `file_context` set and `context_source`.
        // Expected JSON format for return value: { "file_paths": list<string>, "file_count": "int", "context_source": "string" }
        dict<string, Any> get_file_context();

        // Determines and sets relevant file context for a query using the MemorySystem.
        // Preconditions:
        // - query is a non-empty string describing the task or question.
        // Postconditions:
        // - Returns a list of relevant absolute file paths determined by the MemorySystem.
        // - If files are found, updates the internal `file_context` set and sets `context_source` to 'associative_matching'.
        // - Returns an empty list if MemorySystem interaction fails or no relevant files are found.
        // Behavior:
        // - Creates a ContextGenerationInput object for the query.
        // - Calls `memory_system.get_relevant_context_for` to perform associative matching.
        // - Extracts file paths from the AssociativeMatchResult.
        // - Updates internal state if relevant files are found.
        list<string> get_context_for_query(string query);

        // Creates and returns an instance for managing interactive Aider sessions.
        // Preconditions: None.
        // Postconditions:
        // - Imports `AiderInteractiveSession` from `aider_bridge.interactive`.
        // - Returns a new AiderInteractiveSession instance, passing `self` (the bridge) to its constructor.
        // Behavior: Factory method.
        // Returns: AiderInteractiveSession object
        object create_interactive_session();

        // Creates and returns an instance for handling automatic Aider tasks.
        // Preconditions: None.
        // Postconditions:
        // - Imports `AiderAutomaticHandler` from `aider_bridge.automatic`.
        // - Returns a new AiderAutomaticHandler instance, passing `self` (the bridge) to its constructor.
        // Behavior: Factory method.
        // Returns: AiderAutomaticHandler object
        object create_automatic_handler();

        // Executes a single Aider task automatically (convenience method).
        // Preconditions:
        // - prompt is the string instruction for Aider.
        // - file_context is an optional list of explicit file paths to use for this specific task.
        // Postconditions:
        // - Returns a TaskResult dictionary representing the outcome of the automatic execution.
        // Behavior:
        // - Creates an AiderAutomaticHandler instance using `create_automatic_handler`.
        // - Calls the handler's `execute_task` method with the provided prompt and file_context.
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "string", "notes": { ... } }
        dict<string, Any> execute_automatic_task(string prompt, optional list<string> file_context);

        // Starts an interactive Aider session (convenience method).
        // Preconditions:
        // - query is the initial string query/instruction for the session.
        // - file_context is an optional list of explicit file paths to start the session with.
        // Postconditions:
        // - Returns a TaskResult dictionary representing the outcome of the interactive session (e.g., completion status, files modified).
        // Behavior:
        // - Creates an AiderInteractiveSession instance using `create_interactive_session`.
        // - Calls the session's `start_session` method with the provided query and file_context.
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "string", "notes": { ... } }
        dict<string, Any> start_interactive_session(string query, optional list<string> file_context);

        // Executes a code editing operation using the Aider Coder component.
        // This method directly interacts with the Aider library's Coder.
        // Preconditions:
        // - prompt is the string instruction for Aider.
        // - file_context is an optional list of explicit file paths; if None, uses the bridge's current internal context.
        // Postconditions:
        // - Returns a standardized TaskResult dictionary.
        // - 'status' will be 'COMPLETE' if changes were applied or no changes needed, 'error' otherwise.
        // - 'content' provides a summary message.
        // - 'notes' contains 'files_modified' (list of paths) and 'changes' (list of simple change descriptions), and potentially 'error'.
        // Behavior:
        // - Checks if Aider is available (`aider_available` flag).
        // - Determines the final set of file paths (provided context, internal context, or looked up via `get_context_for_query`). Returns error if no files found.
        // - Lazily initializes Aider components (`_initialize_aider_components`) if needed.
        // - Creates an Aider Coder instance (`_get_coder`) configured with the file paths. Returns error if Coder creation fails.
        // - Executes `coder.run` with the prompt.
        // - Extracts the list of edited files from the Coder.
        // - Formats the result into the TaskResult structure. Handles exceptions.
        // @raises_error(condition="AiderNotAvailable", description="Handled internally, returns error TaskResult.")
        // @raises_error(condition="NoFileContext", description="Handled internally, returns error TaskResult.")
        // @raises_error(condition="AiderComponentError", description="Handled internally, returns error TaskResult.")
        // @raises_error(condition="AiderExecutionError", description="Handled internally, returns error TaskResult.")
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "string", "notes": { "files_modified": list<string>, "changes": list<dict>, "error?": "string" } }
        dict<string, Any> execute_code_edit(string prompt, optional list<string> file_context);
    };
};
// == !! END IDL TEMPLATE !! ===
