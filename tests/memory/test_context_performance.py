"""Tests for context generation performance with large inputs."""
import pytest
import time
from unittest.mock import patch, MagicMock

from memory.context_generation import ContextGenerationInput
from memory.memory_system import MemorySystem

class TestContextPerformance:
    """Tests for context generation performance."""
    
    @pytest.fixture
    def setup_components(self):
        """Set up memory system with mock handler."""
        # Create a mock handler
        mock_handler = MagicMock()
        mock_handler.determine_relevant_files.return_value = [
            ("file1.py", "Relevant to query"),
            ("file2.py", "Contains related functionality")
        ]
        
        # Create memory system with mock handler
        memory_system = MemorySystem(handler=mock_handler)
        memory_system.global_index = {
            f"file{i}.py": f"metadata{i}" for i in range(1, 101)
        }
        
        return memory_system, mock_handler
    
    def test_performance_with_large_input(self, setup_components):
        """Test performance with large structured input."""
        memory_system, mock_handler = setup_components
        
        # Generate a large complex input
        large_input = {
            "query": "authentication",
            "topics": ["security", "login", "password", "session", "token"] * 10,  # 50 items
            "parameters": {k: f"value{k}" for k in range(100)},  # 100 key-value pairs
            "settings": {"max_depth": 10, "include_comments": True, "verbose": False}
        }
        
        # Create context input with large input
        context_input = ContextGenerationInput(
            template_description="Large input test",
            template_type="test",
            template_subtype="performance",
            inputs=large_input,
            context_relevance={
                "query": True,
                "topics": True,
                "parameters": True,
                "settings": False
            }
        )
        
        # Measure time to process
        start_time = time.time()
        result = memory_system.get_relevant_context_for(context_input)
        end_time = time.time()
        
        # Verify we got a result and timing is reasonable (adjust threshold as needed)
        assert hasattr(result, "matches")
        assert len(result.matches) == 2
        
        # Performance should be under 50ms for this operation (very generous threshold)
        # Adjust based on your performance requirements
        assert (end_time - start_time) < 0.05, f"Performance too slow: {(end_time - start_time)*1000:.2f}ms"
        
        # Verify handler was called with the context input
        mock_handler.determine_relevant_files.assert_called_once()
        args = mock_handler.determine_relevant_files.call_args[0]
        assert args[0] == context_input
    
    def test_backward_compatibility_performance(self, setup_components):
        """Test performance with legacy format."""
        memory_system, mock_handler = setup_components
        
        # Use legacy format
        legacy_input = {
            "taskText": "This is a very long query with lots of text " * 20,  # ~800 chars
            "inheritedContext": "Additional context information " * 10  # ~300 chars
        }
        
        # Measure time to process
        start_time = time.time()
        result = memory_system.get_relevant_context_for(legacy_input)
        end_time = time.time()
        
        # Verify we got a result
        assert hasattr(result, "matches")
        assert len(result.matches) == 2
        
        # Performance should be under 50ms (very generous threshold)
        assert (end_time - start_time) < 0.05, f"Performance too slow: {(end_time - start_time)*1000:.2f}ms"
        
        # Verify it was converted to ContextGenerationInput
        mock_handler.determine_relevant_files.assert_called_once()
        args = mock_handler.determine_relevant_files.call_args[0]
        assert isinstance(args[0], ContextGenerationInput)
        assert args[0].template_description == legacy_input["taskText"]
