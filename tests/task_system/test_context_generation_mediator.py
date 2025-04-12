"""Integration tests for TaskSystem mediator pattern in context generation."""
import pytest
from unittest.mock import MagicMock, patch
import json

from memory.context_generation import ContextGenerationInput, AssociativeMatchResult
from task_system.task_system import TaskSystem


class TestTaskSystemMediator:
    """Tests for TaskSystem's mediator role in context generation."""

    @pytest.fixture
    def task_system_with_mocks(self):
        """Fixture to create TaskSystem with necessary mocked dependencies."""
        task_system = TaskSystem()

        # Create mock MemorySystem and Handler
        from memory.memory_system import MemorySystem
        from handler.base_handler import BaseHandler
        mock_memory_system = MagicMock(spec=MemorySystem)
        mock_handler = MagicMock(spec=BaseHandler)
        mock_handler.model_provider = MagicMock()  # Must have provider

        # Wire them up
        mock_memory_system.handler = mock_handler
        task_system.memory_system = mock_memory_system

        # Mock the template execution function
        patcher = patch('task_system.templates.associative_matching.execute_template')
        mock_execute_assoc_template = patcher.start()
        # Configure its return value (list of dicts)
        mock_execute_assoc_template.return_value = [
            {"path": "file1.py", "relevance": "Contains auth logic"},
            {"path": "file2.py", "relevance": "Contains user model"}
        ]

        # Yield the configured task_system and the mock for assertions
        yield task_system, mock_execute_assoc_template

        # Cleanup the patch after the test runs
        patcher.stop()

    def test_generate_context_for_memory_system(self, task_system_with_mocks):
        """Test TaskSystem's generate_context_for_memory_system method."""
        task_system, mock_execute_assoc_template = task_system_with_mocks
        
        # Create test input with correct subtype and required inputs
        context_input = ContextGenerationInput(
            template_description="Find auth code",
            template_type="atomic",
            template_subtype="associative_matching",  # Use the subtype that triggers the mocked path
            inputs={"query": "Find auth code", "metadata": "Mock metadata string", "max_results": 10},
            context_relevance={"query": True}
        )
        
        # Create mock global index
        global_index = {
            "file1.py": "Auth module",
            "file2.py": "User module",
            "file3.py": "Unrelated module"
        }
        
        # Call the method under test
        result = task_system.generate_context_for_memory_system(context_input, global_index)
        
        # Verify the result format and content
        assert isinstance(result, AssociativeMatchResult)
        assert result.context.startswith("Found 2 relevant files")
        assert len(result.matches) == 2
        assert result.matches[0] == ("file1.py", "Contains auth logic")
        assert result.matches[1] == ("file2.py", "Contains user model")
        
        # Verify the mocked template execution function was called correctly
        mock_execute_assoc_template.assert_called_once()
        call_args, call_kwargs = mock_execute_assoc_template.call_args
        
        # Verify inputs passed to template execution
        passed_inputs = call_args[0]
        assert passed_inputs["query"] == "Find auth code"
        assert "metadata" in passed_inputs
        assert passed_inputs["additional_context"] == {}  # No extra context in this test case
        
        # Verify the correct handler was passed down
        assert call_args[2] is task_system.memory_system.handler
    
    def test_fresh_context_disabled(self, task_system_with_mocks):
        """Test when fresh_context is disabled."""
        task_system, mock_execute_assoc_template = task_system_with_mocks
        
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
        
        # Verify the template execution (LLM call path) was not reached
        mock_execute_assoc_template.assert_not_called()
    
    def test_error_handling(self, task_system_with_mocks):
        """Test error handling during the template execution step."""
        task_system, mock_execute_assoc_template = task_system_with_mocks
        
        # Configure the mock to raise an error
        mock_execute_assoc_template.side_effect = json.JSONDecodeError(
            "Simulated JSON error", "doc", 0
        )
        
        # Create test input with correct subtype and required inputs
        context_input = ContextGenerationInput(
            template_description="Test",
            template_type="atomic",
            template_subtype="associative_matching",
            inputs={"query": "Test", "metadata": "...", "max_results": 10}
        )
        
        # Call the method under test
        result = task_system.generate_context_for_memory_system(
            context_input, {"file1.py": "test"}
        )
        
        # Verify the mock was called (error happened inside it)
        mock_execute_assoc_template.assert_called_once()
        
        # Verify graceful error handling
        assert isinstance(result, AssociativeMatchResult)
        assert result.matches == []
    def test_handler_missing_in_memory_system(self):
        """Test the case where TaskSystem has MemorySystem, but MemorySystem lacks Handler."""
        task_system = TaskSystem()
        from memory.memory_system import MemorySystem
        mock_memory_system = MagicMock(spec=MemorySystem)
        mock_memory_system.handler = None  # Simulate missing handler
        task_system.memory_system = mock_memory_system

        patcher = patch('task_system.templates.associative_matching.execute_template')
        mock_execute_assoc_template = patcher.start()

        context_input = ContextGenerationInput(template_description="Test")
        result = task_system.generate_context_for_memory_system(context_input, {"file1.py":"meta"})

        assert "Error: Handler not available for context generation" in result.context
        assert result.matches == []
        mock_execute_assoc_template.assert_not_called()
        patcher.stop()

    def test_memory_system_missing_in_task_system(self):
        """Test the case where TaskSystem itself lacks the MemorySystem reference."""
        task_system = TaskSystem()
        task_system.memory_system = None  # Simulate missing memory system

        patcher = patch('task_system.templates.associative_matching.execute_template')
        mock_execute_assoc_template = patcher.start()

        context_input = ContextGenerationInput(template_description="Test")
        result = task_system.generate_context_for_memory_system(context_input, {"file1.py":"meta"})

        assert "Error: Handler not available for context generation" in result.context
        assert result.matches == []
        mock_execute_assoc_template.assert_not_called()
        patcher.stop()
