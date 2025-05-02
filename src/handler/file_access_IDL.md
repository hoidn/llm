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

        // Writes content to a file, optionally overwriting. Constrained by base_path.
        // Preconditions: content is a string. file_path is relative to base_path.
        // Postconditions: Returns true on success, false on failure (e.g., path outside base, permissions, file exists and overwrite=False). Errors logged internally.
        // Behavior: Performs path safety check. Creates parent directories if needed. Handles overwrite logic.
        // @raises_error(None) // Errors handled internally by returning False
        boolean write_file(string file_path, string content, boolean overwrite=False);

        // Inserts content into a file at a specific byte offset. Constrained by base_path.
        // Preconditions: file_path exists and is a file. position is a non-negative integer within the file's bounds.
        // Postconditions: Returns true on success, false on failure (e.g., path outside base, file not found, invalid position, permissions). Errors logged internally.
        // Behavior: Performs path safety check. Reads existing content, inserts new content at position, writes back the modified content.
        // @raises_error(None) // Errors handled internally by returning False
        boolean insert_content(string file_path, string content, int position);
    };
};
// == !! END IDL TEMPLATE !! ===
