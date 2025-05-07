#!/usr/bin/env python
"""
Demonstrates the director-evaluator-loop S-expression special form.

This script orchestrates a simplified coding task:
1. An LLM (via user:generate-plan task) generates a plan to create a Python file
   with a simple function and a corresponding test file.
2. Aider (via aider:automatic tool) attempts to implement this plan.
3. A shell command (via system:execute_shell_command tool) runs the tests.
4. A controller logic (using *loop-config* to access max-iterations for retry logic)
   decides whether the task is complete or if Aider needs to try again.

Usage:
    python src/scripts/director_loop_coding_demo.py
"""
import argparse
import json
import logging
import os
import pathlib
import sys

# Add the project root to the Python path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.main import Application
    from src.system.models import DevelopmentPlan # For type hinting if needed, and schema path
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print(f"Ensure PROJECT_ROOT is correctly set to: {PROJECT_ROOT}")
    print(f"And that the script is run from a context where src.* modules are discoverable.")
    sys.exit(1)

# Configure logging
LOG_LEVEL = logging.INFO # Or DEBUG for more verbosity
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


DEFATOM_GENERATE_PLAN_S_EXPRESSION = """
(defatom user:generate-plan
  (params 
    (user_prompts str) 
    (initial_context optional str)
  )
  (instructions 
    "You are a helpful AI assistant. Your task is to generate a development plan based on the user's request.
    The plan should include:
    1. 'instructions': Detailed, step-by-step instructions for an AI coding assistant like Aider to implement the request. These instructions should be clear and actionable.
    2. 'files': A list of ALL file paths that need to be created or modified to implement the plan. These paths should be relative to the root of the current project workspace (e.g., 'src/new_module/file.py', 'tests/new_module/test_file.py').
    3. 'test_command': A single shell command string that can be executed from the root of the current project workspace to run all tests and verify the implementation. This command should exit with 0 on success and non-zero on failure.

    IMPORTANT: You MUST output ONLY a single JSON string that strictly conforms to the following Pydantic model schema:
    {
      \\"instructions\\": \\"string\\",
      \\"files\\": [\\"string\\"],
      \\"test_command\\": \\"string\\"
    }
    Do not add any explanatory text before or after the JSON object.
    
    User Request: {{user_prompts}}
    Initial Context: {{initial_context}}
    "
  )
  (model "gpt-4-turbo") ;; Or your preferred model for plan generation
  (output_format ((type "json") (schema "src.system.models.DevelopmentPlan")))
  (description "Generates a development plan (instructions, files, test_command) based on user prompts.")
)
"""

MAIN_LOOP_S_EXPRESSION = """
(director-evaluator-loop
  (max-iterations 3)
  (initial-director-input "Create a Python file 'math_util.py' with an 'add(a, b)' function that returns their sum. Also create 'test_math_util.py' with a test for add(2,3)==5.")

  (director (lambda (current-goal iter-num)
              (log-message "Director (Iter " iter-num "): Goal: " current-goal)
              (user:generate-plan (user_prompts current-goal) (initial_context "Operating in temporary workspace."))))

  (executor (lambda (plan-task-result iter-num)
              (log-message "Executor (Iter " iter-num "): Plan TaskResult: " plan-task-result)
              (let ((plan-data (get-field plan-task-result "parsedContent"))) ;; Access DevelopmentPlan object
                (aider_automatic
                  (prompt (get-field plan-data "instructions"))
                  (file_context (get-field plan-data "files"))))))

  (evaluator (lambda (aider-task-result plan-task-result iter-num)
               (log-message "Evaluator (Iter " iter-num "): Aider TaskResult: " aider-task-result)
               (if (string=? (get-field aider-task-result "status") "FAILED")
                   (list (list (quote eval_status) "AIDER_FAILED") (list (quote message) (get-field aider-task-result "content")))
                   (let ((plan-data (get-field plan-task-result "parsedContent"))) ;; First let for plan-data
                     (let ((test-cmd (get-field plan-data "test_command")))       ;; Nested let for test-cmd, can access plan-data
                       (log-message "Evaluator: Running test command: " test-cmd)
                       (let ((test-run-result (system_execute_shell_command (command test-cmd))))
                         (log-message "Evaluator: Test run TaskResult: " test-run-result)
                         (if (string=? (get-field test-run-result "status") "COMPLETE")
                             (if (eq? (get-field (get-field test-run-result "notes") "exit_code") 0)
                                 (list (list (quote eval_status) "TESTS_PASSED") (list (quote message) "Tests passed.") (list (quote test_output) (get-field test-run-result "content")))
                                 (list (list (quote eval_status) "TESTS_FAILED") (list (quote message) "Tests failed.") (list (quote test_output) (get-field test-run-result "content")) (list (quote test_error) (get-field (get-field test-run-result "notes") "stderr"))))
                             (list (list (quote eval_status) "SHELL_CMD_FAILED") (list (quote message) "Test command execution failed.") (list (quote shell_error) (get-field test-run-result "content"))))))))))

  (controller (lambda (eval-feedback plan-task-result aider-task-result iter-num)
                (log-message "Controller (Iter " iter-num "): Eval feedback: " eval-feedback)
                (let ((eval-status (get-field eval-feedback "eval_status"))
                      (max-iters (get-field *loop-config* "max-iterations"))) ;; Access max-iterations
                  (if (string=? eval-status "TESTS_PASSED")
                      (list 'stop aider-task-result)
                      (if (< iter-num max-iters) ;; Check if we can retry
                          (let ((original-instructions (get-field (get-field plan-task-result "parsedContent") "instructions")))
                            (let ((feedback-message (get-field eval-feedback "message")))
                              (list 'continue (string-append original-instructions " -- Previous attempt (iteration " iter-num ") failed or tests did not pass. Feedback: " feedback-message ". Please review and try again."))))
                          (list 'stop eval-feedback))))))) ;; Max retries reached, stop with current feedback
)
"""

