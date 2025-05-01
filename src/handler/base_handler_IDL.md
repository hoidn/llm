// == !! BEGIN IDL TEMPLATE !! ===
module src.handler.base_handler {

    # @depends_on(src.task_system.task_system.TaskSystem, src.memory.memory_system.MemorySystem) // Core system components
    # @depends_on_resource(type="LLMAgentService", purpose="Orchestrating LLM calls via pydantic-ai") // Represents the configured pydantic-ai agent
    # @depends_on(src.handler.file_access.FileAccessManager) // For file operations
    # @depends_on(src.handler.command_executor.CommandExecutorFunctions) // For safe command execution
    # @depends_on(src.handler.llm_interaction_manager.LLMInteractionManager) // For managing pydantic-ai interactions
    # @depends_on(src.handler.file_context_manager.FileContextManager) // For managing file context operations
    interface BaseHandler {

        // Constructor: Initializes the base handler.
        // Preconditions:
        // - task_system is a valid TaskSystem instance.
        // - memory_system is a valid MemorySystem instance.
        // - default_model_identifier is an optional string identifying the pydantic-ai model (e.g., "anthropic:claude-3-5-sonnet-latest").
        // - config is an optional dictionary for configuration settings (e.g., base_system_prompt, API keys for pydantic-ai).
        // Postconditions:
        // - Handler is initialized with references to core systems (TaskSystem, MemorySystem).
        // - LLMInteractionManager is instantiated with the default_model_identifier and config, which internally configures a pydantic-ai Agent.
        // - FileContextManager is instantiated with the memory_system.
        // - FileAccessManager is instantiated.
        // - Tool registries (registered_tools, tool_executors) are initialized as empty dictionaries.
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

        // Resets the internal conversation history.
        // Preconditions: None.
        // Postconditions:
        // - The `conversation_history` list is cleared.
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

        // Internal method to execute a call via the LLMInteractionManager.
        // Preconditions:
        // - prompt is the user's input string.
        // - Optional overrides for system prompt, tools, and output type can be provided.
        // Postconditions:
        // - Returns the result from the LLM call, typically structured like a TaskResult.
        // - Updates the internal conversation history if the call is successful.
        // Behavior:
        // - Delegates the primary interaction logic to the LLMInteractionManager which manages the pydantic-ai agent.
        // - Passes the current conversation history to the manager.
        // - If tools_override is provided, adapts registered tools to the format required by pydantic-ai.
        // - Handles potential errors during the LLM call.
        // @raises_error(condition="LLMInteractionError", description="If the LLM call fails.")
        Any _execute_llm_call(
            string prompt,
            optional string system_prompt_override,
            optional list<function> tools_override,
            optional type output_type_override
        );

        // Builds the complete system prompt for an LLM call.
        // Preconditions:
        // - template is an optional string containing template-specific instructions.
        // - file_context is an optional string containing context from relevant files.
        // Postconditions:
        // - Returns the final system prompt string.
        // Behavior:
        // - Starts with the base system prompt (`self.base_system_prompt`).
        // - Appends template-specific instructions if provided.
        // - Appends file context if provided.
        string _build_system_prompt(
            optional string template,
            optional string file_context
        );

        // Gets relevant file paths based on a query.
        // Preconditions:
        // - query is the string used for relevance matching.
        // Postconditions:
        // - Returns a list of relevant file paths.
        // Behavior:
        // - Delegates file path retrieval logic to the FileContextManager, which interacts with the MemorySystem.
        // @raises_error(condition="ContextRetrievalError", description="If file relevance lookup fails.")
        list<string> _get_relevant_files(string query);

        // Creates a formatted context string from a list of file paths.
        // Preconditions:
        // - file_paths is a list of strings representing file paths.
        // Postconditions:
        // - Returns a single string containing the formatted content of the specified files.
        // Behavior:
        // - Delegates file reading and formatting logic to the FileContextManager, which interacts with the FileAccessManager.
        // @raises_error(condition="FileAccessError", description="If reading any of the files fails.")
        string _create_file_context(list<string> file_paths);

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
    };
};
// == !! END IDL TEMPLATE !! ===
