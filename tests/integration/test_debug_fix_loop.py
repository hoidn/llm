import pytest
from unittest.mock import patch, MagicMock, call
import subprocess
import json
import os
import shutil
import shlex
from pathlib import Path
from typing import Dict, Any

# Assume imports for application components exist, adjust paths as needed
# Example: from src.main import Application
# Example: from src.dispatcher import execute_programmatic_task
# Example: from src.memory.context_generation import AssociativeMatchResult # Or relevant structure

# --- Placeholder Imports (Replace with actuals) ---
# These are placeholders, replace with your actual application structure
class Application: # Placeholder
    def __init__(self):
        self.task_system = MagicMock()
        self.passthrough_handler = MagicMock()
        self.memory_system = MagicMock()
        self.aider_bridge = MagicMock()
        # Mock methods needed by tests
        self.memory_system.get_relevant_context_for.return_value = MagicMock(matches=[])
        self.aider_bridge.execute_automatic_task.return_value = {"status": "COMPLETE", "content": "Mock Aider success"}

def execute_programmatic_task(identifier, params, flags, handler_instance, task_system_instance, **kwargs) -> Dict[str, Any]: # Placeholder
     # In a real test, this would invoke the actual dispatcher logic
     # For this placeholder, we might need to simulate parts of it if Application isn't fully functional
     print(f"Placeholder execute_programmatic_task called for: {identifier}")
     # Simulate finding the template and calling evaluator
     template = task_system_instance.find_template(identifier)
     if template and hasattr(task_system_instance, 'evaluator') and hasattr(task_system_instance.evaluator, 'evaluate'):
         from src.task_system.template_utils import Environment # Assuming this exists
         env = Environment(params)
         # This is a simplification; real dispatcher does more setup
         return task_system_instance.evaluator.evaluate(template, env)
     return {"status": "FAILED", "content": f"Placeholder cannot execute {identifier}"}

class AssociativeMatchResult: # Placeholder
     def __init__(self, matches=None, context=""):
         self.matches = matches if matches is not None else []
         self.context = context
# --- End Placeholder Imports ---


# Define TaskResult type hint if not imported
TaskResult = Dict[str, Any]


@pytest.fixture
def test_files(tmp_path: Path):
    """Creates sample source and test files in a temp directory."""
    src_file = tmp_path / "calculator.py"
    test_file = tmp_path / "test_calculator.py"

    # Initial failing code
    src_file.write_text("def add(a, b):\n    return a - b # Bug!\n")
    # Test that will fail with the bug
    test_file.write_text(
        "import pytest\nfrom calculator import add\n\n"
        "def test_add_positive():\n    assert add(2, 3) == 5\n\n"
        # Add a test that passes initially if needed for other scenarios
        "def test_add_zero():\n    assert add(0, 0) == 0\n"
    )
    # Optional: git init and commit (uncomment if needed)
    # try:
    #     subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    #     subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True, text=True)
    #     # Configure dummy user for commit if running in CI/clean env
    #     subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    #     subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    #     subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True, capture_output=True, text=True)
    # except (subprocess.CalledProcessError, FileNotFoundError) as e:
    #      pytest.skip(f"Git operations skipped: {e}")

    return {"src": src_file, "test": test_file, "dir": tmp_path}

