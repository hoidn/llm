// == !! BEGIN IDL TEMPLATE !! ===
module src.task_system.task_system {

    # @depends_on(src.memory.memory_system.MemorySystem) // For context generation mediation
    # @depends_on(src.handler.base_handler.BaseHandler) // For obtaining handlers for execution

    // Interface for the Task System, responsible for managing and executing task templates.
    interface TaskSystem {

        // Constructor: Initializes the Task System.
        // Preconditions:
        // - memory_system is an optional instance of MemorySystem.
        // Postconditions:
        // - TaskSystem is initialized with empty template storage (`templates`, `template_index`).
        // - Reference to memory_system is stored.
        // - Handler cache and test mode flag are initialized.
        void __init__(optional object memory_system); // Arg represents MemorySystem

        // Enables or disables test mode.
        // Preconditions:
        // - enabled is a boolean value.
        // Postconditions:
        // - The internal `_test_mode` flag is set.
        // - If enabled, subsequent requests for handlers via `_get_handler` will return MockHandler instances.
        void set_test_mode(boolean enabled);

        // Executes a single *atomic* Task System template workflow directly from a SubtaskRequest.
        // This is the primary entry point for programmatic execution of registered *atomic* tasks,
        // typically invoked by the Dispatcher or SexpEvaluator.
        // Preconditions:
        // - request is a valid SubtaskRequest object containing type ('atomic'), name/subtype, inputs, optional file_paths, optional context_management overrides.
        // - env is a valid SexpEnvironment object (used for resolving potential variables *within* the request, e.g., in file paths or context queries, though direct inputs are primary).
        // Postconditions:
        // - Returns the final TaskResult dictionary from the executed atomic template.
        // - The result's 'notes' dictionary includes 'template_used', 'context_source', and 'context_files_count'.
        // - Returns a FAILED TaskResult if the template is not found or execution fails.
        // Behavior:
        // - Executes the workflow defined within a single *atomic* task template. Composite task types are not supported.
        // - This method is invoked by the `SexpEvaluator` when an S-expression calls a registered atomic task template identifier.
        // - Validates that the `request.type` is 'atomic'. Returns error if not.
        // - Identifies the target atomic template using `request.name` (preferred) or `request.type`/`request.subtype`. Returns error if not found.
        // - **Determines Context:** Resolves the final context settings and file paths using the following precedence:
        //   1. Files from `request.file_paths` (if provided via S-expression `(files ...)` arg) OVERRIDE any `<file_paths>` in the XML template.
        //   2. Context settings from `request.context_management` (if provided via S-expression `(context ...)` arg) OVERRIDE any `<context_management>` in the XML template.
        //   3. If not overridden by the request, settings from `<file_paths>` in the XML template are used.
        //   4. If not overridden by the request, settings from `<context_management>` in the XML template are used.
        //   5. If no settings are provided by request or template, system defaults for atomic tasks apply.
        // - Retrieves necessary file content (if file paths determined) via the Handler.
        // - Retrieves fresh context via `MemorySystem.get_relevant_context_for` if the final effective context settings require it. When calling, it constructs `ContextGenerationInput` populating `templateDescription` (from template), `templateType` ('atomic'), `templateSubtype` (if any), and relevant `inputs` (from the request). It does *not* typically populate the `query` field in this case unless specifically designed to.
        // - Creates a parameter dictionary containing the `request.inputs`.
        // - Obtains an appropriate Handler instance (e.g., via internal factory `_get_handler`).
        // - Instantiates the `AtomicTaskExecutor`.
        // - Calls `atomic_task_executor.execute_body`, passing the parsed template definition, the parameter dictionary, and the handler instance.
        // - Handles TaskErrors and unexpected exceptions from the executor, returning formatted error results.
        // - Includes execution metadata (template used, final context source/count) in the result notes.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Handled internally, returns FAILED TaskResult if template not found or type is not 'atomic'.")
        // @raises_error(condition="TASK_FAILURE", description="Handled internally, returns FAILED TaskResult.")
        // @raises_error(condition="UNEXPECTED_ERROR", description="Handled internally, returns FAILED TaskResult.")
        // Expected JSON format for request.inputs: { "param1": "value1", ... }
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "Any", "notes": { ... } }
        dict<string, Any> execute_atomic_template(object request, object env); // Args represent SubtaskRequest, SexpEnvironment

        // Finds matching atomic task templates based on similarity to input text.
        // Preconditions:
        // - input_text is a string describing the desired task.
        // - memory_system is a valid MemorySystem instance (currently unused in implementation but part of signature).
        // Postconditions:
        // - Returns a list of dictionaries, each representing a matching template.
        // - Each dictionary contains 'task' (the template dict), 'score' (float similarity), 'taskType', 'subtype'.
        // - The list is sorted by score in descending order. Returns empty list if no matches found.
        // Behavior:
        // - Iterates through registered templates, filtering for type="atomic".
        // - Calculates a similarity score (e.g., Jaccard index on words) between input_text and template description.
        // - Includes templates with scores above a threshold (e.g., 0.1).
        // Expected JSON format for return list items: { "task": { ... }, "score": "float", "taskType": "string", "subtype": "string" }
        list<dict<string, Any>> find_matching_tasks(string input_text, object memory_system); // Arg represents MemorySystem

