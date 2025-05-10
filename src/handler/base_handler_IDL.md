// == !! BEGIN IDL TEMPLATE !! ===
module src.handler.base_handler {

    # @depends_on(src.task_system.task_system.TaskSystem, src.memory.memory_system.MemorySystem) // Core system components
    # @depends_on_resource(type="LLMAgentService", purpose="Orchestrating LLM calls via pydantic-ai") // Represents the configured pydantic-ai agent
    # @depends_on(src.handler.file_access.FileAccessManager) // For file operations
    # @depends_on(src.handler.command_executor.CommandExecutorFunctions) // For safe command execution
    # @depends_on(src.handler.llm_interaction_manager.LLMInteractionManager) // For managing pydantic-ai interactions
    # @depends_on(src.handler.file_context_manager.FileContextManager) // For managing file context operations
    # @depends_on_type(docs.system.contracts.types.DataContext)
    # @depends_on_type(docs.system.contracts.types.MatchItem)
    # @depends_on_type(docs.system.contracts.types.AssociativeMatchResult)

    interface BaseHandler {

        // Constructor: Initializes the base handler.
        // Preconditions:
        // - task_system is a valid TaskSystem instance.
        // - memory_system is a valid MemorySystem instance.
        // - default_model_identifier is an optional string identifying the pydantic-ai model (e.g., "anthropic:claude-3-5-sonnet-latest").
        // - config is an optional dictionary for configuration settings (e.g., base_system_prompt, API keys for pydantic-ai).
        // Postconditions:
        // - Handler is initialized with references to core systems (TaskSystem, MemorySystem).
        // - LLMInteractionManager is instantiated with the default_model_identifier and config.
        //   The underlying `pydantic-ai Agent` within the manager is **not** created at this time;
        //   its initialization is deferred until triggered by `Application` after tool registration.
        // - FileContextManager is instantiated with the memory_system.
        // - FileAccessManager is instantiated.
        // - Tool registries (registered_tools, tool_executors) are initialized as empty dictionaries.
        // - Internal `data_context` is initialized to an empty state (e.g., None).
        // - Conversation history is initialized as an empty list.
        // - Base system prompt is set from config or default.
        // - Debug mode is initialized to false.
        void __init__(
            object task_system, // Represents TaskSystem instance
            object memory_system, // Represents MemorySystem instance
            optional string default_model_identifier, // e.g., "anthropic:claude-3-5-sonnet-latest"
            optional dict<string, Any> config
        );

        // Registers a tool specification and its executor function for LLM use.
        // Preconditions:
        // - tool_spec is a dictionary containing 'name', 'description', 'input_schema'.
        // - executor_func is a callable function that implements the tool's logic, typically accepting a dictionary based on input_schema and returning a TaskResult-like dictionary.
        // Expected JSON format for tool_spec: { "name": "string", "description": "string", "input_schema": { ... } }
        // Postconditions:
        // - The tool specification and executor are stored in the internal registries.
        // - The `tool_executors` dictionary (keyed by name) is updated for direct programmatic access.
        // - Returns true if registration is successful (tool_spec has a name).
        // - Returns false if registration fails (e.g., missing name in tool_spec).
        // Behavior:
        // - This is the single, unified method for registering any callable action (tool).
        // - Stores the executor_func in `tool_executors` for direct programmatic invocation.
        // - Stores the tool_spec in `registered_tools` for reference.
        // - **Tool Availability Strategy:**
        //   - Model-Agnostic (Generic) Tools (e.g., file access, system commands, Aider via MCP client): Registered unconditionally. The LLMInteractionManager makes these available to any configured pydantic-ai Agent.
        //   - Provider-Specific Tools (e.g., Anthropic Editor): Require conditional registration logic (typically during Application/Handler init). These tools should only be registered if the LLMInteractionManager is configured with a compatible provider/agent.
        // - Note: Making dynamically registered tools available to a *live* pydantic-ai Agent during its execution run can be complex and may require passing them explicitly during the LLM call or agent re-initialization.
        boolean register_tool(dict<string, Any> tool_spec, function executor_func);

        // Executes a shell command expected to output file paths and parses the result.
        // Preconditions:
        // - command is a string containing the shell command to execute.
        // Postconditions:
        // - Returns a list of absolute file paths extracted from the command's standard output, filtered for existence.
        // - Returns an empty list if the command fails, times out, is unsafe, or produces no valid, existing file paths.
        // Behavior:
        // - Delegates execution to `command_executor.execute_command_safely`.
        // - If execution is successful (exit code 0), delegates parsing to `command_executor.parse_file_paths_from_output`.
        // @raises_error(condition="CommandExecutionFailed", description="Handled internally, returns empty list.")
        list<string> execute_file_path_command(string command);

