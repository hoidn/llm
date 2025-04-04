"""Integration tests for template function calls."""
import pytest
from unittest.mock import MagicMock, patch
import json
from task_system.task_system import TaskSystem
from task_system.templates.function_examples import (
    register_function_templates,
    execute_format_json,
    execute_get_date
)
from task_system.template_utils import Environment

class TestTemplateFunctionIntegration:
    """Integration tests for template function calls."""
    
    def test_format_json_template(self):
        """Test the format_json template."""
        # Create TaskSystem instance
        task_system = TaskSystem()
        
        # Register function templates
        register_function_templates(task_system)
        
        # Mock the _execute_associative_matching method to return the JSON result
        task_system._execute_associative_matching = MagicMock(return_value={
            "status": "COMPLETE",
            "content": json.dumps({"name": "Test", "value": 123}, indent=2)
        })
        
        # Execute the format_json template
        result = task_system.execute_task(
            "atomic", "format_json", 
            {"value": {"name": "Test", "value": 123}, "indent": 2}
        )
        
        # Verify result
        assert result["status"] == "COMPLETE"
        
        # Verify the formatted JSON
        parsed = json.loads(result["content"])
        assert parsed["name"] == "Test"
        assert parsed["value"] == 123
    
    def test_greeting_with_function_call(self):
        """Test the greeting template with a function call."""
        # Create TaskSystem instance
        task_system = TaskSystem()
        
        # Register function templates
        register_function_templates(task_system)
        
        # Mock _execute_associative_matching but delegate date function to real implementation
        original_execute = task_system.execute_task
        
        def mock_execute(*args, **kwargs):
            task_type = args[0]
            task_subtype = args[1]
            
            # If this is the get_date function call
            if task_type == "atomic" and task_subtype == "get_date":
                # Delegate to actual date implementation for simplicity
                return {
                    "status": "COMPLETE",
                    "content": execute_get_date()
                }
                
            # For the main greeting template
            if task_type == "atomic" and task_subtype == "greeting":
                # Apply function call result and return
                return {
                    "status": "COMPLETE",
                    "content": "Greeting generated"
                }
            
            # Otherwise use original implementation
            return original_execute(*args, **kwargs)
        
        # Replace execute_task with our mock function
        with patch.object(task_system, 'execute_task', side_effect=mock_execute):
            # Mock the matching for readability in test, but use the real environment
            task_system._execute_associative_matching = MagicMock(return_value={
                "status": "COMPLETE", 
                "content": "Greeting generated"
            })
            
            # Execute the greeting template
            result = task_system.execute_task(
                "atomic", "greeting", 
                {"name": "User", "formal": True}
            )
            
            # Verify that the get_date function was called in system_prompt
            executed_template = task_system._execute_associative_matching.call_args[0][0]
            
            # The current date should be in the system_prompt
            assert "Today's date: " in executed_template["system_prompt"]
            assert "Dear, User!" in executed_template["system_prompt"]
    
    def test_nested_function_calls(self):
        """Test nested function calls in templates."""
        # Create TaskSystem instance
        task_system = TaskSystem()
        
        # Register function templates
        register_function_templates(task_system)
        
        # Mocks for the task execution
        side_effects = [
            # First call: format_json
            {"status": "COMPLETE", "content": json.dumps({"name": "Test", "role": "User"}, indent=4)},
            # Second call: greeting
            {"status": "COMPLETE", "content": "Dear, Test!\n\nWelcome to our service."},
            # Final call: nested_example
            {"status": "COMPLETE", "content": "Nested template result"}
        ]
        
        with patch.object(task_system, '_execute_associative_matching', side_effect=side_effects):
            # Execute the nested template
            result = task_system.execute_task(
                "atomic", "nested_example", 
                {"user_info": {"name": "Test", "role": "User"}}
            )
            
            # Verify the final result
            assert result["status"] == "COMPLETE"
            assert result["content"] == "Nested template result"
            
            # Final call should have both function results in system_prompt
            calls = task_system._execute_associative_matching.call_args_list
            assert len(calls) == 3
            
            # The last call should contain both processed function calls
            final_template = calls[2][0][0]
            assert json.dumps({"name": "Test", "role": "User"}, indent=4) in final_template["system_prompt"]
            assert "Dear, Test!" in final_template["system_prompt"]
    
    def test_recursion_depth_limit(self):
        """Test recursion depth limit in function calls."""
        # Create TaskSystem instance
        task_system = TaskSystem()
        
        # Register a recursive template that calls itself
        recursive_template = {
            "type": "atomic",
            "subtype": "recursive",
            "name": "recursive",
            "description": "Template that calls itself recursively",
            "parameters": {
                "depth": {"type": "integer", "default": 0}
            },
            "system_prompt": "Depth {{depth}}. {{depth < 10 ? recursive(depth=depth+1) : 'Max depth reached'}}"
        }
        task_system.register_template(recursive_template)
        
        # Mock _execute_associative_matching to trace the recursion
        calls = []
        
        def mock_execute_matching(*args, **kwargs):
            template = args[0]
            inputs = args[1]
            depth = inputs.get("depth", 0)
            calls.append(depth)
            return {"status": "COMPLETE", "content": f"Depth {depth}"}
        
        task_system._execute_associative_matching = MagicMock(side_effect=mock_execute_matching)
        
        # Execute the recursive template - should stop at max_depth
        result = task_system.execute_task("atomic", "recursive", {"depth": 0})
        
        # Verify recursion was limited (calls at depth 0-4 only, plus error at depth 5)
        assert len(calls) <= 6  # The max depth is 5, so max 6 calls including the original
        
        # Verify the final template has an error message for exceeding depth
        final_template = task_system._execute_associative_matching.call_args[0][0]
        assert "error in recursive" in final_template["system_prompt"]
        assert "Maximum recursion depth" in final_template["system_prompt"]
