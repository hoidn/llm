"""Integration tests for template enhancements."""
import pytest
from unittest.mock import MagicMock, patch
from task_system.task_system import TaskSystem
from task_system.templates.associative_matching import ASSOCIATIVE_MATCHING_TEMPLATE, execute_template

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
        assert result["status"] == "COMPLETE"
        assert "file1.py" in result["content"]
        
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
        
        # Create mock memory system
        mock_memory = MagicMock()
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
        assert "file_count" in result["notes"]
        assert result["notes"]["file_count"] == 2
    
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
        assert "notes" in result
        assert "selected_model" in result["notes"]
        assert result["notes"]["selected_model"] == "llama-3"  # Second fallback
