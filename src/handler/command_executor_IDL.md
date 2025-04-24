// == !! BEGIN IDL TEMPLATE !! ===
module src.handler.command_executor {

    # @depends_on_resource(type="Shell", purpose="Executing external shell commands")
    # @depends_on_resource(type="FileSystem", purpose="Checking existence of parsed file paths")
    interface CommandExecutorFunctions {

        // Executes a shell command safely with resource limits.
        // Preconditions:
        // - command is a string containing the command to execute.
        // - cwd is an optional string specifying the working directory. Defaults to current dir.
        // - timeout is an optional integer for max execution time in seconds (defaults to 5).
        // Postconditions:
        // - Returns a dictionary containing execution results: 'success' (boolean), 'output' (string, stdout up to MAX_OUTPUT_SIZE), 'error' (string, stderr up to MAX_OUTPUT_SIZE), 'exit_code' (int).
        // - 'success' is true only if the command executes and returns exit code 0.
        // - Returns specific error messages and success=false for unsafe commands, timeouts, or other execution exceptions.
        // Behavior:
        // - Parses the command using shlex to mitigate injection risks.
        // - Performs basic safety checks against known unsafe commands/characters.
        // - Executes the command using subprocess.run with timeout and output capture.
        // - Truncates stdout and stderr to MAX_OUTPUT_SIZE.
        // @raises_error(condition="UnsafeCommandDetected", description="Returned via success=false and specific error message.")
        // @raises_error(condition="TimeoutExpired", description="Returned via success=false and specific error message.")
        // @raises_error(condition="ExecutionException", description="Returned via success=false and specific error message.")
        // Expected JSON format for return value: { "success": "boolean", "output": "string", "error": "string", "exit_code": "int" }
        dict<string, Any> execute_command_safely(string command, optional string cwd, optional int timeout);

        // Parses file paths from command output, filtering for existing files.
        // Preconditions:
        // - output is a string, typically the standard output from a command execution, expected to contain file paths (one per line).
        // Postconditions:
        // - Returns a list of strings, where each string is an absolute path to an existing file identified in the input.
        // - Returns an empty list if the input is empty or no existing file paths are found.
        // Behavior:
        // - Splits the input string by lines.
        // - Strips whitespace from each line.
        // - Filters out empty lines.
        // - Checks if each resulting path corresponds to an existing file on the filesystem.
        list<string> parse_file_paths_from_output(string output);
    };
};
// == !! END IDL TEMPLATE !! ===
