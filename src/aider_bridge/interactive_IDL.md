// == !! BEGIN IDL TEMPLATE !! ===
module src.aider_bridge.interactive {

    # @depends_on(src.aider_bridge.bridge.AiderBridge) // Needs the bridge for context and config
    # @depends_on_resource(type="Shell", purpose="Running the aider command-line tool interactively")
    # @depends_on_resource(type="FileSystem", purpose="Getting file status before/after session")
    # @depends_on_resource(type="Terminal", purpose="Transferring control for interactive session")
    interface AiderInteractiveSession {

        // Constructor: Initializes the interactive session manager.
        // Preconditions:
        // - bridge is a valid AiderBridge instance.
        // Postconditions:
        // - Session manager is initialized with a reference to the AiderBridge.
        // - Internal state flags (`active`, `process`) and tracking sets/lists (`files_before`, `files_after`, `modified_files`) are initialized.
        void __init__(object bridge); // Arg represents AiderBridge

        // Starts an interactive Aider session, transferring terminal control.
        // Preconditions:
        // - query is the initial string query/instruction for the session.
        // - file_context is an optional list of explicit file paths. If None, uses the bridge's current context or attempts lookup via `bridge.get_context_for_query`.
        // - No other interactive session managed by this instance should be active.
        // Postconditions:
        // - Returns a TaskResult dictionary summarizing the session outcome.
        // - 'status' is 'COMPLETE' if the session finished normally, 'FAILED' if errors occurred during setup or execution.
        // - 'content' provides a summary message.
        // - 'notes' contains 'files_modified' (list of paths) and potentially 'session_summary' or 'error'.
        // - Terminal control is returned to the calling process after the Aider subprocess exits.
        // Behavior:
        // - Checks bridge's `aider_available` flag. Returns error if unavailable.
        // - Checks if a session is already active. Returns error if true.
        // - Determines the final file context (provided, bridge's current, or looked up). Returns error if no context found.
        // - Records the state (mtime, size, hash) of context files before starting (`_get_file_states`).
        // - Constructs the `aider` command-line arguments including files and initial query/message.
        // - Runs `aider` as an interactive subprocess using `subprocess.Popen`, redirecting stdin/stdout/stderr. Waits for the subprocess to complete. (`_run_aider_subprocess`).
        // - Records the state of context files after the session (`_get_file_states`).
        // - Compares file states to determine which files were modified (`_get_modified_files`).
        // - Cleans up session resources (`_cleanup_session`).
        // - Formats the result using `result_formatter.format_interactive_result`. Handles exceptions.
        // @raises_error(condition="AiderNotAvailable", description="Handled internally, returns FAILED TaskResult.")
        // @raises_error(condition="SessionActiveError", description="Handled internally, returns FAILED TaskResult.")
        // @raises_error(condition="NoFileContext", description="Handled internally, returns FAILED TaskResult.")
        // @raises_error(condition="SubprocessError", description="Handled internally, returns FAILED TaskResult.")
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "string", "notes": { "files_modified": list<string>, "session_summary?": "string", "error?": "string" } }
        dict<string, Any> start_session(string query, optional list<string> file_context);

        // Terminates the currently active Aider subprocess, if one exists.
        // Preconditions:
        // - An interactive session must have been started by this instance and the subprocess must still be running (`active` is true, `process` is valid).
        // Postconditions:
        // - Returns a TaskResult dictionary indicating termination outcome.
        // - 'status' is 'COMPLETE' if termination was successful, 'PARTIAL' if errors occurred during termination, 'FAILED' if no active session.
        // - Attempts to terminate the Aider subprocess gracefully (SIGTERM) then forcefully (SIGKILL) if needed.
        // - Cleans up session resources (`_cleanup_session`).
        // Behavior:
        // - Checks the `active` flag.
        // - Sends SIGTERM, waits, then sends SIGKILL to the stored `process` handle if necessary.
        // - Calls `_cleanup_session`.
        // - Formats the result. Handles exceptions during termination.
        // @raises_error(condition="NoActiveSession", description="Handled internally, returns FAILED TaskResult.")
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "string", "notes": { ... } }
        dict<string, Any> terminate_session();
    };
};
// == !! END IDL TEMPLATE !! ===
