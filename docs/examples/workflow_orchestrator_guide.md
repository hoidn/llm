# Guide: Aider Test-Fix Loop Orchestrator Script

**Location:** `scripts/run_aider_loop.py` (Assumed script name)

## 1. Purpose

This Python script orchestrates the "Aider Test-Fix Loop" workflow described in [`docs/features/aider_test_fix_loop.md`](../features/aider_test_fix_loop.md). It manages the interaction between the user, the planning LLM ("Model A"), the Aider MCP Server, and the test execution environment to automate a cycle of code generation, testing, and fixing.

## 2. Workflow Overview

The script performs the following high-level steps:

1.  **Initialization:** Parses command-line arguments, sets up logging, and instantiates the main `Application` class (potentially selecting "Model A" based on arguments).
2.  **Initial Context Loading:** Reads a user-provided file containing the initial code/IDL/context and sends it to "Model A" via `Application.handle_query` to establish the session context.
3.  **Planning:** Prompts "Model A" (via `handle_query`) to generate a development plan, requesting the output as structured JSON containing `instructions`, `files`, and `test_command`.
4.  **S-Expression Construction:** Builds the main S-expression string using the new `(loop <max_retries> ...)` primitive. The loop body will contain calls to `aider:automatic`. Data like the test command or Aider model override might be embedded or passed via the initial environment.
5.  **DSL Loop Execution:** Calls `Application.handle_task_command` *once* to execute the S-expression loop. The loop internally handles the fixed iterations of Aider calls.
6.  **Test Execution:** After the DSL loop finishes (Aider attempts complete), the orchestrator extracts the `test_command` from the initial plan (Step 3). It calls `Application.handle_task_command` for `system:execute_shell_command` to run the tests *once*. Stops if this call fails. Extracts `stdout`/`stderr`.
7.  **Final Analysis:** Sends the test command output back to "Model A" via `Application.handle_query`, asking it to analyze the final results and determine overall success/failure. Stops if this call fails.
8.  **Reporting:** Reports the final outcome (Success/Failure based on Model A's final analysis or an earlier error).

*Note: This script implements the "Simplified Workflow" where the DSL loop runs for a fixed number of Aider attempts, and final test verification is done once after the loop, followed by Model A analysis.*

## 3. Prerequisites

*   **Python Environment:** A Python environment with all project dependencies installed (see `pyproject.toml` or `requirements.txt`).
*   **Aider MCP Server:** A compatible Aider MCP Server must be running and accessible.
*   **MCP Configuration:** A `.mcp.json` file must exist in the project root, correctly configured to connect to the Aider MCP Server via STDIO transport (containing `command`, `args`, `env` for the `aider-mcp-server` key). See `docs/librarydocs/mcp_client_developer_guide.md`.
*   **Environment Variables:**
    *   `AIDER_ENABLED=true`: Must be set for the `Application` to initialize Aider integration.
    *   API keys for the desired LLM provider ("Model A") must be set (e.g., `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).
*   **Initial Context File:** The user must prepare a text file containing all necessary context (code snippets, IDLs, requirements) for the initial prompt to Model A.
*   **Target Repository:** The script needs access to the target Git repository specified via the `--repo-path` argument.

## 4. Configuration & Usage

The script is configured and run via command-line arguments:

```bash
# Example usage
python scripts/run_aider_loop.py \
    --context-file /path/to/your/initial_context.txt \
    --prompt "Implement the feature described in the context and ensure tests pass." \
    --repo-path /path/to/your/target/git/repository \
    [--model-a "anthropic:claude-3-opus-20240229"] \
    [--aider-model "openai:gpt-4o"] \
    [--max-retries 3]
```

**Command-Line Arguments:**

*   `--context-file` (Required): Path to the initial context file provided to Model A.
*   `--prompt` (Required): The high-level task prompt given to Model A after the initial context.
*   `--repo-path` (Required): Path to the root of the target Git repository where Aider will operate and tests will run.
*   `--model-a` (Optional): The model identifier string (e.g., "anthropic:...") for the planning/analysis LLM ("Model A"). If omitted, uses the default configured in the `Application`.
*   `--aider-model` (Optional): The model identifier string (e.g., "openai:...") to be used specifically by Aider via its MCP tool parameter within the S-expression loop. If omitted, the Aider MCP server's default is used.
*   `--max-retries` (Optional): Maximum number of Aider attempts (iterations of the DSL loop) before running the final tests. Defaults to 3.

## 5. Expected Behavior & Output

*   The script will log its progress to the console (INFO level by default).
*   It will print status updates indicating which step it's performing (Loading Context, Planning, Executing S-expression Loop, Running Tests, Final Analysis).
*   The final output will indicate overall SUCCESS or FAILURE based on Model A's final analysis or an error during orchestration.
*   If successful, the target repository should contain the code changes made by Aider.

## 6. Code Structure & Comments

The script (`scripts/run_aider_loop.py`) should contain detailed comments explaining:

*   Argument parsing logic.
*   Initialization of the `Application` (including potential Model A selection).
*   Construction of prompts for Model A (initial planning, final analysis).
*   Parsing of the structured JSON plan from Model A.
*   Construction of the main S-expression string including the `(loop ...)` form.
*   Population of the initial `SexpEnvironment`.
*   Invocation of `Application.handle_task_command` for the S-expression loop.
*   Invocation of `Application.handle_task_command` for the test execution command.
*   Error handling logic for each orchestration step.
