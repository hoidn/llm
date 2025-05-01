// == !! BEGIN IDL TEMPLATE !! ===
module src.main {

    # @depends_on(src.memory.memory_system.MemorySystem)
    # @depends_on(src.task_system.task_system.TaskSystem)
    # @depends_on(src.handler.passthrough_handler.PassthroughHandler)
    # @depends_on(src.handler.file_access.FileAccessManager) // ADDED
    # @depends_on(src.aider_bridge.bridge.AiderBridge)
    # @depends_on(src.memory.indexers.git_repository_indexer.GitRepositoryIndexer)
    # @depends_on(src.executors.aider_executors.AiderExecutorFunctions) // Indirectly via initialize_aider
    # @depends_on(src.executors.system_executors.SystemExecutorFunctions) // Indirectly via _register_system_tools

    // Interface for the main Application class, coordinating system components.
    interface Application {

        // Constructor: Initializes the core application components.
        // Preconditions:
        // - config is an optional configuration dictionary.
        // Postconditions:
        // - Initializes FileAccessManager, MemorySystem, TaskSystem, and PassthroughHandler instances.
        // - Establishes necessary dependencies between core components (e.g., MemorySystem gets TaskSystem/Handler/FileManager refs, TaskSystem gets Handler ref).
        // - Registers core task templates with TaskSystem, including **two** associative matching templates: "internal:associative_matching_content" and "internal:associative_matching_metadata".
        //   (Note: The 'internal:associative_matching_content' template uses a simple `{{file_contents}}` placeholder due to limitations in the AtomicTaskExecutor's substitution mechanism).
        // - Calls `initialize_aider` to set up AiderBridge and register Aider tools/executors.
        //   (Note: Aider registration might depend on Handler initialization).
        // - Calls internal `_register_system_tools` to register 'system:get_context' and 'system:read_files' tools and their executor functions using `handler.register_tool(...)`.
        // - Initializes `indexed_repositories` list.
        void __init__(optional dict<string, Any> config);

        // Indexes a local Git repository and updates the MemorySystem's global index.
        // Preconditions:
        // - repo_path is a string representing a valid path to the **root directory** of a local Git repository (i.e., the directory containing the '.git' subdirectory).
        // - options is an optional dictionary for indexer configuration.
        // Expected JSON format for options: { "include_patterns": list<string>, "exclude_patterns": list<string>, "max_file_size": int }
        // Postconditions:
        // - Returns true if indexing completes successfully.
        // - Returns false if the path is invalid, not a git repo root, or indexing fails.
        // - If successful, the MemorySystem's global index is updated with metadata from the repository's files.
        // - The scope of indexed files is determined by the `include_patterns` and `exclude_patterns` provided in the `options` dictionary (relative to `repo_path`).
        // - The absolute path of the indexed repository root is added to the internal `indexed_repositories` list.
        // Behavior:
        // - Normalizes and validates the `repo_path`, ensuring it contains a '.git' directory.
        // - Instantiates `GitRepositoryIndexer` with the validated `repo_path`.
        // - Configures the indexer using the provided `options` (e.g., setting include/exclude patterns).
        // - Calls `indexer.index_repository`, passing the application's `memory_system` instance.
        // - **Note:** To index only a subdirectory (e.g., 'src'), provide the repository root as `repo_path` and use `options={'include_patterns': ['src/**/*']}` (adjust pattern as needed).
        // @raises_error(condition="InvalidPath", description="Handled internally, returns false.")
        // @raises_error(condition="NotGitRepository", description="Handled internally, returns false if .git directory is missing at repo_path.")
        // @raises_error(condition="IndexingError", description="Handled internally, returns false.")
        boolean index_repository(string repo_path, optional dict<string, Any> options);

        // Handles a user query using the PassthroughHandler.
        // Preconditions:
        // - query is a non-empty string from the user.
        // Postconditions:
        // - Returns a TaskResult dictionary containing the response from the PassthroughHandler.
        // - Returns an error dictionary if the handler fails unexpectedly.
        // Behavior:
        // - Delegates the query directly to `passthrough_handler.handle_query`.
        // - Catches potential exceptions during handling.
        // Expected JSON format for return value: TaskResult structure or error dict { "content": "error string", "metadata": { "error": "string" } }
        dict<string, Any> handle_query(string query);

        // Resets the conversation state within the PassthroughHandler.
        // Preconditions: None.
        // Postconditions:
        // - The conversation history in the `passthrough_handler` is cleared.
        // Behavior:
        // - Calls `passthrough_handler.reset_conversation()`.
        void reset_conversation();

        // Initializes the AiderBridge component and registers associated tools and executors.
        // Preconditions:
        // - Core components (MemorySystem, PassthroughHandler) must be initialized.
        // Postconditions:
        // - Instantiates `AiderBridge` if not already done and stores it in `aider_bridge`.
        // - If AiderBridge initializes successfully (Aider is available):
        //   - Registers Aider tools ('aiderInteractive', 'aiderAutomatic') and their corresponding executor functions (wrapping `execute_aider_automatic`, `execute_aider_interactive` to pass the `aider_bridge` instance) with the PassthroughHandler using `handler.register_tool(...)`.
        // - Logs success or failure messages related to Aider initialization and registration.
        // Behavior:
        // - Performs lazy initialization of `aider_bridge`.
        // - Uses helper functions from `aider_bridge.tools` and `executors.aider_executors`.
        void initialize_aider();

        // Note: The main() function and private methods like _register_system_tools
        // are part of the application's execution logic, not its public interface contract,
        // and are therefore excluded from this IDL.
    };
};
// == !! END IDL TEMPLATE !! ===
