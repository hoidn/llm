"""Tests for the AiderBridge interactive session functionality."""
import pytest
from unittest.mock import patch, MagicMock, call
import os
import subprocess
import sys

from aider_bridge.interactive import AiderInteractiveSession
from aider_bridge.tools import register_aider_tools, register_interactive_tool

class TestAiderInteractiveSession:
    """Tests for the AiderInteractiveSession class."""
    
    def test_init(self, mock_memory_system):
        """Test initialization of AiderInteractiveSession."""
        # Create a mock bridge
        bridge = MagicMock()
        bridge.aider_available = True
        
        # Create session
        session = AiderInteractiveSession(bridge)
        
        # Check initial state
        assert session.bridge == bridge
        assert not session.active
        assert session.process is None
        assert session.files_before == set()
        assert session.files_after == set()
        assert session.modified_files == []
        assert session.temp_dir is None
        assert session.last_query is None
        
    def test_start_session(self, mock_memory_system):
        """Test starting an interactive session."""
        # Create a custom mock for format_interactive_result
        expected_result = {
            "status": "COMPLETE",
            "content": "Interactive Aider session completed. Modified 1 files.",
            "notes": {
                "files_modified": ["/path/to/file1.py"],
                "session_summary": "Session initiated with query: Implement a factorial function"
            }
        }
        
        # Create mock objects
        bridge = MagicMock()
        bridge.aider_available = True
        bridge.file_context = {"/path/to/file1.py", "/path/to/file2.py"}
        
        # Use a more targeted patching approach
        with patch('aider_bridge.interactive.AiderInteractiveSession._run_aider_in_process'), \
             patch('tempfile.TemporaryDirectory'), \
             patch.object(AiderInteractiveSession, '_get_file_states') as mock_get_states, \
             patch.object(AiderInteractiveSession, '_get_modified_files', return_value=["/path/to/file1.py"]) as mock_get_modified, \
             patch.object(AiderInteractiveSession, '_cleanup_session'), \
             patch('builtins.__import__', return_value=MagicMock()), \
             patch('aider_bridge.interactive.format_interactive_result', return_value=expected_result) as mock_format_result:
            
            # Set up mocks
            mock_get_states.side_effect = [{"/path/to/file1.py": {"size": 100, "mtime": 123456789, "hash": 12345}},
                                        {"/path/to/file1.py": {"size": 120, "mtime": 123456790, "hash": 67890}}]
            mock_get_modified.return_value = ["/path/to/file1.py"]
            
            # Create session
            session = AiderInteractiveSession(bridge)
            
            # Start session
            result = session.start_session("Implement a factorial function")
            
            # Check result
            assert result == expected_result
            assert result["status"] == "COMPLETE"
            assert "Interactive Aider session completed" in result["content"]
            assert "files_modified" in result["notes"]
            assert result["notes"]["files_modified"] == ["/path/to/file1.py"]
            assert "session_summary" in result["notes"]
            
            # Verify our mock was called with correct arguments
            mock_format_result.assert_called_once()
            args, kwargs = mock_format_result.call_args
            assert kwargs["status"] == "COMPLETE"
            assert "Interactive Aider session completed" in kwargs["content"]
            assert kwargs["files_modified"] == ["/path/to/file1.py"]
            assert "Implement a factorial function" in kwargs["session_summary"]
    
    def test_start_session_minimal_mocking(self, mock_memory_system, tmp_path):
        """Test starting a session with minimal mocking."""
        # Create a real bridge
        from aider_bridge.bridge import AiderBridge
        bridge = AiderBridge(mock_memory_system)
        bridge.aider_available = True
        
        # Create test files
        file1 = tmp_path / "test_file1.py"
        file1.write_text("print('Hello, world!')")
        
        # Set file context
        bridge.file_context = {str(file1)}
        
        # Mock the import check to avoid actual import attempts
        with patch('builtins.__import__', return_value=MagicMock()), \
             patch.object(AiderInteractiveSession, '_run_aider_in_process'), \
             patch.object(AiderInteractiveSession, '_get_file_states') as mock_get_states, \
             patch.object(AiderInteractiveSession, '_get_modified_files', return_value=[str(file1)]), \
             patch.object(AiderInteractiveSession, '_cleanup_session'):
            
            # Set up file states mock
            mock_get_states.side_effect = [
                {str(file1): {"size": 100, "mtime": 123456789, "hash": 12345}},
                {str(file1): {"size": 120, "mtime": 123456790, "hash": 67890}}
            ]
            
            # Create session
            session = AiderInteractiveSession(bridge)
            
            # Start session
            result = session.start_session("Implement a factorial function")
            
            # Check result structure
            assert isinstance(result, dict)
            assert "status" in result
            assert "content" in result
            assert "notes" in result
            
            # Check specific values
            assert result["status"] == "COMPLETE"
            assert "Interactive Aider session completed" in result["content"]
            assert "files_modified" in result["notes"]
            assert "session_summary" in result["notes"]
            assert "Session initiated with query: Implement a factorial function" in result["notes"]["session_summary"]
    
    @pytest.mark.integration
    def test_start_session_integration(self, mock_memory_system, tmp_path):
        """Integration test for starting an interactive session without mocking the formatter."""
        import sys
        
        # Create a real bridge
        from aider_bridge.bridge import AiderBridge
        bridge = AiderBridge(mock_memory_system)
        bridge.aider_available = True
        
        # Create test files
        file1 = tmp_path / "test_file1.py"
        file1.write_text("print('Hello, world!')")
        
        file2 = tmp_path / "test_file2.py"
        file2.write_text("def sample():\n    return 42")
        
        # Set file context
        bridge.file_context = {str(file1), str(file2)}
        
        # Mock the import check to avoid actual import attempts
        with patch('builtins.__import__', return_value=MagicMock()), \
             patch.object(AiderInteractiveSession, '_run_aider_in_process') as mock_run_aider, \
             patch.object(AiderInteractiveSession, '_run_aider_subprocess'), \
             patch.object(AiderInteractiveSession, '_get_file_states') as mock_get_states, \
             patch.object(AiderInteractiveSession, '_get_modified_files', return_value=[str(file1)]) as mock_get_modified, \
             patch.object(AiderInteractiveSession, '_cleanup_session') as mock_cleanup:
            
            # Create session
            session = AiderInteractiveSession(bridge)
            
            # Start session
            sys.stderr.write(f"\nDEBUG - About to call start_session\n")
            result = session.start_session("Implement a factorial function")
            sys.stderr.write(f"\nDEBUG - Result type: {type(result)}\n")
            sys.stderr.write(f"DEBUG - Result content: {result}\n")
            
            # Check result structure
            assert isinstance(result, dict)
            assert "status" in result
            assert "content" in result
            assert "notes" in result
            
            # Check specific values
            assert result["status"] == "COMPLETE"
            assert "Interactive Aider session completed" in result["content"]
            assert "files_modified" in result["notes"]
            assert "session_summary" in result["notes"]
            assert "Session initiated with query: Implement a factorial function" in result["notes"]["session_summary"]
            
            # Check that methods were called
            mock_get_states.assert_called()
            mock_run_aider.assert_called_once()
            mock_get_modified.assert_called_once()
            mock_cleanup.assert_called_once()
    
    def test_start_session_aider_not_available(self, mock_memory_system):
        """Test starting a session when Aider is not available."""
        # Create mock bridge
        bridge = MagicMock()
        bridge.aider_available = False
        
        # Create session
        session = AiderInteractiveSession(bridge)
        
        # Start session
        result = session.start_session("Implement a factorial function")
        
        # Check result
        assert result["status"] == "FAILED"
        assert "Aider is not available" in result["content"]
        assert "error" in result["notes"]
        assert "Aider dependency not installed" in result["notes"]["error"]
    
    def test_start_session_already_active(self, mock_memory_system):
        """Test starting a session when one is already active."""
        # Create mock bridge
        bridge = MagicMock()
        bridge.aider_available = True
        
        # Create session
        session = AiderInteractiveSession(bridge)
        session.active = True
        
        # Start session
        result = session.start_session("Implement a factorial function")
        
        # Check result
        assert result["status"] == "FAILED"
        assert "already active" in result["content"]
        assert "error" in result["notes"]
        assert "Session already active" in result["notes"]["error"]
    
    @patch('aider_bridge.interactive.AiderInteractiveSession._run_aider_in_process', 
           side_effect=Exception("Test error"))
    @patch('aider_bridge.interactive.AiderInteractiveSession._run_aider_subprocess')
    @patch('aider_bridge.result_formatter.format_interactive_result')
    def test_start_session_fallback(self, mock_format_result, mock_run_subprocess, mock_run_in_process, mock_memory_system):
        """Test fallback to subprocess when in-process fails."""
        # Create mock bridge
        bridge = MagicMock()
        bridge.aider_available = True
        bridge.file_context = {"/path/to/file1.py"}
        
        # Set up format_interactive_result mock to return a successful result
        mock_format_result.return_value = {
            "status": "COMPLETE",
            "content": "Interactive Aider session completed.",
            "notes": {}
        }
        
        # Mock methods
        with patch.object(AiderInteractiveSession, '_get_file_states'), \
             patch.object(AiderInteractiveSession, '_get_modified_files'), \
             patch.object(AiderInteractiveSession, '_cleanup_session'):
            
            # Create session
            session = AiderInteractiveSession(bridge)
            
            # Patch the import aider part to avoid ImportError
            with patch('builtins.__import__', return_value=MagicMock()):
                # Start session
                session.start_session("Implement a factorial function")
            
            # Check that fallback was used
            mock_run_in_process.assert_called_once()
            mock_run_subprocess.assert_called_once()
    
    def test_terminate_session_no_active(self, mock_memory_system):
        """Test terminating when no session is active."""
        # Create mock bridge
        bridge = MagicMock()
        
        # Create session
        session = AiderInteractiveSession(bridge)
        session.active = False
        
        # Terminate session
        result = session.terminate_session()
        
        # Check result
        assert result["status"] == "FAILED"
        assert "No active Aider session" in result["content"]
        assert "error" in result["notes"]
        assert "No active session" in result["notes"]["error"]
    
    @patch('subprocess.Popen')
    def test_terminate_session(self, mock_popen, mock_memory_system):
        """Test terminating an active session."""
        # Create mock objects
        bridge = MagicMock()
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process
        
        # Create session
        session = AiderInteractiveSession(bridge)
        session.active = True
        session.process = mock_process
        session.modified_files = ["/path/to/file1.py"]
        
        # Mock cleanup
        with patch.object(AiderInteractiveSession, '_cleanup_session') as mock_cleanup:
            # Terminate session
            result = session.terminate_session()
            
            # Check result
            assert result["status"] == "COMPLETE"
            assert "terminated successfully" in result["content"]
            assert "files_modified" in result["notes"]
            assert result["notes"]["files_modified"] == ["/path/to/file1.py"]
            
            # Check that process was terminated
            mock_process.terminate.assert_called_once()
            mock_cleanup.assert_called_once()
    
    def test_find_aider_executable(self, mock_memory_system):
        """Test finding the Aider executable."""
        # Create mock bridge
        bridge = MagicMock()
        
        # Set up mock subprocess
        with patch('subprocess.check_output') as mock_check_output, \
             patch('os.path.isfile') as mock_isfile, \
             patch('os.access') as mock_access:
            
            # First case: Found via which
            mock_check_output.return_value = "/usr/local/bin/aider\n"
            
            session = AiderInteractiveSession(bridge)
            result = session._find_aider_executable()
            
            assert result == "/usr/local/bin/aider"
            mock_check_output.assert_called_with(["which", "aider"], text=True)
            
            # Reset mock for the second test case
            mock_check_output.reset_mock()
            
            # Second case: which fails, found in common paths
            mock_check_output.side_effect = Exception("Command not found")
            mock_isfile.side_effect = lambda path: path == "/usr/bin/aider"
            mock_access.return_value = True
            
            # Create a new session to avoid state from previous test
            session = AiderInteractiveSession(bridge)
            result = session._find_aider_executable()
            
            assert result == "/usr/bin/aider"
            
            # Third case: Nothing found, fallback to "aider"
            mock_isfile.side_effect = lambda path: False
            
            result = session._find_aider_executable()
            
            assert result == "aider"
    
    def test_get_file_states(self, tmp_path, mock_memory_system):
        """Test getting file states."""
        # Create test files
        file1 = tmp_path / "file1.py"
        file1.write_text("print('Hello, world!')")
        
        file2 = tmp_path / "file2.py"
        file2.write_text("def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)")
        
        # Create mock bridge
        bridge = MagicMock()
        
        # Create session
        session = AiderInteractiveSession(bridge)
        
        # Get file states
        file_paths = [str(file1), str(file2)]
        states = session._get_file_states(file_paths)
        
        # Check result
        assert len(states) == 2
        assert str(file1) in states
        assert str(file2) in states
        
        # Each state should have size, mtime, and hash
        for file_path, state in states.items():
            assert 'size' in state
            assert 'mtime' in state
            assert 'hash' in state
            
        # The sizes should be different
        assert states[str(file1)]['size'] < states[str(file2)]['size']
    
    def test_get_modified_files(self, mock_memory_system):
        """Test getting modified files."""
        # Create mock bridge
        bridge = MagicMock()
        
        # Create session
        session = AiderInteractiveSession(bridge)
        
        # Set up file states
        session.files_before = {
            "/path/to/file1.py": {'size': 100, 'mtime': 123456789, 'hash': 12345},
            "/path/to/file2.py": {'size': 200, 'mtime': 123456790, 'hash': 67890},
            "/path/to/file3.py": {'size': 300, 'mtime': 123456791, 'hash': 24680}
        }
        
        session.files_after = {
            "/path/to/file1.py": {'size': 120, 'mtime': 123456800, 'hash': 13579},  # Modified
            "/path/to/file2.py": {'size': 200, 'mtime': 123456790, 'hash': 67890},  # Unchanged
            "/path/to/file4.py": {'size': 400, 'mtime': 123456792, 'hash': 97531}   # New
        }
        
        # Get modified files
        modified = session._get_modified_files()
        
        # Check result - should include modified, deleted, and new files
        assert "/path/to/file1.py" in modified  # Modified
        assert "/path/to/file3.py" in modified  # Deleted
        assert "/path/to/file4.py" in modified  # New
        assert "/path/to/file2.py" not in modified  # Unchanged
        assert len(modified) == 3

