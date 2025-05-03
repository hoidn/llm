#!/usr/bin/env python3

"""
Enhanced Interactive Demo for Aider Integration.

Allows interactive prompts, specification of file context, and model overrides
for the 'aider:automatic' tool via the Application layer.

Prerequisites:
1.  Set environment variable: `export AIDER_ENABLED=true` (or equivalent).
2.  Ensure the Aider MCP Server is running and configured (e.g., via env vars
    like MCP_STDIO_COMMAND used by the Application/AiderBridge).
3.  Run this script from the project's root directory.
"""

import os
import sys
import json
import logging
import argparse
import readline # For better input history
from typing import Optional, List, Dict, Any

# --- Setup Project Path ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')

if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
    print(f"[Setup] Added {SRC_PATH} to sys.path")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(1, PROJECT_ROOT)
    print(f"[Setup] Added {PROJECT_ROOT} to sys.path")

# --- Import Application ---
try:
    from src.main import Application
    from src.system.models import TaskResult # For type hints
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print(f"PROJECT_ROOT calculated as: {PROJECT_ROOT}")
    print(f"SRC_PATH calculated as: {SRC_PATH}")
    print(f"Current sys.path: {sys.path}")
    print("Please ensure the project structure is correct, dependencies are installed,")
    print("and you are running this script from the project root directory.")
    sys.exit(1)
except Exception as e:
    print(f"An unexpected error occurred during import: {e}")
    sys.exit(1)

# --- Constants ---
AIDER_TOOL_ID = "aider:automatic"

