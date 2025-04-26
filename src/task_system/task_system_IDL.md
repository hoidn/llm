// == !! BEGIN IDL TEMPLATE !! ===
module src.task_system.task_system {

    # @depends_on(src.evaluator.interfaces.EvaluatorInterface) // For executing function calls in templates
    # @depends_on(src.memory.memory_system.MemorySystem) // For context generation mediation
    # @depends_on(src.handler.base_handler.BaseHandler) // For obtaining handlers for execution
    # @depends_on(src.task_system.template_utils.Environment) // For environment management

    // Interface for the Task System, responsible for managing and executing task templates.
    // Conceptually implements src.evaluator.interfaces.TemplateLookupInterface.
    interface TaskSystem { // implements TemplateLookupInterface

        // Constructor: Initializes the Task System.
        // Preconditions:
        // - evaluator is an optional instance implementing EvaluatorInterface. If None, it will be lazy-initialized.
        // - memory_system is an optional instance of MemorySystem.
        // Postconditions:
        // - TaskSystem is initialized with empty template storage (`templates`, `template_index`).
        // - References to evaluator and memory_system are stored.
        // - TemplateProcessor is instantiated.
        // - Handler cache and test mode flag are initialized.
        void __init__(optional object evaluator, optional object memory_system); // Args represent EvaluatorInterface, MemorySystem

        // Enables or disables test mode.
        // Preconditions:
        // - enabled is a boolean value.
        // Postconditions:
        // - The internal `_test_mode` flag is set.
        // - If enabled, subsequent requests for handlers via `_get_handler` will return MockHandler instances.
        void set_test_mode(boolean enabled);

        // Executes a function call represented by an AST node using the Evaluator.
        // Preconditions:
        // - call is a valid FunctionCallNode object.
        // - env is an optional Environment instance. A new one is created if None.
        // Postconditions:
        // - Ensures the Evaluator is initialized.
        // - Delegates the evaluation of the FunctionCallNode to the configured Evaluator.
        // - Returns a TaskResult dictionary representing the outcome of the function execution.
        // - Wraps exceptions (TaskError, other) into a FAILED TaskResult.
        // Behavior:
        // - Handles specific test templates ("greeting", "format_date") directly for compatibility.
        // - For other calls, invokes `evaluator.evaluateFunctionCall`.
        // @raises_error(condition="TASK_FAILURE", description="Handled internally, returns FAILED TaskResult.")
        // @raises_error(condition="UNEXPECTED_ERROR", description="Handled internally, returns FAILED TaskResult.")
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "Any", "notes": { ... } }

