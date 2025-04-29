// == !! BEGIN IDL TEMPLATE !! ===
module src.task_system.task_system {

    # @depends_on(src.handler.base_handler.BaseHandler) // For context generation and file operations
    # @depends_on(src.executors.atomic_executor.AtomicTaskExecutor) // For executing atomic task bodies
    # @depends_on(src.memory.memory_system.MemorySystem) // For context retrieval

    // Interface for the Task System. Manages and executes task templates.
    interface TaskSystem {

        // Constructor: Initializes the Task System.
        // Preconditions:
        // - memory_system is an optional MemorySystem instance.
        // Postconditions:
        // - TaskSystem is initialized with an empty template registry (`_templates`).
        // - Reference to memory_system is stored if provided.
        // - Test mode flag (`_test_mode`) is initialized to false.
        void __init__(optional object memory_system); // Arg represents MemorySystem

        // Enables or disables test mode.
        // Preconditions:
        // - enabled is a boolean value.
        // Postconditions:
        // - The internal test mode flag (`_test_mode`) is set to the value of `enabled`.
        // - When test mode is enabled, certain operations may use simplified or mock behavior.
        void set_test_mode(boolean enabled);

        // Internal method to get a BaseHandler instance.
        // Preconditions: None.
        // Postconditions:
        // - Returns a BaseHandler instance, either from an internal cache or by creating a new one.
        // Behavior:
        // - If an internal handler reference exists, returns it.
        // - Otherwise, attempts to create a new BaseHandler instance.
        // - In test mode, may return a simplified mock handler.
        // @raises_error(condition="DEPENDENCY_ERROR", description="If handler creation fails.")
        object _get_handler(); // Returns BaseHandler

        // Validates and merges context management settings from template and request.
        // Preconditions:
        // - template_settings is an optional dictionary containing context management settings from a template.
        // - request_settings is an optional dictionary containing context management settings from a SubtaskRequest.
        // - subtype is a string indicating the atomic task subtype (e.g., "standard", "subtask").
        // Postconditions:
        // - Returns a merged ContextManagement object with settings from both sources, with request_settings taking precedence.
        // - If neither source provides settings, returns default settings based on the subtype.
        // Behavior:
        // - Starts with default settings appropriate for the subtype.
        // - Applies template_settings if provided.
        // - Applies request_settings if provided, overriding any conflicting settings.
        // - Validates the resulting settings for logical consistency (e.g., freshContext="enabled" cannot be combined with inheritContext="full").
        // @raises_error(condition="VALIDATION_ERROR", description="If the merged settings are logically inconsistent.")
        object _validate_and_merge_context_settings(
            optional dict<string, Any> template_settings,
            optional dict<string, Any> request_settings,
            string subtype
        ); // Returns ContextManagement

        // Executes an atomic template based on a SubtaskRequest.
        // Preconditions:
        // - request is a valid SubtaskRequest object containing at minimum 'name' and 'inputs'.
        // Expected JSON format for request: SubtaskRequest structure { "type": "atomic", "name": "string", "inputs": { ... }, ... }
        // Postconditions:
        // - Returns a TaskResult object representing the outcome of the template execution.
        // - Returns a FAILED TaskResult if the template is not found or execution fails.
        // Behavior:
        // - This method only executes templates of type "atomic".
        // - Finds the template by name using `find_template`.
        // - Validates and merges context management settings from the template and request.
        // - If file_paths are specified in the request, uses those directly.
        // - Otherwise, resolves file paths based on the template and context settings using `resolve_file_paths`.
        // - If fresh context is enabled, retrieves relevant context from the MemorySystem.
        // - Prepares the final context by combining inherited context, fresh context, and previous outputs based on context settings.
        // - Instantiates an AtomicTaskExecutor and calls its `execute_body` method with the template definition,
        //   the evaluated `request.inputs` (as the `params` dictionary), and a BaseHandler instance.
        // - The executor operates in an isolated scope, using only the passed parameters for substitution.
        // - Returns the TaskResult from the executor, potentially with additional notes about context usage.
        // @raises_error(condition="TEMPLATE_NOT_FOUND", description="Handled internally, returns FAILED TaskResult.")
        // @raises_error(condition="CONTEXT_RETRIEVAL_FAILURE", description="Handled internally, returns FAILED TaskResult.")
        // @raises_error(condition="EXECUTION_ERROR", description="Handled internally, returns FAILED TaskResult.")
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "string", "notes": { ... } }
        object execute_atomic_template(object request); // Arg represents SubtaskRequest, returns TaskResult

