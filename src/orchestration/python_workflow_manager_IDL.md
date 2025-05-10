// == !! BEGIN IDL TEMPLATE !! ===
module src.orchestration.python_workflow_manager {

    # @depends_on(src.main.Application) // For executing tasks via app.handle_task_command
    // OR # @depends_on(src.dispatcher.DispatcherFunctions) // Alt: For executing tasks via dispatcher.execute_programmatic_task
    # @depends_on_type(docs.system.contracts.types.TaskResult)
    # @depends_on_type(docs.system.contracts.types.WorkflowStepDefinition)

    // Interface for the Python Workflow Manager.
    // Allows defining and executing sequences of tasks programmatically in Python,
    // with support for passing outputs of one task as inputs to subsequent tasks.
    interface PythonWorkflowManager {

        // Constructor: Initializes the workflow manager.
        // Preconditions:
        // - app_or_dispatcher_instance is a valid Application instance or DispatcherFunctions instance.
        //   This dependency is used to execute individual tasks.
        // Postconditions:
        // - Workflow manager is initialized with an empty list of workflow steps.
        void __init__(object app_or_dispatcher_instance);

        // Adds a task step to the current workflow definition.
        // Preconditions:
        // - step_definition is a valid WorkflowStepDefinition object/dictionary.
        //   - `task_name` must correspond to a registered task/tool.
        //   - `output_name` must be unique within the workflow.
        //   - `dynamic_input_mappings` must refer to `output_name`s of previously added steps
        //     and valid field paths within their `TaskResult`s (e.g., "parsedContent.fieldName", "content", "notes.someKey").
        // Postconditions:
        // - The task step is appended to the internal workflow definition.
        // - Returns true on success, false if step_definition is invalid (e.g., duplicate output_name).
        // Behavior:
        // - Validates the step_definition (e.g., presence of required fields).
        // - Stores the step definition internally in an ordered list.
        // Expected JSON format for step_definition: WorkflowStepDefinition structure (from types.md)
        boolean add_step(object step_definition); // Arg is WorkflowStepDefinition

        // Clears all defined steps from the current workflow.
        // Preconditions: None.
        // Postconditions:
        // - The internal list of workflow steps is empty.
        void clear_workflow();

        // Executes the defined workflow.
        // Preconditions:
        // - At least one step must have been added via `add_step`.
        // - `initial_workflow_context` is an optional dictionary providing initial values
        //   that can be referenced by the `dynamic_input_mappings` of the first task(s).
        //   Keys in this dictionary can be thought of as outputs from a "step 0".
        // Postconditions:
        // - Returns a dictionary representing the final workflow context, containing the
        //   `TaskResult` of each executed step, keyed by their `output_name`.
        // - If any task fails and error handling doesn't allow continuation, the workflow
        //   stops, and the returned context will reflect the state up to the failure.
        //   The `TaskResult` for the failing step will be included.
        // Behavior:
        // - Initializes an internal `current_workflow_context` dictionary with `initial_workflow_context`.
        // - Iterates through the stored `WorkflowStepDefinition`s in order.
        // - For each step:
        //   1. Initializes `task_params` with `step.static_inputs` (if any).
        //   2. For each `target_param: "source_path"` in `step.dynamic_input_mappings`:
        //      a. Parses `source_path` into `source_step_output_name` and `field_path_parts` (e.g., ["parsedContent", "fieldName"]).
        //      b. Retrieves the `source_task_result: TaskResult` from `current_workflow_context` using `source_step_output_name`.
        //      c. If `source_task_result` is not found or is FAILED, handle error (e.g., raise WorkflowExecutionError or skip step).
        //      d. Traverses `source_task_result` using `field_path_parts` to extract the value.
        //         - This involves checking `parsedContent`, then `content` (parsing if JSON string), then `notes`.
        //      e. Assigns the extracted value to `task_params[target_param]`.
        //      f. Handles errors if path is invalid or value not found.
        //   3. Calls `self.app_or_dispatcher_instance.execute_programmatic_task(step.task_name, task_params, flags={})`
        //      (or `app.handle_task_command` equivalent).
        //   4. Stores the returned `TaskResult` into `current_workflow_context` using `step.output_name` as the key.
        //   5. If the `TaskResult.status` is "FAILED":
        //      - Logs the failure.
        //      - The workflow terminates. The returned `current_workflow_context` will include the FAILED TaskResult.
        // - Returns the final `current_workflow_context`.
        // @raises_error(condition="WorkflowExecutionError", description="If a dynamic input cannot be resolved, or an underlying task execution via app/dispatcher raises an unrecoverable error.")
        // @raises_error(condition="InvalidWorkflowDefinition", description="If the workflow is empty or a step definition is malformed.")
        // Expected JSON format for initial_workflow_context: { "key": "Any", ... }
        // Expected JSON format for return value: { "step1_output_name": TaskResult_dict, "step2_output_name": TaskResult_dict, ... }
        dict<string, Any> run(optional dict<string, Any> initial_workflow_context);

        // Invariants:
        // - `app_or_dispatcher_instance` is a valid callable instance.
        // - Internal list of steps only contains valid `WorkflowStepDefinition` objects.
    };
}
// == !! END IDL TEMPLATE !! ===