@pytest.fixture
def app_instance(test_files, mocker):
    """Creates an Application instance pointing to the temp directory."""
    # IMPORTANT: Ensure real API keys are available in the environment for LLM tests
    # e.g., export OPENAI_API_KEY=sk-... or ANTHROPIC_API_KEY=...
    # Mock components that should NOT make external calls unless intended
    mocker.patch('src.main.register_aider_templates') # Avoid issues if Aider isn't fully mocked/available
    # Use the correct import path as used in src/main.py
    mocker.patch('task_system.templates.associative_matching.register_template')
    # mocker.patch('src.main.register_debug_templates') # Keep this if testing template loading

    # --- Crucially, import the *real* components needed for the loop ---
    # This assumes your Application structure allows selective component use/mocking
    # You might need to adjust based on how Application.__init__ works
    try:
        from src.main import Application
        from src.task_system.task_system import TaskSystem
        from src.evaluator.evaluator import Evaluator
        from src.handler.passthrough_handler import PassthroughHandler # Needed for tools like run_script
        from src.memory.memory_system import MemorySystem
        # Import bridge only if needed and intended for real calls/mocking specific methods
        # from src.aider_bridge.bridge import AiderBridge
    except ImportError as e:
        pytest.skip(f"Skipping integration test due to missing component: {e}")


    original_cwd = os.getcwd()
    os.chdir(test_files["dir"])

    # Instantiate real components needed for the test flow
    # We will mock specific methods that interact externally (subprocess, aider exec)
    app = Application() # Assuming this sets up TaskSystem, Handler, MemorySystem, Evaluator

    # Ensure evaluator is linked if not done in App init
    if not hasattr(app.task_system, 'evaluator'):
         app.task_system.evaluator = Evaluator(app.task_system) # Link evaluator

    # Mock system:run_script executor if it's registered as a direct tool
    # This prevents actual subprocess calls unless specifically intended
    if hasattr(app.passthrough_handler, 'direct_tool_executors') and "system:run_script" in app.passthrough_handler.direct_tool_executors:
         mocker.patch.dict(app.passthrough_handler.direct_tool_executors, {"system:run_script": MagicMock()})
         print("Mocked system:run_script direct tool executor.")


    # Optional: Index if memory system is used and not mocked sufficiently
    # try:
    #     app.index_repository(str(test_files["dir"]))
    # except Exception as e:
    #     print(f"Warning: Indexing failed in test setup: {e}")

    yield app # Provide the app instance to the test

    os.chdir(original_cwd) # Change back directory

# ---- Mock Fixtures ----

@pytest.fixture
def mock_run_script_tool(app_instance, mocker):
    """
    Mocks the system:run_script tool execution result within the handler.
    This is crucial to control test success/failure cycles.
    """
    # Find the actual executor function registered for the tool
    # This assumes it's registered via registerDirectTool
    if hasattr(app_instance.passthrough_handler, 'direct_tool_executors') and "system:run_script" in app_instance.passthrough_handler.direct_tool_executors:
        # Patch the *specific executor function* bound to the tool name
        # The lambda makes this tricky, patching the source might be easier if known
        # Alternative: Patch subprocess.run if run_script uses it directly
        mock_subp = mocker.patch('subprocess.run')
        print("Patched subprocess.run for run_script simulation.")

        def configure_mock(side_effect_list):
            mock_subp.side_effect = side_effect_list
            # Need to return a TaskResult structure matching system:run_script's output
            def mock_executor_func(params):
                 # Simulate calling subprocess.run and formatting the result
                 command = params.get("command", "")
                 print(f"Mock system:run_script executing: {command}")
                 try:
                     # Call the mocked subprocess.run to get the configured side effect
                     result = mock_subp(shlex.split(command), capture_output=True, text=True, check=False) # Use configured side effect
                     print(f"Mock subprocess result: rc={result.returncode}, stdout={result.stdout[:50]}..., stderr={result.stderr[:50]}...")
                     return {
                         "status": "COMPLETE",
                         "content": f"Executed: {command}",
                         "notes": {
                             "scriptOutput": {
                                 "stdout": result.stdout,
                                 "stderr": result.stderr,
                                 "exit_code": result.returncode
                             }
                         }
                     }
                 except Exception as e:
                      print(f"Error in mock executor: {e}")
                      return {"status": "FAILED", "content": str(e)}

            # Re-register the tool with our mock executor function
            app_instance.passthrough_handler.registerDirectTool("system:run_script", mock_executor_func)
            print("Re-registered system:run_script with mock executor.")
            return mock_subp # Return the subprocess mock for assertion checks

        return configure_mock # Return the function that configures the mock
    else:
        pytest.skip("system:run_script tool not found or not registered as expected.")


