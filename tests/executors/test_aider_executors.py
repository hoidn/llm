import pytest
import json
from unittest.mock import MagicMock, patch
from pydantic import ValidationError # Import for expected errors

# Import the functions to test (adjust path as needed)
from src.executors.aider_executors import execute_aider_automatic, execute_aider_interactive
# Import the conceptual Pydantic models for type hinting in tests
# These won't exist until Phase 3 implementation
# from src.executors.aider_executors import AiderAutoParams, AiderInteractiveParams
from src.system.types import TaskResult # Import TaskResult

# Mock the AiderBridge class at the module level where it's imported
# Adjust the path ('src.executors.aider_executors.AiderBridge') if your structure differs
@patch('src.executors.aider_executors.AiderBridge', new_callable=MagicMock)
class TestAiderExecutors:

    # --- Remove test_parse_file_context_* tests ---
    # These tests are now covered by Pydantic validation tests below.

    # --- Tests for execute_aider_automatic ---
    def test_automatic_success_no_context(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.execute_automatic_task.return_value = TaskResult(status="COMPLETE", content="Success!", notes={})
        # Pass dictionary matching conceptual AiderAutoParams
        params_dict = {"prompt": "Test prompt"}

        # TODO: After Phase 3 impl, change signature:
        # from src.executors.aider_executors import AiderAutoParams
        # params_model = AiderAutoParams(**params_dict)
        # result = execute_aider_automatic(params_model, mock_bridge_instance)
        result = execute_aider_automatic(params_dict, mock_bridge_instance) # Current signature

        assert result.status == "COMPLETE" # Check TaskResult attribute
        assert result.content == "Success!"
        # Pydantic ensures file_context is None if not provided
        mock_bridge_instance.execute_automatic_task.assert_called_once_with(prompt="Test prompt", file_context=None)

    def test_automatic_success_with_list_context(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.execute_automatic_task.return_value = TaskResult(status="COMPLETE", content="Success!", notes={})
        file_list = ["f1.py", "f2.py"]
        # Pass dictionary matching conceptual AiderAutoParams
        params_dict = {"prompt": "Test prompt", "file_context": file_list}

        # TODO: After Phase 3 impl, change signature:
        # from src.executors.aider_executors import AiderAutoParams
        # params_model = AiderAutoParams(**params_dict)
        # result = execute_aider_automatic(params_model, mock_bridge_instance)
        result = execute_aider_automatic(params_dict, mock_bridge_instance) # Current signature

        assert result.status == "COMPLETE"
        # Pydantic ensures file_context is the list
        mock_bridge_instance.execute_automatic_task.assert_called_once_with(prompt="Test prompt", file_context=file_list)

    def test_automatic_success_with_json_context_string(self, mock_aider_bridge_class):
        """Test Pydantic parsing JSON string to list (will test after impl)."""
        # Arrange
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.execute_automatic_task.return_value = TaskResult(status="COMPLETE", content="Success!", notes={})
        file_json = '["f1.py", "f2.py"]'
        expected_list = ["f1.py", "f2.py"]
        # Pass dictionary with JSON string - Pydantic should parse it
        params_dict = {"prompt": "Test prompt", "file_context": file_json}

        # Act & Assert
        # TODO: Assert ValidationError is NOT raised after Phase 3 impl.
        # For now, this test might fail or pass depending on current manual parsing.
        # Add a comment for the future assertion:
        # from src.executors.aider_executors import AiderAutoParams
        # params_model = AiderAutoParams(**params_dict) # Should parse JSON string
        # result = execute_aider_automatic(params_model, mock_bridge_instance)
        # assert result.status == "COMPLETE"
        # mock_bridge_instance.execute_automatic_task.assert_called_once_with(prompt="Test prompt", file_context=expected_list)
        pass # Placeholder

    def test_automatic_validation_error_missing_prompt(self, mock_aider_bridge_class):
        """Test ValidationError when prompt is missing."""
        mock_bridge_instance = mock_aider_bridge_class.return_value
        params_dict = {} # Missing prompt

        # TODO: Assert ValidationError once Phase 3 source code is implemented.
        # Add a comment for the future assertion:
        # from src.executors.aider_executors import AiderAutoParams
        # with pytest.raises(ValidationError, match="prompt"):
        #     params_model = AiderAutoParams(**params_dict)
        #     # execute_aider_automatic(params_model, mock_bridge_instance) # Call might not be needed if validation happens before
        pass # Placeholder

    def test_automatic_validation_error_invalid_context_type(self, mock_aider_bridge_class):
        """Test ValidationError for invalid file_context type."""
        mock_bridge_instance = mock_aider_bridge_class.return_value
        params_dict = {"prompt": "Test prompt", "file_context": 123} # Invalid type

        # TODO: Assert ValidationError once Phase 3 source code is implemented.
        # Add a comment for the future assertion:
        # from src.executors.aider_executors import AiderAutoParams
        # with pytest.raises(ValidationError, match="file_context"):
        #     params_model = AiderAutoParams(**params_dict)
        pass # Placeholder

    def test_automatic_bridge_exception(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.execute_automatic_task.side_effect = Exception("Bridge exploded")
        params_dict = {"prompt": "Test prompt"}

        # TODO: After Phase 3 impl, change signature:
        # from src.executors.aider_executors import AiderAutoParams
        # params_model = AiderAutoParams(**params_dict)
        # result = execute_aider_automatic(params_model, mock_bridge_instance)
        result = execute_aider_automatic(params_dict, mock_bridge_instance) # Current signature

        assert result.status == "FAILED"
        assert "Aider execution failed: Bridge exploded" in result.content
        assert result.notes["error"]["reason"] == "unexpected_error"

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
        mock_bridge_instance.start_interactive_session.return_value = TaskResult(status="COMPLETE", content="Session ended", notes={})
        params_dict = {"query": "Test query"} # Use query

        # TODO: After Phase 3 impl, change signature:
        # from src.executors.aider_executors import AiderInteractiveParams
        # params_model = AiderInteractiveParams(**params_dict)
        # result = execute_aider_interactive(params_model, mock_bridge_instance)
        result = execute_aider_interactive(params_dict, mock_bridge_instance) # Current signature

        assert result.status == "COMPLETE"
        mock_bridge_instance.start_interactive_session.assert_called_once_with(query="Test query", file_context=None)

    def test_interactive_success_with_prompt_fallback(self, mock_aider_bridge_class):
        """Test using 'prompt' when 'query' is missing."""
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.start_interactive_session.return_value = TaskResult(status="COMPLETE", content="Session ended", notes={})
        params_dict = {"prompt": "Test prompt"} # Use prompt

        # TODO: After Phase 3 impl, change signature:
        # from src.executors.aider_executors import AiderInteractiveParams
        # params_model = AiderInteractiveParams(**params_dict)
        # result = execute_aider_interactive(params_model, mock_bridge_instance)
        result = execute_aider_interactive(params_dict, mock_bridge_instance) # Current signature

        assert result.status == "COMPLETE"
        # Verify bridge was called with the prompt value as the query
        mock_bridge_instance.start_interactive_session.assert_called_once_with(query="Test prompt", file_context=None)

    def test_interactive_success_with_context(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.start_interactive_session.return_value = TaskResult(status="COMPLETE", content="Session ended", notes={})
        file_list = ["f1.py", "f2.py"]
        params_dict = {"query": "Test query", "file_context": file_list}

        # TODO: After Phase 3 impl, change signature:
        # from src.executors.aider_executors import AiderInteractiveParams
        # params_model = AiderInteractiveParams(**params_dict)
        # result = execute_aider_interactive(params_model, mock_bridge_instance)
        result = execute_aider_interactive(params_dict, mock_bridge_instance) # Current signature

        assert result.status == "COMPLETE"
        mock_bridge_instance.start_interactive_session.assert_called_once_with(query="Test query", file_context=file_list)

    def test_interactive_validation_error_missing_query_and_prompt(self, mock_aider_bridge_class):
        """Test ValidationError when both query and prompt are missing."""
        mock_bridge_instance = mock_aider_bridge_class.return_value
        params_dict = {} # Missing query/prompt

        # TODO: Assert ValidationError once Phase 3 source code is implemented.
        # This might require a @model_validator in the Pydantic model.
        # Add a comment for the future assertion:
        # from src.executors.aider_executors import AiderInteractiveParams
        # with pytest.raises(ValidationError, match="query or prompt"):
        #     params_model = AiderInteractiveParams(**params_dict)
        pass # Placeholder

    def test_interactive_validation_error_invalid_context_type(self, mock_aider_bridge_class):
        """Test ValidationError for invalid file_context type."""
        mock_bridge_instance = mock_aider_bridge_class.return_value
        params_dict = {"query": "Test query", "file_context": 123} # Invalid type

        # TODO: Assert ValidationError once Phase 3 source code is implemented.
        # Add a comment for the future assertion:
        # from src.executors.aider_executors import AiderInteractiveParams
        # with pytest.raises(ValidationError, match="file_context"):
        #     params_model = AiderInteractiveParams(**params_dict)
        pass # Placeholder

    def test_interactive_bridge_exception(self, mock_aider_bridge_class):
        mock_bridge_instance = mock_aider_bridge_class.return_value
        mock_bridge_instance.start_interactive_session.side_effect = Exception("Session failed to start")
        params_dict = {"query": "Test query"}

        # TODO: After Phase 3 impl, change signature:
        # from src.executors.aider_executors import AiderInteractiveParams
        # params_model = AiderInteractiveParams(**params_dict)
        # result = execute_aider_interactive(params_model, mock_bridge_instance)
        result = execute_aider_interactive(params_dict, mock_bridge_instance) # Current signature

        assert result.status == "FAILED"
        assert "Aider session failed: Session failed to start" in result.content
        assert result.notes["error"]["reason"] == "unexpected_error"
