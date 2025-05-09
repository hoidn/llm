#!/usr/bin/env python
"""
Script to run a coding workflow using S-expressions.

This script orchestrates a series of tasks including:
1. Generating a development plan using an LLM.
2. Executing coding tasks using Aider (via aider:automatic tool).
3. Running user-provided test commands to verify the code.
4. Analyzing Aider and test results using an LLM to decide on next steps (revise or stop).
This entire workflow is defined and driven by S-expressions.

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
     --test-command "pytest tests/test_utils.py"

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
# from src.sexp_evaluator.sexp_environment import SexpEnvironment # No longer needed for Sexp initial_env
from src.orchestration.coding_workflow_orchestrator import CodingWorkflowOrchestrator # Add this import
import json

# --- Logging Setup ---
LOG_LEVEL = logging.INFO # Or DEBUG
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger().setLevel(LOG_LEVEL)
logger = logging.getLogger("CodingWorkflowScript")


# S-expression to define the planning task (outputs instructions/files ONLY)
DEFATOM_GENERATE_PLAN_S_EXPRESSION = """
(defatom user:generate-plan-from-goal
  (instructions
    "Analyze the user's goal: '{{goal}}' with the provided context: '{{context_string}}'.
    Your *only* task is to generate a development plan. Do *not* attempt to execute any tools or commands yourself.
    The plan must include ONLY:
    1. 'instructions': Detailed steps for an AI coder (Aider).
    2. 'files': List of relative file paths to create / modify or use as context (including both souce modules and their associated test files)
    Do NOT generate a 'test_command'.
    Output ONLY a single JSON object conforming to the DevelopmentPlan schema (ignore the test_command field). No other text."
  )
  (params (goal string) (context_string string)) ;; <<< RENAMED HERE
  (output_format ((type "json") (schema "src.system.models.DevelopmentPlan")))
  (description "Generates DevelopmentPlan JSON (instructions/files only) from goal/context.")
  ;; (model "...") ; Optionally specify model
)
"""

# S-expression to define the combined analysis task
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
    Files In Play: {{previous_files}}

    Analyze the test output (stdout/stderr) to determine if tests passed.
    - If tests passed (e.g., pytest shows PASSED, no errors in stderr), verdict is 'SUCCESS'.
    - If tests failed:
        - Check if iteration < max_retries.
        - If yes, analyze the failure (test output, Aider diff) and generate a *revised* 'next_prompt' for Aider to fix the issues. Verdict is 'RETRY'.
        - If no (max retries reached or failure seems unfixable), verdict is 'FAILURE'.
    - If the Aider task itself failed ('aider_status' != 'COMPLETE'), verdict is usually 'FAILURE' unless a simple retry seems possible (provide 'next_prompt' and verdict 'RETRY').

    Provide a concise explanation in 'message'.
    Output ONLY JSON conforming to the CombinedAnalysisResult schema.
    Ensure 'next_prompt' is provided *only* if verdict is 'RETRY'.
    If you output verdict:RETRY you must echo a non-empty files array; otherwise the controller will reuse the prior list.
    Ensure you include ALL the relevant filenames from previous_files that will be needed, in addition to any new additions not part of previous_files
    **IMPORTANT:** Your entire response MUST be the JSON object itself, starting with `{` and ending with `}`."
  )
  (params
    (original_goal string)
    (initial_task_context string) ;; <<< ADD THIS NEW PARAMETER
    (aider_instructions string) ;; The prompt given to Aider this round
    (aider_status string) ;; Status of the aider:automatic task result
    (aider_diff string) ;; Content (diff/error) from the aider:automatic task result
    (test_command string)
    (test_stdout string)
    (test_stderr string)
    (test_exit_code int)
    (previous_files list) ;; <-- ADD THIS LINE
    (iteration integer)
    (max_retries integer)
  )
  (output_format ((type "json") (schema "src.system.models.CombinedAnalysisResult")))
  (description "Analyzes Aider and test results, determines success/failure/retry, and provides the next prompt if needed.")
  (model "google-gla:gemini-2.5-pro-exp-03-25") ;; Explicitly set the model to use
)
"""

