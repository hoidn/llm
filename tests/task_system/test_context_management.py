"""Tests for TaskSystem context management features."""
import pytest
from unittest.mock import MagicMock, patch
import json

from src.task_system.task_system import TaskSystem
from src.memory.context_generation import ContextGenerationInput, AssociativeMatchResult
from src.memory.memory_system import MemorySystem


class TestContextManagement:
    """Tests for TaskSystem context management."""
    
    @pytest.fixture
    def setup_components(self):
        """Set up TaskSystem with mock dependencies."""
        # Create mock memory system
        mock_memory = MagicMock(spec=MemorySystem)
        
        # Create standard result for context queries
        standard_result = MagicMock()
        standard_result.matches = [("file1.py", "Relevant"), ("file2.py", "Also relevant")]
        standard_result.context = "Found 2 relevant files"
        
        # Configure mock memory system to return standard result
        mock_memory.get_relevant_context_for.return_value = standard_result
        
        # Create TaskSystem
        task_system = TaskSystem()
        
        # Configure TaskSystem to use test mode
        task_system.set_test_mode(True)
        
        return task_system, mock_memory
    
    def test_inherited_context(self, setup_components):
        """Test that inherited context is properly passed to memory system."""
        task_system, mock_memory = setup_components
        
        # Create a template with inherit_context enabled
        template = {
            "type": "test",
            "subtype": "inherit",
            "name": "test_inherit",
            "description": "Test template with inherited context",
            "context_management": {
                "inherit_context": "enabled",
                "accumulate_data": False,
                "fresh_context": "enabled"
            }
        }
        
        # Register the template
        task_system.register_template(template)
        
        # Execute task with inherited context
        result = task_system.execute_task(
            "test", "inherit", 
            {"param1": "value1"},
            memory_system=mock_memory,
            inherited_context="Previous task context"
        )
        
        # Verify memory system was called with correct parameters
        mock_memory.get_relevant_context_for.assert_called_once()
        args = mock_memory.get_relevant_context_for.call_args[0]
        
        # Check the first argument is a ContextGenerationInput
        assert isinstance(args[0], ContextGenerationInput)
        
        # Verify inherited context was passed
        assert args[0].inherited_context == "Previous task context"
        
        # Verify the result contains context management info
        assert "notes" in result
        assert "context_management" in result["notes"]
        assert result["notes"]["context_management"]["inherit_context"] == "enabled"
    
    def test_fresh_context_disabled(self, setup_components):
        """Test that fresh_context=disabled prevents context generation."""
        task_system, mock_memory = setup_components
        
        # Create a template with fresh_context disabled
        template = {
            "type": "test",
            "subtype": "no_fresh",
            "name": "test_no_fresh",
            "description": "Test template with fresh_context disabled",
            "context_management": {
                "inherit_context": "none",
                "accumulate_data": False,
                "fresh_context": "disabled"
            }
        }
        
        # Register the template
        task_system.register_template(template)
        
        # Execute task
        result = task_system.execute_task(
            "test", "no_fresh", 
            {"param1": "value1"},
            memory_system=mock_memory
        )
        
        # Verify memory system was NOT called (fresh_context disabled)
        mock_memory.get_relevant_context_for.assert_not_called()
        
        # Verify the result contains context management info
        assert "notes" in result
        assert "context_management" in result["notes"]
        assert result["notes"]["context_management"]["fresh_context"] == "disabled"
    
    def test_accumulate_data(self, setup_components):
        """Test that accumulated data is properly passed to memory system."""
        task_system, mock_memory = setup_components
        
        # Create a template with accumulate_data enabled
        template = {
            "type": "test",
            "subtype": "accumulate",
            "name": "test_accumulate",
            "description": "Test template with accumulate_data enabled",
            "context_management": {
                "inherit_context": "none",
                "accumulate_data": True,
                "fresh_context": "enabled"
            }
        }
        
        # Register the template
        task_system.register_template(template)
        
        # Create previous outputs
        previous_outputs = ["Output 1", "Output 2"]
        
        # Execute task with previous outputs
        result = task_system.execute_task(
            "test", "accumulate", 
            {"param1": "value1"},
            memory_system=mock_memory,
            previous_outputs=previous_outputs
        )
        
        # Verify memory system was called with correct parameters
        mock_memory.get_relevant_context_for.assert_called_once()
        args = mock_memory.get_relevant_context_for.call_args[0]
        
        # Check the first argument is a ContextGenerationInput
        assert isinstance(args[0], ContextGenerationInput)
        
        # Verify previous outputs were passed
        assert args[0].previous_outputs == previous_outputs
        
        # Verify the result contains context management info
        assert "notes" in result
        assert "context_management" in result["notes"]
        assert result["notes"]["context_management"]["accumulate_data"] is True
