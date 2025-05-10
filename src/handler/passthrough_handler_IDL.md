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
        // - Adds the user query to the internal conversation history.
        // - Calls `self.prime_data_context(query=query)` to populate/update the `BaseHandler`'s `data_context`.
        // - Determines if the query matches an Aider command (internal logic).
        // - If no active subtask, creates a new one (`_create_new_subtask`):
        //   - Tries to find a matching template via TaskSystem.
        //   - Invokes `_execute_llm_call`. The necessary data context string will be constructed internally
        //     by `_build_system_prompt` using the primed `data_context`.
        // - If an active subtask exists, continues it (`_continue_subtask`), similarly using the primed `data_context`.
        // - The underlying BaseHandler logic uses the pydantic-ai agent to handle the LLM call.
        // - Adds the assistant's response to the conversation history.
        // @raises_error(condition="TASK_FAILURE", reason="llm_error", description="If interaction via the pydantic-ai agent fails.")
        // @raises_error(condition="TASK_FAILURE", reason="tool_execution_error", description="If an LLM-invoked tool fails.")
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "string", "metadata": { "subtask_id": "string", "relevant_files": list<string>, "template?": {...} } }
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
        // - Calls `BaseHandler.reset_conversation()` (which now also clears `data_context`).
        // - Resets the internal `active_subtask_id` to None.
        void reset_conversation();

        // Invariants:
        // - Inherits invariants from BaseHandler.
        // - `active_subtask_id` is either None or a string.
    };
};
// == !! END IDL TEMPLATE !! ===
