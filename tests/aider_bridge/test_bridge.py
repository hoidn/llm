# tests/aider_bridge/test_bridge.py
import pytest
import json
import os
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Optional, Dict, Any, Set # Added Set

# Import the class to test
try:
    from src.aider_bridge.bridge import AiderBridge
except ImportError:
    AiderBridge = None # type: ignore

# Import system models used in results/mocks
from src.system.models import TaskResult, AssociativeMatchResult, MatchTuple, TaskFailureError, TaskFailureReason, ContextGenerationInput

# Import exceptions potentially raised by mcp.py
try:
    # Assuming mcp.py might raise these - adjust if library uses different ones
    from mcp.exceptions import MCPError, ConnectionClosed, TimeoutError, ConnectionRefusedError
    from mcp.client.session import ClientSession as RealClientSession
    from mcp.client.stdio import stdio_client as real_stdio_client
    # Use TextContent from common if available, otherwise mock it
    from mcp.types import TextContent as RealTextContent # Corrected import path
except ImportError:
    MCPError = ConnectionClosed = TimeoutError = ConnectionRefusedError = Exception # Fallback
    RealClientSession = object # Fallback type
    real_stdio_client = object
    RealTextContent = object

# Import MemorySystem and FileAccessManager for specing mocks
try:
    from src.memory.memory_system import MemorySystem
except ImportError:
    MemorySystem = object # Fallback type
try:
    from src.handler.file_access import FileAccessManager
except ImportError:
    FileAccessManager = object # Fallback type

# Mock mcp.py TextContent if needed for responses
class MockTextContent:
    def __init__(self, text: str):
        self.text = text

# --- Fixtures ---

@pytest.fixture
def mock_memory_system_bridge(): # Renamed fixture
    """Provides a MagicMock for MemorySystem for bridge tests."""
    # Use spec=MemorySystem if MemorySystem is importable and stable
    return MagicMock(spec=MemorySystem)

@pytest.fixture
def mock_file_access_manager_bridge(): # Renamed fixture
    """Provides a MagicMock for FileAccessManager for bridge tests."""
    # Use spec=FileAccessManager if importable and stable
    mock_fam = MagicMock(spec=FileAccessManager)
    # Configure mock methods used by context helpers
    mock_fam._is_path_safe = MagicMock(return_value=True) # Assume safe by default
    mock_fam._resolve_path = MagicMock(side_effect=lambda p: os.path.abspath(f"/test_base/{p}")) # Simple mock resolve
    # Mock os.path.isfile behavior needed by set_file_context
    # Patching os.path directly is often cleaner in the test itself
    return mock_fam

@pytest.fixture
def default_mcp_config_bridge(): # Renamed fixture
    """Provides a default configuration dictionary for the AiderBridge (MCP STDIO)."""
    return {
        "mcp_transport": "stdio", # Assuming stdio based on aider_MCP_server.md
        "mcp_stdio_command": "dummy_aider_mcp_server_command",
        "mcp_stdio_args": ["--port", "1234"],
        "mcp_stdio_env": {"TEST_VAR": "test_value"}
    }

@pytest.fixture
def aider_bridge_instance(mock_memory_system_bridge, mock_file_access_manager_bridge, default_mcp_config_bridge):
    """Provides an instance of AiderBridge with mocked dependencies."""
    if not AiderBridge:
        pytest.skip("AiderBridge class not available for testing.")
    # No need to patch stdio_client here, patch it in the actual test methods where call_aider_tool is tested
    bridge = AiderBridge(
        memory_system=mock_memory_system_bridge,
        file_access_manager=mock_file_access_manager_bridge,
        config=default_mcp_config_bridge
    )
    return bridge


# Use fixtures defined above
pytestmark = pytest.mark.skipif(AiderBridge is None, reason="AiderBridge class not found")

