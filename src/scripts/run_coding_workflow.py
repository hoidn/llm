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
  (params (goal string) (context string))
  (instructions
    "Analyze the user's goal: '{{goal}}' with the provided context: '{{context}}'.
    Generate a development plan including ONLY:
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

# S-expression for the main DEEC loop workflow
MAIN_WORKFLOW_S_EXPRESSION = """
(begin ;; Variables initial-user-goal, initial-context-data, user-test-command are expected in env

  (log-message "Starting workflow for goal:" initial-user-goal)
  (log-message "Using Test Command:" user-test-command)

  ;; 1. Generate the Plan (Instructions/Files only)
  (let ((plan-task-result (user:generate-plan-from-goal
                            (goal initial-user-goal)
                            (context initial-context-data))))

    (log-message "Plan generation task result:" plan-task-result)

    ;; 2. Check Plan Generation Success & Extract Data
    (if (string=? (get-field plan-task-result "status") "COMPLETE")
        (let ((plan-data (get-field plan-task-result "parsedContent")))
          (if (null? plan-data)
              (progn (log-message "ERROR: Failed to parse plan JSON.") (quote plan_parsing_failed))
              ;; --- Plan successful, extract components ---
              (let ((aider-instructions (get-field plan-data "instructions"))
                    (aider-files        (get-field plan-data "files")))

                (log-message "Plan extracted successfully. Instructions:" aider-instructions)
                (log-message "Files:" aider-files)

                ;; 3. Enter the Director-Evaluator-Executor-Controller Loop
                (director-evaluator-loop
                  (max-iterations 3) ;; Example max retries
                  (initial-director-input aider-instructions)

                  ;; --- Director Phase ---
                  (director (lambda (current-aider-prompt iter-num)
                              (log-message "Director (Iter " iter-num "): Prompting Aider with:" current-aider-prompt)
                              current-aider-prompt ))

                  ;; --- Executor Phase ---
                  (executor (lambda (aider-prompt-from-director iter-num)
                              (log-message "Executor (Iter " iter-num "): Calling aider:automatic")
                              (aider_automatic
                                (prompt aider-prompt-from-director)
                                (file_context aider-files) )))

                  ;; --- Evaluator Phase ---
                  (evaluator (lambda (aider-task-result director-prompt iter-num)
                               (log-message "Evaluator (Iter " iter-num "): Aider TaskResult:" aider-task-result)
                               (if (string=? (get-field aider-task-result "status") "FAILED")
                                   (list (list 'eval_status "AIDER_FAILED") (list 'message (get-field aider-task-result "content")))
                                   (progn
                                     (log-message "Evaluator: Running user-provided test command:" user-test-command)
                                     (let ((test-run-result (system_execute_shell_command (command user-test-command))))
                                       (log-message "Evaluator: Test run TaskResult:" test-run-result)
                                       (if (string=? (get-field test-run-result "status") "COMPLETE")
                                           (if (eq? (get-field (get-field test-run-result "notes") "exit_code") 0)
                                               (list (list 'eval_status "TESTS_PASSED") (list 'message "Tests passed.") (list 'test_output (get-field test-run-result "content")))
                                               (list (list 'eval_status "TESTS_FAILED") (list 'message "Tests failed.") (list 'test_output (get-field test-run-result "content")) (list 'test_error (get-field (get-field test-run-result "notes") "stderr"))))
                                           (list (list 'eval_status "SHELL_CMD_FAILED") (list 'message "Test command execution failed.") (list 'shell_error (get-field test-run-result "content")))))))))

                  ;; --- Controller Phase ---
                  (controller (lambda (eval-feedback director-prompt aider-task-result iter-num)
                                (log-message "Controller (Iter " iter-num "): Eval feedback:" eval-feedback)
                                (let ((eval-status (get-field eval-feedback "eval_status"))
                                      (max-iters (get-field *loop-config* "max-iterations")))
                                  (if (string=? eval-status "TESTS_PASSED")
                                      (list 'stop aider-task-result)
                                      (if (< iter-num max-iters)
                                          (let ((analysis-task-result
                                                  (user:analyze-aider-result
                                                    (aider_result_content (get-field aider-task-result "content"))
                                                    (aider_result_status (get-field aider-task-result "status"))
                                                    (original_prompt director-prompt)
                                                    (iteration iter-num)
                                                    (max_retries max-iters))))
                                            (log-message "Controller: Feedback analysis result:" analysis-task-result)
                                            (if (string=? (get-field analysis-task-result "status") "COMPLETE")
                                                (let ((feedback-data (get-field analysis-task-result "parsedContent")))
                                                  (if (null? feedback-data)
                                                      (progn (log-message "ERROR: Failed to parse FeedbackResult JSON.") (list 'stop eval-feedback))
                                                      (let ((feedback-status (get-field feedback-data "status")))
                                                        (if (string=? feedback-status "REVISE")
                                                            (list 'continue (get-field feedback-data "next_prompt"))
                                                            (list 'stop eval-feedback) ))))
                                                (list 'stop eval-feedback) ))
                                          (progn (log-message "Controller: Max iterations reached. Stopping.") (list 'stop eval-feedback)) ))))))
                ) ;; End director-evaluator-loop
              ) ;; End inner let (extracted plan components)
          ) ;; End if plan-data not null
        ) ;; End if plan generation COMPLETE
        (progn
          (log-message "ERROR: Plan generation failed. Status:" (get-field plan-task-result "status"))
          plan-task-result ;; Return the failed plan result
        ) ;; End outer if
    ) ;; End outer let (plan-task-result)
) ;; End begin
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
