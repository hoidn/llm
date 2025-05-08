#!/usr/bin/env python
"""
Demonstrates the iterative-loop S-expression special form.

This script orchestrates a coding task using the iterative-loop pattern:
1. Initial planning: An LLM (via user:generate-plan-from-goal task) generates a plan to create 
   Python files based on a user-provided goal.
2. Iterative execution:
   a. Executor: Aider (via aider:automatic tool) attempts to implement the current plan.
   b. Validator: A shell command (via system:execute_shell_command tool) runs tests.
   c. Controller: An LLM analysis task evaluates results and decides whether to continue with 
      a revised plan or stop (success/failure).

The iterative-loop pattern separates the initial planning from the execution-validation-analysis cycle,
allowing for more focused iterations with explicit control flow decisions.

Usage:
    python src/scripts/iterative_loop_coding_demo.py --goal "Create a simple calculator module" --test-command "python -m pytest tests/test_calculator.py -v"
"""
import argparse
import json
import logging
import os
import pathlib
import sys
from typing import Dict, Any, Optional

# Add the project root to the Python path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.main import Application
    from src.sexp_evaluator.sexp_environment import SexpEnvironment
    from src.system.models import DevelopmentPlan, ControllerAnalysisResult  # Import the models we'll use
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print(f"Ensure PROJECT_ROOT is correctly set to: {PROJECT_ROOT}")
    print(f"And that the script is run from a context where src.* modules are discoverable.")
    sys.exit(1)

# Configure logging
LOG_LEVEL = logging.INFO  # Or DEBUG for more verbosity
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Define the atomic task for generating the initial plan
DEFATOM_GENERATE_PLAN_S_EXPRESSION = """
(defatom user:generate-plan-from-goal
  (params 
    (goal str) 
    (context_string optional str)
  )
  (instructions 
    "You are a helpful AI assistant. Your task is to generate a development plan based on the user's goal.
    The plan should include:
    1. 'instructions': Detailed, step-by-step instructions for an AI coding assistant like Aider to implement the request. These instructions should be clear and actionable.
    2. 'files': A list of ALL file paths that need to be created or modified to implement the plan. These paths should be relative to the root of the current project workspace (e.g., 'src/new_module/file.py', 'tests/new_module/test_file.py').

    IMPORTANT: You MUST output ONLY a single JSON string that strictly conforms to the following Pydantic model schema:
    {
      \\"instructions\\": \\"string\\",
      \\"files\\": [\\"string\\"]
    }
    Do not add any explanatory text before or after the JSON object.
    
    User Goal: {{goal}}
    Context: {{context_string}}
    "
  )
  (model "gpt-4-turbo") ;; Or your preferred model for plan generation
  (output_format ((type "json") (schema "src.system.models.DevelopmentPlan")))
  (description "Generates a development plan (instructions, files) based on user goal.")
)
"""

# Define the atomic task for analyzing results and deciding next steps
DEFATOM_ANALYZE_REVISE_S_EXPRESSION = """
(defatom user:analyze-and-revise-plan
  (params 
    (original_goal str)
    (previous_instructions str)
    (previous_files list)
    (aider_status str)
    (aider_output str)
    (test_stdout str)
    (test_stderr str)
    (test_exit_code int)
    (iteration int)
    (max_iterations int)
  )
  (instructions 
    "You are a helpful AI assistant. Your task is to analyze the results of a coding iteration and decide on the next steps.

    You will be given:
    1. The original goal
    2. The previous instructions and file list given to the coding assistant (Aider)
    3. Aider's execution status and output
    4. The test command results (stdout, stderr, exit code)
    5. The current iteration number and maximum iterations allowed

    Based on this information, you must decide:
    
    A. If the tests passed (exit code 0) and the implementation meets the goal, choose STOP_SUCCESS.
    B. If the tests failed but we can fix the issues with a revised plan, choose CONTINUE and provide a revised plan.
    C. If the tests failed and we're approaching max iterations or the issues seem unfixable, choose STOP_FAILURE.

    IMPORTANT: You MUST output ONLY a single JSON string that strictly conforms to the following schema:
    {
      \\"decision\\": \\"CONTINUE\\" | \\"STOP_SUCCESS\\" | \\"STOP_FAILURE\\",
      \\"next_plan\\": {  // Required only if decision is CONTINUE
        \\"instructions\\": \\"string\\", // Revised instructions for Aider
        \\"files\\": [\\"string\\"]       // List of files to focus on
      },
      \\"analysis\\": \\"string\\"        // Your explanation of the decision
    }

    If your decision is CONTINUE, you MUST include a complete next_plan with revised instructions and files.
    Do not add any explanatory text before or after the JSON object.
    
    Original Goal: {{original_goal}}
    Previous Instructions: {{previous_instructions}}
    Previous Files: {{previous_files}}
    Aider Status: {{aider_status}}
    Aider Output: {{aider_output}}
    Test Stdout: {{test_stdout}}
    Test Stderr: {{test_stderr}}
    Test Exit Code: {{test_exit_code}}
    Current Iteration: {{iteration}}
    Max Iterations: {{max_iterations}}
    "
  )
  (model "gpt-4-turbo") ;; Or your preferred model for analysis
  (output_format ((type "json") (schema "src.system.models.ControllerAnalysisResult")))
  (description "Analyzes coding results and decides whether to continue with a revised plan or stop.")
)
"""

