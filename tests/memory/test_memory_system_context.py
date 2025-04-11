"""Tests for Memory System's context generation functionality."""
import pytest
from unittest.mock import patch, MagicMock

from memory.memory_system import MemorySystem
from memory.context_generation import ContextGenerationInput


class TestMemorySystemContext:
    """Tests for the Memory System's context generation functionality."""
    
    def test_build_query_from_input(self):
        """Test building query from context input."""
        memory_system = MemorySystem()
        
        # Test with template description only
        input1 = ContextGenerationInput(
            template_description="Find files for authentication"
        )
        query1 = memory_system._build_query_from_input(input1)
        assert query1 == "Find files for authentication"
        
        # Test with relevant inputs
        input2 = ContextGenerationInput(
            template_description="Find files",
            inputs={"feature": "authentication", "exclude_tests": True},
            context_relevance={"feature": True, "exclude_tests": True}
        )
        query2 = memory_system._build_query_from_input(input2)
        assert "Find files" in query2
        assert "feature: authentication" in query2
        assert "exclude_tests: True" in query2
        
        # Test with some inputs marked as not relevant
        input3 = ContextGenerationInput(
            template_description="Find files",
            inputs={"feature": "authentication", "format": "json"},
            context_relevance={"feature": True, "format": False}
        )
        query3 = memory_system._build_query_from_input(input3)
        assert "Find files" in query3
        assert "feature: authentication" in query3
        assert "format: json" not in query3
    
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
