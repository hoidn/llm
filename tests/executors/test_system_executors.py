"""Unit tests for system executors."""
import pytest
import json
from unittest.mock import MagicMock, patch

from src.executors.system_executors import execute_get_context, execute_read_files
from memory.context_generation import ContextGenerationInput, AssociativeMatchResult
from memory.memory_system import MemorySystem  # Import for type hinting mock
from handler.file_access import FileAccessManager  # Import for type hinting mock
from system.errors import INPUT_VALIDATION_FAILURE, UNEXPECTED_ERROR


@pytest.fixture
def mock_memory():
    """Create a mock memory system for testing."""
    mock = MagicMock(spec=MemorySystem)
    # Configure default return value for get_relevant_context_for
    mock_result = MagicMock(spec=AssociativeMatchResult)
    mock_result.context = "Mock context"
    mock_result.matches = [("file1.py", "rel1", 0.9), ("file2.txt", "rel2", 0.8)]
    mock.get_relevant_context_for.return_value = mock_result
    return mock


@pytest.fixture
def mock_file_manager():
    """Create a mock file manager for testing."""
    mock = MagicMock(spec=FileAccessManager)
    # Configure mock read_file behavior
    def mock_read(path):
        if path == "path/to/file1.py":
            return "content of file1"
        elif path == "path/to/nonexistent.txt":
            return None  # Simulate file not found or unreadable
        elif path == "path/to/file2.md":
            return "content of file2"
        else:
            return None
    mock.read_file.side_effect = mock_read
    return mock