# --- Test Class ---
class TestAiderBridge:

    # Test __init__ implicitly via aider_bridge_instance fixture setup

    # --- call_aider_tool Tests ---

    @pytest.mark.asyncio
    # Patch the specific transport client used *within* call_aider_tool
    # Patch where it's looked up: 'src.aider_bridge.bridge.stdio_client'
    @patch('src.aider_bridge.bridge.stdio_client', spec=real_stdio_client)
    # Patch where it's looked up: 'src.aider_bridge.bridge.ClientSession'
    @patch('src.aider_bridge.bridge.ClientSession', spec=RealClientSession)
    async def test_call_aider_tool_ai_code_success(self, MockClientSession, mock_stdio_client, aider_bridge_instance):
        """Verify call_aider_tool invokes aider_ai_code and maps success response."""
        # Arrange
        tool_name = "aider_ai_code"
        params = {"ai_coding_prompt": "Implement fibonacci", "relative_editable_files": ["math.py"]}
        mock_diff = "--- a/math.py\n+++ b/math.py\n@@ ..."
        server_response_json = json.dumps({"success": True, "diff": mock_diff})
        # Use the local mock or real TextContent if import works
        mock_server_response = [MockTextContent(server_response_json)]

        # --- CORRECTED MOCK CONFIGURATION ---
        # Mock the instance returned by ClientSession()
        mock_session_instance = AsyncMock(spec=RealClientSession)
        mock_session_instance.call_tool.return_value = mock_server_response
        # Configure the CLASS mock's return_value for the async context manager
        MockClientSession.return_value = mock_session_instance
        # Explicitly configure the async context manager methods on the INSTANCE mock
        mock_session_instance.__aenter__.return_value = mock_session_instance # Often returns self
        mock_session_instance.__aexit__.return_value = None # Return value for __aexit__ usually None
        # --- END CORRECTION ---

        # Configure mock stdio_client context manager (remains the same)
        mock_stdio_client.return_value.__aenter__.return_value = (MagicMock(), MagicMock()) # Dummy read/write streams

        # Act
        result = await aider_bridge_instance.call_aider_tool(tool_name, params)

        # Assert
        mock_stdio_client.assert_called_once() # Check transport was used
        # Check transport args if config stores them directly
        # Example: Check command passed to StdioServerParameters if bridge creates it inside
        # server_params_arg = mock_stdio_client.call_args[0][0]
        # assert server_params_arg.command == "dummy_aider_mcp_server_command"
        MockClientSession.assert_called_once() # Check class was called
        mock_session_instance.initialize.assert_awaited_once() # Check init called
        mock_session_instance.call_tool.assert_awaited_once_with(name=tool_name, arguments=params) # Check tool call
        mock_session_instance.__aenter__.assert_awaited_once() # Check context manager entry
        mock_session_instance.__aexit__.assert_awaited_once() # Check context manager exit
        assert isinstance(result, dict)
        assert result.get("status") == "COMPLETE"
        assert result.get("content") == mock_diff
        assert result.get("notes", {}).get("success") is True # Check specific note
        assert "error" not in result.get("notes", {})

    @pytest.mark.asyncio
    @patch('src.aider_bridge.bridge.stdio_client', spec=real_stdio_client)
    @patch('src.aider_bridge.bridge.ClientSession', spec=RealClientSession)
    async def test_call_aider_tool_ai_code_failure(self, MockClientSession, mock_stdio_client, aider_bridge_instance):
        """Verify call_aider_tool handles application error from aider_ai_code."""
        # Arrange
        tool_name = "aider_ai_code"
        params = {"ai_coding_prompt": "Bad prompt", "relative_editable_files": ["file.py"]}
        error_msg = "Aider execution failed due to invalid syntax"
        # Simulate server response indicating application error
        server_response_json = json.dumps({"success": False, "error": error_msg, "diff": "partial diff..."})
        mock_server_response = [MockTextContent(server_response_json)]

        # --- CORRECTED MOCK CONFIGURATION ---
        mock_session_instance = AsyncMock(spec=RealClientSession)
        mock_session_instance.call_tool.return_value = mock_server_response
        MockClientSession.return_value = mock_session_instance
        mock_session_instance.__aenter__.return_value = mock_session_instance
        mock_session_instance.__aexit__.return_value = None
        # --- END CORRECTION ---
        mock_stdio_client.return_value.__aenter__.return_value = (MagicMock(), MagicMock())

        # Act
        result = await aider_bridge_instance.call_aider_tool(tool_name, params)

        # Assert
        mock_session_instance.call_tool.assert_awaited_once_with(name=tool_name, arguments=params)
        assert isinstance(result, dict)
        assert result.get("status") == "FAILED"
        assert error_msg in result.get("content", "") # Error message should be in content
        assert result.get("notes", {}).get("success") is False # Include success flag if present
        error_note = result.get("notes", {}).get("error")
        assert error_note is not None
        assert isinstance(error_note, dict) # Check error structure
        assert error_note.get("reason") == "tool_execution_error" # Default reason for server app error
        assert error_msg in error_note.get("message", "")
        # Check if extra info from server response is preserved (optional)
        assert result.get("notes", {}).get("diff") == "partial diff..."

    @pytest.mark.asyncio
    @patch('src.aider_bridge.bridge.stdio_client', spec=real_stdio_client)
    @patch('src.aider_bridge.bridge.ClientSession', spec=RealClientSession)
    async def test_call_aider_tool_list_models_success(self, MockClientSession, mock_stdio_client, aider_bridge_instance):
        """Verify call_aider_tool invokes list_models and maps success response."""
        # Arrange
        tool_name = "list_models"
        params = {"substring": "gpt"}
        model_list = ["openai/gpt-4o", "openai/gpt-3.5-turbo"]
        server_response_json = json.dumps({"models": model_list})
        mock_server_response = [MockTextContent(server_response_json)]

        # --- CORRECTED MOCK CONFIGURATION ---
        mock_session_instance = AsyncMock(spec=RealClientSession)
        mock_session_instance.call_tool.return_value = mock_server_response
        MockClientSession.return_value = mock_session_instance
        mock_session_instance.__aenter__.return_value = mock_session_instance
        mock_session_instance.__aexit__.return_value = None
        # --- END CORRECTION ---
        mock_stdio_client.return_value.__aenter__.return_value = (MagicMock(), MagicMock())

        # Act
        result = await aider_bridge_instance.call_aider_tool(tool_name, params)

        # Assert
        mock_session_instance.call_tool.assert_awaited_once_with(name=tool_name, arguments=params)
        assert isinstance(result, dict)
        assert result.get("status") == "COMPLETE"
        # Content should be the JSON string representation of the model list
        assert result.get("content") == json.dumps(model_list)
        # Check if the list is also added to notes for easier access
        assert result.get("notes", {}).get("models") == model_list

    @pytest.mark.asyncio
    @patch('src.aider_bridge.bridge.stdio_client', spec=real_stdio_client)
    @patch('src.aider_bridge.bridge.ClientSession', spec=RealClientSession)
    async def test_call_aider_tool_mcp_exception(self, MockClientSession, mock_stdio_client, aider_bridge_instance):
        """Verify call_aider_tool handles exceptions from mcp.py client."""
        # Arrange
        tool_name = "aider_ai_code"
        params = {"ai_coding_prompt": "Test", "relative_editable_files": ["f.py"]}
        mcp_exception = TimeoutError("MCP call timed out") # Use specific or generic Exception

        # --- CORRECTED MOCK CONFIGURATION ---
        mock_session_instance = AsyncMock(spec=RealClientSession)
        # Configure side_effect on the instance's method
        mock_session_instance.call_tool.side_effect = mcp_exception
        MockClientSession.return_value = mock_session_instance
        mock_session_instance.__aenter__.return_value = mock_session_instance
        mock_session_instance.__aexit__.return_value = None
        # --- END CORRECTION ---
        mock_stdio_client.return_value.__aenter__.return_value = (MagicMock(), MagicMock())

        # Act
        result = await aider_bridge_instance.call_aider_tool(tool_name, params)

        # Assert
        mock_session_instance.call_tool.assert_awaited_once_with(name=tool_name, arguments=params)
        assert isinstance(result, dict)
        assert result.get("status") == "FAILED"
        # Fix: Check reason is connection_error for MCP issues
        assert "MCP communication error: MCP call timed out" in result.get("content", "")
        error_note = result.get("notes", {}).get("error")
        assert error_note is not None
        assert isinstance(error_note, dict)
        assert error_note.get("reason") == "connection_error" # Map communication errors to connection_error
        assert "MCP communication error: MCP call timed out" in error_note.get("message", "")

    @pytest.mark.asyncio
    @patch('src.aider_bridge.bridge.stdio_client', spec=real_stdio_client)
    @patch('src.aider_bridge.bridge.ClientSession', spec=RealClientSession)
    async def test_call_aider_tool_json_parse_error(self, MockClientSession, mock_stdio_client, aider_bridge_instance):
        """Verify call_aider_tool handles invalid JSON from server."""
        # Arrange
        tool_name = "aider_ai_code"
        params = {"ai_coding_prompt": "Test", "relative_editable_files": ["f.py"]}
        invalid_json = "This is not JSON {"
        mock_server_response = [MockTextContent(invalid_json)] # Server sends bad JSON string

        # --- CORRECTED MOCK CONFIGURATION ---
        mock_session_instance = AsyncMock(spec=RealClientSession)
        mock_session_instance.call_tool.return_value = mock_server_response
        MockClientSession.return_value = mock_session_instance
        mock_session_instance.__aenter__.return_value = mock_session_instance
        mock_session_instance.__aexit__.return_value = None
        # --- END CORRECTION ---
        mock_stdio_client.return_value.__aenter__.return_value = (MagicMock(), MagicMock())

        # Act
        result = await aider_bridge_instance.call_aider_tool(tool_name, params)

        # Assert
        mock_session_instance.call_tool.assert_awaited_once_with(name=tool_name, arguments=params)
        assert isinstance(result, dict)
        assert result.get("status") == "FAILED"
        assert "Failed to parse JSON response" in result.get("content", "")
        error_note = result.get("notes", {}).get("error")
        assert error_note is not None
        assert isinstance(error_note, dict)
        # Assign appropriate reason for parsing failure
        assert error_note.get("reason") == "output_format_failure"
        assert "Failed to parse JSON response" in error_note.get("message", "")

    # --- Context Helper Method Tests ---

    # Patch os.path.isfile where AiderBridge.set_file_context looks it up
    # This assumes AiderBridge imports 'os' and calls os.path.isfile
    @patch('src.aider_bridge.bridge.os.path.isfile')
    def test_set_file_context_valid_files(self, mock_os_isfile, aider_bridge_instance, mock_file_access_manager_bridge):
        """Verify set_file_context updates internal state with valid files."""
        # Arrange
        # Mock isfile to always return True for this test
        mock_os_isfile.return_value = True
        # FAM mocks configured in fixture

        file_paths = ["file1.py", "subdir/file2.txt"]
        # Use the mock FAM's path resolution logic
        abs_paths = {mock_file_access_manager_bridge._resolve_path(p) for p in file_paths}

        # Act
        status_result = aider_bridge_instance.set_file_context(file_paths, source="test_source")

        # Assert
        assert status_result.get("status") == "success"
        assert status_result.get("file_count") == len(file_paths) # Assert should now pass
        assert status_result.get("context_source") == "test_source"
        # Check internal state (accessing protected member for testing)
        assert aider_bridge_instance._file_context == abs_paths
        assert aider_bridge_instance._context_source == "test_source"
        # Verify FAM methods were used for validation
        assert mock_file_access_manager_bridge._resolve_path.call_count == len(file_paths)
        assert mock_file_access_manager_bridge._is_path_safe.call_count == len(file_paths)
        # Assert os.path.isfile was called via the bridge's logic
        # Check the paths passed to the mock
        assert mock_os_isfile.call_count == len(file_paths)
        for p in abs_paths:
            mock_os_isfile.assert_any_call(p) # Check it was called with the resolved absolute path

    @patch('src.aider_bridge.bridge.os.path.isfile') # Correct patch target
    def test_set_file_context_filters_nonexistent_files(self, mock_os_isfile, aider_bridge_instance, mock_file_access_manager_bridge):
        """Verify set_file_context filters out non-existent files based on FAM."""
        # Arrange
        # Simulate only file1.py existing at OS level
        # The side_effect needs to check the path passed to *it*
        abs_path_file1 = os.path.abspath("/test_base/file1.py")
        abs_path_nonexistent = os.path.abspath("/test_base/nonexistent.txt")

        def isfile_side_effect(path_arg):
            # Make the check explicit against expected absolute paths
            return path_arg == abs_path_file1
        mock_os_isfile.side_effect = isfile_side_effect
        # FAM mocks configured in fixture

        file_paths = ["file1.py", "nonexistent.txt"]
        expected_paths = {abs_path_file1} # Use path from mock FAM

        # Act
        status_result = aider_bridge_instance.set_file_context(file_paths)

        # Assert
        assert status_result.get("status") == "success" # Still success, just fewer files added
        assert status_result.get("file_count") == 1 # Assert should now pass
        assert aider_bridge_instance._file_context == expected_paths
        assert mock_file_access_manager_bridge._resolve_path.call_count == len(file_paths)
        assert mock_file_access_manager_bridge._is_path_safe.call_count == len(file_paths)
        # Check calls to the mock with specific absolute paths
        mock_os_isfile.assert_any_call(abs_path_file1)
        mock_os_isfile.assert_any_call(abs_path_nonexistent)
        assert mock_os_isfile.call_count == len(file_paths)

    def test_get_file_context(self, aider_bridge_instance):
        """Verify get_file_context returns the current internal state."""
        # Arrange
        abs_path = os.path.abspath("/test_base/file1.py")
        aider_bridge_instance._file_context = {abs_path}
        aider_bridge_instance._context_source = "explicit"

        # Act
        context_info = aider_bridge_instance.get_file_context()

        # Assert
        # Result should be a list, sorted for consistent testing
        assert sorted(context_info.get("file_paths", [])) == [abs_path]
        assert context_info.get("file_count") == 1
        assert context_info.get("context_source") == "explicit"

    # Also apply the corrected patch target here
    # And ensure the mock is configured correctly for the paths returned by memory system mock
    @patch('src.aider_bridge.bridge.os.path.isfile')
    def test_get_context_for_query_success(self, mock_os_isfile, aider_bridge_instance, mock_memory_system_bridge, mock_file_access_manager_bridge):
        """Verify get_context_for_query calls memory_system and updates state."""
        # Arrange
        # FAM mocks configured in fixture
        query = "find function foo"
        # Use paths consistent with mock FAM resolution
        mock_paths = [os.path.abspath("/test_base/foo.py"), os.path.abspath("/test_base/bar.py")]
        mock_matches = [MatchTuple(path=p, relevance=0.9) for p in mock_paths]
        mock_memory_result = AssociativeMatchResult(context_summary="Found foo", matches=mock_matches)
        mock_memory_system_bridge.get_relevant_context_for.return_value = mock_memory_result

        # Configure os.path.isfile mock to return True for the paths memory system returns
        mock_os_isfile.side_effect = lambda p: p in mock_paths

        # Act
        result_paths = aider_bridge_instance.get_context_for_query(query)

        # Assert
        mock_memory_system_bridge.get_relevant_context_for.assert_called_once()
        # Check the input argument passed to the mock
        call_args, call_kwargs = mock_memory_system_bridge.get_relevant_context_for.call_args
        assert len(call_args) == 1
        input_arg = call_args[0]
        # Check if it's the right type and has the query
        assert isinstance(input_arg, ContextGenerationInput)
        assert input_arg.query == query

        assert set(result_paths) == set(mock_paths) # Check returned paths - Should now pass
        assert aider_bridge_instance._file_context == set(mock_paths) # Check internal state update
        assert aider_bridge_instance._context_source == "associative_matching"
        # Verify os.path.isfile was called during the internal set_file_context call
        assert mock_os_isfile.call_count == len(mock_paths)
        for p in mock_paths:
            mock_os_isfile.assert_any_call(p)

    def test_get_context_for_query_failure(self, aider_bridge_instance, mock_memory_system_bridge):
        """Verify get_context_for_query handles memory system errors."""
        # Arrange
        query = "find function foo"
        # Simulate memory system returning error
        mock_memory_result = AssociativeMatchResult(context_summary="Error", matches=[], error="Lookup failed")
        mock_memory_system_bridge.get_relevant_context_for.return_value = mock_memory_result
        initial_context = aider_bridge_instance._file_context.copy() # Store initial state

        # Act
        result_paths = aider_bridge_instance.get_context_for_query(query)

        # Assert
        mock_memory_system_bridge.get_relevant_context_for.assert_called_once()
        assert result_paths == [] # Should return empty list on error
        assert aider_bridge_instance._file_context == initial_context # Internal state should not change
