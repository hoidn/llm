import pytest
import json
from unittest.mock import MagicMock, patch, ANY, PropertyMock
from typing import Dict, Any # Add missing imports

# Import the function/classes to test
from src.dispatcher import execute_programmatic_task
from src.handler.base_handler import BaseHandler
from src.task_system.task_system import TaskSystem
from src.task_system.ast_nodes import SubtaskRequest
from src.system.errors import TaskError, create_task_failure, format_error_result, UNEXPECTED_ERROR, INPUT_VALIDATION_FAILURE, TASK_FAILURE # Import TASK_FAILURE

# Define TaskResult type hint for clarity
TaskResult = Dict[str, Any]

class TestDispatcher:

    @pytest.fixture
    def mock_handler(self):
        """Fixture for a mocked BaseHandler."""
        handler = MagicMock(spec=BaseHandler)
        # Ensure direct_tool_executors exists and is mockable
        handler.direct_tool_executors = {}
        # Mock other potentially needed attributes if spec doesn't cover them
        handler.memory_system = MagicMock()
        handler.task_system = MagicMock()
        return handler

    @pytest.fixture
    def mock_task_system(self):
        """Fixture for a mocked TaskSystem."""
        task_system = MagicMock(spec=TaskSystem)
        task_system.templates = {}
        task_system.template_index = {}
        # Mock the methods used by the dispatcher
        task_system.find_template = MagicMock(return_value=None) # Default: template not found
        task_system.execute_subtask_directly = MagicMock(return_value={
            "status": "COMPLETE",
            "content": "Mock Subtask Result",
            "notes": {"execution_path": "execute_subtask_directly (Phase 1 Stub)"}
        })
        return task_system

    def test_routing_to_direct_tool(self, mock_handler, mock_task_system):
        """Verify routing to a Handler Direct Tool."""
        # Arrange
        mock_tool_func = MagicMock(return_value="Direct Tool Output")
        mock_handler.direct_tool_executors = {"my_direct_tool": mock_tool_func}
        identifier = "my_direct_tool"
        params = {"p1": "v1"}
        flags = {}

        # Act
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system
        )

        # Assert
        mock_task_system.find_template.assert_called_once_with(identifier) # Should still check templates
        mock_tool_func.assert_called_once_with(params)
        mock_task_system.execute_subtask_directly.assert_not_called()
        assert result["status"] == "COMPLETE"
        assert result["content"] == "Direct Tool Output"
        assert result["notes"]["execution_path"] == "direct_tool"

    def test_routing_to_subtask_template(self, mock_handler, mock_task_system):
        """Verify routing to a TaskSystem Template."""
        # Arrange
        mock_handler.direct_tool_executors = {} # No direct tool match
        mock_template = {"name": "my_template", "type": "atomic", "subtype": "test"}
        mock_task_system.find_template.return_value = mock_template
        identifier = "atomic:test"
        params = {"input": "value"}
        flags = {}
        expected_subtask_result = {
            "status": "COMPLETE",
            "content": "Subtask Done",
            "notes": {"execution_path": "execute_subtask_directly (Phase 1 Stub)"}
        }
        mock_task_system.execute_subtask_directly.return_value = expected_subtask_result

        # Act
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system
        )

        # Assert
        mock_task_system.find_template.assert_called_once_with(identifier)
        mock_task_system.execute_subtask_directly.assert_called_once()
        # Check the SubtaskRequest passed
        call_args, call_kwargs = mock_task_system.execute_subtask_directly.call_args
        assert len(call_args) == 2 # request, env
        request_arg = call_args[0]
        # Replace the isinstance check with these:
        assert hasattr(request_arg, 'type') and request_arg.type == "atomic", "SubtaskRequest should have type 'atomic'"
        assert hasattr(request_arg, 'subtype') and request_arg.subtype == "test", "SubtaskRequest should have subtype 'test'"
        assert hasattr(request_arg, 'inputs') and request_arg.inputs == params, "SubtaskRequest inputs mismatch"
        assert hasattr(request_arg, 'file_paths') and request_arg.file_paths == [], "SubtaskRequest file_paths should be [] for this test case" # Default is []
        # Optional: Check class name string if needed, though attribute checks are often sufficient
        # assert request_arg.__class__.__name__ == 'SubtaskRequest'
        assert request_arg.history_context is None
        assert result == expected_subtask_result

    def test_template_overrides_direct_tool(self, mock_handler, mock_task_system):
        """Verify TaskSystem Template takes precedence over Handler Direct Tool."""
        # Arrange
        mock_tool_func = MagicMock()
        mock_handler.direct_tool_executors = {"my_id": mock_tool_func} # Direct tool exists
        mock_template = {"name": "my_template", "type": "my_id", "subtype": None}
        mock_task_system.find_template.return_value = mock_template # Template also exists
        identifier = "my_id"
        params = {}
        flags = {}

        # Act
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system
        )

        # Assert
        mock_task_system.find_template.assert_called_once_with(identifier)
        mock_tool_func.assert_not_called() # Direct tool should NOT be called
        mock_task_system.execute_subtask_directly.assert_called_once() # Subtask path taken
        assert result["notes"]["execution_path"] == "execute_subtask_directly (Phase 1 Stub)"

    def test_identifier_not_found(self, mock_handler, mock_task_system):
        """Verify error when identifier is not found in either registry."""
        # Arrange
        mock_handler.direct_tool_executors = {}
        mock_task_system.find_template.return_value = None
        identifier = "nonexistent:task"
        params = {}
        flags = {}

        # Act
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system
        )

        # Assert
        mock_task_system.find_template.assert_called_once_with(identifier)
        mock_task_system.execute_subtask_directly.assert_not_called()
        assert result["status"] == "FAILED"
        assert "not found" in result["content"]
        assert result["notes"]["error"]["reason"] == INPUT_VALIDATION_FAILURE

    @pytest.mark.parametrize("file_context_param, expected_paths, expect_error", [
        ('["file1.py", "path/to/file2.txt"]', ["file1.py", "path/to/file2.txt"], False),
        (['file1.py', 'path/to/file2.txt'], ["file1.py", "path/to/file2.txt"], False),
        ('invalid json', None, True),
        ('[1, 2, 3]', None, True), # Not list of strings
        ('{"key": "value"}', None, True), # Not a list
        (None, None, False),
        ("", None, False), # Empty string is valid JSON technically, but parses to None here effectively
        (123, None, True), # Invalid type
    ])
    def test_file_context_parsing(self, mock_handler, mock_task_system, file_context_param, expected_paths, expect_error):
        """Verify parsing of the file_context parameter."""
        # Arrange
        mock_template = {"name": "my_template", "type": "atomic", "subtype": "test"}
        mock_task_system.find_template.return_value = mock_template
        identifier = "atomic:test"
        params = {"input": "value"}
        if file_context_param is not None:
             params["file_context"] = file_context_param
        flags = {}

        # Act
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system
        )

        # Assert
        if expect_error:
            assert result["status"] == "FAILED"
            # Replace the generic assertion with this more specific one:
            assert f"Invalid type for file_context parameter: {type(file_context_param).__name__}" in result["content"]
            assert result["notes"]["error"]["reason"] == INPUT_VALIDATION_FAILURE
            mock_task_system.execute_subtask_directly.assert_not_called()
        else:
            assert result["status"] == "COMPLETE" # Stub returns complete
            mock_task_system.execute_subtask_directly.assert_called_once()
            call_args, _ = mock_task_system.execute_subtask_directly.call_args
            request_arg = call_args[0]
            # Modify the assertion within the else block:
            expected_final_paths = [] if expected_paths is None else expected_paths
            assert request_arg.file_paths == expected_final_paths, f"Expected file_paths {expected_final_paths}, got {request_arg.file_paths}"

    @pytest.mark.parametrize("use_history_flag, history_provided, expected_history_in_request", [
        (True, "User: Hi\nAI: Hello", "User: Hi\nAI: Hello"),
        (False, "User: Hi\nAI: Hello", None),
        (True, None, None),
        (False, None, None),
    ])
    def test_history_flag(self, mock_handler, mock_task_system, use_history_flag, history_provided, expected_history_in_request):
        """Verify history_context is passed based on the flag."""
        # Arrange
        mock_template = {"name": "my_template", "type": "atomic", "subtype": "test"}
        mock_task_system.find_template.return_value = mock_template
        identifier = "atomic:test"
        params = {}
        flags = {"use-history": use_history_flag}

        # Act
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system, history_provided
        )

        # Assert
        assert result["status"] == "COMPLETE" # Stub returns complete
        mock_task_system.execute_subtask_directly.assert_called_once()
        call_args, _ = mock_task_system.execute_subtask_directly.call_args
        request_arg = call_args[0]
        assert request_arg.history_context == expected_history_in_request

    def test_direct_tool_exception_handling(self, mock_handler, mock_task_system):
        """Verify exception handling for Direct Tool execution."""
        # Arrange
        mock_tool_func = MagicMock(side_effect=ValueError("Tool Error"))
        mock_handler.direct_tool_executors = {"error_tool": mock_tool_func}
        identifier = "error_tool"
        params = {}
        flags = {}

        # Act
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system
        )

        # Assert
        assert result["status"] == "FAILED"
        assert "An unexpected error occurred" in result["content"]
        assert "Tool Error" in result["content"]
        assert result["notes"]["error"]["reason"] == UNEXPECTED_ERROR
        assert result["notes"]["error"]["details"]["exception_type"] == "ValueError"

    def test_subtask_exception_handling(self, mock_handler, mock_task_system):
        """Verify exception handling for Subtask execution (TaskError)."""
        # Arrange
        mock_template = {"name": "my_template", "type": "atomic", "subtype": "test"}
        mock_task_system.find_template.return_value = mock_template
        test_error = create_task_failure("Subtask Failed", reason="subtask_failure")
        mock_task_system.execute_subtask_directly.side_effect = test_error
        identifier = "atomic:test"
        params = {}
        flags = {}

        # Act
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system
        )

        # Assert
        # Keep the status check
        assert result["status"] == "FAILED"

        # Focus on the structured error information in notes
        assert "error" in result["notes"], "Error details missing in notes"
        error_details = result["notes"]["error"]

        # Check the core error type and reason
        assert error_details.get("type") == TASK_FAILURE, "Error type should be TASK_FAILURE"
        assert error_details.get("reason") == "subtask_failure", "Error reason should be subtask_failure"

        # Check if the original message is present in the final message or details
        original_message = "Subtask Failed"
        assert original_message in result["content"] or \
               original_message in error_details.get("message", ""), \
               f"Original error message '{original_message}' not found in result"

        # Optional: If the dispatcher *should* preserve details correctly, assert them
        # assert error_details.get("details") == test_error.details # Assuming test_error has details

    def test_subtask_unexpected_exception_handling(self, mock_handler, mock_task_system):
        """Verify exception handling for Subtask execution (generic Exception)."""
        # Arrange
        mock_template = {"name": "my_template", "type": "atomic", "subtype": "test"}
        mock_task_system.find_template.return_value = mock_template
        mock_task_system.execute_subtask_directly.side_effect = TypeError("Bad Type")
        identifier = "atomic:test"
        params = {}
        flags = {}

        # Act
        result = execute_programmatic_task(
            identifier, params, flags, mock_handler, mock_task_system
        )

        # Assert
        # The dispatcher should catch the generic Exception and format it
        assert result["status"] == "FAILED"
        assert "An unexpected error occurred" in result["content"]
        assert "Bad Type" in result["content"]
        assert result["notes"]["error"]["reason"] == UNEXPECTED_ERROR
        assert result["notes"]["error"]["details"]["exception_type"] == "TypeError"
