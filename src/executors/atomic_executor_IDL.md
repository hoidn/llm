// == !! BEGIN IDL TEMPLATE !! ===
module src.executors.atomic_executor {

    # @depends_on(src.handler.base_handler.BaseHandler) // For invoking the handler
    # @depends_on(src.system.types.TaskResult) // Return type

    // Interface for the Atomic Task Executor.
    // Responsible for executing the body of a pre-parsed atomic task template using provided parameters.
    // It handles parameter substitution and invokes the necessary Handler method.
    // It does **not** evaluate S-expressions or handle task composition.
    // For S-expression evaluation, refer to the `SexpEvaluator` component.
    interface AtomicTaskExecutor {

        // Constructor: Initializes the AtomicTaskExecutor.
        // Preconditions: None (dependencies are passed to execute_body).
        // Postconditions: Executor is initialized.
        void __init__();

        // Executes the body of a pre-parsed atomic task template.
        // Preconditions:
        // - atomic_task_def is a representation of the parsed atomic task XML (e.g., a dictionary or object).
        // - params is a dictionary mapping declared input parameter names (from template's <inputs>) to their evaluated values (from SubtaskRequest).
        // - handler is a valid BaseHandler instance to use for LLM execution.
        // Postconditions:
        // - Returns a TaskResult dictionary representing the outcome of the atomic task execution (typically from the Handler call).
        // Behavior:
        // - Performs {{parameter_name}} substitution within the atomic_task_def's prompts/description using ONLY the provided `params` dictionary.
        // - Constructs the final HandlerPayload (prompts, model info from def, tools if applicable).
        // - Invokes the appropriate method on the provided `handler` instance (e.g., `handler.executePrompt`).
        // - May perform output parsing/validation based on `atomic_task_def.output_format`.
        // - Returns the TaskResult from the handler, potentially adding output parsing info to notes.
        // @raises_error(condition="ParameterMismatch", description="Raised if substitution references a parameter name not present in the `params` dictionary.")
        // @raises_error(condition="TASK_FAILURE", description="Propagated from the handler call if LLM execution fails.")
        // Expected JSON format for params: { "param_name": "value", ... }
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "Any", "notes": { ... } }
        dict<string, Any> execute_body(object atomic_task_def, dict<string, Any> params, object handler); // Args represent ParsedAtomicTask, ParamsDict, BaseHandler
    };
};
// == !! END IDL TEMPLATE !! ===
