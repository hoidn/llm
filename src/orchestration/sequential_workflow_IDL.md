// == !! BEGIN IDL TEMPLATE !! ===
module src.orchestration.sequential_workflow {

    # @depends_on(src.main.Application) // For executing tasks
    // OR # @depends_on(src.dispatcher.DispatcherFunctions) // Alternative dependency for task execution
    # @depends_on_type(docs.system.contracts.types.TaskResult) // For TaskResult type
    # @depends_on_type(docs.system.contracts.types.ContextManagement) // For context concepts
    # @depends_on_type(docs.system.contracts.types.HistoryConfigSettings) // For history concepts

    // Interface for a Python-fluent sequential workflow orchestrator.
    // Executes a sequence of pre-registered tasks, allowing outputs of one
    // task to be mapped as inputs to subsequent tasks.
    //
    // **Context and History Management:**
    // This workflow orchestrator executes tasks that may interact with a shared
    // `BaseHandler` instance (provided via `app_or_dispatcher_instance`). The
    // `BaseHandler` maintains its own `data_context` (for LLM prompt enrichment)
    // and `conversation_history`.
    //
    // - **Implicit Behavior:** The context and history behavior for any given
    //   LLM task step within this workflow is primarily determined by that
    //   task's own definition (e.g., its `ContextManagement` or
    //   `HistoryConfigSettings` in its template). `SequentialWorkflow` does not
    //   offer per-step overrides for these settings directly in its API.
    //
    // - **Explicit Management via System Tools:** To explicitly manage the
    //   `BaseHandler`'s `data_context` or `conversation_history` *between*
    //   steps in a `SequentialWorkflow`, users should include calls to
    //   dedicated system tools as steps within their workflow definition.
    //   Examples of such tools include:
    //     - `"system:clear_handler_data_context"`: Clears the BaseHandler's data context.
    //     - `"system:prime_handler_data_context"`: Primes the BaseHandler's data context
    //       (e.g., with a query or initial files). Its parameters (`query`, `initial_files`)
    //       can be supplied via `static_inputs` or `input_mappings`.
    //     - (If available) `"system:clear_handler_conversation_history"`: Clears the BaseHandler's
    //       conversation history.
    //
    //   By sequencing these system tools alongside other tasks, users can control
    //   the state of the `BaseHandler`'s context and history as the workflow progresses.
    //
    // - **No Workflow-Scoped Isolation:** `SequentialWorkflow` does not create its own
    //   isolated context/history scope that shadows or overrides the `BaseHandler`'s
    //   state for LLM tasks. All LLM tasks orchestrated will interact with the
    //   same underlying `BaseHandler` instance's state.
    //
    interface SequentialWorkflow {

        // Constructor: Initializes the workflow orchestrator.
        // Preconditions:
        // - app_or_dispatcher_instance is a valid Application or DispatcherFunctions instance,
        //   used for executing individual tasks.
        // Postconditions:
        // - Workflow is initialized with an empty sequence of tasks.
        void __init__(object app_or_dispatcher_instance);

        // Adds a task to the execution sequence.
        // Preconditions:
        // - task_name is the identifier of a pre-registered task or direct tool,
        //   resolvable by the Application or Dispatcher.
        // - output_name is a unique string key used to store this task's TaskResult
        //   in the workflow context and for subsequent tasks to reference its output.
        // - static_inputs (optional) is a dictionary of literal values for the task's parameters.
        // - input_mappings (optional) is a dictionary where:
        //   - Keys: Target parameter names for the current task.
        //   - Values: Strings like "source_output_name.path.to.value" or "initial.path.to.value".
        //     - "source_output_name" refers to an 'output_name' of a previously added task.
        //     - "initial" refers to keys in the 'initial_context' passed to 'run()'.
        //       (To access, use a convention like "_initial_.your_key" in the path string,
        //        assuming initial_context is stored under a special key like "_initial_"
        //        within the internal workflow_results_context).
        //     - "path.to.value" is a dot-separated path to extract from the source TaskResult
        //       (e.g., "parsedContent.field", "content", "notes.some_key"). Path traversal
        //       should handle attribute access for objects and key access for dictionaries.
        //       If a path segment is None or a key/attribute is missing during resolution,
        //       it should result in a WorkflowExecutionError.
        // - If a parameter name exists in both static_inputs and input_mappings, input_mappings takes precedence.
        // Postconditions:
        // - The task call definition is added to the internal sequence.
        // - Returns self to allow for fluent chaining (e.g., workflow.add_task(...).add_task(...)).
        // Behavior:
        // - Stores the task call configuration (name, output_name, static_inputs, input_mappings) internally.
        // - Validates that output_name is unique within the current workflow definition.
        // @raises_error(condition="DuplicateOutputNameError", description="If output_name is not unique.")
        object add_task( // Returns Self for chaining
            string task_name,
            string output_name,
            optional dict<string, Any> static_inputs,
            optional dict<string, string> input_mappings
        );

