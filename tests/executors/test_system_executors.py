"""Unit tests for system executors."""
import pytest
import json
from unittest.mock import MagicMock, patch
from pydantic import ValidationError # Import for expected errors

# Import the functions to test
from src.executors.system_executors import execute_get_context, execute_read_files
# Import conceptual Pydantic models for type hinting in tests
# from src.executors.system_executors import GetContextParams, ReadFilesParams, RunScriptParams
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
    mock_result.context = "Mock context" # Use attribute access
    # Use 3-tuples for matches as AssociativeMatchResult expects
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
        # Arrange
        # Pass dictionary matching conceptual GetContextParams
        params_dict = {"query": "test query"}
        
        # Act
        # TODO: After Phase 3 impl, change signature:
        # from src.executors.system_executors import GetContextParams
        # params_model = GetContextParams(**params_dict)
        # result = execute_get_context(params_model, mock_memory)
        result = execute_get_context(params_dict, mock_memory) # Current signature
        
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
        # Arrange
        params_dict = {
            "query": "test query",
            "history": "previous conversation"
        }
        
        # Act
        # TODO: Refactor signature after Phase 3 impl
        result = execute_get_context(params_dict, mock_memory)
        
        # Assert
        assert result["status"] == "COMPLETE"
        
        # Verify memory_system was called with history context
        call_arg = mock_memory.get_relevant_context_for.call_args[0][0]
        assert call_arg.history_context == "previous conversation"

    def test_success_with_target_files_list(self, mock_memory):
        """Test successful execution with query and target files hint as a list."""
        # Arrange
        params_dict = {
            "query": "test query",
            "target_files": ["specific_file.py"]
        }
        
        # Act
        # TODO: Refactor signature after Phase 3 impl
        result = execute_get_context(params_dict, mock_memory)
        
        # Assert
        assert result["status"] == "COMPLETE"
        
        # Verify memory_system was called with target files hint
        call_arg = mock_memory.get_relevant_context_for.call_args[0][0]
        assert call_arg.inputs["target_files_hint"] == ["specific_file.py"]

    def test_success_with_target_files_json_string(self, mock_memory):
        """Test Pydantic parsing target_files JSON string (will test after impl)."""
        # Arrange
        params_dict = {"query": "test query", "target_files": '["specific_file.py"]'}
        expected_list = ["specific_file.py"]

        # Act & Assert
        # TODO: Assert ValidationError is NOT raised after Phase 3 impl.
        # For now, this test might fail or pass depending on current manual parsing.
        # Add a comment for the future assertion:
        # from src.executors.system_executors import GetContextParams
        # params_model = GetContextParams(**params_dict) # Should parse JSON string
        # result = execute_get_context(params_model, mock_memory)
        # assert result["status"] == "COMPLETE"
        # call_arg = mock_memory.get_relevant_context_for.call_args[0][0]
        # assert call_arg.inputs["target_files_hint"] == expected_list
        pass # Placeholder

    def test_validation_error_missing_query(self, mock_memory):
        """Test ValidationError when query is missing (assuming it becomes required)."""
        # Arrange
        params_dict = {} # Missing query

        # Act & Assert
        # TODO: Assert ValidationError once Phase 3 source code is implemented.
        # Assuming 'query' will be required in GetContextParams model.
        # Add a comment for the future assertion:
        # from src.executors.system_executors import GetContextParams
        # with pytest.raises(ValidationError, match="query"):
        #     params_model = GetContextParams(**params_dict)
        #     # execute_get_context(params_model, mock_memory) # Call might not be needed
        pass # Placeholder

    def test_validation_error_invalid_target_files_type(self, mock_memory):
        """Test ValidationError for invalid target_files type."""
        # Arrange
        params_dict = {"query": "test query", "target_files": 123} # Invalid type

        # Act & Assert
        # TODO: Assert ValidationError once Phase 3 source code is implemented.
        # Add a comment for the future assertion:
        # from src.executors.system_executors import GetContextParams
        # with pytest.raises(ValidationError, match="target_files"):
        #     params_model = GetContextParams(**params_dict)
        pass # Placeholder

    def test_memory_system_error(self, mock_memory):
        """Test handling of memory system errors."""
        # Arrange
        params_dict = {"query": "test query"}
        mock_memory.get_relevant_context_for.side_effect = Exception("Memory system error")
        
        # Act
        # TODO: Refactor signature after Phase 3 impl
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
        # Arrange
        params_dict = {"query": "test query"}
        mock_result = MagicMock(spec=AssociativeMatchResult)
        mock_result.context = "No matches found" # Use attribute access
        mock_result.matches = []  # Empty matches list
        mock_memory.get_relevant_context_for.return_value = mock_result
        
        # Act
        # TODO: Refactor signature after Phase 3 impl
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
        # Arrange
        params_dict = {"file_paths": ["path/to/file1.py", "path/to/file2.md"]}
        
        # Act
        # TODO: Refactor signature after Phase 3 impl
        # from src.executors.system_executors import ReadFilesParams
        # params_model = ReadFilesParams(**params_dict)
        # result = execute_read_files(params_model, mock_file_manager)
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
        # Arrange
        params_dict = {"file_paths": ["path/to/file1.py", "path/to/nonexistent.txt"]}
        
        # Act
        # TODO: Refactor signature after Phase 3 impl
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

    def test_validation_error_missing_file_paths(self, mock_file_manager):
        """Test ValidationError when file_paths is missing."""
        # Arrange
        params_dict = {} # Missing file_paths

        # Act & Assert
        # TODO: Assert ValidationError once Phase 3 source code is implemented.
        # Add a comment for the future assertion:
        # from src.executors.system_executors import ReadFilesParams
        # with pytest.raises(ValidationError, match="file_paths"):
        #     params_model = ReadFilesParams(**params_dict)
        pass # Placeholder

    def test_empty_input_list(self, mock_file_manager):
        """Test with empty file paths list."""
        # Arrange
        params_dict = {"file_paths": []}
        
        # Assert
        assert result["status"] == "COMPLETE"
        assert result["content"] == ""  # Empty content
        assert result["notes"]["files_read_count"] == 0
        assert result["notes"]["skipped_files"] == []
        
        # Verify file_manager was not called
        mock_file_manager.read_file.assert_not_called()

    def test_validation_error_invalid_file_paths_type(self, mock_file_manager):
        """Test ValidationError for invalid file_paths type."""
        # Arrange
        params_dict = {"file_paths": "not_a_list"}

        # Act & Assert
        # TODO: Assert ValidationError once Phase 3 source code is implemented.
        # Add a comment for the future assertion:
        # from src.executors.system_executors import ReadFilesParams
        # with pytest.raises(ValidationError, match="file_paths"):
        #     params_model = ReadFilesParams(**params_dict)
        pass # Placeholder

    def test_validation_error_invalid_path_type_in_list(self, mock_file_manager):
        """Test ValidationError for invalid type within file_paths list."""
        # Arrange
        params_dict = {"file_paths": ["path/to/file1.py", 123]}

        # Act & Assert
        # TODO: Assert ValidationError once Phase 3 source code is implemented.
        # Add a comment for the future assertion:
        # from src.executors.system_executors import ReadFilesParams
        # with pytest.raises(ValidationError, match="file_paths"):
        #     params_model = ReadFilesParams(**params_dict)
        pass # Placeholder

    def test_file_manager_error(self, mock_file_manager):
        """Test handling of file manager errors."""
        # Arrange
        params = {"file_paths": ["path/to/file1.py"]}
        mock_file_manager.read_file.side_effect = Exception("File manager error")
        
        # Act
        # TODO: Refactor signature after Phase 3 impl
        result = execute_read_files(params, mock_file_manager)
        
        # Assert
        assert result["status"] == "FAILED"
        assert "Failed to read files" in result["content"]
        assert "File manager error" in result["content"]
        assert result["notes"]["error"]["reason"] == UNEXPECTED_ERROR
