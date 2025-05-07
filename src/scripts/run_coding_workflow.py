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
from src.sexp_evaluator.sexp_environment import SexpEnvironment

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
  (params (goal string) (context_string string)) ;; <<< RENAMED HERE
  (instructions
    "Analyze the user's goal: '{{goal}}' with the provided context: '{{context_string}}'.
    Your *only* task is to generate a development plan. Do *not* attempt to execute any tools or commands yourself.
    The plan must include ONLY:
    1. 'instructions': Detailed steps for an AI coder (Aider).
    2. 'files': List of relative file paths to create/modify.
    Do NOT generate a 'test_command'.
    Output ONLY a single JSON object conforming to the DevelopmentPlan schema (ignore the test_command field). No other text."
  )
  (output_format ((type "json") (schema "src.system.models.DevelopmentPlan")))
  (description "Generates DevelopmentPlan JSON (instructions/files only) from goal/context.")
  ;; (model "...") ; Optionally specify model
)
"""

# S-expression to define the combined analysis task
DEFATOM_COMBINED_ANALYSIS_S_EXPRESSION = """
(defatom user:evaluate-and-retry-analysis
  (params
    (original_goal string)
    (aider_instructions string) ;; The prompt given to Aider this round
    (aider_status string) ;; Status of the aider:automatic task result
    (aider_diff string) ;; Content (diff/error) from the aider:automatic task result
    (test_command string)
    (test_stdout string)
    (test_stderr string)
    (iteration integer)
    (max_retries integer)
  )
  (instructions
    "You are an AI evaluator reviewing a coding task iteration ({{iteration}}/{{max_retries}}).
    Goal: {{original_goal}}
    Aider Prompt This Iteration: {{aider_instructions}}
    Aider Task Status: {{aider_status}}
    Aider Output/Diff/Error:
    {{aider_diff}}

    Test Command Run: {{test_command}}
    Test Stdout:
    {{test_stdout}}
    Test Stderr:
    {{test_stderr}}

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
    **IMPORTANT:** Your entire response MUST be the JSON object itself, starting with `{` and ending with `}`."
  )
  (output_format ((type "json") (schema "src.system.models.CombinedAnalysisResult")))
  (description "Analyzes Aider and test results, determines success/failure/retry, and provides the next prompt if needed.")
  ;; (model "gpt-4-turbo") ; Choose a capable model like gpt-4-turbo or claude-3-opus
)
"""

# REVISED S-expression for the main DEEC loop workflow
MAIN_WORKFLOW_S_EXPRESSION = """
(progn
  (log-message "Starting workflow for goal:" initial-user-goal)
  (log-message "Using Test Command:" user-test-command)

  ;; --- Step 1: Generate Plan ---
  (let ((plan-task-result (user:generate-plan-from-goal
                            (goal initial-user-goal)
                            (context_string initial-context-data))))

    (log-message "Plan generation task. Status:" (get-field plan-task-result "status"))

    ;; --- Step 2: Check Plan Generation Success ---
    (if (not (string=? (get-field plan-task-result "status") "COMPLETE"))
        (progn
          (log-message "ERROR: Plan generation failed.")
          plan-task-result) ;; Return the failed task result

        ;; Success Path: Plan generation succeeded, try parsing
        (let ((plan-data (get-field plan-task-result "parsedContent")))

          ;; --- Step 3: Check Plan Parsing Success ---
          (if (null? plan-data)
              (progn
                (log-message "ERROR: Failed to parse plan JSON.")
                ;; Return a FAILED TaskResult for consistency
                (list (quote status) "FAILED") (list (quote content) "Failed to parse plan JSON.") (list (quote notes) (list (list (quote error) (list (list (quote type) "TASK_FAILURE") (list (quote reason) "output_format_failure") (list (quote message) "Plan parsing failed."))))))

              ;; Success Path: Plan generated and parsed successfully
              (let ((aider-instructions (get-field plan-data "instructions"))
                    (aider-files        (get-field plan-data "files")))

                (log-message "Plan extracted successfully. Files:" aider-files)

                ;; --- Step 4: Execute the DEEC Loop ---
                (director-evaluator-loop
                  (max-iterations 3) ;; Example max retries
                  (initial-director-input aider-instructions)

                  ;; --- Director Phase ---
                  (director (lambda (current-aider-prompt iter-num)
                              (log-message "Director (Iter " iter-num "): Prompting Aider...")
                              current-aider-prompt ))

                  ;; --- Executor Phase ---
                  (executor (lambda (aider-prompt-from-director iter-num)
                              (log-message "Executor (Iter " iter-num "): Calling aider:automatic")
                              (aider_automatic
                                (prompt aider-prompt-from-director)
                                (file_context aider-files) )))

                  ;; --- Evaluator Phase --- (SIMPLIFIED - RUNS TESTS & CALLS COMBINED ANALYSIS)
                  (evaluator (lambda (aider-task-result director-prompt iter-num)
                               (log-message "Evaluator (Iter " iter-num "): Aider TaskResult:" aider-task-result)
                               ;; First, run the tests
                               (log-message "Evaluator: Running test command:" user-test-command)
                               (let ((test-run-result (system_execute_shell_command (command user-test-command))))
                                 (log-message "Evaluator: Test run TaskResult:" test-run-result)

                                 ;; Check if test command itself failed
                                 (if (not (string=? (get-field test-run-result "status") "COMPLETE"))
                                     ;; Test command execution failed, create a FAILED CombinedAnalysisResult structure manually
                                     (progn
                                        (log-message "Evaluator: Shell command for tests failed to execute.")
                                        ;; We need to return something shaped like the CombinedAnalysisResult task *would* have returned
                                        ;; Create a FAILED TaskResult that the Controller can parse
                                        (list (quote status) "COMPLETE") ;; The *evaluator* completed, but contains failure info
                                              (list (quote content) "") ;; No LLM content
                                              (list (quote parsedContent) ;; Mock the parsed content structure
                                                    (list (list (quote verdict) "FAILURE")
                                                          (list (quote next_prompt) nil)
                                                          (list (quote message) (string-append "Test command execution failed: " (get-field test-run-result "content")))))
                                              (list (quote notes) (get-field test-run-result "notes")) ;; Include shell notes if useful
                                      )
                                     ;; Test command executed, call combined LLM analysis task
                                     (progn
                                       (log-message "Evaluator: Calling combined analysis task 'user:evaluate-and-retry-analysis'")
                                       (user:evaluate-and-retry-analysis
                                         (original_goal initial-user-goal)
                                         (aider_instructions director-prompt)
                                         (aider_status (get-field aider-task-result "status"))
                                         (aider_diff (get-field aider-task-result "content")) ;; Pass Aider's content/diff/error
                                         (test_command user-test-command)
                                         (test_stdout (get-field (get-field test-run-result "notes") "stdout"))
                                         (test_stderr (get-field (get-field test-run-result "notes") "stderr"))
                                         (iteration iter-num)
                                         (max_retries (get-field *loop-config* "max-iterations")) ;; Pass max retries
                                        )
                                      )
                                  ) ;; End inner if (test command status check)
                                ) ;; End let test-run-result
                              ) ;; End lambda evaluator
                            ) ;; End evaluator clause

                  ;; --- Controller Phase --- (SIMPLIFIED)
                  (controller (lambda (eval-feedback director-prompt aider-task-result iter-num)
                                ;; eval-feedback is the TaskResult from the *combined* analysis task
                                (log-message "Controller (Iter " iter-num "): Received Combined Analysis TaskResult:" eval-feedback)

                                ;; Check if the combined analysis task ITSELF failed
                                (if (not (string=? (get-field eval-feedback "status") "COMPLETE"))
                                    (progn
                                      (log-message "Controller: Combined analysis task failed!")
                                      (list 'stop eval-feedback)) ;; Stop with the failed analysis task result

                                    ;; Combined analysis task succeeded, parse its structured output
                                    (let ((analysis-data (get-field eval-feedback "parsedContent")))

                                      (if (null? analysis-data)
                                          (progn
                                            (log-message "Controller: Failed to parse combined analysis JSON!")
                                            (list 'stop eval-feedback)) ;; Stop with the unparsed analysis result

                                          ;; Successfully parsed analysis data (CombinedAnalysisResult)
                                          (let ((verdict (get-field analysis-data "verdict")))
                                            (log-message "Controller: Parsed Verdict:" verdict)

                                            (if (string=? verdict "SUCCESS")
                                                (list 'stop aider-task-result) ;; Stop successfully with Aider's result

                                                (if (string=? verdict "RETRY")
                                                    ;; Extract next prompt and continue
                                                    (let ((next-prompt (get-field analysis-data "next_prompt")))
                                                      (log-message "Controller: Verdict is RETRY. Next prompt:" next-prompt)
                                                      (list 'continue next-prompt))

                                                    ;; Verdict must be FAILURE (or unexpected)
                                                    (progn
                                                      (log-message "Controller: Verdict is FAILURE. Stopping loop.")
                                                      (list 'stop eval-feedback)) ;; Stop with the analysis result containing the failure message
                                                )
                                            )
                                          ) ;; End let verdict
                                        ) ;; End if null? analysis-data
                                      ) ;; End let analysis-data
                                    ) ;; End if status COMPLETE check
                                  ) ;; End lambda controller
                                ) ;; End controller clause
                ) ;; End director-evaluator-loop
              ) ;; End let aider-instructions/files
          ) ;; End inner if (null? plan-data)
        ) ;; End outer let (plan-data)
    ) ;; End outer if (status check)
  ) ;; End outer let (plan-task-result)
) ;; End progn
"""

def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Run a coding workflow using S-expressions.")
    parser.add_argument("--goal", required=True, help="The user's coding goal.")
    parser.add_argument("--context-file", help="Optional path to a file containing initial context.")
    parser.add_argument("--test-command", default="pytest tests/", help="The shell command to run for verification.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)
        logger.info("Debug logging enabled.")

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

    # --- Instantiate Application ---
    try:
        # Ensure Aider is enabled if needed by the workflow
        os.environ['AIDER_ENABLED'] = 'true'
        app = Application()
        if args.debug:
             if hasattr(app, 'passthrough_handler') and app.passthrough_handler:
                 app.passthrough_handler.set_debug_mode(True)
             else:
                 logger.warning("Could not enable debug mode on handler (not found).")

        logger.info("Application instantiated.")
    except Exception as e:
        logger.exception("Failed to instantiate Application. Exiting.")
        sys.exit(1)

    # --- !!! ADD THIS STEP: Index the Repository !!! ---
    logger.info(f"Indexing repository: {PROJECT_ROOT}") # Assuming PROJECT_ROOT is the target
    index_options = { # Optional: Define specific include/exclude patterns if needed
         "include_patterns": ["src/**/*.py", "*.py", "*.md"],
         "exclude_patterns": ["**/venv/**", "**/.*/**", "**/__pycache__/**"]
    }
    try:
        success = app.index_repository(str(PROJECT_ROOT), options=index_options) # Ensure PROJECT_ROOT is string
        if not success:
            logger.warning("Repository indexing failed or returned False. Context might be incomplete.")
            # Decide whether to exit or continue
        else:
            logger.info("Repository indexing complete.")
    except Exception as index_err:
        logger.exception(f"Error during repository indexing: {index_err}")
        # Decide whether to exit or continue
    # --- END ADDED STEP ---

    # --- Define Atomic Tasks ---
    logger.info("Defining atomic tasks via defatom...")
    try:
        # Execute Plan Generator Defatom
        plan_def_result = app.handle_task_command(DEFATOM_GENERATE_PLAN_S_EXPRESSION)
        if plan_def_result.get("status") == "FAILED":
             logger.error(f"Failed to define 'user:generate-plan-from-goal': {plan_def_result.get('content')}")
             sys.exit(1)
        logger.debug("Defined 'user:generate-plan-from-goal'")

        # Execute COMBINED Feedback Analyzer Defatom
        combined_analysis_def_result = app.handle_task_command(DEFATOM_COMBINED_ANALYSIS_S_EXPRESSION)
        if combined_analysis_def_result.get("status") == "FAILED":
             logger.error(f"Failed to define 'user:evaluate-and-retry-analysis': {combined_analysis_def_result.get('content')}")
             sys.exit(1)
        logger.debug("Defined 'user:evaluate-and-retry-analysis'")

        logger.info("Atomic tasks defined successfully.")
    except Exception as e:
         logger.exception("Error occurred while defining atomic tasks. Exiting.")
         sys.exit(1)


    # --- Prepare Initial Parameters for Dispatcher ---
    initial_params = {
        "initial-user-goal": initial_user_goal,
        "initial-context-data": initial_context_data,
        "user-test-command": user_test_command
    }
    logger.debug(f"Initial parameters for workflow execution: {initial_params}")

    # --- Execute Main Workflow ---
    logger.info("Executing main workflow S-expression...")
    try:
        # Use the main workflow string defined earlier
        final_result = app.handle_task_command(
            identifier=MAIN_WORKFLOW_S_EXPRESSION,
            params=initial_params, # Pass the dictionary here
            flags={"is_sexp_string": True} # Ensure this flag is handled
        )
        logger.info("Main workflow execution finished.")
    except Exception as e:
        logger.exception("An error occurred during main workflow execution.")
        final_result = {"status": "FAILED", "content": f"Python script error: {e}", "notes": {}}


    # --- Print Final Result ---
    print("\n" + "="*20 + " Workflow Final Result " + "="*20)
    try:
        print(json.dumps(final_result, indent=2))
        if final_result.get("status") == "FAILED":
            print("\n--- WORKFLOW FAILED ---")
        elif final_result.get("status") == "COMPLETE":
             print("\n--- WORKFLOW COMPLETED ---")
        else:
             print("\n--- WORKFLOW ENDED WITH UNEXPECTED STATUS ---")

    except Exception as e:
        logger.error(f"Error formatting/printing final result: {e}")
        print("\nRaw Final Result:")
        print(final_result)
    print("="*63)


if __name__ == "__main__":
    main()
