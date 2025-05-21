// == !! BEGIN IDL TEMPLATE !! ===
module src.memory.memory_system {

    # @depends_on(src.handler.base_handler.BaseHandler) // For invoking tasks via TaskSystem
    # @depends_on(src.task_system.task_system.TaskSystem) // For executing matching tasks
    # @depends_on(src.handler.file_access.FileAccessManager) // For reading file content
    # @depends_on(src.memory.indexers.git_repository_indexer.GitRepositoryIndexer) // For indexing repos
    # @depends_on_type(docs.system.contracts.types.MatchItem)
    # @depends_on_type(docs.system.contracts.types.AssociativeMatchResult)

    // Interface for the Memory System. Manages file metadata and context retrieval.
    interface MemorySystem {

        // Constructor: Initializes the Memory System.
        // Preconditions:
        // - handler is a valid BaseHandler instance.
        // - task_system is a valid TaskSystem instance.
        // - file_access_manager is a valid FileAccessManager instance.
        // - config is an optional dictionary for sharding parameters and other settings.
        // Postconditions:
        // - MemorySystem is initialized with an empty global index (`global_index`).
        // - References to handler, task_system, and file_access_manager are stored.
        // - Sharding configuration (`_config`) is initialized with defaults or values from config.
        // - Sharded index (`_sharded_index`) is initialized as an empty list.
        void __init__(object handler, object task_system, object file_access_manager, optional dict<string, Any> config); // Args represent BaseHandler, TaskSystem, FileAccessManager

        // Retrieves the current global file metadata index.
        // Preconditions: None.
        // Postconditions:
        // - Returns the dictionary mapping absolute file paths to metadata strings.
        dict<string, string> get_global_index();

        // Updates the global file metadata index with new entries.
        // Preconditions:
        // - index is a dictionary mapping absolute file paths to metadata strings. Metadata is used for the 'metadata' matching strategy.
        // - File paths in the index MUST be absolute paths (validation performed).
        // Postconditions:
        // - Entries from the input `index` are added to or update the internal `global_index`.
        // - If sharding is enabled, the internal shards (`_sharded_index`) are recalculated based on the updated `global_index`.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Raised if a non-absolute path is provided.")
        void update_global_index(dict<string, string> index);

        // Enables or disables the use of sharded context retrieval.
        // Preconditions:
        // - enabled is a boolean value.
        // Postconditions:
        // - The internal sharding flag `_config['sharding_enabled']` is set.
        // - If enabling sharding, the internal shards (`_sharded_index`) are calculated/updated based on the current `global_index`.
        void enable_sharding(boolean enabled);

        // Configures parameters for sharded context retrieval.
        // Preconditions:
        // - Parameters (token_size_per_shard, max_shards, token_estimation_ratio, max_parallel_shards) are optional and must be valid types (int, float) if provided.
        // Postconditions:
        // - The corresponding keys in the internal `_config` dictionary are updated.
        // - If sharding is enabled, the internal shards (`_sharded_index`) are recalculated based on the updated configuration and `global_index`.
        void configure_sharding(optional int token_size_per_shard, optional int max_shards, optional float token_estimation_ratio, optional int max_parallel_shards);

        // Retrieves relevant context using a specific description string for matching, bypassing the main query.
        // Deprecated or less common way to get context. `get_relevant_context_for` is preferred.
        // Behavior: Constructs a ContextGenerationInput with the description as the query and calls get_relevant_context_for.
        // Returns: AssociativeMatchResult object.
        async object get_relevant_context_with_description(string query, string context_description);

        // Retrieves relevant context for a task, orchestrating content/metadata retrieval and LLM analysis.
        // This is the primary method for context retrieval.
        // Preconditions:
        // - input_data is a valid ContextGenerationInput object.
        // - TaskSystem and FileAccessManager dependencies must be available.
        // Postconditions:
        // - Returns an AssociativeMatchResult object containing the context summary and a list of `MatchItem` objects.
        // - Returns an error result if dependencies are unavailable, pre-filtering/reading fails, or the LLM task fails.
        // Behavior:
        // 1. Determines the matching strategy ('content' default, or 'metadata' from input_data.matching_strategy).
        // 2. Determines the query string from input_data.
        // 3. (Optional) Performs pre-filtering on stored file paths based on query to get candidate_paths.
        // 4. For the 'content' strategy, inputs_for_llm["file_contents"] is a single string containing the contents of each candidate file (or relevant chunks)
        //    formatted appropriately (e.g., wrapped in tags). Sets task name to "internal:associative_matching_content".
        //    The result of this task should be parsable into `MatchItem`s (e.g., `item_type="file_content"` or `"text_chunk"`).
        // 5. If strategy is 'metadata': Retrieves metadata for candidate_paths from internal index. Packages metadata into `inputs_for_llm`.
        //    Sets task name to "internal:associative_matching_metadata".
        //    The result of this task should be parsable into `MatchItem`s (e.g., `item_type="file_summary"` or similar).
        // 6. Handles potential sharding of content/metadata if applicable.
        // 7. Creates a SubtaskRequest with the determined task name and inputs_for_llm.
        // 8. Calls `task_system.execute_atomic_template(request)`.
        // 9. Parses the `AssociativeMatchResult` (expecting `MatchItem`s in its `matches` field) from the returned TaskResult's `parsedContent`.
        // 10. Returns the AssociativeMatchResult.
        // @raises_error(condition="TASK_FAILURE", reason="dependency_error", description="Handled internally, returns error result if TaskSystem or FileAccessManager is unavailable.")
        // @raises_error(condition="CONTEXT_RETRIEVAL_FAILURE", description="Handled internally, returns error result.")
        // Expected JSON format for input_data: ContextGenerationInput structure.
        // Returns: AssociativeMatchResult object (containing list<MatchItem>).
        async object get_relevant_context_for(object input_data); // Arg represents ContextGenerationInput

        // Indexes a Git repository and updates the global index.
        // Preconditions:
        // - repo_path is a string representing a valid path to a local Git repository.
        // - options is an optional dictionary for indexer configuration (include_patterns, exclude_patterns, max_file_size).
        // Expected JSON format for options: { "include_patterns": list<string>, "exclude_patterns": list<string>, "max_file_size": int }
        // Postconditions:
        // - Instantiates GitRepositoryIndexer with the repo_path.
        // - Configures the indexer based on the provided options.
        // - Calls the indexer's `index_repository` method, passing `self` (the MemorySystem instance).
        // - The indexer updates the MemorySystem's global index via `update_global_index`.
        // - Logs the number of files indexed.
        // Behavior:
        // - Delegates the indexing process to the GitRepositoryIndexer class.
        void index_git_repository(string repo_path, optional dict<string, Any> options);

        // Invariants:
        // - `global_index` is always a dictionary.
        // - `_sharded_index` is always a list of dictionaries if sharding is enabled and index updated.
    };

    // Removed: generate_context_for_memory_system (Absorbed into get_relevant_context_for)

};
// == !! END IDL TEMPLATE !! ===
