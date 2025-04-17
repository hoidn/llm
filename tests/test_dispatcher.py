import pytest
from unittest.mock import MagicMock, patch, ANY # ANY is useful for partial argument matching
from typing import Dict, Any

# Import the function to test
from src.dispatcher import execute_programmatic_task

# Import necessary classes/types to mock or type hint
from src.handler.base_handler import BaseHandler # Or specific handler
from src.task_system.task_system import TaskSystem
from src.task_system.ast_nodes import SubtaskRequest
from src.system.errors import TaskError, create_task_failure, format_error_result, UNEXPECTED_ERROR, INPUT_VALIDATION_FAILURE

# Define TaskResult type hint for clarity
TaskResult = Dict[str, Any]


class TestDispatcher:

    @pytest.fixture
    def mock_handler(self):
        handler = MagicMock(spec=BaseHandler) # Use spec for better mocking
        handler.tool_executors = {} # Simulate the tool registry
        # Ensure the spec includes the attribute we check for
        # If BaseHandler doesn't define tool_executors, mock might complain without this:
        # type(handler).tool_executors = PropertyMock(return_value={})
        return handler

    @pytest.fixture
    def mock_task_system(self):
        task_system = MagicMock(spec=TaskSystem)
        task_system.templates = {} # Simulate template registry
        task_system.template_index = {}
        # Mock the method we expect to be called for subtasks
        task_system.execute_subtask_directly = MagicMock(return_value={
            "status": "COMPLETE", "content": "Mock Subtask Result", "notes": {"execution_path": "subtask_template"} # Add expected note
        })
        # Mock find_template used by the dispatcher to check for templates
        task_system.find_template = MagicMock(return_value=None) # Default to not found
        return task_system

    def test_routing_to_direct_tool(self, mock_handler, mock_task_system):
        # Arrange: Register a mock direct tool executor in the handler
        mock_tool_func = MagicMock(return_value="Raw Tool Result")
        # Ensure the mock handler *has* the tool_executors attribute
        mock_handler.tool_executors = {"tool:direct": mock_tool_func}
        identifier = "tool:direct"
        params = {"arg1": "value1"}
        flags = {}

        # Act: Call the dispatcher
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system
        )

        # Assert:
        # 1. Check that the handler's tool executor was called correctly
        mock_tool_func.assert_called_once_with(params)
        # 2. Check that the TaskSystem's execute_subtask_directly was NOT called
        mock_task_system.execute_subtask_directly.assert_not_called()
        # 3. Check that the result is a correctly formatted TaskResult
        assert result["status"] == "COMPLETE"
        assert result["content"] == "Raw Tool Result" # Based on simple wrapping logic
        assert result["notes"] == {"execution_path": "direct_tool"}

    def test_routing_to_subtask_template(self, mock_handler, mock_task_system):
        # Arrange:
        # - Handler has NO tool for this identifier
        mock_handler.tool_executors = {}
        # - TaskSystem *does* have a template for this identifier
        mock_task_system.find_template.return_value = {"name": "template_name", "type": "sub", "subtype": "task"} # Mock template definition
        identifier = "sub:task"
        params = {"input1": "data"}
        flags = {}
        # Mock the return value of the subtask execution
        expected_subtask_result = {"status": "COMPLETE", "content": "Subtask Done", "notes": {"detail": "abc", "execution_path": "subtask_template"}} # Ensure note is present
        mock_task_system.execute_subtask_directly.return_value = expected_subtask_result

        # Act: Call the dispatcher
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system
        )

        # Assert:
        # 1. Check that TaskSystem.find_template was called
        mock_task_system.find_template.assert_called_once_with(identifier)
        # 2. Check that TaskSystem.execute_subtask_directly was called
        mock_task_system.execute_subtask_directly.assert_called_once()
        # 3. Verify the SubtaskRequest passed to execute_subtask_directly
        call_args = mock_task_system.execute_subtask_directly.call_args[0] # Get positional args
        assert len(call_args) == 1
        request_arg = call_args[0]
        assert isinstance(request_arg, SubtaskRequest)
        assert request_arg.type == "sub"
        assert request_arg.subtype == "task"
        assert request_arg.inputs == params
        assert request_arg.file_paths == [] # Explicit file_context not passed
        # 4. Check that the final result matches the one from TaskSystem
        assert result == expected_subtask_result

    def test_identifier_not_found(self, mock_handler, mock_task_system):
        # Arrange: Neither Handler nor TaskSystem have the identifier
        mock_handler.tool_executors = {}
        mock_task_system.find_template.return_value = None
        identifier = "unknown:task"
        params = {}
        flags = {}

        # Act: Call the dispatcher
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system
        )

        # Assert:
        # 1. Check that the result indicates failure
        assert result["status"] == "FAILED"
        assert "not found" in result["content"]
        assert result["notes"]["error"]["type"] == "TASK_FAILURE"
        assert result["notes"]["error"]["reason"] == INPUT_VALIDATION_FAILURE
        # 2. Check that neither execution path was called
        mock_task_system.execute_subtask_directly.assert_not_called()
        # (No direct tool function to check call for)

    def test_handling_task_error(self, mock_handler, mock_task_system):
        # Arrange: Mock the target (e.g., subtask execution) to raise TaskError
        test_error = create_task_failure("Something specific failed", reason="subtask_failure", details={"step": 3})
        mock_task_system.find_template.return_value = {"name": "template_name", "type": "sub", "subtype": "task"} # Found template
        mock_task_system.execute_subtask_directly.side_effect = test_error
        identifier = "sub:task"
        params = {}
        flags = {}

        # Act: Call the dispatcher
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system
        )

        # Assert:
        # 1. Check that the result is the formatted version of the original error
        assert result["status"] == "FAILED"
        assert result["content"] == test_error.message
        assert result["notes"]["error"]["type"] == test_error.error_type
        assert result["notes"]["error"]["reason"] == test_error.reason
        assert result["notes"]["error"]["details"] == test_error.details

    def test_handling_unexpected_exception(self, mock_handler, mock_task_system):
        # Arrange: Mock the target (e.g., direct tool) to raise a standard Python Exception
        mock_tool_func = MagicMock(side_effect=ValueError("Bad value"))
        mock_handler.tool_executors = {"tool:direct": mock_tool_func}
        identifier = "tool:direct"
        params = {}
        flags = {}

        # Act: Call the dispatcher
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system
        )

        # Assert:
        # 1. Check that the result indicates failure with an unexpected error reason
        assert result["status"] == "FAILED"
        assert "An unexpected error occurred" in result["content"]
        assert result["notes"]["error"]["type"] == "TASK_FAILURE"
        assert result["notes"]["error"]["reason"] == UNEXPECTED_ERROR
        assert result["notes"]["error"]["details"]["exception_type"] == "ValueError"
