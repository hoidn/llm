#!/usr/bin/env python3

import os
import sys
import json
import logging
# import shutil # No longer needed for cleanup

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

# Add PROJECT_ROOT to sys.path.
if PROJECT_ROOT not in sys.path:
    sys.path.insert(1, PROJECT_ROOT) # Insert after SRC_PATH
    print(f"DEBUG: Added {PROJECT_ROOT} to sys.path") # Optional debug print

# --- Import Application ---
try:
    from main import Application
    from system.models import TaskResult
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print(f"PROJECT_ROOT calculated as: {PROJECT_ROOT}")
    print(f"SRC_PATH calculated as: {SRC_PATH}")
    print(f"Current sys.path: {sys.path}")
    print("Please ensure the project structure is correct and dependencies are installed.")
    sys.exit(1)

# --- Configuration ---
LOG_LEVEL = logging.DEBUG # Keep DEBUG for detailed output during demo
# --- START MODIFICATION ---
# Point to the actual project root directory for indexing
REPO_TO_INDEX = PROJECT_ROOT # Pass the actual Git repo root
# Change search keyword to something likely in the project code
SEARCH_KEYWORD = "TaskSystem"
# --- END MODIFICATION ---

# --- Logging Setup ---
logging.basicConfig(level=LOG_LEVEL,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
# Force the root logger level AFTER basicConfig
logging.getLogger().setLevel(LOG_LEVEL)
logger = logging.getLogger("DemoScript")
print(f"##### Root logger effective level: {logging.getLogger().getEffectiveLevel()} (DEBUG={logging.DEBUG}, INFO={logging.INFO}) #####")

# --- Helper Functions (Removed create/cleanup sample repo) ---

# --- Main Demo Logic ---
def run_demo():
    """Runs Demo 2: S-expression workflow using the actual project repo."""

    app: Application | None = None

    try:
        # 1. Log Target Repo Path
        logger.info(f"Target repository for indexing: {REPO_TO_INDEX}")

        # 2. Instantiate Application
        logger.info("Instantiating Application...")
        try:
            app = Application()
            logger.info("Application instantiated successfully.")
        except Exception as e:
            logger.exception("Failed to instantiate Application.")
            return

        # 3. Index Repository
        logger.info(f"Indexing repository: {REPO_TO_INDEX}")
        try:
            # Define index options to limit scope using patterns
            # These patterns are relative to REPO_TO_INDEX (which is now PROJECT_ROOT)
            index_options = {
                # Include Python files ONLY within the 'src' directory
                "include_patterns": ["src/**/*.py"],
                # Exclude common unwanted directories/files globally
                "exclude_patterns": [
                    "**/venv/**",
                    "**/__pycache__/**",
                    ".git/**",
                    "**/node_modules/**",
                    "*.pyc",
                    "*.log",
                    "demo_sample_repo/**",
                    "src/scripts/**" # Exclude this script itself
                 ]
            }
            logger.info(f"Using index options: {index_options}") # Log the options being used
            # Pass the correct repo path (PROJECT_ROOT) and options
            success = app.index_repository(REPO_TO_INDEX, options=index_options)
            if not success:
                logger.error("Failed to index repository. Context may be unavailable.")
                # Decide if you want to exit here or continue without context
                # return # Optional: exit if indexing fails
            else:
                logger.info("Repository indexing initiated successfully.")
        except Exception as e:
            logger.exception("Error during repository indexing.")
            # Decide if you want to exit here or continue without context
            # return # Optional: exit if indexing fails

        # 4. Define S-expression Command
        # Use the updated SEARCH_KEYWORD
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
            print(json.dumps(result_dict, indent=2))

            if result_dict.get("status") == "COMPLETE":
                print("\n--- Interpretation ---")
                print(f"Workflow looked for files related to '{SEARCH_KEYWORD}' in the project repo (scoped by index patterns) and attempted to read them.")
                read_count = result_dict.get('notes', {}).get('files_read_count', 'N/A')
                skipped_list = result_dict.get('notes', {}).get('skipped_files', [])
                print(f"Files Found & Attempted: {len(skipped_list) + (read_count if isinstance(read_count, int) else 0)}") # Approx based on skipped + read
                print(f"Files Successfully Read: {read_count}")
                print(f"Files Skipped (Not Found/Access Denied): {len(skipped_list)}")
                if skipped_list:
                     print(f"  (Examples: {skipped_list[:3]}{'...' if len(skipped_list)>3 else ''})") # Show a few skipped
                print("\nThe 'content' field shows the concatenated text from successfully read files (if any).")
                # Check if content actually contains the keyword (less reliable now)
                if SEARCH_KEYWORD in result_dict.get("content", ""):
                    print(f"(Note: Result content contains the keyword '{SEARCH_KEYWORD}')")
                elif read_count == 0 and skipped_list:
                     print(f"(Note: No files were read, likely because paths returned by LLM context task don't exactly match local paths)")
                elif read_count > 0:
                     print(f"(Note: Result content might not contain '{SEARCH_KEYWORD}' if it wasn't in the specific parts read)")

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
        # Remove cleanup call
        logger.info("Demo script finished.")


# --- Run Script ---
if __name__ == "__main__":
    run_demo()
