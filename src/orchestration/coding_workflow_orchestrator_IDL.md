// == !! BEGIN IDL TEMPLATE !! ===
module src.orchestration.coding_workflow_orchestrator {

    # @depends_on(src.main.Application) // Primary dependency
    # @depends_on_type(src.system.models.DevelopmentPlan) // Uses this type for internal state
    # @depends_on_type(src.system.models.CombinedAnalysisResult) // Uses this type for decision making
    # @depends_on_type(src.system.models.TaskResult) // For interacting with app and phase methods

    interface CodingWorkflowOrchestrator {

        // Constructor: Initializes the workflow orchestrator.
        // Preconditions:
        // - app is a valid Application instance.
        // - initial_goal, initial_context, test_command are non-empty strings.
        // - max_retries is a non-negative integer.
        // Postconditions:
        // - Orchestrator is initialized and ready to run the workflow.
        void __init__(
            object app, // Represents Application instance
            string initial_goal,
            string initial_context,
            string test_command,
            optional int max_retries // Defaults to a value like 3
        );

        // Executes the entire iterative coding workflow.
        // Preconditions:
        // - Orchestrator has been initialized.
        // - Necessary atomic tasks (e.g., "user:generate-plan-from-goal", "user:analyze-aider-result", "user:evaluate-and-retry-analysis")
        //   and direct tools (e.g., "aider:automatic", "system:execute_shell_command") are expected to be
        //   registered with the Application instance.
        // Postconditions:
        // - Returns a dictionary representing the final outcome of the workflow.
        //   This will typically be a TaskResult-like structure indicating overall success or failure,
        //   and may contain the final Aider output or analysis details.
        // Behavior:
        // - Manages the iterative loop:
        //   1. Calls an internal method `_generate_plan` (which uses `app.handle_task_command` for "user:generate-plan-from-goal").
        //   2. In a loop (up to `max_retries`):
        //      a. Calls `_execute_code` (uses `app.handle_task_command` for an Aider task like "aider:automatic").
        //      b. Calls `_validate_code` (uses `app.handle_task_command` for "system:execute_shell_command").
        //      c. Calls `_analyze_iteration` (uses `app.handle_task_command` for "user:evaluate-and-retry-analysis").
        //      d. Based on analysis, either stops (SUCCESS/FAILURE) or updates the plan and continues (RETRY).
        // - Returns the final result dictionary.
        // @raises_error(None) // Errors are typically handled internally and reflected in the returned dictionary's status/error fields.
        // Expected JSON format for return value: TaskResult-like structure, e.g.,
        // { "status": "COMPLETE" | "FAILED", "content": "string", "reason?": "string", "details?": object, "final_aider_result?": object, "analysis_result?": object }
        dict<string, Any> run();
    }
}
// == !! END IDL TEMPLATE !! ===
