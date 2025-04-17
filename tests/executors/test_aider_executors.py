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
        params = {"prompt": "Test prompt"}

        result = execute_aider_automatic(params, mock_bridge_instance)

        assert result == {"status": "COMPLETE", "content": "Success!"}
        mock_bridge_instance.execute_automatic_task.assert_called_once_with(prompt="Test prompt", file_context=None)

    def test_automatic_success_with_list_context(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.execute_automatic_task.return_value = {"status": "COMPLETE", "content": "Success!"}
        file_list = ["f1.py", "f2.py"]
        params = {"prompt": "Test prompt", "file_context": file_list}

        result = execute_aider_automatic(params, mock_bridge_instance)

        assert result == {"status": "COMPLETE", "content": "Success!"}
        mock_bridge_instance.execute_automatic_task.assert_called_once_with(prompt="Test prompt", file_context=file_list)

    def test_automatic_success_with_json_context(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.execute_automatic_task.return_value = {"status": "COMPLETE", "content": "Success!"}
        file_json = '["f1.py", "f2.py"]'
        expected_list = ["f1.py", "f2.py"]
        params = {"prompt": "Test prompt", "file_context": file_json}

        result = execute_aider_automatic(params, mock_bridge_instance)

        assert result == {"status": "COMPLETE", "content": "Success!"}
        mock_bridge_instance.execute_automatic_task.assert_called_once_with(prompt="Test prompt", file_context=expected_list)

    def test_automatic_missing_prompt(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        params = {} # Missing prompt

        result = execute_aider_automatic(params, mock_bridge_instance)

        assert result["status"] == "FAILED"
        assert "Missing required parameter: prompt" in result["content"]
        mock_bridge_instance.execute_automatic_task.assert_not_called()

    def test_automatic_invalid_context(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        params = {"prompt": "Test prompt", "file_context": '["f1.py",'} # Invalid JSON

        result = execute_aider_automatic(params, mock_bridge_instance)

        assert result["status"] == "FAILED"
        assert "Invalid file_context" in result["content"]
        mock_bridge_instance.execute_automatic_task.assert_not_called()

    def test_automatic_bridge_exception(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.execute_automatic_task.side_effect = Exception("Bridge exploded")
        params = {"prompt": "Test prompt"}

        result = execute_aider_automatic(params, mock_bridge_instance)

        assert result["status"] == "FAILED"
        assert "Aider execution failed: Bridge exploded" in result["content"]
        assert result["notes"]["error"]["reason"] == "unexpected_error"

    # --- Tests for execute_aider_interactive ---
    def test_interactive_success_no_context(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.start_interactive_session.return_value = {"status": "COMPLETE", "content": "Session ended"}
        params = {"query": "Test query"}

        result = execute_aider_interactive(params, mock_bridge_instance)

        assert result == {"status": "COMPLETE", "content": "Session ended"}
        mock_bridge_instance.start_interactive_session.assert_called_once_with(query="Test query", file_context=None)

    def test_interactive_success_with_context(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.start_interactive_session.return_value = {"status": "COMPLETE", "content": "Session ended"}
        file_list = ["f1.py", "f2.py"]
        params = {"query": "Test query", "file_context": file_list}

        result = execute_aider_interactive(params, mock_bridge_instance)

        assert result == {"status": "COMPLETE", "content": "Session ended"}
        mock_bridge_instance.start_interactive_session.assert_called_once_with(query="Test query", file_context=file_list)

    def test_interactive_missing_query(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        params = {} # Missing query

        result = execute_aider_interactive(params, mock_bridge_instance)

        assert result["status"] == "FAILED"
        assert "Missing required parameter: query" in result["content"]
        mock_bridge_instance.start_interactive_session.assert_not_called()

    def test_interactive_invalid_context(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        params = {"query": "Test query", "file_context": 123} # Invalid type

        result = execute_aider_interactive(params, mock_bridge_instance)

        assert result["status"] == "FAILED"
        assert "Invalid type for file_context" in result["content"]
        mock_bridge_instance.start_interactive_session.assert_not_called()

    def test_interactive_bridge_exception(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.start_interactive_session.side_effect = Exception("Session failed to start")
        params = {"query": "Test query"}

        result = execute_aider_interactive(params, mock_bridge_instance)

        assert result["status"] == "FAILED"
        assert "Aider session failed: Session failed to start" in result["content"]
        assert result["notes"]["error"]["reason"] == "unexpected_error"