# Define the main workflow S-expression using iterative-loop
MAIN_WORKFLOW_S_EXPRESSION = """
(progn
  (log-message "Starting iterative-loop workflow for goal:" initial_user_goal)

  ;; Variables initial_plan_data, fixed_test_command, initial_user_goal, max_iterations_config
  ;; are expected to be bound in the initial environment passed from Python.

  (iterative-loop
    (max-iterations max_iterations_config)
    (initial-input initial_plan_data) ;; Pass the initial plan dict/assoc-list
    (test-command fixed_test_command) ;; Pass the fixed test command string

    ;; --- Executor Phase ---
    (executor (lambda (current-plan iter-num)
                (log-message "Executor (Iter " iter-num "): Executing plan...")
                (aider_automatic
                  (prompt (get-field current-plan "instructions"))
                  (file_context (get-field current-plan "files")))))

    ;; --- Validator Phase ---
    (validator (lambda (test-cmd iter-num)
                 (log-message "Validator (Iter " iter-num "): Running command:" test-cmd)
                 (let ((test-task-result (system_execute_shell_command (command test-cmd))))
                   (log-message "Validator: Shell command TaskResult:" test-task-result)
                   ;; Construct ValidationResult association list
                   (let ((notes (get-field test-task-result "notes")))
                     (list
                       (list 'stdout (get-field notes "stdout"))
                       (list 'stderr (get-field notes "stderr"))
                       (list 'exit_code (get-field notes "exit_code"))
                       (list 'error (if (string=? (get-field test-task-result "status") "FAILED")
                                        (get-field test-task-result "content")
                                        nil)))))))

    ;; --- Controller Phase ---
    (controller (lambda (aider-result validation-result current-plan iter-num)
                  (log-message "Controller (Iter " iter-num "): Analyzing Aider result:" (get-field aider-result "status") " and Validation result exit_code:" (get-field validation-result "exit_code"))
                  ;; Call the analysis/revision LLM task
                  (let ((analysis-task-result
                         (user:analyze-and-revise-plan
                           (original_goal initial_user_goal) ;; From outer env
                           (previous_instructions (get-field current-plan "instructions"))
                           (previous_files (get-field current-plan "files"))
                           (aider_status (get-field aider-result "status"))
                           (aider_output (get-field aider-result "content"))
                           (test_stdout (get-field validation-result "stdout"))
                           (test_stderr (get-field validation-result "stderr"))
                           (test_exit_code (get-field validation-result "exit_code"))
                           (iteration iter-num)
                           (max_iterations max_iterations_config) ;; From outer env
                          )))
                    (log-message "Controller: Analysis TaskResult:" analysis-task-result)

                    ;; Process analysis result
                    (if (string=? (get-field analysis-task-result "status") "FAILED")
                        (list 'stop analysis-task-result) ;; Stop if analysis task itself failed
                        (let ((analysis-data (get-field analysis-task-result "parsedContent"))) ;; Expects ControllerAnalysisResult dict
                          (if (null? analysis-data)
                              (progn
                                (log-message "Controller: Failed to parse analysis task result!")
                                (list 'stop analysis-task-result)) ;; Stop if parsing failed
                              (let ((decision (get-field analysis-data "decision")))
                                (log-message "Controller: Analysis Decision:" decision)
                                (if (string=? decision "CONTINUE")
                                    (list 'continue (get-field analysis-data "next_plan"))
                                    (if (string=? decision "STOP_SUCCESS")
                                        (list 'stop aider-result) ;; Stop successfully with Aider's result
                                        ;; Decision is STOP_FAILURE or unexpected
                                        (list 'stop analysis-task-result) ;; Stop with the analysis result explaining why
                                    )))))))))
    ) ;; End iterative-loop
) ;; End progn
"""

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run the iterative-loop coding demo.")
    parser.add_argument("--goal", type=str, required=True,
                        help="The goal for the coding task (e.g., 'Create a simple calculator module').")
    parser.add_argument("--context-file", type=str, default=None,
                        help="Optional path to a file containing additional context for the planning task.")
    parser.add_argument("--test-command", type=str, required=True,
                        help="The shell command to run for testing the implementation.")
    parser.add_argument("--max-iterations", type=int, default=3,
                        help="Maximum number of iterations to attempt (default: 3).")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging.")
    return parser.parse_args()

def load_context_file(file_path: Optional[str]) -> str:
    """Load context from a file if provided, otherwise return empty string."""
    if not file_path:
        return "Operating in temporary workspace."
    
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except Exception as e:
        logger.warning(f"Failed to read context file {file_path}: {e}")
        return "Failed to load context file. Operating in temporary workspace."

