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
# Assuming MemorySystem and FileAccessManager are importable for spec/type checks if needed
# from src.memory.memory_system import MemorySystem
# from src.handler.file_access import FileAccessManager

@pytest.fixture
def mock_memory_system():
    """Fixture providing a mock MemorySystem instance."""
    # Use spec=MemorySystem if MemorySystem is importable and you want stricter mocking
    memory_system = MagicMock() # spec=MemorySystem
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
    # Use spec=FileAccessManager if importable
    file_manager = MagicMock() # spec=FileAccessManager
    # Configure default behavior for read_file - returns content for valid paths, None for invalid
    # Ensure the mock signature matches the expected call (with max_size)
    file_manager.read_file.side_effect = lambda path, max_size=None: (
        f"Content of {path}" if "nonexistent" not in path and "error" not in path else None
    )
    return file_manager

# --- Basic Module/Class Tests ---

def test_module_structure():
    """Verify the SystemExecutorFunctions class has the required methods."""
    # Check that both required methods exist
    assert hasattr(SystemExecutorFunctions, "execute_get_context")
    assert hasattr(SystemExecutorFunctions, "execute_read_files")

    # Check method signatures
    # Check execute_get_context signature
    sig = signature(SystemExecutorFunctions.execute_get_context)
    params = list(sig.parameters.keys())
    assert len(params) == 2
    assert params[0] == "params"
    assert params[1] == "memory_system"

    # Check execute_read_files signature
    sig = signature(SystemExecutorFunctions.execute_read_files)
    params = list(sig.parameters.keys())
    assert len(params) == 2
    assert params[0] == "params"
    assert params[1] == "file_manager"

# --- Tests for execute_get_context ---

def test_execute_get_context_success(mock_memory_system):
    """Test successful context retrieval with valid query."""
    # Setup
    params = {"query": "search term"}

    # Act
    result = SystemExecutorFunctions.execute_get_context(params, mock_memory_system)

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
    mock_memory_system.get_relevant_context_for.assert_called_once()
    # Get the call arguments
    call_args = mock_memory_system.get_relevant_context_for.call_args[0][0]
    assert isinstance(call_args, ContextGenerationInput)
    assert call_args.query == "search term"
    # FIX: Check inheritedContext instead of history
    assert call_args.inheritedContext is None
    # FIX: Check inputs instead of target_files directly
    assert call_args.inputs is None

def test_execute_get_context_with_history(mock_memory_system):
    """Test context retrieval with history parameter."""
    # Setup
    params = {
        "query": "search term",
        "history": "Previous conversation context"
    }

    # Act
    result = SystemExecutorFunctions.execute_get_context(params, mock_memory_system)

    # Assert
    assert result["status"] == "COMPLETE"

    # Verify memory_system was called with history included
    mock_memory_system.get_relevant_context_for.assert_called_once()
    call_args = mock_memory_system.get_relevant_context_for.call_args[0][0]
    assert isinstance(call_args, ContextGenerationInput)
    assert call_args.query == "search term"
    # FIX: Check inheritedContext instead of history
    assert call_args.inheritedContext == "Previous conversation context"
    assert call_args.inputs is None # Check inputs is None when only history is passed

def test_execute_get_context_with_target_files(mock_memory_system):
    """Test context retrieval with target_files parameter."""
    # Setup
    target_list = ["/target/file1.py", "/target/file2.py"]
    params = {
        "query": "search term",
        "target_files": target_list
    }

    # Act
    result = SystemExecutorFunctions.execute_get_context(params, mock_memory_system)

    # Assert
    assert result["status"] == "COMPLETE"

    # Verify memory_system was called with target_files included
    mock_memory_system.get_relevant_context_for.assert_called_once()
    call_args = mock_memory_system.get_relevant_context_for.call_args[0][0]
    assert isinstance(call_args, ContextGenerationInput)
    assert call_args.query == "search term"
    # FIX: Check inheritedContext instead of history
    assert call_args.inheritedContext is None
    # FIX: Check inputs['target_files'] instead of target_files directly
    assert call_args.inputs is not None
    assert "target_files" in call_args.inputs
    assert call_args.inputs["target_files"] == target_list

def test_execute_get_context_missing_query(mock_memory_system):
    """Test validation failure when query parameter is missing."""
    # Setup
    params = {"history": "Some history"}  # Missing required 'query'

    # Act
    result = SystemExecutorFunctions.execute_get_context(params, mock_memory_system)

    # Assert
    assert result["status"] == "FAILED"
    assert "query" in result["content"].lower()  # Error message mentions missing param
    assert "error" in result["notes"]
    error_details = result["notes"]["error"]
    assert isinstance(error_details, dict) # Should be a dict representation of TaskFailureError
    assert error_details["type"] == "TASK_FAILURE"
    # FIX: Use string literal for reason check
    assert error_details["reason"] == "input_validation_failure"
    mock_memory_system.get_relevant_context_for.assert_not_called()

def test_execute_get_context_empty_query(mock_memory_system):
    """Test validation failure when query parameter is empty."""
    # Setup
    params = {"query": ""}  # Empty query

    # Act
    result = SystemExecutorFunctions.execute_get_context(params, mock_memory_system)

    # Assert
    assert result["status"] == "FAILED"
    assert "empty" in result["content"].lower() or "null" in result["content"].lower() # Error message mentions empty query
    assert "error" in result["notes"]
    # FIX: Use string literal for reason check
    assert result["notes"]["error"]["reason"] == "input_validation_failure"
    mock_memory_system.get_relevant_context_for.assert_not_called()