class TestGetContextExecutor:
    """Tests for the execute_get_context function."""

    def test_success(self, mock_memory):
        """Test successful execution with valid query."""
        # Arrange: Params dict matching conceptual GetContextParams
        params_dict = {"query": "test query"}

        # Act
        result = execute_get_context(params_dict, mock_memory)
        
        # Assert
        assert result["status"] == "COMPLETE"
        assert isinstance(result["content"], str)
        
        # Verify content is valid JSON containing expected file paths
        file_paths = json.loads(result["content"])
        assert isinstance(file_paths, list)
        assert "file1.py" in file_paths
        assert "file2.txt" in file_paths
        
        # Verify notes
        assert result["notes"]["file_paths"] == ["file1.py", "file2.txt"]
        assert result["notes"]["context_summary"] == "Mock context"
        
        # Verify memory_system was called correctly
        mock_memory.get_relevant_context_for.assert_called_once()
        call_arg = mock_memory.get_relevant_context_for.call_args[0][0]
        assert isinstance(call_arg, ContextGenerationInput)
        assert call_arg.template_description == "test query"

    def test_success_with_history(self, mock_memory):
        """Test successful execution with query and history."""
        # Arrange: Params dict matching conceptual GetContextParams
        params_dict = {
            "query": "test query",
            "history": "previous conversation"
        }

        # Act
        result = execute_get_context(params_dict, mock_memory)
        
        # Assert
        assert result["status"] == "COMPLETE"
        
        # Verify memory_system was called with history context
        call_arg = mock_memory.get_relevant_context_for.call_args[0][0]
        assert call_arg.history_context == "previous conversation"

    def test_success_with_target_files(self, mock_memory):
        """Test successful execution with query and target files hint."""
        # Arrange: Params dict matching conceptual GetContextParams
        # Note: target_files should be a list according to conceptual model
        params_dict = {
            "query": "test query",
            "target_files": ["specific_file.py"]
        }

        # Act
        result = execute_get_context(params_dict, mock_memory)
        
        # Assert
        assert result["status"] == "COMPLETE"
        
        # Verify memory_system was called with target files hint
        call_arg = mock_memory.get_relevant_context_for.call_args[0][0]
        assert call_arg.inputs["target_files_hint"] == ["specific_file.py"]

    def test_no_query_param(self, mock_memory):
        """Test failure when query parameter is missing (current behavior)."""
        # Arrange: Params dict missing the 'query' key
        params_dict = {}

        # Act
        result = execute_get_context(params_dict, mock_memory)
        
        # Assert
        assert result["status"] == "FAILED"
        assert "Missing required parameter: query" in result["content"]
        assert result["notes"]["error"]["reason"] == INPUT_VALIDATION_FAILURE
        
        # Verify memory_system was not called
        mock_memory.get_relevant_context_for.assert_not_called()

    def test_memory_system_error(self, mock_memory):
        """Test handling of memory system errors."""
        # Arrange: Params dict matching conceptual GetContextParams
        params_dict = {"query": "test query"}
        mock_memory.get_relevant_context_for.side_effect = Exception("Memory system error")

        # Act
        result = execute_get_context(params_dict, mock_memory)
        
        # Assert
        assert result["status"] == "FAILED"
        assert "Failed to get context" in result["content"]
        assert "Memory system error" in result["content"]
        assert result["notes"]["error"]["reason"] == UNEXPECTED_ERROR

    @pytest.mark.xfail(reason="Pydantic validation not implemented in executor yet (Phase 3 Part 2)")
    def test_invalid_input_type_validation(self, mock_file_manager):
        """Test validation error for wrong file_paths type."""
        from pydantic import ValidationError # Import locally for test
        params_dict = {"file_paths": "not_a_list"} # Invalid type

        with pytest.raises(ValidationError, match="file_paths"):
            # Hypothetical future call with Pydantic model:
            # execute_read_files(ReadFilesParams(**params_dict), mock_file_manager)
            # For now, call current signature and expect xfail
            execute_read_files(params_dict, mock_file_manager)

    @pytest.mark.xfail(reason="Pydantic validation not implemented in executor yet (Phase 3 Part 2)")
    def test_missing_filepaths_validation(self, mock_file_manager):
        """Test validation error when file_paths is missing."""
        from pydantic import ValidationError # Import locally for test
        params_dict = {} # Missing required 'file_paths'

        with pytest.raises(ValidationError, match="file_paths"):
            # Hypothetical future call with Pydantic model:
            # execute_read_files(ReadFilesParams(**params_dict), mock_file_manager)
            # For now, call current signature and expect xfail
            execute_read_files(params_dict, mock_file_manager)

    def test_no_matches_found(self, mock_memory):
        """Test when memory system returns no matches."""
        # Arrange: Params dict matching conceptual GetContextParams
        params_dict = {"query": "test query"}
        mock_result = MagicMock(spec=AssociativeMatchResult)
        mock_result.context = "No matches found"
        mock_result.matches = []  # Empty matches list
        mock_memory.get_relevant_context_for.return_value = mock_result

        # Act
        result = execute_get_context(params_dict, mock_memory)
        
        # Assert
        assert result["status"] == "COMPLETE"
        assert result["content"] == "[]"  # Empty JSON array
        assert result["notes"]["file_paths"] == []
        assert result["notes"]["context_summary"] == "No matches found"

    @pytest.mark.xfail(reason="Pydantic validation not implemented in executor yet (Phase 3 Part 2)")
    def test_missing_query_validation(self, mock_memory):
        """Test validation error when query is missing."""
        from pydantic import ValidationError # Import locally for test
        params_dict = {} # Missing required 'query'

        with pytest.raises(ValidationError, match="query"):
            # Hypothetical future call with Pydantic model:
            # execute_get_context(GetContextParams(**params_dict), mock_memory)
            # For now, call current signature and expect xfail
            execute_get_context(params_dict, mock_memory)


