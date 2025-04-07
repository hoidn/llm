"""Integration tests for the function call translation mechanism."""
import pytest
from unittest.mock import MagicMock, patch

from task_system.ast_nodes import FunctionCallNode, ArgumentNode
from task_system.template_utils import Environment, resolve_function_calls
from task_system.task_system import TaskSystem
from evaluator.evaluator import Evaluator
from system.errors import TaskError, INPUT_VALIDATION_FAILURE


class TestFunctionCallIntegration:
    """Integration tests for function call execution."""
    
    @pytest.fixture
    def task_system(self):
        """Create a TaskSystem with a mock template."""
        ts = TaskSystem()
        
        # Register a test template
        ts.templates["test_template"] = {
            "name": "test_template",
            "type": "atomic",
            "subtype": "test",
            "description": "Test template",
            "parameters": {
                "param1": {"type": "string", "required": True},
                "param2": {"type": "number", "default": 42}
            }
        }
        
        # Mock execute_task to return a simple result
        ts.execute_task = MagicMock(return_value={
            "content": "Executed with param1={param1}, param2={param2}".format(
                param1="$param1$", param2="$param2$"
            ),
            "status": "COMPLETE",
            "notes": {}
        })
        
        # Initialize evaluator
        ts._ensure_evaluator()
        
        return ts
    
    @pytest.fixture
    def environment(self):
        """Create a test environment."""
        return Environment({
            "test_var": "test_value",
            "num_var": 99,
            "nested": {"key": "nested_value"}
        })
    
    def test_direct_function_call(self, task_system, environment):
        """Test direct function call using FunctionCallNode."""
        # Create a function call node
        args = [
            ArgumentNode("test_value"),
            ArgumentNode(99, name="param2")
        ]
        func_call = FunctionCallNode("test_template", args)
        
        # Execute the call
        result = task_system.executeCall(func_call, environment)
        
        # Verify result
        assert result["status"] == "COMPLETE"
        assert "Executed with param1=test_value, param2=99" in result["content"]
        
        # Verify task_system.execute_task was called
        task_system.execute_task.assert_called_once()
    
    def test_template_level_function_call(self, task_system, environment):
        """Test template-level function call using string syntax."""
        # Create a template with a function call
        template_text = "Result: {{test_template(test_var, param2=num_var)}}"
        
        # Resolve function calls
        result_text = resolve_function_calls(template_text, task_system, environment)
        
        # Verify result
        assert "Result: Executed with param1=test_value, param2=99" in result_text
        
        # Verify task_system.execute_task was called
        task_system.execute_task.assert_called_once()
    
    def test_variable_references_in_arguments(self, task_system, environment):
        """Test variable references in function call arguments."""
        # Create a template with variable references in arguments
        template_text = "{{test_template(test_var, param2=num_var)}}"
        
        # Resolve function calls
        result_text = resolve_function_calls(template_text, task_system, environment)
        
        # Verify result contains the resolved variable values
        assert "Executed with param1=test_value, param2=99" in result_text
    
    def test_nested_property_access(self, task_system, environment):
        """Test accessing nested properties in function call arguments."""
        # Create a template with nested property access
        template_text = "{{test_template(nested.key, param2=num_var)}}"
        
        # Resolve function calls
        result_text = resolve_function_calls(template_text, task_system, environment)
        
        # Verify result contains the nested property value
        assert "Executed with param1=nested_value, param2=99" in result_text
    
    def test_error_handling(self, task_system, environment):
        """Test error handling in function call resolution."""
        # Create a template with an invalid function call
        template_text = "{{nonexistent_template(test_var)}}"
        
        # Resolve function calls - this should show an error message
        result_text = resolve_function_calls(template_text, task_system, environment)
        
        # Verify error message is included
        assert "error in nonexistent_template()" in result_text
        assert "Template not found" in result_text
        
        # Test with missing required parameter
        template_text = "{{test_template()}}"  # param1 is required
        result_text = resolve_function_calls(template_text, task_system, environment)
        
        assert "error in test_template()" in result_text
    
    def test_both_execution_paths(self, task_system, environment):
        """Test that both execution paths yield identical results."""
        # Direct AST path
        args = [
            ArgumentNode("test_value"),
            ArgumentNode(99, name="param2")
        ]
        func_call = FunctionCallNode("test_template", args)
        direct_result = task_system.executeCall(func_call, environment)
        
        # Template syntax path
        template_text = "{{test_template(\"test_value\", param2=99)}}"
        template_result = resolve_function_calls(template_text, task_system, environment)
        
        # Both should contain the same content
        assert "Executed with param1=test_value, param2=99" in direct_result["content"]
        assert "Executed with param1=test_value, param2=99" in template_result
