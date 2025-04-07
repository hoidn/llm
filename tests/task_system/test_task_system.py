"""Tests for TaskSystem enhancements."""
import pytest
from unittest.mock import MagicMock, patch
from task_system.task_system import TaskSystem
from task_system.template_utils import resolve_function_calls as original_resolve_function_calls

def patched_resolve_function_calls(text, task_system, env, **kwargs):
    return original_resolve_function_calls(text, task_system, env)

import pytest

@pytest.fixture(autouse=True)
def patch_resolve_function_calls(monkeypatch):
    monkeypatch.setattr("task_system.template_utils.resolve_function_calls", patched_resolve_function_calls)

class TestTaskSystemRegistration:
    """Tests for TaskSystem template registration and lookup."""
    
    def test_register_template(self):
        """Test registering a template."""
        task_system = TaskSystem()
        
        # Simple template
        template = {
            "type": "atomic",
            "subtype": "test",
            "name": "test_template",
            "description": "Test template"
        }
        
        task_system.register_template(template)
        
        # Verify template was stored by name
        assert "test_template" in task_system.templates
        
        # Verify template was indexed by type:subtype
        assert "atomic:test" in task_system.template_index
        assert task_system.template_index["atomic:test"] == "test_template"
    
    def test_register_template_without_name(self):
        """Test registering a template without a name."""
        task_system = TaskSystem()
        
        # Template without name
        template = {
            "type": "atomic",
            "subtype": "test",
            "description": "Test template"
        }
        
        task_system.register_template(template)
        
        # Template should be stored with generated name
        generated_name = "atomic_test"
        assert generated_name in task_system.templates
        assert task_system.template_index["atomic:test"] == generated_name
    
    def test_find_template_by_name(self):
        """Test finding a template by name."""
        task_system = TaskSystem()
        
        # Register a template
        template = {
            "type": "atomic",
            "subtype": "test",
            "name": "test_template",
            "description": "Test template"
        }
        
        task_system.register_template(template)
        
        # Find by name
        found = task_system.find_template("test_template")
        assert found is not None
        assert found["name"] == "test_template"
    
    def test_find_template_by_type_subtype(self):
        """Test finding a template by type:subtype."""
        task_system = TaskSystem()
        
        # Register a template
        template = {
            "type": "atomic",
            "subtype": "test",
            "name": "test_template",
            "description": "Test template"
        }
        
        task_system.register_template(template)
        
        # Find by type:subtype
        found = task_system.find_template("atomic:test")
        assert found is not None
        assert found["name"] == "test_template"
    
    def test_find_nonexistent_template(self):
        """Test finding a template that doesn't exist."""
        task_system = TaskSystem()
        
        # Find nonexistent template
        found = task_system.find_template("nonexistent")
        assert found is None