class TestReadFilesExecutor:
    """Tests for the execute_read_files function."""

    def test_success(self, mock_file_manager):
        """Test successful reading of multiple files."""
        # Arrange: Params dict matching conceptual ReadFilesParams
        params_dict = {"file_paths": ["path/to/file1.py", "path/to/file2.md"]}

        # Act
        result = execute_read_files(params_dict, mock_file_manager)
        
        # Assert
        assert result["status"] == "COMPLETE"
        
        # Verify content contains both files with separators
        assert "--- START FILE: path/to/file1.py ---" in result["content"]
        assert "content of file1" in result["content"]
        assert "--- END FILE: path/to/file1.py ---" in result["content"]
        assert "--- START FILE: path/to/file2.md ---" in result["content"]
        assert "content of file2" in result["content"]
        assert "--- END FILE: path/to/file2.md ---" in result["content"]
        
        # Verify notes
        assert result["notes"]["files_read_count"] == 2
        assert result["notes"]["skipped_files"] == []
        
        # Verify file_manager was called for both paths
        assert mock_file_manager.read_file.call_count == 2
        mock_file_manager.read_file.assert_any_call("path/to/file1.py")
        mock_file_manager.read_file.assert_any_call("path/to/file2.md")

    def test_partial_success(self, mock_file_manager):
        """Test partial success when some files can't be read."""
        # Arrange: Params dict matching conceptual ReadFilesParams
        params_dict = {"file_paths": ["path/to/file1.py", "path/to/nonexistent.txt"]}

        # Act
        result = execute_read_files(params_dict, mock_file_manager)
        
        # Assert
        assert result["status"] == "COMPLETE"
        
        # Verify content contains only the readable file
        assert "--- START FILE: path/to/file1.py ---" in result["content"]
        assert "content of file1" in result["content"]
        assert "--- END FILE: path/to/file1.py ---" in result["content"]
        assert "path/to/nonexistent.txt" not in result["content"]
        
        # Verify notes
        assert result["notes"]["files_read_count"] == 1
        assert "path/to/nonexistent.txt" in result["notes"]["skipped_files"]
        
        # Verify file_manager was called for both paths
        assert mock_file_manager.read_file.call_count == 2

    def test_empty_input_list(self, mock_file_manager):
        """Test with empty file paths list."""
        # Arrange: Params dict matching conceptual ReadFilesParams
        params_dict = {"file_paths": []}

        # Act
        result = execute_read_files(params_dict, mock_file_manager)
        
        # Assert
        assert result["status"] == "COMPLETE"
        assert result["content"] == ""  # Empty content
        assert result["notes"]["files_read_count"] == 0
        assert result["notes"]["skipped_files"] == []
        
        # Verify file_manager was not called
        mock_file_manager.read_file.assert_not_called()

    def test_invalid_input_not_list(self, mock_file_manager):
        """Test with invalid file_paths (not a list) - current behavior."""
        # Arrange: Params dict with wrong type for file_paths
        params_dict = {"file_paths": "not_a_list"}

        # Act
        result = execute_read_files(params_dict, mock_file_manager)
        
        # Assert
        assert result["status"] == "FAILED"
        assert "Missing or invalid parameter: file_paths" in result["content"]
        assert result["notes"]["error"]["reason"] == INPUT_VALIDATION_FAILURE
        
        # Verify file_manager was not called
        mock_file_manager.read_file.assert_not_called()

    def test_invalid_path_type_in_list(self, mock_file_manager):
        """Test with invalid path type in the list - current behavior."""
        # Arrange: Params dict with list containing non-string
        params_dict = {"file_paths": ["path/to/file1.py", 123]}

        # Act
        result = execute_read_files(params_dict, mock_file_manager)
        
        # Assert
        assert result["status"] == "COMPLETE"
        
        # Verify content contains only the valid file
        assert "--- START FILE: path/to/file1.py ---" in result["content"]
        assert "content of file1" in result["content"]
        
        # Verify notes
        assert result["notes"]["files_read_count"] == 1
        assert "<invalid_type: int>" in result["notes"]["skipped_files"]
        
        # Verify file_manager was called only for the valid path
        assert mock_file_manager.read_file.call_count == 1
        mock_file_manager.read_file.assert_called_once_with("path/to/file1.py")

    def test_file_manager_error(self, mock_file_manager):
        """Test handling of file manager errors."""
        # Arrange: Params dict matching conceptual ReadFilesParams
        params_dict = {"file_paths": ["path/to/file1.py"]}
        mock_file_manager.read_file.side_effect = Exception("File manager error")

        # Act
        result = execute_read_files(params_dict, mock_file_manager)
        
        # Assert
        assert result["status"] == "FAILED"
        assert "Failed to read files" in result["content"]
        assert "File manager error" in result["content"]
        assert result["notes"]["error"]["reason"] == UNEXPECTED_ERROR
