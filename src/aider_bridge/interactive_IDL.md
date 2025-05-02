// == !! DEPRECATED INTERFACE !! ===
// This interface (AiderInteractiveSession) is deprecated as of ADR 19.
// Interactive Aider execution is now handled via the refactored AiderBridge (acting as an MCP Client)
// and the AiderExecutorFunctions which invoke it. The session state is managed by the external Aider MCP Server.
// See:
// - src/aider_bridge/bridge_IDL.md
// - src/executors/aider_executors_IDL.md
// ==================================

/*
module src.aider_bridge.interactive {
    # @depends_on(src.aider_bridge.bridge.AiderBridge)
    interface AiderInteractiveSession {
        void __init__(object bridge);
        dict<string, Any> start_session(string query, optional list<string> file_context);
        dict<string, Any> terminate_session();
    };
};
*/
// == !! END DEPRECATED INTERFACE !! ===
