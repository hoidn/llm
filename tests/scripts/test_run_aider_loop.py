"""
Unit and integration tests for the Aider Test-Fix Loop orchestrator script.
(scripts/run_aider_loop.py)
"""

import pytest
import sys
import os
import json
import argparse
from unittest.mock import patch, MagicMock, mock_open, call

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

def test_parse_arguments_missing_required(mock_sys_exit):
    """Test parsing fails if required arguments are missing."""
    with patch.object(sys, 'argv', ['script_name']): # Missing all required
        with pytest.raises(SystemExit): # argparse calls sys.exit on error
            parse_arguments()
    mock_sys_exit.assert_called()

def test_parse_arguments_mutually_exclusive_prompts(mock_sys_exit):
    """Test parsing fails if both prompt and prompt-file are given."""
    test_args = ['/repo', 'ctx.txt', '-p', 'prompt1', '-f', 'prompts.txt']
    with patch.object(sys, 'argv', ['script_name'] + test_args):
        with pytest.raises(SystemExit):
            parse_arguments()
    mock_sys_exit.assert_called()

# --- Test Prompt Loading ---

def test_load_prompts_from_args():
    """Test loading prompts directly from args.prompt."""
    args = argparse.Namespace(prompt=['prompt1', 'prompt2'], prompt_file=None)
    prompts = load_prompts(args)
    assert prompts == ['prompt1', 'prompt2']

def test_load_prompts_from_file_success(mock_os_path_exists, mock_open_file):
    """Test loading prompts successfully from a file."""
    file_content = "Some text\n<prompt> Prompt One </prompt>\nMore text\n<prompt>\nPrompt Two\n</prompt>Empty<prompt></prompt>"
    mock_open_file.configure_mock(read_data=file_content)
    mock_os_path_exists.return_value = True
    args = argparse.Namespace(prompt=None, prompt_file='prompts.txt')

    prompts = load_prompts(args)

    mock_os_path_exists.assert_called_once_with('prompts.txt')
    mock_open_file.assert_called_once_with('prompts.txt', 'r', encoding='utf-8')
    assert prompts == ['Prompt One', 'Prompt Two'] # Check stripping and removal of empty

def test_load_prompts_from_file_not_found(mock_os_path_exists, mock_sys_exit):
    """Test loading prompts when file does not exist."""
    mock_os_path_exists.return_value = False
    args = argparse.Namespace(prompt=None, prompt_file='missing.txt')

    with pytest.raises(SystemExit):
        load_prompts(args)
    mock_sys_exit.assert_called_with("Error: Prompt file not found: missing.txt")

def test_load_prompts_from_file_no_tags(mock_os_path_exists, mock_open_file, mock_sys_exit):
    """Test loading prompts when file has no <prompt> tags."""
    mock_open_file.configure_mock(read_data="Just plain text.")
    mock_os_path_exists.return_value = True
    args = argparse.Namespace(prompt=None, prompt_file='no_tags.txt')

    with pytest.raises(SystemExit):
        load_prompts(args)
    mock_sys_exit.assert_called_with("Error: No prompts found in file: no_tags.txt")

def test_load_prompts_no_prompts_provided(mock_sys_exit):
    """Test error when neither --prompt nor --prompt-file is provided."""
    args = argparse.Namespace(prompt=None, prompt_file=None)
    with pytest.raises(SystemExit):
        load_prompts(args)
    mock_sys_exit.assert_called_with("Error: No prompts provided.")

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
    for i, res_status in enumerate(analysis_results):
        feedback_data = {"status": res_status}
        if res_status == "REVISE":
            feedback_data["next_prompt"] = f"Revised prompt {i+1}"
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


