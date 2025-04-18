"""Integration tests for template enhancements."""
import pytest
from unittest.mock import MagicMock, patch
from task_system.task_system import TaskSystem
from task_system.templates.associative_matching import ASSOCIATIVE_MATCHING_TEMPLATE, execute_template
from task_system.template_utils import resolve_function_calls as original_resolve_function_calls

def patched_resolve_function_calls(text, task_system, env, **kwargs):
    return original_resolve_function_calls(text, task_system, env)

import pytest

@pytest.fixture(autouse=True)
def patch_resolve_function_calls(monkeypatch):
    monkeypatch.setattr("task_system.template_utils.resolve_function_calls", patched_resolve_function_calls)

class TestTemplateIntegration:
    """Integration tests for template system."""
    
    def test_register_and_execute_enhanced_template(self):
        """Test registering and executing an enhanced template."""
        # Create task system
        task_system = TaskSystem()
        
        # Create a test template based on associative matching
        test_template = {
            "type": "atomic",
            "subtype": "test_matching",
            "name": "test_matching_template",
            "description": "Test matching template",
            "parameters": {
                "query": {"type": "string", "required": True},
                "max_results": {"type": "integer", "default": 5}
            }
        }
        
        # Register the template
        task_system.register_template(test_template)
        
        # Mock _execute_associative_matching for the test
        task_system._execute_associative_matching = MagicMock(return_value={
            "status": "COMPLETE",
            "content": '["file1.py", "file2.py"]'
        })
        
        # Execute the template
        result = task_system.execute_task(
            "atomic", "test_matching", 
            {"query": "test query"}
        )
        
        # Verify successful execution
        assert result.status == "COMPLETE"
        assert "file1.py" in result.content
        
        # Verify parameters were passed correctly
        args = task_system._execute_associative_matching.call_args[0]
        assert "parameters" in args[0]
        assert args[1]["query"] == "test query"
        assert args[1]["max_results"] == 5  # Default value
    
    def test_backward_compatibility(self):
        """Test backward compatibility with existing template usage."""
        # Create task system
        task_system = TaskSystem()
        
        # Register the real associative matching template
        task_system.register_template(ASSOCIATIVE_MATCHING_TEMPLATE)
        
        # IMPORTANT: Also mock the execute_template function to avoid actual execution
        with patch('task_system.templates.associative_matching.execute_template') as mock_execute_template:
            # Configure mock to return test data
            mock_execute_template.return_value = ["file1.py", "file2.py"]
            
            # Create mock memory system
            mock_memory = MagicMock()
            # Initialize global_index
            mock_memory.global_index = {"file1.py": "Test metadata", "file2.py": "Test metadata"}
            mock_memory.get_global_index = MagicMock(return_value=mock_memory.global_index)
            mock_memory.get_relevant_context_for.return_value = MagicMock(
                matches=[("file1.py", 0.9), ("file2.py", 0.8)]
            )
            
            # Execute using the legacy style (type and subtype)
            result = task_system.execute_task(
                "atomic", "associative_matching", 
                {"query": "test query"},
                memory_system=mock_memory
            )
            
            # Verify successful execution
            assert result["status"] == "COMPLETE"
            assert mock_execute_template.called
    
    def test_enhanced_template_with_model_selection(self):
        """Test enhanced template with model selection."""
        # Create task system
        task_system = TaskSystem()
        
        # Create a test template with model preferences
        test_template = {
            "type": "atomic",
            "subtype": "model_test",
            "name": "model_test_template",
            "description": "Test template with model preference",
            "parameters": {
                "query": {"type": "string", "required": True}
            },
            "model": {
                "preferred": "claude-3",
                "fallback": ["gpt-4", "llama-3"]
            }
        }
        
        # Register the template
        task_system.register_template(test_template)
        
        # Mock _execute_associative_matching for the test
        task_system._execute_associative_matching = MagicMock(return_value={
            "status": "COMPLETE",
            "content": '[]'
        })
        
        # Available models (preferred not available)
        available_models = ["llama-3", "gpt-3.5"]
        
        # Execute with available models
        result = task_system.execute_task(
            "atomic", "model_test", 
            {"query": "test query"},
            available_models=available_models
        )
        
        # Verify model selection
        assert hasattr(result, "notes")
        assert "selected_model" in result.notes
        assert result.notes["selected_model"] == "llama-3"  # Second fallback
