"""
Unit tests for the SystemExecutorFunctions class.
Tests the execute_get_context and execute_read_files methods.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from inspect import signature # For signature check

from src.executors.system_executors import SystemExecutorFunctions
from src.system.models import (
    ContextGenerationInput, AssociativeMatchResult, MatchTuple,
    TaskResult, TaskFailureError, TaskFailureReason
)
# Import classes for spec parameter in MagicMock
from src.memory.memory_system import MemorySystem
from src.handler.file_access import FileAccessManager

@pytest.fixture
def mock_memory_system():
    """Fixture providing a mock MemorySystem instance."""
    # Use spec=MemorySystem for stricter mocking
    memory_system = MagicMock(spec=MemorySystem)
    # Configure default behavior for get_relevant_context_for
    mock_result = AssociativeMatchResult(
        context_summary="Test context summary",
        matches=[
            MatchTuple(path="/path/file1.py", relevance=0.9),
            MatchTuple(path="/path/file2.py", relevance=0.8)
        ]
    )
    memory_system.get_relevant_context_for.return_value = mock_result
    return memory_system

@pytest.fixture
def mock_file_manager():
    """Fixture providing a mock FileAccessManager instance."""
    # Use spec=FileAccessManager for stricter mocking
    file_manager = MagicMock(spec=FileAccessManager)
    # Configure default behavior for read_file - returns content for valid paths, None for invalid
    # Ensure the mock signature matches the expected call (with max_size)
    file_manager.read_file.side_effect = lambda path, max_size=None: (
        f"Content of {path}" if "nonexistent" not in path and "error" not in path else None
    )
    return file_manager

@pytest.fixture
def mock_command_executor():
    """Fixture providing a mock command_executor module."""
    command_executor = MagicMock()
    # Configure default behavior for execute_command_safely
    command_executor.execute_command_safely.return_value = {
        'success': True,
        'exit_code': 0,
        'stdout': 'Command output',
        'stderr': ''
    }
    return command_executor

@pytest.fixture
def system_executor_instance(mock_memory_system, mock_file_manager, mock_command_executor):
    """Fixture providing an instance of SystemExecutorFunctions with mock dependencies."""
    return SystemExecutorFunctions(
        memory_system=mock_memory_system,
        file_manager=mock_file_manager,
        command_executor_module=mock_command_executor
    )

# --- Basic Module/Class Tests ---

def test_module_structure(system_executor_instance):
    """Verify the SystemExecutorFunctions class has the required methods."""
    # Check that all required methods exist
    assert hasattr(system_executor_instance, "execute_get_context")
    assert hasattr(system_executor_instance, "execute_read_files")
    assert hasattr(system_executor_instance, "execute_list_directory")
    assert hasattr(system_executor_instance, "execute_write_file")
    assert hasattr(system_executor_instance, "execute_shell_command")

    # Check method signatures
    # Check execute_get_context signature
    sig = signature(system_executor_instance.execute_get_context)
    params = list(sig.parameters.keys())
    assert len(params) == 1
    assert params[0] == "params"

    # Check execute_read_files signature
    sig = signature(system_executor_instance.execute_read_files)
    params = list(sig.parameters.keys())
    assert len(params) == 1
    assert params[0] == "params"

    # Check execute_shell_command signature
    sig = signature(system_executor_instance.execute_shell_command)
    params = list(sig.parameters.keys())
    assert len(params) == 1
    assert params[0] == "params"

# --- Tests for execute_get_context ---

def test_execute_get_context_success(system_executor_instance):
    """Test successful context retrieval with valid query."""
    # Setup
    params = {"query": "search term"}

    # Act
    result = system_executor_instance.execute_get_context(params)

    # Assert
    assert isinstance(result, dict) # Should return a dict (TaskResult structure)
    assert result["status"] == "COMPLETE"
    assert isinstance(result["content"], str)  # Should be JSON string
    # Parse content to check it's valid JSON containing the file paths
    content_parsed = json.loads(result["content"])
    assert content_parsed == ["/path/file1.py", "/path/file2.py"]

    # Check notes contains the expected fields
    assert "notes" in result
    assert isinstance(result["notes"], dict)
    assert "file_paths" in result["notes"]
    assert result["notes"]["file_paths"] == ["/path/file1.py", "/path/file2.py"]
    assert "context_summary" in result["notes"]
    assert result["notes"]["context_summary"] == "Test context summary"

    # Verify memory_system was called with correct parameters
    system_executor_instance.memory_system.get_relevant_context_for.assert_called_once()
    # Get the call arguments
    call_args = system_executor_instance.memory_system.get_relevant_context_for.call_args[0][0]
    assert isinstance(call_args, ContextGenerationInput)
    assert call_args.query == "search term"
    # FIX: Check inheritedContext instead of history
    assert call_args.inheritedContext is None
    # FIX: Check inputs instead of target_files directly
    assert call_args.inputs is None

def test_execute_get_context_with_history(system_executor_instance):
    """Test context retrieval with history parameter."""
    # Setup
    params = {
        "query": "search term",
        "history": "Previous conversation context"
    }

    # Act
    result = system_executor_instance.execute_get_context(params)

    # Assert
    assert result["status"] == "COMPLETE"

    # Verify memory_system was called with history included
    system_executor_instance.memory_system.get_relevant_context_for.assert_called_once()
    call_args = system_executor_instance.memory_system.get_relevant_context_for.call_args[0][0]
    assert isinstance(call_args, ContextGenerationInput)
    assert call_args.query == "search term"
    # FIX: Check inheritedContext instead of history
    assert call_args.inheritedContext == "Previous conversation context"
    assert call_args.inputs is None # Check inputs is None when only history is passed

def test_execute_get_context_with_target_files(system_executor_instance):
    """Test context retrieval with target_files parameter."""
    # Setup
    target_list = ["/target/file1.py", "/target/file2.py"]
    params = {
        "query": "search term",
        "target_files": target_list
    }

    # Act
    result = system_executor_instance.execute_get_context(params)

    # Assert
    assert result["status"] == "COMPLETE"

    # Verify memory_system was called with target_files included
    system_executor_instance.memory_system.get_relevant_context_for.assert_called_once()
    call_args = system_executor_instance.memory_system.get_relevant_context_for.call_args[0][0]
    assert isinstance(call_args, ContextGenerationInput)
    assert call_args.query == "search term"
    # FIX: Check inheritedContext instead of history
    assert call_args.inheritedContext is None
    # FIX: Check inputs['target_files'] instead of target_files directly
    assert call_args.inputs is not None
    assert "target_files" in call_args.inputs
    assert call_args.inputs["target_files"] == target_list

def test_execute_get_context_missing_query(system_executor_instance):
    """Test validation failure when query parameter is missing."""
    # Setup
    params = {"history": "Some history"}  # Missing required 'query'

    # Act
    result = system_executor_instance.execute_get_context(params)

    # Assert
    assert result["status"] == "FAILED"
    assert "query" in result["content"].lower()  # Error message mentions missing param
    assert "error" in result["notes"]
    error_details = result["notes"]["error"]
    assert isinstance(error_details, dict) # Should be a dict representation of TaskFailureError
    assert error_details["type"] == "TASK_FAILURE"
    # FIX: Use string literal for reason check
    assert error_details["reason"] == "input_validation_failure"
    system_executor_instance.memory_system.get_relevant_context_for.assert_not_called()

def test_execute_get_context_empty_query(system_executor_instance):
    """Test validation failure when query parameter is empty."""
    # Setup
    params = {"query": ""}  # Empty query

    # Act
    result = system_executor_instance.execute_get_context(params)

    # Assert
    assert result["status"] == "FAILED"
    assert "empty" in result["content"].lower() or "null" in result["content"].lower() # Error message mentions empty query
    assert "error" in result["notes"]
    # FIX: Use string literal for reason check
    assert result["notes"]["error"]["reason"] == "input_validation_failure"
    system_executor_instance.memory_system.get_relevant_context_for.assert_not_called()

def test_execute_get_context_memory_system_error(system_executor_instance):
    """Test handling of errors from MemorySystem."""
    # Setup
    system_executor_instance.memory_system.get_relevant_context_for.side_effect = Exception("Memory error")
    params = {"query": "search term"}

    # Act
    result = system_executor_instance.execute_get_context(params)

    # Assert
    assert result["status"] == "FAILED"
    assert "context retrieval" in result["content"].lower() or "memory" in result["content"].lower()
    assert "error" in result["notes"]
    # FIX: Use string literal for reason check
    assert result["notes"]["error"]["reason"] == "context_retrieval_failure"

def test_execute_get_context_memory_system_returns_error(system_executor_instance):
    """Test handling when MemorySystem returns result with error."""
    # Setup
    error_result = AssociativeMatchResult(
        context_summary="Error in matching",
        matches=[],
        error="Failed to match query"
    )
    system_executor_instance.memory_system.get_relevant_context_for.return_value = error_result
    params = {"query": "search term"}

    # Act
    result = system_executor_instance.execute_get_context(params)

    # Assert
    # Even though there's an error in the result, the function itself worked correctly
    # So this should still be a COMPLETE status, but notes should include the error
    assert result["status"] == "COMPLETE"
    assert isinstance(result["content"], str)  # JSON string of empty list
    assert json.loads(result["content"]) == []  # Empty list of files
    assert "file_paths" in result["notes"]
    assert result["notes"]["file_paths"] == []
    assert "context_summary" in result["notes"]
    assert result["notes"]["context_summary"] == "Error in matching" # Summary from error result
    assert "error" in result["notes"]
    assert result["notes"]["error"] == "Failed to match query" # Error string from result

# --- Tests for execute_read_files ---

def test_execute_read_files_success(system_executor_instance):
    """Test successful reading of files."""
    # Setup
    # Use a more specific side effect for this test
    def read_side_effect(path, max_size=None): # Ensure signature matches call
        if path == "/path/file1.txt":
            return "Content of file1"
        elif path == "/path/file2.txt":
            return "Content of file2"
        elif path == "/path/nonexistent.txt":
            return None # Simulate file not found
        else:
            return None # Default for unexpected paths

    system_executor_instance.file_manager.read_file.side_effect = read_side_effect

    params = {"file_paths": ["/path/file1.txt", "/path/file2.txt", "/path/nonexistent.txt"]}

    # Act
    result = system_executor_instance.execute_read_files(params)

    # Assert
    assert isinstance(result, dict)
    assert result["status"] == "COMPLETE"
    # Check that content contains both files' content and appropriate delimiters
    assert "Content of file1" in result["content"]
    assert "Content of file2" in result["content"]
    assert "--- File: /path/file1.txt ---" in result["content"] # Check delimiter format
    assert "--- File: /path/file2.txt ---" in result["content"] # Check delimiter format
    assert "nonexistent.txt" not in result["content"] # Content of skipped file shouldn't be there

    # Check notes
    assert "notes" in result
    assert isinstance(result["notes"], dict)
    assert result["notes"]["files_read_count"] == 2
    assert result["notes"]["skipped_files"] == ["/path/nonexistent.txt"]
    assert "errors" not in result["notes"] # No unexpected errors

    # Verify read_file was called for each path
    assert system_executor_instance.file_manager.read_file.call_count == 3
    # FIX: Assertions now match the expected call signature
    system_executor_instance.file_manager.read_file.assert_any_call("/path/file1.txt", max_size=None)
    system_executor_instance.file_manager.read_file.assert_any_call("/path/file2.txt", max_size=None)
    system_executor_instance.file_manager.read_file.assert_any_call("/path/nonexistent.txt", max_size=None)


def test_execute_read_files_all_files_missing(system_executor_instance):
    """Test behavior when all files are missing/unreadable."""
    # Setup
    system_executor_instance.file_manager.read_file.return_value = None  # All files fail to read

    params = {"file_paths": ["/path/nonexistent1.txt", "/path/nonexistent2.txt"]}

    # Act
    result = system_executor_instance.execute_read_files(params)

    # Assert
    assert result["status"] == "COMPLETE"  # Still COMPLETE as the function worked
    assert "No readable files" in result["content"] or "Could not read any" in result["content"] # Should indicate no readable files
    assert result["notes"]["files_read_count"] == 0
    assert result["notes"]["skipped_files"] == ["/path/nonexistent1.txt", "/path/nonexistent2.txt"]
    assert "errors" not in result["notes"]

    # Verify read_file was called for each path
    assert system_executor_instance.file_manager.read_file.call_count == 2

def test_execute_read_files_empty_paths_list(system_executor_instance):
    """Test behavior with empty file_paths list."""
    # Setup
    params = {"file_paths": []}

    # Act
    result = system_executor_instance.execute_read_files(params)

    # Assert
    assert result["status"] == "COMPLETE"  # Still COMPLETE as the function worked
    assert "No files specified" in result["content"]
    assert result["notes"]["files_read_count"] == 0
    assert result["notes"]["skipped_files"] == []
    assert "errors" not in result["notes"]

    # Verify read_file was not called
    system_executor_instance.file_manager.read_file.assert_not_called()

def test_execute_read_files_missing_paths_param(system_executor_instance):
    """Test validation failure when file_paths parameter is missing."""
    # Setup
    params = {}  # Missing required 'file_paths'

    # Act
    result = system_executor_instance.execute_read_files(params)

    # Assert
    assert result["status"] == "FAILED"
    assert "file_paths" in result["content"].lower()  # Error message mentions missing param
    assert "error" in result["notes"]
    # FIX: Use string literal for reason check
    assert result["notes"]["error"]["reason"] == "input_validation_failure"
    system_executor_instance.file_manager.read_file.assert_not_called()

def test_execute_read_files_invalid_paths_type(system_executor_instance):
    """Test validation failure when file_paths is not a list."""
    # Setup
    params = {"file_paths": "not_a_list"}  # Wrong type

    # Act
    result = system_executor_instance.execute_read_files(params)

    # Assert
    assert result["status"] == "FAILED"
    assert "list" in result["content"].lower()  # Error message mentions expected list
    assert "error" in result["notes"]
    # FIX: Use string literal for reason check
    assert result["notes"]["error"]["reason"] == "input_validation_failure"
    system_executor_instance.file_manager.read_file.assert_not_called()

def test_execute_read_files_with_unexpected_error(system_executor_instance):
    """Test handling of unexpected exceptions during file reading."""
    # Setup
    # Make read_file raise an exception for a specific path
    def side_effect(path, max_size=None): # Ensure signature matches call
        if path == "/path/error.txt":
            raise Exception("Unexpected file error")
        elif path == "/path/file1.txt":
            return "Content of /path/file1.txt"
        elif path == "/path/file2.txt":
            return "Content of /path/file2.txt"
        else:
            return None # Default for other paths

    system_executor_instance.file_manager.read_file.side_effect = side_effect

    params = {"file_paths": ["/path/file1.txt", "/path/error.txt", "/path/file2.txt"]}

    # Act
    result = system_executor_instance.execute_read_files(params)

    # Assert
    assert result["status"] == "COMPLETE"  # Still COMPLETE as two files were read successfully
    assert "Content of /path/file1.txt" in result["content"]
    assert "Content of /path/file2.txt" in result["content"]
    assert "--- File: /path/file1.txt ---" in result["content"]
    assert "--- File: /path/file2.txt ---" in result["content"]
    assert "error.txt" not in result["content"] # Content of errored file shouldn't be there

    assert result["notes"]["files_read_count"] == 2
    assert result["notes"]["skipped_files"] == ["/path/error.txt"] # Errored file is skipped
    assert "errors" in result["notes"] # Check that errors are noted
    assert isinstance(result["notes"]["errors"], list)
    assert len(result["notes"]["errors"]) == 1
    assert "/path/error.txt" in result["notes"]["errors"][0] # Error message should mention the file
    assert "Unexpected file error" in result["notes"]["errors"][0] # Error message should contain exception detail

    # Verify read_file was called for each path
    assert system_executor_instance.file_manager.read_file.call_count == 3

# --- Tests for execute_shell_command ---

def test_execute_shell_command_success(system_executor_instance):
    """Test successful shell command execution."""
    # Setup
    system_executor_instance.command_executor.execute_command_safely.return_value = {
        'success': True,
        'exit_code': 0,
        'stdout': 'Command executed successfully',
        'stderr': ''
    }
    params = {"command": "echo 'test'"}

    # Act
    result = system_executor_instance.execute_shell_command(params)

    # Assert
    assert isinstance(result, dict)
    assert result["status"] == "COMPLETE"
    assert result["content"] == "Command executed successfully"
    assert "notes" in result
    assert result["notes"]["success"] is True
    assert result["notes"]["exit_code"] == 0
    assert result["notes"]["stdout"] == "Command executed successfully"
    assert result["notes"]["stderr"] == ""
    assert "error" not in result["notes"] # No error object on success

    # Verify command_executor was called with correct parameters
    system_executor_instance.command_executor.execute_command_safely.assert_called_once_with(
        command="echo 'test'",
        cwd=None,
        timeout=None
    )

def test_execute_shell_command_failure_exit_code(system_executor_instance):
    """Test handling of failed shell command execution (non-zero exit code)."""
    # Setup
    system_executor_instance.command_executor.execute_command_safely.return_value = {
        'success': False,
        'exit_code': 1,
        'stdout': '',
        'stderr': 'Command failed: permission denied',
        'error': 'Permission denied' # command_executor might add this key
    }
    params = {"command": "cat /root/secret"}

    # Act
    result = system_executor_instance.execute_shell_command(params)

    # Assert
    assert isinstance(result, dict)
    assert result["status"] == "FAILED"
    assert "Command failed: permission denied" in result["content"] # Content should be stderr or error
    assert "notes" in result
    assert result["notes"]["success"] is False
    assert result["notes"]["exit_code"] == 1
    assert result["notes"]["stdout"] == ""
    assert result["notes"]["stderr"] == "Command failed: permission denied"
    assert "error" in result["notes"]
    assert isinstance(result["notes"]["error"], dict) # Should be dumped TaskFailureError
    assert result["notes"]["error"]["type"] == "TASK_FAILURE"
    assert result["notes"]["error"]["reason"] == "tool_execution_error"
    assert result["notes"]["error"]["message"] == "Command failed: permission denied"

def test_execute_shell_command_timeout(system_executor_instance):
    """Test handling of command timeout."""
    # Setup
    system_executor_instance.command_executor.execute_command_safely.return_value = {
        'success': False,
        'exit_code': None, # Typically None on timeout
        'stdout': 'Partial output...',
        'stderr': '',
        'error': 'Command timed out after 5 seconds'
    }
    params = {"command": "sleep 10", "timeout": 5}

    # Act
    result = system_executor_instance.execute_shell_command(params)

    # Assert
    assert result["status"] == "FAILED"
    assert "Command timed out" in result["content"]
    assert result["notes"]["success"] is False
    assert result["notes"]["exit_code"] is None
    assert result["notes"]["stdout"] == "Partial output..."
    assert result["notes"]["stderr"] == ""
    assert "error" in result["notes"]
    assert result["notes"]["error"]["reason"] == "execution_timeout"
    assert "Command timed out" in result["notes"]["error"]["message"]

def test_execute_shell_command_unsafe(system_executor_instance):
    """Test handling of unsafe command detected by command_executor."""
    # Setup
    system_executor_instance.command_executor.execute_command_safely.return_value = {
        'success': False,
        'exit_code': None,
        'stdout': '',
        'stderr': 'Unsafe command pattern detected: rm -rf /',
        'error': 'Unsafe command pattern detected: rm -rf /'
    }
    params = {"command": "rm -rf /"}

    # Act
    result = system_executor_instance.execute_shell_command(params)

    # Assert
    assert result["status"] == "FAILED"
    assert "Unsafe command pattern detected" in result["content"]
    assert result["notes"]["success"] is False
    assert result["notes"]["exit_code"] is None
    assert "error" in result["notes"]
    assert result["notes"]["error"]["reason"] == "input_validation_failure" # Specific reason for unsafe
    assert "Unsafe command pattern detected" in result["notes"]["error"]["message"]

def test_execute_shell_command_missing_command(system_executor_instance):
    """Test validation failure when command parameter is missing."""
    # Setup
    params = {}  # Missing required 'command'

    # Act
    result = system_executor_instance.execute_shell_command(params)

    # Assert
    assert result["status"] == "FAILED"
    assert "Missing or invalid required parameter: 'command'" in result["content"]
    assert "error" in result["notes"]
    assert result["notes"]["error"]["reason"] == "input_validation_failure"
    system_executor_instance.command_executor.execute_command_safely.assert_not_called()

def test_execute_shell_command_invalid_cwd_type(system_executor_instance):
    """Test validation failure when cwd parameter has wrong type."""
    params = {"command": "echo test", "cwd": 123} # cwd should be string
    result = system_executor_instance.execute_shell_command(params)
    assert result["status"] == "FAILED"
    assert "Invalid parameter type: 'cwd'" in result["content"]
    assert result["notes"]["error"]["reason"] == "input_validation_failure"
    system_executor_instance.command_executor.execute_command_safely.assert_not_called()

def test_execute_shell_command_invalid_timeout_type(system_executor_instance):
    """Test validation failure when timeout parameter has wrong type."""
    params = {"command": "echo test", "timeout": "fast"} # timeout should be int
    result = system_executor_instance.execute_shell_command(params)
    assert result["status"] == "FAILED"
    assert "Invalid parameter type or value: 'timeout'" in result["content"]
    assert result["notes"]["error"]["reason"] == "input_validation_failure"
    system_executor_instance.command_executor.execute_command_safely.assert_not_called()

def test_execute_shell_command_invalid_timeout_value(system_executor_instance):
    """Test validation failure when timeout parameter is not positive."""
    params = {"command": "echo test", "timeout": 0} # timeout should be positive
    result = system_executor_instance.execute_shell_command(params)
    assert result["status"] == "FAILED"
    assert "Invalid parameter type or value: 'timeout'" in result["content"]
    assert result["notes"]["error"]["reason"] == "input_validation_failure"
    system_executor_instance.command_executor.execute_command_safely.assert_not_called()


def test_execute_shell_command_with_optional_params(system_executor_instance):
    """Test shell command execution with optional parameters."""
    # Setup
    system_executor_instance.command_executor.execute_command_safely.return_value = {
        'success': True,
        'exit_code': 0,
        'stdout': 'Command with options executed',
        'stderr': ''
    }
    params = {
        "command": "ls -la",
        "cwd": "/home/user",
        "timeout": 30
    }

    # Act
    result = system_executor_instance.execute_shell_command(params)

    # Assert
    assert result["status"] == "COMPLETE"
    assert result["content"] == "Command with options executed"
    
    # Verify command_executor was called with all parameters
    system_executor_instance.command_executor.execute_command_safely.assert_called_once_with(
        command="ls -la",
        cwd="/home/user",
        timeout=30
    )

def test_execute_shell_command_unexpected_error(system_executor_instance):
    """Test handling of unexpected exceptions during command execution."""
    # Setup
    system_executor_instance.command_executor.execute_command_safely.side_effect = Exception("Unexpected command error")
    params = {"command": "valid command"}

    # Act
    result = system_executor_instance.execute_shell_command(params)

    # Assert
    assert result["status"] == "FAILED"
    assert "Unexpected error executing command" in result["content"]
    assert "Unexpected command error" in result["content"]
    assert "error" in result["notes"]
    assert result["notes"]["error"]["reason"] == "unexpected_error"

def test_execute_shell_command_failure_reporting(system_executor_instance):
    """Test correct reporting for a failed shell command (e.g., pytest failure)."""
    # Setup
    command_to_test = "pytest tests/"
    mock_command_output = {
        'success': False,
        'exit_code': 1,
        'stdout': '== test session starts ==\n...collected 1 item...\nFAILED tests/test_example.py::test_failure - AssertionError',
        'stderr': 'tests/test_example.py:5: AssertionError\n== 1 failed in 0.01s ==',
        'error': 'pytest command failed' # This might be set by command_executor on non-zero exit
    }
    system_executor_instance.command_executor.execute_command_safely.return_value = mock_command_output
    
    params = {"command": command_to_test}

    # Act
    result = system_executor_instance.execute_shell_command(params)

    # Assert
    assert isinstance(result, dict)
    assert result["status"] == "FAILED"
    
    expected_content_summary = f"Command '{command_to_test}' failed with exit code 1."
    assert result["content"] == expected_content_summary
    
    assert "notes" in result
    notes = result["notes"]
    assert notes["success"] is False
    assert notes["exit_code"] == 1
    assert notes["stdout"] == mock_command_output['stdout']
    assert notes["stderr"] == mock_command_output['stderr']
    
    assert "error" in notes
    error_details = notes["error"]
    assert isinstance(error_details, dict)
    assert error_details["type"] == "TASK_FAILURE"
    assert error_details["reason"] == "tool_execution_error" # Default for non-zero exit unless specific pattern matches
    # The message in TaskFailureError should prioritize stderr if available
    assert error_details["message"] == mock_command_output['stderr']

    # Verify command_executor was called
    system_executor_instance.command_executor.execute_command_safely.assert_called_once_with(
        command=command_to_test,
        cwd=None,
        timeout=None
    )
