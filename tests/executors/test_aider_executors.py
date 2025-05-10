# tests/executors/test_aider_executors.py
import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock # Import AsyncMock
from typing import Callable # Add Callable

# Import functions to test
try:
    from src.executors.aider_executors import AiderExecutorFunctions
except ImportError:
    AiderExecutorFunctions = None # type: ignore

# Import bridge for specing mock
try:
    from src.aider_bridge.bridge import AiderBridge
except ImportError:
    AiderBridge = None # type: ignore

# Import models
from src.system.models import TaskResult, TaskFailureError, TaskFailureReason

# Use fixtures defined above (or in conftest)
pytestmark = pytest.mark.skipif(AiderExecutorFunctions is None or AiderBridge is None,
                                reason="AiderExecutorFunctions or AiderBridge class not found")

# Helper to create a TaskResult dict
def _create_task_result_dict(status="COMPLETE", content="", notes=None, error=None):
    """Creates a TaskResult dict, adding error to notes if provided."""
    if notes is None:
        notes = {}
    if error:
        # Assume error is already a dict conforming to TaskError structure
        notes['error'] = error
    # Use model_dump for consistency, even though it's just a dict helper
    return TaskResult(status=status, content=content, notes=notes).model_dump(exclude_none=True)

# --- Test Class ---
class TestAiderExecutorFunctions:

    @pytest.fixture
    def mock_aider_bridge(self):
        """Provides an AsyncMock for AiderBridge."""
        # Use spec=AiderBridge if AiderBridge is importable and stable
        # Make the relevant method awaitable
        mock = MagicMock(spec=AiderBridge)
        mock.call_aider_tool = AsyncMock() # Make the method async
        return mock

    # --- Tests for execute_aider_automatic ---

    @pytest.mark.asyncio
    async def test_execute_aider_automatic_success_with_editable_files_list(self, mock_aider_bridge):
        """Verify execute_aider_automatic calls bridge correctly when editable_files is a list."""
        # Arrange
        input_params = {
            "prompt": "Refactor this code.",
            "editable_files": ["file1.py", "util/helper.py"] # Use editable_files as list
        }
        # Simulate bridge returning a successful TaskResult dict
        mock_response_dict = _create_task_result_dict(content="Refactoring diff...", notes={"success": True})
        # Configure the awaitable mock method
        mock_aider_bridge.call_aider_tool.return_value = mock_response_dict

        # Expected parameters for the MCP server's tool
        expected_mcp_params = {
            "ai_coding_prompt": "Refactor this code.",
            "relative_editable_files": ["file1.py", "util/helper.py"], # CHANGED KEY
            # Add other defaults expected by the aider_ai_code tool if any
            "relative_readonly_files": [], # Changed from None to empty list
            "model": None # Assuming None if not provided
        }

        # Act
        # Await the executor function call
        result = await AiderExecutorFunctions.execute_aider_automatic(input_params, mock_aider_bridge)

        # Assert
        # Use assert_awaited_once_with for async mocks
        mock_aider_bridge.call_aider_tool.assert_awaited_once_with(
            tool_name="aider_ai_code",
            params=expected_mcp_params
        )
        assert result == mock_response_dict # Should return the bridge's result directly

    @pytest.mark.asyncio
    async def test_execute_aider_automatic_success_with_editable_files_json_string(self, mock_aider_bridge):
        """Verify execute_aider_automatic calls bridge correctly when editable_files is a JSON string."""
        # Arrange
        input_params = {
            "prompt": "Refactor this code.",
            "editable_files": json.dumps(["file3.py", "module/file4.py"]) # Use editable_files as JSON string
        }
        mock_response_dict = _create_task_result_dict(content="Refactoring diff...", notes={"success": True})
        mock_aider_bridge.call_aider_tool.return_value = mock_response_dict

        expected_mcp_params = {
            "ai_coding_prompt": "Refactor this code.",
            "relative_editable_files": ["file3.py", "module/file4.py"], # CHANGED KEY
            "relative_readonly_files": [],
            "model": None
        }
        # Act
        result = await AiderExecutorFunctions.execute_aider_automatic(input_params, mock_aider_bridge)
        # Assert
        mock_aider_bridge.call_aider_tool.assert_awaited_once_with(tool_name="aider_ai_code", params=expected_mcp_params)
        assert result == mock_response_dict

    @pytest.mark.asyncio
    async def test_execute_aider_automatic_success_no_files_provided(self, mock_aider_bridge):
        """Verify execute_aider_automatic works without any files parameter."""
        # Arrange
        input_params = {"prompt": "Explain this."}
        mock_response_dict = _create_task_result_dict(content="Explanation...")
        mock_aider_bridge.call_aider_tool.return_value = mock_response_dict
        expected_mcp_params = {
            "ai_coding_prompt": "Explain this.",
            "relative_editable_files": [], # CHANGED KEY # Expect empty list if no files key
            "relative_readonly_files": [],
            "model": None
        }
        # Act
        result = await AiderExecutorFunctions.execute_aider_automatic(input_params, mock_aider_bridge)
        # Assert
        mock_aider_bridge.call_aider_tool.assert_awaited_once_with(tool_name="aider_ai_code", params=expected_mcp_params)
        assert result == mock_response_dict

    @pytest.mark.asyncio
    @patch('src.executors.aider_executors.logger.warning')
    async def test_execute_aider_automatic_fallback_to_file_context(self, mock_logger_warning, mock_aider_bridge):
        """Verify fallback to file_context and warning log."""
        # Arrange
        input_params = {
            "prompt": "Refactor this code.",
            "file_context": ["fallback.py"] # Use deprecated file_context
        }
        mock_response_dict = _create_task_result_dict(content="Refactoring diff...", notes={"success": True})
        mock_aider_bridge.call_aider_tool.return_value = mock_response_dict

        expected_mcp_params = {
            "ai_coding_prompt": "Refactor this code.",
            "relative_editable_files": ["fallback.py"], # CHANGED KEY
            "relative_readonly_files": [],
            "model": None
        }
        # Act
        result = await AiderExecutorFunctions.execute_aider_automatic(input_params, mock_aider_bridge)
        # Assert
        mock_aider_bridge.call_aider_tool.assert_awaited_once_with(tool_name="aider_ai_code", params=expected_mcp_params)
        assert result == mock_response_dict
        mock_logger_warning.assert_called_once()
        assert "deprecated 'file_context' key" in mock_logger_warning.call_args[0][0]
        assert "execute_aider_automatic" in mock_logger_warning.call_args[0][0]


    @pytest.mark.asyncio
    @patch('src.executors.aider_executors.logger.warning')
    async def test_execute_aider_automatic_editable_files_takes_precedence(self, mock_logger_warning, mock_aider_bridge):
        """Verify editable_files is used if both editable_files and file_context are present."""
        # Arrange
        input_params = {
            "prompt": "Refactor this code.",
            "editable_files": ["actual.py"],
            "file_context": ["ignored.py"] # This should be ignored
        }
        mock_response_dict = _create_task_result_dict(content="Refactoring diff...", notes={"success": True})
        mock_aider_bridge.call_aider_tool.return_value = mock_response_dict

        expected_mcp_params = {
            "ai_coding_prompt": "Refactor this code.",
            "relative_editable_files": ["actual.py"], # CHANGED KEY # actual.py should be used
            "relative_readonly_files": [],
            "model": None
        }
        # Act
        result = await AiderExecutorFunctions.execute_aider_automatic(input_params, mock_aider_bridge)
        # Assert
        mock_aider_bridge.call_aider_tool.assert_awaited_once_with(tool_name="aider_ai_code", params=expected_mcp_params)
        assert result == mock_response_dict
        mock_logger_warning.assert_not_called() # Warning should not be logged as fallback was not used

    @pytest.mark.asyncio
    async def test_execute_aider_automatic_bridge_failure(self, mock_aider_bridge):
        """Verify execute_aider_automatic returns FAILED result on bridge failure."""
        # Arrange
        input_params = {"prompt": "Refactor this code."}
        # Simulate bridge returning a FAILED TaskResult dict
        fail_error = TaskFailureError(type="TASK_FAILURE", reason="tool_execution_error", message="Bridge connection failed").model_dump()
        mock_error_dict = _create_task_result_dict(status="FAILED", content="Bridge connection failed", error=fail_error)
        mock_aider_bridge.call_aider_tool.return_value = mock_error_dict

        # Act
        result = await AiderExecutorFunctions.execute_aider_automatic(input_params, mock_aider_bridge)

        # Assert
        mock_aider_bridge.call_aider_tool.assert_awaited_once() # Check call was made
        assert result == mock_error_dict # Executor returns the failure result

    @pytest.mark.asyncio
    async def test_execute_aider_automatic_missing_prompt(self, mock_aider_bridge):
        """Verify execute_aider_automatic returns FAILED on missing prompt."""
        # Arrange
        input_params = {"editable_files": "[]"} # Missing prompt, using new key for consistency
        # mock_aider_bridge.call_aider_tool doesn't need specific config here

        # Act
        result = await AiderExecutorFunctions.execute_aider_automatic(input_params, mock_aider_bridge)

        # Assert
        mock_aider_bridge.call_aider_tool.assert_not_awaited() # Bridge should not be called
        assert result.get("status") == "FAILED"
        assert "Missing required parameter: 'prompt'" in result.get("content", "")
        error_note = result.get("notes", {}).get("error")
        assert error_note is not None
        assert isinstance(error_note, dict)
        assert error_note.get("reason") == "input_validation_failure"

    @pytest.mark.asyncio
    async def test_execute_aider_automatic_invalid_files_param_json(self, mock_aider_bridge):
        """Verify execute_aider_automatic returns FAILED on invalid files_param JSON."""
        # Arrange
        input_params = {"prompt": "Test", "editable_files": "not a valid json string"}
        # mock_aider_bridge.call_aider_tool doesn't need specific config here

        # Act
        result = await AiderExecutorFunctions.execute_aider_automatic(input_params, mock_aider_bridge)

        # Assert
        mock_aider_bridge.call_aider_tool.assert_not_awaited()
        assert result.get("status") == "FAILED"
        assert "Failed to parse files parameter string" in result.get("content", "")
        error_note = result.get("notes", {}).get("error")
        assert error_note is not None
        assert isinstance(error_note, dict)
        assert error_note.get("reason") == "input_validation_failure"

    # --- Tests for execute_aider_interactive ---
    # Note: These assume interactive mode maps to 'aider_ai_code' for now.
    # Adjust tool_name and expected_mcp_params if a different server tool is used.

    @pytest.mark.asyncio
    async def test_execute_aider_interactive_success_with_editable_files_list(self, mock_aider_bridge):
        """Verify execute_aider_interactive calls bridge correctly with editable_files list."""
        # Arrange
        input_params = {
            "query": "Start interactive refactor.", # Use 'query' key
            "editable_files": ["main.py"] # Use editable_files as list
        }
        mock_response_dict = _create_task_result_dict(content="Interactive session started diff...")
        mock_aider_bridge.call_aider_tool.return_value = mock_response_dict

        # Assuming interactive maps to aider_ai_code for now
        expected_mcp_params = {
            "ai_coding_prompt": "Start interactive refactor.",
            "relative_editable_files": ["main.py"], # CHANGED KEY
            "relative_readonly_files": [],
            "model": None
        }

        # Act
        result = await AiderExecutorFunctions.execute_aider_interactive(input_params, mock_aider_bridge)

        # Assert
        # Assuming interactive call also uses 'aider_ai_code' for now
        mock_aider_bridge.call_aider_tool.assert_awaited_once_with(
            tool_name="aider_ai_code", # Adjust if interactive uses a different MCP tool
            params=expected_mcp_params
        )
        assert result == mock_response_dict

    @pytest.mark.asyncio
    async def test_execute_aider_interactive_success_with_editable_files_json(self, mock_aider_bridge):
        """Verify execute_aider_interactive calls bridge correctly with editable_files JSON string."""
        # Arrange
        input_params = {
            "prompt": "Start interactive refactor.", # Use 'prompt' key
            "editable_files": json.dumps(["app.py", "tests/test_app.py"]) # Use editable_files as JSON
        }
        mock_response_dict = _create_task_result_dict(content="Interactive session started diff...")
        mock_aider_bridge.call_aider_tool.return_value = mock_response_dict

        expected_mcp_params = {
            "ai_coding_prompt": "Start interactive refactor.",
            "relative_editable_files": ["app.py", "tests/test_app.py"], # CHANGED KEY
            "relative_readonly_files": [],
            "model": None
        }
        # Act
        result = await AiderExecutorFunctions.execute_aider_interactive(input_params, mock_aider_bridge)
        # Assert
        mock_aider_bridge.call_aider_tool.assert_awaited_once_with(tool_name="aider_ai_code", params=expected_mcp_params)
        assert result == mock_response_dict

    @pytest.mark.asyncio
    @patch('src.executors.aider_executors.logger.warning')
    async def test_execute_aider_interactive_fallback_to_file_context(self, mock_logger_warning, mock_aider_bridge):
        """Verify interactive fallback to file_context and warning log."""
        # Arrange
        input_params = {
            "query": "Interactive task",
            "file_context": ["interactive_fallback.js"] # Use deprecated file_context
        }
        mock_response_dict = _create_task_result_dict(content="Interactive fallback diff...")
        mock_aider_bridge.call_aider_tool.return_value = mock_response_dict

        expected_mcp_params = {
            "ai_coding_prompt": "Interactive task",
            "relative_editable_files": ["interactive_fallback.js"], # CHANGED KEY
            "relative_readonly_files": [],
            "model": None
        }
        # Act
        result = await AiderExecutorFunctions.execute_aider_interactive(input_params, mock_aider_bridge)
        # Assert
        mock_aider_bridge.call_aider_tool.assert_awaited_once_with(tool_name="aider_ai_code", params=expected_mcp_params)
        assert result == mock_response_dict
        mock_logger_warning.assert_called_once()
        assert "deprecated 'file_context' key" in mock_logger_warning.call_args[0][0]
        assert "execute_aider_interactive" in mock_logger_warning.call_args[0][0]


    @pytest.mark.asyncio
    @patch('src.executors.aider_executors.logger.warning')
    async def test_execute_aider_interactive_editable_files_takes_precedence(self, mock_logger_warning, mock_aider_bridge):
        """Verify interactive uses editable_files if both are present."""
        # Arrange
        input_params = {
            "query": "Interactive task",
            "editable_files": ["interactive_actual.ts"],
            "file_context": ["interactive_ignored.js"] # This should be ignored
        }
        mock_response_dict = _create_task_result_dict(content="Interactive precedence diff...")
        mock_aider_bridge.call_aider_tool.return_value = mock_response_dict

        expected_mcp_params = {
            "ai_coding_prompt": "Interactive task",
            "relative_editable_files": ["interactive_actual.ts"], # CHANGED KEY # actual should be used
            "relative_readonly_files": [],
            "model": None
        }
        # Act
        result = await AiderExecutorFunctions.execute_aider_interactive(input_params, mock_aider_bridge)
        # Assert
        mock_aider_bridge.call_aider_tool.assert_awaited_once_with(tool_name="aider_ai_code", params=expected_mcp_params)
        assert result == mock_response_dict
        mock_logger_warning.assert_not_called() # Fallback not used

    @pytest.mark.asyncio
    async def test_execute_aider_interactive_missing_query(self, mock_aider_bridge):
        """Verify execute_aider_interactive returns FAILED on missing query/prompt."""
        # Arrange
        input_params = {} # Missing query/prompt
        # mock_aider_bridge.call_aider_tool doesn't need specific config here

        # Act
        result = await AiderExecutorFunctions.execute_aider_interactive(input_params, mock_aider_bridge)

        # Assert
        mock_aider_bridge.call_aider_tool.assert_not_awaited()
        assert result.get("status") == "FAILED"
        assert "Missing required parameter: 'query' or 'prompt'" in result.get("content", "")
        error_note = result.get("notes", {}).get("error")
        assert error_note is not None
        assert isinstance(error_note, dict)
        assert error_note.get("reason") == "input_validation_failure"
