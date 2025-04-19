import pytest
import json
from unittest.mock import MagicMock, patch

# Import the functions to test (adjust path as needed)
from src.executors.aider_executors import execute_aider_automatic, execute_aider_interactive, _parse_file_context

# Mock the AiderBridge class at the module level where it's imported
# Adjust the path ('src.executors.aider_executors.AiderBridge') if your structure differs
@patch('src.executors.aider_executors.AiderBridge', new_callable=MagicMock)
class TestAiderExecutors:

    # --- Tests for _parse_file_context helper ---
    def test_parse_file_context_none(self, mock_aider_bridge_class):
        paths, error = _parse_file_context(None)
        assert paths is None
        assert error is None

    def test_parse_file_context_empty_string(self, mock_aider_bridge_class):
        paths, error = _parse_file_context("")
        assert paths is None
        assert error is None

    def test_parse_file_context_valid_list(self, mock_aider_bridge_class):
        input_list = ["/path/to/file1.py", "file2.txt"]
        paths, error = _parse_file_context(input_list)
        assert paths == input_list
        assert error is None

    def test_parse_file_context_invalid_list_content(self, mock_aider_bridge_class):
        input_list = ["/path/to/file1.py", 123] # Contains non-string
        paths, error = _parse_file_context(input_list)
        assert paths is None
        assert error is not None
        assert error["status"] == "FAILED"
        assert "list must contain only strings" in error["content"]

    def test_parse_file_context_valid_json_string(self, mock_aider_bridge_class):
        input_json = '["/path/to/file1.py", "file2.txt"]'
        expected_list = ["/path/to/file1.py", "file2.txt"]
        paths, error = _parse_file_context(input_json)
        assert paths == expected_list
        assert error is None

    def test_parse_file_context_invalid_json_string_syntax(self, mock_aider_bridge_class):
        input_json = '["/path/to/file1.py", "file2.txt"' # Missing closing bracket
        paths, error = _parse_file_context(input_json)
        assert paths is None
        assert error is not None
        assert error["status"] == "FAILED"
        assert "Invalid file_context" in error["content"]
        assert "JSON string array" in error["content"]

    def test_parse_file_context_invalid_json_string_type(self, mock_aider_bridge_class):
        input_json = '{"key": "value"}' # JSON object, not array
        paths, error = _parse_file_context(input_json)
        assert paths is None
        assert error is not None
        assert error["status"] == "FAILED"
        assert "JSON must be an array of strings" in error["content"]

    def test_parse_file_context_invalid_json_string_content(self, mock_aider_bridge_class):
        input_json = '["/path/to/file1.py", 123]' # Array contains non-string
        paths, error = _parse_file_context(input_json)
        assert paths is None
        assert error is not None
        assert error["status"] == "FAILED"
        assert "JSON must be an array of strings" in error["content"]

    def test_parse_file_context_invalid_type(self, mock_aider_bridge_class):
        input_other = 12345
        paths, error = _parse_file_context(input_other)
        assert paths is None
        assert error is not None
        assert error["status"] == "FAILED"
        assert "Invalid type for file_context" in error["content"]
        assert "int" in error["content"]

    # --- Tests for execute_aider_automatic ---
    def test_automatic_success_no_context(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.execute_automatic_task.return_value = {"status": "COMPLETE", "content": "Success!"}
        # Arrange: Params dict matching conceptual AiderAutoParams
        params_dict = {"prompt": "Test prompt"}

        result = execute_aider_automatic(params_dict, mock_bridge_instance)

        assert result == {"status": "COMPLETE", "content": "Success!"}
        mock_bridge_instance.execute_automatic_task.assert_called_once_with(prompt="Test prompt", file_context=None)

    def test_automatic_success_with_list_context(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.execute_automatic_task.return_value = {"status": "COMPLETE", "content": "Success!"}
        file_list = ["f1.py", "f2.py"]
        # Arrange: Params dict matching conceptual AiderAutoParams (file_context is list)
        params_dict = {"prompt": "Test prompt", "file_context": file_list}

        result = execute_aider_automatic(params_dict, mock_bridge_instance)

        assert result == {"status": "COMPLETE", "content": "Success!"}
        mock_bridge_instance.execute_automatic_task.assert_called_once_with(prompt="Test prompt", file_context=file_list)

    def test_automatic_success_with_json_context_string(self, mock_aider_bridge_class):
        """Test executor handling JSON string context (current behavior via helper)."""
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.execute_automatic_task.return_value = {"status": "COMPLETE", "content": "Success!"}
        file_json = '["f1.py", "f2.py"]'
        expected_list = ["f1.py", "f2.py"]
        # Arrange: Params dict with file_context as JSON string (as received from dispatcher currently)
        params_dict = {"prompt": "Test prompt", "file_context": file_json}

        result = execute_aider_automatic(params_dict, mock_bridge_instance)

        assert result == {"status": "COMPLETE", "content": "Success!"}
        mock_bridge_instance.execute_automatic_task.assert_called_once_with(prompt="Test prompt", file_context=expected_list)

    def test_automatic_missing_prompt_param(self, mock_aider_bridge_class):
        """Test executor failure when prompt param is missing (current behavior)."""
        mock_bridge_instance = mock_aider_bridge_class.return_value
        # Arrange: Params dict missing 'prompt'
        params_dict = {}

        result = execute_aider_automatic(params_dict, mock_bridge_instance)

        assert result["status"] == "FAILED"
        assert "Missing required parameter: prompt" in result["content"]
        mock_bridge_instance.execute_automatic_task.assert_not_called()

    def test_automatic_invalid_context_string(self, mock_aider_bridge_class):
        """Test executor failure with invalid JSON context string (current behavior via helper)."""
        mock_bridge_instance = mock_aider_bridge_class.return_value
        # Arrange: Params dict with invalid JSON string
        params_dict = {"prompt": "Test prompt", "file_context": '["f1.py",'}

        result = execute_aider_automatic(params_dict, mock_bridge_instance)

        assert result["status"] == "FAILED"
        assert "Invalid file_context" in result["content"]
        mock_bridge_instance.execute_automatic_task.assert_not_called()

    def test_automatic_bridge_exception(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.execute_automatic_task.side_effect = Exception("Bridge exploded")
        # Arrange: Params dict matching conceptual AiderAutoParams
        params_dict = {"prompt": "Test prompt"}

        result = execute_aider_automatic(params_dict, mock_bridge_instance)

        assert result["status"] == "FAILED"
        assert "Aider execution failed: Bridge exploded" in result["content"]
        assert result["notes"]["error"]["reason"] == "unexpected_error"

    @pytest.mark.xfail(reason="Pydantic validation not implemented in executor yet (Phase 3 Part 2)")
    def test_interactive_missing_query_validation(self, mock_aider_bridge_class):
        """Test validation error when query is missing."""
        from pydantic import ValidationError # Import locally for test
        mock_bridge_instance = mock_aider_bridge_class.return_value
        params_dict = {} # Missing required 'query'

        with pytest.raises(ValidationError, match="query"):
            # Hypothetical future call with Pydantic model:
            # execute_aider_interactive(AiderInteractiveParams(**params_dict), mock_bridge_instance)
            # For now, call current signature and expect xfail
            execute_aider_interactive(params_dict, mock_bridge_instance)

    @pytest.mark.xfail(reason="Pydantic validation not implemented in executor yet (Phase 3 Part 2)")
    def test_interactive_invalid_context_type_validation(self, mock_aider_bridge_class):
        """Test validation error for wrong file_context type."""
        from pydantic import ValidationError # Import locally for test
        mock_bridge_instance = mock_aider_bridge_class.return_value
        # Pass invalid type directly, assuming dispatcher/Pydantic handles JSON string -> list conversion
        params_dict = {"query": "Test", "file_context": {"invalid": "type"}}

        with pytest.raises(ValidationError, match="file_context"):
            # Hypothetical future call with Pydantic model:
            # execute_aider_interactive(AiderInteractiveParams(**params_dict), mock_bridge_instance)
            # For now, call current signature and expect xfail
            execute_aider_interactive(params_dict, mock_bridge_instance)

    @pytest.mark.xfail(reason="Pydantic validation not implemented in executor yet (Phase 3 Part 2)")
    def test_automatic_missing_prompt_validation(self, mock_aider_bridge_class):
        """Test validation error when prompt is missing."""
        from pydantic import ValidationError # Import locally for test
        mock_bridge_instance = mock_aider_bridge_class.return_value
        params_dict = {} # Missing required 'prompt'

        with pytest.raises(ValidationError, match="prompt"):
            # Hypothetical future call with Pydantic model:
            # execute_aider_automatic(AiderAutoParams(**params_dict), mock_bridge_instance)
            # For now, call current signature and expect xfail
            execute_aider_automatic(params_dict, mock_bridge_instance)

    @pytest.mark.xfail(reason="Pydantic validation not implemented in executor yet (Phase 3 Part 2)")
    def test_automatic_invalid_context_type_validation(self, mock_aider_bridge_class):
        """Test validation error for wrong file_context type."""
        from pydantic import ValidationError # Import locally for test
        mock_bridge_instance = mock_aider_bridge_class.return_value
        # Pass invalid type directly, assuming dispatcher/Pydantic handles JSON string -> list conversion
        params_dict = {"prompt": "Test", "file_context": "not_a_list_or_none"}

        with pytest.raises(ValidationError, match="file_context"):
            # Hypothetical future call with Pydantic model:
            # execute_aider_automatic(AiderAutoParams(**params_dict), mock_bridge_instance)
            # For now, call current signature and expect xfail
            execute_aider_automatic(params_dict, mock_bridge_instance)


    # --- Tests for execute_aider_interactive ---
    def test_interactive_success_no_context(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.start_interactive_session.return_value = {"status": "COMPLETE", "content": "Session ended"}
        # Arrange: Params dict matching conceptual AiderInteractiveParams
        params_dict = {"query": "Test query"}

        result = execute_aider_interactive(params_dict, mock_bridge_instance)

        assert result == {"status": "COMPLETE", "content": "Session ended"}
        mock_bridge_instance.start_interactive_session.assert_called_once_with(query="Test query", file_context=None)

    def test_interactive_success_with_list_context(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.start_interactive_session.return_value = {"status": "COMPLETE", "content": "Session ended"}
        file_list = ["f1.py", "f2.py"]
        # Arrange: Params dict matching conceptual AiderInteractiveParams
        params_dict = {"query": "Test query", "file_context": file_list}

        result = execute_aider_interactive(params_dict, mock_bridge_instance)

        assert result == {"status": "COMPLETE", "content": "Session ended"}
        mock_bridge_instance.start_interactive_session.assert_called_once_with(query="Test query", file_context=file_list)

    def test_interactive_missing_query_param(self, mock_aider_bridge_class):
        """Test executor failure when query param is missing (current behavior)."""
        mock_bridge_instance = mock_aider_bridge_class.return_value
        # Arrange: Params dict missing 'query'
        params_dict = {}

        result = execute_aider_interactive(params_dict, mock_bridge_instance)

        assert result["status"] == "FAILED"
        assert "Missing required parameter: query" in result["content"]
        mock_bridge_instance.start_interactive_session.assert_not_called()

    def test_interactive_invalid_context_type(self, mock_aider_bridge_class):
        """Test executor failure with invalid context type (current behavior via helper)."""
        mock_bridge_instance = mock_aider_bridge_class.return_value
        # Arrange: Params dict with invalid type for file_context
        params_dict = {"query": "Test query", "file_context": 123}

        result = execute_aider_interactive(params_dict, mock_bridge_instance)

        assert result["status"] == "FAILED"
        assert "Invalid type for file_context" in result["content"]
        mock_bridge_instance.start_interactive_session.assert_not_called()

    def test_interactive_bridge_exception(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.start_interactive_session.side_effect = Exception("Session failed to start")
        # Arrange: Params dict matching conceptual AiderInteractiveParams
        params_dict = {"query": "Test query"}

        result = execute_aider_interactive(params_dict, mock_bridge_instance)

        assert result["status"] == "FAILED"
        assert "Aider session failed: Session failed to start" in result["content"]
        assert result["notes"]["error"]["reason"] == "unexpected_error"
