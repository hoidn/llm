"""Tests for Memory System's context generation functionality."""
import pytest
from unittest.mock import patch, MagicMock

from memory.memory_system import MemorySystem
from memory.context_generation import ContextGenerationInput


class TestMemorySystemContext:
    """Tests for the Memory System's context generation functionality."""
    
    def test_context_input_handling(self):
        """Test handling of context input objects."""
        memory_system = MemorySystem()
        
        # Create test input
        input1 = ContextGenerationInput(
            template_description="Find files for authentication",
            inputs={"query": "auth", "max_results": 10},
            context_relevance={"query": True, "max_results": False}
        )
        
        # Mock the handler for this test
        mock_handler = MagicMock()
        mock_handler.determine_relevant_files.return_value = [("file1.py", "Relevant")]
        memory_system.handler = mock_handler
        
        # Test get_relevant_context_for with ContextGenerationInput
        result = memory_system.get_relevant_context_for(input1)
        
        # Verify handler was called with the right input
        mock_handler.determine_relevant_files.assert_called_once()
        args = mock_handler.determine_relevant_files.call_args[0]
        assert args[0] == input1
        
        # Verify result
        assert hasattr(result, "matches")
        assert len(result.matches) == 1
        assert result.matches[0][0] == "file1.py"
    
    @patch('memory.memory_system.MemorySystem._get_relevant_context_standard')
    def test_get_relevant_context_for_with_context_input(self, mock_standard):
        """Test get_relevant_context_for with ContextGenerationInput."""
        # Setup mock
        mock_result = MagicMock()
        mock_standard.return_value = mock_result
        
        # Create memory system
        memory_system = MemorySystem()
        
        # Create context input
        context_input = ContextGenerationInput(
            template_description="Find authentication files",
            template_type="atomic",
            template_subtype="associative_matching",
            inputs={"feature": "authentication"}
        )
        
        # Call method
        result = memory_system.get_relevant_context_for(context_input)
        
        # Verify standard method was called with context input
        mock_standard.assert_called_once()
        assert mock_standard.call_args[0][0] is context_input
        
        # Verify result
        assert result is mock_result
    
    @patch('memory.memory_system.MemorySystem._get_relevant_context_standard')
    def test_get_relevant_context_for_with_legacy_format(self, mock_standard):
        """Test get_relevant_context_for with legacy format."""
        # Setup mock
        mock_result = MagicMock()
        mock_standard.return_value = mock_result
        
        # Create memory system
        memory_system = MemorySystem()
        
        # Create legacy input
        legacy_input = {
            "taskText": "Find authentication files",
            "inheritedContext": "Previous context"
        }
        
        # Call method
        result = memory_system.get_relevant_context_for(legacy_input)
        
        # Verify standard method was called with converted input
        mock_standard.assert_called_once()
        context_input = mock_standard.call_args[0][0]
        assert isinstance(context_input, ContextGenerationInput)
        assert context_input.template_description == "Find authentication files"
        assert context_input.inherited_context == "Previous context"
        
        # Verify result
        assert result is mock_result
