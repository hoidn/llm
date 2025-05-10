#!/usr/bin/env python
"""
Script to run a coding workflow using the Python-based CodingWorkflowOrchestrator.

This script orchestrates a series of tasks including:
1. Generating a development plan using an LLM.
2. Executing coding tasks using Aider (via aider:automatic tool).
3. Running user-provided test commands to verify the code.
4. Analyzing Aider and test results using an LLM to decide on next steps (revise or stop).

Usage Examples:

1. Simple file creation:
   python src/scripts/run_coding_workflow.py \
     --goal "Create a file named output.txt with the content 'Hello Workflow!'" \
     --test-command "cat output.txt | grep 'Hello Workflow!'"

2. Python function definition with context and pytest:
   # First, create context.txt: echo "Base path is /app/src" > context.txt
   python src/scripts/run_coding_workflow.py \
     --goal "Define a python function 'greet(name)' in utils.py that returns 'Hello, {name}!'" \
     --context-file context.txt \
     --test-command "pytest tests/test_utils.py" # Ensure test_utils.py exists and is runnable

3. Debug mode:
   python src/scripts/run_coding_workflow.py --debug \
     --goal "Your goal here" \
     --test-command "Your test command here"
"""

import argparse
import json
import logging
import os
import sys
import pathlib

# --- Path Setup ---
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# --- Application Imports ---
from src.main import Application
from src.orchestration.coding_workflow_orchestrator import CodingWorkflowOrchestrator # Import the orchestrator

# --- Logging Setup ---
LOG_LEVEL = logging.INFO
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger().setLevel(LOG_LEVEL) # Ensure root logger level is set
logger = logging.getLogger("RunCodingWorkflowScript")


# S-expression to define the planning task (outputs instructions/files ONLY)
# This task is used by the CodingWorkflowOrchestrator's _generate_plan method.
DEFATOM_GENERATE_PLAN_S_EXPRESSION = """
(defatom user:generate-plan-from-goal
  (instructions
    "Analyze the user's goal: '{{goal}}' with the provided context: '{{context_string}}'.
    Your *only* task is to generate a development plan. Do *not* attempt to execute any tools or commands yourself.
    The plan must include ONLY:
    1. 'instructions': Detailed steps for an AI coder (Aider), derived from the user's goal.
    2. 'files': A list of ALL file paths that need to be created or modified to implement the plan. **Carefully review the '{{goal}}' for any explicitly mentioned file paths (e.g., under sections like 'File to Modify' or paths mentioned in test names like 'tests/some_module/test_file.py') and ensure these are accurately extracted and included in this 'files' list.** This list should include both source code modules and their associated test files if they are mentioned or clearly implied as needing changes by the goal.
    Do NOT generate a 'test_command'.
    Output ONLY a single JSON object conforming to the DevelopmentPlan schema (which has 'instructions' and 'files' as required, 'test_command' is optional). No other text."
  )
  (params (goal string) (context_string string))
  (output_format ((type "json") (schema "src.system.models.DevelopmentPlan")))
  (description "Generates DevelopmentPlan JSON (instructions/files only) from goal/context.")
  (model "google-gla:gemini-2.5-pro-exp-03-25") 
  (history_config (quote ((use_session_history false) (record_in_session_history true) (history_turns_to_include nil))))
)
"""

# S-expression to define the combined analysis task
# This task is used by the CodingWorkflowOrchestrator's _analyze_iteration method.
DEFATOM_COMBINED_ANALYSIS_S_EXPRESSION = """
(defatom user:evaluate-and-retry-analysis
  (instructions
    "You are an AI evaluator reviewing a coding task iteration ({{iteration}}/{{max_retries}}).
    Original User Goal: {{original_goal}}
    Original Task Context File Content:
    {{initial_task_context}}

    Aider Prompt This Iteration: {{aider_instructions}}
    Aider Task Status: {{aider_status}}
    Aider Output/Diff/Error:
    {{aider_diff}}

    Test Command Run: {{test_command}}
    Test Stdout:
    {{test_stdout}}
    Test Stderr:
    {{test_stderr}}
    Test Exit Code: {{test_exit_code}}
    Files In Play (from previous plan): {{previous_files}}

    Analyze the test output (stdout/stderr) to determine if tests passed.
    - If tests passed (e.g., pytest shows PASSED, no errors in stderr, exit_code 0), verdict is 'SUCCESS'.
    - If tests failed:
        - Check if iteration < max_retries.
        - If yes, analyze the failure (test output, Aider diff) and generate a *revised* 'next_prompt' AND 'next_files' list for Aider to fix the issues. Verdict is 'RETRY'. The 'next_files' list should include all relevant files for the fix.
        - If no (max retries reached or failure seems unfixable), verdict is 'FAILURE'.
    - If the Aider task itself reported failure, continue to retry unless the failure looks critical (provide 'next_prompt', 'next_files', and verdict 'RETRY').

    Provide a concise explanation in 'message'.
    Output ONLY JSON conforming to the CombinedAnalysisResult schema.
    Ensure 'next_prompt' AND 'next_files' are provided *only* if verdict is 'RETRY'.
    **IMPORTANT:** Your entire response MUST be the JSON object itself, starting with `{` and ending with `}`."
  )
  (params
    (original_goal string)
    (initial_task_context string)
    (aider_instructions string) 
    (aider_status string) 
    (aider_diff string) 
    (test_command string)
    (test_stdout string)
    (test_stderr string)
    (test_exit_code integer)
    (previous_files list) 
    (iteration integer)
    (max_retries integer)
  )
  (output_format ((type "json") (schema "src.system.models.CombinedAnalysisResult")))
  (description "Analyzes Aider and test results, determines success/failure/retry, and provides the next prompt and files if needed.")
  (model "google-gla:gemini-2.5-pro-exp-03-25")
  (history_config (quote ((use_session_history false) (record_in_session_history true) (history_turns_to_include nil))))
)
"""