# REVISED S-expression for the main DEEC loop workflow
MAIN_WORKFLOW_S_EXPRESSION = """
(progn
  (log-message "Starting iterative-loop workflow for goal:" initial-user-goal) ;; Use hyphenated symbol
  (log-message "Using Test Command:" fixed-test-command) ;; Use hyphenated symbol

  ;; Variables initial_plan_data, fixed_test_command, initial_user_goal, max_iterations_config
  ;; are expected to be bound in the initial environment passed from Python (using hyphens).

  ;; Generate first plan so current-plan is not empty
  (bind initial-plan-task-result ;; Store the full task result
        (user:generate-plan-from-goal
          (goal           initial-user-goal)
          (context_string initial-context-data)))
  (bind initial-plan-data ;; Extract parsedContent for the loop
        (get-field initial-plan-task-result "parsedContent"))
    
  (iterative-loop
    (max-iterations max-iterations-config) ;; Use hyphenated symbol
    (initial-input initial-plan-data) ;; Pass the initial plan dict/assoc-list
    (test-command fixed-test-command) ;; Use hyphenated symbol

    ;; --- Executor Phase ---
    (executor (lambda (current-plan iter-num)
                (log-message "Executor (Iter " iter-num "): Executing plan with instructions: " (get-field current-plan "instructions"))
                (aider_automatic
                  (prompt (get-field current-plan "instructions"))
                  ;; If the plan’s list is empty use NIL so MCP will allow new files
                  (relative_editable_files
                       (if (null? (get-field current-plan "files"))
                           nil
                           (get-field current-plan "files"))))))

    ;; --- Validator Phase ---
    (validator (lambda (test-cmd iter-num)
                 (log-message "Validator (Iter " iter-num "): Running command:" test-cmd)
                 (let ((test_task_result (system_execute_shell_command (command test-cmd))))
                   (log-message "Validator: Shell command TaskResult:" test_task_result)
                   ;; Construct ValidationResult association list safely
                   (let ((test_notes (get-field test_task_result "notes"))
                         (stdout_val "") ;; Default values
                         (stderr_val "")
                         (exit_code_val -1)
                         (error_val nil))

                     ;; Safely extract notes if they exist
                     (if (not (null? test_notes))
                         (progn ;; Use progn for multiple expressions in 'then'
                           (set! stdout_val (if (null? (get-field test_notes "stdout")) "" (get-field test_notes "stdout")))
                           (set! stderr_val (if (null? (get-field test_notes "stderr")) "" (get-field test_notes "stderr")))
                           (set! exit_code_val (if (null? (get-field test_notes "exit_code")) -1 (get-field test_notes "exit_code")))
                         )
                         nil ;; 'if' else branch returns nil
                     )
                     ;; Set error value if the task itself failed
                     (if (string=? (get-field test_task_result "status") "FAILED")
                         (set! error_val (get-field test_task_result "content"))
                         nil ;; else branch for the error check
                     )
                     ;; Return the final validation structure
                     (list
                       (list 'stdout stdout_val)
                       (list 'stderr stderr_val)
                       (list 'exit_code exit_code_val)
                       (list 'error error_val)
                      )))))

    ;; --- Controller Phase ---
    (controller (lambda (aider_result validation_result current-plan iter_num)
                  (log-message "Controller (Iter " iter_num "): Analyzing Aider result status:" (get-field aider_result "status") " and Validation result exit_code:" (get-field validation_result "exit_code"))
                  ;; Call the analysis/revision LLM task
                  (let ((analysis_task_result
                         (user:evaluate-and-retry-analysis ;; Corrected task name
                           ;; Parameters for user:evaluate-and-retry-analysis
                           (original_goal initial-user-goal)
                           (initial_task_context initial-context-data) ;; <<< ADD THIS ARGUMENT
                           (aider_instructions (get-field current-plan "instructions"))
                           (previous_files (get-field current-plan "files"))
                           (aider_status (get-field aider_result "status"))
                           (aider_diff (get-field aider_result "content"))
                           (test_command fixed-test-command)
                           (test_stdout (get-field validation_result "stdout"))
                           (test_stderr (get-field validation_result "stderr"))
                           (test_exit_code (get-field validation_result "exit_code"))
                           (iteration iter_num)
                           (max_retries max-iterations-config)
                          )))
                    (log-message "Controller: Analysis TaskResult:" analysis_task_result)

                    ;; Process analysis result
                    (if (string=? (get-field analysis_task_result "status") "FAILED")
                        (list 'stop analysis_task_result) ;; Stop if analysis task itself failed
                        (let ((analysis_data (get-field analysis_task_result "parsedContent"))) ;; Expects ControllerAnalysisResult dict
                          (if (null? analysis_data)
                              (progn
                                (log-message "Controller: Failed to parse analysis task result!")
                                (list 'stop analysis_task_result)) ;; Stop if parsing failed
                              (let ((verdict (get-field analysis_data "verdict")))
                                (log-message "Controller: Analysis Verdict:" verdict)
                                (if (string=? verdict "RETRY")
                                    (let ((next-instructions (get-field analysis_data "next_prompt"))
                                          (next-files (get-field analysis_data "files")))
                                      (if (null? next-files) ;; If LLM omits files on RETRY or files field is null
                                          (set! next-files (get-field current-plan "files")) ;; Fallback to current plan's files
                                          nil)
                                      (list 'continue (list
                                                        (list 'instructions next-instructions)
                                                        (list 'files next-files))))
                                    (if (string=? verdict "SUCCESS")
                                        (list 'stop analysis_task_result) ;; Stop with the SUCCESS analysis result
                                        ;; verdict == "FAILURE" (or anything unexpected)
                                        (list 'stop analysis_task_result) ;; Stop with the analysis result explaining why
                                    ))))))))))
) ;; End progn
"""

