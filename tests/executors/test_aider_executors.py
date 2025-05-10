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

    @pytest.mark.asyncio # Mark test as async
    async def test_execute_aider_automatic_success(self, mock_aider_bridge): # Make test async
        """Verify execute_aider_automatic calls bridge correctly on success."""
        # Arrange
        input_params = {
            "prompt": "Refactor this code.",
            "file_context": json.dumps(["file1.py", "util/helper.py"])
        }
        # Simulate bridge returning a successful TaskResult dict
        mock_response_dict = _create_task_result_dict(content="Refactoring diff...", notes={"success": True})
        # Configure the awaitable mock method
        mock_aider_bridge.call_aider_tool.return_value = mock_response_dict

        # Expected parameters for the MCP server's tool
        expected_mcp_params = {
            "ai_coding_prompt": "Refactor this code.",
            "editable_files": ["file1.py", "util/helper.py"], # Expect parsed list
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
    async def test_execute_aider_automatic_success_no_context(self, mock_aider_bridge):
        """Verify execute_aider_automatic works without file_context."""
        # Arrange
        input_params = {"prompt": "Explain this."}
        mock_response_dict = _create_task_result_dict(content="Explanation...")
        mock_aider_bridge.call_aider_tool.return_value = mock_response_dict
        expected_mcp_params = {
            "ai_coding_prompt": "Explain this.",
            "editable_files": [], # Expect empty list if no context
            "relative_readonly_files": [], # Changed from None to empty list
            "model": None
        }
        # Act
        result = await AiderExecutorFunctions.execute_aider_automatic(input_params, mock_aider_bridge)
        # Assert
        mock_aider_bridge.call_aider_tool.assert_awaited_once_with(tool_name="aider_ai_code", params=expected_mcp_params)
        assert result == mock_response_dict

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
        input_params = {"file_context": "[]"} # Missing prompt
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
    async def test_execute_aider_automatic_invalid_file_context(self, mock_aider_bridge):
        """Verify execute_aider_automatic returns FAILED on invalid file_context JSON."""
        # Arrange
        input_params = {"prompt": "Test", "file_context": "not a valid json string"}
        # mock_aider_bridge.call_aider_tool doesn't need specific config here

        # Act
        result = await AiderExecutorFunctions.execute_aider_automatic(input_params, mock_aider_bridge)

        # Assert
        mock_aider_bridge.call_aider_tool.assert_not_awaited()
        assert result.get("status") == "FAILED"
        assert "Failed to parse 'file_context'" in result.get("content", "")
        error_note = result.get("notes", {}).get("error")
        assert error_note is not None
        assert isinstance(error_note, dict)
        assert error_note.get("reason") == "input_validation_failure"

    # --- Tests for execute_aider_interactive ---
    # Note: These assume interactive mode maps to 'aider_ai_code' for now.
    # Adjust tool_name and expected_mcp_params if a different server tool is used.

    @pytest.mark.asyncio
    async def test_execute_aider_interactive_success(self, mock_aider_bridge):
        """Verify execute_aider_interactive calls bridge correctly."""
        # Arrange
        input_params = {
            "query": "Start interactive refactor.", # Use 'query' key
            "file_context": json.dumps(["main.py"])
        }
        mock_response_dict = _create_task_result_dict(content="Interactive session started diff...")
        mock_aider_bridge.call_aider_tool.return_value = mock_response_dict

        # Assuming interactive maps to aider_ai_code for now
        expected_mcp_params = {
            "ai_coding_prompt": "Start interactive refactor.",
            "editable_files": ["main.py"],
            "relative_readonly_files": [], # Changed from None to empty list
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
