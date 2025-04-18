"""Integration tests for Memory System with TaskSystem mediator."""
import pytest
from unittest.mock import MagicMock, patch
import os
import sys

from memory.memory_system import MemorySystem
from memory.context_generation import ContextGenerationInput, AssociativeMatchResult
from task_system.task_system import TaskSystem

class TestMemorySystemIntegration:
    """Integration tests for Memory System with TaskSystem mediator."""
    
    @pytest.fixture
    def setup_components(self):
        """Set up MemorySystem and mocked TaskSystem."""
        # Create mock TaskSystem
        mock_task_system = MagicMock(spec=TaskSystem)
        
        # Create standard result for most tests
        standard_result = AssociativeMatchResult(
            context="Found 2 relevant files",
            matches=[("file1.py", "Relevant to query"), ("file2.py", "Also relevant")]
        )
        
        # Configure mock to return standard result
        mock_task_system.generate_context_for_memory_system.return_value = standard_result
        
        # Create Memory System with mock TaskSystem
        memory_system = MemorySystem(task_system=mock_task_system)
        
        # Add test files to global index
        memory_system.global_index = {
            "file1.py": "Test file 1 with keywords",
            "file2.py": "Test file 2 with other content",
            "file3.py": "Unrelated file"
        }
        
        # Disable sharding by default
        memory_system._config["sharding_enabled"] = False
        
        return memory_system, mock_task_system
    
    def test_context_retrieval_with_mediator(self, setup_components):
        """Test context retrieval using TaskSystem mediator."""
        memory_system, mock_task_system = setup_components
        
        # Create context input
        context_input = ContextGenerationInput(
            template_description="Find test files",
            template_type="test",
            template_subtype="standard"
        )
        
        # Get relevant context
        result = memory_system.get_relevant_context_for(context_input)
        
        # Verify TaskSystem mediator was called
        mock_task_system.generate_context_for_memory_system.assert_called_once()
        
        # Verify result structure
        assert hasattr(result, 'context')
        assert hasattr(result, 'matches')
        assert len(result.matches) == 2
        assert result.matches[0].path == "file1.py"
        assert result.matches[1].path == "file2.py"
    
    def test_backwards_compatibility_with_dict_input(self, setup_components):
        """Test backward compatibility with dictionary input."""
        memory_system, mock_task_system = setup_components
        
        # Create legacy format input
        legacy_input = {
            "taskText": "Find files with legacy input",
            "inheritedContext": "Previous context"
        }
        
        # Get relevant context
        result = memory_system.get_relevant_context_for(legacy_input)
        
        # Verify TaskSystem mediator was called with converted input
        args = mock_task_system.generate_context_for_memory_system.call_args[0]
        assert isinstance(args[0], ContextGenerationInput)
        assert args[0].template_description == "Find files with legacy input"
        assert args[0].inherited_context == "Previous context"
        
        # Verify result structure
        assert len(result.matches) == 2
        
    def test_sharded_context_retrieval_with_mediator(self, setup_components):
        """Test sharded context retrieval using TaskSystem mediator."""
        memory_system, mock_task_system = setup_components
        
        # Create test results for different shards
        shard1_result = AssociativeMatchResult(
            context="Found 2 files in shard 1",
            matches=[("file1.py", "Relevant to query"), ("file2.py", "Also relevant")]
        )
        shard2_result = AssociativeMatchResult(
            context="Found 1 file in shard 2",
            matches=[("file3.py", "Relevant to shard 2")]
        )
        
        # Configure mock to return different results for different shards
        mock_task_system.generate_context_for_memory_system.side_effect = [shard1_result, shard2_result]
        
        # Enable sharding and set up sharded index
        memory_system._config["sharding_enabled"] = True
        memory_system._sharded_index = [
            {"file1.py": "Content 1", "file2.py": "Content 2"},  # Shard 1
            {"file3.py": "Content 3", "file4.py": "Content 4"}   # Shard 2
        ]
        
        # Create context input
        context_input = ContextGenerationInput(
            template_description="Test sharded retrieval",
            template_type="test",
            template_subtype="sharded"
        )
        
        # Get relevant context
        result = memory_system.get_relevant_context_for(context_input)
        
        # Verify TaskSystem was called for each shard
        assert mock_task_system.generate_context_for_memory_system.call_count == 2
        
        # Verify results were combined correctly
        assert len(result.matches) == 3  # Total matches from both shards
        assert "shards" in result.context.lower()  # Context mentions shards
    
    def test_error_handling_in_context_retrieval(self, setup_components):
        """Test error handling in context retrieval."""
        memory_system, mock_task_system = setup_components
        
        # Configure mock to raise an exception
        mock_task_system.generate_context_for_memory_system.side_effect = Exception("Test error")
        
        # Create context input
        context_input = ContextGenerationInput(
            template_description="Should handle error",
            template_type="test",
            template_subtype="error"
        )
        
        # Get relevant context (should not raise exception)
        result = memory_system.get_relevant_context_for(context_input)
        
        # Verify error is handled gracefully
        assert "Error during context generation" in result.context
        assert len(result.matches) == 0  # No matches on error
        
        # Reset side effect
        mock_task_system.generate_context_for_memory_system.side_effect = None
        
        # Test error handling in sharded retrieval
        # Configure mock to succeed for first shard but fail for second
        mock_task_system.generate_context_for_memory_system.side_effect = [
            AssociativeMatchResult(
                context="Found 1 file in shard 1",
                matches=[("file1.py", "Relevant")]
            ),
            Exception("Test error for shard 2")
        ]
        
        # Enable sharding and set up sharded index
        memory_system._config["sharding_enabled"] = True
        memory_system._sharded_index = [
            {"file1.py": "Content 1"},  # Shard 1
            {"file2.py": "Content 2"}   # Shard 2 (will fail)
        ]
        
        # Get relevant context (should return partial results)
        result = memory_system.get_relevant_context_for(context_input)
        
        # Verify we still got results from the successful shard
        assert len(result.matches) == 1
        assert result.matches[0][0] == "file1.py"
        assert "1/2" in result.context  # Should mention successful/total shards
