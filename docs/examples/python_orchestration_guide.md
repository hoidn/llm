## Using `SequentialWorkflow` for Python-Fluent Orchestration

The `SequentialWorkflow` component allows you to define and execute a sequence of tasks directly in Python, managing the flow of data between them. This is useful for linear workflows where you prefer a Pythonic API over S-expressions.

### Key Concepts:

*   **Task Execution:** It relies on the project's `Application` or `Dispatcher` to execute pre-registered tasks (both LLM tasks and direct tools).
*   **Data Flow:** Outputs from one task (specifically, its `TaskResult`) can be mapped to the inputs of subsequent tasks using string-based path selectors (e.g., `"previous_step_output.parsedContent.data_field"`).
*   **Context Management:** For LLM tasks that interact with the `BaseHandler`'s data context or conversation history, `SequentialWorkflow` itself does not provide per-step overrides. Instead, you should include calls to system tools like `"system:clear_handler_data_context"` or `"system:prime_handler_data_context"` as explicit steps within your workflow to manage the handler's state.

### Example: Multi-Step Analysis

Let's say we have three registered tasks:
1.  `"user:generate_initial_summary"`: Takes a `topic` string, returns a summary in `TaskResult.content`.
2.  `"user:extract_keywords"`: Takes `text_to_analyze` string, returns keywords in `TaskResult.parsedContent.keywords` (a list).
3.  `"system:format_report"`: Takes `summary_text` and `keyword_list`, returns a formatted string.

Here's how you could orchestrate them:

```python
from src.orchestration.sequential_workflow import SequentialWorkflow
# Assuming 'app' is an initialized Application instance from src.main
# from src.system.models import WorkflowOutcome # Import WorkflowOutcome
# import asyncio # Import asyncio for running the async main function

# This example is now structured within an async function
async def main_workflow_example():
    # Assuming 'app' is an initialized Application instance available in this scope
    # If 'app' is not globally available, you might pass it as an argument to main_workflow_example

    # Initialize the workflow orchestrator
    workflow = SequentialWorkflow(app_instance=app)

    # Define the initial topic for the workflow
    initial_topic = "The future of renewable energy."

    # Step 1: Generate an initial summary
    workflow.add_task(
        task_name="user:generate_initial_summary",
        output_name="summary_step_output",
        static_inputs={"topic": initial_topic} # Provide static input
    )

    # Step 2: Extract keywords from the summary generated in Step 1
    workflow.add_task(
        task_name="user:extract_keywords",
        output_name="keywords_step_output",
        input_mappings={
            # Map the 'content' of 'summary_step_output' TaskResult
            # to the 'text_to_analyze' parameter of 'user:extract_keywords'
            "text_to_analyze": "summary_step_output.content"
        }
    )

    # Step 3: Format a report using the summary and keywords
    workflow.add_task(
        task_name="system:format_report",
        output_name="report_step_output",
        input_mappings={
            "summary_text": "summary_step_output.content",
            "keyword_list": "keywords_step_output.parsedContent.keywords"
        }
    )

    # Execute the entire workflow (now async)
    print("Running workflow...")
    # outcome: WorkflowOutcome = await workflow.run(initial_context={"user_topic": initial_topic})
    # For type hinting, ensure WorkflowOutcome is imported, e.g.:
    # from src.system.models import WorkflowOutcome
    outcome = await workflow.run(initial_context={"user_topic": initial_topic})


    if outcome.success:
        print("Workflow completed successfully!")
        final_report_task_result = outcome.results_context.get("report_step_output")
        if final_report_task_result and final_report_task_result.status == "COMPLETE":
            print("Generated Report:")
            print(final_report_task_result.content)
        else:
            print("Report generation step might have had an issue or was not found in results_context.")
        
        # Example of accessing intermediate results:
        # summary_task_result = outcome.results_context.get("summary_step_output")
        # if summary_task_result:
        #    print(f"\nIntermediate summary: {summary_task_result.content[:100]}...")
    else:
        print("Workflow failed.")
        print(f"  Failing Step: {outcome.failing_step_name}")
        print(f"  Error Message: {outcome.error_message}")
        if outcome.details:
            print(f"  Details: {outcome.details}")

# To run this example:
# if __name__ == "__main__":
#    # You would need to set up 'app' (the Application instance) first.
#    # For example:
#    # from src.main import Application
#    # app = Application() # Or however your app is initialized
#    # app.initialize_components() # If needed
#
#    # Then run the async function:
#    # asyncio.run(main_workflow_example())
```
This example demonstrates how to chain tasks, map data using dot-notation paths into TaskResult objects, and access the final and intermediate results. The `run()` method is now asynchronous and returns a `WorkflowOutcome` object. This object contains a `success` flag, the `results_context` (a dictionary of `TaskResult` objects from each step if successful), and error details if it failed.

Remember to consult the `src/orchestration/sequential_workflow_IDL.md` for full details on its API and behavior.

### WorkflowOutcome Structure

The `WorkflowOutcome` object returned by `workflow.run()` has roughly the following structure (defined in `src/system/models.py`):

```python
class WorkflowOutcome(BaseModel):
    success: bool
    results_context: Dict[str, TaskResult] # Dictionary of TaskResult objects
    error_message: Optional[str] = None
    failing_step_name: Optional[str] = None
    details: Optional[Dict[str, Any]] = None # e.g., failed TaskResult, resolution error
```

### Troubleshooting

*   **Symptom:** Workflow stops, `run()` call doesn't raise an exception directly but returns an object.
    *   **Likely Cause:** A task within the workflow failed, or input mapping failed.
    *   **Fix/Check:** Inspect the returned `WorkflowOutcome` object. Check `outcome.success` (will be `False`), `outcome.failing_step_name`, `outcome.error_message`, and `outcome.details` for information about the failure.
