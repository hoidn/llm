// == !! BEGIN IDL TEMPLATE !! ===
module src.evaluator.interfaces {

    // Interface defining the contract for AST evaluation.
    // Based on the EvaluatorInterface Protocol.
    // Implementations are responsible for evaluating AST nodes,
    // particularly function calls, managing variable bindings,
    // and handling execution context.
    interface EvaluatorInterface {

        // Evaluates a function call AST node.
        // This is the canonical execution path for all function calls.
        // Preconditions:
        // - call_node is a FunctionCallNode object.
        // - env is a valid Environment object.
        // - template is an optional dictionary representing a pre-fetched template.
        // Postconditions:
        // - Returns the result of the function execution as a TaskResult dictionary.
        // Behavior:
        // - Implementations should look up the template if not provided.
        // - Evaluate arguments in the caller's environment (env).
        // - Bind arguments to template parameters.
        // - Execute the template logic.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Raised if the template specified in call_node cannot be found.")
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Raised if arguments cannot be bound to template parameters.")
        // @raises_error(condition="SUBTASK_FAILURE", description="Raised if an error occurs during template execution.")
        // @raises_error(condition="TaskError", description="Generic task error during evaluation.")
        // Expected JSON format for return value: { "status": "string", "content": "Any", "notes": { ... } } (TaskResult structure)
        dict<string, Any> evaluateFunctionCall(FunctionCallNode call_node, Environment env, optional dict<string, Any> template);

        // Evaluates an arbitrary AST node in the given environment.
        // Preconditions:
        // - node is an AST node object.
        // - env is a valid Environment object.
        // Postconditions:
        // - Returns the result of evaluating the node. The type depends on the node.
        // Behavior:
        // - Implementations should handle different AST node types (e.g., literals, variable references, function calls).
        // - Delegates to evaluateFunctionCall for call nodes.
        // @raises_error(condition="TaskError", description="Generic task error during evaluation.")
        Any evaluate(Any node, Environment env);
    };

    // Interface for template lookup operations.
    // Based on the TemplateLookupInterface Protocol.
    // Implemented by components (like TaskSystem) that manage templates.
    interface TemplateLookupInterface {

        // Finds a template by its identifier (name or type:subtype).
        // Preconditions:
        // - identifier is a non-empty string.
        // Postconditions:
        // - Returns the template definition dictionary if found.
        // - Returns None if no template matches the identifier.
        // Behavior:
        // - Searches registered templates using the provided identifier.
        optional dict<string, Any> find_template(string identifier);

        // Executes a task defined by a template.
        // Preconditions:
        // - task_type and task_subtype identify a registered template.
        // - inputs is a dictionary of parameters conforming to the template's requirements.
        // Postconditions:
        // - Executes the workflow defined by the identified template.
        // - Returns a TaskResult dictionary representing the outcome.
        // Behavior:
        // - Looks up the template using type/subtype.
        // - Validates and binds inputs to template parameters.
        // - Executes the template logic (potentially involving LLM calls or other actions).
        // @raises_error(condition="TemplateNotFound", description="Raised if the template specified by type/subtype cannot be found.")
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Raised if inputs are invalid for the template.")
        // @raises_error(condition="SUBTASK_FAILURE", description="Raised if an error occurs during task execution.")
        // @raises_error(condition="TaskError", description="Generic task error during execution.")
        // Expected JSON format for inputs: { "param1": "value1", ... }
        // Expected JSON format for return value: { "status": "string", "content": "Any", "notes": { ... } } (TaskResult structure)
        dict<string, Any> execute_task(string task_type, string task_subtype, dict<string, Any> inputs);
    };
};
// == !! END IDL TEMPLATE !! ===
