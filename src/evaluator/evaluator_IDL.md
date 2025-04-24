// == !! BEGIN IDL TEMPLATE !! ===
module src.evaluator.evaluator {

    # @depends_on(src.evaluator.interfaces.TemplateLookupInterface) // Provided by TaskSystem
    # @depends_on(src.task_system.template_utils.Environment) // For environment management

    // Interface for the Evaluator component, responsible for evaluating AST nodes.
    // Conceptually implements src.evaluator.interfaces.EvaluatorInterface.
    interface Evaluator { // implements EvaluatorInterface

        // Constructor: Initializes the Evaluator.
        // Preconditions:
        // - template_provider is an instance implementing TemplateLookupInterface (e.g., TaskSystem).
        // Postconditions:
        // - Evaluator is initialized with the template provider dependency.
        void __init__(object template_provider); // Arg represents TemplateLookupInterface

        // Evaluates an AST node within a given environment.
        // Preconditions:
        // - node is an AST node object (e.g., FunctionCallNode, DirectorEvaluatorLoopNode, literal).
        // - env is a valid Environment instance.
        // Postconditions:
        // - Returns the result of evaluating the node. The type depends on the node evaluated.
        // - Often returns a TaskResult dictionary for executable nodes like function calls or loops.
        // - Returns literals or unresolved variable references as is.
        // Behavior:
        // - Checks the type of the node.
        // - Delegates evaluation to specific methods based on node type (e.g., `evaluateFunctionCall`, `_evaluate_director_evaluator_loop`).
        // - Returns the node itself for unrecognized or literal types.
        // @raises_error(condition="TASK_FAILURE", description="Raised if evaluation of a sub-node fails.")
        Any evaluate(Any node, object env); // Second arg represents Environment

        // Evaluates a function call AST node. Canonical path for all function calls.
        // Preconditions:
        // - call_node is a valid FunctionCallNode object.
        // - env is a valid Environment instance.
        // - template is an optional pre-fetched template dictionary to avoid redundant lookups.
        // Postconditions:
        // - Returns a TaskResult dictionary representing the outcome of the function execution.
        // - Returns a FAILED TaskResult if template lookup, argument binding, or execution fails.
        // - If the template specifies JSON output and parsing succeeds, the parsed object is available in `TaskResult.parsedContent`.
        // Behavior:
        // - Looks up the template using the `template_provider` if not provided.
        // - Evaluates function call arguments in the caller's environment (`env`) using `_evaluate_arguments`.
        // - Binds the evaluated arguments to the template's parameters using `_bind_arguments_to_parameters`.
        // - Creates a new function execution environment by extending `env` with the parameter bindings.
        // - Executes the template logic via `_execute_template` (which calls `template_provider.execute_task`).
        // - Handles TaskErrors and other exceptions during the process.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Handled internally, returns FAILED TaskResult if template not found.")
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Handled internally, returns FAILED TaskResult if argument binding fails.")
        // @raises_error(condition="TASK_FAILURE", description="Handled internally, returns FAILED TaskResult if execution fails.")
        // @raises_error(condition="UNEXPECTED_ERROR", description="Handled internally, returns FAILED TaskResult for other exceptions.")
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "Any", "notes": { ... } }
        dict<string, Any> evaluateFunctionCall(object call_node, object env, optional dict<string, Any> template); // Args represent FunctionCallNode, Environment

        // Executes a subtask template with appropriate environment isolation.
        // Preconditions:
        // - inputs is a dictionary of parameters for the subtask template.
        // - template is the dictionary definition of the subtask template.
        // - parent_env is an optional Environment instance from the caller.
        // - isolate is a boolean indicating whether the subtask environment should inherit (`false`) or be isolated (`true`, default).
        // Expected JSON format for inputs: { "param1": "value1", ... }
        // Expected JSON format for template: { "name": "string", ... }
        // Postconditions:
        // - Returns the TaskResult dictionary from the subtask execution.
        // Behavior:
        // - Creates a new Environment for the subtask. If `isolate` is false and `parent_env` is provided, the new environment extends the parent; otherwise, it's created solely from `inputs`.
        // - Executes the subtask template via `_execute_template` using the created environment.
        // @raises_error(condition="TASK_FAILURE", description="Propagated from _execute_template.")
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "Any", "notes": { ... } }
        dict<string, Any> execute_subtask(dict<string, Any> inputs, dict<string, Any> template, optional object parent_env, boolean isolate); // Arg represents Environment
    };
};
// == !! END IDL TEMPLATE !! ===
