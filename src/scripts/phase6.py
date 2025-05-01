#!/usr/bin/env python3

import os
import sys
import json
import logging
import shutil # For removing directory if needed

# --- Setup Project Path ---
# Calculate paths relative to the script's location (src/scripts/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Project root is two levels up from the script's directory (src/scripts -> src -> PROJECT_ROOT)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
# Source directory is one level down from the project root
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')

# Add SRC_PATH to sys.path FIRST to prioritize imports from src
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
    print(f"DEBUG: Added {SRC_PATH} to sys.path") # Optional debug print

# Add PROJECT_ROOT to sys.path. This might be needed if some imports
# within src are relative to the project root (e.g., from src.some_module import ...)
# although absolute imports from src (from handler import ...) should work with just SRC_PATH.
# Adding PROJECT_ROOT can sometimes help resolve complex import scenarios.
if PROJECT_ROOT not in sys.path:
    sys.path.insert(1, PROJECT_ROOT) # Insert after SRC_PATH
    print(f"DEBUG: Added {PROJECT_ROOT} to sys.path") # Optional debug print

# --- Import Application ---
# Now the import should work correctly
try:
    from main import Application
    # Import specific models needed for type hints or checks if necessary
    from system.models import TaskResult
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print(f"PROJECT_ROOT calculated as: {PROJECT_ROOT}")
    print(f"SRC_PATH calculated as: {SRC_PATH}")
    print(f"Current sys.path: {sys.path}")
    print("Please ensure the project structure is correct and dependencies are installed.")
    sys.exit(1)

# --- Configuration ---
LOG_LEVEL = logging.DEBUG # Change to logging.DEBUG for more verbose output
SAMPLE_REPO_PATH = os.path.join(PROJECT_ROOT, "demo_sample_repo")
# Keyword used in the S-expression query and placed in sample files
SEARCH_KEYWORD = "class"