        // Resets the internal conversation history AND data context.
        // Preconditions: None.
        // Postconditions:
        // - The `conversation_history` list is cleared.
        // - The internal `data_context` (holding `MatchItem`s) is reset to an empty state.
        // - May also reset state within the LLMInteractionManager if necessary.
        void reset_conversation();

        // Logs a debug message if debug mode is enabled.
        // Preconditions:
        // - message is a string.
        // Postconditions:
        // - If `debug_mode` is true, the message is printed to the console/logger prefixed with '[DEBUG]'.
        void log_debug(string message);

        // Enables or disables the internal debug logging flag.
        // Preconditions:
        // - enabled is a boolean value.
        // Postconditions:
        // - The internal `debug_mode` flag is set to the value of `enabled`.
        // - A message indicating the new debug mode status is logged (if debug was already enabled or just got enabled).
        // - Configures debug mode on the LLMInteractionManager if applicable.
        void set_debug_mode(boolean enabled);

        // Clears the currently stored data context.
        // Preconditions: None.
        // Postconditions:
        // - The internal `data_context` (instance of `DataContext`) is reset to an empty or null state.
        // - Subsequent calls requiring data context will need `prime_data_context` to be called again
        //   or will operate with no specific data context.
        void clear_data_context();

        // Primes or updates the data context using associative matching or explicit initial files.
        // Preconditions:
        // - `query` is an optional string for associative matching via MemorySystem.
        // - `initial_files` is an optional list of file paths to directly form the basis of the context.
        //   (Note: if `initial_files` are provided, they will be transformed into `MatchItem`s of type "file_content").
        // Postconditions:
        // - The internal `data_context` (instance of `DataContext`) is populated.
        //   Its `items` field will contain a list of `MatchItem` objects.
        // - Returns true on success, false on failure to prime context (e.g., MemorySystem error, file reading error).
        // Behavior:
        // - If `query` is provided:
        //   - Calls `self._get_relevant_files(query)` (which uses MemorySystem) to get an `AssociativeMatchResult`.
        //   - Constructs a `DataContext` object, populating `items` with `MatchItem`s from the result,
        //     `source_query` with the query, and `retrieved_at`.
        //   - May generate an `overall_summary` for the `DataContext` (e.g., by concatenating excerpts or using a quick LLM call if complex).
        // - If `initial_files` are provided (and no `query`, or to augment query results):
        //   - For each file path in `initial_files`:
        //     - Attempts to read the file content (e.g., via FileContextManager).
        //     - Creates a `MatchItem` of `content_type="file_content"` with the path as `id` and file text as `content`.
        //     - Adds this `MatchItem` to the `DataContext.items`.
        //   - Sets `retrieved_at` and potentially a simple `overall_summary` (e.g., "Context primed with N files").
        // - If both `query` and `initial_files` are provided, the behavior needs to be defined (e.g., merge results, prioritize query).
        // - The populated `DataContext` object is stored internally (e.g., `self.data_context`).
        boolean prime_data_context(optional string query, optional list<string> initial_files);

        // Retrieves the configured LLM provider/model identifier string.
        // Preconditions:
        // - LLMInteractionManager must be initialized.
        // Postconditions:
        // - Returns the identifier string (e.g., "anthropic:claude-3-5-sonnet-latest") stored in the LLMInteractionManager.
        // - Returns None if the manager is not available or no identifier was configured.
        // Behavior:
        // - Delegates the call to the internal LLMInteractionManager instance.
        optional string get_provider_identifier();

    // Sets the list of *active tool definitions* (specifications) to be used by the LLM.
    // This is typically called once by the Application after determining the appropriate tools
    // based on the configured provider.
    // Preconditions:
    // - tool_definitions is a list of dictionaries, where each dictionary represents a tool
    //   specification compatible with the underlying LLM provider and pydantic-ai library.
    // Postconditions:
    // - The internal list `active_tool_definitions` is replaced with the provided list.
    // - Returns true (or void, depending on implementation choice).
    // Behavior:
    // - Stores the provided list of tool specifications. This list will be passed to the
    //   LLMInteractionManager during LLM calls.
    // Retrieves the registered tool executor functions required by the Agent constructor.
    // Preconditions:
    // - Tools should have been registered via `register_tool`.
    // Postconditions:
    // - Returns a list of callables corresponding to each registered tool executor.
    // Behavior:
    // - Extracts executor functions from the internal `tool_executors` dictionary.
    list<function> get_tools_for_agent();

    boolean set_active_tool_definitions(list<dict<string, Any>> tool_definitions);

    // Retrieves the registered tools in the format required by the pydantic-ai Agent constructor.
    // Preconditions: Tools should have been registered via `register_tool`.
    // Postconditions:
    // - Returns a list of callables corresponding to each registered tool executor,
    //   suitable for passing to the `pydantic-ai Agent` constructor.
    // Behavior:
    // - Extracts executor functions (callables) from the internal `tool_executors` dictionary.
    list<Any> get_tools_for_agent();

