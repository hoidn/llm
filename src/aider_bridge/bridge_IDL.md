// == !! BEGIN IDL TEMPLATE !! ===
// **Note:** This interface definition reflects the refactoring based on ADR 19.
// The AiderBridge now acts as an MCP Client, communicating with an external Aider MCP Server.
// The previous interface assuming direct Aider interaction is deprecated.
module src.aider_bridge.bridge {

    // Dependencies for preparing context before calling the MCP server
    # @depends_on(src.memory.memory_system.MemorySystem)
    # @depends_on(src.handler.file_access.FileAccessManager)
    // Dependency on the external service
    # @depends_on_resource(type="ExternalMCPService", purpose="Aider MCP Server")
    # @depends_on_library(name="mcp.py", purpose="MCP Client Communication")
    // Conceptual dependency on an MCP client library (e.g., pydantic-ai client or mcp.py)

    // Interface for the Aider Bridge, acting as an MCP Client.
    // Connects to and interacts with a remote Aider MCP Server.
    interface AiderBridge {

        // Constructor: Initializes the Aider Bridge MCP Client.
        // Preconditions:
        // - memory_system is a valid MemorySystem instance (needed for context prep methods).
        // - file_access_manager is an optional FileAccessManager instance (needed for context prep methods).
        // - config contains necessary connection details for the Aider MCP Server, suitable for the chosen mcp.py transport
        //   (e.g., 'mcp_server_url' for WebSocket/SSE, or parameters for StdioServerParameters if using STDIO). May also contain 'mcp_auth_token'.
        // Postconditions:
        // - Bridge is initialized with MemorySystem and FileAccessManager references.
        // - MCP client mechanism is configured using details from `config`.
        // - Internal file context set (`file_context`) and source (`context_source`) are initialized.
        // - Checks for Aider *server* availability conceptually (e.g., connection test or assumes availability).
        void __init__(object memory_system, optional object file_access_manager, dict<string, Any> config); // Args represent MemorySystem, FileAccessManager, ConfigDict

        // Calls a specific tool on the remote Aider MCP Server.
        // Preconditions:
        // - tool_name is the name of the MCP tool exposed by the Aider server (e.g., "aider_ai_code", "list_models").
        // - params is a dictionary containing parameters required by the specific Aider MCP tool (e.g., for "aider_ai_code": ai_coding_prompt, relative_editable_files, etc.).
        // - MCP client (e.g., mcp.client.ClientSession) is initialized and connected.
        // Postconditions:
        // - Returns a dictionary representing the TaskResult structure, derived from the Aider MCP server's response.
        // - Returns a FAILED TaskResult dictionary if the MCP call fails (communication error) or the server reports an application error.
        // Behavior:
        // - Uses the underlying MCP client library (e.g., mcp.client.ClientSession) to invoke `call_tool(name=tool_name, arguments=params)`.
        // - Expects the MCP client library to return the server's response payload, typically within a structure like `list[mcp.types.TextContent]`.
        // - Extracts the text content (which is expected to be a JSON string) from the response.
        // - Parses the JSON string using `json.loads()`.
        // - Checks the parsed dictionary for an `"error"` key. If present, formats a FAILED TaskResult using the error message.
        // - If no `"error"` key, maps the success payload (e.g., `{"success": bool, "diff": str}` for aider_ai_code) to a COMPLETE TaskResult dictionary (e.g., content=diff, notes={'success': True}).
        // - Handles potential communication exceptions raised by the MCP client library (e.g., connection errors, timeouts) by formatting them into a FAILED TaskResult.
        // @raises_error(condition="MCPCommunicationError", description="Handled internally. Raised by mcp.py client for connection/timeout issues, returned as FAILED TaskResult.")
        // @raises_error(condition="JSONDecodeError", description="Handled internally. If server response is not valid JSON, returned as FAILED TaskResult.")
        // @raises_error(condition="TaskFailureError", description="Returned via FAILED TaskResult if the parsed JSON response from the Aider MCP Server contains an 'error' key.")
        // Expected JSON format for params: Dependent on `tool_name`. See `docs/librarydocs/aider_MCP_server.md`.
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "string", "notes": { ... } }
        dict<string, Any> call_aider_tool(string tool_name, dict<string, Any> params);

        // --- Context Preparation Methods (Retained but role clarified) ---
        // These methods now primarily help prepare the 'file_context' parameter *before* calling call_aider_tool.
        // They no longer interact directly with Aider components.

        // Sets the file context explicitly for subsequent *preparation* of Aider calls.
        // Preconditions:
        // - file_paths is a list of strings representing file paths.
        // - source is an optional string indicating the origin ('explicit_specification' or 'associative_matching').
        // Postconditions:
        // - Updates the internal `file_context` set with only the paths that correspond to existing files (validated via FileAccessManager).
        // - Updates the internal `context_source` string.
        // - Returns a dictionary indicating status and file count.
        // Behavior:
        // - Validates file existence using FileAccessManager. Stores valid paths internally for potential use in subsequent `call_aider_tool` invocations.
        // Expected JSON format for return value: { "status": "success|error", "file_count": "int", "context_source": "string", "message?": "string" }
        dict<string, Any> set_file_context(list<string> file_paths, optional string source);

        // Retrieves the current file context stored by the bridge (for preparing calls).
        // Preconditions: None.
        // Postconditions:
        // - Returns a dictionary containing 'file_paths' (list of strings), 'file_count' (int), and 'context_source' (string or None).
        // Behavior:
        // - Reads the internal `file_context` set and `context_source`.
        // Expected JSON format for return value: { "file_paths": list<string>, "file_count": "int", "context_source": "string" }
        dict<string, Any> get_file_context();

        // Determines relevant file context for a query using the MemorySystem (for preparing calls).
        // Preconditions:
        // - query is a non-empty string describing the task or question.
        // Postconditions:
        // - Returns a list of relevant absolute file paths determined by the MemorySystem.
        // - If files are found, updates the internal `file_context` set and sets `context_source` to 'associative_matching'.
        // - Returns an empty list if MemorySystem interaction fails or no relevant files are found.
        // Behavior:
        // - Creates a ContextGenerationInput object for the query.
        // - Calls `memory_system.get_relevant_context_for` to perform associative matching.
        // - Extracts file paths from the AssociativeMatchResult. Updates internal state if relevant files are found.
        list<string> get_context_for_query(string query);

        // --- Deprecated Methods (Removed from Interface) ---
        // - execute_code_edit
        // - start_interactive_session
        // - create_interactive_session
        // - create_automatic_handler
    };
};
// == !! END IDL TEMPLATE !! ===
