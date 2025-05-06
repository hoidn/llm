#!/usr/bin/env python
"""
Demonstrates S-expression lambda functions orchestrating a mock LLM-driven
code processing workflow.

This script showcases:
- Defining mock LLM atomic tasks using `(defatom ...)` for code analysis,
  refactoring, and optimization.
- Using a lambda function within an S-expression to dynamically choose
  and invoke a specialized LLM task based on the output of an initial
  analysis task.
- Placeholder S-expression primitives `(get-field ...)` to extract data
  from TaskResult dictionaries and `(string=? ...)` for comparison.
- Use of `(log-message ...)` for S-expression level logging.
"""

import os
os.environ['AIDER_ENABLED'] = 'true' # SET THIS VERY EARLY
import logging
import sys
from typing import Any, Dict, Optional

# --- Path Setup ---
# Add the project root to the Python path to allow importing from src
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

# --- Application Imports ---
from src.main import Application # Assuming Application is in src.main
from src.system.models import TaskResult # For type hinting and checking

# --- Logging Setup ---
LOG_LEVEL = logging.DEBUG
# Configure basic logging
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Optionally, set specific log levels for noisy modules if needed
# logging.getLogger("src.some_module").setLevel(logging.INFO)
logging.getLogger().setLevel(LOG_LEVEL)
logger = logging.getLogger(__name__) # Logger for this script


def execute_and_print(
    app_instance: Application,
    title: str,
    sexp_string: str,
    expected_content_substring: Optional[str] = None
) -> Dict[str, Any]:
    """
    Helper function to execute an S-expression string via the Application
    and print the results.
    """
    logger.info(f"\n--- {title} ---")
    logger.info(f"Executing S-expression:\n{sexp_string}")

    try:
        # S-expressions should be handled as task commands
        result_dict = app_instance.handle_task_command(identifier=sexp_string, params={})
        
        logger.info("S-expression raw result (dictionary):")
        # Basic print for readability, could use pprint for complex dicts
        for key, value in result_dict.items():
            if key == "notes" and isinstance(value, dict):
                logger.info(f"  {key}:")
                for n_key, n_value in value.items():
                    logger.info(f"    {n_key}: {n_value}")
            else:
                logger.info(f"  {key}: {value}")

        # Validate TaskResult structure and expected content
        if not isinstance(result_dict, dict) or "status" not in result_dict:
            logger.error("Execution did not return a valid TaskResult-like dictionary.")
            return result_dict # Or raise an error

        if result_dict["status"] == "FAILED":
            logger.error(f"S-expression execution FAILED. Error details: {result_dict.get('notes', {}).get('error')}")
        elif expected_content_substring:
            content = result_dict.get("content", "")
            if isinstance(content, str) and expected_content_substring in content:
                logger.info(f"SUCCESS: Expected substring '{expected_content_substring}' found in content.")
            else:
                logger.error(f"FAILURE: Expected substring '{expected_content_substring}' NOT found in content: '{content}'")
        else:
            logger.info(f"S-expression execution COMPLETED with status: {result_dict['status']}")
            
        return result_dict

    except Exception as e:
        logger.exception(f"An error occurred during S-expression execution for '{title}': {e}")
        # Return a mock error TaskResult for consistency if needed by caller
        return {
            "status": "FAILED",
            "content": f"Python exception: {e}",
            "notes": {"error": {"type": "PYTHON_EXCEPTION", "message": str(e)}}
        }


