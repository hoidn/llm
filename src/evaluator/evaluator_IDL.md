// == !! BEGIN IDL TEMPLATE !! ===
module src.evaluator.evaluator {

    # @depends_on(src.evaluator.interfaces.TemplateLookupInterface) // Provided by TaskSystem
    # @depends_on(src.task_system.template_utils.Environment) // For environment management

    // Note: This IDL describes the core **Template Evaluator** responsible for executing the internal AST derived from **atomic XML task templates** when invoked by the TaskSystem (e.g., via `execute_subtask_directly`).
    // It does **not** evaluate the S-expression DSL. It does **not** handle composite tasks like sequential, reduce, or loops defined in XML (these are removed).
    // For evaluation of the S-expression DSL used in programmatic workflows (`/task '(...)`), refer to the `SexpEvaluator` component defined in `src/sexp_evaluator/sexp_evaluator_IDL.md`.
    // The `SexpEvaluator` utilizes core system services (TaskSystem, Handler, MemorySystem) as its backend, which may indirectly involve this Template Evaluator for executing atomic steps defined in XML.
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
        // - Often returns a TaskResult dictionary for executable nodes.
        // - Returns literals or unresolved variable references as is (though typically called on executable nodes).
        // Behavior:
        // - Checks the type of the node (expected to be the root of an atomic task's body).
        // - Executes the logic defined within the atomic task template's body.
        // - When evaluating nodes within an atomic template body, variable resolution for `{{...}}` placeholders is confined to the parameters provided in the execution environment created specifically for that template call.
        // - Returns literals or unresolved variable references as is (though typically called on executable nodes).
        // - Does not handle composite task types (sequential, reduce, etc.) or S-expressions.
        // @raises_error(condition="TASK_FAILURE", description="Raised if evaluation of a sub-node fails.")
        Any evaluate(Any node, object env); // Second arg represents Environment


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
