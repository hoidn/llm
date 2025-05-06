"""
Unit and integration tests for the Aider Test-Fix Loop orchestrator script.
(scripts/run_aider_loop.py)
"""

import pytest
import sys
import os
import json
import argparse
import logging # Added import
from unittest.mock import patch, MagicMock, mock_open, call, ANY # Added ANY

# Ensure src and scripts directory are in path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')
SCRIPTS_PATH = os.path.join(PROJECT_ROOT, 'scripts') # Add scripts path

if SRC_PATH not in sys.path: sys.path.insert(0, SRC_PATH)
if SCRIPTS_PATH not in sys.path: sys.path.insert(0, SCRIPTS_PATH) # Insert scripts path
if PROJECT_ROOT not in sys.path: sys.path.insert(1, PROJECT_ROOT)

# Import the script module to test its functions
try:
    import run_aider_loop
    # Import specific functions/classes if needed directly
    from run_aider_loop import parse_arguments, load_prompts, run_orchestration_loop, setup_logging
except ImportError as e:
    pytest.skip(f"Skipping script tests, failed to import run_aider_loop: {e}", allow_module_level=True)

# Mock the Application class and its methods before tests run
@pytest.fixture(autouse=True)
def mock_application(mocker):
    """Mocks the Application class for all tests in this module."""
    mock_app_instance = MagicMock()
    # Configure default return values for mocked methods
    mock_app_instance.handle_task_command.return_value = {"status": "FAILED", "content": "Default mock task fail"}
    mock_app_instance.handle_query.return_value = {"status": "FAILED", "content": "Default mock query fail"}

    # Patch the Application class where it's looked up in the script
    mock_app_class = mocker.patch('run_aider_loop.Application', return_value=mock_app_instance)
    return mock_app_instance # Return the instance for configuration in tests

@pytest.fixture
def mock_sys_exit(mocker):
    """Mocks sys.exit."""
    return mocker.patch('sys.exit')

@pytest.fixture
def mock_os_path_exists(mocker):
    """Mocks os.path.exists."""
    return mocker.patch('os.path.exists', return_value=True) # Default to True

@pytest.fixture
def mock_os_path_isdir(mocker):
    """Mocks os.path.isdir."""
    # Default to True, can be overridden in tests
    return mocker.patch('os.path.isdir', return_value=True)

@pytest.fixture
def mock_open_file(mocker):
    """Mocks the built-in open function."""
    return mocker.patch('builtins.open', mock_open(read_data="Default file content"))

@pytest.fixture
def mock_logging(mocker):
    """Mocks logging functions."""
    mocker.patch('logging.basicConfig')
    mocker.patch('logging.getLogger')
    # Return the mocked logger instance if needed
    return logging.getLogger.return_value

# --- Test Argument Parsing ---

def test_parse_arguments_required():
    """Test parsing required arguments."""
    test_args = ['/path/to/repo', '/path/to/context.txt', '-p', 'prompt1']
    with patch.object(sys, 'argv', ['script_name'] + test_args):
        args = parse_arguments()
    assert args.repo_path == '/path/to/repo'
    assert args.context_file == '/path/to/context.txt'
    assert args.prompt == ['prompt1']
    assert args.prompt_file is None
    assert args.max_retries == 3 # Default
    assert args.log_level == "INFO" # Default

def test_parse_arguments_optional():
    """Test parsing optional arguments."""
    test_args = [
        '/repo', 'ctx.txt', '-f', 'prompts.txt',
        '--model-a', 'model-a-id', '--aider-model', 'aider-id',
        '--max-retries', '5', '--log-level', 'DEBUG'
    ]
    with patch.object(sys, 'argv', ['script_name'] + test_args):
        args = parse_arguments()
    assert args.repo_path == '/repo'
    assert args.context_file == 'ctx.txt'
    assert args.prompt is None
    assert args.prompt_file == 'prompts.txt'
    assert args.model_a == 'model-a-id'
    assert args.aider_model == 'aider-id'
    assert args.max_retries == 5
    assert args.log_level == 'DEBUG'

@patch('argparse.ArgumentParser.exit') # Mock argparse's exit method
def test_parse_arguments_missing_required(mock_argparse_exit):
    """Test parsing fails if required arguments are missing."""
    with patch.object(sys, 'argv', ['script_name']):
        parse_arguments() # Call the function
    # Assert that argparse's exit was called (indicating an error)
    mock_argparse_exit.assert_called()
    # Optionally check the error code if needed, often it's 2 for argparse errors
    # print(mock_argparse_exit.call_args) # Uncomment to see call details

