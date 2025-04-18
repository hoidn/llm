"""Tests for the Template-Aware Context Generation architecture."""
import pytest
from unittest.mock import patch, MagicMock

from src.memory.memory_system import MemorySystem
from src.memory.context_generation import ContextGenerationInput, AssociativeMatchResult, MatchTuple
from src.task_system.task_system import TaskSystem


class TestTemplateAwareContextGeneration:
    """Tests for the Template-Aware Context Generation architecture."""

    def test_memory_system_uses_task_system_mediator(self):
        """Test that MemorySystem uses TaskSystem as a mediator for context generation."""
        # Create mock TaskSystem
        mock_task_system = MagicMock(spec=TaskSystem)
        mock_task_system.generate_context_for_memory_system.return_value = AssociativeMatchResult(
            context="Found 2 relevant files.",
            matches=[
                MatchTuple(path="file1.py", relevance="Relevant to query", score=0.9),
                MatchTuple(path="file2.py", relevance="Relevant to query", score=0.8)
            ]
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
        assert result.matches[0].path == "file1.py"
        assert result.matches[1].path == "file2.py"
    
    def test_memory_system_handles_task_system_errors(self):
        """Test that MemorySystem handles TaskSystem errors gracefully."""
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
        
        # Verify result contains error message
        assert "Error during context generation" in result.context
        assert len(result.matches) == 0  # No matches on error
        
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
        from src.aider_bridge.bridge import AiderBridge
        
        # Create mock memory system
        mock_memory_system = MagicMock(spec=MemorySystem)
        # Return a proper AssociativeMatchResult Pydantic model
        mock_memory_system.get_relevant_context_for.return_value = AssociativeMatchResult(
            context="Mock context for query",
            matches=[
                MatchTuple(path="file1.py", relevance="Relevant to query", score=0.9),
                MatchTuple(path="file2.py", relevance="Relevant to query", score=0.8)
            ]
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
        # Create real components
        task_system = TaskSystem()
        memory_system = MemorySystem(task_system=task_system)
        
        # Wire TaskSystem <-> MemorySystem (critical for mediator pattern)
        task_system.memory_system = memory_system
        
        # Create mock handler with model_provider (needed by associative_matching)
        from src.handler.base_handler import BaseHandler
        mock_handler = MagicMock(spec=BaseHandler)
        mock_handler.model_provider = MagicMock()  # Must have model_provider
        memory_system.handler = mock_handler  # Assign to memory system
        
        # Create mock global index
        memory_system.global_index = {
            "auth.py": "Authentication module for login feature",
            "user.py": "User management module",
            "config.py": "Configuration module"
        }
        
        # Register associative matching template
        from src.task_system.templates.associative_matching import register_template
        register_template(task_system)
        
        # Create context input with correct subtype and required inputs
        context_input = ContextGenerationInput(
            template_description="Find authentication code",
            template_type="atomic",
            template_subtype="associative_matching",  # Use actual subtype
            inputs={"query": "Find authentication code", "metadata": "...", "max_results": 5},
            context_relevance={"query": True}
        )
        
        # Mock the template execution function (simulates LLM call)
        with patch('src.task_system.templates.associative_matching.execute_template') as mock_execute_template:
            # Configure mock to return the expected list of dicts format
            mock_execute_template.return_value = [
                {"path": "auth.py", "relevance": "Matches authentication query", "score": 0.95},
                {"path": "user.py", "relevance": "Related to user management", "score": 0.85}
            ]
            
            # Call get_relevant_context_for
            result = memory_system.get_relevant_context_for(context_input)
            
            # Verify the mock was called
            mock_execute_template.assert_called_once()
        
            # Verify arguments passed to the mocked function
            call_args, call_kwargs = mock_execute_template.call_args
            passed_inputs = call_args[0]  # First arg is 'inputs' dict
            passed_handler = call_args[2]  # Third arg is handler
            assert passed_inputs['query'] == "Find authentication code"
            assert passed_handler is mock_handler  # Ensure correct handler was passed
            
            # Verify result
            assert isinstance(result, AssociativeMatchResult)
            assert result.context.startswith("Found 2 relevant files")
            assert len(result.matches) == 2
            assert result.matches[0].path == "auth.py"
            assert result.matches[0].relevance == "Matches authentication query"
            assert result.matches[0].score == 0.95
            assert result.matches[1].path == "user.py"
            assert result.matches[1].relevance == "Related to user management"
            assert result.matches[1].score == 0.85
"""Tests for context generation classes."""
import pytest
from typing import Dict, Any, List, Tuple
from pydantic import ValidationError

from src.memory.context_generation import ContextGenerationInput, AssociativeMatchResult, MatchTuple

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
        assert input1.history_context is None # Check new default
        
        # Test validation with invalid input
        with pytest.raises(ValidationError):
            ContextGenerationInput(template_description=123)  # type error

        # Test with complete args
        input2 = ContextGenerationInput(
            template_description="Process data",
            template_type="atomic",
            template_subtype="data_processor",
            inputs={"data": [1, 2, 3], "mode": "sum"},
            context_relevance={"data": True, "mode": False},
            inherited_context="Previous context data",
            previous_outputs=["Previous output"],
            fresh_context="disabled",
            history_context="User: Hi\nAssistant: Hello" # Add history
        )

        assert input2.template_description == "Process data"
        assert input2.template_type == "atomic"
        assert input2.template_subtype == "data_processor"
        assert input2.inputs == {"data": [1, 2, 3], "mode": "sum"}
        assert input2.context_relevance == {"data": True, "mode": False}
        assert input2.inherited_context == "Previous context data"
        assert input2.previous_outputs == ["Previous output"]
        assert input2.fresh_context == "disabled"
        assert input2.history_context == "User: Hi\nAssistant: Hello" # Check history

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
        assert input_obj.history_context is None # Check history default

        # Test with history in legacy
        legacy_with_history = {
            "taskText": "Find auth code",
            "history_context": "User: Query\nAssistant: Response"
        }
        input_with_history = ContextGenerationInput.from_legacy_format(legacy_with_history)
        assert input_with_history.history_context == "User: Query\nAssistant: Response"

        # Test with missing fields
        minimal_legacy = {"taskText": "Minimal test"}
        minimal_obj = ContextGenerationInput.from_legacy_format(minimal_legacy)
        
        assert minimal_obj.template_description == "Minimal test"
        assert minimal_obj.inherited_context == ""
        assert minimal_obj.previous_outputs == []
        assert minimal_obj.history_context is None


class TestAssociativeMatchResult:
    """Tests for AssociativeMatchResult class."""
    
    def test_initialization(self):
        """Test basic initialization."""
        matches = [
            MatchTuple(path="file1.py", relevance="Contains authentication logic", score=0.9),
            MatchTuple(path="file2.py", relevance="Contains login UI", score=0.8)
        ]
        
        result = AssociativeMatchResult(context="Found 2 matching files", matches=matches)
        
        assert result.context == "Found 2 matching files"
        assert len(result.matches) == 2
        assert result.matches[0].path == "file1.py"
        assert result.matches[0].relevance == "Contains authentication logic"
        assert result.matches[0].score == 0.9
        
        # Test validation
        with pytest.raises(ValidationError):
            AssociativeMatchResult(context="Test", matches="not a list")  # type error
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "context": "Found 3 matching files",
            "matches": [
                {"path": "file1.py", "relevance": "Match reason 1", "score": 0.9},
                {"path": "file2.py", "relevance": "Match reason 2", "score": 0.8},
                {"path": "file3.py", "relevance": "Match reason 3", "score": 0.7}
            ]
        }
        
        result = AssociativeMatchResult.model_validate(data)
        
        assert result.context == "Found 3 matching files"
        assert len(result.matches) == 3
        assert result.matches[0].path == "file1.py"
        assert result.matches[0].score == 0.9
        
        # Test with missing fields
        with pytest.raises(ValidationError):
            AssociativeMatchResult.model_validate({})
        
        # Test with minimal valid data
        minimal_result = AssociativeMatchResult(context="No context", matches=[])
        assert minimal_result.context == "No context"
        assert minimal_result.matches == []
