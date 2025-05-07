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
        // - params is a dictionary mapping declared input parameter names (from template's `params` definition)
        //   to their evaluated values (from SubtaskRequest). Values can be simple types or complex objects/dictionaries
        //   (e.g., ContextGenerationInput dict, file content dict/string).
        // - handler is a valid BaseHandler instance to use for LLM execution.
        // - history_config is an optional HistoryConfigSettings object to control conversational history usage.
        // Postconditions:
        // - Returns a TaskResult dictionary representing the outcome of the atomic task execution (typically from the Handler call).
        // Behavior:
        // - Performs {{variable}} or {{variable.attribute}} substitution within the atomic_task_def's prompts/description.
        // - **Substitution Mechanism:** Uses a simple regular expression (`\{\{([\w.]+)\}\}`) to find placeholders. It converts the resolved parameter value to a string using `str()` before insertion. **Crucially, this mechanism does NOT support template engine features like filters (e.g., `{{ my_var | filter }}`) or complex logic within placeholders.** Placeholders must strictly match the `{{word.characters.or.dots}}` pattern.
        // - Substitution ONLY uses the key-value pairs provided in the `params` dictionary. Access to the caller's wider environment or any variables not explicitly passed in `params` is forbidden.
        // - Constructs the final HandlerPayload (prompts, model info from def, tools if applicable).
        // - It receives HistoryConfigSettings via the history_config parameter. These settings are passed through to the handler._execute_llm_call method to control conversational history usage for the LLM interaction.
        // - Invokes the appropriate method on the provided `handler` instance (e.g., `handler._execute_llm_call`).
        // - May perform output parsing/validation based on `atomic_task_def.output_format`.
        // - Returns the TaskResult from the handler, potentially adding output parsing info to notes.
        @raises_error(condition="ParameterError", description="Raised if substitution references a variable name not present as a key in the `params` dictionary or if the placeholder syntax is incompatible with the regex.")
        // @raises_error(condition="TASK_FAILURE", description="Propagated from the handler call if LLM execution fails.")
        // Expected JSON format for params: { "param_name": "value", ... }
        // Expected JSON format for return value: TaskResult structure { "status": "string", "content": "Any", "notes": { ... } }
        dict<string, Any> execute_body(
            object atomic_task_def, 
            dict<string, Any> params, 
            object handler,
            optional object history_config // Arg represents HistoryConfigSettings
        ); // Args represent ParsedAtomicTask, ParamsDict, BaseHandler, HistoryConfigSettings
    };
};
// == !! END IDL TEMPLATE !! ===