def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Run a coding workflow using Python orchestration.")
    parser.add_argument("--goal", required=True, help="The user's coding goal.")
    parser.add_argument("--context-file", help="Optional path to a file containing initial context.")
    parser.add_argument("--test-command", default="pytest tests/", help="The shell command to run for verification.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3, 
        help="Maximum number of retry iterations for the coding loop."
    )
    # Only parse known args to avoid errors when running in test environments
    args, _ = parser.parse_known_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers: # Ensure handlers also respect the level
            handler.setLevel(logging.INFO)
        logger.info("Debug logging enabled.")
        os.environ['DEBUG_LLM_FLOW'] = 'true' # For LLMInteractionManager logging

    initial_user_goal = args.goal
    initial_context_data = "Operating in the current project workspace." # Default context
    if args.context_file:
        try:
            context_file_path = pathlib.Path(args.context_file).resolve()
            logger.info(f"Reading context file: {context_file_path}")
            if context_file_path.is_file():
                with open(context_file_path, 'r', encoding='utf-8') as f:
                    initial_context_data = f.read()
                logger.debug("Context file read successfully.")
            else:
                logger.warning(f"Context file not found: {context_file_path}. Using default context.")
        except Exception as e:
            logger.warning(f"Could not read context file {args.context_file}: {e}. Using default context.")

    user_test_command = args.test_command
    logger.info(f"Using Goal: {initial_user_goal}")
    logger.info(f"Using Context Data (length): {len(initial_context_data)}")
    logger.info(f"Using Test Command: {user_test_command}")
    logger.info(f"Using Max Retries: {args.max_retries}")

    # --- Instantiate Application ---
    try:
        os.environ['AIDER_ENABLED'] = 'true' # Ensure Aider tools are registered
        app_config = {
            "aider": {"enabled": True},
            "handler_config": { 
                "default_model_identifier": "google-gla:gemini-2.5-pro-exp-03-25" 
            }
        }
        app = Application(config=app_config)
        if args.debug and hasattr(app, 'passthrough_handler') and app.passthrough_handler:
            app.passthrough_handler.set_debug_mode(True)
        logger.info("Application instantiated.")

        # Index repository
        logger.info(f"Indexing repository: {PROJECT_ROOT}")
        index_options = {
             "include_patterns": ["src/**/*.py", "*.py", "*.md", "pyproject.toml", "README.md"], 
             "exclude_patterns": ["**/venv/**", "**/.*/**", "**/__pycache__/**", "**/node_modules/**", "*.log", "tests/**"]
        }
        app.index_repository(str(PROJECT_ROOT), options=index_options)
        logger.info("Repository indexing complete (or attempted).")

        # Define necessary atomic tasks for the orchestrator
        plan_def_result = app.handle_task_command(DEFATOM_GENERATE_PLAN_S_EXPRESSION)
        if plan_def_result.get("status") == "FAILED":
             logger.error(f"Failed to define 'user:generate-plan-from-goal': {plan_def_result.get('content')}")
             sys.exit(1)
        
        analysis_def_result = app.handle_task_command(DEFATOM_COMBINED_ANALYSIS_S_EXPRESSION)
        if analysis_def_result.get("status") == "FAILED":
             logger.error(f"Failed to define 'user:evaluate-and-retry-analysis': {analysis_def_result.get('content')}")
             sys.exit(1)
        logger.info("Atomic tasks for workflow defined successfully.")

    except Exception as e:
        logger.exception("Failed to instantiate Application or define tasks. Exiting.")
        sys.exit(1)

    # --- Instantiate and Run the Orchestrator ---
    try:
        orchestrator = CodingWorkflowOrchestrator(
            app=app,
            initial_goal=initial_user_goal,
            initial_context=initial_context_data,
            test_command=user_test_command,
            max_retries=args.max_retries
        )
        
        logger.info("Executing Python-driven coding workflow via orchestrator...")
        final_result = orchestrator.run()
        logger.info("Python-driven coding workflow finished.")

    except Exception as e:
        logger.exception("An error occurred during orchestrator execution.")
        final_result = {"status": "SCRIPT_ERROR", "content": f"Python script error: {e}", "notes": {}}

    # --- Print Final Result ---
    print("\n" + "="*20 + " Workflow Final Result (Python Orchestrator) " + "="*20)
    try:
        print(json.dumps(final_result, indent=2))
        status = final_result.get("status", "UNKNOWN_STATUS")
        reason = final_result.get("reason", "No reason provided.")
        
        if status == "FAILED":
            print("\n--- WORKFLOW FAILED ---")
            print(f"Reason: {reason}")
            details = final_result.get("details")
            if details:
                print(f"Details: {details}")
            analysis_data = final_result.get("analysis_data")
            if analysis_data:
                print(f"Final Analysis Data: {json.dumps(analysis_data, indent=2)}")
        elif status == "COMPLETE" or status == "SUCCESS": 
            print("\n--- WORKFLOW COMPLETED SUCCESSFULLY ---")
            print(f"Final Content/Diff: {final_result.get('content')}")
        else:
            print(f"\n--- WORKFLOW ENDED WITH STATUS: {status} ---")
            print(f"Content: {final_result.get('content')}")
            print(f"Reason: {reason}")

    except Exception as e:
        logger.error(f"Error formatting/printing final result: {e}")
        print("\nRaw Final Result:")
        print(final_result)
    print("="*70)


if __name__ == "__main__":
    main()
