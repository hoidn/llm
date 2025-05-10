// == !! BEGIN IDL TEMPLATE !! ===
module src.handler.file_context_manager {

    # @depends_on(src.memory.memory_system.MemorySystem) // For context retrieval (though direct usage by BaseHandler is now preferred for some ops)
    # @depends_on(src.handler.file_access.FileAccessManager) // For reading files
    # @depends_on_type(docs.system.contracts.types.MatchItem) // For MatchItem type
    # @depends_on_type(docs.system.contracts.types.AssociativeMatchResult) // For deprecated method

    // Interface for the File Context Manager.
    // Provides utility functions for retrieving and formatting file-based context,
    // acting as a helper to components like BaseHandler.
    // It uses MemorySystem for relevance and FileAccessManager for direct file operations.
    interface FileContextManager {

        // Constructor: Initializes the File Context Manager.
        // Preconditions:
        // - memory_system is a valid MemorySystem instance.
        // - file_access_manager is a valid FileAccessManager instance.
        // Postconditions:
        // - Manager is initialized with references to MemorySystem and FileAccessManager.
        void __init__(
            object memory_system, // Represents MemorySystem instance
            object file_access_manager // Represents FileAccessManager instance
        );

        // Creates MatchItem objects for a list of file paths, reading their content.
        // Preconditions:
        // - file_paths is a list of strings representing file paths.
        // Postconditions:
        // - Returns a list of MatchItem objects. Each MatchItem will have its 'id' set to the
        //   absolute path, 'content' populated with file content (if readable and not too large),
        //   'relevance_score' set to 1.0 (by default, can be adjusted by caller),
        //   'content_type' to "file_content", and 'source_path' to the absolute path.
        // - Logs warnings for files that cannot be read or are too large.
        // Behavior:
        // - Iterates through file_paths.
        // - For each path, calls self.file_manager.read_file().
        // - If successful, creates and appends a MatchItem.
        list<object> get_match_items_for_paths(list<string> file_paths); // Returns List<MatchItem>

        // Ensures a MatchItem has its content populated, fetching it if necessary using FileAccessManager.
        // Preconditions:
        // - item is a MatchItem object.
        // Postconditions:
        // - Modifies item.content in-place if content was missing and successfully fetched.
        // - If content cannot be fetched, item.content remains or is set to None.
        // Behavior:
        // - Checks if item.content is already populated.
        // - If not, uses item.id (or item.source_path if available) to read the file via self.file_manager.read_file().
        // - Updates item.content with the fetched content or sets to None on failure.
        void ensure_match_item_content(object item); // Param is MatchItem

        // (DEPRECATED: BaseHandler now calls MemorySystem directly for its primary context priming.)
        // Retrieves relevant MatchItems based on a query using the MemorySystem.
        // This method primarily delegates to MemorySystem.
        // Preconditions:
        // - query is a non-empty string for relevance matching.
        // Postconditions:
        // - Returns an AssociativeMatchResult object containing MatchItems.
        // - Returns an AssociativeMatchResult with an error field if retrieval fails.
        // Behavior:
        // - Constructs a ContextGenerationInput object.
        // - Calls `memory_system.get_relevant_context_for(input_data)`.
        // - Returns the result from MemorySystem.
        // @raises_error(None) // Errors from MemorySystem are expected to be in AssociativeMatchResult.error
        object get_relevant_items_for_query(string query); // Returns AssociativeMatchResult

        // (DEPRECATED: BaseHandler._create_data_context_string now handles this with MatchItems.)
        // Creates a single formatted string from a list of file paths by reading their content.
        // This is a more traditional "create file context string from paths" method.
        // Preconditions:
        // - file_paths is a list of strings representing file paths.
        // - max_total_chars is an optional int to limit the total length of the combined context.
        // Postconditions:
        // - Returns a single string containing the formatted content of the specified files,
        //   potentially truncated or summarized if limits are hit.
        // Behavior:
        // - Iterates `file_paths`. For each, reads content via `file_access_manager.read_file()`.
        // - Formats each file's content (e.g., with path headers).
        // - Concatenates formatted content, respecting `max_total_chars`.
        // - May involve truncation or summarization strategies if content exceeds limits.
        // @raises_error(condition="FileAccessError", description="If reading any of the files fails.")
        string build_context_string_from_paths(list<string> file_paths, optional int max_total_chars);
    };
}
// == !! END IDL TEMPLATE !! ===