# --- Logging Setup ---
logging.basicConfig(level=LOG_LEVEL,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger("DemoScript")
print(f"##### Root logger effective level: {logging.getLogger().getEffectiveLevel()} (DEBUG={logging.DEBUG}, INFO={logging.INFO}) #####") # Added diagnostic print

# --- Helper Functions ---
def create_sample_repo(repo_path: str):
    """Creates a dummy repo with sample files if it doesn't exist."""
    logger.info(f"Checking/Creating sample repository at: {repo_path}")
    git_dir = os.path.join(repo_path, ".git")

    # Create base and .git directories
    try:
        os.makedirs(git_dir, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create directory structure for {repo_path}: {e}")
        return False

    # Sample file content
    file1_path = os.path.join(repo_path, "module_one.py")
    file1_content = f"""
# Module One

def simple_function(a, b):
    \"\"\"Adds two numbers.\"\"\"
    return a + b

class MyImportant{SEARCH_KEYWORD.capitalize()}:
    \"\"\"A sample {SEARCH_KEYWORD} for demonstration.\"\"\"
    def __init__(self, name):
        self.name = name

    def greet(self):
        print(f"Hello from {{self.name}}")

instance = MyImportant{SEARCH_KEYWORD.capitalize()}("Demo")
"""

    file2_path = os.path.join(repo_path, "docs.md")
    file2_content = f"""
# Documentation File

This file describes the system.
It mentions the concept of a {SEARCH_KEYWORD}.

Another paragraph here.
"""

    file3_path = os.path.join(repo_path, "another_script.py")
    file3_content = """
# Another Script
# This one does NOT contain the target keyword.

def utility_func():
    return "utility"
"""

    # Write files only if they don't exist to avoid overwriting
    files_to_create = {
        file1_path: file1_content,
        file2_path: file2_content,
        file3_path: file3_content,
    }

    files_created_count = 0
    for f_path, f_content in files_to_create.items():
        if not os.path.exists(f_path):
            try:
                with open(f_path, 'w', encoding='utf-8') as f:
                    f.write(f_content.strip())
                files_created_count += 1
            except IOError as e:
                logger.error(f"Failed to write sample file {f_path}: {e}")
                # Continue trying to write other files
        else:
            logger.debug(f"Sample file already exists: {f_path}")

    logger.info(f"Sample repository ready. {files_created_count} new file(s) created.")
    # Note: We are not running `git init/add/commit` to avoid external dependency
    # The indexer just needs the .git directory to exist. Git metadata extraction will fail silently.
    return True

def cleanup_sample_repo(repo_path: str):
    """Removes the sample repository."""
    if os.path.exists(repo_path):
        try:
            shutil.rmtree(repo_path)
            logger.info(f"Cleaned up sample repository: {repo_path}")
        except OSError as e:
            logger.error(f"Failed to clean up sample repository {repo_path}: {e}")

# --- Main Demo Logic ---
def run_demo():
    """Runs Demo 2: S-expression workflow with get_context and read_files."""

    app: Application | None = None # Type hint for clarity

    try:
        # 1. Create Sample Repo
        if not create_sample_repo(SAMPLE_REPO_PATH):
            logger.error("Failed to set up sample repository. Aborting demo.")
            return

        # 2. Instantiate Application
        logger.info("Instantiating Application...")
        try:
            # Pass config if needed, e.g., Application(config={"handler_config": {"log_level": "DEBUG"}})
            app = Application()
            logger.info("Application instantiated successfully.")
        except Exception as e:
            logger.exception("Failed to instantiate Application.")
            return # Cannot proceed

        # 3. Index Repository
        logger.info(f"Indexing repository: {SAMPLE_REPO_PATH}")
        try:
            success = app.index_repository(SAMPLE_REPO_PATH)
            if not success:
                logger.error("Failed to index repository. Context may be unavailable.")
                # Decide whether to continue or abort
                # For this demo, context is crucial, so abort.
                return
            logger.info("Repository indexing initiated successfully.")
        except Exception as e:
            logger.exception("Error during repository indexing.")
            return

        # 4. Define S-expression Command
        # This workflow finds files containing SEARCH_KEYWORD, then reads them.
        sexp_command = f"""
        (let ((relevant_files (get_context (query "{SEARCH_KEYWORD}"))))
          (system:read_files (file_paths relevant_files)))
        """
        logger.info(f"Prepared S-expression command:\n{sexp_command}")

        # 5. Execute S-expression via handle_task_command
        logger.info("Executing S-expression workflow via /task command...")
        try:
            result_dict = app.handle_task_command(sexp_command)
            logger.info("S-expression execution complete.")
        except Exception as e:
            logger.exception("Error executing S-expression task command.")
            return

        # 6. Print Result
        print("\n" + "="*20 + " Demo Result " + "="*20)
        try:
            # Pretty print the JSON result
            print(json.dumps(result_dict, indent=2))

            # Optionally, add specific checks/comments based on expected output
            if result_dict.get("status") == "COMPLETE":
                print("\n--- Interpretation ---")
                print(f"The workflow successfully found files related to '{SEARCH_KEYWORD}' and read their content.")
                print(f"Files Read Count: {result_dict.get('notes', {}).get('files_read_count', 'N/A')}")
                print(f"Skipped Files: {result_dict.get('notes', {}).get('skipped_files', 'N/A')}")
                print("The 'content' field shows the concatenated text from the relevant files.")
                # Check if content actually contains the keyword
                if SEARCH_KEYWORD in result_dict.get("content", ""):
                    print(f"(Confirmed: Result content contains the keyword '{SEARCH_KEYWORD}')")
                else:
                     print(f"(Warning: Result content might not contain the keyword '{SEARCH_KEYWORD}', check MemorySystem matching)")

            else:
                print("\n--- Workflow Execution Failed ---")
                print(f"Status: {result_dict.get('status')}")
                print(f"Content: {result_dict.get('content')}")
                if 'error' in result_dict.get('notes', {}):
                    print(f"Error Details: {result_dict['notes']['error']}")

        except Exception as e:
            logger.error(f"Error printing/interpreting result: {e}")
            print("\nRaw Result Dictionary:")
            print(result_dict)

        print("="*53)

    finally:
        # Optional: Cleanup the sample repo after the demo
        # cleanup_sample_repo(SAMPLE_REPO_PATH)
        logger.info("Demo script finished.")


# --- Run Script ---
if __name__ == "__main__":
    run_demo()