@pytest.fixture
def mock_memory_lookup(mocker, app_instance, test_files):
    """Mocks MemorySystem context lookup to return the source file."""
    # Ensure memory_system exists on the app instance
    if not hasattr(app_instance, 'memory_system'):
         pytest.skip("Application instance does not have memory_system attribute.")

    mock_lookup = mocker.patch.object(app_instance.memory_system, 'get_relevant_context_for')

    # Simulate finding the source file based on a (mocked) error query
    # Use relative path as that's likely what indexers store/tools expect
    relative_src_path = str(test_files["src"].relative_to(test_files["dir"]))
    mock_lookup.return_value = AssociativeMatchResult(
         matches=[(relative_src_path, "Simulated match based on error", 0.9)],
         context=f"Content of {relative_src_path}" # Optional: Add mock content
    )
    print(f"Mocked memory_system.get_relevant_context_for to return: {relative_src_path}")
    return mock_lookup

@pytest.fixture
def mock_aider_execution(mocker, app_instance, test_files):
    """Mocks AiderBridge task execution (aider:automatic)."""
     # Ensure aider_bridge exists on the app instance
    if not hasattr(app_instance, 'aider_bridge'):
         pytest.skip("Application instance does not have aider_bridge attribute.")

    mock_exec = mocker.patch.object(app_instance.aider_bridge, 'execute_automatic_task')
    relative_src_path = str(test_files["src"].relative_to(test_files["dir"]))

    # Default: Simulate successful application
    mock_exec.return_value = {
        "status": "COMPLETE",
        "content": "Simulated fix applied by Aider.",
        "notes": {"files_modified": [relative_src_path]} # Use relative path
    }
    print(f"Mocked aider_bridge.execute_automatic_task to return success for: {relative_src_path}")
    return mock_exec


# ---- Test Cases ----

