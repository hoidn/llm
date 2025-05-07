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

# S-expression to define the feedback analysis task
DEFATOM_ANALYZE_AIDER_RESULT_S_EXPRESSION = """
(defatom user:analyze-aider-result
  (params
    (aider_result_content string)
    (aider_result_status string)
    (original_prompt string)
    (iteration integer)
    (max_retries integer)
  )
  (instructions
    "Analyze Aider result (Iter {{iteration}}/{{max_retries}}):
    Status: {{aider_result_status}}
    Output/Error: {{aider_result_content}}
    Original Prompt: {{original_prompt}}
    Decide: SUCCESS, REVISE (provide 'next_prompt'), or ABORT.
    Output ONLY JSON conforming to FeedbackResult schema."
  )
  (output_format ((type "json") (schema "src.system.models.FeedbackResult")))
  (description "Analyzes Aider result and provides feedback/next steps.")
  ;; (model "...") ; Optionally specify model
)
"""

# S-expression to define the task that analyzes test command output
DEFATOM_ANALYZE_TEST_RESULT_S_EXPRESSION = """
(defatom user:analyze-test-result
  (params
    (test_command string)
    (test_stdout string)
    (test_stderr string)
    (aider_diff string) ;; Optional context: what changes were made?
    (original_goal string) ;; Optional context: what was the goal?
  )
  (instructions
    "You are an AI test evaluator. Analyze the output of a test command run after an AI coding assistant made changes.
    Goal being worked on: {{original_goal}}
    Changes made by AI (diff):
    {{aider_diff}}

    Test command executed: {{test_command}}
    Standard Output (stdout):
    {{test_stdout}}
    Standard Error (stderr):
    {{test_stderr}}

    Based *only* on the stdout and stderr, determine if the tests passed successfully or if there were failures.
    - If the output indicates all tests passed (e.g., pytest showing 'PASSED', no errors), status is 'TESTS_PASSED'.
    - If the output indicates test failures, errors, or an empty test suite run, status is 'TESTS_FAILED'.

    Output ONLY a valid JSON object strictly conforming to this structure:
    {
      \\"eval_status\\": \\"TESTS_PASSED\\" | \\"TESTS_FAILED\\",
      \\"message\\": \\"Brief summary (e.g., 'All tests passed.', 'Pytest reported 3 failures.')\\"
    }
    Do not include any other text, explanations, or formatting."
  )
  ;; Choose a model good at analysis and JSON output
  ;; (model "gpt-4-turbo")
  (output_format ((type "json") (schema null))) ;; We'll parse manually or define a schema later if needed
  (description "Analyzes test command stdout/stderr to determine pass/fail status.")
)
"""