        // Finds templates matching a natural language input.
        // Preconditions:
        // - input_text is a string containing the natural language query or task description.
        // - memory_system is an optional MemorySystem instance for context retrieval.
        // Postconditions:
        // - Returns a list of tuples, each containing an atomic template identifier and a relevance score (0.0 to 1.0).
        // - The list is sorted by relevance score in descending order.
        // - Returns an empty list if no matching templates are found.
        // Behavior:
        // - This method only searches for and considers templates where `type` is "atomic".
        // - Filters the template registry for atomic templates.
        // - For each template, calculates a relevance score based on similarity between the input_text and the template's name, description, and other metadata.
        // - If memory_system is provided, may use it to enhance matching with relevant context.
        // - Sorts the results by relevance score and returns the top matches.
        // - In test mode, may return simplified or predetermined matches.
        // Expected JSON format for return value: [ ["template_id", 0.95], ["another_template", 0.82], ... ]
        list<tuple<string, float>> find_matching_tasks(string input_text, optional object memory_system); // Second arg represents MemorySystem

        // Registers a template with the TaskSystem.
        // Preconditions:
        // - template is a dictionary representing a valid task template.
        // - The template must have a 'name' field as its identifier.
        // - The template dictionary MUST contain a 'params' key defining its accepted parameters.
        // - The template dictionary MUST have 'type' set to "atomic".
        // Expected JSON format for template: { "name": "string", "type": "atomic", "subtype": "string", ... }
        // Postconditions:
        // - The template is added to the internal template registry (`_templates`), keyed by its name.
        // - If a template with the same name already exists, it is overwritten.
        // Behavior:
        // - Validates that the template has a 'name' field.
        // - Adds the template to the registry.
        // - May perform additional validation or preprocessing of the template.
        // - Templates with a 'type' other than "atomic" will be ignored and not registered.
        // @raises_error(condition="VALIDATION_ERROR", description="If the template is missing required fields or has invalid structure.")
        void register_template(dict<string, Any> template);

        // Finds a template by its identifier.
        // Preconditions:
        // - identifier is a string representing the template name or ID.
        // Postconditions:
        // - Returns the atomic template dictionary if found.
        // - Returns None if no template with the given identifier exists.
        // Behavior:
        // - This method only searches for and considers templates where `type` is "atomic".
        // - Looks up the template in the internal registry (`_templates`) by the identifier.
        // - May perform additional processing or validation before returning the template.
        optional dict<string, Any> find_template(string identifier);

        // Generates context for the Memory System using an associative matching template.
        // Preconditions:
        // - context_input is a ContextGenerationInput object containing query information.
        // - global_index is a dictionary mapping file paths to metadata strings.
        // Expected JSON format for context_input: ContextGenerationInput structure { "query": "string", ... }
        // Expected JSON format for global_index: { "file_path": "metadata_string", ... }
        // Postconditions:
        // - Returns an AssociativeMatchResult object containing matched files and a context summary.
        // - Returns an error result if context generation fails.
        // Behavior:
        // - Finds the internal associative_matching template.
        // - Creates a SubtaskRequest with the context_input and global_index as inputs.
        // - Calls execute_atomic_template with this request.
        // - Parses the TaskResult to extract the AssociativeMatchResult.
        // - Handles potential errors during template execution or result parsing.
        // @raises_error(condition="TEMPLATE_NOT_FOUND", description="Handled internally, returns error result.")
        // @raises_error(condition="EXECUTION_ERROR", description="Handled internally, returns error result.")
        // @raises_error(condition="PARSING_ERROR", description="Handled internally, returns error result.")
        // Returns: AssociativeMatchResult object
        object generate_context_for_memory_system(object context_input, dict<string, string> global_index); // First arg represents ContextGenerationInput

        // Resolves file paths for a template execution based on various sources.
        // Preconditions:
        // - template is a dictionary representing a task template.
        // - memory_system is an optional MemorySystem instance for context retrieval.
        // - handler is an optional BaseHandler instance for command execution.
        // Expected JSON format for template: { "file_paths_source": { "type": "string", ... }, ... }
        // Postconditions:
        // - Returns a list of file paths relevant to the template execution.
        // - Returns an empty list if no relevant files are found or if file path resolution fails.
        // Behavior:
        // - Examines the template's file_paths_source configuration to determine the resolution method.
        // - Depending on the source type:
        //   - "literal": Returns the literal file paths specified in the template.
        //   - "command": Executes the specified command via handler.execute_file_path_command and returns the result.
        //   - "description": Uses memory_system.get_relevant_files with the provided description.
        //   - "context_description": Similar to "description" but may use a different method or context.
        // - Handles potential errors during resolution.
        // @raises_error(condition="INVALID_SOURCE_TYPE", description="Handled internally, returns empty list.")
        // @raises_error(condition="COMMAND_EXECUTION_FAILURE", description="Handled internally, returns empty list.")
        // @raises_error(condition="CONTEXT_RETRIEVAL_FAILURE", description="Handled internally, returns empty list.")
        list<string> resolve_file_paths(
            dict<string, Any> template,
            optional object memory_system,
            optional object handler
        ); // Args represent template dict, MemorySystem, BaseHandler

        // Invariants:
        // - `_templates` is always a dictionary mapping template names to template definitions.
        // - `_memory_system` is either None or a valid MemorySystem instance.
    };
};
// == !! END IDL TEMPLATE !! ===