        // Executes the defined sequence of tasks.
        // Preconditions:
        // - At least one task must have been added via `add_task`.
        // - initial_context (optional) is a dictionary providing initial values. Keys in this
        //   dictionary can be referenced by input_mappings using a convention like "_initial_.key_name".
        // Postconditions:
        // - Returns a dictionary (the workflow context) where keys are the 'output_name's
        //   provided in `add_task`, and values are the corresponding `TaskResult` objects.
        // - If any task fails (returns a FAILED TaskResult or input mapping fails):
        //   - The workflow stops execution at that point by raising a WorkflowExecutionError.
        //   - The exception should contain details about the failing step and reason.
        // Behavior:
        // - Initializes an internal `workflow_results_context` dictionary. The `initial_context`
        //   is made available, for example, by storing it under a special key like `workflow_results_context["_initial_"] = initial_context`.
        // - Iterates through the stored task call configurations in order.
        // - For each task:
        //   1. Prepare `current_task_params`:
        //      a. Start with `static_inputs`.
        //      b. For each `target_param: "source_path_string"` in `input_mappings`:
        //         i. Resolve `source_path_string` (e.g., "step_A_output.parsedContent.data" or "_initial_.user_data").
        //         ii. Extract the `source_name` (e.g., "step_A_output" or "_initial_") and the `value_path` (e.g., "parsedContent.data").
        //         iii. Retrieve the source `TaskResult` (or initial data dictionary) from `workflow_results_context` using `source_name`.
        //         iv. If source not found, or if it's a FAILED TaskResult and its output is being accessed in a way that's problematic, raise WorkflowExecutionError.
        //         v. Use an internal helper to safely extract the value from the source object/dictionary using `value_path`. This helper must handle attribute access for objects (like TaskResult properties) and key access for dictionaries (like TaskResult.notes or TaskResult.parsedContent if it's a dict). If path is invalid or value not found, raise WorkflowExecutionError.
        //         vi. Assign the extracted value to `current_task_params[target_param]`.
        //   2. Call `self.app_or_dispatcher_instance.execute_programmatic_task(task_name, current_task_params, flags={})`.
        //      This can invoke any registered atomic LLM task or direct tool.
        //   3. Store the returned `TaskResult` into `workflow_results_context[output_name]`.
        //   4. If `TaskResult.status` is "FAILED", raise `WorkflowExecutionError` detailing the failing step and the FAILED TaskResult.
        // - Returns the final `workflow_results_context` if all steps complete successfully.
        // @raises_error(condition="WorkflowExecutionError", description="If a dynamic input cannot be resolved (e.g., invalid path, source step failed and output is unusable, underlying task execution error), or if a task returns a FAILED status.")
        // @raises_error(condition="InvalidWorkflowDefinition", description="If the workflow is empty when `run()` is called.")
        // Expected JSON format for initial_context: { "key": "Any", ... }
        // Expected JSON format for return value (on success): { "step1_output_name": TaskResult_dict, "step2_output_name": TaskResult_dict, ... }
        dict<string, Any> run(optional dict<string, Any> initial_context);

        // Clears all defined tasks from the current workflow.
        // Preconditions: None.
        // Postconditions:
        // - The internal sequence of tasks is empty.
        void clear();
    };

---

## Sequence Diagram: `run()` Method

```mermaid
sequenceDiagram
    participant C as Calling Code
    participant SW as SequentialWorkflow
    participant AD as App/Dispatcher
    participant WRC as workflow_results_context (internal to SW)

    C->>SW: run(initial_context)
    SW->>WRC: Initialize (e.g., WRC["_initial_"] = initial_context)
    
    loop For each task_config in sequence
        Note over SW: Resolve inputs for current task:\n1. static_inputs\n2. input_mappings (from WRC, incl. WRC["_initial_"])
        alt Input Resolution Fails or Source Task FAILED
            SW-->>C: raise WorkflowExecutionError
            break
        end
        SW->>AD: execute_programmatic_task(task_name, resolved_params)
        AD-->>SW: task_result: TaskResult
        SW->>WRC: Store task_result (by output_name)
        alt task_result.status == "FAILED"
            SW-->>C: raise WorkflowExecutionError (with details)
            break
        end
    end
    
    SW-->>C: Return final WRC (if all successful)
```
}
// == !! END IDL TEMPLATE !! ===
