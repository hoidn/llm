"""Tests for the Evaluator component."""
import pytest
import json
from unittest.mock import MagicMock, patch

from task_system.ast_nodes import ArgumentNode, FunctionCallNode
from task_system.template_utils import Environment
from system.errors import TaskError, INPUT_VALIDATION_FAILURE, SUBTASK_FAILURE
from evaluator.evaluator import Evaluator
from evaluator.interfaces import TemplateLookupInterface

class MockTemplateLookup(TemplateLookupInterface):
    """Mock implementation of TemplateLookupInterface for testing."""
    
    def __init__(self):
        """Initialize with test templates."""
        self.templates = {
            "test_template": {
                "name": "test_template",
                "type": "atomic",
                "subtype": "test",
                "parameters": {
                    "param1": {"type": "string", "required": True},
                    "param2": {"type": "number", "default": 42}
                }
            }
        }
        
        # Mock for execute_task to return a test result
        self._execute_task_result = {
            "content": "Executed template with param1=test_value, param2=42",
            "status": "COMPLETE",
            "notes": {}
        }
        
        # Mock to track calls
        self.execute_task_calls = []
        self.find_template_calls = []
    
    def find_template(self, identifier: str):
        """Find a template by name."""
        self.find_template_calls.append(identifier)
        return self.templates.get(identifier)
    
    def execute_task(self, task_type, task_subtype, inputs):
        """Execute a task (mock implementation)."""
        self.execute_task_calls.append((task_type, task_subtype, inputs))
        return self._execute_task_result


