"""Unit tests for the Director-Evaluator Loop execution logic in the Evaluator component."""

import pytest
from unittest.mock import MagicMock, call, ANY, patch

from evaluator.evaluator import Evaluator, DEFAULT_MAX_ITERATIONS
from task_system.template_utils import Environment
from system.errors import (
    TaskError, 
    create_task_failure, 
    format_error_result, 
    SUBTASK_FAILURE, 
    UNEXPECTED_ERROR, 
    INPUT_VALIDATION_FAILURE
)

# Define type hints
from typing import Dict, Any, List, Optional, Iterator
TaskResult = Dict[str, Any]
EvaluationResult = Dict[str, Any]  # Alias for clarity

# --- Mock Recursive Eval Logic Helpers ---
MOCK_EVAL_RESULTS = {}  # Module-level store for mock results


def _configure_mock_eval(results_map: Dict[str, List[TaskResult]]):
    """Configure the side effects for the mocked eval."""
    global MOCK_EVAL_RESULTS
    MOCK_EVAL_RESULTS = {}
    for node_type, results in results_map.items():
        MOCK_EVAL_RESULTS[node_type] = iter(results)  # Use iterator


def _mock_recursive_eval(node: Any, env: Environment) -> TaskResult:
    """Mock function for recursive self.eval calls inside the loop."""
    global MOCK_EVAL_RESULTS
    node_type = getattr(node, 'type', 'unknown')

    if node_type in MOCK_EVAL_RESULTS:
        try:
            result = next(MOCK_EVAL_RESULTS[node_type])
            # Simulate adding env keys for verification in tests
            if "notes" not in result:
                result["notes"] = {}
            result["notes"]["_mock_received_env_keys"] = list(env.bindings.keys()) if env else []
            # Simulate script output structure if it's a script call result
            if node_type == "call" and getattr(node, 'template_name', '') == "system:run_script":
                if result.get("status") == "COMPLETE":
                    result["notes"]["scriptOutput"] = {
                        "stdout": result.get("content", "mock stdout"),
                        "stderr": result.get("notes", {}).get("stderr", ""),
                        "exit_code": result.get("notes", {}).get("exit_code", 0)
                    }
            return result
        except StopIteration:
            pytest.fail(f"Mock eval ran out of results for node type: {node_type}")
        except Exception as e:
            pytest.fail(f"Unexpected error in mock eval for {node_type}: {e}")
    else:
        # Default success result if not configured
        return {
            "status": "COMPLETE", 
            "content": f"Default mock result for {node_type}", 
            "notes": {"_mock_received_env_keys": list(env.bindings.keys()) if env else []}
        }


# --- Fixtures ---
@pytest.fixture
def mock_director_node():
    node = MagicMock(name="DirectorNode")
    node.type = "mock_director"  # Use distinct types for clarity in mocks
    return node


@pytest.fixture
def mock_evaluator_node():
    node = MagicMock(name="EvaluatorNode")
    node.type = "mock_evaluator"
    return node


@pytest.fixture
def mock_script_call_node():
    # Assumes script is called via <call>
    node = MagicMock(name="ScriptCallNode")
    node.type = "call"
    node.template_name = "system:run_script"
    # Add other necessary attributes if eval('call') expects them
    return node


@pytest.fixture
def mock_termination_condition_node():
    node = MagicMock(name="TerminationConditionNode")
    node.type = "termination_condition"
    # Use getattr for safe access in implementation
    node.condition_string = "evaluation.notes.success == true"
    return node


@pytest.fixture
def loop_node(mock_director_node, mock_evaluator_node, mock_script_call_node, mock_termination_condition_node):
    # Create the main loop node using the component fixtures
    node = MagicMock(name="DirectorEvaluatorLoopNode")
    node.type = "director_evaluator_loop"
    node.description = "Test Loop"
    node.max_iterations = 3  # Default max for tests
    node.director_node = mock_director_node
    node.evaluator_node = mock_evaluator_node
    node.script_execution_node = mock_script_call_node
    node.termination_condition_node = mock_termination_condition_node
    return node


@pytest.fixture
def initial_env():
    return Environment({"user_query": "Solve the problem."})