def run_demo(app: Application):
    """Runs the director-evaluator-loop coding demo."""
    original_cwd = os.getcwd()
    try:
        # Ensure we are in the project root for Aider operations
        # and for relative paths in the plan to make sense.
        if str(PROJECT_ROOT) != original_cwd:
            os.chdir(PROJECT_ROOT)
            logger.info(f"Changed current working directory to project root: {PROJECT_ROOT}")
        else:
            logger.info(f"Already in project root: {PROJECT_ROOT}")

        # 1. Define the user:generate-plan task
        logger.info("Defining 'user:generate-plan' S-expression task...")
        defatom_result = app.handle_task_command(
            identifier=DEFATOM_GENERATE_PLAN_S_EXPRESSION, # Pass the S-expression string directly
            params={}, # No params for defatom itself when passed as a string
            flags={"is_sexp_string": True}
        )
        logger.info(f"'user:generate-plan' definition result: {json.dumps(defatom_result, indent=2)}")
        if defatom_result.get("status") == "FAILED":
            logger.error("Failed to define 'user:generate-plan'. Aborting demo.")
            return

        # 2. Execute the main director-evaluator-loop
        logger.info("Executing main director-evaluator-loop S-expression...")
        loop_result = app.handle_task_command(
            identifier=MAIN_LOOP_S_EXPRESSION, # Pass the S-expression string directly
            params={}, # No params for the loop itself when passed as a string
            flags={"is_sexp_string": True}
        )
        logger.info("--- Director-Evaluator Loop Final Result ---")
        logger.info(json.dumps(loop_result, indent=2))
        logger.info("--------------------------------------------")

    except Exception as e:
        logger.exception(f"An error occurred during the demo: {e}")
    finally:
        os.chdir(original_cwd)
        logger.info(f"Restored current working directory to: {original_cwd}")


if __name__ == "__main__":
    # No longer need command line arguments as we're not using a temp workspace
    logger.info("Initializing Application for director_loop_coding_demo...")
    
    # Explicitly enable Aider via config for this demo
    app_config_for_demo = {
        "aider": {
            "enabled": True
        },
        # Optional: Set a default model if your demo tasks rely on a specific one
        # and you don't want to rely on PassthroughHandler's default.
        # "handler_config": {
        #     "default_model_identifier": "anthropic:claude-3-5-sonnet-latest" 
        # }
    }
    # The os.environ['AIDER_ENABLED'] = 'true' line earlier in the script is now a fallback
    # if the config method isn't implemented or the 'aider' key is missing from app_config_for_demo.

    app = Application(config=app_config_for_demo) # Pass the config

    run_demo(app)
    logger.info("Director loop coding demo finished.")