class TestEvaluator:
    """Tests for the Evaluator class."""
    
    @pytest.fixture
    def template_provider(self):
        """Create a mock template provider."""
        return MockTemplateLookup()
    
    @pytest.fixture
    def evaluator(self, template_provider):
        """Create an Evaluator instance."""
        return Evaluator(template_provider)
    
    @pytest.fixture
    def base_environment(self):
        """Create a base environment with some variables."""
        return Environment({
            "var1": "test_value",
            "var2": 42,
            "nested": {"key": "value"}
        })
    
    def test_evaluator_initialization(self, evaluator, template_provider):
        """Test Evaluator initialization."""
        assert evaluator.template_provider == template_provider
    
    def test_evaluate_function_call_basic(self, evaluator, template_provider, base_environment):
        """Test basic function call evaluation."""
        # Create a function call node
        args = [
            ArgumentNode("{{var1}}"),  # Variable reference
            ArgumentNode(99, name="param2")  # Named argument
        ]
        func_call = FunctionCallNode("test_template", args)
        
        # Evaluate the function call
        result = evaluator.evaluateFunctionCall(func_call, base_environment)
        
        # Verify template was looked up
        assert "test_template" in template_provider.find_template_calls
        
        # Verify result
        assert result["content"] == "Executed template with param1=test_value, param2=42"
        assert result["status"] == "COMPLETE"
        
        # Verify task execution
        assert len(template_provider.execute_task_calls) == 1
        call_args = template_provider.execute_task_calls[0]
        assert call_args[0] == "atomic"  # task_type
        assert call_args[1] == "test"    # task_subtype
        
        # Verify inputs contain the evaluated arguments
        inputs = call_args[2]
        assert inputs["param1"] == "test_value"  # Resolved from var1
        assert inputs["param2"] == 99            # Direct value
    
    def test_evaluate_variable_references(self, evaluator, base_environment):
        """Test evaluating variable references in arguments."""
        # Create arguments with variable references
        args = [
            ArgumentNode("{{var1}}"),
            ArgumentNode("{{var2}}"),
            ArgumentNode("{{var2}}", name="named_arg")
        ]
        
        # Evaluate arguments
        pos_args, named_args = evaluator._evaluate_arguments(args, base_environment)
        
        # Verify variable resolution
        assert pos_args[0] == "test_value"  # var1
        assert pos_args[1] == 42            # var2
        assert named_args["named_arg"] == 42  # var2
    
    def test_template_not_found(self, evaluator, base_environment):
        """Test error handling when template is not found."""
        # Create function call node for nonexistent template
        func_call = FunctionCallNode("nonexistent_template", [])
        
        # Evaluate should raise TaskError
        with pytest.raises(TaskError) as excinfo:
            evaluator.evaluateFunctionCall(func_call, base_environment)
        
        # Check error message and details
        assert "Template not found" in str(excinfo.value)
        assert "nonexistent_template" in str(excinfo.value)
        assert excinfo.value.reason == "input_validation_failure"
        assert "template_name" in excinfo.value.details
    
    def test_missing_required_parameter(self, evaluator, base_environment):
        """Test error handling when a required parameter is missing."""
        # Create function call with missing required parameter
        func_call = FunctionCallNode("test_template", [])  # No arguments, but param1 is required
        
        # Evaluate should raise TaskError
        with pytest.raises(TaskError) as excinfo:
            evaluator.evaluateFunctionCall(func_call, base_environment)
        
        # Check error details
        assert "Error binding arguments" in str(excinfo.value)
        assert "test_template" in str(excinfo.value)
        assert excinfo.value.reason == INPUT_VALIDATION_FAILURE
    
    def test_unknown_variable(self, evaluator, base_environment):
        """Test error handling when a variable reference can't be resolved."""
        # Create function call with unknown variable
        args = [ArgumentNode("{{unknown_var}}")]
        func_call = FunctionCallNode("test_template", args)
        
        # Evaluate should raise TaskError
        with pytest.raises(TaskError) as excinfo:
            evaluator.evaluateFunctionCall(func_call, base_environment)
        
        # Check error details
        assert "Error resolving variable" in str(excinfo.value)
        assert "unknown_var" in str(excinfo.value)
        assert excinfo.value.reason == INPUT_VALIDATION_FAILURE
        assert "variable_name" in excinfo.value.details
    
    def test_evaluate_generic_node(self, evaluator, base_environment):
        """Test evaluating a generic node (not a function call)."""
        # Call evaluate with a non-AST node (just a regular value)
        result = evaluator.evaluate("test string", base_environment)
        
        # Should return the value unchanged
        assert result == "test string"
        
        # Test with a number
        assert evaluator.evaluate(42, base_environment) == 42
        
        # Test with a dict
        test_dict = {"key": "value"}
        assert evaluator.evaluate(test_dict, base_environment) == test_dict
        
    def test_evaluate_argument_with_complex_references(self):
        """Test evaluating arguments with complex reference patterns."""
        # Create test environment
        env = Environment({
            "items": [1, 2, 3, 4, 5],
            "results": [{"name": "first"}, {"name": "second"}],
            "nested": {"key": {"subkey": "value"}}
        })
        
        # Create evaluator
        evaluator = Evaluator(MagicMock())
        
        # Test array indexing in arguments
        arg1 = ArgumentNode("items[0]")
        assert evaluator._evaluate_argument(arg1, env) == 1
        
        # Test nested object access
        arg2 = ArgumentNode("nested.key.subkey")
        assert evaluator._evaluate_argument(arg2, env) == "value"
        
        # Test combined patterns
        arg3 = ArgumentNode("results[1].name")
        assert evaluator._evaluate_argument(arg3, env) == "second"
        
        # Test with explicit variable reference syntax
        arg4 = ArgumentNode("{{items[0]}}")
        assert evaluator._evaluate_argument(arg4, env) == 1
        
        # Test fallback to literal for non-existent variables
        arg5 = ArgumentNode("nonexistent[0]")
        assert evaluator._evaluate_argument(arg5, env) == "nonexistent[0]"
    
    def test_integration_with_task_system(self):
        """Test integration between Evaluator and TaskSystem."""
        # Import components
        from task_system.task_system import TaskSystem
        from evaluator.evaluator import Evaluator
        
        # Create instances with proper dependency injection
        task_system = TaskSystem()
        evaluator = Evaluator(task_system)
        task_system.evaluator = evaluator
        
        # Mock the find_template method
        task_system.find_template = MagicMock(return_value={
            "name": "test_template",
            "type": "atomic",
            "subtype": "test",
            "parameters": {}
        })
        
        # Mock the execute_task method
        task_system.execute_task = MagicMock(return_value={
            "content": "Executed from task system",
            "status": "COMPLETE"
        })
        
        # Create a function call
        func_call = FunctionCallNode("test_template", [])
        env = Environment({})
        
        # Execute the call through TaskSystem's executeCall
        result = task_system.executeCall(func_call, env)
        
        # Verify the result
        assert result["content"] == "Executed from task system"
        assert result["status"] == "COMPLETE"
        
        # Verify task_system.find_template was called
        task_system.find_template.assert_called_once_with("test_template")
        
        # Verify task_system.execute_task was called
        task_system.execute_task.assert_called_once()