@patch('argparse.ArgumentParser.exit') # Mock argparse's exit method
def test_parse_arguments_mutually_exclusive_prompts(mock_argparse_exit):
    """Test parsing fails if both prompt and prompt-file are given."""
    # NOTE: Argparse handles required positional args BEFORE mutual exclusion usually.
    # Need to provide dummy positional args for repo_path and context_file.
    test_args = ['/repo', 'ctx.txt', '--prompt', 'prompt1', '--prompt-file', 'prompts.txt']
    with patch.object(sys, 'argv', ['script_name'] + test_args):
        parse_arguments()
    mock_argparse_exit.assert_called()

# --- Test Prompt Loading ---

def test_load_prompts_from_args():
    """Test loading prompts directly from args.prompt."""
    args = argparse.Namespace(prompt=['prompt1', 'prompt2'], prompt_file=None)
    prompts = load_prompts(args)
    assert prompts == ['prompt1', 'prompt2']

@patch('sys.exit') # Keep mocking exit just in case
@patch('os.path.exists')
@patch('builtins.open', new_callable=mock_open) # Mock open directly
def test_load_prompts_from_file_success(mock_open_handle, mock_exists, mock_exit):
    """Test loading prompts successfully from a file."""
    # Correct file content with actual prompts
    file_content = "Some text\n<prompt>Prompt One</prompt>\nMore text\n<prompt>\nPrompt Two\n</prompt>Empty<prompt>  </prompt><prompt>Prompt Three</prompt>"
    # Configure mock_open to simulate reading this content
    mock_open_handle.return_value.read.return_value = file_content
    mock_exists.return_value = True
    args = argparse.Namespace(prompt=None, prompt_file='prompts.txt')

    prompts = load_prompts(args)

    # Assertions
    assert prompts == ["Prompt One", "Prompt Two", "Prompt Three"] # Check stripped, non-empty prompts
    mock_open_handle.assert_called_once_with('prompts.txt', 'r', encoding='utf-8')
    mock_exit.assert_not_called() # Ensure sys.exit wasn't called

@patch('sys.exit')
def test_load_prompts_from_file_not_found(mock_sys_exit, mock_os_path_exists): # Pass mock_sys_exit
    """Test loading prompts when file does not exist."""
    mock_os_path_exists.return_value = False
    args = argparse.Namespace(prompt=None, prompt_file='missing.txt')
    load_prompts(args) # Call the function
    mock_sys_exit.assert_called_once_with("Error: Prompt file not found: missing.txt") # Assert exit call

@patch('sys.exit')
def test_load_prompts_from_file_no_tags(mock_sys_exit, mock_os_path_exists, mock_open_file): # Pass mock_sys_exit
    """Test loading prompts when file has no <prompt> tags."""
    mock_open_file.configure_mock(read_data="Just plain text.")
    mock_os_path_exists.return_value = True
    args = argparse.Namespace(prompt=None, prompt_file='no_tags.txt')
    load_prompts(args)
    mock_sys_exit.assert_called_once_with("Error: No prompts found in file: no_tags.txt")

@patch('sys.exit')
def test_load_prompts_no_prompts_provided(mock_sys_exit): # Pass mock_sys_exit
    """Test error when neither --prompt nor --prompt-file is provided."""
    args = argparse.Namespace(prompt=None, prompt_file=None)
    load_prompts(args)
    mock_sys_exit.assert_called_once_with("Error: No prompts provided.")

# --- Test Main Orchestration Logic ---

@pytest.fixture
def default_args():
    """Provides default valid arguments for run_orchestration_loop."""
    return argparse.Namespace(
        repo_path='/mock/repo',
        context_file='/mock/context.txt',
        prompt=['Initial prompt'],
        prompt_file=None,
        model_a=None,
        aider_model=None,
        max_retries=3,
        log_level='INFO'
    )

