"""Integration tests for Memory System with new context generation."""
import pytest
from unittest.mock import MagicMock, patch
import os
import tempfile

from memory.memory_system import MemorySystem
from memory.context_generation import ContextGenerationInput, AssociativeMatchResult
from task_system.task_system import TaskSystem


class TestMemorySystemIntegration:
    """Integration tests for Memory System with new context generation."""
    
    @pytest.fixture
    def memory_system_with_task_system(self):
        """Create a Memory System with TaskSystem for testing."""
        # Create mock TaskSystem
        task_system = MagicMock()
        
        # Get absolute paths for test files
        file1_path = os.path.abspath("file1.py")
        file2_path = os.path.abspath("file2.py")
        file3_path = os.path.abspath("file3.py")
        
        # Mock generate_context_for_memory_system method with absolute paths
        task_system.generate_context_for_memory_system.return_value = AssociativeMatchResult(
            context="Found 2 relevant files",
            matches=[
                (file1_path, "Contains authentication logic"),
                (file2_path, "Contains user model")
            ]
        )
        
        # Create Memory System
        memory_system = MemorySystem()
        
        # Set task_system attribute
        memory_system.task_system = task_system
        
        # Add some test data to global index with absolute paths
        memory_system.update_global_index({
            file1_path: "Authentication module for user login",
            file2_path: "User model definition with profile data",
            file3_path: "Unrelated utility functions"
        })
        
        return memory_system
    
    def test_get_relevant_context_with_context_generation_input(self, memory_system_with_task_system):
        """Test get_relevant_context_for with ContextGenerationInput."""
        memory_system = memory_system_with_task_system
        
        # Create context input
        context_input = ContextGenerationInput(
            template_description="Find authentication code",
            template_type="atomic",
            template_subtype="test",
            inputs={"feature": "login", "component": "auth"},
            context_relevance={"feature": True, "component": True}
        )
        
        # Get relevant context
        result = memory_system.get_relevant_context_for(context_input)
        
        # Verify result
        assert hasattr(result, "context")
        assert hasattr(result, "matches")
        assert "Found 2 relevant files" in result.context
        assert len(result.matches) == 2
        assert os.path.basename(result.matches[0][0]) == "file1.py"
        assert os.path.basename(result.matches[1][0]) == "file2.py"
        
        # Verify TaskSystem was called with correct parameters
        memory_system.task_system.generate_context_for_memory_system.assert_called_once()
        args = memory_system.task_system.generate_context_for_memory_system.call_args[0]
        assert args[0] == context_input
        assert isinstance(args[1], dict)  # global_index
    
    def test_get_relevant_context_with_legacy_format(self, memory_system_with_task_system):
        """Test get_relevant_context_for with legacy dictionary format."""
        memory_system = memory_system_with_task_system
        
        # Create legacy input format
        legacy_input = {
            "taskText": "Find user model code",
            "inheritedContext": "Previous task context"
        }
        
        # Get relevant context
        result = memory_system.get_relevant_context_for(legacy_input)
        
        # Verify result
        assert hasattr(result, "context")
        assert hasattr(result, "matches")
        assert "Found 2 relevant files" in result.context
        assert len(result.matches) == 2
        # Check filenames without full paths
        assert all(os.path.basename(match[0]) in ["file1.py", "file2.py"] for match in result.matches)
        
        # Verify TaskSystem was called
        memory_system.task_system.generate_context_for_memory_system.assert_called_once()
        # Verify conversion to ContextGenerationInput
        args = memory_system.task_system.generate_context_for_memory_system.call_args[0]
        assert isinstance(args[0], ContextGenerationInput)
        assert args[0].template_description == "Find user model code"
        assert args[0].inherited_context == "Previous task context"
    
    def test_fresh_context_disabled(self, memory_system_with_task_system):
        """Test when fresh_context is disabled."""
        memory_system = memory_system_with_task_system
        
        # Create context input with fresh_context=disabled
        context_input = ContextGenerationInput(
            template_description="Find authentication code",
            inherited_context="Inherited context data",
            fresh_context="disabled"
        )
        
        # Get relevant context
        result = memory_system.get_relevant_context_for(context_input)
        
        # Verify result contains only inherited context
        assert result.context == "Inherited context data"
        assert result.matches == []
        
        # Verify TaskSystem was not called
        memory_system.task_system.generate_context_for_memory_system.assert_not_called()
    
    def test_fallback_to_simple_matching(self, memory_system_with_task_system):
        """Test fallback to simple matching when TaskSystem fails."""
        memory_system = memory_system_with_task_system
        
        # Make TaskSystem raise an exception
        memory_system.task_system.generate_context_for_memory_system.side_effect = Exception("Test error")
        
        # Create context input
        context_input = ContextGenerationInput(
            template_description="authentication login",
            inputs={"feature": "login"}
        )
        
        # Get absolute path for test file
        file1_path = os.path.abspath("file1.py")
        
        # Patch _get_relevant_context_standard to verify it's called
        with patch.object(memory_system, '_get_relevant_context_standard') as mock_standard:
            # Create a mock return value with absolute path
            mock_result = MagicMock()
            mock_result.context = "Found files using standard method"
            mock_result.matches = [(file1_path, "Standard match")]
            mock_standard.return_value = mock_result
            
            # Get relevant context
            result = memory_system.get_relevant_context_for(context_input)
            
            # Verify fallback was used
            mock_standard.assert_called_once_with(context_input)
            assert result.context == "Found files using standard method"