        // Internal method to execute a call via the LLMInteractionManager.
        // Preconditions:
        // - LLMInteractionManager's `initialize_agent` must have been called.
        // - prompt is the user's input string.
        // - Optional overrides for system prompt, tools, output type, and model can be provided.
        // - `history_config` is an optional `HistoryConfigSettings` object. If not provided, default history behavior (use session history, include all turns, record current turn) is applied.
        // Postconditions:
        // - Returns the result from the LLM call, typically structured like a TaskResult.
        // - Updates the internal conversation history based on `history_config.record_in_session_history` if the call is successful.
        // Behavior:
        // - Assembles the system prompt using `_build_system_prompt(system_prompt_override)`.
        //   (The main system prompt construction logic now resides in `_build_system_prompt` and uses `self.data_context`).
        // - Passes the `model_override` parameter down to the LLMInteractionManager.
        // - Handles potential errors during the LLM call.
        // @raises_error(condition="LLMInteractionError", description="If the LLM call fails.")
        Any _execute_llm_call(
            string prompt,
            optional string system_prompt_override, // This override is for the *base* part of the system prompt, not the data context part.
            optional list<function> tools_override,
            optional type output_type_override,
            optional string model_override, 
            optional object history_config 
        );

        // Builds the complete system prompt for an LLM call.
        // Preconditions:
        // - `self.data_context` may have been populated by `prime_data_context`.
        // - `template_specific_instructions` is an optional string to be appended after the base system prompt
        //   but before the data context.
        // Postconditions:
        // - Returns the final system prompt string.
        // Behavior:
        // - Starts with the base system prompt (`self.base_system_prompt`).
        // - Appends `template_specific_instructions` if provided.
        // - If `self.data_context` is populated and `self.data_context.items` is not empty:
        //   - Calls `self._create_data_context_string(self.data_context.items)` to get a textual representation.
        //   - Appends this textual representation to the system prompt.
        //   - May also append `self.data_context.overall_summary` if present.
        string _build_system_prompt(
           optional string template_specific_instructions
        );

        // Gets relevant context items based on a query.
        // This method is now primarily a helper for `prime_data_context`.
        // Preconditions:
        // - query is the string used for relevance matching.
        // Postconditions:
        // - Returns an `AssociativeMatchResult` object (whose `matches` field contains `MatchItem` objects).
        // Behavior:
        // - Delegates to `FileContextManager.get_relevant_files` (which interacts with MemorySystem).
        // @raises_error(condition="ContextRetrievalError", description="If file relevance lookup fails.")
        object _get_relevant_files(string query); // Returns AssociativeMatchResult

        // Creates a formatted textual representation from a list of MatchItem objects.
        // Preconditions:
        // - items is a list of `MatchItem` objects.
        // Postconditions:
        // - Returns a single string containing the formatted textual representation of the items.
        // Behavior:
        // - Iterates through each `MatchItem` in `items`.
        // - For each item, uses `item.content` as the primary text.
        // - May use `item.content_type` and `item.id` (or `item.source_path`) to add formatting
        //   (e.g., `<file path="${item.id}">\n${item.content}\n</file>`, or "Summary of ${item.id}:\n${item.content}").
        // - Concatenates the formatted strings for all items.
        // - This method is called by `_build_system_prompt` to prepare the data context part of the prompt.
        // @raises_error(condition="FileAccessError", description="If reading any of the files fails (e.g., if an item has content_type='file_path_only' and content needs to be fetched).")
        string _create_data_context_string(list<object> items); // Param is list<MatchItem>

        // Executes a registered tool directly by name.
        // Preconditions:
        // - tool_name is the name of a tool previously registered via `register_tool`.
        // - tool_input is a dictionary containing the arguments for the tool.
        // Postconditions:
        // - Returns the result of the tool execution, typically formatted as a TaskResult.
        // Behavior:
        // - Looks up the executor function associated with `tool_name` in `self.tool_executors`.
        // - Calls the executor function with `tool_input`.
        // - Handles exceptions during tool execution.
        // - Formats the result into a TaskResult structure.
        // @raises_error(condition="ToolNotFound", description="If no tool with the given name is registered.")
        // @raises_error(condition="ToolExecutionError", description="If the tool's executor function raises an exception.")
        dict<string, Any> _execute_tool(string tool_name, dict<string, Any> tool_input); // Return should be TaskResult

        // Invariants:
        // - `task_system`, `memory_system`, `file_manager` hold valid references after initialization.
        // - `llm_manager` holds a valid LLMInteractionManager instance.
        // - `file_context_manager` holds a valid FileContextManager instance.
        // - `registered_tools`, `tool_executors` are dictionaries.
        // - `conversation_history` is a list.
        // - `data_context` is either None or a valid `DataContext` instance.
    };
};
// == !! END IDL TEMPLATE !! ===
