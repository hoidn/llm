// == !! BEGIN IDL TEMPLATE !! ===
module src.memory.indexers.git_repository_indexer {

    # @depends_on(src.memory.memory_system.MemorySystem) // Needs MemorySystem to update the index
    # @depends_on_resource(type="FileSystem", purpose="Scanning directories, reading files, checking paths")
    # @depends_on_resource(type="Git", purpose="Getting commit history for files")
    # @depends_on_resource(type="Shell", purpose="Running git commands")
    interface GitRepositoryIndexer {

        // Constructor: Initializes the indexer for a specific repository path.
        // Preconditions:
        // - repo_path is a string representing the path to the local Git repository.
        // Postconditions:
        // - Indexer is initialized with the repository path.
        // - Default values are set for max_file_size (1MB) and include_patterns (["**/*.py"]).
        // - exclude_patterns is initialized as an empty list.
        void __init__(string repo_path);

        // Indexes the configured Git repository and updates the provided Memory System.
        // Preconditions:
        // - memory_system is a valid instance implementing the MemorySystem interface.
        // Postconditions:
        // - Returns a dictionary mapping the absolute file paths of indexed files to their generated metadata strings.
        // - Calls `memory_system.update_global_index` with the generated file metadata.
        // - Skips files exceeding `max_file_size` or identified as binary.
        // Behavior:
        // - Scans the repository using `scan_repository` based on `include_patterns` and `exclude_patterns`.
        // - For each matching text file within size limits:
        //   - Reads its content.
        //   - Generates metadata using `create_metadata`.
        // - Updates the `memory_system`'s global index.
        // - Handles potential errors during file processing.
        // @raises_error(condition="FileProcessingError", description="Logged internally, file is skipped.")
        // Expected JSON format for return value: { "absolute/path/to/file.py": "metadata string\n...", ... }
        dict<string, string> index_repository(object memory_system); // Arg represents MemorySystem

        // Scans the repository directory for files matching include/exclude patterns.
        // Preconditions:
        // - `repo_path`, `include_patterns`, `exclude_patterns` attributes are set.
        // Postconditions:
        // - Returns a list of absolute file paths within the `repo_path` that match the include patterns but not the exclude patterns.
        // - Filters out directories, returning only file paths.
        // Behavior:
        // - Uses glob matching (recursive) for include and exclude patterns relative to `repo_path`.
        // - Calculates the set difference to get the final list.
        // - Filters the result to ensure only files are returned.
        list<string> scan_repository();

        // Determines if a file is likely a text file based on extension and content sniffing.
        // Preconditions:
        // - file_path is a string representing the path to the file.
        // Postconditions:
        // - Returns true if the file is likely a text file.
        // - Returns false if the file extension is in a known binary list or if the initial bytes contain common binary patterns (e.g., null bytes).
        // Behavior:
        // - Checks file extension against a predefined list of binary extensions.
        // - Reads the first 1024 bytes of the file.
        // - Checks for common binary signatures/patterns (null byte, JPEG/PNG/ZIP markers).
        // - Attempts to decode the initial bytes as UTF-8.
        boolean is_text_file(string file_path);

        // Creates a metadata string for a given file and its content.
        // Preconditions:
        // - file_path is the absolute path to the file.
        // - content is the string content of the file.
        // Postconditions:
        // - Returns a multi-line string containing structured metadata about the file.
        // Behavior:
        // - Extracts relative path, filename, and extension.
        // - Gets file size (if file exists).
        // - Extracts document summary using `text_extraction.extract_document_summary`.
        // - Extracts code identifiers using `text_extraction.extract_identifiers_by_language`.
        // - Attempts to get Git commit information (hash, author, date) for the file using `git log`.
        // - Formats all extracted information into a newline-separated string.
        string create_metadata(string file_path, string content);
    };
};
// == !! END IDL TEMPLATE !! ===