        // Executes a Task System template workflow directly from a SubtaskRequest.
        // This is a primary entry point for programmatic task execution via Dispatcher.
        // Preconditions:
        // - request is a valid SubtaskRequest object containing type, subtype, inputs, optional file_paths, optional history_context.
        // - env is a valid Environment object (provides base context, often empty initially).
        // Postconditions:
        // - Returns the final TaskResult dictionary from the executed workflow.
        // - The result's 'notes' dictionary includes 'template_used', 'context_source', and 'context_files_count'.
        // - Returns a FAILED TaskResult if the template is not found or execution fails.
        // Behavior:
        // - Executes the workflow defined within a single *atomic* task template. Composite task types (sequential, reduce, etc.) are not supported here.
        // - This method is invoked by the `SexpEvaluator` when an S-expression calls a registered atomic task template identifier.
        // - Identifies the target *atomic* template using request.type and request.subtype. Returns error if not atomic or not found.
        // - Determines the file context based on template definition, request.file_paths, or automatic lookup (via MemorySystem) as configured in the template's context_management and the request.
        // - Creates a new execution environment for the core Template Evaluator containing bindings *only* for the template's declared parameters, populated from the `request.inputs`.
        // - Obtains an appropriate Handler instance via `_get_handler`.
        // - Calls the core **Template Evaluator** to execute the atomic template's body within the created environment and context.
        // - Handles TaskErrors and unexpected exceptions, returning formatted error results.
        // - Includes execution metadata (template used, context source/count) in the result notes.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Handled internally, returns FAILED TaskResult if template not found.")
        // @raises_error(condition="TASK_FAILURE", description="Handled internally, returns FAILED TaskResult.")
        // @raises_error(condition="UNEXPECTED_ERROR", description="Handled internally, returns FAILED TaskResult.")
        // Expected JSON format for request.inputs: { "param1": "value1", ... }
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "Any", "notes": { ... } }
        dict<string, Any> execute_subtask_directly(object request, object env); // Args represent SubtaskRequest, Environment

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

        // Registers a task template definition.
        // Preconditions:
        // - template is a dictionary representing the template, expected to have 'name', 'type', 'subtype'.
        // Expected JSON format for template: { "name": "string", "type": "string", "subtype": "string", "description": "string", "params": "string", ... }
        // Postconditions:
        // - The template is validated and enhanced for compatibility (using `ensure_template_compatibility`).
        // - Performs validation to ensure the template definition includes the required parameter declaration (e.g., a non-missing `params` attribute in the source).
        // - The template is stored in the internal `templates` dictionary, keyed by its 'name'.
        // - An index mapping 'type:subtype' to the template 'name' is updated in `template_index`.
        void register_template(dict<string, Any> template);

        // Finds a template definition by its identifier.
        // Implements TemplateLookupInterface.find_template.
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

        // Executes a task specified by type and subtype. Core execution logic.
        // Implements TemplateLookupInterface.execute_task.
        // Preconditions:
        // - task_type and task_subtype identify a registered template.
        // - inputs is a dictionary of parameters for the task.
        // - memory_system is an optional MemorySystem instance.
        // - available_models is an optional list of model names for handler selection.
        // - call_depth indicates recursion depth for function calls (defaults to 0).
        // - handler is an optional specific Handler instance to use; if None, one is obtained via `_get_handler`.
        // - kwargs may contain 'inherited_context', 'previous_outputs', 'handler_config'.
        // Postconditions:
        // - Returns a TaskResult dictionary representing the outcome.
        // - Returns a FAILED TaskResult if the template is not found, parameter validation fails, or execution fails.
        // - If the template specifies JSON output and parsing succeeds, the parsed object is available in `TaskResult.parsedContent`.
        // Behavior:
        // - Finds the specified template.
        // - Resolves input parameters against the template schema (`resolve_parameters`).
        // - Selects the appropriate Handler instance based on model preference or defaults.
        // - Manages context based on template's `context_management` settings (inheritance, accumulation, fresh lookup).
        // - Processes the template using TemplateProcessor (substitutes variables, resolves function calls).
        // - Note on Context: Follows hybrid config (defaults + overrides). `fresh_context='enabled'` is mutually exclusive with `inherit_context='full'/'subset'`.
        // - Resolves the final file paths for context using `resolve_file_paths`.
        // - Executes the task logic:
        //   - For specialized atomic tasks (e.g., 'associative_matching', 'format_json'), calls internal handlers.
        //   - For general tasks, calls `handler.execute_prompt` with the processed description, system prompt, and file context.
        // - Includes context management info and selected model (if any) in the result notes.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Handled internally, returns FAILED TaskResult if template not found.")
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Handled internally, returns FAILED TaskResult if parameter validation fails.")
        // @raises_error(condition="TASK_FAILURE", description="Handled internally, returns FAILED TaskResult if context retrieval fails.")
        // @raises_error(condition="TASK_FAILURE", description="Handled internally by handler, returns FAILED TaskResult if execution fails.")
        // Expected JSON format for inputs: { "param1": "value1", ... }
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "Any", "notes": { ... } }
        dict<string, Any> execute_task(
            string task_type,
            string task_subtype,
            dict<string, Any> inputs,
            optional object memory_system, // Represents MemorySystem
            optional list<string> available_models,
            optional int call_depth,
            optional object handler, // Represents BaseHandler
            // Note: Implicit kwargs like inherited_context, previous_outputs, handler_config influence behavior. See description.
        );
    };
};
// == !! END IDL TEMPLATE !! ===