def run_code_processing_demo():
    """
    Main function to run the lambda and LLM code processing demo.
    """
    logger.info("Starting Lambda & LLM Code Processing Demo...")

    try:
        app = Application()
        logger.info("Application instantiated successfully.")
    except Exception as e:
        logger.exception(f"Failed to instantiate Application: {e}. Demo cannot continue.")
        return

    # 1. Define Mock LLM Tasks using (defatom ...)
    # These tasks have instructions designed for predictable string output for the demo.
    define_tasks_sexp = """
    (progn
      (defatom code-analyzer-llm
        (params (code-snippet))
        (instructions "LLM, analyze the following code snippet: '{{code-snippet}}'. Based on the analysis, if the code contains the word 'complex' or 'loop', output the STRING 'refactoring_needed'. Otherwise, output the STRING 'optimization_candidate'.")
        (description "Analyzes code and suggests 'refactoring_needed' or 'optimization_candidate'.")
      )

      (defatom refactor-code-llm
        (params (code-snippet))
        (instructions "Output exactly: Refactored Code: {{code-snippet}} - now with more clarity!")
        (description "Refactors code for clarity.")
      )

      (defatom optimize-code-llm
        (params (code-snippet))
        (instructions "Output exactly: Optimized Code: {{code-snippet}} - now runs faster!")
        (description "Optimizes code for performance.")
      )
      (quote tasks_defined_successfully) ; Return a symbol to confirm execution
    )
    """
    execute_and_print(app, "Defining Mock LLM Tasks via S-expression", define_tasks_sexp, "tasks_defined_successfully")

    # 2. Demo Case: LLM-Driven Dynamic Code Processing Path
    title_main_demo = "LLM-Driven Dynamic Code Processing Path"
    
    # Two sample code snippets for different outcomes from code-analyzer-llm
    code_sample_for_refactor = "def complex_function_with_loop(data_list):\\n  temp = []\\n  for i in range(len(data_list)):\\n    if data_list[i] > 10:\\n      res = data_list[i] * data_list[i] + 5\\n      temp.append(res)\\n  return temp"
    code_sample_for_optimize = "def simple_calc(a, b): return a + b" # Does not contain 'complex' or 'loop'

    # S-expression workflow template
    # This workflow uses a lambda to dynamically choose the processing function.
    sexp_workflow_template = """
    (let ((code-to-process "{code_snippet_placeholder}"))
      (log-message "Starting code processing for snippet:" code-to-process)

      (let ((analysis-result (code-analyzer-llm (code-snippet code-to-process))))
        ; analysis-result is a TaskResult-like dictionary.
        ; Its "content" field should hold "refactoring_needed" or "optimization_candidate".
        (log-message "Analysis task raw result:" analysis-result)

        (let ((analysis-decision (get-field analysis-result "content"))) 
          (log-message "Code Analyzer Decision (extracted via get-field):" analysis-decision)

          (if (string=? analysis-decision "refactoring_needed")
              (let ((refactor-fn (lambda (code) 
                                   (log-message "Lambda: Invoking refactor-code-llm for:" code)
                                   (refactor-code-llm (code-snippet code)))))
                (refactor-fn code-to-process))
              
              (if (string=? analysis-decision "optimization_candidate")
                  (let ((optimize-fn (lambda (code) 
                                     (log-message "Lambda: Invoking optimize-code-llm for:" code)
                                     (optimize-code-llm (code-snippet code)))))
                    (optimize-fn code-to-process))
                  
                  (progn
                    (log-message "Unknown analysis decision:" analysis-decision)
                    (quote unknown_decision_path_taken))))
          )
        )
      )
    """

    # Execute for refactoring case
    logger.info("\n" + "="*30 + " EXECUTING WORKFLOW FOR REFACTORING CASE " + "="*30)
    # Replace placeholder with escaped code snippet
    sexp_refactor_case = sexp_workflow_template.format(
        code_snippet_placeholder=code_sample_for_refactor.replace("\n", "\\n").replace("\"", "\\\"")
    )
    execute_and_print(app, title_main_demo + " (Refactor Path)", sexp_refactor_case, "Refactored Code:")

    # Execute for optimization case
    logger.info("\n" + "="*30 + " EXECUTING WORKFLOW FOR OPTIMIZATION CASE " + "="*30)
    sexp_optimize_case = sexp_workflow_template.format(
        code_snippet_placeholder=code_sample_for_optimize.replace("\n", "\\n").replace("\"", "\\\"")
    )
    execute_and_print(app, title_main_demo + " (Optimize Path)", sexp_optimize_case, "Optimized Code:")

    logger.info("\nLambda & LLM Code Processing Demo finished.")


if __name__ == "__main__":
    run_code_processing_demo()
