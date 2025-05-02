# tests/aider_bridge/test_bridge.py
import pytest
import json
import asyncio # Add asyncio
import os
from unittest.mock import patch, MagicMock, AsyncMock # Keep AsyncMock
from typing import Optional, Dict, Any, Set

# Import the class to test
try:
    from src.aider_bridge.bridge import AiderBridge
except ImportError:
    AiderBridge = None # type: ignore

# Import system models used in results/mocks
from src.system.models import TaskResult, AssociativeMatchResult, MatchTuple, TaskFailureError, TaskFailureReason, ContextGenerationInput

# --- Import or Define REAL/DUMMY mcp.py types ---
# If mcp.py IS installed, these imports should work directly.
# If NOT, define simple dummy classes for the patch 'spec'.
try:
    from mcp.client.stdio import stdio_client as real_stdio_client, StdioServerParameters as RealStdioServerParameters
    from mcp.client.session import ClientSession as RealClientSession
    from mcp.types import TextContent as RealTextContent
    from mcp.exceptions import MCPError, ConnectionClosed, TimeoutError, ConnectionRefusedError
    MCP_INSTALLED = True
except ImportError:
    MCP_INSTALLED = False
    # Define dummy classes just for type hinting/spec in patches if needed
    class DummyStdioClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return (AsyncMock(), AsyncMock()) # Return mocks for streams
        async def __aexit__(self, *args): pass
    class DummyStdioParams:
        def __init__(self, *args, **kwargs): pass
    class DummyClientSession:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def initialize(self): pass
        async def call_tool(self, *args, **kwargs): return []
    class DummyTextContent:
        def __init__(self, text=""): self.text = text
    real_stdio_client = DummyStdioClient # type: ignore
    RealStdioServerParameters = DummyStdioParams # type: ignore
    RealClientSession = DummyClientSession # type: ignore
    RealTextContent = DummyTextContent # type: ignore
    # Define dummy exceptions if needed
    MCPError = ConnectionClosed = ConnectionRefusedError = Exception
    # TimeoutError might come from asyncio or mcp.exceptions
    try:
        from asyncio import TimeoutError # Fallback to asyncio version
    except ImportError:
        TimeoutError = Exception # Further fallback
# --- End REAL/DUMMY types ---

# Use the real or dummy TextContent for mocking the response
MockTextContent = RealTextContent

# Import MemorySystem and FileAccessManager for specing mocks
try:
    from src.memory.memory_system import MemorySystem
except ImportError:
    MemorySystem = object # Fallback type
try:
    from src.handler.file_access import FileAccessManager
except ImportError:
    FileAccessManager = object # Fallback type


# --- Fixtures ---

@pytest.fixture
def mock_memory_system_bridge(): # Renamed fixture
    """Provides a MagicMock for MemorySystem for bridge tests."""
    # Use spec=MemorySystem if MemorySystem is importable and stable
    return MagicMock(spec=MemorySystem)

@pytest.fixture # Ensure decorator is present
def mock_file_access_manager_bridge(): # Ensure name matches exactly
    """Provides a MagicMock for FileAccessManager for bridge tests."""
    mock_fam = MagicMock(spec=FileAccessManager)
    mock_fam.base_path = "/test_base" # Define base_path for tests
    # Mock _resolve_path to simulate its behavior based on base_path
    mock_fam._resolve_path.side_effect = lambda p: os.path.abspath(os.path.join(mock_fam.base_path, p)) if p else os.path.abspath(mock_fam.base_path) # Handle empty path case
    # Mock _is_path_safe to assume paths resolved are safe unless test overrides
    mock_fam._is_path_safe.return_value = True
    return mock_fam

@pytest.fixture
def aider_bridge_instance(mock_memory_system_bridge, mock_file_access_manager_bridge): # Check spelling here
    """Provides an instance of AiderBridge with mocked dependencies."""
    if not AiderBridge:
        pytest.skip("AiderBridge class not available for testing.")
    # Provide minimal config for MCP STDIO
    config = {
        "mcp_stdio_command": "dummy_aider_mcp_server",
        "mcp_stdio_args": [],
        "mcp_stdio_env": {}
    }
    # Pass mocks to the constructor
    return AiderBridge(
        memory_system=mock_memory_system_bridge,
        file_access_manager=mock_file_access_manager_bridge, # Pass the correct fixture
        config=config
    )


