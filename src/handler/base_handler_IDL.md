// == !! BEGIN IDL TEMPLATE !! ===
module src.handler.base_handler {

    # @depends_on(src.task_system.task_system.TaskSystem, src.memory.memory_system.MemorySystem) // Core system components
    # @depends_on(src.handler.model_provider.ProviderAdapter) // For LLM interaction
    # @depends_on(src.handler.file_access.FileAccessManager) // For file operations
    # @depends_on(src.handler.command_executor.CommandExecutorFunctions) // For safe command execution
    interface BaseHandler {

        // Constructor: Initializes the base handler.
        // Preconditions:
        // - task_system is a valid TaskSystem instance.
        // - memory_system is a valid MemorySystem instance.
        // - model_provider is an optional ProviderAdapter instance (defaults to ClaudeProvider).
        // - config is an optional dictionary for configuration settings (e.g., base_system_prompt).
        // Postconditions:
        // - Handler is initialized with references to core systems (TaskSystem, MemorySystem, ProviderAdapter).
        // - FileAccessManager is instantiated.
        // - Tool registries (registered_tools, tool_executors, direct_tool_executors) are initialized as empty dictionaries.
        // - Conversation history is initialized as an empty list.
        // - Base system prompt is set from config or default.
        // - Debug mode is initialized to false.
        void __init__(
            object task_system, // Represents TaskSystem instance
            object memory_system, // Represents MemorySystem instance
            optional object model_provider, // Represents ProviderAdapter instance
            optional dict<string, Any> config
        );

        // Registers a tool specification and its executor function for LLM use.
        // Preconditions:
        // - tool_spec is a dictionary containing 'name', 'description', 'input_schema'.
        // - executor_func is a callable function that implements the tool's logic, typically accepting a dictionary based on input_schema and returning a TaskResult-like dictionary.
        // Expected JSON format for tool_spec: { "name": "string", "description": "string", "input_schema": { ... } }
        // Postconditions:
        // - If successful, the tool_spec is added to the `registered_tools` dictionary (keyed by name).
        // - The executor_func is added to the `tool_executors` dictionary (keyed by name).
        // - Returns true if registration is successful (tool_spec has a name).
        // - Returns false if registration fails (e.g., missing name in tool_spec).
        // Behavior:
        // - Validates that tool_spec contains a 'name'.
        // - Stores the spec and executor function in internal registries.
        boolean register_tool(dict<string, Any> tool_spec, function executor_func);

        // Registers a direct tool executor function for programmatic invocation (e.g., via Dispatcher).
        // These tools are not necessarily intended for direct LLM tool use but are callable via identifiers.
        // Preconditions:
        // - tool_name is a non-empty string identifier for the tool.
        // - executor_func is a callable function implementing the tool's logic. The expected signature may vary depending on the tool.
        // Postconditions:
        // - If successful, the executor_func is added to the `direct_tool_executors` dictionary (keyed by tool_name).
        // - Returns true if registration is successful (tool_name is provided).
        // - Returns false if registration fails (e.g., empty tool_name).
        boolean registerDirectTool(string tool_name, function executor_func);

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
        void set_debug_mode(boolean enabled);

        // Invariants:
        // - `task_system`, `memory_system`, `model_provider`, `file_manager` hold valid references after initialization.
        // - `registered_tools`, `tool_executors`, `direct_tool_executors` are dictionaries.
        // - `conversation_history` is a list.
    };
};
// == !! END IDL TEMPLATE !! ===
