"""Tests for the command executor module."""
import pytest
from unittest.mock import patch, MagicMock
import os
import tempfile
import subprocess

from src.handler.command_executor import (
    execute_command_safely,
    parse_file_paths_from_output,
    _is_potentially_unsafe
)

class TestCommandExecutor:
    """Tests for the command executor functionality."""
    
    def test_is_potentially_unsafe(self):
        """Test security validation of commands."""
        # Test unsafe commands
        unsafe_commands = [
            ["rm", "-rf", "/"],
            ["sudo", "apt-get", "install"],
            ["chmod", "777", "file.txt"]
        ]
        for cmd in unsafe_commands:
            assert _is_potentially_unsafe(cmd) is True
        
        # Test commands with dangerous characters
        dangerous_cmds = [
            ["echo", "hello", ">", "file.txt"],
            ["find", ".", "-name", "*.py", "|", "grep", "test"],
            ["echo", "test", "&&", "rm", "file"]
        ]
        for cmd in dangerous_cmds:
            assert _is_potentially_unsafe(cmd) is True
        
        # Test safe commands
        safe_commands = [
            ["echo", "hello"],
            ["ls", "-la"],
            ["find", ".", "-name", "*.py"]
        ]
        for cmd in safe_commands:
            assert _is_potentially_unsafe(cmd) is False
    
    def test_parse_file_paths_from_output(self):
        """Test parsing file paths from command output."""
        # Create temporary files for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            file1_path = os.path.join(temp_dir, "file1.txt")
            file2_path = os.path.join(temp_dir, "file2.py")
            
            with open(file1_path, "w") as f:
                f.write("test")
            with open(file2_path, "w") as f:
                f.write("test")
            
            # Test with valid output
            output = f"{file1_path}\n{file2_path}\n"
            paths = parse_file_paths_from_output(output)
            assert len(paths) == 2
            assert file1_path in paths
            assert file2_path in paths
            
            # Test with non-existent file
            nonexistent_path = os.path.join(temp_dir, "nonexistent.txt")
            output = f"{file1_path}\n{nonexistent_path}\n"
            paths = parse_file_paths_from_output(output)
            assert len(paths) == 1
            assert file1_path in paths
            assert nonexistent_path not in paths
            
            # Test with empty output
            paths = parse_file_paths_from_output("")
            assert len(paths) == 0
    
    @patch("subprocess.run")
    def test_execute_command_safely_success(self, mock_run):
        """Test successful command execution."""
        # Setup mock
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "test output"
        mock_process.stderr = ""
        mock_run.return_value = mock_process
        
        # Execute test
        result = execute_command_safely("echo hello")
        
        # Verify result
        assert result["success"] is True
        assert result["output"] == "test output"
        assert result["error"] == ""
        assert result["exit_code"] == 0
        
        # Verify subprocess.run was called correctly
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0] == ["echo", "hello"]
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert "timeout" in kwargs
    
    @patch("subprocess.run")
    def test_execute_command_safely_failure(self, mock_run):
        """Test failed command execution."""
        # Setup mock
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "command not found"
        mock_run.return_value = mock_process
        
        # Execute test
        result = execute_command_safely("invalid_command")
        
        # Verify result
        assert result["success"] is False
        assert result["output"] == ""
        assert result["error"] == "command not found"
        assert result["exit_code"] == 1
    
    @patch("subprocess.run")
    def test_execute_command_safely_timeout(self, mock_run):
        """Test command timeout handling."""
        # Setup mock to raise TimeoutExpired
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=1)
        
        # Execute test
        result = execute_command_safely("sleep 10", timeout=1)
        
        # Verify result
        assert result["success"] is False
        assert "timed out" in result["error"]  # Changed from "timeout" to "timed out"
        assert result["exit_code"] == -1
    
    def test_unsafe_command_rejected(self):
        """Test that unsafe commands are rejected."""
        # Test with unsafe command
        result = execute_command_safely("rm -rf /")
        
        # Verify result
        assert result["success"] is False
        assert "unsafe" in result["error"]
        assert result["exit_code"] == -1
