#!/usr/bin/env python3
"""
Orchestrator script for the Aider Test-Fix Loop workflow (Option A).

Manages interaction between Model A (planning/analysis), Aider (coding),
and the test execution environment using the Application layer and atomic tasks.
The core feedback loop is managed in Python.
"""

import os
import sys
import json
import logging
import argparse
import re
import readline # Optional: for better interactive input history
from typing import Optional, List, Dict, Any

# --- Setup Project Path ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..')) # Assumes scripts/ is one level below project root
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')
if SRC_PATH not in sys.path: sys.path.insert(0, SRC_PATH)
if PROJECT_ROOT not in sys.path: sys.path.insert(1, PROJECT_ROOT)

# --- Import Application & Models ---
try:
    # Using a placeholder name that might exist during development
    # try:
    #     from src.scripts.main_implementation import Application # If main is refactored
    # except ImportError:
    from src.main import Application # Use standard main
    from src.system.models import TaskResult, DevelopmentPlan, FeedbackResult
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"sys.path: {sys.path}")
    sys.exit(1)

# --- Logging Setup ---
# Logger defined here, configured in main() after parsing args
logger = logging.getLogger("AiderLoopOrchestrator")

# --- Helper Functions ---
def print_help():
    """Prints help messages for the interactive prompt (if adapted for interactive use)."""
    print("\n--- Aider Test-Fix Loop Orchestrator Help ---")
    print("This script automates the Aider loop based on provided arguments.")
    print("Arguments:")
    # Use argparse help for detailed argument info
    print("  Use --help flag for detailed argument descriptions.")
    print("-" * 40)

def load_prompts(args: argparse.Namespace) -> list[str]:
    """Loads prompts from command line args or file."""
    if args.prompt:
        logger.info(f"Loading {len(args.prompt)} prompts from command line.")
        return args.prompt
    elif args.prompt_file:
        logger.info(f"Loading prompts from file: {args.prompt_file}")
        if not os.path.exists(args.prompt_file):
            logger.error(f"Prompt file not found: {args.prompt_file}")
            sys.exit(f"Error: Prompt file not found: {args.prompt_file}")
            # Return here to prevent the try block from executing
            # This is unreachable but makes the intent clear
            return []
        try:
            with open(args.prompt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            # Find content between <prompt>...</prompt> tags
            prompts = re.findall(r'<prompt>(.*?)</prompt>', content, re.DOTALL)
            stripped_prompts = [p.strip() for p in prompts]
            final_prompts = [p for p in stripped_prompts if p] # Remove empty prompts
            if not final_prompts:
                logger.error(f"No prompts found between <prompt> tags in file: {args.prompt_file}")
                sys.exit(f"Error: No prompts found in file: {args.prompt_file}")
            logger.info(f"Loaded {len(final_prompts)} prompts from file.")
            return final_prompts
        except Exception as e:
            logger.exception(f"Error reading or parsing prompt file: {args.prompt_file}")
            sys.exit(f"Error reading prompt file: {e}")
    else:
        logger.error("No prompts provided via --prompt or --prompt-file.")
        sys.exit("Error: No prompts provided.")

def escape_json_string(value: str) -> str:
    """Escapes a string for safe embedding within a JSON string value."""
    # This might not be needed if passing dicts directly to handle_task_command
    return json.dumps(value)[1:-1]

def setup_logging(log_level_str: str):
    """Configures logging based on the provided level string."""
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    # Configure root logger or specific logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)] # Ensure logs go to stdout
    )
    # Set level for the script's logger specifically
    logger.setLevel(log_level)
    # Optionally adjust levels for other noisy loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logger.info(f"Logging configured to level: {log_level_str.upper()}")


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Aider Test-Fix Loop Orchestrator (Option A)")

    # Required arguments
    parser.add_argument("repo_path", help="Path to the target Git repository.")
    parser.add_argument("context_file", help="Path to the file containing initial context for Model A.")

    # Prompt arguments (mutually exclusive group)
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("-p", "--prompt", nargs='+', help="One or more user prompts for the task.")
    prompt_group.add_argument("-f", "--prompt-file", help="Path to a file containing prompts within <prompt> tags.")

    # Optional arguments
    parser.add_argument("--model-a", help="Override Model A identifier (planning/analysis).")
    parser.add_argument("--aider-model", help="Override model identifier used by Aider.")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum number of Aider execution retries (default: 3).")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level (default: INFO).")

    return parser.parse_args()