        // Registers an *atomic* task template definition.
        // Preconditions:
        // - template is a dictionary representing the template, expected to have 'name', 'type', 'subtype'.
        // Expected JSON format for template: { "name": "string", "type": "string", "subtype": "string", "description": "string", "params": "string", ... }
        // Postconditions:
        // - The template is validated and enhanced for compatibility (using `ensure_template_compatibility`).
        // - Performs validation to ensure the template definition includes the required parameter declaration (e.g., a non-missing `params` attribute in the source).
        // - The template is stored in the internal `templates` dictionary, keyed by its 'name'.
        // - An index mapping 'type:subtype' to the template 'name' is updated in `template_index`.
        // Note: Composite tasks are no longer registered here; they are defined and executed via S-expressions.
        void register_template(dict<string, Any> template);

        // Finds a template definition by its identifier.
        // Used by Dispatcher/SexpEvaluator to locate atomic tasks.
        // Preconditions:
        // - identifier is a string, either the template's unique 'name' or its 'type:subtype' combination.
        // Postconditions:
        // - Returns the template definition dictionary if found.
        // - Returns None if no template matches the identifier.
        // Behavior:
        // - First attempts lookup by direct name in the `templates` dictionary.
        // - If not found by name, attempts lookup using the identifier as a 'type:subtype' key in the `template_index`.
        // Only searches for templates of type 'atomic'.
        optional dict<string, Any> find_template(string identifier);

        // Generates context for the Memory System, acting as a mediator.
        // This method delegates the actual context generation (often involving LLM calls)
        // to a specialized task ('atomic:associative_matching') executed via the appropriate Handler.
        // Preconditions:
        // - context_input is a valid ContextGenerationInput object containing details about the required context.
        // - global_index is a dictionary mapping file paths to their metadata strings.
        // - The TaskSystem must have a valid reference to the MemorySystem, which in turn must have a valid Handler.
        // Postconditions:
        // - Returns an AssociativeMatchResult object containing a context summary string and a list of MatchTuple objects (path, relevance, score).
        // - Returns an empty/error result if the Handler is not available or the context generation task fails.
        // Behavior:
        // - Verifies that a Handler instance is accessible via the MemorySystem.
        // - Formats the global_index metadata and context_input into parameters for the 'atomic:associative_matching' task.
        // - Executes the 'atomic:associative_matching' task using `execute_task`, passing the correct Handler.
        // - Parses the JSON response from the task execution (expected to be a list of file objects with path, relevance, score).
        // - Validates and formats the parsed file list into MatchTuple objects.
        // - Constructs and returns the final AssociativeMatchResult.
        // @raises_error(condition="TASK_FAILURE", reason="dependency_error", description="Handled internally, returns error result if Handler not available.")
        // @raises_error(condition="TASK_FAILURE", reason="output_format_failure", description="Handled internally, returns error/empty result if JSON parsing fails.")
        // @raises_error(condition="TASK_FAILURE", description="If the underlying context generation task fails.")
        // Expected JSON format for global_index: { "path/to/file": "metadata string", ... }
        // Returns: AssociativeMatchResult object
        object generate_context_for_memory_system(object context_input, dict<string, string> global_index); // Args represent ContextGenerationInput, AssociativeMatchResult

        // Resolves the final list of file paths to be used for context based on template settings.
        // Preconditions:
        // - template is a dictionary representing a fully resolved task template (variables substituted).
        // - memory_system is a valid MemorySystem instance.
        // - handler is a valid Handler instance (needed for command execution).
        // Postconditions:
        // - Returns a tuple: (list_of_file_paths, optional_error_message).
        // - The list contains absolute file paths determined by the template's context strategy.
        // - error_message is a string if context retrieval failed (e.g., command error), otherwise None.
        // Behavior:
        // - Aggregates paths from multiple sources based on template configuration:
        //   - Explicit `file_paths` defined in the template.
        //   - Context generated via MemorySystem using `template['_context_input']` (if present).
        //   - Paths retrieved using `memory_system.get_relevant_context_with_description` if `file_paths_source.type` is 'description'.
        //   - Paths obtained by executing a command via the handler if `file_paths_source.type` is 'command'.
        // - Handles potential errors during context retrieval or command execution.
        tuple<list<string>, optional string> resolve_file_paths(dict<string, Any> template, object memory_system, object handler); // Args represent MemorySystem, BaseHandler
    };
};
// == !! END IDL TEMPLATE !! ===
