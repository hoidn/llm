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
# Assume 'app' is an initialized Application instance from src.main

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

# Execute the entire workflow
# We can pass an initial_context if the first task needed dynamic inputs from it.
# For this example, initial_topic was handled by static_inputs.
workflow_results = workflow.run(initial_context={"user_topic": initial_topic})

# Access the final report
if workflow_results["report_step_output"].status == "COMPLETE":
    final_report = workflow_results["report_step_output"].content
    print("Generated Report:")
    print(final_report)
else:
    print("Workflow failed.")
    print("Details:", workflow_results["report_step_output"].notes.get("error"))

# Example of accessing intermediate results:
# summary_task_result = workflow_results["summary_step_output"]
# keywords_task_result = workflow_results["keywords_step_output"]
```
This example demonstrates how to chain tasks, map data using dot-notation paths into TaskResult objects, and access the final and intermediate results. Remember to consult the `src/orchestration/sequential_workflow_IDL.md` for full details on its API and behavior.
