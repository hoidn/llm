#!/usr/bin/env python
"""
Demonstrates an S-expression workflow where an LLM task is expected
to fetch context dynamically using the 'system:get_context' tool.

Usage:
    python src/scripts/context_fetching_demo.py --query "What components handle LLM interaction?" [--repo PATH/TO/REPO]
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
try:
    from src.main import Application
    from src.sexp_evaluator.sexp_environment import SexpEnvironment
    from src.system.models import TaskResult # For type hints
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print(f"PROJECT_ROOT calculated as: {PROJECT_ROOT}")
    print(f"SRC_PATH calculated as: {PROJECT_ROOT / 'src'}")
    print(f"Current sys.path: {sys.path}")
    print("Please ensure the project structure is correct, dependencies are installed,")
    print("and you are running this script from the project root directory.")
    sys.exit(1)

# --- Logging Setup ---
LOG_LEVEL = logging.INFO # Or DEBUG
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger().setLevel(LOG_LEVEL)
logger = logging.getLogger("ContextFetchingDemo")

# --- S-expression Definitions ---

# 1. Defatom for a task that SHOULD call get_context
DEFATOM_PROCESS_QUERY_S_EXPRESSION = """
(defatom user:process-query-with-context
  (params (user_query string)) ;; Parameter for the initial query
  (instructions
    "You are an AI assistant. Your goal is to find relevant files for the user's query: '{{user_query}}'.
    To do this, you MUST use the available 'system_get_context' tool.
    Invoke the tool like this: (system_get_context (query \\"{{user_query}}\\")).
    Your FINAL response should be ONLY the list of file paths returned by the 'system_get_context' tool.
    Do not add any explanation or introductory text. Just output the result from the tool."
  )
  (description "Processes a query by first calling system:get_context to find relevant files.")
  ;; (model "...") ; Optionally specify a model known to be good at tool use
)
"""

# 2. Main workflow that calls the above task
MAIN_WORKFLOW_S_EXPRESSION = """
(progn
  (log-message "Context Fetching Demo: Starting main workflow.")
  ;; 'initial_user_query' is expected to be bound in the environment
  (user:process-query-with-context (user_query initial_user_query))
)
"""

# --- Main Demo Logic ---

def run_demo(query: str, repo_path: str):
    """Runs the context fetching demo."""
    logger.info(f"Starting Context Fetching Demo with query: '{query}'")
    logger.info(f"Using repository path: {repo_path}")

    app: Application | None = None

    try:
        # 1. Instantiate Application
        # Ensure Aider is disabled if not needed, ensure system tools are registered
        app_config = { "aider": { "enabled": False } }
        app = Application(config=app_config)
        logger.info("Application instantiated.")

        # 2. Index Repository (CRUCIAL for get_context to work)
        logger.info(f"Indexing repository: {repo_path}")
        index_options = {
             "include_patterns": ["src/**/*.py", "*.py", "*.md"],
             "exclude_patterns": ["**/venv/**", "**/.*/**", "**/__pycache__/**"]
        }
        success = app.index_repository(repo_path, options=index_options)
        if not success:
            logger.error("Repository indexing failed. 'system:get_context' will likely find no files. Exiting.")
            return
        logger.info("Repository indexing complete.")

        # 3. Define the LLM Task via defatom
        logger.info("Defining 'user:process-query-with-context' task...")
        def_result = app.handle_task_command(DEFATOM_PROCESS_QUERY_S_EXPRESSION)
        if def_result.get("status") == "FAILED":
            logger.error(f"Failed to define task: {def_result.get('content')}")
            return
        logger.info("Task defined successfully.")

        # 4. Prepare Environment for Main Workflow
        initial_env = SexpEnvironment(bindings={
            "initial_user_query": query
        })
        logger.debug(f"Initial environment prepared with query: '{query}'")

        # 5. Execute Main Workflow
        logger.info("Executing main S-expression workflow...")
        final_result = app.handle_task_command(
            identifier=MAIN_WORKFLOW_S_EXPRESSION,
            params={}, # Params are passed via environment binding
            flags={"is_sexp_string": True, "initial_env": initial_env} # Pass the env
        )
        logger.info("Main workflow execution finished.")

        # 6. Print Final Result
        print("\n" + "="*20 + " Workflow Final Result " + "="*20)
        try:
            print(json.dumps(final_result, indent=2))
            if final_result.get("status") == "COMPLETE":
                print("\n--- Interpretation ---")
                print("The workflow completed. The 'content' field should contain the list")
                print("of files returned by the 'system:get_context' tool, which was invoked")
                print("by the 'user:process-query-with-context' LLM task.")
                print(f"Files found for query '{query}':")
                try:
                    # Content might be a JSON string list, try parsing
                    files = json.loads(final_result.get("content", "[]"))
                    if isinstance(files, list):
                        for f in files:
                            print(f" - {f}")
                    else:
                        print(f"  (Content was not a list: {final_result.get('content')})")
                except json.JSONDecodeError:
                     print(f"  (Content was not valid JSON: {final_result.get('content')})")

            else:
                print("\n--- Workflow Execution Failed ---")
                print(f"Status: {final_result.get('status')}")
                print(f"Content: {final_result.get('content')}")
                if 'error' in final_result.get('notes', {}):
                    print(f"Error Details: {final_result['notes']['error']}")

        except Exception as e:
            logger.error(f"Error formatting/printing final result: {e}")
            print("\nRaw Final Result:")
            print(final_result)
        print("="*53)

    except Exception as e:
        logger.exception(f"An unexpected error occurred during the demo: {e}")
        print(f"\nFATAL ERROR: {e}")

# --- Argument Parsing and Script Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Demo: LLM task calling system:get_context.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--query",
        required=True,
        help="The query to pass to the LLM task (e.g., 'What handles LLM calls?')."
    )
    parser.add_argument(
        "--repo",
        default=str(PROJECT_ROOT), # Default to the project root
        help="Path to the root of the Git repository to index."
    )
    args = parser.parse_args()

    # Validate repo path
    if not os.path.isdir(args.repo):
        print(f"ERROR: Provided repository path is not a valid directory: {args.repo}")
        sys.exit(1)

    run_demo(query=args.query, repo_path=args.repo)
