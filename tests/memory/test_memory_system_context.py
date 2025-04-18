"""Tests for Memory System's context generation functionality."""
import pytest
from unittest.mock import patch, MagicMock

from memory.memory_system import MemorySystem
from memory.context_generation import ContextGenerationInput
from task_system.task_system import TaskSystem


class TestMemorySystemContext:
    """Tests for the Memory System's context generation functionality."""
    
    def test_context_input_handling(self):
        """Test handling of context input objects."""
        memory_system = MemorySystem()
        
        # Initialize _config and _sharded_index for proper flow
        memory_system._config = {
            "sharding_enabled": False,
            "token_size_per_shard": 4000,
            "max_shards": 8,
            "token_estimation_ratio": 0.25
        }
        memory_system._sharded_index = []
        
        # Add this line to initialize global_index
        memory_system.global_index = {"file.py": "Test metadata"}
        
        # Create and configure mock TaskSystem
        mock_task_system = MagicMock(spec=TaskSystem)
        memory_system.task_system = mock_task_system
        
        # Configure mock to return test matches
        from memory.context_generation import AssociativeMatchResult
        mock_task_system.generate_context_for_memory_system.return_value = AssociativeMatchResult(
            context="Found 1 file",
            matches=[("file1.py", "Relevant")]
        )
        
        # Create test input
        input1 = ContextGenerationInput(
            template_description="Find files for authentication",
            inputs={"query": "auth", "max_results": 10},
            context_relevance={"query": True, "max_results": False}
        )
        
        # Test get_relevant_context_for with ContextGenerationInput
        result = memory_system.get_relevant_context_for(input1)
        
        # Verify TaskSystem was called with the right input
        mock_task_system.generate_context_for_memory_system.assert_called_once()
        args = mock_task_system.generate_context_for_memory_system.call_args[0]
        assert args[0] is input1  # First argument should be the context input
        
        # Verify result structure
        assert hasattr(result, "context")
        assert hasattr(result, "matches")
        assert len(result.matches) == 1
        assert result.matches[0].path == "file1.py"
    
    def test_get_relevant_context_for_with_context_input(self):
        """Test get_relevant_context_for with ContextGenerationInput."""
        memory_system = MemorySystem()
        
        # Initialize _config and _sharded_index for proper flow
        memory_system._config = {
            "sharding_enabled": False,
            "token_size_per_shard": 4000,
            "max_shards": 8,
            "token_estimation_ratio": 0.25
        }
        memory_system._sharded_index = []
        
        # Initialize global_index
        memory_system.global_index = {"file1.py": "Test metadata"}
        
        # Create a mock TaskSystem
        mock_task_system = MagicMock(spec=TaskSystem)
        memory_system.task_system = mock_task_system
        
        # Configure mock to return test result
        from memory.context_generation import AssociativeMatchResult
        mock_result = AssociativeMatchResult(
            context="Test context", 
            matches=[("file1.py", "Test relevance")]
        )
        mock_task_system.generate_context_for_memory_system.return_value = mock_result
        
        # Create context input
        context_input = ContextGenerationInput(
            template_description="Test query",
            template_type="test",
            template_subtype="test"
        )
        
        # Call get_relevant_context_for
        result = memory_system.get_relevant_context_for(context_input)
        
        # Verify TaskSystem.generate_context_for_memory_system was called with correct params
        mock_task_system.generate_context_for_memory_system.assert_called_once()
        args = mock_task_system.generate_context_for_memory_system.call_args[0]
        assert args[0] is context_input
        
        # Verify result has expected content
        assert result.context == "Test context"
        assert len(result.matches) == 1
        assert result.matches[0][0] == "file1.py"
    
    def test_get_relevant_context_for_with_legacy_format(self):
        """Test get_relevant_context_for with legacy dictionary format."""
        memory_system = MemorySystem()
        
        # Initialize _config and _sharded_index for proper flow
        memory_system._config = {
            "sharding_enabled": False,
            "token_size_per_shard": 4000,
            "max_shards": 8,
            "token_estimation_ratio": 0.25
        }
        memory_system._sharded_index = []
        
        # Initialize global_index
        memory_system.global_index = {"file1.py": "Test metadata"}
        
        # Create a mock TaskSystem
        mock_task_system = MagicMock(spec=TaskSystem)
        memory_system.task_system = mock_task_system
        
        # Configure mock to return test result
        from memory.context_generation import AssociativeMatchResult
        mock_result = AssociativeMatchResult(
            context="Test context", 
            matches=[("file1.py", "Test relevance")]
        )
        mock_task_system.generate_context_for_memory_system.return_value = mock_result
        
        # Create legacy input format
        legacy_input = {
            "taskText": "Test query",
            "inheritedContext": "Inherited context"
        }
        
        # Call get_relevant_context_for
        result = memory_system.get_relevant_context_for(legacy_input)
        
        # Verify TaskSystem.generate_context_for_memory_system was called with converted input
        mock_task_system.generate_context_for_memory_system.assert_called_once()
        args = mock_task_system.generate_context_for_memory_system.call_args[0]
        assert isinstance(args[0], ContextGenerationInput)
        assert args[0].template_description == "Test query"
        assert args[0].inherited_context == "Inherited context"
        
        # Verify result has expected content
        assert result.context == "Test context"
        assert len(result.matches) == 1
        assert result.matches[0].path == "file1.py"
