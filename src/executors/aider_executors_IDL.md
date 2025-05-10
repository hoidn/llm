// == !! BEGIN IDL TEMPLATE !! ===
module src.executors.aider_executors {

    # @depends_on(src.aider_bridge.bridge.AiderBridge) // Depends on the REFACRORED AiderBridge (MCP Client)
    # @depends_on(src.system.models.TaskResult) // Return type

    // Interface aggregating Aider Direct Tool executor functions.
    // These functions wrap calls to the AiderBridge for specific Aider modes.
    interface AiderExecutorFunctions {

        // Executor logic for the 'aider:automatic' Direct Tool.
        // Preconditions:
        // - params is a dictionary containing:
        //   - 'prompt': string (required) - The instruction for code changes.
        //   - 'editable_files': list<string> or string (JSON array) (optional) - List of file paths Aider is allowed to edit.
        //   - 'model': string (optional) - Specific model override for Aider.
        // - aider_bridge is a valid instance implementing AiderBridge.
        // Postconditions:
        // - Returns a TaskResult dictionary, typically forwarded directly from `aider_bridge.call_aider_tool`.
        // - Returns a FAILED TaskResult if required parameters are missing or file list parsing fails.
        // Behavior:
        // - Validates the 'prompt' parameter.
        // - Parses the 'editable_files' parameter (if provided) into a list of strings. Handles list input or JSON string array.
        // - Constructs the parameter dictionary expected by the Aider MCP Server's 'aider_ai_code' tool (mapping 'prompt' to 'ai_coding_prompt', 'editable_files' to 'editable_files', etc.).
        // - Calls `await aider_bridge.call_aider_tool(tool_name="aider_ai_code", params=mcp_params)`.
        // - Handles exceptions during the bridge call.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult for missing prompt or invalid editable_files.")
        // @raises_error(condition="AiderExecutionError", description="Returned via FAILED TaskResult if bridge call fails or reports an error.")
        // Expected JSON format for params: { "prompt": "string", "editable_files?": "list<string> | string (JSON array)", "model?": "string" }
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "string", "notes": { ... } }
        async dict<string, Any> execute_aider_automatic(dict<string, Any> params, object aider_bridge); // Second arg represents AiderBridge

        // Executor logic for the 'aider:interactive' Direct Tool.
        // Preconditions:
        // - params is a dictionary containing:
        //   - 'query' or 'prompt': string (required) - The initial query/instruction for the session.
        //   - 'editable_files': list<string> or string (JSON array) (optional) - List of file paths Aider is allowed to edit.
        //   - 'model': string (optional) - Specific model override for Aider.
        // - aider_bridge is a valid instance implementing AiderBridge.
        // Postconditions:
        // - Returns a TaskResult dictionary, typically forwarded directly from `aider_bridge.call_aider_tool`.
        // - Returns a FAILED TaskResult if required parameters are missing or file list parsing fails.
        // Behavior:
        // - Validates that 'query' or 'prompt' parameter is present.
        // - Parses the 'editable_files' parameter (if provided) into a list of strings. Handles list input or JSON string array.
        // - Constructs the parameter dictionary expected by the Aider MCP Server's 'aider_ai_code' tool (mapping 'query'/'prompt' to 'ai_coding_prompt', 'editable_files' to 'editable_files', etc.).
        // - Calls `await aider_bridge.call_aider_tool(tool_name="aider_ai_code", params=mcp_params)` (assuming 'aider_ai_code' handles interactive starts).
        // - Handles exceptions during the bridge call.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult for missing query/prompt or invalid editable_files.")
        // @raises_error(condition="AiderExecutionError", description="Returned via FAILED TaskResult if bridge call fails or reports an error.")
        // Expected JSON format for params: { "query?" or "prompt?": "string", "editable_files?": "list<string> | string (JSON array)", "model?": "string" }
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "string", "notes": { ... } }
        async dict<string, Any> execute_aider_interactive(dict<string, Any> params, object aider_bridge); // Second arg represents AiderBridge
    };
};
// == !! END IDL TEMPLATE !! ===
