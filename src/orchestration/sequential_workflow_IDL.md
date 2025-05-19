// == !! BEGIN IDL TEMPLATE !! ===
module src.orchestration.sequential_workflow {

    # @depends_on(src.main.Application) // For executing tasks
    // OR # @depends_on(src.dispatcher.DispatcherFunctions) // Alternative dependency for task execution
    # @depends_on_type(docs.system.contracts.types.TaskResult) // For TaskResult type
    # @depends_on_type(docs.system.contracts.types.ContextManagement) // For context concepts
    # @depends_on_type(docs.system.contracts.types.HistoryConfigSettings) // For history concepts
    # @depends_on_type(src.system.models.WorkflowOutcome) // For WorkflowOutcome type

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
        //   - Values: Dot-separated strings like "source_output_name.path.to.value"
        //     OR a list of strings representing path segments, e.g.,
        //     ["source_output_name", "parsedContent", "key.with.dots"].
        //     The list format is for keys/attributes containing special characters in their names.
        //     - "source_output_name" refers to an 'output_name' of a previously added task.
        //     - "initial" refers to keys in the 'initial_context' passed to 'run()'.
        //       (To access, use a convention like "_initial_.your_key" in the path string/list,
        //        assuming initial_context is stored under a special key like "_initial_"
        //        within the internal workflow_results_context).
        //     - "path.to.value" (or subsequent list elements) is a path to extract from the source TaskResult.
        //       Path traversal should handle attribute access for objects and key access for dictionaries.
        //       If a path segment is None or a key/attribute is missing during resolution,
        //       it should result in a WorkflowExecutionError during the `run` phase.
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
            optional dict<string, union<string, list<string>>> input_mappings // Updated type
        );

            // Executes the defined sequence of tasks asynchronously.
            // Preconditions:
            // - At least one task must have been added via `add_task`.
            // - initial_context (optional) is a dictionary providing initial values. Keys in this
            //   dictionary can be referenced by input_mappings using a convention like "_initial_.key_name".
            // Postconditions:
            // - Returns a WorkflowOutcome object indicating overall success or failure.
            // - If successful (WorkflowOutcome.success == true), WorkflowOutcome.results_context
            //   contains a dictionary where keys are 'output_name's and values are the
            //   corresponding TaskResult objects for all executed steps.
            // - If failed (WorkflowOutcome.success == false), WorkflowOutcome contains
            //   error_message, failing_step_name, and potentially further details.
            // Behavior:
            // - Performs cycle detection on the defined task sequence based on input_mappings.
            //   Raises InvalidWorkflowDefinition if a cycle exists.
            // - Checks if the task sequence is empty. Raises InvalidWorkflowDefinition if it is.
            // - Initializes an internal `workflow_results_context` dictionary. A deep copy of
            //   `initial_context` is made available (e.g., via `workflow_results_context["_initial_"]`).
            // - Iterates through the stored task call configurations in order:
            //   1. Prepare `current_task_params` (as previously defined, handling ValueResolutionError internally).
            //      If input resolution fails for a step, the workflow terminates, returning a
            //      WorkflowOutcome with success=false and error details.
            //   2. Asynchronously calls `self.app_or_dispatcher_instance.execute_programmatic_task(...)`.
            //      If this call raises an unhandled exception, the workflow terminates, returning
            //      a WorkflowOutcome with success=false and error details.
            //   3. Stores the returned `TaskResult` into `workflow_results_context[output_name]`.
            //   4. If `TaskResult.status` is "FAILED", the workflow terminates, returning a
            //      WorkflowOutcome with success=false, the failing_step_name, and the FAILED TaskResult in details.
            // - If all steps complete successfully, returns a WorkflowOutcome with success=true
            //   and the populated `results_context`.
            // @raises_error(condition="InvalidWorkflowDefinition", description="If the workflow is empty or contains cyclic dependencies.")
            // Note: Most operational failures during execution (e.g., step failure, input resolution error)
            //       are reported via the returned WorkflowOutcome object (success=false), not by raising
            //       WorkflowExecutionError directly from this method for those cases.
            //       WorkflowExecutionError might still be raised for unexpected internal errors.
            // Expected JSON format for return value (WorkflowOutcome object):
            // {
            //   "success": boolean,
            //   "results_context": { "step1_output_name": /* TaskResult_object */, ... },
            //   "error_message"?: string,
            //   "failing_step_name"?: string,
            //   "details"?: { "failed_task_result"?: /* TaskResult_object */, "resolution_error"?: string, ... }
            // }
            async object run(optional dict<string, Any> initial_context); // Returns WorkflowOutcome

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

    C->>+SW: await run(initial_context)
    SW->>SW: Detect Cycles in Task Sequence
    alt Cycle Detected or Empty Workflow
        SW-->>-C: raise InvalidWorkflowDefinition
    end
    SW->>WRC: Initialize with deepcopy(initial_context) (e.g., WRC["_initial_"] = ...)
    
    loop For each task_config in sequence
        Note over SW: Resolve inputs for current task (static + dynamic from WRC)
        alt Input Resolution Fails
            SW-->>-C: return WorkflowOutcome(success=false, error_message="Input resolution failed for step X", failing_step_name="X")
            break
        end
        SW->>+AD: await execute_programmatic_task(task_name, resolved_params)
        AD-->>-SW: task_result: TaskResult
        SW->>WRC: Store task_result (by output_name)
        alt task_result.status == "FAILED"
            SW-->>-C: return WorkflowOutcome(success=false, error_message="Step X failed", failing_step_name="X", details={"failed_task_result": task_result})
            break
        end
        alt execute_programmatic_task raises Exception
            SW-->>-C: return WorkflowOutcome(success=false, error_message="Dispatcher error for step X", failing_step_name="X", details={"exception": ...})
            break
        end
    end
    
    alt All steps successful
        SW-->>-C: return WorkflowOutcome(success=True, results_context=WRC)
    end
```
}
// == !! END IDL TEMPLATE !! ===
