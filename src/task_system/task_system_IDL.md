// == !! BEGIN IDL TEMPLATE !! ===
module src.memory.memory_system {

    # @depends_on(src.handler.base_handler.BaseHandler) // For context generation LLM calls
    # @depends_on(src.task_system.task_system.TaskSystem) // For mediating context generation
    # @depends_on(src.memory.indexers.git_repository_indexer.GitRepositoryIndexer) // For indexing repos

    // Interface for the Memory System. Manages file metadata and context retrieval.
    interface MemorySystem {

        // Constructor: Initializes the Memory System.
        // Preconditions:
        // - handler is an optional BaseHandler instance (required for context generation).
        // - task_system is an optional TaskSystem instance (required for context generation mediation).
        // - config is an optional dictionary for sharding parameters and other settings.
        // Postconditions:
        // - MemorySystem is initialized with an empty global index (`global_index`).
        // - References to handler and task_system are stored.
        // - Sharding configuration (`_config`) is initialized with defaults or values from config.
        // - Sharded index (`_sharded_index`) is initialized as an empty list.
        void __init__(optional object handler, optional object task_system, optional dict<string, Any> config); // Args represent BaseHandler, TaskSystem

        // Retrieves the current global file metadata index.
        // Preconditions: None.
        // Postconditions:
        // - Returns the dictionary mapping absolute file paths to metadata strings.
        dict<string, string> get_global_index();

        // Updates the global file metadata index with new entries.
        // Preconditions:
        // - index is a dictionary mapping file paths to metadata strings.
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
        // Preconditions:
        // - query is the main task query string (potentially used for logging/metadata but not matching).
        // - context_description is the string to be used for the associative matching process.
        // Postconditions:
        // - Returns an AssociativeMatchResult object.
        // Behavior:
        // - Constructs a simple input dictionary using `context_description` as the 'taskText'.
        // - Calls `get_relevant_context_for` with this constructed input.
        // Returns: AssociativeMatchResult object
        object get_relevant_context_with_description(string query, string context_description);

        // Retrieves relevant context for a task, mediating through the TaskSystem.
        // This is the primary method for context retrieval.
        // Preconditions:
        // - input_data is either a legacy dictionary (containing 'taskText') or a ContextGenerationInput object.
        // - The TaskSystem dependency must be available and correctly configured.
        // Postconditions:
        // - Returns an AssociativeMatchResult object containing the context summary and a list of MatchTuple objects (path, relevance, score).
        // - Returns an error result if TaskSystem is unavailable or context generation fails.
        // Behavior:
        // - Converts legacy dictionary input to ContextGenerationInput if necessary.
        // - Checks if fresh context is disabled; if so, returns inherited context.
        // - If sharding is enabled and applicable, processes shards in parallel using `_process_single_shard`, then aggregates results.
        // - If sharding is disabled or not applicable, calls `_get_relevant_context_with_mediator`.
        // - The mediator method (`_get_relevant_context_with_mediator`) delegates the actual context generation (LLM call) to `TaskSystem.generate_context_for_memory_system`.
        // Behavior:
        // - Receives a `ContextGenerationInput` object.
        // - **Determines Match Query:** Prioritizes `input_data.query` if present (typically from Sexp `get_context`). If `query` is absent, uses `input_data.templateDescription` and relevant `input_data.inputs` (typically from TaskSystem calling for a template).
        // - Checks if fresh context is effectively disabled based on other context factors (e.g., if only `inheritedContext` is provided and no fresh lookup needed based on task settings - logic handled by caller like TaskSystem, MemorySystem just performs match if asked).
        // - Performs associative matching against the `global_index` using the determined match query and potentially `input_data.inheritedContext` / `input_data.previousOutputs` as additional signals.
        // - If sharding is enabled and applicable, processes shards in parallel using `_process_single_shard`, then aggregates results.
        // - If sharding is disabled or not applicable, calls `_get_relevant_context_with_mediator` (delegating actual LLM call for summary to TaskSystem if needed).
        // - Handles exceptions during context generation.
        // - Returns an AssociativeMatchResult object.
        // This method is invoked by the `SexpEvaluator` when processing the `(get_context ...)` S-expression primitive, and by TaskSystem when preparing context for `execute_atomic_template`.
        // @raises_error(condition="TASK_FAILURE", reason="dependency_error", description="Handled internally, returns error result if TaskSystem is unavailable.")
        // @raises_error(condition="CONTEXT_RETRIEVAL_FAILURE", description="Handled internally, returns error result.")
        // Expected JSON format for legacy input_data: { "taskText": "string", ... }
        // Returns: AssociativeMatchResult object.
        object get_relevant_context_for(object input_data); // Arg represents updated ContextGenerationInput

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
};
// == !! END IDL TEMPLATE !! ===
