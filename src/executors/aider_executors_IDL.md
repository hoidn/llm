// == !! BEGIN IDL TEMPLATE !! ===
module src.executors.aider_executors {

    # @depends_on(src.aider_bridge.bridge.AiderBridge) // Depends on the REFACRORED AiderBridge (MCP Client)

    // Interface aggregating Aider Direct Tool executor functions.
    // These functions wrap calls to the AiderBridge for specific Aider modes.
    interface AiderExecutorFunctions {

        // Executor logic for the 'aider:automatic' Direct Tool.
        // Preconditions:
        // - params is a dictionary containing:
        //   - 'prompt': string (required) - The instruction for code changes.
        //   - 'file_context': string (optional) - JSON string array of explicit file paths.
        // - aider_bridge is a valid instance implementing AiderBridge.
        // Postconditions:
        // - Returns a TaskResult dictionary, typically forwarded directly from `aider_bridge.execute_automatic_task`.
        // - Returns a FAILED TaskResult if required parameters are missing or file_context parsing fails.
        // Behavior:
        // - Validates the 'prompt' parameter.
        // - Parses the 'file_context' parameter (if provided) into a list of strings. Handles parsing errors.
        // - Retrieves/uses the `aider_bridge` (MCP Client) instance.
        // - Calls `aider_bridge.call_aider_tool`, passing the Aider MCP tool name (e.g., "aider_ai_code") and the necessary parameters (prompt, parsed file paths, etc.).
        // - Handles exceptions during the bridge call.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult for missing prompt or invalid file_context.")
        // @raises_error(condition="AiderExecutionError", description="Returned via FAILED TaskResult if bridge call fails.")
        // Expected JSON format for params: { "prompt": "string", "file_context?": "string" } // file_context is JSON array string
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "string", "notes": { ... } }
        dict<string, Any> execute_aider_automatic(dict<string, Any> params, object aider_bridge); // Second arg represents AiderBridge

        // Executor logic for the 'aider:interactive' Direct Tool.
        // Preconditions:
        // - params is a dictionary containing:
        //   - 'query' or 'prompt': string (required) - The initial query/instruction for the session.
        //   - 'file_context': string (optional) - JSON string array of explicit file paths.
        // - aider_bridge is a valid instance implementing AiderBridge.
        // Postconditions:
        // - Returns a TaskResult dictionary, typically forwarded directly from `aider_bridge.start_interactive_session`.
        // - Returns a FAILED TaskResult if required parameters are missing or file_context parsing fails.
        // Behavior:
        // - Validates that 'query' or 'prompt' parameter is present.
        // - Parses the 'file_context' parameter (if provided) into a list of strings. Handles parsing errors.
        // - Retrieves/uses the `aider_bridge` (MCP Client) instance.
        // - Calls `aider_bridge.call_aider_tool`, passing the Aider MCP tool name for starting an interactive session (exact name TBD by server) and the necessary parameters (query, parsed file paths, etc.).
        // - Handles exceptions during the bridge call.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult for missing query/prompt or invalid file_context.")
        // @raises_error(condition="AiderExecutionError", description="Returned via FAILED TaskResult if bridge call fails.")
        // Expected JSON format for params: { "query?" or "prompt?": "string", "file_context?": "string" } // file_context is JSON array string
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "string", "notes": { ... } }
        dict<string, Any> execute_aider_interactive(dict<string, Any> params, object aider_bridge); // Second arg represents AiderBridge
    };
};
// == !! END IDL TEMPLATE !! ===