class TestTaskSystemExecution:
    """Tests for TaskSystem task execution."""
    
    def test_execute_task_with_validation(self):
        """Test executing a task with parameter validation."""
        task_system = TaskSystem()
        
        # Register a mock template
        template = {
            "type": "atomic",
            "subtype": "associative_matching",
            "name": "test_template",
            "parameters": {
                "query": {"type": "string", "required": True}
            }
        }
        
        task_system.register_template(template)
        
        # Mock the _execute_associative_matching method
        task_system._execute_associative_matching = MagicMock(return_value={
            "status": "COMPLETE",
            "content": "[]"
        })
        
        # Execute with valid parameters
        result = task_system.execute_task("atomic", "associative_matching", {"query": "test"})
        
        assert result["status"] == "COMPLETE"
        task_system._execute_associative_matching.assert_called_once()
    
    def test_execute_task_with_function_calls(self):
        """Test executing a task with function calls in template fields."""
        # Create a TaskSystem instance
        task_system = TaskSystem()
        
        # Register a simple function template
        format_template = {
            "type": "atomic",
            "subtype": "format",
            "name": "format_greeting",
            "description": "Format a greeting for a person",
            "parameters": {
                "name": {"type": "string", "required": True},
                "formal": {"type": "boolean", "default": False}
            },
            "system_prompt": "{{formal ? 'Dear' : 'Hello'}}, {{name}}!"
        }
        task_system.register_template(format_template)
        
        # Register a template that calls the function
        caller_template = {
            "type": "atomic",
            "subtype": "caller",
            "name": "greeting_caller",
            "description": "Template that calls format_greeting",
            "parameters": {
                "person": {"type": "string", "required": True}
            },
            "system_prompt": "Greeting: {{format_greeting(name=person, formal=true)}}"
        }
        task_system.register_template(caller_template)
        
        # Mock the _execute_associative_matching method for both templates
        # First mock for the caller template
        task_system._execute_associative_matching = MagicMock(side_effect=[
            # Result from the main template execution
            {
                "status": "COMPLETE",
                "content": "Template with call result"
            }
        ])
        
        # Create a separate mock for the function template execution
        original_execute = task_system.execute_task
        
        def mock_execute(*args, **kwargs):
            task_type = args[0]
            task_subtype = args[1]
            
            # If this is the format_greeting function call
            if task_type == "atomic" and task_subtype == "format":
                return {
                    "status": "COMPLETE",
                    "content": "Dear, Test!"
                }
            
            # Otherwise delegate to original implementation
            return original_execute(*args, **kwargs)
        
        # Use our mock function for task execution
        with patch.object(task_system, 'execute_task', side_effect=mock_execute):
            # Execute the caller template
            result = task_system.execute_task("atomic", "caller", {"person": "Test"})
            
            # Verify that the format_greeting function call was processed
            # and its result was included in the system_prompt
            executed_template = task_system._execute_associative_matching.call_args[0][0]
            assert "Greeting: Dear, Test!" in executed_template["system_prompt"]
            
            # Verify final result
            assert result["status"] == "COMPLETE"
            assert result["content"] == "Template with call result"
    
    def test_execute_task_with_variable_resolution(self):
        """Test executing a task with variable resolution."""
        task_system = TaskSystem()
        
        # Register a test template with variables in fields
        template = {
            "type": "atomic",
            "subtype": "var_test",
            "name": "variable_test",
            "description": "Test for {{user}}",
            "system_prompt": "Process query '{{query}}' with limit {{limit}}",
            "parameters": {
                "query": {"type": "string", "required": True},
                "user": {"type": "string", "default": "default_user"},
                "limit": {"type": "integer", "default": 10}
            }
        }
        
        task_system.register_template(template)
        
        # Mock the _execute_associative_matching method
        task_system._execute_associative_matching = MagicMock(return_value={
            "status": "COMPLETE",
            "content": "Test result"
        })
        
        # Execute task with inputs that will be used for variable resolution
        task_system.execute_task(
            "atomic", "var_test", 
            {"query": "search_query", "user": "test_user"}
        )
        
        # Verify that variables were resolved in the template
        template_arg = task_system._execute_associative_matching.call_args[0][0]
        assert template_arg["description"] == "Test for test_user"
        assert template_arg["system_prompt"] == "Process query 'search_query' with limit 10"
    
    def test_execute_task_with_invalid_parameters(self):
        """Test executing a task with invalid parameters."""
        task_system = TaskSystem()
        
        # Register a mock template
        template = {
            "type": "atomic",
            "subtype": "associative_matching",
            "name": "test_template",
            "parameters": {
                "query": {"type": "string", "required": True}
            }
        }
        
        task_system.register_template(template)
        
        # Execute with missing required parameter
        result = task_system.execute_task("atomic", "associative_matching", {})
        
        assert result["status"] == "FAILED"
        assert "PARAMETER_ERROR" in result["notes"]["error"]
    
    def test_execute_task_with_model_selection(self):
        """Test executing a task with model selection."""
        task_system = TaskSystem()
        
        # Register a mock template with model preferences
        template = {
            "type": "atomic",
            "subtype": "associative_matching",
            "name": "test_template",
            "parameters": {
                "query": {"type": "string", "required": True}
            },
            "model": {
                "preferred": "claude-3",
                "fallback": ["gpt-4"]
            }
        }
        
        task_system.register_template(template)
        
        # Mock the _execute_associative_matching method
        task_system._execute_associative_matching = MagicMock(return_value={
            "status": "COMPLETE",
            "content": "[]"
        })
        
        # Execute with available models
        available_models = ["gpt-4"]  # Claude-3 not available
        result = task_system.execute_task(
            "atomic", "associative_matching", 
            {"query": "test"}, 
            available_models=available_models
        )
        
        assert result["status"] == "COMPLETE"
        assert result["notes"]["selected_model"] == "gpt-4"
    
    def test_execute_unknown_task(self):
        """Test executing an unknown task type."""
        task_system = TaskSystem()
        
        # Execute unknown task
        result = task_system.execute_task("unknown", "task", {})
        
        assert result["status"] == "FAILED"
        assert "Unknown task type" in result["content"]
