// == !! DEPRECATED INTERFACE !! ===
// This interface (AiderAutomaticHandler) is deprecated as of ADR 19.
// Automatic Aider execution is now handled via the refactored AiderBridge (acting as an MCP Client)
// and the AiderExecutorFunctions which invoke it. Refer to those components.
// See:
// - src/aider_bridge/bridge_IDL.md
// - src/executors/aider_executors_IDL.md
// =================================

/*
module src.aider_bridge.automatic {
    # @depends_on(src.aider_bridge.bridge.AiderBridge)
    interface AiderAutomaticHandler {
        void __init__(object bridge);
        dict<string, Any> execute_task(string prompt, optional list<string> file_context);
        optional dict<string, Any> get_last_result();
    };
};
*/
// == !! END DEPRECATED INTERFACE !! ===