def test_run_orchestration_success_path(
    default_args, mock_application, mock_sys_exit, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test the successful execution path of the orchestration loop."""
    # Arrange: Configure mocks for success
    configure_mock_app(
        mock_application,
        plan_success=True,
        aider_results=[{"status": "COMPLETE", "content": "Aider success"}], # Single successful Aider run
        analysis_results=["SUCCESS"], # Model A says success on first try
        test_success=True,
        final_analysis_success=True,
        final_verdict="OVERALL_SUCCESS"
    )
    mock_open_file.configure_mock(read_data="Initial context") # Mock context file read

    # Act
    with pytest.raises(SystemExit) as excinfo:
         run_orchestration_loop(default_args)

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

    # Check final exit code
    assert excinfo.value.code == 0
    mock_sys_exit.assert_called_once_with(0)

def test_run_orchestration_planning_fails(
    default_args, mock_application, mock_sys_exit, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test failure during the planning phase."""
    configure_mock_app(mock_application, plan_success=False)
    mock_open_file.configure_mock(read_data="Initial context")

    with pytest.raises(SystemExit) as excinfo:
        run_orchestration_loop(default_args)

    mock_application.handle_task_command.assert_called_once_with("user:generate-plan", ANY)
    # Ensure other phases were not reached
    mock_application.handle_query.assert_not_called()
    assert excinfo.value.code == 1
    mock_sys_exit.assert_called_once_with(1)

def test_run_orchestration_loop_revise_then_success(
    default_args, mock_application, mock_sys_exit, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test loop with one revision then success."""
    configure_mock_app(
        mock_application,
        plan_success=True,
        aider_results=[
            {"status": "COMPLETE", "content": "Aider attempt 1"},
            {"status": "COMPLETE", "content": "Aider attempt 2"}
        ],
        analysis_results=["REVISE", "SUCCESS"], # Revise first, then success
        test_success=True,
        final_analysis_success=True,
        final_verdict="OVERALL_SUCCESS"
    )
    mock_open_file.configure_mock(read_data="Initial context")

    with pytest.raises(SystemExit) as excinfo:
        run_orchestration_loop(default_args)

    # Assertions
    assert mock_application.handle_task_command.call_count == 5 # plan + aider*2 + analysis*2 + test
    aider_calls = [c for c in mock_application.handle_task_command.call_args_list if c.args[0] == 'aider:automatic']
    analysis_calls = [c for c in mock_application.handle_task_command.call_args_list if c.args[0] == 'user:analyze-aider-result']
    assert len(aider_calls) == 2
    assert len(analysis_calls) == 2
    # Check second aider call used revised prompt
    assert aider_calls[1].args[1]['prompt'] == "Revised prompt 1"
    mock_application.handle_query.assert_called_once()
    assert excinfo.value.code == 0
    mock_sys_exit.assert_called_once_with(0)

def test_run_orchestration_loop_abort(
    default_args, mock_application, mock_sys_exit, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
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

    with pytest.raises(SystemExit) as excinfo:
        run_orchestration_loop(default_args)

    # Assertions
    assert mock_application.handle_task_command.call_count == 3 # plan + aider + analysis
    # Ensure test and final query were skipped
    test_call = next((c for c in mock_application.handle_task_command.call_args_list if c.args[0] == 'system:execute_shell_command'), None)
    assert test_call is None
    mock_application.handle_query.assert_not_called()
    assert excinfo.value.code == 1
    mock_sys_exit.assert_called_once_with(1)

def test_run_orchestration_max_retries_reached(
    default_args, mock_application, mock_sys_exit, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
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
        analysis_results=["REVISE", "REVISE"], # Always revise
        test_success=True, # Tests run after loop finishes
        final_analysis_success=True,
        final_verdict="OVERALL_FAILURE" # Assume final analysis says failure
    )
    mock_open_file.configure_mock(read_data="Initial context")

    with pytest.raises(SystemExit) as excinfo:
        run_orchestration_loop(default_args)

    # Assertions
    assert mock_application.handle_task_command.call_count == 6 # plan + aider*2 + analysis*2 + test
    aider_calls = [c for c in mock_application.handle_task_command.call_args_list if c.args[0] == 'aider:automatic']
    analysis_calls = [c for c in mock_application.handle_task_command.call_args_list if c.args[0] == 'user:analyze-aider-result']
    assert len(aider_calls) == 2
    assert len(analysis_calls) == 2
    mock_application.handle_query.assert_called_once() # Final analysis still runs
    assert excinfo.value.code == 1 # Overall failure
    mock_sys_exit.assert_called_once_with(1)

def test_run_orchestration_tests_fail(
    default_args, mock_application, mock_sys_exit, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
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

    with pytest.raises(SystemExit) as excinfo:
        run_orchestration_loop(default_args)

    # Assertions
    assert mock_application.handle_task_command.call_count == 4 # plan + aider + analysis + test
    mock_application.handle_query.assert_called_once()
    # Check final analysis prompt includes test failure info
    assert "Test Exit Code: 1" in mock_application.handle_query.call_args[0][0]
    assert "Test failed" in mock_application.handle_query.call_args[0][0]
    assert excinfo.value.code == 1 # Overall failure because tests failed
    mock_sys_exit.assert_called_once_with(1)

def test_run_orchestration_final_analysis_fails(
     default_args, mock_application, mock_sys_exit, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
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

    with pytest.raises(SystemExit) as excinfo:
        run_orchestration_loop(default_args)

    # Assertions
    assert mock_application.handle_task_command.call_count == 4 # plan + aider + analysis + test
    mock_application.handle_query.assert_called_once()
    assert excinfo.value.code == 1 # Overall failure
    mock_sys_exit.assert_called_once_with(1)

def test_run_orchestration_repo_path_invalid(
    default_args, mock_application, mock_sys_exit, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test script exits if repo path is invalid."""
    mock_os_path_isdir.return_value = False # Simulate invalid repo path
    with pytest.raises(SystemExit) as excinfo:
        run_orchestration_loop(default_args)
    mock_application.handle_task_command.assert_not_called() # Should exit early
    assert excinfo.value.code == 1
    mock_sys_exit.assert_called_once_with(1)

def test_run_orchestration_context_file_not_found(
    default_args, mock_application, mock_sys_exit, mock_os_path_exists, mock_os_path_isdir, mock_open_file, mock_logging
):
    """Test script exits if context file is not found."""
    mock_os_path_exists.side_effect = lambda path: path != '/mock/context.txt' # Only context file doesn't exist
    with pytest.raises(SystemExit) as excinfo:
        run_orchestration_loop(default_args)
    mock_application.handle_task_command.assert_not_called() # Should exit early
    assert excinfo.value.code == 1
    mock_sys_exit.assert_called_once_with(1)
