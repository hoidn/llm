// == !! BEGIN IDL TEMPLATE !! ===
module src.handler.base_handler {

    # @depends_on(src.task_system.task_system.TaskSystem, src.memory.memory_system.MemorySystem) // Core system components
    # @depends_on_resource(type="LLMAgentService", purpose="Orchestrating LLM calls via pydantic-ai") // Represents the configured pydantic-ai agent
    # @depends_on(src.handler.file_access.FileAccessManager) // For file operations
    # @depends_on(src.handler.command_executor.CommandExecutorFunctions) // For safe command execution
    interface BaseHandler {

        // Constructor: Initializes the base handler.
        // Preconditions:
        // - task_system is a valid TaskSystem instance.
        // - memory_system is a valid MemorySystem instance.
        // - default_model_identifier is an optional string identifying the pydantic-ai model (e.g., "anthropic:claude-3-5-sonnet-latest").
        // - config is an optional dictionary for configuration settings (e.g., base_system_prompt, API keys for pydantic-ai).
        // Postconditions:
        // - Handler is initialized with references to core systems (TaskSystem, MemorySystem).
        // - Internally configures and instantiates a pydantic-ai Agent using the default_model_identifier and config.
        // - FileAccessManager is instantiated.
        // - Tool registries (registered_tools, tool_executors) are initialized as empty dictionaries.
        //   (Note: `registered_tools` will likely hold specs formatted for the internal pydantic-ai agent).
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
        // - If successful, the tool specification and executor are registered with the internal pydantic-ai Agent instance.
        // - The `tool_executors` dictionary (keyed by name) is updated for direct programmatic access if needed.
        // - Returns true if registration is successful (tool_spec has a name).
        // - Returns false if registration fails (e.g., missing name in tool_spec).
        // Behavior:
        // - This is the single, unified method for registering any callable action (tool) intended for LLM use or programmatic invocation.
        // - Validates that tool_spec contains a 'name'.
        // - **Adapts** the provided tool_spec and executor_func into the format required by the internal pydantic-ai Agent.
        // - Registers the adapted tool with the pydantic-ai Agent.
        // - Stores the original executor_func in the `tool_executors` registry for direct programmatic invocation (e.g., by SexpEvaluator).
        // - The `registered_tools` registry might store the original spec or the adapted spec for reference.
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
        // - May also reset state within the internal pydantic-ai Agent if necessary.
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
        // - May configure instrumentation on the internal pydantic-ai Agent if applicable.
        void set_debug_mode(boolean enabled);

        // Invariants:
        // - `task_system`, `memory_system`, `file_manager` hold valid references after initialization.
        // - An internal `pydantic_ai.Agent` instance is configured and available.
        // - `registered_tools`, `tool_executors`, `direct_tool_executors` are dictionaries.
        // - `conversation_history` is a list.
    };
};
// == !! END IDL TEMPLATE !! ===
