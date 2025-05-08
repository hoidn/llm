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
  (model "google-gla:gemini-2.0-flash") ;; Explicitly set the model to use
)
"""

# REVISED S-expression for the main DEEC loop workflow
MAIN_WORKFLOW_S_EXPRESSION = """
(progn
  (log-message "Starting iterative-loop workflow for goal:" initial-user-goal) ;; Use hyphenated symbol
  (log-message "Using Test Command:" fixed-test-command) ;; Use hyphenated symbol

  ;; Variables initial_plan_data, fixed_test_command, initial_user_goal, max_iterations_config
  ;; are expected to be bound in the initial environment passed from Python (using hyphens).

  (iterative-loop
    (max-iterations max-iterations-config) ;; Use hyphenated symbol
    (initial-input initial-plan-data) ;; Pass the initial plan dict/assoc-list
    (test-command fixed-test-command) ;; Use hyphenated symbol

    ;; --- Executor Phase ---
    (executor (lambda (current-plan iter-num)
                (log-message "Executor (Iter " iter-num "): Executing plan with instructions: " (get-field current-plan "instructions"))
                (aider_automatic
                  (prompt (get-field current-plan "instructions"))
                  (file_context (get-field current-plan "files")))))

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
                         nil ;; <<< CORRECTED 'if': Added nil else branch
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
    (controller (lambda (aider_result validation_result current_plan iter_num)
                  (log-message "Controller (Iter " iter-num "): Analyzing Aider result status:" (get-field aider_result "status") " and Validation result exit_code:" (get-field validation_result "exit_code"))
                  ;; Call the analysis/revision LLM task
                  (let ((analysis_task_result
                         (user:evaluate-and-retry-analysis ;; Corrected task name
                           (original_goal initial-user-goal) ;; Use hyphenated symbol
                           (previous_instructions (get-field current-plan "instructions"))
                           (previous_files (get-field current-plan "files"))
                           (aider_status (get-field aider_result "status"))
                           (aider_output (get-field aider_result "content")) ;; Pass Aider's content/diff/error
                           (test_stdout (get-field validation_result "stdout"))
                           (test_stderr (get-field validation_result "stderr"))
                           (test_exit_code (get-field validation_result "exit_code"))
                           (iteration iter_num)
                           (max_iterations max-iterations-config) ;; Use hyphenated symbol
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
                              (let ((decision (get-field analysis_data "decision")))
                                (log-message "Controller: Analysis Decision:" decision)
                                (if (string=? decision "CONTINUE")
                                    (list 'continue (get-field analysis_data "next_plan"))
                                    (if (string=? decision "STOP_SUCCESS")
                                        (list 'stop aider_result) ;; Stop successfully with Aider's result
                                        ;; Decision is STOP_FAILURE or unexpected
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
    parser.add_argument("--trace-sexp", action="store_true", help="Enable detailed S-expression evaluation tracing.")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3, # Default to 3 retries
        help="Maximum number of retry iterations for the coding loop."
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers:
            handler.setLevel(logging.DEBUG)
        logger.info("Debug logging enabled.")
        
        # Set environment variable for additional debug info
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

    # --- Instantiate Application ---
    try:
        # Ensure Aider is enabled if needed by the workflow
        os.environ['AIDER_ENABLED'] = 'true'
        
        logger.info("Initializing Application for coding workflow...")
        
        # Explicitly enable Aider via config and set model
        app_config = {
            "aider": {"enabled": True},
            "handler_config": {
                "default_model_identifier": "google-gla:gemini-2.0-flash"
            }
        }
        
        logger.debug(f"Application config: {json.dumps(app_config, indent=2)}")
        
        # Initialize the application with our config
        app = Application(config=app_config)
        
        # Verify the model configuration was applied
        if hasattr(app, 'passthrough_handler') and app.passthrough_handler:
            model_id = app.passthrough_handler.get_provider_identifier()
            logger.info(f"Using LLM provider: {model_id}")
            
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
        "initial-user-goal": initial_user_goal, # Use hyphenated key
        "initial-context-data": initial_context_data, # Keep hyphenated key
        "fixed-test-command": user_test_command, # Use hyphenated key to match Sexp
        "max-iterations-config": args.max_retries, # Use hyphenated key
        "initial-plan-data": {} # Add empty dict as placeholder for initial plan data
    }
    logger.debug(f"Initial parameters for workflow execution: {initial_params}")

    # --- Execute Main Workflow ---
    logger.info("Executing main workflow S-expression...")
    try:
        # Use the main workflow string defined earlier
        flags = {
            "is_sexp_string": True,
            "trace_sexp": args.trace_sexp  # Add tracing flag if requested
        }
            
        final_result = app.handle_task_command(
            identifier=MAIN_WORKFLOW_S_EXPRESSION,
            params=initial_params, # Pass the dictionary here
            flags=flags
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