# @pytest.mark.llm # Uncomment if OPENAI_API_KEY or ANTHROPIC_API_KEY is set and real LLM calls are desired
@pytest.mark.integration # General integration test marker
def test_loop_success_after_fix(
    app_instance,
    test_files,
    mock_run_script_tool, # Use the fixture to configure subprocess mock
    mock_memory_lookup,
    mock_aider_execution,
    mocker # pytest-mock fixture
):
    """
    Tests the loop failing once, then succeeding after a simulated fix.
    Uses real LLM calls for analysis and fix generation by default.
    Mocks subprocess (test execution) and Aider (fix application).
    """
    # ---- Arrange Mocks ----
    import shlex # Needed for mock_run_script_tool setup

    # 1. Configure mock_run_script_tool: Fail first, then succeed
    # Use the configure function returned by the fixture
    subprocess_mock = mock_run_script_tool([
        # First run (fails) - Provide realistic pytest output
        MagicMock(
            returncode=1,
            stdout="== test session starts ==\ncollecting ... collected 2 items\n\ntest_calculator.py::test_add_positive FAILED [ 50%]\ntest_calculator.py::test_add_zero PASSED [100%]\n\n=========================== FAILURES ===========================\n_______________________ test_add_positive ________________________\n\n    def test_add_positive():\n>       assert add(2, 3) == 5\nE       assert -1 == 5\nE        +  where -1 = add(2, 3)\n\ncalculator.py:2: AssertionError\n================ short test summary info ================\nFAILED test_calculator.py::test_add_positive - assert -1 == 5\n== 1 failed, 1 passed in 0.03s ==",
            stderr="" # Pytest often puts failures in stdout
        ),
        # Second run (after simulated fix - passes)
        MagicMock(returncode=0, stdout="== test session starts ==\ncollecting ... collected 2 items\n\ntest_calculator.py::test_add_positive PASSED [ 50%]\ntest_calculator.py::test_add_zero PASSED [100%]\n\n================= 2 passed in 0.01s ==================", stderr="")
    ])


    # mock_memory_lookup is set by fixture to return calculator.py
    # mock_aider_execution is set by fixture to simulate success

    # ---- Act ----
    # Use dispatcher to run the task
    # Ensure dispatcher is imported correctly
    try:
        from src.dispatcher import execute_programmatic_task
    except ImportError:
        pytest.skip("Dispatcher function not found.")

    # Prepare parameters for the dispatcher
    test_command = f"pytest {test_files['test'].name}"
    target_files_json = json.dumps([]) # Empty list for this test

    print(f"\nExecuting debug:loop task with command: '{test_command}'")
    result = execute_programmatic_task(
        identifier="debug:loop",
        params={
            "test_cmd": test_command,
            "target_files": target_files_json
            # Use default max_cycles=3
        },
        flags={}, # No flags needed for this test
        # Pass the real, instantiated components from the app
        handler_instance=app_instance.passthrough_handler,
        task_system_instance=app_instance.task_system
        # Pass memory_system, etc. if dispatcher needs them directly (depends on dispatcher impl)
    )

    # ---- Assert ----
    print("\nFinal Result:", json.dumps(result, indent=2)) # Debug output

    # 1. Final Status & Iterations
    assert result is not None, "Dispatcher returned None"
    assert 'status' in result, "Result missing 'status' key"
    assert result['status'] == 'COMPLETE', f"Expected status COMPLETE, got {result['status']}"
    assert 'notes' in result, "Result missing 'notes' key"
    assert result['notes'].get('iterations_completed') == 2, f"Expected 2 iterations, got {result['notes'].get('iterations_completed')}"
    final_eval = result['notes'].get('final_evaluation', {})
    assert final_eval.get('notes', {}).get('success') is True, "Final evaluation success was not True"

    # 2. Orchestration Checks (Mock Calls)
    assert subprocess_mock.call_count == 2, f"Expected subprocess.run to be called twice, got {subprocess_mock.call_count}" # Tests run twice
    mock_memory_lookup.assert_called_once() # Context lookup happened once after failure

    # Check context query *content* if desired (might be fragile)
    # Example: Check if the error message was used in the query
    # query_arg = mock_memory_lookup.call_args[0][0] # Assuming first arg is ContextGenerationInput or similar
    # assert "AssertionError" in query_arg.get('query', ''), "Context query did not contain expected error"

    mock_aider_execution.assert_called_once() # Aider applied fix once
    # Check arguments passed to Aider
    aider_call_args = mock_aider_execution.call_args
    # Note: Exact LLM fix output is non-deterministic, so don't assert aider_call_args[0][0] (prompt)
    # Assert file context was passed correctly (as list)
    relative_src_path = str(test_files["src"].relative_to(test_files["dir"]))
    assert aider_call_args[1]['file_context'] == [relative_src_path], f"Aider called with incorrect file context: {aider_call_args[1]['file_context']}"

    # 3. Check data propagation in notes (optional but useful)
    assert 'iteration_history' in result['notes'], "Missing 'iteration_history' in notes"
    assert len(result['notes']['iteration_history']) == 2, "Incorrect number of iterations in history"
    # Check director step result from the *second* iteration (index 1) contains aider result
    # The director runs *after* the failure in the *first* iteration, leading to the second iteration's script run.
    # So, the aider result should be part of the director's output in the *first* iteration history entry.
    first_iter_director_result = result['notes']['iteration_history'][0].get('director', {})
    assert first_iter_director_result.get('notes', {}).get('files_modified') == [relative_src_path], "Aider modification notes not found in director result"

# --- Add other test cases ---
# @pytest.mark.integration
# def test_loop_success_first_try(...): ...

# @pytest.mark.integration
# def test_loop_failure_max_cycles(...): ...

# @pytest.mark.integration
# def test_loop_failure_aider_error(...):
#     # Configure mock_aider_execution to return status: FAILED
#     mock_aider_execution.return_value = {"status": "FAILED", "content": "Aider failed"}
#     # ... rest of test setup and assertions ...

# @pytest.mark.integration
# def test_loop_with_target_files(...):
#     # Pass target_files param: json.dumps([str(test_files['src'].relative_to(test_files['dir']))])
#     # Assert mock_memory_lookup was called with the correct target_files list
#     # ... rest of test setup and assertions ...
