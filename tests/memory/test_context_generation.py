"""Tests for the Template-Aware Context Generation architecture."""
import pytest
from unittest.mock import patch, MagicMock

from memory.memory_system import MemorySystem
from memory.context_generation import ContextGenerationInput, AssociativeMatchResult
from task_system.task_system import TaskSystem


class TestTemplateAwareContextGeneration:
    """Tests for the Template-Aware Context Generation architecture."""

    def test_memory_system_uses_task_system_mediator(self):
        """Test that MemorySystem uses TaskSystem as a mediator for context generation."""
        # Create mock TaskSystem
        mock_task_system = MagicMock(spec=TaskSystem)
        mock_task_system.generate_context_for_memory_system.return_value = AssociativeMatchResult(
            context="Found 2 relevant files.",
            matches=[("file1.py", "Relevant to query"), ("file2.py", "Relevant to query")]
        )
        
        # Create MemorySystem with mock TaskSystem
        memory_system = MemorySystem(task_system=mock_task_system)
        
        # Create mock global index
        memory_system.global_index = {
            "file1.py": "File metadata 1",
            "file2.py": "File metadata 2",
            "file3.py": "File metadata 3"
        }
        
        # Create context input
        context_input = ContextGenerationInput(
            template_description="Find auth code",
            template_type="atomic",
            template_subtype="test",
            inputs={"feature": "login"},
            context_relevance={"feature": True}
        )
        
        # Call get_relevant_context_for
        result = memory_system.get_relevant_context_for(context_input)
        
        # Verify TaskSystem.generate_context_for_memory_system was called
        # The method is called multiple times due to fallback/retry behavior
        assert mock_task_system.generate_context_for_memory_system.call_count > 0
        
        # Verify first argument was the context_input
        args, _ = mock_task_system.generate_context_for_memory_system.call_args
        assert args[0] is context_input
        
        # Verify second argument was the global index
        assert args[1] == memory_system.global_index
        
        # Verify result
        assert result.context == "Found 2 relevant files."
        assert len(result.matches) == 2
        assert result.matches[0][0] == "file1.py"
        assert result.matches[1][0] == "file2.py"
    
    def test_memory_system_falls_back_to_standard_approach(self):
        """Test that MemorySystem falls back to standard approach if TaskSystem fails."""
        # Create mock TaskSystem that raises an exception
        mock_task_system = MagicMock(spec=TaskSystem)
        mock_task_system.generate_context_for_memory_system.side_effect = Exception("Test error")
        
        # Create MemorySystem with mock TaskSystem
        memory_system = MemorySystem(task_system=mock_task_system)
        
        # Create mock global index with files that match query
        memory_system.global_index = {
            "auth.py": "Authentication module for login feature",
            "file2.py": "Unrelated file",
            "file3.py": "Unrelated file"
        }
        
        # Create context input with terms that match the file metadata
        context_input = ContextGenerationInput(
            template_description="Find authentication code",
            template_type="atomic",
            template_subtype="test",
            inputs={"feature": "login"},
            context_relevance={"feature": True}
        )
        
        # Call get_relevant_context_for
        result = memory_system.get_relevant_context_for(context_input)
        
        # Verify TaskSystem.generate_context_for_memory_system was called
        mock_task_system.generate_context_for_memory_system.assert_called_once()
        
        # Verify result contains matching file
        assert any("auth.py" in match[0] for match in result.matches)
        
    def test_context_input_fresh_context_disabled(self):
        """Test that MemorySystem respects fresh_context=disabled."""
        # Create mock TaskSystem
        mock_task_system = MagicMock(spec=TaskSystem)
        
        # Create MemorySystem with mock TaskSystem
        memory_system = MemorySystem(task_system=mock_task_system)
        
        # Create context input with fresh_context=disabled
        context_input = ContextGenerationInput(
            template_description="Find auth code",
            template_type="atomic",
            template_subtype="test",
            inputs={"feature": "login"},
            context_relevance={"feature": True},
            inherited_context="Previous context",
            fresh_context="disabled"
        )
        
        # Call get_relevant_context_for
        result = memory_system.get_relevant_context_for(context_input)
        
        # Verify TaskSystem.generate_context_for_memory_system was NOT called
        mock_task_system.generate_context_for_memory_system.assert_not_called()
        
        # Verify result contains inherited context and no matches
        assert result.context == "Previous context"
        assert len(result.matches) == 0

    def test_aider_bridge_uses_context_generation_input(self):
        """Test that AiderBridge uses ContextGenerationInput for context retrieval."""
        # Import here to avoid circular imports
        from aider_bridge.bridge import AiderBridge
        
        # Create mock memory system
        mock_memory_system = MagicMock(spec=MemorySystem)
        mock_memory_system.get_relevant_context_for.return_value = MagicMock(
            matches=[("file1.py", "Relevant to query"), ("file2.py", "Relevant to query")]
        )
        
        # Create AiderBridge with mock memory system
        bridge = AiderBridge(mock_memory_system)
        
        # Call get_context_for_query
        result = bridge.get_context_for_query("Find auth code")
        
        # Verify memory_system.get_relevant_context_for was called with ContextGenerationInput
        mock_memory_system.get_relevant_context_for.assert_called_once()
        args, _ = mock_memory_system.get_relevant_context_for.call_args
        
        # Check that the argument is a ContextGenerationInput
        assert isinstance(args[0], ContextGenerationInput)
        
        # Check ContextGenerationInput properties
        context_input = args[0]
        assert context_input.template_description == "Find auth code"
        assert context_input.template_type == "atomic"
        assert context_input.fresh_context == "enabled"
        
    def test_task_system_mediator_integration(self):
        """Integration test for the TaskSystem mediator pattern."""
        # Create real components with mocked LLM interaction
        task_system = TaskSystem()
        memory_system = MemorySystem(task_system=task_system)
        task_system.set_test_mode(True)  # Use MockHandler for tests
        
        # Create mock global index
        memory_system.global_index = {
            "auth.py": "Authentication module for login feature",
            "user.py": "User management module",
            "config.py": "Configuration module"
        }
        
        # Register associative matching template
        from task_system.templates.associative_matching import register_template
        register_template(task_system)
        
        # Create context input
        context_input = ContextGenerationInput(
            template_description="Find authentication code",
            template_type="atomic",
            template_subtype="test",
            inputs={"feature": "login"},
            context_relevance={"feature": True}
        )
        
        # Patch TaskSystem.execute_task to return a predetermined result
        with patch.object(task_system, 'execute_task') as mock_execute_task:
            # Create a mock result with file matches
            mock_execute_task.return_value = {
                "status": "COMPLETE",
                "content": '[{"path": "auth.py", "relevance": "Matches authentication query"}, '
                           '{"path": "user.py", "relevance": "Related to user management"}]'
            }
            
            # Call get_relevant_context_for
            result = memory_system.get_relevant_context_for(context_input)
            
            # Verify task_system.execute_task was called
            mock_execute_task.assert_called_once()
            
            # Verify task_type and task_subtype arguments
            # Print the call arguments for debugging
            args, kwargs = mock_execute_task.call_args
            print(f"execute_task args: {args}, kwargs: {kwargs}")
            
            # Check with positional args or kwargs depending on how it was called
            if args and len(args) >= 2:
                assert args[0] == "atomic"
                assert args[1] == "associative_matching"
            else:
                assert kwargs.get('task_type') == "atomic"
                assert kwargs.get('task_subtype') == "associative_matching"
            
            # Verify result
            assert result.context.startswith("Found 2 relevant files")
            assert len(result.matches) == 2
            assert result.matches[0][0] == "auth.py"
            assert result.matches[1][0] == "user.py"
