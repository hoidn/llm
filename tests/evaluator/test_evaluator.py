"""Tests for the Evaluator component."""
import pytest
from unittest.mock import MagicMock, patch

from task_system.ast_nodes import ArgumentNode, FunctionCallNode
from task_system.template_utils import Environment
from system.errors import TaskError, INPUT_VALIDATION_FAILURE
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
