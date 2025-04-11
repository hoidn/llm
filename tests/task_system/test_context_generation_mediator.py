"""Integration tests for TaskSystem mediator pattern in context generation."""
import pytest
from unittest.mock import MagicMock, patch
import json

from memory.context_generation import ContextGenerationInput, AssociativeMatchResult
from task_system.task_system import TaskSystem


class TestTaskSystemMediator:
    """Tests for TaskSystem's mediator role in context generation."""

    def test_generate_context_for_memory_system(self):
        """Test TaskSystem's generate_context_for_memory_system method."""
        # Create TaskSystem with mocked dependencies
        task_system = TaskSystem()
        
        # Mock the execute_task method
        task_system.execute_task = MagicMock(return_value={
            "status": "COMPLETE",
            "content": json.dumps([
                {"path": "file1.py", "relevance": "Contains auth logic"},
                {"path": "file2.py", "relevance": "Contains user model"}
            ])
        })
        
        # Create test input
        context_input = ContextGenerationInput(
            template_description="Find auth code",
            template_type="atomic",
            template_subtype="test",
            inputs={"feature": "login"},
            context_relevance={"feature": True}
        )
        
        # Create mock global index
        global_index = {
            "file1.py": "Auth module",
            "file2.py": "User module",
            "file3.py": "Unrelated module"
        }
        
        # Call the method under test
        result = task_system.generate_context_for_memory_system(context_input, global_index)
        
        # Verify the result
        assert isinstance(result, AssociativeMatchResult)
        assert "Found 2 relevant files" in result.context
        assert len(result.matches) == 2
        assert result.matches[0][0] == "file1.py"
        assert result.matches[1][0] == "file2.py"
        
        # Verify execute_task was called with correct parameters
        task_system.execute_task.assert_called_once()
        call_args = task_system.execute_task.call_args[0]
        assert call_args[0] == "atomic"  # task_type
        assert call_args[1] == "associative_matching"  # task_subtype
        
        # Check inputs
        inputs = call_args[2]
        assert inputs["query"] == "Find auth code"
        assert "metadata" in inputs
        assert inputs["additional_context"] == {"feature": "login"}
    
    def test_fresh_context_disabled(self):
        """Test when fresh_context is disabled."""
        # Create TaskSystem
        task_system = TaskSystem()
        
        # Mock execute_task to ensure it's not called
        task_system.execute_task = MagicMock()
        
        # Create test input with fresh_context=disabled
        context_input = ContextGenerationInput(
            template_description="Test query",
            inherited_context="Inherited context data",
            fresh_context="disabled"
        )
        
        # Call the method under test
        result = task_system.generate_context_for_memory_system(
            context_input, {"file1.py": "test"}
        )
        
        # Verify result contains only inherited context
        assert result.context == "Inherited context data"
        assert result.matches == []
        
        # Verify execute_task was not called
        task_system.execute_task.assert_not_called()
    
    def test_error_handling(self):
        """Test error handling in context generation."""
        # Create TaskSystem
        task_system = TaskSystem()
        
        # Mock execute_task to return invalid JSON
        task_system.execute_task = MagicMock(return_value={
            "status": "COMPLETE",
            "content": "Not valid JSON"
        })
        
        # Create test input
        context_input = ContextGenerationInput(template_description="Test")
        
        # Call the method under test
        result = task_system.generate_context_for_memory_system(
            context_input, {"file1.py": "test"}
        )
        
        # Should handle error gracefully
        assert isinstance(result, AssociativeMatchResult)
        assert result.matches == []