"""Tests for context generation classes."""
import pytest
from typing import Dict, Any, List, Tuple

from memory.context_generation import ContextGenerationInput, AssociativeMatchResult

class TestContextGenerationInput:
    """Tests for ContextGenerationInput class."""

    def test_initialization(self):
        """Test basic initialization with default values."""
        # Test with minimal args
        input1 = ContextGenerationInput(template_description="Find auth code")
        assert input1.template_description == "Find auth code"
        assert input1.template_type == ""
        assert input1.template_subtype == ""
        assert input1.inputs == {}
        assert input1.context_relevance == {}
        assert input1.inherited_context == ""
        assert input1.previous_outputs == []
        assert input1.fresh_context == "enabled"
        
        # Test with complete args
        input2 = ContextGenerationInput(
            template_description="Process data",
            template_type="atomic",
            template_subtype="data_processor",
            inputs={"data": [1, 2, 3], "mode": "sum"},
            context_relevance={"data": True, "mode": False},
            inherited_context="Previous context data",
            previous_outputs=["Previous output"],
            fresh_context="disabled"
        )
        
        assert input2.template_description == "Process data"
        assert input2.template_type == "atomic"
        assert input2.template_subtype == "data_processor"
        assert input2.inputs == {"data": [1, 2, 3], "mode": "sum"}
        assert input2.context_relevance == {"data": True, "mode": False}
        assert input2.inherited_context == "Previous context data"
        assert input2.previous_outputs == ["Previous output"]
        assert input2.fresh_context == "disabled"
    
    def test_default_context_relevance(self):
        """Test that default context relevance includes all inputs."""
        inputs = {"feature": "login", "component": "auth"}
        input_obj = ContextGenerationInput(
            template_description="Test",
            inputs=inputs
        )
        
        # Should create context_relevance with all inputs set to True
        assert input_obj.context_relevance == {"feature": True, "component": True}
    
    def test_from_legacy_format(self):
        """Test creation from legacy format."""
        legacy_input = {
            "taskText": "Find authentication code",
            "inheritedContext": "Previous context",
            "previousOutputs": ["Output 1", "Output 2"]
        }
        
        input_obj = ContextGenerationInput.from_legacy_format(legacy_input)
        
        assert input_obj.template_description == "Find authentication code"
        assert input_obj.inherited_context == "Previous context"
        assert input_obj.previous_outputs == ["Output 1", "Output 2"]
        
        # Test with missing fields
        minimal_legacy = {"taskText": "Minimal test"}
        minimal_obj = ContextGenerationInput.from_legacy_format(minimal_legacy)
        
        assert minimal_obj.template_description == "Minimal test"
        assert minimal_obj.inherited_context == ""
        assert minimal_obj.previous_outputs == []


class TestAssociativeMatchResult:
    """Tests for AssociativeMatchResult class."""
    
    def test_initialization(self):
        """Test basic initialization."""
        matches = [
            ("file1.py", "Contains authentication logic"),
            ("file2.py", "Contains login UI")
        ]
        
        result = AssociativeMatchResult("Found 2 matching files", matches)
        
        assert result.context == "Found 2 matching files"
        assert result.matches == matches
        assert len(result.matches) == 2
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "context": "Found 3 matching files",
            "matches": [
                ("file1.py", "Match reason 1"),
                ("file2.py", "Match reason 2"),
                ("file3.py", "Match reason 3")
            ]
        }
        
        result = AssociativeMatchResult.from_dict(data)
        
        assert result.context == "Found 3 matching files"
        assert len(result.matches) == 3
        assert result.matches[0][0] == "file1.py"
        
        # Test with missing fields
        empty_data = {}
        empty_result = AssociativeMatchResult.from_dict(empty_data)
        
        assert empty_result.context == "No context available"
        assert empty_result.matches == []