# --- Logging Setup ---
LOG_LEVEL = logging.INFO # Default to INFO, can be overridden if needed
logging.basicConfig(level=LOG_LEVEL,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("mcp").setLevel(logging.INFO)
logger = logging.getLogger("EnhancedAiderDemo")

# --- Helper Functions ---
def print_help():
    """Prints help messages for the interactive prompt."""
    print("\n--- Demo Help ---")
    print("Enter a coding prompt for Aider.")
    print("You will be asked for optional files to include in the context.")
    print("You can also specify an Aider model override for the request.")
    print("Commands:")
    print("  /help     - Show this help message.")
    print("  /quit     - Exit the demo.")
    print("  /exit     - Exit the demo.")
    print("-" * 17)

def parse_file_list(input_str: str) -> list[str]:
    """Parses a comma-separated string into a list of stripped filenames."""
    if not input_str.strip():
        return []
    return [f.strip() for f in input_str.split(',') if f.strip()]

# --- Main Demo Logic ---
def run_interactive_demo(repo_path: str, default_model: Optional[str] = None):
    """Runs the enhanced interactive Aider demo."""

    print("--- Enhanced Aider Interactive Demo ---")
    print(f"Target Repository: {repo_path}")
    if default_model:
        print(f"Default Aider Model: {default_model}")
    print("\nPrerequisites:")
    print("1. Ensure `AIDER_ENABLED=true` environment variable is set.")
    print("2. Ensure the Aider MCP Server is configured and running.")
    print(f"3. Ensure the target repository '{repo_path}' is a valid Git repo.")
    print("-" * 37)

    # Force set the environment variable in the current process
    os.environ['AIDER_ENABLED'] = 'true'
    logger.info("Ensuring AIDER_ENABLED=true is set in process environment")

    if not os.path.isdir(repo_path) or not os.path.isdir(os.path.join(repo_path, ".git")):
        logger.error(f"Provided repository path is not a valid Git repository: {repo_path}")
        print(f"\nERROR: Path '{repo_path}' is not a valid Git repository root. Exiting.")
        return

    app: Application | None = None

    try:
        # 1. Instantiate Application
        logger.info("Instantiating Application...")
        # Pass config with explicit AIDER_ENABLED to ensure it's recognized
        app_config = {
            "aider": {
                "enabled": True  # Force enable Aider regardless of environment variable
            }
        }
        logger.info("Explicitly enabling Aider in application config")
        app = Application(config=app_config)
        logger.info("Application instantiated successfully.")

        # 2. Index Repository
        logger.info(f"Indexing repository: {repo_path}")
        print(f"\nIndexing repository '{os.path.basename(repo_path)}'. This might take a moment...")
        # More targeted indexing for potentially faster startup
        index_options = {
            "include_patterns": ["src/**/*.py", "*.py", "*.md", "pyproject.toml", "README.md"],
             "exclude_patterns": [
                    "**/venv/**", "**/.*/**", "**/__pycache__/**",
                    "**/node_modules/**", "*.pyc", "*.log", "tests/**", # Exclude tests?
                 ]
        }
        success = app.index_repository(repo_path, options=index_options)
        if not success:
            logger.warning("Failed to index repository. Aider might lack context.")
            print("WARNING: Failed to fully index repository. Aider might lack necessary context.")
        else:
            logger.info("Repository indexing complete.")
            print("Repository indexing complete.")

        # 3. Interactive Loop
        print("\nEnter your coding prompt for Aider. Type /help for commands.")
        print("-" * 60)

        while True:
            try:
                prompt = input("Aider Prompt [/help, /quit]> ")
            except EOFError:
                print("\nExiting.")
                break

            if prompt.lower() in ['/quit', '/exit']:
                print("Exiting.")
                break
            if prompt.lower() == '/help':
                print_help()
                continue
            if not prompt.strip():
                continue

            # Get optional file context
            file_context_input = input("Files (comma-separated, relative to repo root, optional)> ")
            relative_files = parse_file_list(file_context_input)
            file_context_json = json.dumps(relative_files) if relative_files else None

            # Get optional model override
            model_override_input = input(f"Aider Model [Enter for default: {default_model or 'Server Default'}]> ")
            model_override = model_override_input.strip() or default_model # Use arg default if provided

            # 4. Prepare Task Command
            identifier = AIDER_TOOL_ID
            params = {"prompt": prompt}
            if file_context_json:
                params["file_context"] = file_context_json # Pass as JSON string
                logger.info(f"Including file context: {relative_files}")
            if model_override:
                params["model"] = model_override
                logger.info(f"Using model override: {model_override}")
            else:
                 logger.info("Using default Aider model.")

            # 5. Call handle_task_command
            logger.info(f"Calling handle_task_command for '{identifier}'...")
            print("\nSending request to Aider via Application layer...")
            print("-" * 20)
            try:
                # Ensure handle_task_command is called correctly
                # It should internally handle async calls if needed
                result_dict = app.handle_task_command(identifier, params)
                logger.info("Aider task command finished.")
            except Exception as e:
                logger.exception("Error executing Aider task command.")
                print(f"\nERROR: An unexpected error occurred during execution: {e}")
                print("-" * 60)
                continue # Continue to next prompt

            # 6. Display Result
            print("\n--- Aider Result ---")
            try:
                status = result_dict.get("status", "UNKNOWN")
                content = result_dict.get("content", "")
                notes = result_dict.get("notes", {})
                error_details = notes.get("error")

                print(f"Status: {status}")

                if status == "COMPLETE":
                    aider_success = notes.get("success", False)
                    if aider_success:
                        print("Aider Execution: Successful")
                        print("\nDiff / Output:")
                        print("-" * 15)
                        print(content if content else "[No diff/output generated by Aider]")
                        print("-" * 15)
                    else:
                        print("Aider Execution: Failed (Reported by tool)")
                        print("\nError / Output:")
                        print("-" * 15)
                        print(content if content else "[No specific error message provided by tool]")
                        print("-" * 15)
                elif status == "FAILED":
                    print("Aider Execution: Failed (System Level)")
                    print("\nError Message:")
                    print(content)
                    if error_details:
                        print("\nError Details (from notes):")
                        # Attempt to pretty print if it's a dictionary
                        if isinstance(error_details, dict):
                            print(json.dumps(error_details, indent=2))
                        else:
                            print(error_details) # Print as is otherwise
                else:
                    print(f"Aider Execution: Status '{status}'")
                    print("\nContent:")
                    print(content)

            except Exception as e:
                logger.error(f"Error displaying result: {e}")
                print(f"\nERROR: Could not process result dictionary: {e}")
                print("Raw Result:", result_dict)
            print("-" * 60) # Separator for next prompt

    except Exception as e:
        logger.exception("An error occurred during demo setup.")
        print(f"\nFATAL ERROR during setup: {e}")
    finally:
        logger.info("Enhanced interactive Aider demo finished.")
        print("\nDemo finished.")


# --- Argument Parsing and Script Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Interactive Demo for Aider Integration.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=PROJECT_ROOT,
        help="Path to the root of the Git repository to index and work within."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Optional: Default Aider model identifier to suggest/use."
    )
    args = parser.parse_args()

    # Set AIDER_ENABLED in the current process environment
    # This ensures it's available for any subprocess or module that checks it
    os.environ['AIDER_ENABLED'] = 'true'
    logger.info("Setting AIDER_ENABLED=true in process environment")
    
    # Run the demo (we've already set the environment variable)
    run_interactive_demo(repo_path=args.repo, default_model=args.model)
