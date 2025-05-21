// == !! BEGIN IDL TEMPLATE !! ===
module src.main {

    # @depends_on(src.memory.memory_system.MemorySystem)
    # @depends_on(src.task_system.task_system.TaskSystem)
    # @depends_on(src.handler.passthrough_handler.PassthroughHandler)
    # @depends_on(src.handler.file_access.FileAccessManager) // ADDED
    # @depends_on(src.aider_bridge.bridge.AiderBridge) // Depends on the REFACRORED AiderBridge (MCP Client)
    # @depends_on(src.memory.indexers.git_repository_indexer.GitRepositoryIndexer)
    # @depends_on(src.executors.aider_executors.AiderExecutorFunctions) // Indirectly via initialize_aider
    # @depends_on(src.executors.system_executors.SystemExecutorFunctions) // Indirectly via _register_system_tools

    // Interface for the main Application class, coordinating system components.
    interface Application {

        // Constructor: Initializes the core application components.
        // Preconditions:
        // - config is an optional configuration dictionary.
        // Postconditions:
        // - Core components (FileAccessManager, TaskSystem, PassthroughHandler, MemorySystem) are instantiated and dependencies wired.
        // - Crucially, the internal `pydantic-ai Agent` within the LLMInteractionManager (inside the Handler)
        //   is **only initialized at the end of this constructor**, after all tools are registered.
        // - Core task templates (e.g., associative matching) are registered with TaskSystem.
        // - System tools (e.g., system:get_context) are registered with the Handler.
        // - Provider-specific tools (e.g., Anthropic Editor) are conditionally registered with the Handler.
        // - `indexed_repositories` list is initialized.
        // Behavior: Follows this specific initialization sequence:
        //   1. Instantiate `FileAccessManager`.
        //   2. Instantiate `TaskSystem`.
        //   3. Instantiate `PassthroughHandler` (passing TaskSystem, MemorySystem=None, FileManager). Handler internally instantiates `LLMInteractionManager` (agent=None).
        //   4. Instantiate `MemorySystem` (passing Handler, TaskSystem, FileManager).
        //   5. Wire dependencies: Set `handler.memory_system = memory_system`, `task_system.memory_system = memory_system`, `task_system.set_handler(handler)`.
        //   6. Register core templates with `task_system`.
        //   7. Call internal `_register_system_tools` which registers tools with `handler`.
        //   8. **(Phase 7 Logic Placeholder)** Check `handler.get_provider_identifier()` and conditionally register provider-specific tools with `handler`.
        //   9. Retrieve the complete list of tools for the agent: `agent_tools = handler.get_tools_for_agent()`.
        //   10. **Trigger agent initialization**: Call `handler.llm_manager.initialize_agent(tools=agent_tools)`.
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
        // - `__init__` must have completed successfully (including agent initialization).
        // - query is a non-empty string from the user.
        // Postconditions:
        // - Returns a `TaskResult` Pydantic model instance containing the response from the PassthroughHandler.
        // - Returns an error dictionary if the handler fails unexpectedly.
        // Behavior:
        // - Delegates the query directly to `passthrough_handler.handle_query`.
        // - Catches potential exceptions during handling.
        // Expected JSON format for return value: TaskResult Pydantic model instance (or error dict if handler fails unexpectedly).
        object handle_query(string query);

        // Resets the conversation state within the PassthroughHandler.
        // Preconditions: None.
        // Postconditions:
        // - The conversation history in the `passthrough_handler` is cleared.
        // Behavior:
        // - Calls `passthrough_handler.reset_conversation()`.
        void reset_conversation();


        // Note: The main() function and private methods like _register_system_tools
        // are part of the application's execution logic, not its public interface contract,
        // and are therefore excluded from this IDL.
    };
};
// == !! END IDL TEMPLATE !! ===