# Use fixtures defined above
pytestmark = pytest.mark.skipif(AiderBridge is None, reason="AiderBridge class not found")

# --- Test Class ---
class TestAiderBridge:

    # Test __init__ implicitly via aider_bridge_instance fixture setup

    # --- call_aider_tool Tests ---

    @pytest.mark.asyncio
    @patch('src.aider_bridge.bridge.MCP_AVAILABLE', True)           # Decorator 4 (Outermost)
    @patch('src.aider_bridge.bridge.StdioServerParameters', spec=RealStdioServerParameters) # Decorator 3
    @patch('src.aider_bridge.bridge.stdio_client', spec=real_stdio_client) # Decorator 2
    @patch('src.aider_bridge.bridge.ClientSession', spec=RealClientSession) # Decorator 1 (Innermost)
    async def test_call_aider_tool_ai_code_success(self,
                                                 mock_client_session_cls,  # From Decorator 1 (Innermost)
                                                 mock_stdio_client_func,   # From Decorator 2
                                                 mock_stdio_params_cls,    # From Decorator 3
                                                 # REMOVED mock_mcp_flag parameter
                                                 aider_bridge_instance):   # Fixture
        """Verify call_aider_tool invokes aider_ai_code and maps success response."""
        # Arrange
        tool_name = "aider_ai_code"
        params = {"ai_coding_prompt": "Implement fibonacci", "relative_editable_files": ["math.py"]}
        mock_diff = "--- a/math.py\n+++ b/math.py\n@@ ..."
        server_response_json = json.dumps({"success": True, "diff": mock_diff})
        mock_server_response = [MockTextContent(server_response_json)]

        # --- Mock Configuration (Use the CORRECT argument names now) ---
        mock_session_instance = AsyncMock(spec=RealClientSession)
        mock_session_instance.call_tool.return_value = mock_server_response # Configure instance method

        mock_cm_session = AsyncMock() # Context manager for the session
        mock_cm_session.__aenter__.return_value = mock_session_instance # __aenter__ returns the session instance
        # 1. Configure the ClientSession CLASS mock
        mock_client_session_cls.return_value = mock_cm_session # Session CLASS returns the context manager

        mock_stdio_cm = AsyncMock()
        mock_stdio_cm.__aenter__.return_value = (AsyncMock(), AsyncMock()) # Dummy streams
        mock_stdio_client_func.return_value = mock_stdio_cm # stdio_client FUNCTION returns the context manager

        # Act
        result = await aider_bridge_instance.call_aider_tool(tool_name, params)

        # Assert
        mock_stdio_params_cls.assert_called_once_with( # Check StdioServerParameters was called
             command="dummy_aider_mcp_server", args=[], env={}
        )
        mock_stdio_client_func.assert_called_once()
        mock_client_session_cls.assert_called_once()
        mock_session_instance.initialize.assert_awaited_once()
        mock_session_instance.call_tool.assert_awaited_once_with(name=tool_name, arguments=params)

        assert result.get("status") == "COMPLETE"
        assert result.get("content") == mock_diff
        assert result.get("notes", {}).get("success") is True
        # mock_mcp_flag is unused in the test logic

    @pytest.mark.asyncio
    @patch('src.aider_bridge.bridge.MCP_AVAILABLE', True)           # Decorator 4 (Outermost)
    @patch('src.aider_bridge.bridge.StdioServerParameters', spec=RealStdioServerParameters) # Decorator 3
    @patch('src.aider_bridge.bridge.stdio_client', spec=real_stdio_client) # Decorator 2
    @patch('src.aider_bridge.bridge.ClientSession', spec=RealClientSession) # Decorator 1 (Innermost)
    async def test_call_aider_tool_ai_code_failure(self,
                                                 mock_client_session_cls,  # From Decorator 1 (Innermost)
                                                 mock_stdio_client_func,   # From Decorator 2
                                                 mock_stdio_params_cls,    # From Decorator 3
                                                 # REMOVED mock_mcp_flag parameter
                                                 aider_bridge_instance):   # Fixture
        """Verify call_aider_tool handles application error from aider_ai_code."""
        # Arrange
        tool_name = "aider_ai_code"
        params = {"ai_coding_prompt": "Bad prompt", "relative_editable_files": ["file.py"]}
        error_msg = "Aider execution failed due to invalid syntax"
        server_payload = {"success": False, "error": error_msg, "diff": "partial diff..."}
        server_response_json = json.dumps(server_payload)
        mock_server_response = [MockTextContent(server_response_json)]

        # --- Mock Configuration (Use the CORRECT argument names now) ---
        mock_session_instance = AsyncMock(spec=RealClientSession)
        mock_session_instance.call_tool.return_value = mock_server_response # Configure instance method
        mock_cm_session = AsyncMock() # Context manager for the session
        mock_cm_session.__aenter__.return_value = mock_session_instance # __aenter__ returns the session instance
        # 1. Configure the ClientSession CLASS mock
        mock_client_session_cls.return_value = mock_cm_session
        mock_stdio_cm = AsyncMock(); mock_stdio_cm.__aenter__.return_value = (AsyncMock(), AsyncMock())
        mock_stdio_client_func.return_value = mock_stdio_cm

        # Act
        result = await aider_bridge_instance.call_aider_tool(tool_name, params)

        # Assert
        mock_stdio_params_cls.assert_called_once()
        mock_stdio_client_func.assert_called_once()
        mock_client_session_cls.assert_called_once()
        mock_session_instance.initialize.assert_awaited_once()
        mock_session_instance.call_tool.assert_awaited_once_with(name=tool_name, arguments=params)

        assert result.get("status") == "FAILED"
        # Check that the original error message from the server is in the content set by _create_failed_result_dict
        assert error_msg in result.get("content", "")
        assert result.get("notes", {}).get("error", {}).get("reason") == "tool_execution_error"
        # Check that the original error details are included in the notes
        # The details dict passed to _create_failed_result_dict should contain the server payload
        assert result.get("notes", {}).get("error", {}).get("details", {}).get("error") == error_msg
        assert result.get("notes", {}).get("error", {}).get("details", {}).get("diff") == "partial diff..."
        # mock_mcp_flag is unused in the test logic

    @pytest.mark.asyncio
    @patch('src.aider_bridge.bridge.MCP_AVAILABLE', True)           # Decorator 4 (Outermost)
    @patch('src.aider_bridge.bridge.StdioServerParameters', spec=RealStdioServerParameters) # Decorator 3
    @patch('src.aider_bridge.bridge.stdio_client', spec=real_stdio_client) # Decorator 2
    @patch('src.aider_bridge.bridge.ClientSession', spec=RealClientSession) # Decorator 1 (Innermost)
    async def test_call_aider_tool_list_models_success(self,
                                                     mock_client_session_cls,  # From Decorator 1 (Innermost)
                                                     mock_stdio_client_func,   # From Decorator 2
                                                     mock_stdio_params_cls,    # From Decorator 3
                                                     # REMOVED mock_mcp_flag parameter
                                                     aider_bridge_instance):   # Fixture
        """Verify call_aider_tool invokes list_models and maps success response."""
        # Arrange
        tool_name = "list_models"
        params = {"substring": "gpt"}
        model_list = ["openai/gpt-4o", "openai/gpt-3.5-turbo"]
        server_response_json = json.dumps({"models": model_list})
        mock_server_response = [MockTextContent(server_response_json)]

        # --- Mock Configuration (Use the CORRECT argument names now) ---
        mock_session_instance = AsyncMock(spec=RealClientSession)
        mock_session_instance.call_tool.return_value = mock_server_response # Configure instance method
        mock_cm_session = AsyncMock() # Context manager for the session
        mock_cm_session.__aenter__.return_value = mock_session_instance # __aenter__ returns the session instance
        # 1. Configure the ClientSession CLASS mock
        mock_client_session_cls.return_value = mock_cm_session
        mock_stdio_cm = AsyncMock(); mock_stdio_cm.__aenter__.return_value = (AsyncMock(), AsyncMock())
        mock_stdio_client_func.return_value = mock_stdio_cm

        # Act
        result = await aider_bridge_instance.call_aider_tool(tool_name, params)

        # Assert
        mock_stdio_params_cls.assert_called_once()
        mock_stdio_client_func.assert_called_once()
        mock_client_session_cls.assert_called_once()
        mock_session_instance.initialize.assert_awaited_once()
        mock_session_instance.call_tool.assert_awaited_once_with(name=tool_name, arguments=params)

        assert isinstance(result, dict)
        assert result.get("status") == "COMPLETE"
        # Content should be the JSON string of the list
        assert result.get("content") == json.dumps(model_list)
        # Notes should contain the actual list
        assert result.get("notes", {}).get("models") == model_list
        # mock_mcp_flag is unused in the test logic

    @pytest.mark.asyncio
    @patch('src.aider_bridge.bridge.MCP_AVAILABLE', True)           # Decorator 4 (Outermost)
    @patch('src.aider_bridge.bridge.StdioServerParameters', spec=RealStdioServerParameters) # Decorator 3
    @patch('src.aider_bridge.bridge.stdio_client', spec=real_stdio_client) # Decorator 2
    @patch('src.aider_bridge.bridge.ClientSession', spec=RealClientSession) # Decorator 1 (Innermost)
    async def test_call_aider_tool_mcp_exception(self,
                                               mock_client_session_cls,  # From Decorator 1 (Innermost)
                                               mock_stdio_client_func,   # From Decorator 2
                                               mock_stdio_params_cls,    # From Decorator 3
                                               # REMOVED mock_mcp_flag parameter
                                               aider_bridge_instance):   # Fixture
        """Verify call_aider_tool handles exceptions from mcp.py client."""
        # Arrange
        tool_name = "aider_ai_code"
        params = {"ai_coding_prompt": "Test", "relative_editable_files": ["f.py"]}
        mcp_exception = TimeoutError("MCP call timed out") # Use specific or generic Exception

        # --- Mock Configuration (Use the CORRECT argument names now) ---
        mock_session_instance = AsyncMock(spec=RealClientSession)
        mock_session_instance.call_tool.side_effect = mcp_exception # Configure instance method
        mock_cm_session = AsyncMock() # Context manager for the session
        mock_cm_session.__aenter__.return_value = mock_session_instance # __aenter__ returns the session instance
        # 1. Configure the ClientSession CLASS mock
        mock_client_session_cls.return_value = mock_cm_session
        mock_stdio_cm = AsyncMock(); mock_stdio_cm.__aenter__.return_value = (AsyncMock(), AsyncMock())
        mock_stdio_client_func.return_value = mock_stdio_cm

        # Act
        result = await aider_bridge_instance.call_aider_tool(tool_name, params)

        # Assert
        mock_stdio_params_cls.assert_called_once()
        mock_stdio_client_func.assert_called_once()
        mock_client_session_cls.assert_called_once()
        mock_session_instance.initialize.assert_awaited_once()
        mock_session_instance.call_tool.assert_awaited_once_with(name=tool_name, arguments=params)

        assert result.get("status") == "FAILED"
        assert "MCP communication error" in result.get("content", "")
        assert "MCP call timed out" in result.get("content", "") # Check specific error message
        assert result.get("notes", {}).get("error", {}).get("reason") == "connection_error"
        # mock_mcp_flag is unused in the test logic

    @pytest.mark.asyncio
    @patch('src.aider_bridge.bridge.MCP_AVAILABLE', True)           # Decorator 4 (Outermost)
    @patch('src.aider_bridge.bridge.StdioServerParameters', spec=RealStdioServerParameters) # Decorator 3
    @patch('src.aider_bridge.bridge.stdio_client', spec=real_stdio_client) # Decorator 2
    @patch('src.aider_bridge.bridge.ClientSession', spec=RealClientSession) # Decorator 1 (Innermost)
    async def test_call_aider_tool_json_parse_error(self,
                                                  mock_client_session_cls,  # From Decorator 1 (Innermost)
                                                  mock_stdio_client_func,   # From Decorator 2
                                                  mock_stdio_params_cls,    # From Decorator 3
                                                  # REMOVED mock_mcp_flag parameter
                                                  aider_bridge_instance):   # Fixture
        """Verify call_aider_tool handles invalid JSON from server."""
        # Arrange
        tool_name = "aider_ai_code"
        params = {"ai_coding_prompt": "Test", "relative_editable_files": ["f.py"]}
        invalid_json = "This is not JSON {"
        mock_server_response = [MockTextContent(invalid_json)] # Server sends bad JSON string

        # --- Mock Configuration (Use the CORRECT argument names now) ---
        mock_session_instance = AsyncMock(spec=RealClientSession)
        mock_session_instance.call_tool.return_value = mock_server_response # Configure instance method
        mock_cm_session = AsyncMock() # Context manager for the session
        mock_cm_session.__aenter__.return_value = mock_session_instance # __aenter__ returns the session instance
        # 1. Configure the ClientSession CLASS mock
        mock_client_session_cls.return_value = mock_cm_session
        mock_stdio_cm = AsyncMock(); mock_stdio_cm.__aenter__.return_value = (AsyncMock(), AsyncMock())
        mock_stdio_client_func.return_value = mock_stdio_cm

        # Act
        result = await aider_bridge_instance.call_aider_tool(tool_name, params)

        # Assert
        mock_stdio_params_cls.assert_called_once()
        mock_stdio_client_func.assert_called_once()
        mock_client_session_cls.assert_called_once()
        mock_session_instance.initialize.assert_awaited_once()
        mock_session_instance.call_tool.assert_awaited_once_with(name=tool_name, arguments=params)

        assert result.get("status") == "FAILED"
        assert "Failed to parse JSON response" in result.get("content", "")
        assert result.get("notes", {}).get("error", {}).get("reason") == "output_format_failure"
        # Check that raw response is included in details
        assert result.get("notes", {}).get("error", {}).get("details", {}).get("raw_response") == invalid_json
        # mock_mcp_flag is unused in the test logic

    # --- Context Helper Method Tests ---

    # PATCH BOTH isfile and exists
    @patch('src.aider_bridge.bridge.os.path.exists')
    @patch('src.aider_bridge.bridge.os.path.isfile')
    def test_set_file_context_valid_files(self, mock_os_isfile, mock_os_exists, aider_bridge_instance, mock_file_access_manager_bridge):
        """Verify set_file_context updates internal state with valid files."""
        # Arrange
        # Mock isfile AND exists to always return True for this test
        mock_os_isfile.return_value = True
        mock_os_exists.return_value = True
        # FAM mocks configured in fixture

        file_paths = ["file1.py", "subdir/file2.txt"]
        # Use the mock FAM's path resolution logic
        abs_paths = {mock_file_access_manager_bridge._resolve_path(p) for p in file_paths}

        # Act
        status_result = aider_bridge_instance.set_file_context(file_paths, source="test_source")

        # Assert
        assert status_result.get("status") == "success"
        assert status_result.get("file_count") == len(file_paths) # Should pass now
        assert status_result.get("context_source") == "test_source"
        # Check internal state uses absolute paths from mock FAM
        assert aider_bridge_instance._file_context == abs_paths
        assert aider_bridge_instance._context_source == "test_source"
        # Ensure mocks were called correctly
        assert mock_os_exists.call_count == len(file_paths)
        assert mock_os_isfile.call_count == len(file_paths)

    # PATCH BOTH isfile and exists
    @patch('src.aider_bridge.bridge.os.path.exists')
    @patch('src.aider_bridge.bridge.os.path.isfile')
    def test_set_file_context_filters_nonexistent_files(self, mock_os_isfile, mock_os_exists, aider_bridge_instance, mock_file_access_manager_bridge):
        """Verify set_file_context filters out non-existent files based on OS checks."""
        # Arrange
        abs_path_file1 = mock_file_access_manager_bridge._resolve_path("file1.py")
        abs_path_nonexistent = mock_file_access_manager_bridge._resolve_path("nonexistent.txt")

        # Simulate only file1.py existing at OS level for BOTH checks
        def exists_side_effect(path_arg):
            return path_arg == abs_path_file1
        def isfile_side_effect(path_arg):
            return path_arg == abs_path_file1
        mock_os_exists.side_effect = exists_side_effect
        mock_os_isfile.side_effect = isfile_side_effect
        # FAM mocks configured in fixture

        file_paths = ["file1.py", "nonexistent.txt"]
        expected_paths = {abs_path_file1} # Use path from mock FAM

        # Act
        status_result = aider_bridge_instance.set_file_context(file_paths)

        # Assert
        assert status_result.get("status") == "success" # Still success, just fewer files added
        assert status_result.get("file_count") == 1 # Should pass now
        assert status_result.get("context_source") == "explicit_specification"
        assert aider_bridge_instance._file_context == expected_paths
        # Ensure mocks were called correctly
        assert mock_os_exists.call_count == len(file_paths)
        # isfile should only be called if exists returns True
        assert mock_os_isfile.call_count == 1 # Only called for file1.py

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

    # PATCH BOTH isfile and exists
    @patch('src.aider_bridge.bridge.os.path.exists')
    @patch('src.aider_bridge.bridge.os.path.isfile')
    def test_get_context_for_query_success(self, mock_os_isfile, mock_os_exists, aider_bridge_instance, mock_memory_system_bridge, mock_file_access_manager_bridge):
        """Verify get_context_for_query calls memory_system and updates state."""
        # Arrange
        # FAM mocks configured in fixture
        query = "find function foo"
        # Use paths consistent with mock FAM resolution
        mock_paths_abs = [
            mock_file_access_manager_bridge._resolve_path("foo.py"),
            mock_file_access_manager_bridge._resolve_path("bar.py")
        ]
        mock_matches = [MatchTuple(path=p, relevance=0.9) for p in mock_paths_abs]
        mock_memory_result = AssociativeMatchResult(context_summary="Found foo", matches=mock_matches)
        mock_memory_system_bridge.get_relevant_context_for.return_value = mock_memory_result

        # Configure os.path.exists and os.path.isfile mock to return True for the paths memory system returns
        mock_os_exists.side_effect = lambda p: p in mock_paths_abs
        mock_os_isfile.side_effect = lambda p: p in mock_paths_abs

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

        assert set(result_paths) == set(mock_paths_abs) # Check returned paths - Should now pass
        # Check internal state was updated
        assert aider_bridge_instance._file_context == set(mock_paths_abs)
        assert aider_bridge_instance._context_source == "associative_matching"
        # Check os mocks were called by set_file_context
        assert mock_os_exists.call_count == len(mock_paths_abs)
        assert mock_os_isfile.call_count == len(mock_paths_abs) # Called because exists returned True

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

    # --- Tests for MCP_AVAILABLE = False ---
    @pytest.mark.asyncio
    @patch('src.aider_bridge.bridge.MCP_AVAILABLE', False) # Mock MCP as unavailable
    async def test_call_aider_tool_mcp_unavailable(self, mock_mcp_flag, aider_bridge_instance):
        """Verify call_aider_tool returns error if MCP lib is unavailable."""
        # Arrange
        tool_name = "aider_ai_code"
        params = {"ai_coding_prompt": "Test", "relative_editable_files": ["f.py"]}

        # Act
        result = await aider_bridge_instance.call_aider_tool(tool_name, params)

        # Assert
        assert result.get("status") == "FAILED"
        assert "mcp.py library not available" in result.get("content", "")
        assert result.get("notes", {}).get("error", {}).get("reason") == "dependency_error"

    @pytest.mark.asyncio
    @patch('src.aider_bridge.bridge.MCP_AVAILABLE', True) # Assume available for this test
    async def test_call_aider_tool_no_command_config(self, mock_mcp_flag, mock_memory_system_bridge, mock_file_access_manager_bridge):
        """Verify call_aider_tool returns error if MCP command is not configured."""
         # Arrange
        tool_name = "aider_ai_code"
        params = {"ai_coding_prompt": "Test", "relative_editable_files": ["f.py"]}
        # Create bridge with empty config
        bad_config = {}
        bridge = AiderBridge(mock_memory_system_bridge, mock_file_access_manager_bridge, bad_config)

        # Act
        result = await bridge.call_aider_tool(tool_name, params)

        # Assert
        assert result.get("status") == "FAILED"
        assert "Aider MCP server command not configured" in result.get("content", "")
        assert result.get("notes", {}).get("error", {}).get("reason") == "configuration_error"