# Helper to configure mock app returns
def configure_mock_app(mock_app, plan_success=True, aider_results=None, analysis_results=None, test_success=True, final_analysis_success=True, final_verdict="OVERALL_SUCCESS"):
    """Configures the mock Application instance for different scenarios."""
    aider_results = aider_results or [{"status": "COMPLETE", "content": "Aider success"}]
    analysis_results = analysis_results or [{"status": "SUCCESS"}] # Default to immediate success

    # --- Planning Task ---
    if plan_success:
        plan_data = {
            "instructions": "Mock instructions",
            "files": ["file.py"],
            "test_command": "mock_test_command"
        }
        plan_result = {"status": "COMPLETE", "parsedContent": plan_data, "content": json.dumps(plan_data)}
    else:
        plan_result = {"status": "FAILED", "content": "Planning failed"}

    # --- Aider Task ---
    aider_call_results = []
    for res in aider_results:
        aider_call_results.append(res)

    # --- Analysis Task ---
    analysis_call_results = []
    for i, res in enumerate(analysis_results):
        # --- FIX: Convert status strings to FeedbackResult dicts ---
        if isinstance(res, str): # Handle old string format if needed, but prefer dicts
            if res == "SUCCESS":
                feedback_data = {"status": "SUCCESS", "next_prompt": None, "explanation": "Looks good!"}
            elif res.startswith("REVISE:"):
                feedback_data = {"status": "REVISE", "next_prompt": res[len("REVISE:"):].strip(), "explanation": "Needs revision."}
            elif res == "ABORT":
                feedback_data = {"status": "ABORT", "next_prompt": None, "explanation": "Cannot proceed."}
            else: # Default to ABORT on unknown string
                feedback_data = {"status": "ABORT", "next_prompt": None, "explanation": f"Unknown feedback string: {res}"}
        elif isinstance(res, dict) and "status" in res: # Accept pre-formatted dicts
            feedback_data = res
        else: # Invalid mock input
            feedback_data = {"status": "ABORT", "next_prompt": None, "explanation": f"Invalid mock analysis result: {res}"}
        # --- END FIX ---
        
        analysis_call_results.append({"status": "COMPLETE", "parsedContent": feedback_data, "content": json.dumps(feedback_data)})

    # --- Test Execution Task ---
    if test_success:
        test_result = {"status": "COMPLETE", "notes": {"exit_code": 0, "stdout": "Tests passed", "stderr": ""}}
    else:
        test_result = {"status": "COMPLETE", "notes": {"exit_code": 1, "stdout": "", "stderr": "Test failed"}}

    # --- Final Analysis Query ---
    if final_analysis_success:
        final_analysis_result = {"status": "COMPLETE", "content": f"{final_verdict}\nExplanation..."}
    else:
        final_analysis_result = {"status": "FAILED", "content": "Final analysis failed"}

    # Configure side effects for handle_task_command
    task_results_map = {
        "user:generate-plan": plan_result,
        "aider:automatic": aider_call_results, # List of results for loop
        "user:analyze-aider-result": analysis_call_results, # List of results for loop
        "system:execute_shell_command": test_result
    }

    aider_call_index = 0
    analysis_call_index = 0

    def handle_task_side_effect(task_id, params=None, flags=None):
        nonlocal aider_call_index, analysis_call_index
        if task_id == "aider:automatic":
            res = task_results_map[task_id][aider_call_index]
            aider_call_index += 1
            return res
        elif task_id == "user:analyze-aider-result":
            res = task_results_map[task_id][analysis_call_index]
            analysis_call_index += 1
            return res
        elif task_id in task_results_map:
            return task_results_map[task_id]
        else:
            return {"status": "FAILED", "content": f"Unexpected task mock call: {task_id}"}

    mock_app.handle_task_command.side_effect = handle_task_side_effect
    mock_app.handle_query.return_value = final_analysis_result


