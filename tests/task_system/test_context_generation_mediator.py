"""Integration tests for TaskSystem mediator pattern in context generation."""
import pytest
from unittest.mock import MagicMock, patch
import json
import logging # Import logging

from memory.context_generation import ContextGenerationInput, AssociativeMatchResult
from task_system.task_system import TaskSystem
# Import necessary components to mock
from memory.memory_system import MemorySystem
from handler.base_handler import BaseHandler
# Import the template registration function
from task_system.templates.associative_matching import register_template as register_associative_matching_template


class TestTaskSystemMediator:
    """Tests for TaskSystem's mediator role in context generation."""

    @pytest.fixture
    def task_system_with_mocks(self):
        """Fixture to create TaskSystem with necessary mocked dependencies."""
        task_system = TaskSystem()

        # Create mock MemorySystem and Handler
        mock_memory_system = MagicMock(spec=MemorySystem)
        mock_handler = MagicMock(spec=BaseHandler)
        mock_handler.model_provider = MagicMock() # Must have provider

        # Wire them up: TaskSystem needs MemorySystem reference, MemorySystem needs Handler reference
        mock_memory_system.handler = mock_handler
        task_system.memory_system = mock_memory_system

        # === FIX: Register the associative matching template ===
        # Ensure the TaskSystem instance used in the test knows this template exists.
        register_associative_matching_template(task_system)
        # =======================================================

        # Mock the template execution function that would normally call the LLM
        # This allows us to control the simulated LLM response for the test
        patcher = patch('task_system.templates.associative_matching.execute_template')
        mock_execute_assoc_template = patcher.start()
        # Configure its return value to be the list of dicts format
        mock_execute_assoc_template.return_value = [
            {"path": "file1.py", "relevance": "Contains auth logic"},
            {"path": "file2.py", "relevance": "Contains user model"}
        ]

        # Yield the configured task_system and the mock for assertions in the tests
        yield task_system, mock_execute_assoc_template

        # Cleanup the patch after the test finishes
        patcher.stop()

    def test_generate_context_for_memory_system(self, task_system_with_mocks):
        """Test TaskSystem's generate_context_for_memory_system method."""
        task_system, mock_execute_assoc_template = task_system_with_mocks # Get instances from fixture

        # Create test input: Use the correct subtype and provide necessary inputs
        # for the associative_matching template.
        context_input = ContextGenerationInput(
            template_description="Find auth code",
            template_type="atomic",
            template_subtype="associative_matching", # Critical: Matches the registered template
            inputs={"query": "Find auth code", "metadata": "Mock metadata string", "max_results": 10}, # Provide required inputs
            context_relevance={"query": True}
        )

        # Mock global index (file paths and their metadata content)
        global_index = {
            "file1.py": "Auth module",
            "file2.py": "User module",
            "file3.py": "Unrelated module"
        }

        # Call the method under test (TaskSystem's role as mediator)
        result = task_system.generate_context_for_memory_system(context_input, global_index)

        # Verify the final result object returned by TaskSystem
        assert isinstance(result, AssociativeMatchResult)
        # The context message might have extra details, so use startswith
        assert result.context.startswith("Found 2 relevant files")
        # Verify the number of matches
        assert len(result.matches) == 2
        # Verify the structure and content of the matches (tuples of path, relevance)
        assert result.matches[0] == ("file1.py", "Contains auth logic")
        assert result.matches[1] == ("file2.py", "Contains user model")

        # Verify the mocked template execution function was called once
        mock_execute_assoc_template.assert_called_once()
        call_args, call_kwargs = mock_execute_assoc_template.call_args

        # Verify arguments passed *to* the template execution function
        passed_inputs = call_args[0] # The 'inputs' dict for the template
        passed_handler = call_args[2] # The 'handler' instance passed down
        assert passed_inputs["query"] == "Find auth code"
        assert "metadata" in passed_inputs # Check presence of metadata input
        # Ensure the correct handler instance was passed down the chain
        assert passed_handler is task_system.memory_system.handler
    
    def test_fresh_context_disabled(self, task_system_with_mocks):
        """Test TaskSystem's behavior when fresh_context is disabled."""
        task_system, mock_execute_assoc_template = task_system_with_mocks

        # Create input explicitly disabling fresh context generation
        context_input = ContextGenerationInput(
            template_description="Test query",
            inherited_context="Inherited context data",
            fresh_context="disabled" # Key setting for this test
        )

        # Call the method under test
        result = task_system.generate_context_for_memory_system(
            context_input, {"file1.py": "test"} # Global index doesn't matter here
        )

        # Verify result contains only the inherited context
        assert result.context == "Inherited context data"
        assert result.matches == []
        # Verify the template execution function (LLM path) was NOT called
        mock_execute_assoc_template.assert_not_called()
    
    def test_error_handling(self, task_system_with_mocks):
        """Test error handling during the template execution step."""
        task_system, mock_execute_assoc_template = task_system_with_mocks

        # Configure the mock to raise an error *when called*
        mock_execute_assoc_template.side_effect = json.JSONDecodeError(
            "Simulated JSON error", "doc", 0
        )

        # Create test input (again, ensuring correct subtype and inputs)
        context_input = ContextGenerationInput(
             template_description="Test",
             template_type="atomic",
             template_subtype="associative_matching", # Must match registered template
             inputs={"query": "Test", "metadata": "...", "max_results": 10} # Required inputs
        )

        # Call the method under test
        result = task_system.generate_context_for_memory_system(
            context_input, {"file1.py": "test"}
        )

        # Verify the mock was called (template was found, execution was attempted)
        mock_execute_assoc_template.assert_called_once()

        # Verify graceful error handling in the final result
        assert isinstance(result, AssociativeMatchResult)
        assert result.matches == [] # No matches should be returned on error
        # Check that the context message indicates an error occurred during processing
        # The exact message might vary slightly depending on where the exception is caught.
        assert "Error processing context generation result" in result.context \
            or "Error during associative matching" in result.context \
            or "Context generation failed" in result.context
    def test_handler_missing_in_memory_system(self):
        """Test the case where TaskSystem has MemorySystem, but MemorySystem lacks Handler."""
        task_system = TaskSystem()
        # Register template so the 'template not found' error doesn't mask the real issue
        register_associative_matching_template(task_system)

        mock_memory_system = MagicMock(spec=MemorySystem)
        mock_memory_system.handler = None  # Simulate the missing handler link
        task_system.memory_system = mock_memory_system

        # Patch the template execution to ensure it's NOT called if the handler check fails
        patcher = patch('task_system.templates.associative_matching.execute_template')
        mock_execute_assoc_template = patcher.start()

        context_input = ContextGenerationInput(
            template_description="Test",
            template_type="atomic",
             # Need subtype so execute_task logic is followed up to the handler check
            template_subtype="associative_matching",
            inputs={"query": "Test", "metadata": "...", "max_results": 10}
        )
        # Call the method under test
        result = task_system.generate_context_for_memory_system(context_input, {"file1.py":"meta"})

        # Assert the specific error about the handler missing
        assert "Error: Handler not available for context generation" in result.context
        assert result.matches == []
        # The template execution should not be called if the handler check fails early
        mock_execute_assoc_template.assert_not_called()
        patcher.stop() # Cleanup patch

    def test_memory_system_missing_in_task_system(self):
        """Test the case where TaskSystem itself lacks the MemorySystem reference."""
        task_system = TaskSystem()
        # Register template so the 'template not found' error doesn't mask the real issue
        register_associative_matching_template(task_system)

        task_system.memory_system = None  # Simulate missing memory system reference

        # Patch the template execution to ensure it's NOT called if the memory_system check fails
        patcher = patch('task_system.templates.associative_matching.execute_template')
        mock_execute_assoc_template = patcher.start()

        context_input = ContextGenerationInput(
            template_description="Test",
            template_type="atomic",
            template_subtype="associative_matching", # Need subtype
            inputs={"query": "Test", "metadata": "...", "max_results": 10}
        )
        # Call the method under test
        result = task_system.generate_context_for_memory_system(context_input, {"file1.py":"meta"})

        # Assert the specific error about the handler missing (as that's the ultimate check that fails)
        assert "Error: Handler not available for context generation" in result.context
        assert result.matches == []
        # Template execution not called
        mock_execute_assoc_template.assert_not_called()
        patcher.stop() # Cleanup patch