def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Run a coding workflow using S-expressions.")
    parser.add_argument("--goal", required=True, help="The user's coding goal.")
    parser.add_argument("--context-file", help="Optional path to a file containing initial context.")
    parser.add_argument("--test-command", default="pytest tests/", help="The shell command to run for verification.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retry iterations.")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)
        logger.info("Debug logging enabled.")
        os.environ['DEBUG_LLM_FLOW'] = 'true'

    initial_user_goal = args.goal
    initial_context_data = ""
    if args.context_file:
        try:
            context_file_path = pathlib.Path(args.context_file).resolve()
            logger.info(f"Reading context file: {context_file_path}")
            if context_file_path.is_file():
                with open(context_file_path, 'r') as f:
                    initial_context_data = f.read()
                logger.debug("Context file read successfully.")
            else:
                logger.warning(f"Context file not found: {context_file_path}")
        except Exception as e:
            logger.warning(f"Could not read context file {args.context_file}: {e}")

    user_test_command = args.test_command
    logger.info(f"Using Goal: {initial_user_goal}")
    logger.info(f"Using Context Data (length): {len(initial_context_data)}")
    logger.info(f"Using Test Command: {user_test_command}")
    logger.info(f"Using Max Retries: {args.max_retries}")

    try:
        os.environ['AIDER_ENABLED'] = 'true'
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

        logger.info(f"Indexing repository: {PROJECT_ROOT}")
        index_options = {
             "include_patterns": ["src/**/*.py", "*.py", "*.md"],
             "exclude_patterns": ["**/venv/**", "**/.*/**", "**/__pycache__/**"]
        }
        app.index_repository(str(PROJECT_ROOT), options=index_options)
        logger.info("Repository indexing complete (or attempted).")

        plan_def_result = app.handle_task_command(DEFATOM_GENERATE_PLAN_S_EXPRESSION)
        if plan_def_result.get("status") == "FAILED":
             logger.error(f"Failed to define 'user:generate-plan-from-goal': {plan_def_result.get('content')}")
             sys.exit(1)
        
        analysis_def_result = app.handle_task_command(DEFATOM_COMBINED_ANALYSIS_S_EXPRESSION)
        if analysis_def_result.get("status") == "FAILED":
             logger.error(f"Failed to define 'user:evaluate-and-retry-analysis': {analysis_def_result.get('content')}")
             sys.exit(1)
        logger.info("Atomic tasks for workflow defined successfully.")

        orchestrator = CodingWorkflowOrchestrator(
            app=app,
            initial_goal=initial_user_goal,
            initial_context=initial_context_data,
            test_command=user_test_command,
            max_retries=args.max_retries
        )
        
        logger.info("Executing Python-driven coding workflow...")
        final_result = orchestrator.run()
        logger.info("Python-driven coding workflow finished.")

    except Exception as e:
        logger.exception("An error occurred during main script execution.")
        final_result = {"status": "SCRIPT_ERROR", "content": f"Python script error: {e}", "notes": {}}

    print("\n" + "="*20 + " Workflow Final Result (Python Orchestrator) " + "="*20)
    try:
        print(json.dumps(final_result, indent=2))
        if final_result.get("status") == "FAILED":
            print("\n--- WORKFLOW FAILED ---")
            print(f"Reason: {final_result.get('reason', 'Unknown')}")
            if "details" in final_result: # Check if 'details' key exists
                details_content = final_result['details']
                # If details is a dict (e.g. from model_dump), pretty print it
                if isinstance(details_content, dict):
                    print(f"Details: {json.dumps(details_content, indent=2)}")
                else:
                    print(f"Details: {details_content}")
        elif final_result.get("status") == "COMPLETE" or final_result.get("status") == "SUCCESS":
            print("\n--- WORKFLOW COMPLETED SUCCESSFULLY (according to orchestrator) ---")
        else:
            print(f"\n--- WORKFLOW ENDED WITH STATUS: {final_result.get('status')} ---")

    except Exception as e:
        logger.error(f"Error formatting/printing final result: {e}")
        print("\nRaw Final Result:")
        print(final_result)
    print("="*70) # Adjusted length to match the header

if __name__ == "__main__":
    main()