# S-expression for the main DEEC loop workflow (REVISED EVALUATOR)
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
                (list 'error 'plan_parsing_failed "Failed to parse plan JSON from task result."))
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

                  ;; --- Evaluator Phase --- # <<<< MODIFIED LOGIC >>>>
                  (evaluator (lambda (aider-task-result director-prompt iter-num)
                               (log-message "Evaluator (Iter " iter-num "): Aider TaskResult:" aider-task-result)
                               (if (string=? (get-field aider-task-result "status") "FAILED")
                                   ;; Aider itself failed - create feedback directly
                                   (list (list 'eval_status "AIDER_FAILED")
                                         (list 'message (get-field aider-task-result "content")))
                                   ;; Aider succeeded, run tests and ANALYZE OUTPUT WITH LLM
                                   (progn
                                     (log-message "Evaluator: Running test command:" user-test-command)
                                     (let ((test-run-result (system_execute_shell_command (command user-test-command))))
                                       (log-message "Evaluator: Test run TaskResult:" test-run-result)
                                       (if (string=? (get-field test-run-result "status") "COMPLETE")
                                           ;; Test command ran, call LLM to analyze its output
                                           (let ((test-stdout (get-field (get-field test-run-result "notes") "stdout"))
                                                 (test-stderr (get-field (get-field test-run-result "notes") "stderr"))
                                                 (aider-diff (get-field (get-field aider-task-result "notes") "diff"))) ;; Get diff for context
                                             (log-message "Evaluator: Calling LLM to analyze test output...")
                                             ;; Call the new LLM analysis task
                                             (user:analyze-test-result
                                               (test_command user-test-command)
                                               (test_stdout test-stdout)
                                               (test_stderr test-stderr)
                                               (aider_diff aider-diff) ;; Pass diff
                                               (original_goal initial-user-goal) ;; Pass goal
                                              )
                                            )
                                           ;; Test command itself failed to execute - create feedback directly
                                           (list (list 'eval_status "SHELL_CMD_FAILED")
                                                 (list 'message "Test command execution failed.")
                                                 (list 'shell_error (get-field test-run-result "content")))
                                        )
                                      ) ;; end let test-run-result
                                    ) ;; end progn
                                ) ;; end if aider status check
                              ) ;; end lambda evaluator
                            ) ;; end evaluator clause

                  ;; --- Controller Phase --- (REVISED FIELD CHECK)
                  (controller (lambda (eval-feedback director-prompt aider-task-result iter-num)
                                ;; eval-feedback is the TaskResult from user:analyze-test-result
                                (log-message "Controller (Iter " iter-num "): Received Eval Feedback TaskResult:" eval-feedback)
                                (if (not (string=? (get-field eval-feedback "status") "COMPLETE")) ;; Check if the analysis task ITSELF failed
                                    (progn (log-message "Controller: Test analysis task failed!") (list 'stop eval-feedback))
                                    ;; Test analysis task succeeded, parse its structured output
                                    (let ((analysis-data (get-field eval-feedback "parsedContent")))
                                      (if (null? analysis-data)
                                          (progn (log-message "Controller: Failed to parse test analysis JSON!") (list 'stop eval-feedback))
                                          ;; Successfully parsed analysis data
                                          (let ((eval-status (get-field analysis-data "eval_status")) ;; <<< GET eval_status FROM PARSED CONTENT
                                                (max-iters (get-field *loop-config* "max-iterations")))
                                              (log-message "Controller: Parsed Eval Status:" eval-status)
                                              (if (string=? eval-status "TESTS_PASSED") ;; <<< CHECK CORRECT FIELD
                                                  (list 'stop aider-task-result)
                                                  ;; --- Rest of failure/retry logic (using user:analyze-aider-result for Aider feedback) ---
                                                  (if (< iter-num max-iters)
                                                      (let ((aider-analysis-task-result ;; Renamed variable clearly
                                                             (user:analyze-aider-result ;; Call Aider analysis task
                                                               (aider_result_content (get-field aider-task-result "content"))
                                                               (aider_result_status (get-field aider-task-result "status"))
                                                               (original_prompt director-prompt)
                                                               (iteration iter-num)
                                                               (max_retries max-iters))))
                                                        (log-message "Controller: Aider result analysis status:" (get-field aider-analysis-task-result "status"))
                                                        (if (and (string=? (get-field aider-analysis-task-result "status") "COMPLETE")
                                                                 (not (null? (get-field aider-analysis-task-result "parsedContent")))
                                                                 (string=? (get-field (get-field aider-analysis-task-result "parsedContent") "status") "REVISE"))
                                                            (list 'continue (get-field (get-field aider-analysis-task-result "parsedContent") "next_prompt"))
                                                            (progn (log-message "Controller: Stopping loop due to Aider analysis result (failed, abort, or parse error).") (list 'stop eval-feedback)) ;; Stop with TEST eval feedback if Aider analysis fails/aborts
                                                        ))
                                                      (progn (log-message "Controller: Max iterations reached.") (list 'stop eval-feedback)) ;; Stop with TEST eval feedback
                                                  )
                                                ) ;; end if TESTS_PASSED check
                                            ) ;; end let eval-status
                                          ) ;; end if null? analysis-data
                                        ) ;; end let analysis-data
                                    ) ;; end if status COMPLETE check
                                  ) ;; end lambda controller
                                ) ;; end controller clause
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

        # Execute Feedback Analyzer Defatom
        feedback_def_result = app.handle_task_command(DEFATOM_ANALYZE_AIDER_RESULT_S_EXPRESSION)
        if feedback_def_result.get("status") == "FAILED":
             logger.error(f"Failed to define 'user:analyze-aider-result': {feedback_def_result.get('content')}")
             sys.exit(1)
        logger.debug("Defined 'user:analyze-aider-result'")

        # Execute Test Result Analyzer Defatom
        test_analysis_def_result = app.handle_task_command(DEFATOM_ANALYZE_TEST_RESULT_S_EXPRESSION)
        if test_analysis_def_result.get("status") == "FAILED":
            logger.error(f"Failed to define 'user:analyze-test-result': {test_analysis_def_result.get('content')}")
            sys.exit(1)
        logger.debug("Defined 'user:analyze-test-result'")

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