# --- Tests for Step Execution ---

class TestStepExecution:
    """Tests for the _execute_steps method and step handling in evaluate."""

    @pytest.fixture
    def mock_template_provider(self):
        provider = MagicMock(spec=TemplateLookupInterface)
        provider.find_template.side_effect = lambda name: {"name": name, "parameters": {}} if name != "not_found" else None
        return provider

    @pytest.fixture
    def evaluator(self, mock_template_provider):
        eval = Evaluator(mock_template_provider)
        # Mock evaluateFunctionCall directly on the instance for step tests
        eval.evaluateFunctionCall = MagicMock()
        return eval

    @pytest.fixture
    def base_environment(self):
        return Environment({"initial_var": "value"})

    def test_execute_steps_basic_sequence(self, evaluator, base_environment):
        """Test executing a simple sequence of steps."""
        steps = [
            {"type": "call", "template": "step1", "arguments": [], "bind_result_to": "res1"},
            {"type": "call", "template": "step2", "arguments": [{"name": "input", "value": "{{res1.content}}"}]}
        ]
        # Mock results for each step call
        evaluator.evaluateFunctionCall.side_effect = [
            {"status": "COMPLETE", "content": "Result Step 1", "notes": {}},
            {"status": "COMPLETE", "content": "Result Step 2", "notes": {}}
        ]

        final_result = evaluator._execute_steps(steps, base_environment)

        assert final_result["status"] == "COMPLETE"
        assert final_result["content"] == "Result Step 2"
        assert evaluator.evaluateFunctionCall.call_count == 2

        # Check environment passed to step 2 contains result of step 1
        call_args_step2 = evaluator.evaluateFunctionCall.call_args_list[1]
        env_step2 = call_args_step2[0][1] # Environment is the second positional arg
        assert env_step2.find("res1")["content"] == "Result Step 1"
        # Check argument was evaluated correctly for step 2 call node
        call_node_step2 = call_args_step2[0][0] # Call node is the first positional arg
        assert call_node_step2.arguments[0].value == "{{res1.content}}" # Arg value before evaluation

    def test_execute_steps_failure_stops_sequence(self, evaluator, base_environment):
        """Test that sequence stops if a step fails."""
        steps = [
            {"type": "call", "template": "step1", "arguments": [], "bind_result_to": "res1"},
            {"type": "call", "template": "step2_fails", "arguments": []},
            {"type": "call", "template": "step3_skipped", "arguments": []}
        ]
        evaluator.evaluateFunctionCall.side_effect = [
            {"status": "COMPLETE", "content": "Result Step 1", "notes": {}},
            {"status": "FAILED", "content": "Step 2 Error", "notes": {"reason": "test_fail"}}
        ]

        final_result = evaluator._execute_steps(steps, base_environment)

        assert final_result["status"] == "FAILED"
        assert final_result["content"] == "Step 2 Error"
        assert final_result["notes"]["sequence_failure_step"] == 2
        assert evaluator.evaluateFunctionCall.call_count == 2 # Step 3 should not be called

    def test_execute_steps_template_not_found(self, evaluator, base_environment):
        """Test sequence failure if a step's template isn't found."""
        steps = [
            {"type": "call", "template": "step1", "arguments": []},
            {"type": "call", "template": "not_found", "arguments": []}
        ]
        evaluator.evaluateFunctionCall.side_effect = [
            {"status": "COMPLETE", "content": "Result Step 1", "notes": {}}
        ]
        # find_template mock already configured to return None for "not_found"

        final_result = evaluator._execute_steps(steps, base_environment)

        assert final_result["status"] == "FAILED"
        assert "Template 'not_found' not found" in final_result["content"]
        assert final_result["notes"]["failed_template"] == "not_found"
        assert evaluator.evaluateFunctionCall.call_count == 1 # Only step 1 called

    def test_evaluate_calls_execute_steps_for_template_with_steps(self, evaluator, base_environment):
        """Test that the main evaluate method routes to _execute_steps."""
        template_with_steps = {
            "name": "template_with_steps",
            "steps": [
                {"type": "call", "template": "sub_step1"}
            ]
        }
        # Mock find_template to return this template
        evaluator.template_provider.find_template.return_value = template_with_steps
        # Mock _execute_steps to check if it was called
        evaluator._execute_steps = MagicMock(return_value={"status": "COMPLETE", "content": "Steps executed"})

        # Evaluate using a FunctionCallNode referencing the template
        call_node = FunctionCallNode("template_with_steps", [])
        result = evaluator.evaluate(call_node, base_environment)

        assert result["content"] == "Steps executed"
        evaluator._execute_steps.assert_called_once_with(template_with_steps['steps'], base_environment)
        # Ensure evaluateFunctionCall wasn't called directly for the outer node
        evaluator.evaluateFunctionCall.assert_not_called()


