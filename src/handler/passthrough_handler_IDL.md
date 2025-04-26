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
        // - Metadata includes relevant files found and potentially template info if a match occurred.
        // - The conversation history (internal state) is updated with the user query and the assistant response.
        // Behavior:
        // - Adds the user query to the internal conversation history.
        // - Retrieves relevant files using `_get_relevant_files` (delegates to MemorySystem/TaskSystem).
        // - Determines if the query matches an Aider command (internal logic).
        // - If no active subtask, creates a new one (`_create_new_subtask`):
        //   - Tries to find a matching template via TaskSystem.
        //   - Creates file context string.
        //   - Invokes the internal pydantic-ai agent (via BaseHandler's logic) with appropriate prompts, context, and tools.
        // - If an active subtask exists, continues it (`_continue_subtask`):
        //   - Tries to find a matching template.
        //   - Creates file context string.
        //   - Invokes the internal pydantic-ai agent (via BaseHandler's logic) with appropriate prompts, context, and tools.
        // - The underlying BaseHandler logic uses the pydantic-ai agent to handle the LLM call, including system prompt construction, message history, tool preparation, tool execution, and response generation.
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
        // - Calls `BaseHandler.reset_conversation()` to clear history and potentially reset the pydantic-ai agent state.
        // - Resets the internal `active_subtask_id` to None.
        void reset_conversation();

        // Invariants:
        // - Inherits invariants from BaseHandler.
        // - `active_subtask_id` is either None or a string.
    };
};
// == !! END IDL TEMPLATE !! ===