class TestAiderTools:
    """Tests for the Aider tools registration utilities."""
    
    def test_register_interactive_tool(self):
        """Test registering the interactive tool."""
        # Create mock objects
        handler = MagicMock()
        handler.registerDirectTool = MagicMock()
        
        aider_bridge = MagicMock()
        aider_bridge.start_interactive_session = MagicMock()
        
        # Register tool
        result = register_interactive_tool(handler, aider_bridge)
        
        # Check result
        assert result["status"] == "success"
        assert result["name"] == "aiderInteractive"
        assert result["type"] == "direct"
        
        # Check that tool was registered
        handler.registerDirectTool.assert_called_once()
        tool_name, tool_func = handler.registerDirectTool.call_args[0]
        assert tool_name == "aiderInteractive"
        assert callable(tool_func)
    
    def test_register_interactive_tool_handler_error(self):
        """Test registering when handler doesn't support tool registration."""
        # Create mock objects
        handler = MagicMock()
        # Remove registerDirectTool method
        del handler.registerDirectTool
        
        aider_bridge = MagicMock()
        
        # Register tool
        result = register_interactive_tool(handler, aider_bridge)
        
        # Check result
        assert result["status"] == "error"
        assert "does not support" in result["message"]
    
    def test_register_aider_tools(self):
        """Test registering all Aider tools."""
        # Create mock objects
        handler = MagicMock()
        handler.registerDirectTool = MagicMock()
        
        aider_bridge = MagicMock()
        
        # Register tools
        with patch('aider_bridge.tools.register_interactive_tool') as mock_register_interactive:
            mock_register_interactive.return_value = {"status": "success", "name": "aiderInteractive"}
            
            result = register_aider_tools(handler, aider_bridge)
            
            # Check result
            assert "interactive" in result
            assert result["interactive"]["status"] == "success"
            
            # Check that individual register function was called
            mock_register_interactive.assert_called_once_with(handler, aider_bridge)
    
    def test_tool_function(self):
        """Test the tool function created during registration."""
        # Create mock objects
        handler = MagicMock()
        
        aider_bridge = MagicMock()
        aider_bridge.start_interactive_session = MagicMock()
        
        # Register tool
        register_interactive_tool(handler, aider_bridge)
        
        # Get tool function
        tool_func = handler.registerDirectTool.call_args[0][1]
        
        # Call tool function
        tool_func("Implement a factorial function", ["/path/to/file.py"])
        
        # Check that bridge method was called
        aider_bridge.start_interactive_session.assert_called_once_with(
            "Implement a factorial function", 
            ["/path/to/file.py"]
        )

