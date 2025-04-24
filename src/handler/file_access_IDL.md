// == !! BEGIN IDL TEMPLATE !! ===
module src.handler.file_access {

    # @depends_on_resource(type="FileSystem", purpose="Reading file content and metadata")
    interface FileAccessManager {

        // Constructor: Initializes the FileAccessManager.
        // Preconditions:
        // - base_path is an optional string specifying the base directory for resolving relative paths. Defaults to the current working directory.
        // Postconditions:
        // - FileAccessManager is initialized, ready to perform file operations relative to the base_path.
        void __init__(optional string base_path);

        // Reads the content of a specified file safely.
        // Preconditions:
        // - file_path is a string representing the path to the file (can be relative to base_path).
        // - max_size is an optional integer specifying the maximum file size in bytes (defaults to 100KB).
        // Postconditions:
        // - Returns the file content as a string if the file exists, is readable, and within the size limit.
        // - Returns a specific error string "File too large..." if the file exceeds max_size.
        // - Returns None if the file is not found or another reading error occurs.
        // Behavior:
        // - Resolves relative paths using the configured base_path.
        // - Checks file existence and size limits.
        // - Reads file content using UTF-8 encoding, replacing errors.
        // @raises_error(condition="FileNotFound", description="Implicitly handled by returning None.")
        // @raises_error(condition="ReadError", description="Implicitly handled by returning None.")
        // @raises_error(condition="FileTooLarge", description="Handled by returning specific string.")
        optional string read_file(string file_path, optional int max_size);

        // Retrieves metadata information about a specified file.
        // Preconditions:
        // - file_path is a string representing the path to the file (can be relative to base_path).
        // Postconditions:
        // - If the file exists, returns a dictionary containing file 'path' (absolute), 'size' (string), and 'modified' timestamp (string).
        // - If the file does not exist or an error occurs, returns a dictionary containing an 'error' key with a descriptive message.
        // Behavior:
        // - Resolves relative paths.
        // - Uses OS functions to get file status (size, modification time).
        // Expected JSON format for success return value: { "path": "string", "size": "string", "modified": "string" }
        // Expected JSON format for error return value: { "error": "string" }
        dict<string, string> get_file_info(string file_path);
    };
};
// == !! END IDL TEMPLATE !! ===