def test_execute_get_context_memory_system_error(mock_memory_system):
    """Test handling of errors from MemorySystem."""
    # Setup
    mock_memory_system.get_relevant_context_for.side_effect = Exception("Memory error")
    params = {"query": "search term"}

    # Act
    result = SystemExecutorFunctions.execute_get_context(params, mock_memory_system)

    # Assert
    assert result["status"] == "FAILED"
    assert "context retrieval" in result["content"].lower() or "memory" in result["content"].lower()
    assert "error" in result["notes"]
    # FIX: Use string literal for reason check
    assert result["notes"]["error"]["reason"] == "context_retrieval_failure"

def test_execute_get_context_memory_system_returns_error(mock_memory_system):
    """Test handling when MemorySystem returns result with error."""
    # Setup
    error_result = AssociativeMatchResult(
        context_summary="Error in matching",
        matches=[],
        error="Failed to match query"
    )
    mock_memory_system.get_relevant_context_for.return_value = error_result
    params = {"query": "search term"}

    # Act
    result = SystemExecutorFunctions.execute_get_context(params, mock_memory_system)

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

def test_execute_read_files_success(mock_file_manager):
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

    mock_file_manager.read_file.side_effect = read_side_effect

    params = {"file_paths": ["/path/file1.txt", "/path/file2.txt", "/path/nonexistent.txt"]}

    # Act
    result = SystemExecutorFunctions.execute_read_files(params, mock_file_manager)

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
    assert mock_file_manager.read_file.call_count == 3
    # FIX: Assertions now match the expected call signature
    mock_file_manager.read_file.assert_any_call("/path/file1.txt", max_size=None)
    mock_file_manager.read_file.assert_any_call("/path/file2.txt", max_size=None)
    mock_file_manager.read_file.assert_any_call("/path/nonexistent.txt", max_size=None)


def test_execute_read_files_all_files_missing(mock_file_manager):
    """Test behavior when all files are missing/unreadable."""
    # Setup
    mock_file_manager.read_file.return_value = None  # All files fail to read

    params = {"file_paths": ["/path/nonexistent1.txt", "/path/nonexistent2.txt"]}

    # Act
    result = SystemExecutorFunctions.execute_read_files(params, mock_file_manager)

    # Assert
    assert result["status"] == "COMPLETE"  # Still COMPLETE as the function worked
    assert "No readable files" in result["content"] or "Could not read any" in result["content"] # Should indicate no readable files
    assert result["notes"]["files_read_count"] == 0
    assert result["notes"]["skipped_files"] == ["/path/nonexistent1.txt", "/path/nonexistent2.txt"]
    assert "errors" not in result["notes"]

    # Verify read_file was called for each path
    assert mock_file_manager.read_file.call_count == 2

def test_execute_read_files_empty_paths_list(mock_file_manager):
    """Test behavior with empty file_paths list."""
    # Setup
    params = {"file_paths": []}

    # Act
    result = SystemExecutorFunctions.execute_read_files(params, mock_file_manager)

    # Assert
    assert result["status"] == "COMPLETE"  # Still COMPLETE as the function worked
    assert "No files specified" in result["content"]
    assert result["notes"]["files_read_count"] == 0
    assert result["notes"]["skipped_files"] == []
    assert "errors" not in result["notes"]

    # Verify read_file was not called
    mock_file_manager.read_file.assert_not_called()

def test_execute_read_files_missing_paths_param(mock_file_manager):
    """Test validation failure when file_paths parameter is missing."""
    # Setup
    params = {}  # Missing required 'file_paths'

    # Act
    result = SystemExecutorFunctions.execute_read_files(params, mock_file_manager)

    # Assert
    assert result["status"] == "FAILED"
    assert "file_paths" in result["content"].lower()  # Error message mentions missing param
    assert "error" in result["notes"]
    # FIX: Use string literal for reason check
    assert result["notes"]["error"]["reason"] == "input_validation_failure"
    mock_file_manager.read_file.assert_not_called()

def test_execute_read_files_invalid_paths_type(mock_file_manager):
    """Test validation failure when file_paths is not a list."""
    # Setup
    params = {"file_paths": "not_a_list"}  # Wrong type

    # Act
    result = SystemExecutorFunctions.execute_read_files(params, mock_file_manager)

    # Assert
    assert result["status"] == "FAILED"
    assert "list" in result["content"].lower()  # Error message mentions expected list
    assert "error" in result["notes"]
    # FIX: Use string literal for reason check
    assert result["notes"]["error"]["reason"] == "input_validation_failure"
    mock_file_manager.read_file.assert_not_called()

def test_execute_read_files_with_unexpected_error(mock_file_manager):
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

    mock_file_manager.read_file.side_effect = side_effect

    params = {"file_paths": ["/path/file1.txt", "/path/error.txt", "/path/file2.txt"]}

    # Act
    result = SystemExecutorFunctions.execute_read_files(params, mock_file_manager)

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
    assert mock_file_manager.read_file.call_count == 3