class TestAiderBridgeInteractive:
    """Tests for the interactive session methods in AiderBridge."""
    
    def test_create_interactive_session(self, mock_memory_system):
        """Test creating an interactive session."""
        # Create AiderBridge
        from aider_bridge.bridge import AiderBridge
        bridge = AiderBridge(mock_memory_system)
        
        # Create interactive session
        with patch('aider_bridge.interactive.AiderInteractiveSession') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            session = bridge.create_interactive_session()
            
            # Check result
            assert session == mock_session
            mock_session_class.assert_called_once_with(bridge)
    
    def test_start_interactive_session(self, mock_memory_system):
        """Test starting an interactive session."""
        # Create AiderBridge
        from aider_bridge.bridge import AiderBridge
        bridge = AiderBridge(mock_memory_system)
        
        # Mock session
        mock_session = MagicMock()
        mock_session.start_session.return_value = {"status": "COMPLETE", "content": "Session completed"}
        
        # Start interactive session
        with patch.object(bridge, 'create_interactive_session') as mock_create_session:
            mock_create_session.return_value = mock_session
            
            result = bridge.start_interactive_session("Implement a factorial function", ["/path/to/file.py"])
            
            # Check result
            assert result == {"status": "COMPLETE", "content": "Session completed"}
            
            # Check that methods were called
            mock_create_session.assert_called_once()
            mock_session.start_session.assert_called_once_with(
                "Implement a factorial function", 
                ["/path/to/file.py"]
            )
