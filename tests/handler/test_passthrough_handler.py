"""Tests for the PassthroughHandler."""
import pytest
from unittest.mock import patch, MagicMock
from handler.passthrough_handler import PassthroughHandler
from handler.model_provider import ClaudeProvider
from handler.file_access import FileAccessManager

class TestPassthroughHandler:
    """Tests for the PassthroughHandler class."""

    def test_init(self, mock_task_system, mock_memory_system):
        """Test PassthroughHandler initialization."""
        # Mock the ClaudeProvider to avoid API key requirement in tests
        with patch('handler.passthrough_handler.ClaudeProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider
            
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            
            assert handler.task_system == mock_task_system
            assert handler.memory_system == mock_memory_system
            assert handler.active_subtask_id is None
            assert handler.conversation_history == []
            assert handler.model_provider == mock_provider
            assert isinstance(handler.file_manager, FileAccessManager)

    def test_handle_query_new_subtask(self, mock_task_system, mock_memory_system):
        """Test handle_query when no active subtask exists."""
        # Mock the ClaudeProvider and FileAccessManager
        with patch('handler.passthrough_handler.ClaudeProvider') as mock_provider_class, \
             patch('handler.passthrough_handler.FileAccessManager') as mock_file_manager_class:
            # Setup mocks
            mock_provider = MagicMock()
            mock_provider.send_message.return_value = "This is a model response"
            mock_provider_class.return_value = mock_provider
            
            mock_file_manager = MagicMock()
            mock_file_manager.read_file.return_value = "File content"
            mock_file_manager_class.return_value = mock_file_manager
            
            # Setup memory system mock to return relevant files
            mock_memory_system.get_relevant_context_for.return_value = MagicMock(
                matches=[("file1.py", "metadata1"), ("file2.py", "metadata2")]
            )
            
            # Create handler and test
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            result = handler.handle_query("test query")
            
            # Verify the result
            assert result["status"] == "success"
            assert result["content"] == "This is a model response"
            assert "metadata" in result
            assert "subtask_id" in result["metadata"]
            assert "relevant_files" in result["metadata"]
            assert len(result["metadata"]["relevant_files"]) == 2
            
            # Verify conversation history was updated
            assert len(handler.conversation_history) == 2
            assert handler.conversation_history[0]["role"] == "user"
            assert handler.conversation_history[0]["content"] == "test query"
            assert handler.conversation_history[1]["role"] == "assistant"
            assert handler.conversation_history[1]["content"] == "This is a model response"
            
            # Verify active subtask ID was set
            assert handler.active_subtask_id is not None

    def test_handle_query_continue_subtask(self, mock_task_system, mock_memory_system):
        """Test handle_query when an active subtask exists."""
        # Mock the ClaudeProvider and FileAccessManager
        with patch('handler.passthrough_handler.ClaudeProvider') as mock_provider_class, \
             patch('handler.passthrough_handler.FileAccessManager') as mock_file_manager_class:
            # Setup mocks
            mock_provider = MagicMock()
            mock_provider.send_message.side_effect = ["First response", "Second response"]
            mock_provider_class.return_value = mock_provider
            
            mock_file_manager = MagicMock()
            mock_file_manager.read_file.return_value = "File content"
            mock_file_manager_class.return_value = mock_file_manager
            
            # Setup memory system mock to return relevant files
            mock_memory_system.get_relevant_context_for.return_value = MagicMock(
                matches=[("file1.py", "metadata1"), ("file2.py", "metadata2")]
            )
            
            # Create handler and test
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            
            # First query to establish conversation
            handler.handle_query("first query")
            
            # Reset mocks to verify second call
            mock_memory_system.get_relevant_context_for.reset_mock()
            mock_provider.send_message.reset_mock()
            mock_provider.send_message.return_value = "Second response"
            
            # Second query to continue conversation
            result = handler.handle_query("second query")
            
            # Verify the result
            assert result["status"] == "success"
            assert result["content"] == "Second response"
            
            # Verify conversation history was updated
            assert len(handler.conversation_history) == 4  # 2 user + 2 assistant messages
            
            # Verify memory system was called again
            mock_memory_system.get_relevant_context_for.assert_called_once()
            
            # Verify model was called with conversation history
            mock_provider.send_message.assert_called_once()

    def test_get_relevant_files(self, mock_task_system, mock_memory_system):
        """Test _get_relevant_files method."""
        # Mock the ClaudeProvider
        with patch('handler.passthrough_handler.ClaudeProvider'):
            # Setup memory system mock to return relevant files
            mock_memory_system.get_relevant_context_for.return_value = MagicMock(
                matches=[("file1.py", "metadata1"), ("file2.py", "metadata2")]
            )
            
            # Create handler and test
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            relevant_files = handler._get_relevant_files("test query")
            
            # Verify the result
            assert len(relevant_files) == 2
            assert "file1.py" in relevant_files
            assert "file2.py" in relevant_files
            
            # Verify memory system was called with correct input
            mock_memory_system.get_relevant_context_for.assert_called_once_with({
                "taskText": "test query",
                "inheritedContext": ""
            })

    def test_create_file_context(self, mock_task_system, mock_memory_system):
        """Test _create_file_context method."""
        # Mock the ClaudeProvider and FileAccessManager
        with patch('handler.passthrough_handler.ClaudeProvider'), \
             patch('handler.passthrough_handler.FileAccessManager') as mock_file_manager_class:
            # Setup file manager mock
            mock_file_manager = MagicMock()
            mock_file_manager.read_file.side_effect = lambda path: f"Content of {path}" if path == "file1.py" else None
            mock_file_manager_class.return_value = mock_file_manager
            
            # Create handler and test
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            file_context = handler._create_file_context(["file1.py", "file2.py"])
            
            # Verify the result
            assert "file1.py" in file_context
            assert "Content of file1.py" in file_context
            assert "file2.py" in file_context
            assert "could not be read" in file_context
            
            # Verify file manager was called for each file
            assert mock_file_manager.read_file.call_count == 2

    def test_reset_conversation(self, mock_task_system, mock_memory_system):
        """Test reset_conversation method."""
        # Mock the ClaudeProvider
        with patch('handler.passthrough_handler.ClaudeProvider'):
            # Create handler and setup conversation state
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            handler.conversation_history = [
                {"role": "user", "content": "test query"},
                {"role": "assistant", "content": "test response"}
            ]
            handler.active_subtask_id = "test-id"
            
            # Reset conversation
            handler.reset_conversation()
            
            # Verify state was reset
            assert handler.conversation_history == []
            assert handler.active_subtask_id is None