# --- Main Orchestration Logic ---
def run_orchestration_loop(args: argparse.Namespace):
    """Main orchestration logic."""
    logger.info("Starting orchestration...")
    print("--- Aider Test-Fix Loop Orchestrator (Task-Based) ---")
    logger.info(f"Parsed arguments: {args}")
    logger.info(f"Target Repository: {args.repo_path}")
    if args.model_a: logger.info(f"Model A override: {args.model_a}")
    if args.aider_model: logger.info(f"Aider Model override: {args.aider_model}")
    logger.info(f"Max Retries: {args.max_retries}")

    app: Optional[Application] = None
    plan: Optional[DevelopmentPlan] = None
    overall_status = "FAILURE" # Default to failure
    final_message = "Orchestration did not complete."
    final_loop_result_dict = None # Store the last result from the loop (Aider or Analysis)
    test_result_dict = None
    analysis_result_dict = None

    try:
        # --- Step 4: Prerequisite Checks ---
        logger.info("Performing prerequisite checks...")
        if not os.path.isdir(args.repo_path) or not os.path.isdir(os.path.join(args.repo_path, ".git")):
            raise ValueError(f"Provided repository path is not a valid Git repository: {args.repo_path}")
        if not os.path.exists(args.context_file):
            raise FileNotFoundError(f"Context file not found: {args.context_file}")
        # Ensure AIDER_ENABLED is set for Application init
        os.environ['AIDER_ENABLED'] = 'true'
        logger.info("Ensured AIDER_ENABLED=true is set in process environment")
        if not os.path.exists(os.path.join(PROJECT_ROOT, ".mcp.json")):
             logger.warning("'.mcp.json' not found in project root. Aider MCP connection might fail.")
        logger.info("Prerequisite checks passed.")

        # --- Step 5: Initialize Application ---
        logger.info("Instantiating Application...")
        # Pass Model A override if provided
        app_config = {'handler_config': {'default_model_identifier': args.model_a}} if args.model_a else {}
        # Ensure file manager base path is set correctly for the target repo
        app_config['file_manager_base_path'] = os.path.abspath(args.repo_path)
        logger.info(f"Using FileAccessManager base path: {app_config['file_manager_base_path']}")

        app = Application(config=app_config)
        logger.info("Application instantiated successfully.")

        # --- Step 6: Load Initial Context File ---
        logger.info(f"Loading initial context from: {args.context_file}")
        try:
            with open(args.context_file, 'r', encoding='utf-8') as f:
                initial_context_content = f.read()
            logger.info(f"Loaded {len(initial_context_content)} characters of initial context.")
        except Exception as e:
            raise IOError(f"Failed to read context file: {e}") from e

        # --- Step 7: Load Prompts ---
        model_a_prompts = load_prompts(args)

        # --- Step 8: Generate Plan using Atomic Task ---
        print("\n--- Phase: Generating Plan (using Model A) ---")
        logger.info("Calling 'user:generate-plan' atomic task...")

        # Combine prompts into a single string for the task input
        user_prompts_combined = "\n---\n".join(model_a_prompts)

        # Parameters for the planning task
        planning_params = {
            "user_prompts": user_prompts_combined,
            "initial_context": initial_context_content
        }
        planning_task_id = "user:generate-plan"

        logger.debug(f"Calling handle_task_command for '{planning_task_id}' with params: {list(planning_params.keys())}")
        planning_result_dict = app.handle_task_command(planning_task_id, planning_params)
        logger.debug(f"Planning task result: {planning_result_dict}")

        if planning_result_dict.get("status") != "COMPLETE":
            raise RuntimeError(f"Planning phase failed: {planning_result_dict.get('content')}")

        parsed_content = planning_result_dict.get("parsedContent")
        if not isinstance(parsed_content, dict):
            # Attempt to parse if it's a string containing JSON
            if isinstance(parsed_content, str):
                try:
                    parsed_content = json.loads(parsed_content)
                    logger.warning("Planning task returned JSON as string, parsed successfully.")
                except json.JSONDecodeError:
                     raise RuntimeError(f"Planning phase failed: Model A did not return valid JSON. Got string: {parsed_content[:200]}...")
            else:
                raise RuntimeError(f"Planning phase failed: Model A did not return a valid plan dictionary. Got: {type(parsed_content)}")

        try:
            plan = DevelopmentPlan.model_validate(parsed_content)
            logger.info("Successfully parsed development plan from Model A.")
            print("Plan Generated Successfully.")
            print(f"  Instructions: {plan.instructions[:100]}...") # Optional print
            print(f"  Files: {plan.files}")
            print(f"  Test Command: {plan.test_command}")
        except Exception as e:
            raise RuntimeError(f"Planning phase failed: Model A's plan failed validation: {e}\nReceived: {parsed_content}")

        # --- Step 9: Python Loop using Atomic Tasks ---
        print("\n--- Phase: Aider Execution Loop ---")
        current_aider_prompt = plan.instructions
        # Files need to be relative to repo root for Aider
        # Assuming FileAccessManager base path is repo root, paths in plan should be relative
        aider_files_json_str = json.dumps(plan.files)
        loop_aborted = False
        loop_succeeded = False
        iteration = 0 # Initialize iteration

        for i in range(args.max_retries):
            iteration = i + 1
            logger.info(f"--- Aider Loop Iteration {iteration}/{args.max_retries} ---")
            print(f"\n--- Aider Loop Iteration {iteration}/{args.max_retries} ---")

            # --- 9a: Call aider:automatic ---
            aider_params = {
                "prompt": current_aider_prompt,
                "file_context": aider_files_json_str
            }
            if args.aider_model:
                aider_params["model"] = args.aider_model

            logger.info(f"Calling aider:automatic (Iteration {iteration})...")
            print(f"Running Aider (Attempt {iteration})...")
            aider_result_dict = app.handle_task_command("aider:automatic", aider_params)
            logger.debug(f"Aider result (Iteration {iteration}): {aider_result_dict}")
            print(f"  Aider Status: {aider_result_dict.get('status')}")
            # Print Aider content/error for visibility
            print(f"  Aider Output/Error: {aider_result_dict.get('content', '[No Content]')[:500]}...")

            final_loop_result_dict = aider_result_dict # Store latest result

            # --- 9b: Call user:analyze-aider-result ---
            analysis_params = {
                "aider_result_content": str(aider_result_dict.get('content', '')),
                "aider_result_status": str(aider_result_dict.get('status', 'UNKNOWN')),
                "original_prompt": current_aider_prompt,
                "iteration": iteration,
                "max_retries": args.max_retries
            }
            analysis_task_id = "user:analyze-aider-result"

            logger.info("Calling user:analyze-aider-result...")
            print("Asking Model A for analysis of Aider iteration...")
            feedback_result_dict = app.handle_task_command(analysis_task_id, analysis_params)
            logger.debug(f"Analysis task result: {feedback_result_dict}")

            if feedback_result_dict.get("status") != "COMPLETE":
                logger.error(f"Analysis task failed: {feedback_result_dict.get('content')}. Aborting loop.")
                print(f"ERROR: Model A failed to provide feedback ({feedback_result_dict.get('content')}). Aborting loop.")
                loop_aborted = True
                break # Exit loop

            parsed_feedback_content = feedback_result_dict.get("parsedContent")
            if not isinstance(parsed_feedback_content, dict):
                 # Attempt to parse if it's a string containing JSON
                if isinstance(parsed_feedback_content, str):
                    try:
                        parsed_feedback_content = json.loads(parsed_feedback_content)
                        logger.warning("Analysis task returned JSON as string, parsed successfully.")
                    except json.JSONDecodeError:
                        logger.error(f"Analysis task failed: Model A did not return valid JSON feedback. Got string: {parsed_feedback_content[:200]}...")
                        print("ERROR: Model A failed to provide structured feedback (invalid JSON string). Aborting loop.")
                        loop_aborted = True
                        break
                else:
                    logger.error(f"Analysis task failed: Model A did not return a valid feedback dictionary. Got: {type(parsed_feedback_content)}")
                    print("ERROR: Model A failed to provide structured feedback. Aborting loop.")
                    loop_aborted = True
                    break

            try:
                feedback = FeedbackResult.model_validate(parsed_feedback_content)
                logger.info(f"Parsed feedback from Model A: Status={feedback.status}")
                print(f"  Model A Feedback Status: {feedback.status}")
                if feedback.explanation: print(f"  Explanation: {feedback.explanation}")
            except Exception as e:
                logger.error(f"Analysis task failed: Model A's feedback failed validation: {e}\nReceived: {parsed_feedback_content}")
                print(f"ERROR: Model A's feedback failed validation: {e}. Aborting loop.")
                loop_aborted = True
                break

            # --- 9c: Process Feedback ---
            if feedback.status == "SUCCESS":
                logger.info("Model A indicated SUCCESS. Exiting loop.")
                print("Model A indicated SUCCESS.")
                loop_succeeded = True
                break
            elif feedback.status == "REVISE":
                if feedback.next_prompt:
                    current_aider_prompt = feedback.next_prompt
                    logger.info("Model A suggested revision. Updating prompt for next iteration.")
                    print("Model A suggested revision. Updating prompt...")
                else:
                    logger.warning("Model A suggested REVISE but provided no next_prompt. Aborting loop.")
                    print("WARNING: Model A suggested REVISE but provided no next prompt. Aborting loop.")
                    loop_aborted = True
                    break
            elif feedback.status == "ABORT":
                logger.warning("Model A suggested ABORT. Exiting loop.")
                print("Model A suggested ABORT.")
                loop_aborted = True
                break
            else:
                # Should not happen if validation passed, but handle defensively
                logger.error(f"Model A provided invalid feedback status: {feedback.status}. Aborting.")
                print(f"ERROR: Model A provided invalid feedback status: {feedback.status}. Aborting.")
                loop_aborted = True
                break

        logger.info("--- Aider loop finished ---")
        print("\n--- Aider loop finished ---")

        if loop_aborted:
            final_message = "Loop aborted based on Model A feedback or analysis failure."
            overall_status = "FAILURE"
        elif not loop_succeeded and iteration == args.max_retries:
            final_message = f"Max retries ({args.max_retries}) reached without success signal from Model A."
            logger.warning(final_message)
            overall_status = "FAILURE" # Assume failure if max retries hit without success
        elif loop_succeeded:
             logger.info("Loop finished with SUCCESS signal from Model A.")
             # Tentative success, pending tests
             pass # Keep overall_status as FAILURE until tests pass


        # --- Step 10: Run Tests (Only if loop didn't abort) ---
        if not loop_aborted:
            print("\n--- Phase: Running Tests ---")
            logger.info("Executing test command...")
            test_command = plan.test_command
            # Ensure cwd is absolute path for execute_shell_command
            abs_repo_path = os.path.abspath(args.repo_path)
            shell_params = {"command": test_command, "cwd": abs_repo_path}

            logger.debug(f"Calling system:execute_shell_command with params: {shell_params}")
            test_result_dict = app.handle_task_command("system:execute_shell_command", shell_params)
            logger.info(f"Test command execution status: {test_result_dict.get('status')}")
            print(f"Test Command Status: {test_result_dict.get('status')}")
            test_exit_code = test_result_dict.get('notes', {}).get('exit_code')
            print(f"Test Command Exit Code: {test_exit_code}")
            # Print test output for visibility
            print("--- Test Stdout ---")
            print(test_result_dict.get('notes', {}).get('stdout', '[No Stdout]'))
            print("--- Test Stderr ---")
            print(test_result_dict.get('notes', {}).get('stderr', '[No Stderr]'))
            print("-------------------")


            # --- Step 11: Final Analysis (Only if loop didn't abort) ---
            print("\n--- Phase: Final Analysis (using Model A) ---")
            logger.info("Performing final analysis query...")

            test_output_summary = f"""
Test Command: {test_command}
Test Execution Status: {test_result_dict.get('status')}
Test Exit Code: {test_exit_code}
Test Stdout:
{test_result_dict.get('notes', {}).get('stdout', '[No Stdout]')}
Test Stderr:
{test_result_dict.get('notes', {}).get('stderr', '[No Stderr]')}
"""
            # Include loop outcome message
            loop_outcome_msg = "Loop finished: "
            if loop_succeeded: loop_outcome_msg += "SUCCESS signal received from Model A."
            elif loop_aborted: loop_outcome_msg += "Aborted."
            else: loop_outcome_msg += f"Max retries ({args.max_retries}) reached."

            final_analysis_prompt = f"""The initial goal was derived from the context and these prompts: {' | '.join(model_a_prompts)}

{loop_outcome_msg}

Last Aider Result:
Status: {final_loop_result_dict.get('status') if final_loop_result_dict else 'N/A'}
Output/Error: {final_loop_result_dict.get('content') if final_loop_result_dict else 'N/A'}

{test_output_summary}

Based on all the above, was the overall task goal successfully achieved, considering BOTH the Aider execution outcome AND the test results? Respond ONLY with 'OVERALL_SUCCESS' or 'OVERALL_FAILURE' followed by a brief final explanation.
"""
            logger.debug(f"Final analysis prompt: {final_analysis_prompt[:500]}...")
            analysis_result_dict = app.handle_query(final_analysis_prompt)
            logger.debug(f"Final analysis result: {analysis_result_dict}")

            if analysis_result_dict.get("status") == "COMPLETE":
                final_message = analysis_result_dict.get('content', 'Analysis complete.')
                # Determine overall status based on Model A's final verdict AND test results
                model_a_verdict_success = final_message.strip().upper().startswith("OVERALL_SUCCESS")
                tests_passed = test_result_dict.get("status") == "COMPLETE" and test_exit_code == 0

                if model_a_verdict_success and tests_passed:
                    overall_status = "SUCCESS"
                    logger.info("Final verdict: OVERALL_SUCCESS (Model A agreed and tests passed)")
                elif model_a_verdict_success and not tests_passed:
                    overall_status = "FAILURE"
                    logger.warning("Final verdict: OVERALL_FAILURE (Model A said success, but tests failed or execution error)")
                    final_message += "\n[Orchestrator Note: Overall status set to FAILURE due to non-passing tests or test execution error.]"
                else: # Model A said failure
                    overall_status = "FAILURE"
                    logger.warning(f"Final verdict: OVERALL_FAILURE (Based on Model A analysis: {final_message})")
            else:
                final_message = f"Final analysis query failed: {analysis_result_dict.get('content')}"
                logger.error(final_message)
                overall_status = "FAILURE"
        else:
            # Loop was aborted, use the message set earlier
            test_result_dict = {"status": "SKIPPED", "content": "Tests skipped due to loop abort.", "notes": {}}
            analysis_result_dict = {"status": "SKIPPED", "content": final_message, "notes": {}}


    except Exception as e:
        final_message = f"Orchestration script failed unexpectedly: {type(e).__name__}: {e}"
        logger.exception(final_message)
        overall_status = "FAILURE"
    finally:
        # --- Step 12: Report Outcome ---
        print("\n" + "="*20 + " Final Orchestration Result " + "="*20)
        print(f"Overall Status: {overall_status}")
        print("\nFinal Message/Analysis:")
        print(final_message if final_message else "[No final message]")
        print("="*66)
        logger.info(f"Orchestration finished with Overall Status: {overall_status}")
        # Exit with appropriate status code
        sys.exit(0 if overall_status == "SUCCESS" else 1)


# --- Main Execution Block ---
if __name__ == "__main__":
    cli_args = parse_arguments()
    setup_logging(cli_args.log_level)
    run_orchestration_loop(cli_args)