@pytest.fixture
def evaluator():
    # Instantiate the real Evaluator, mocking only recursive eval calls
    mock_template_provider = MagicMock()  # Mock dependency
    eval_instance = Evaluator(template_provider=mock_template_provider)
    # Patch the instance's evaluate method for mocking *recursive* calls
    eval_instance.evaluate = MagicMock(side_effect=lambda node, env: _mock_recursive_eval(node, env))
    # Patch the condition evaluator helper method on the instance
    eval_instance._evaluate_termination_condition = MagicMock(return_value=False)
    return eval_instance


class TestDirectorEvaluatorLoop:
    """Tests for the Director-Evaluator Loop execution logic."""

    def test_loop_success_on_evaluation(self, evaluator, loop_node, initial_env):
        """Test loop terminating successfully when evaluator returns success=True."""
        # Configure mocks for 2 iterations (evaluator success on iter 2)
        _configure_mock_eval({
            "mock_director": [
                {"status": "COMPLETE", "content": "Director iteration 1", "notes": {}},
                {"status": "COMPLETE", "content": "Director iteration 2", "notes": {}}
            ],
            "call": [
                {"status": "COMPLETE", "content": "Script output 1", "notes": {"stderr": "", "exit_code": 0}},
                {"status": "COMPLETE", "content": "Script output 2", "notes": {"stderr": "", "exit_code": 0}}
            ],
            "mock_evaluator": [
                {"status": "COMPLETE", "content": "Evaluator iteration 1", "notes": {"success": False, "feedback": "Not yet correct"}},
                {"status": "COMPLETE", "content": "Evaluator iteration 2", "notes": {"success": True, "feedback": "Success!"}}
            ]
        })
        
        # Set max_iterations high enough
        loop_node.max_iterations = 5
        
        # Execute the loop
        result = evaluator._evaluate_director_evaluator_loop(loop_node, initial_env)
        
        # Assertions
        assert result["status"] == "COMPLETE"
        assert result["content"] == "Director iteration 2"
        assert len(result["notes"]["iteration_history"]) == 2
        assert result["notes"]["final_evaluation"]["notes"]["success"] is True
        assert result["notes"]["final_evaluation"]["notes"]["feedback"] == "Success!"
        assert result["notes"]["iterations_completed"] == 2
        
        # Check call counts (2 iterations * 3 steps = 6 calls)
        assert evaluator.evaluate.call_count == 6

    def test_loop_reaches_max_iterations(self, evaluator, loop_node, initial_env):
        """Test loop terminating after reaching max_iterations without success."""
        # Configure mocks for 3 iterations (evaluator always returns success=False)
        _configure_mock_eval({
            "mock_director": [
                {"status": "COMPLETE", "content": "Director iteration 1", "notes": {}},
                {"status": "COMPLETE", "content": "Director iteration 2", "notes": {}},
                {"status": "COMPLETE", "content": "Director iteration 3", "notes": {}}
            ],
            "call": [
                {"status": "COMPLETE", "content": "Script output 1", "notes": {"stderr": "", "exit_code": 0}},
                {"status": "COMPLETE", "content": "Script output 2", "notes": {"stderr": "", "exit_code": 0}},
                {"status": "COMPLETE", "content": "Script output 3", "notes": {"stderr": "", "exit_code": 0}}
            ],
            "mock_evaluator": [
                {"status": "COMPLETE", "content": "Evaluator iteration 1", "notes": {"success": False, "feedback": "Not correct"}},
                {"status": "COMPLETE", "content": "Evaluator iteration 2", "notes": {"success": False, "feedback": "Still not correct"}},
                {"status": "COMPLETE", "content": "Evaluator iteration 3", "notes": {"success": False, "feedback": "Final attempt failed"}}
            ]
        })
        
        # Set max_iterations to 3
        loop_node.max_iterations = 3
        
        # Execute the loop
        result = evaluator._evaluate_director_evaluator_loop(loop_node, initial_env)
        
        # Assertions
        assert result["status"] == "COMPLETE"
        assert "reached max iterations" in result["content"].lower()
        assert len(result["notes"]["iteration_history"]) == 3
        assert result["notes"]["final_evaluation"]["notes"]["success"] is False
        assert result["notes"]["iterations_completed"] == 3
        assert result["notes"]["termination_reason"] == "max_iterations_reached"
        
        # Check call counts (3 iterations * 3 steps = 9 calls)
        assert evaluator.evaluate.call_count == 9

    def test_loop_early_termination_condition(self, evaluator, loop_node, initial_env):
        """Test loop terminating early due to a custom termination condition."""
        # Configure mocks for 2+ iterations (evaluator always returns success=False)
        _configure_mock_eval({
            "mock_director": [
                {"status": "COMPLETE", "content": "Director iteration 1", "notes": {}},
                {"status": "COMPLETE", "content": "Director iteration 2", "notes": {}}
            ],
            "call": [
                {"status": "COMPLETE", "content": "Script output 1", "notes": {"stderr": "", "exit_code": 0}},
                {"status": "COMPLETE", "content": "Script output 2", "notes": {"stderr": "", "exit_code": 0}}
            ],
            "mock_evaluator": [
                {"status": "COMPLETE", "content": "Evaluator iteration 1", "notes": {"success": False, "feedback": "Not correct"}},
                {"status": "COMPLETE", "content": "Evaluator iteration 2", "notes": {"success": False, "feedback": "Still not correct"}}
            ]
        })
        
        # Set termination condition
        loop_node.termination_condition_node.condition_string = "current_iteration >= 2"
        
        # Configure termination condition to return True on second call
        evaluator._evaluate_termination_condition.side_effect = [False, True]
        
        # Execute the loop
        result = evaluator._evaluate_director_evaluator_loop(loop_node, initial_env)
        
        # Assertions
        assert result["status"] == "COMPLETE"
        assert result["content"] == "Director iteration 2"
        assert len(result["notes"]["iteration_history"]) == 2
        assert result["notes"]["iterations_completed"] == 2
        
        # Check termination condition was called twice
        assert evaluator._evaluate_termination_condition.call_count == 2

    def test_loop_with_script_execution_data_pass(self, evaluator, loop_node, initial_env):
        """Test script execution results are correctly passed to evaluator step."""
        # Configure mocks for 1 iteration with specific script output
        script_stdout = "Script execution output"
        script_stderr = "Warning: some issue"
        script_exit_code = 0
        
        _configure_mock_eval({
            "mock_director": [
                {"status": "COMPLETE", "content": "Director output", "notes": {}}
            ],
            "call": [
                {
                    "status": "COMPLETE", 
                    "content": script_stdout, 
                    "notes": {
                        "stderr": script_stderr, 
                        "exit_code": script_exit_code
                    }
                }
            ],
            "mock_evaluator": [
                {"status": "COMPLETE", "content": "Evaluator output", "notes": {"success": True}}
            ]
        })
        
        # Execute the loop
        result = evaluator._evaluate_director_evaluator_loop(loop_node, initial_env)
        
        # Get the call arguments for the evaluator node evaluation
        evaluator_call = None
        for call_args in evaluator.evaluate.call_args_list:
            if call_args[0][0] == loop_node.evaluator_node:
                evaluator_call = call_args
                break
        
        assert evaluator_call is not None, "Evaluator node was not called"
        
        # Extract the environment passed to evaluator
        evaluator_env = evaluator_call[0][1]
        
        # Verify script output was passed to evaluator
        assert evaluator_env.find("script_stdout") == script_stdout
        assert evaluator_env.find("script_stderr") == script_stderr
        assert evaluator_env.find("script_exit_code") == script_exit_code
        
        # Verify the final result structure
        assert result["status"] == "COMPLETE"
        assert len(result["notes"]["iteration_history"]) == 1

    def test_data_flow_evaluator_to_next_director(self, evaluator, loop_node, initial_env):
        """Test evaluator feedback is correctly passed to the next director step."""
        # Configure mocks for 2 iterations with specific evaluator feedback
        feedback_message = "Fix the indentation in line 42"
        
        _configure_mock_eval({
            "mock_director": [
                {"status": "COMPLETE", "content": "Director iteration 1", "notes": {}},
                {"status": "COMPLETE", "content": "Director iteration 2", "notes": {}}
            ],
            "call": [
                {"status": "COMPLETE", "content": "Script output 1", "notes": {}},
                {"status": "COMPLETE", "content": "Script output 2", "notes": {}}
            ],
            "mock_evaluator": [
                {"status": "COMPLETE", "content": "Evaluator iteration 1", "notes": {"success": False, "feedback": feedback_message}},
                {"status": "COMPLETE", "content": "Evaluator iteration 2", "notes": {"success": True, "feedback": "Success!"}}
            ]
        })
        
        # Execute the loop
        result = evaluator._evaluate_director_evaluator_loop(loop_node, initial_env)
        
        # Find the call to the second director iteration
        director_calls = [call_args for call_args in evaluator.evaluate.call_args_list 
                         if call_args[0][0] == loop_node.director_node]
        
        assert len(director_calls) >= 2, "Director node should be called at least twice"
        second_director_call = director_calls[1]
        
        # Extract the environment passed to the second director call
        director_env = second_director_call[0][1]
        
        # Verify evaluator feedback was passed to the next director
        assert director_env.find("evaluation_feedback") == feedback_message
        assert director_env.find("evaluation_success") is False
        assert "last_evaluation" in director_env.bindings
        
        # Verify the final result structure
        assert result["status"] == "COMPLETE"
        assert len(result["notes"]["iteration_history"]) == 2

    def test_error_in_director_step(self, evaluator, loop_node, initial_env):
        """Test loop termination when director step fails."""
        # Configure director to fail
        director_error = create_task_failure("Director failed", "test_failure")
        director_error_result = format_error_result(director_error)
        
        _configure_mock_eval({
            "mock_director": [
                director_error_result
            ],
            # No need to configure script or evaluator as they won't be called
        })
        
        # Execute the loop
        result = evaluator._evaluate_director_evaluator_loop(loop_node, initial_env)
        
        # Assertions
        assert result["status"] == "FAILED"
        assert "failed during iteration 1" in result["content"]
        assert len(result["notes"]["iteration_history"]) == 1
        assert result["notes"]["iterations_completed"] == 0
        assert "error" in result["notes"]
        assert SUBTASK_FAILURE in result["notes"]["error"]["reason"]
        
        # Check call count (only director should be called)
        assert evaluator.evaluate.call_count == 1

    def test_error_in_script_step(self, evaluator, loop_node, initial_env):
        """Test loop termination when script step fails."""
        # Configure director to succeed but script to fail
        script_error = create_task_failure("Script execution failed", "test_failure")
        script_error_result = format_error_result(script_error)
        
        _configure_mock_eval({
            "mock_director": [
                {"status": "COMPLETE", "content": "Director output", "notes": {}}
            ],
            "call": [
                script_error_result
            ],
            # No need to configure evaluator as it won't be called
        })
        
        # Execute the loop
        result = evaluator._evaluate_director_evaluator_loop(loop_node, initial_env)
        
        # Assertions
        assert result["status"] == "FAILED"
        assert "failed during iteration 1" in result["content"]
        assert len(result["notes"]["iteration_history"]) == 1
        assert result["notes"]["iterations_completed"] == 0
        assert "error" in result["notes"]
        assert SUBTASK_FAILURE in result["notes"]["error"]["reason"]
        
        # Check call counts (director and script should be called)
        assert evaluator.evaluate.call_count == 2

    def test_error_in_evaluator_step(self, evaluator, loop_node, initial_env):
        """Test loop termination when evaluator step fails."""
        # Configure director and script to succeed but evaluator to fail
        evaluator_error = create_task_failure("Evaluator failed", "test_failure")
        evaluator_error_result = format_error_result(evaluator_error)
        
        _configure_mock_eval({
            "mock_director": [
                {"status": "COMPLETE", "content": "Director output", "notes": {}}
            ],
            "call": [
                {"status": "COMPLETE", "content": "Script output", "notes": {}}
            ],
            "mock_evaluator": [
                evaluator_error_result
            ]
        })
        
        # Execute the loop
        result = evaluator._evaluate_director_evaluator_loop(loop_node, initial_env)
        
        # Assertions
        assert result["status"] == "FAILED"
        assert "failed during iteration 1" in result["content"]
        assert len(result["notes"]["iteration_history"]) == 1
        assert result["notes"]["iterations_completed"] == 0
        assert "error" in result["notes"]
        assert SUBTASK_FAILURE in result["notes"]["error"]["reason"]
        
        # Check call counts (director, script, and evaluator should be called)
        assert evaluator.evaluate.call_count == 3

    def test_missing_required_nodes(self, evaluator, loop_node, initial_env):
        """Test validation of required nodes (director and evaluator)."""
        # Create a loop node missing the required nodes
        incomplete_loop_node = MagicMock(name="IncompleteLoopNode")
        incomplete_loop_node.type = "director_evaluator_loop"
        incomplete_loop_node.description = "Incomplete Loop"
        incomplete_loop_node.max_iterations = 3
        incomplete_loop_node.director_node = None  # Missing director
        incomplete_loop_node.evaluator_node = loop_node.evaluator_node
        
        # Execute the loop
        result = evaluator._evaluate_director_evaluator_loop(incomplete_loop_node, initial_env)
        
        # Assertions
        assert result["status"] == "FAILED"
        assert "missing director or evaluator definition" in result["content"].lower()
        assert INPUT_VALIDATION_FAILURE in result["notes"]["error"]["reason"]
        
        # No eval calls should be made
        assert evaluator.evaluate.call_count == 0
        
        # Test with missing evaluator
        incomplete_loop_node.director_node = loop_node.director_node
        incomplete_loop_node.evaluator_node = None
        
        # Execute the loop
        result = evaluator._evaluate_director_evaluator_loop(incomplete_loop_node, initial_env)
        
        # Assertions
        assert result["status"] == "FAILED"
        assert "missing director or evaluator definition" in result["content"].lower()

    def test_loop_without_script_node(self, evaluator, loop_node, initial_env):
        """Test loop execution without a script node."""
        # Configure loop without script node
        loop_node.script_execution_node = None
        
        # Configure mocks for 1 iteration
        _configure_mock_eval({
            "mock_director": [
                {"status": "COMPLETE", "content": "Director output", "notes": {}}
            ],
            "mock_evaluator": [
                {"status": "COMPLETE", "content": "Evaluator output", "notes": {"success": True}}
            ]
        })
        
        # Execute the loop
        result = evaluator._evaluate_director_evaluator_loop(loop_node, initial_env)
        
        # Assertions
        assert result["status"] == "COMPLETE"
        assert len(result["notes"]["iteration_history"]) == 1
        
        # Check call counts (only director and evaluator should be called, no script)
        assert evaluator.evaluate.call_count == 2
        
        # Verify the calls were only to director and evaluator
        call_nodes = [call_args[0][0] for call_args in evaluator.evaluate.call_args_list]
        assert loop_node.director_node in call_nodes
        assert loop_node.evaluator_node in call_nodes

    def test_evaluator_missing_success_field(self, evaluator, loop_node, initial_env):
        """Test handling of evaluator result missing the required success field."""
        # Configure mocks with evaluator missing success field
        _configure_mock_eval({
            "mock_director": [
                {"status": "COMPLETE", "content": "Director output", "notes": {}}
            ],
            "call": [
                {"status": "COMPLETE", "content": "Script output", "notes": {}}
            ],
            "mock_evaluator": [
                {"status": "COMPLETE", "content": "Evaluator output", "notes": {}}  # Missing success field
            ]
        })
        
        # Execute the loop
        result = evaluator._evaluate_director_evaluator_loop(loop_node, initial_env)
        
        # Assertions
        assert result["status"] == "COMPLETE"
        assert "reached max iterations" in result["content"].lower()
        
        # Check that success was defaulted to False
        assert result["notes"]["final_evaluation"]["notes"]["success"] is False
        assert "feedback" in result["notes"]["final_evaluation"]["notes"]

    def test_unexpected_exception_handling(self, evaluator, loop_node, initial_env):
        """Test handling of unexpected exceptions during loop execution."""
        # Make evaluate throw an exception on the second call
        def side_effect(node, env):
            if evaluator.evaluate.call_count == 2:  # Second call (script execution)
                raise RuntimeError("Unexpected runtime error")
            return _mock_recursive_eval(node, env)
        
        evaluator.evaluate.side_effect = side_effect
        
        # Configure mocks for normal execution
        _configure_mock_eval({
            "mock_director": [
                {"status": "COMPLETE", "content": "Director output", "notes": {}}
            ],
            # No need to configure script or evaluator as exception will occur
        })
        
        # Execute the loop
        result = evaluator._evaluate_director_evaluator_loop(loop_node, initial_env)
        
        # Assertions
        assert result["status"] == "FAILED"
        assert "unexpected error in loop iteration" in result["content"].lower()
        assert len(result["notes"]["iteration_history"]) == 1
        assert "error" in result["notes"]["iteration_history"][0]
        assert UNEXPECTED_ERROR in result["notes"]["error"]["reason"]