class TestDirectorEvaluatorLoop:
    """Tests for the Director-Evaluator loop functionality in Evaluator."""
    @pytest.fixture
    def mock_template_provider(self):
        """Create a mock template provider."""
        return MagicMock(spec=TemplateLookupInterface)
    
    @pytest.fixture
    def evaluator(self, mock_template_provider):
        """Create an Evaluator instance with mocked dependencies."""
        return Evaluator(mock_template_provider)
    
    @pytest.fixture
    def base_environment(self):
        """Create a base environment for testing."""
        return Environment({
            "test_var": "test_value",
            "history": "previous conversation"
        })
    
    @pytest.fixture
    def mock_director_node(self):
        """Create a mock director node."""
        node = MagicMock()
        node.type = "call"
        node.template_name = "test:director"
        return node
    
    @pytest.fixture
    def mock_evaluator_node(self):
        """Create a mock evaluator node."""
        node = MagicMock()
        node.type = "call"
        node.template_name = "debug:analyze_test_results"
        return node
    
    @pytest.fixture
    def mock_script_node(self):
        """Create a mock script execution node."""
        node = MagicMock()
        node.type = "call"
        node.template_name = "system:run_script"
        return node
    
    @pytest.fixture
    def mock_loop_node(self, mock_director_node, mock_evaluator_node, mock_script_node):
        """Create a mock director_evaluator_loop node."""
        node = MagicMock()
        node.type = "director_evaluator_loop"
        node.description = "Test D-E Loop"
        node.max_iterations = 3
        node.director_node = mock_director_node
        node.evaluator_node = mock_evaluator_node
        node.script_execution_node = mock_script_node
        node.termination_condition_node = None
        return node
    
    def test_evaluator_step_success(self, evaluator, mock_loop_node, base_environment):
        """Test D-E loop when evaluator step returns success."""
        # Setup mocks for evaluate method
        with patch.object(evaluator, 'evaluate') as mock_evaluate:
            # Configure mock to return different results for different nodes
            def mock_evaluate_side_effect(node, env):
                if node == mock_loop_node.director_node:
                    return {
                        "status": "COMPLETE",
                        "content": "Director output",
                        "notes": {}
                    }
                elif node == mock_loop_node.script_execution_node:
                    return {
                        "status": "COMPLETE",
                        "content": "Script executed",
                        "notes": {
                            "scriptOutput": {
                                "stdout": "Test output",
                                "stderr": "",
                                "exit_code": 0
                            }
                        }
                    }
                elif node == mock_loop_node.evaluator_node:
                    # Evaluator returns success
                    return {
                        "status": "COMPLETE",
                        "content": json.dumps({
                            "success": True,
                            "feedback": "Tests passed."
                        }),
                        "notes": {
                            "success": True,
                            "feedback": "Tests passed."
                        }
                    }
                return {}
            
            mock_evaluate.side_effect = mock_evaluate_side_effect
            
            # Call the method under test
            result = evaluator._evaluate_director_evaluator_loop(mock_loop_node, base_environment)
            
            # Assertions
            assert result["status"] == "COMPLETE"
            assert "iteration_history" in result["notes"]
            assert len(result["notes"]["iteration_history"]) == 1  # Should terminate after first iteration
            assert result["notes"]["iterations_completed"] == 1
            assert "final_evaluation" in result["notes"]
            assert result["notes"]["final_evaluation"]["notes"]["success"] is True
            
            # Verify evaluate was called for each node
            assert mock_evaluate.call_count == 3  # director, script, evaluator
    
    def test_evaluator_step_failure(self, evaluator, mock_loop_node, base_environment):
        """Test D-E loop when evaluator step returns failure but loop continues."""
        # Setup mocks for evaluate method
        with patch.object(evaluator, 'evaluate') as mock_evaluate:
            # Configure mock to return different results for different nodes
            def mock_evaluate_side_effect(node, env):
                if node == mock_loop_node.director_node:
                    return {
                        "status": "COMPLETE",
                        "content": "Director output",
                        "notes": {}
                    }
                elif node == mock_loop_node.script_execution_node:
                    return {
                        "status": "COMPLETE",
                        "content": "Script executed",
                        "notes": {
                            "scriptOutput": {
                                "stdout": "",
                                "stderr": "Test failed",
                                "exit_code": 1
                            }
                        }
                    }
                elif node == mock_loop_node.evaluator_node:
                    # Evaluator returns failure
                    return {
                        "status": "COMPLETE",
                        "content": json.dumps({
                            "success": False,
                            "feedback": "Tests failed."
                        }),
                        "notes": {
                            "success": False,
                            "feedback": "Tests failed."
                        }
                    }
                return {}
            
            mock_evaluate.side_effect = mock_evaluate_side_effect
            
            # Set max_iterations to 1 to test single iteration
            mock_loop_node.max_iterations = 1
            
            # Call the method under test
            result = evaluator._evaluate_director_evaluator_loop(mock_loop_node, base_environment)
            
            # Assertions
            assert result["status"] == "COMPLETE"
            assert "iteration_history" in result["notes"]
            assert len(result["notes"]["iteration_history"]) == 1
            assert result["notes"]["iterations_completed"] == 1
            assert "final_evaluation" in result["notes"]
            assert result["notes"]["final_evaluation"]["notes"]["success"] is False
            assert result["notes"].get("termination_reason") == "max_iterations_reached"

    def test_evaluator_step_invalid_evaluator_output(self, evaluator, mock_loop_node, base_environment):
        """Test D-E loop when evaluator step returns invalid structure (missing notes.success)."""
        # Setup mocks for evaluate method
        with patch.object(evaluator, 'evaluate') as mock_evaluate:
            # Configure mock to return different results for different nodes
            def mock_evaluate_side_effect(node, env):
                if node == mock_loop_node.director_node:
                    return {
                        "status": "COMPLETE",
                        "content": "Director output",
                        "notes": {}
                    }
                elif node == mock_loop_node.script_execution_node:
                    return {
                        "status": "COMPLETE",
                        "content": "Script executed",
                        "notes": {
                            "scriptOutput": {
                                "stdout": "",
                                "stderr": "",
                                "exit_code": 1
                            }
                        }
                    }
                elif node == mock_loop_node.evaluator_node:
                    # Evaluator returns invalid JSON
                    return {
                        "status": "COMPLETE",
                        "status": "COMPLETE",
                        "content": "Evaluator output missing success field",
                        "notes": {"feedback": "Something happened"} # Missing 'success'
                    }
                return {}
            mock_evaluate.side_effect = mock_evaluate_side_effect
            
            # Set max_iterations to 1 to test single iteration
            mock_loop_node.max_iterations = 1
            
            # Call the method under test
            result = evaluator._evaluate_director_evaluator_loop(mock_loop_node, base_environment)
            
            # Assertions
            assert result["status"] == "COMPLETE"
            assert "iteration_history" in result["notes"]
            assert len(result["notes"]["iteration_history"]) == 1
            assert result["notes"]["iterations_completed"] == 1
            assert "final_evaluation" in result["notes"]
            # Should default to failure when success field is missing
            assert result["notes"]["final_evaluation"]["notes"]["success"] is False # Should default to False
            assert "Evaluation failed or structure invalid" in result["notes"]["final_evaluation"]["notes"]["feedback"]

    def test_director_step_task_failure(self, evaluator, mock_loop_node, base_environment):
        """Test D-E loop when the director step returns a task failure."""
        # Setup mocks for evaluate method
        with patch.object(evaluator, 'evaluate') as mock_evaluate:
            # Configure mock evaluate to fail the director step
            def mock_evaluate_side_effect(node, env):
                if node == mock_loop_node.director_node:
                    # Director returns FAILED status
                    return {
                        "status": "FAILED",
                        "content": "Director step failed execution",
                        "notes": {"reason": "subtask_error"}
                    }
                # Other steps won't be called if director fails first
                return {"status": "COMPLETE"} # Placeholder for other nodes if needed
            mock_evaluate.side_effect = mock_evaluate_side_effect
            
            # Call the method under test
            result = evaluator._evaluate_director_evaluator_loop(mock_loop_node, base_environment)
            
            # Assertions
            assert result["status"] == "FAILED", "Loop should fail if director fails"
            assert "iteration_history" in result["notes"]
            assert len(result["notes"]["iteration_history"]) == 1, "Should fail in first iteration"
            assert "error" in result["notes"], "Overall error details should be in notes"
            assert result["notes"]["error"]["reason"] == SUBTASK_FAILURE, "Error reason should indicate subtask failure"
            assert "Director step failed" in result["notes"]["error"]["message"]

            # Verify the loop terminated immediately after director failure
            assert mock_evaluate.call_count == 1 # Only director node should be evaluated

    def test_script_step_task_failure(self, evaluator, mock_loop_node, base_environment):
        """Test D-E loop when the script execution step returns a task failure."""
        with patch.object(evaluator, 'evaluate') as mock_evaluate:
            def mock_evaluate_side_effect(node, env):
                if node == mock_loop_node.director_node:
                    return {"status": "COMPLETE", "content": "Director output"}
                elif node == mock_loop_node.script_execution_node:
                    # Script execution returns FAILED status
                    return {
                        "status": "FAILED",
                        "content": "Script command failed",
                        "notes": {"reason": "command_failed", "exit_code": 1}
                    }
                # Evaluator won't be called if script fails
                return {"status": "COMPLETE"}

            mock_evaluate.side_effect = mock_evaluate_side_effect
            result = evaluator._evaluate_director_evaluator_loop(mock_loop_node, base_environment)

            assert result["status"] == "FAILED"
            assert len(result["notes"]["iteration_history"]) == 1
            assert result["notes"]["error"]["reason"] == SUBTASK_FAILURE
            assert "Script execution step failed" in result["notes"]["error"]["message"]
            assert mock_evaluate.call_count == 2 # Director, Script

    def test_multiple_iterations_to_success(self, evaluator, mock_loop_node, base_environment):
        """Test D-E loop with multiple iterations until success."""
        # Setup mocks for evaluate method
        with patch.object(evaluator, 'evaluate') as mock_evaluate:
            # Use a counter to track iterations and change behavior
            iteration_counter = [0]
            
            def mock_evaluate_side_effect(node, env):
                if node == mock_loop_node.director_node:
                    iteration_counter[0] += 1
                    return {
                        "status": "COMPLETE",
                        "content": f"Director output iteration {iteration_counter[0]}",
                        "notes": {}
                    }
                elif node == mock_loop_node.script_execution_node:
                    return {
                        "status": "COMPLETE",
                        "content": "Script executed",
                        "notes": {
                            "scriptOutput": {
                                "stdout": f"Test output iteration {iteration_counter[0]}",
                                "stderr": "",
                                "exit_code": 0
                            }
                        }
                    }
                elif node == mock_loop_node.evaluator_node:
                    # Return success only on the second iteration
                    success = iteration_counter[0] == 2
                    return {
                        "status": "COMPLETE",
                        "content": json.dumps({
                            "success": success,
                            "feedback": "Tests passed." if success else "Tests failed."
                        }),
                        "notes": {
                            "success": success,
                            "feedback": "Tests passed." if success else "Tests failed."
                        }
                    }
                return {}
            
            mock_evaluate.side_effect = mock_evaluate_side_effect
            
            # Set max_iterations to 3
            mock_loop_node.max_iterations = 3
            
            # Call the method under test
            result = evaluator._evaluate_director_evaluator_loop(mock_loop_node, base_environment)
            
            # Assertions
            assert result["status"] == "COMPLETE"
            assert "iteration_history" in result["notes"]
            assert len(result["notes"]["iteration_history"]) == 2  # Should succeed on second iteration
            assert result["notes"]["iterations_completed"] == 2
            assert result["notes"]["final_evaluation"]["notes"]["success"] is True
            
            # Verify evaluate was called the expected number of times
            assert mock_evaluate.call_count == 6 # 2 iterations * 3 nodes (director, script, evaluator)

    def test_loop_parses_target_files_parameter(self, evaluator, mock_loop_node, base_environment):
        """Test that the D-E loop correctly parses the target_files JSON string."""
        # Modify the loop node mock to include parameters
        mock_loop_node.parameters = {
            "test_cmd": {"type": "string", "required": True},
            "target_files": {"type": "string", "default": "[]"},
            "max_cycles": {"type": "integer", "default": 3}
        }
        # Provide the target_files parameter in the initial environment
        initial_env = base_environment.extend({
            "test_cmd": "pytest",
            "target_files": '["file1.py", "path/to/file2.py"]' # JSON string
        })

        with patch.object(evaluator, 'evaluate') as mock_evaluate:
            # Simulate success on first try to stop loop quickly
            mock_evaluate.side_effect = lambda node, env: {
                "status": "COMPLETE",
                "content": "Mocked step",
                "notes": {"success": True} if node == mock_loop_node.evaluator_node else {}
            }

            evaluator._evaluate_director_evaluator_loop(mock_loop_node, initial_env)

            # Check the environment passed to the *director* node in the first iteration
            # The D-E loop creates loop_env, then loop_env_iter, then director_env
            # We need to capture the environment passed to the director call
            director_call_args = None
            for call_arg in mock_evaluate.call_args_list:
                 if call_arg[0][0] == mock_loop_node.director_node: # Check if node matches director
                      director_call_args = call_arg
                      break

            assert director_call_args is not None, "Director node was not evaluated"
            director_env = director_call_args[0][1] # Get the environment argument

            # Assert that 'target_files' in the director's env is a list
            assert "target_files" in director_env.bindings
            assert director_env.bindings["target_files"] == ["file1.py", "path/to/file2.py"]

    def test_loop_fails_on_invalid_target_files_json(self, evaluator, mock_loop_node, base_environment):
        """Test D-E loop failure when target_files is invalid JSON."""
        mock_loop_node.parameters = { "target_files": {"type": "string"} }
        initial_env = base_environment.extend({"target_files": '["file1.py",'}) # Invalid JSON

        result = evaluator._evaluate_director_evaluator_loop(mock_loop_node, initial_env)

        assert result["status"] == "FAILED"
        assert "Invalid target_files parameter" in result["content"]


    def test_json_output_parsing(self):
        """Test JSON output parsing for template results."""
        # Setup mock template provider
        mock_provider = MagicMock()
        mock_provider.execute_task.return_value = {
            "content": '{"key": "value", "items": [1, 2, 3]}',
            "status": "COMPLETE",
            "notes": {}
        }
        
        # Create evaluator with mock provider
        evaluator = Evaluator(mock_provider)
        
        # Create environment
        env = Environment({})
        
        # Test template with JSON output format
        template = {
            "name": "test_template",
            "type": "atomic",
            "subtype": "test",
            "output_format": {"type": "json"}
        }
        
        # Execute template
        result = evaluator._execute_template(template, env)
        
        # Verify parsed content
        assert "parsedContent" in result
        assert result["parsedContent"]["key"] == "value"
        assert result["parsedContent"]["items"] == [1, 2, 3]
        
        # Test with invalid JSON
        mock_provider.execute_task.return_value = {
            "content": "This is not JSON",
            "status": "COMPLETE",
            "notes": {}
        }
        
        result = evaluator._execute_template(template, env)
        
        # Verify error handling
        assert "parsedContent" not in result
        assert "notes" in result
        assert "parseError" in result["notes"]
        assert "Failed to parse output as JSON" in result["notes"]["parseError"]