@patch('sys.exit') # Patch sys.exit for all orchestration tests
def test_run_orchestration_success_path(
    mock_sys_exit, # Add mock_sys_exit parameter
    default_args, mock_application, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test the successful execution path of the orchestration loop."""
    configure_mock_app(
        mock_application,
        plan_success=True,
        aider_results=[{"status": "COMPLETE", "content": "Aider success"}],
        analysis_results=["SUCCESS"],
        test_success=True,
        final_analysis_success=True,
        final_verdict="OVERALL_SUCCESS"
    )
    mock_open_file.configure_mock(read_data="Initial context")

    # Act
    run_orchestration_loop(default_args) # Call directly

    # Assert
    # Check planning call
    mock_application.handle_task_command.assert_any_call("user:generate-plan", ANY)
    # Check Aider call
    mock_application.handle_task_command.assert_any_call("aider:automatic", ANY)
    # Check analysis call
    mock_application.handle_task_command.assert_any_call("user:analyze-aider-result", ANY)
    # Check test execution call
    mock_application.handle_task_command.assert_any_call("system:execute_shell_command", {"command": "mock_test_command", "cwd": os.path.abspath('/mock/repo')})
    # Check final analysis query
    mock_application.handle_query.assert_called_once()
    assert "OVERALL_SUCCESS" in mock_application.handle_query.call_args[0][0] # Check prompt content

    mock_sys_exit.assert_called_once_with(0) # Expect exit code 0 for success

@patch('sys.exit')
def test_run_orchestration_planning_fails(
    mock_sys_exit, # Add mock
    default_args, mock_application, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test failure during the planning phase."""
    configure_mock_app(mock_application, plan_success=False)
    mock_open_file.configure_mock(read_data="Initial context")

    run_orchestration_loop(default_args)
    mock_application.handle_task_command.assert_called_once_with("user:generate-plan", ANY)
    # Ensure other phases were not reached
    mock_application.handle_query.assert_not_called()
    mock_sys_exit.assert_called_once_with(1) # Expect exit code 1 for failure

@patch('sys.exit')
def test_run_orchestration_loop_revise_then_success(
    mock_sys_exit, # Add mock
    default_args, mock_application, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test loop with one revision then success."""
    configure_mock_app(
        mock_application,
        plan_success=True,
        aider_results=[
            {"status": "COMPLETE", "content": "Aider attempt 1"},
            {"status": "COMPLETE", "content": "Aider attempt 2"}
        ],
        analysis_results=[
            {"status": "REVISE", "next_prompt": "Prompt 2", "explanation": "Revise 1"}, # Correct dict
            {"status": "SUCCESS", "explanation": "Success!"} # Correct dict
        ],
        test_success=True,
        final_analysis_success=True,
        final_verdict="OVERALL_SUCCESS"
    )
    mock_open_file.configure_mock(read_data="Initial context")

    run_orchestration_loop(default_args)

    # Assertions
    # Recalculate expected calls: 1(plan) + 2(aider) + 2(analysis) + 1(test) = 6
    assert mock_application.handle_task_command.call_count == 6 # CORRECTED COUNT
    aider_calls = [c for c in mock_application.handle_task_command.call_args_list if c.args[0] == 'aider:automatic']
    analysis_calls = [c for c in mock_application.handle_task_command.call_args_list if c.args[0] == 'user:analyze-aider-result']
    assert len(aider_calls) == 2
    assert len(analysis_calls) == 2
    # Check second aider call used revised prompt
    assert aider_calls[1].args[1]['prompt'] == "Revised prompt 1"
    mock_application.handle_query.assert_called_once()
    mock_sys_exit.assert_called_once_with(0)

@patch('sys.exit')
def test_run_orchestration_loop_abort(
    mock_sys_exit, # Add mock
    default_args, mock_application, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test loop aborts based on Model A feedback."""
    configure_mock_app(
        mock_application,
        plan_success=True,
        aider_results=[{"status": "FAILED", "content": "Aider failed badly"}],
        analysis_results=["ABORT"], # Model A says abort
        test_success=True, # Should be skipped
        final_analysis_success=True # Should be skipped
    )
    mock_open_file.configure_mock(read_data="Initial context")

    run_orchestration_loop(default_args)

    # Assertions
    assert mock_application.handle_task_command.call_count == 3 # plan + aider + analysis
    # Ensure test and final query were skipped
    test_call = next((c for c in mock_application.handle_task_command.call_args_list if c.args[0] == 'system:execute_shell_command'), None)
    assert test_call is None
    mock_application.handle_query.assert_not_called()
    mock_sys_exit.assert_called_once_with(1)

@patch('sys.exit')
def test_run_orchestration_max_retries_reached(
    mock_sys_exit, # Add mock
    default_args, mock_application, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test loop finishes due to max retries without success."""
    default_args.max_retries = 2
    configure_mock_app(
        mock_application,
        plan_success=True,
        aider_results=[
            {"status": "COMPLETE", "content": "Aider attempt 1"},
            {"status": "COMPLETE", "content": "Aider attempt 2"}
        ],
        analysis_results=[
            {"status": "REVISE", "next_prompt": "Prompt 2", "explanation":"Revise 1"}, # Correct dict
            {"status": "REVISE", "next_prompt": "Prompt 3", "explanation":"Revise 2"}  # Correct dict
        ],
        test_success=True, # Tests run after loop finishes
        final_analysis_success=True,
        final_verdict="OVERALL_FAILURE" # Assume final analysis says failure
    )
    mock_open_file.configure_mock(read_data="Initial context")

    run_orchestration_loop(default_args)

    # Assertions
    # Recalculate expected calls: 1(plan) + 2(aider) + 2(analysis) + 1(test) = 6
    assert mock_application.handle_task_command.call_count == 6 # CORRECTED COUNT
    aider_calls = [c for c in mock_application.handle_task_command.call_args_list if c.args[0] == 'aider:automatic']
    analysis_calls = [c for c in mock_application.handle_task_command.call_args_list if c.args[0] == 'user:analyze-aider-result']
    assert len(aider_calls) == 2
    assert len(analysis_calls) == 2
    mock_application.handle_query.assert_called_once() # Final analysis still runs
    mock_sys_exit.assert_called_once_with(1) # Overall failure

@patch('sys.exit')
def test_run_orchestration_tests_fail(
    mock_sys_exit, # Add mock
    default_args, mock_application, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test overall failure when tests fail after a successful loop."""
    configure_mock_app(
        mock_application,
        plan_success=True,
        aider_results=[{"status": "COMPLETE", "content": "Aider success"}],
        analysis_results=["SUCCESS"],
        test_success=False, # Tests fail
        final_analysis_success=True,
        final_verdict="OVERALL_SUCCESS" # Model A might still say success initially
    )
    mock_open_file.configure_mock(read_data="Initial context")

    run_orchestration_loop(default_args)

    # Assertions
    assert mock_application.handle_task_command.call_count == 4 # plan + aider + analysis + test
    mock_application.handle_query.assert_called_once()
    # Check final analysis prompt includes test failure info
    assert "Test Exit Code: 1" in mock_application.handle_query.call_args[0][0]
    assert "Test failed" in mock_application.handle_query.call_args[0][0]
    mock_sys_exit.assert_called_once_with(1) # Overall failure because tests failed

@patch('sys.exit')
def test_run_orchestration_final_analysis_fails(
    mock_sys_exit, # Add mock
     default_args, mock_application, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test overall failure when the final analysis query fails."""
    configure_mock_app(
        mock_application,
        plan_success=True,
        aider_results=[{"status": "COMPLETE", "content": "Aider success"}],
        analysis_results=["SUCCESS"],
        test_success=True,
        final_analysis_success=False # Final query fails
    )
    mock_open_file.configure_mock(read_data="Initial context")

    run_orchestration_loop(default_args)

    # Assertions
    assert mock_application.handle_task_command.call_count == 4 # plan + aider + analysis + test
    mock_application.handle_query.assert_called_once()
    mock_sys_exit.assert_called_once_with(1) # Overall failure

@patch('sys.exit')
def test_run_orchestration_repo_path_invalid(
    mock_sys_exit, # Add mock
    default_args, mock_application, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test script exits if repo path is invalid."""
    # Simulate only the second isdir check (for .git) failing
    mock_os_path_isdir.side_effect = lambda path: '.git' not in path
    mock_os_path_exists.return_value = True # Assume base path exists

    run_orchestration_loop(default_args)
    # Assert that sys.exit was called due to the ValueError raised
    mock_application.handle_task_command.assert_not_called() # Should exit early
    mock_sys_exit.assert_called_once_with(1)

@patch('sys.exit')
def test_run_orchestration_context_file_not_found(
    mock_sys_exit, # Add mock
    default_args, mock_application, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test script exits if context file is not found."""
    # Make os.path.exists return False only for the context file
    original_exists = os.path.exists
    def exists_side_effect(path):
        if path == default_args.context_file:
            return False
        return original_exists(path) # Or use mock_os_path_exists for others if needed
    mock_os_path_exists.side_effect = exists_side_effect
    mock_os_path_isdir.return_value = True # Assume repo path is valid

    run_orchestration_loop(default_args)
    mock_application.handle_task_command.assert_not_called() # Should exit early
    mock_sys_exit.assert_called_once_with(1)
