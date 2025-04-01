"""Tests for the PassthroughHandler."""
import pytest
from unittest.mock import patch, MagicMock
from handler.passthrough_handler import PassthroughHandler
from handler.model_provider import ClaudeProvider
from handler.file_access import FileAccessManager
from handler.base_handler import BaseHandler

class TestPassthroughHandler:
    """Tests for the PassthroughHandler class."""

    def test_init(self, mock_task_system, mock_memory_system):
        """Test PassthroughHandler initialization."""
        # Mock the ProviderAdapter and FileAccessManager to avoid API key requirement in tests
        with patch('handler.model_provider.ClaudeProvider') as mock_provider_class, \
             patch('handler.file_access.FileAccessManager') as mock_file_manager_class:
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider
            
            mock_file_manager = MagicMock()
            mock_file_manager_class.return_value = mock_file_manager
            
            # Create handler with mocked dependencies
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            # Replace the file_manager that was created in __init__
            handler.file_manager = mock_file_manager
            
            # Check inheritance
            assert isinstance(handler, BaseHandler)
            
            # Check PassthroughHandler specific attributes
            assert handler.task_system == mock_task_system
            assert handler.memory_system == mock_memory_system
            assert handler.active_subtask_id is None
            assert handler.conversation_history == []
            assert handler.file_manager == mock_file_manager

    def test_handle_query_new_subtask(self, mock_task_system, mock_memory_system):
        """Test handle_query when no active subtask exists."""
        # Mock the ClaudeProvider and FileAccessManager
        with patch('handler.model_provider.ClaudeProvider') as mock_provider_class, \
             patch('handler.file_access.FileAccessManager') as mock_file_manager_class:
            # Setup mocks
            mock_provider = MagicMock()
            mock_provider.send_message.return_value = "This is a model response"
            # Mock the extract_tool_calls method to return standardized format
            mock_provider.extract_tool_calls.return_value = {
                "content": "This is a model response",
                "tool_calls": [],
                "awaiting_tool_response": False
            }
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
            # Replace the file_manager and model_provider that were created in __init__
            handler.file_manager = mock_file_manager
            handler.model_provider = mock_provider
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
        with patch('handler.model_provider.ClaudeProvider') as mock_provider_class, \
             patch('handler.file_access.FileAccessManager') as mock_file_manager_class:
            # Setup mocks
            mock_provider = MagicMock()
            # Mock extract_tool_calls for both responses
            mock_provider.extract_tool_calls.side_effect = [
                {
                    "content": "First response",
                    "tool_calls": [],
                    "awaiting_tool_response": False
                },
                {
                    "content": "Second response",
                    "tool_calls": [],
                    "awaiting_tool_response": False
                }
            ]
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
            # Replace the file_manager and model_provider that were created in __init__
            handler.file_manager = mock_file_manager
            handler.model_provider = mock_provider
            
            # First query to establish conversation
            handler.handle_query("first query")
            
            # Reset mocks to verify second call
            mock_memory_system.get_relevant_context_for.reset_mock()
            mock_provider.send_message.reset_mock()
            mock_provider.send_message.return_value = "Second response"
            # Reset extract_tool_calls mock
            mock_provider.extract_tool_calls.reset_mock()
            mock_provider.extract_tool_calls.return_value = {
                "content": "Second response",
                "tool_calls": [],
                "awaiting_tool_response": False
            }
            
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
        with patch('handler.model_provider.ClaudeProvider'):
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
        with patch('handler.model_provider.ClaudeProvider'), \
             patch('handler.file_access.FileAccessManager') as mock_file_manager_class:
            # Setup file manager mock
            mock_file_manager = MagicMock()
            mock_file_manager.read_file.side_effect = lambda path: f"Content of {path}" if path == "file1.py" else None
            mock_file_manager_class.return_value = mock_file_manager
            
            # Create handler and test
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            # Replace the file_manager that was created in __init__
            handler.file_manager = mock_file_manager
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
        with patch('handler.model_provider.ClaudeProvider'):
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
            
    def test_find_matching_template(self, mock_task_system, mock_memory_system):
        """Test finding matching templates for queries."""
        # Mock task_system.find_matching_tasks
        mock_task_system.find_matching_tasks = MagicMock()
        
        # Create test templates
        test_templates = [
            {
                "task": {
                    "type": "atomic",
                    "subtype": "associative_matching",
                    "description": "Find relevant files"
                },
                "score": 0.8,
                "taskType": "atomic",
                "subtype": "associative_matching"
            },
            {
                "task": {
                    "type": "atomic",
                    "subtype": "standard",
                    "description": "Process data"
                },
                "score": 0.5,
                "taskType": "atomic",
                "subtype": "standard"
            }
        ]
        
        # Set up mock to return test templates
        mock_task_system.find_matching_tasks.return_value = test_templates
        
        # Create handler
        with patch('handler.model_provider.ClaudeProvider'):
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            
            # Test template finding
            template = handler._find_matching_template("find files for my project")
            
            # Verify template selection
            assert template is not None
            assert template["type"] == "atomic"
            assert template["subtype"] == "associative_matching"
            
            # Test with no matching templates
            mock_task_system.find_matching_tasks.return_value = []
            template = handler._find_matching_template("unrelated query")
            assert template is None
            
            # Test with exception
            mock_task_system.find_matching_tasks.side_effect = Exception("Test error")
            template = handler._find_matching_template("error query")
            assert template is None
    
    def test_send_to_model_with_template(self, mock_task_system, mock_memory_system):
        """Test sending query to model with template system prompt."""
        # Mock provider
        with patch('handler.model_provider.ClaudeProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.send_message.return_value = "Model response"
            mock_provider.extract_tool_calls.return_value = {
                "content": "Model response",
                "tool_calls": [],
                "awaiting_tool_response": False
            }
            mock_provider_class.return_value = mock_provider
            
            # Create test template with system_prompt
            test_template = {
                "type": "atomic",
                "subtype": "test",
                "description": "Test template",
                "system_prompt": "Template-specific instructions"
            }
            
            # Create handler
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            handler.model_provider = mock_provider
            
            # Mock _build_system_prompt to verify it's called with the template
            with patch.object(handler, '_build_system_prompt') as mock_build_prompt:
                mock_build_prompt.return_value = "Combined system prompt"
                
                # Test sending query to model
                handler._send_to_model("test query", "file context", test_template)
                
                # Verify that _build_system_prompt was called with the template
                mock_build_prompt.assert_called_once_with(test_template, "file context")
                
                # Verify that model receives combined prompt
                mock_provider.send_message.assert_called_once()
                call_args = mock_provider.send_message.call_args[1]
                assert call_args["system_prompt"] == "Combined system prompt"
    # Add test for tool extraction with provider adapter
    def test_send_to_model_with_tool_extraction(self, mock_task_system, mock_memory_system):
        """Test _send_to_model with tool extraction using provider adapter."""
        # Mock the provider and FileAccessManager
        with patch('handler.model_provider.ClaudeProvider') as mock_provider_class, \
             patch('handler.file_access.FileAccessManager'):
            # Create mock provider
            mock_provider = MagicMock()
            mock_provider.send_message.return_value = "Response with tool call"
            
            # Mock tool extraction with standardized format
            mock_provider.extract_tool_calls.return_value = {
                "content": "Using tool",
                "tool_calls": [
                    {"name": "test_tool", "parameters": {"param": "value"}}
                ],
                "awaiting_tool_response": False
            }
            
            mock_provider_class.return_value = mock_provider
            
            # Create handler
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            handler.model_provider = mock_provider
            
            # Mock tool execution
            with patch.object(handler, '_execute_tool') as mock_execute_tool:
                mock_execute_tool.return_value = {
                    "status": "success",
                    "content": "Tool executed"
                }
                
                # Send to model
                result = handler._send_to_model("test query", "file context")
                
                # Check that tool was executed
                mock_execute_tool.assert_called_once_with("test_tool", {"param": "value"})
                
                # Check result
                assert result == "Tool executed"
                
                # Verify provider was called correctly
                mock_provider.send_message.assert_called_once()
                mock_provider.extract_tool_calls.assert_called_once_with("Response with tool call")
                
    # Test handling of awaiting_tool_response
    def test_send_to_model_awaiting_tool_response(self, mock_task_system, mock_memory_system):
        """Test handling of awaiting_tool_response flag."""
        # Mock the provider
        with patch('handler.model_provider.ClaudeProvider') as mock_provider_class, \
             patch('handler.file_access.FileAccessManager'):
            # Create mock provider
            mock_provider = MagicMock()
            mock_provider.send_message.return_value = "Response requesting tool"
            
            # Mock tool extraction with awaiting_tool_response=True
            mock_provider.extract_tool_calls.return_value = {
                "content": "I need to use a tool",
                "tool_calls": [],  # No specific tool calls yet
                "awaiting_tool_response": True  # Indicates model is waiting for tool response
            }
            
            mock_provider_class.return_value = mock_provider
            
            # Create handler
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            handler.model_provider = mock_provider
            
            # Send to model
            result = handler._send_to_model("test query", "file context")
            
            # Check that the response indicates waiting for tool response
            assert "The model is requesting to use a tool" in result
            assert "multi-step tool interactions" in result
            
            # Verify provider methods were called
            mock_provider.send_message.assert_called_once()
            mock_provider.extract_tool_calls.assert_called_once()
