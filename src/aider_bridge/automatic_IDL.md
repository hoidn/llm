// == !! BEGIN IDL TEMPLATE !! ===
module src.aider_bridge.automatic {

    # @depends_on(src.aider_bridge.bridge.AiderBridge) // Needs the bridge for core operations

    // Interface for handling automatic Aider tasks with auto-confirmation.
    interface AiderAutomaticHandler {

        // Constructor: Initializes the automatic mode handler.
        // Preconditions:
        // - bridge is a valid AiderBridge instance.
        // Postconditions:
        // - Handler is initialized with a reference to the AiderBridge.
        // - Internal `last_result` is initialized to None.
        void __init__(object bridge); // Arg represents AiderBridge

        // Executes a single Aider task automatically, applying changes without user confirmation.
        // Preconditions:
        // - prompt is a string instruction for the code changes.
        // - file_context is an optional list of explicit file paths. If None, uses the bridge's current context or attempts lookup via `bridge.get_context_for_query`.
        // Postconditions:
        // - Returns a TaskResult dictionary representing the outcome.
        // - If Aider is unavailable, returns a FAILED TaskResult.
        // - If no file context can be determined, returns a FAILED TaskResult.
        // - The internal `last_result` attribute is updated with the raw result from the bridge's `execute_code_edit`.
        // Behavior:
        // - Checks bridge's `aider_available` flag.
        // - Determines the final file context (provided, bridge's current, or looked up).
        // - Calls `bridge.execute_code_edit` to perform the actual Aider operation.
        // - Formats the result from `execute_code_edit` into the standard TaskResult structure using `result_formatter.format_automatic_result`.
        // @raises_error(condition="AiderNotAvailable", description="Handled internally, returns FAILED TaskResult.")
        // @raises_error(condition="NoFileContext", description="Handled internally, returns FAILED TaskResult.")
        // @raises_error(condition="AiderExecutionError", description="Handled internally, returns FAILED TaskResult.")
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "string", "notes": { "files_modified": list<string>, "changes": list<dict>, "error?": "string" } }
        dict<string, Any> execute_task(string prompt, optional list<string> file_context);

        // Retrieves the result of the last task executed by this handler instance.
        // Preconditions: None.
        // Postconditions:
        // - Returns the last stored TaskResult dictionary, or None if no task has been executed yet.
        optional dict<string, Any> get_last_result();
    };
};
// == !! END IDL TEMPLATE !! ===
