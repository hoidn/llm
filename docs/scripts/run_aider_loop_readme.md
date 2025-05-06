# Aider Test-Fix Loop Orchestrator Script (`scripts/run_aider_loop.py`)

This script automates a test-fix development loop using an AI model (Model A) for planning/analysis and Aider (via MCP) for code implementation.

## Workflow (Option A: Python Orchestration)

1.  **Prerequisites:** Checks for a valid Git repository, context file, and Aider MCP configuration (`.mcp.json`). Sets `AIDER_ENABLED=true`.
2.  **Initialization:** Instantiates the main `Application` class, configuring the Model A identifier and setting the file manager base path to the target repository.
3.  **Load Context:** Reads initial context from the specified file.
4.  **Load Prompts:** Reads the user's task prompt(s) from the command line or a file.
5.  **Generate Plan:** Calls the `user:generate-plan` atomic task (using Model A) with the prompts and context to get a structured `DevelopmentPlan` (instructions, files, test command).
6.  **Aider Loop:**
    a.  Calls the `aider:automatic` tool with the current plan instructions and target files.
    b.  Calls the `user:analyze-aider-result` atomic task (using Model A) to evaluate the Aider iteration's outcome.
    c.  Processes the `FeedbackResult`:
        *   **SUCCESS:** Breaks the loop.
        *   **REVISE:** Updates the instructions for Aider and continues the loop (up to `max_retries`).
        *   **ABORT:** Breaks the loop and marks as aborted.
7.  **Run Tests:** If the loop didn't abort, executes the `test_command` from the plan using the `system:execute_shell_command` tool within the target repository.
8.  **Final Analysis:** If the loop didn't abort, performs a final query to Model A, providing the loop outcome and test results, asking for an overall success/failure verdict.
9.  **Report Outcome:** Prints the overall status (SUCCESS/FAILURE) and the final message/analysis. Exits with status code 0 for SUCCESS, 1 for FAILURE.

## Usage

```bash
# Ensure you are in the project root directory
# Make sure your virtual environment is activated

python scripts/run_aider_loop.py <repo_path> <context_file> [options]

# Example: Using command-line prompts
python scripts/run_aider_loop.py \
    /path/to/your/git/repo \
    docs/context_for_task.txt \
    -p "Refactor the main function in main.py to improve readability." "Add unit tests for the refactored function." \
    --model-a "anthropic:claude-3-5-sonnet-latest" \
    --aider-model "openai:gpt-4o" \
    --max-retries 5 \
    --log-level DEBUG

# Example: Using a prompt file
# prompts.txt contains:
# <prompt>Prompt 1 content...</prompt>
# <prompt>Prompt 2 content...</prompt>
python scripts/run_aider_loop.py \
    /path/to/your/git/repo \
    docs/context_for_task.txt \
    -f prompts.txt \
    --max-retries 3
```

### Arguments

*   `repo_path`: (Required) Path to the target Git repository.
*   `context_file`: (Required) Path to the file containing initial context for Model A.
*   `-p`, `--prompt`: (Required, unless `-f` used) One or more user prompts for the task.
*   `-f`, `--prompt-file`: (Required, unless `-p` used) Path to a file containing prompts within `<prompt>...</prompt>` tags.
*   `--model-a`: (Optional) Override the default LLM identifier used for planning and analysis (Model A). Defaults to the Application's configured default.
*   `--aider-model`: (Optional) Override the LLM identifier passed to the Aider tool.
*   `--max-retries`: (Optional) Maximum number of Aider execution attempts in the loop (default: 3).
*   `--log-level`: (Optional) Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: INFO.

### Prerequisites

*   The target `repo_path` must be a valid Git repository.
*   The `context_file` must exist.
*   Aider MCP Server must be configured in `.mcp.json` in the project root (see `docs/librarydocs/aider_MCP_server.md`).
*   Required Python dependencies must be installed (`pip install -r requirements.txt` or `uv sync`).
*   Environment variables for LLM API keys (e.g., `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) must be set as required by the chosen models and `pydantic-ai`.
