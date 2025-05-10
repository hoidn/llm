// == !! BEGIN IDL TEMPLATE !! ===
module src.handler.passthrough_handler {

    # @depends_on(src.handler.base_handler.BaseHandler) // Inherits from BaseHandler
    # @depends_on(src.task_system.task_system.TaskSystem) // For template finding
    # @depends_on(src.memory.memory_system.MemorySystem) // For context retrieval
    # @depends_on_resource(type="LLMAgentService", purpose="Orchestrating LLM calls via pydantic-ai") // Via BaseHandler
    # @depends_on(src.handler.command_executor.CommandExecutorFunctions) // For command execution tool

    // Interface for the passthrough handler, responsible for handling raw text queries.
    // Conceptually extends src.handler.base_handler.BaseHandler.
    interface PassthroughHandler { // extends BaseHandler

        // Constructor: Initializes the passthrough handler.
        // Preconditions:
        // - task_system is a valid TaskSystem instance.
        // - memory_system is a valid MemorySystem instance.
        // - default_model_identifier is an optional string identifying the pydantic-ai model (passed to BaseHandler).
        // - config is an optional configuration dictionary (passed to BaseHandler).
        // Postconditions:
        // - BaseHandler is initialized with dependencies.
        // - Passthrough-specific system prompt instructions are appended to the base system prompt.
        // - Internal state `active_subtask_id` is initialized to None.
        // - The built-in command execution tool ('executeFilePathCommand') is registered using `register_tool`.
        void __init__(
            object task_system, // Represents TaskSystem
            object memory_system, // Represents MemorySystem
            optional string default_model_identifier, // Passed to BaseHandler
            optional dict<string, Any> config
        );

        // Handles a raw text query from the user in passthrough mode.
        // Preconditions:
        // - query is a non-empty string representing the user's input.
        // Postconditions:
        // - Returns a TaskResult dictionary containing the status, assistant's content response, and metadata.
        // - Metadata includes information about the data context used (e.g., from notes in TaskResult).
        // - The conversation history and data context (in BaseHandler) are updated.
        // Behavior:
        // 1. Calls `BaseHandler.prime_data_context(query=query)` to populate `self.data_context`.
        //    - If priming fails, returns a FAILED TaskResult with reason 'context_priming_failure'.
        // 2. (Placeholder) Aider command checks.
        // 3. Subtask Logic:
        //    - If `self.active_subtask_id` is None, calls `_create_new_subtask(query)`.
        //    - Else, calls `_continue_subtask(query)`.
        //    (Note: Current implementation of _create_new_subtask and _continue_subtask are single-turn and do not set/persist active_subtask_id across calls).
        // 4. The called subtask method (_create_new_subtask or _continue_subtask) will:
        //    - Find a template (e.g., "generic_llm_task").
        //    - Call `BaseHandler._build_system_prompt()` which uses `self.data_context`.
        //    - Call `BaseHandler._execute_llm_call()` with the query and built system prompt.
        // 5. Populates `result.notes["relevant_files_from_context"]` from `self.data_context`.
        // 6. Returns the TaskResult from the subtask method.
        // @raises_error(condition="TASK_FAILURE", reason="context_priming_failure", description="If data context priming fails.")
        // @raises_error(condition="TASK_FAILURE", reason="template_not_found", description="If the default passthrough template is not found by subtask logic.")
        // @raises_error(condition="TASK_FAILURE", reason="llm_error", description="If interaction via the pydantic-ai agent fails during subtask execution.")
        // @raises_error(condition="TASK_FAILURE", reason="tool_execution_error", description="If an LLM-invoked tool fails during subtask execution.")
        // @raises_error(condition="TASK_FAILURE", reason="unexpected_error", description="For other unexpected errors during query handling.")
        // Expected JSON format for return value: TaskResult structure.
        dict<string, Any> handle_query(string query);

        // Registers the built-in command execution tool ('executeFilePathCommand').
        // Preconditions: None.
        // Postconditions:
        // - The 'executeFilePathCommand' tool specification is created.
        // - A wrapper function is defined to handle input and call `command_executor.execute_command_safely` and `command_executor.parse_file_paths_from_output`.
        // - The tool spec and wrapper function are registered using `BaseHandler.register_tool`.
        // - Returns true if registration was successful, false otherwise.
        boolean register_command_execution_tool();

        // Resets the conversation state.
        // Preconditions: None.
        // Postconditions:
        // - Calls `BaseHandler.reset_conversation()` (which clears conversation history and `data_context`).
        // - Resets the internal `active_subtask_id` to None.
        void reset_conversation();

        // Invariants:
        // - Inherits invariants from BaseHandler.
        // - `active_subtask_id` is either None or a string.
    };
};
// == !! END IDL TEMPLATE !! ===
