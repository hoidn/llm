// == !! BEGIN IDL TEMPLATE !! ===
module src.dispatcher {

    # @depends_on(src.handler.base_handler.BaseHandler) // Passed as argument, needed for direct tools
    # @depends_on(src.task_system.task_system.TaskSystem) // Passed as argument, needed for template execution
    # @depends_on(src.task_system.ast_nodes.SubtaskRequest) // Used internally to call TaskSystem
    # @depends_on(src.system.models.TaskResult) // Return type
    # @depends_on(src.system.errors.TaskError) // Error handling

    // Interface representing the dispatcher functionality.
    // Routes programmatic task requests (/task command) to the appropriate executor.
    interface DispatcherFunctions {

        // Routes a programmatic task request to the appropriate executor (TaskSystem template or Handler direct tool).
        // Preconditions:
        // - identifier is a string (task type:subtype or direct tool name).
        // - params is a dictionary of task parameters. Must be JSON-serializable.
        // - flags is a dictionary of boolean flags (e.g., {"use-history": true}).
        // - handler_instance is a valid instance implementing BaseHandler.
        // - task_system_instance is a valid instance implementing TaskSystem.
        // - memory_system is a valid instance implementing MemorySystem.
        // - optional_history_str is an optional string of recent conversation history.
        // Expected JSON format for params: { "param1": "value1", "file_context?": "list<string> | string (JSON array)", ... }
        // Expected JSON format for flags: { "use-history": "boolean", ... }
        // Postconditions:
        // - Returns a `TaskResult` Pydantic model instance representing the outcome.
        // - The 'notes' field in the TaskResult is populated with execution details:
        //   - 'execution_path': "direct_tool" or "subtask_template".
        //   - 'context_source': "explicit_request", "none", or potentially values set by TaskSystem.
        //   - 'context_file_count'/'context_files_count': Number of files used from explicit 'file_context' param (for direct tools) or as reported by TaskSystem.
        // - Returns a FAILED TaskResult if the identifier is not found, input validation fails, or execution fails.
        // - If the executed task/template specifies JSON output and parsing succeeds, the parsed object is available in `TaskResult.parsedContent`.
        // Behavior:
        // - Checks if the `identifier` string starts with `'(`. If so, assumes it's an S-expression workflow:
        //   - Instantiates or accesses the S-expression evaluator component (`SexpEvaluator`).
        //   - Calls `await sexp_evaluator.evaluate_string(identifier, initial_environment)` where `identifier` contains the full S-expression string and `initial_environment` might contain bindings for `params`.
        //   - The S-expression string itself should follow the standard evaluation rules, including the use of `(quote ...)` to represent literal data arguments within the workflow.
        //   - Takes the raw result from `evaluate_string`. If it's not already a TaskResult dictionary, formats it into one (e.g., placing the result in `content`, setting `status` to `COMPLETE`). Handles potential exceptions from `evaluate_string` by creating a `FAILED` TaskResult.
        //   - Returns the formatted TaskResult.
        //   - Skips the subsequent template/tool lookup steps.
        // - If the identifier is *not* an S-expression, performs routing lookup with the following precedence:
        // - Parses 'file_context' parameter if present (handles list or JSON string array).
        // - Routing Precedence: Checks TaskSystem first for an **atomic** template using `task_system_instance.find_template(identifier)`.
        // - If not found as a template, checks Handler's unified tool registry using `handler_instance.tool_executors`.
        // - If template found: Creates a `SubtaskRequest` (ensuring inputs are values, not expressions) and calls `await task_system_instance.execute_atomic_template(request)`.
        // - If direct tool found: Calls the tool function directly with `params`. Wraps result in TaskResult if needed. Populates standard notes if the tool didn't.
        // - Checks the return value from the executed tool. If the result is a dictionary containing `status: "CONTINUATION"`, treats this as an error for a direct programmatic call and returns a FAILED TaskResult.
        // - If identifier not found: Returns a FAILED TaskResult.
        // - Handles TaskError exceptions from underlying calls and formats them into a FAILED TaskResult.
        // - Handles unexpected Python exceptions and formats them into a FAILED TaskResult with reason UNEXPECTED_ERROR.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Returned via FAILED TaskResult for invalid file_context JSON or missing identifier.")
        // @raises_error(condition="TASK_FAILURE", description="Returned via FAILED TaskResult if underlying TaskSystem or Direct Tool execution raises TaskError (e.g., SUBTASK_FAILURE).")
        // @raises_error(condition="UNEXPECTED_ERROR", description="Returned via FAILED TaskResult for unexpected Python exceptions during dispatch.")
        // Expected JSON format for return value: TaskResult Pydantic model instance.
        async object execute_programmatic_task(
            string identifier,
            dict<string, Any> params,
            dict<string, boolean> flags,
            object handler_instance, // Represents BaseHandler
            object task_system_instance, // Represents TaskSystem
            object memory_system, // Represents MemorySystem
            optional string optional_history_str
        );
    };
};
// == !! END IDL TEMPLATE !! ===