def run_demo(app: Application, args: argparse.Namespace):
    """Runs the iterative-loop coding demo."""
    original_cwd = os.getcwd()
    try:
        # Ensure we are in the project root for Aider operations
        # and for relative paths in the plan to make sense.
        if str(PROJECT_ROOT) != original_cwd:
            os.chdir(PROJECT_ROOT)
            logger.info(f"Changed current working directory to project root: {PROJECT_ROOT}")
        else:
            logger.info(f"Already in project root: {PROJECT_ROOT}")

        # Load initial context if provided
        initial_context_data = load_context_file(args.context_file)
        
        # 1. Define the atomic tasks
        logger.info("Defining 'user:generate-plan-from-goal' S-expression task...")
        defatom_result = app.handle_task_command(
            identifier=DEFATOM_GENERATE_PLAN_S_EXPRESSION,
            params={},
            flags={"is_sexp_string": True}
        )
        logger.info(f"'user:generate-plan-from-goal' definition result: {json.dumps(defatom_result, indent=2)}")
        if defatom_result.get("status") == "FAILED":
            logger.error("Failed to define 'user:generate-plan-from-goal'. Aborting demo.")
            return

        logger.info("Defining 'user:analyze-and-revise-plan' S-expression task...")
        defatom_result = app.handle_task_command(
            identifier=DEFATOM_ANALYZE_REVISE_S_EXPRESSION,
            params={},
            flags={"is_sexp_string": True}
        )
        logger.info(f"'user:analyze-and-revise-plan' definition result: {json.dumps(defatom_result, indent=2)}")
        if defatom_result.get("status") == "FAILED":
            logger.error("Failed to define 'user:analyze-and-revise-plan'. Aborting demo.")
            return

        # 2. Generate the initial plan
        logger.info(f"Generating initial plan for goal: {args.goal}")
        initial_plan_params = {
            "goal": args.goal,
            "context_string": initial_context_data
        }
        initial_plan_result = app.handle_task_command(
            identifier="user:generate-plan-from-goal",
            params=initial_plan_params
        )
        logger.info(f"Initial plan generation result: {json.dumps(initial_plan_result, indent=2)}")
        
        if initial_plan_result.get("status") == "FAILED":
            logger.error("Failed to generate initial plan. Aborting demo.")
            return
        
        # Extract the parsed plan data
        initial_plan_data = initial_plan_result.get("parsedContent")
        if not initial_plan_data:
            logger.error("Failed to parse initial plan result. Aborting demo.")
            return
        
        logger.info(f"Initial plan generated successfully:")
        logger.info(f"  - Instructions: {initial_plan_data.get('instructions', '')[:100]}...")
        logger.info(f"  - Files: {initial_plan_data.get('files', [])}")
        
        # 3. Create environment for the iterative-loop S-expression
        env_bindings = {
            "initial_plan_data": initial_plan_data,
            "fixed_test_command": args.test_command,
            "initial_user_goal": args.goal,
            "max_iterations_config": args.max_iterations
        }
        
        # 4. Execute the main workflow
        logger.info("Executing main iterative-loop S-expression workflow...")
        loop_result = app.handle_task_command(
            identifier=MAIN_WORKFLOW_S_EXPRESSION,
            params={},
            flags={"is_sexp_string": True, "initial_env": env_bindings}
        )
        
        # 5. Process and display results
        logger.info("--- Iterative-Loop Final Result ---")
        logger.info(json.dumps(loop_result, indent=2))
        
        # Interpret the result based on its structure
        if loop_result.get("status") == "COMPLETE":
            if "parsedContent" in loop_result and isinstance(loop_result["parsedContent"], dict):
                # If the result contains a parsed ControllerAnalysisResult
                if "decision" in loop_result["parsedContent"]:
                    decision = loop_result["parsedContent"]["decision"]
                    analysis = loop_result["parsedContent"].get("analysis", "No analysis provided")
                    logger.info(f"Workflow completed with decision: {decision}")
                    logger.info(f"Analysis: {analysis}")
                else:
                    # If it's the Aider result (from STOP_SUCCESS)
                    logger.info("Workflow completed successfully with Aider's implementation.")
            else:
                logger.info("Workflow completed, but result structure is not as expected.")
        else:
            logger.error(f"Workflow failed with status: {loop_result.get('status')}")
            if "notes" in loop_result and "error" in loop_result["notes"]:
                logger.error(f"Error: {loop_result['notes']['error']}")
        
        logger.info("--------------------------------------------")

    except Exception as e:
        logger.exception(f"An error occurred during the demo: {e}")
    finally:
        os.chdir(original_cwd)
        logger.info(f"Restored current working directory to: {original_cwd}")

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    logger.info("Initializing Application for iterative_loop_coding_demo...")
    
    # Explicitly enable Aider via config for this demo
    app_config_for_demo = {
        "aider": {
            "enabled": True
        },
        # Optional: Set a default model if your demo tasks rely on a specific one
        # "handler_config": {
        #     "default_model_identifier": "anthropic:claude-3-5-sonnet-latest" 
        # }
    }

    app = Application(config=app_config_for_demo)

    run_demo(app, args)
    logger.info("Iterative loop coding demo finished.")
