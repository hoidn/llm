"""Integration tests for handler system."""
import pytest
from unittest.mock import patch, MagicMock, call

from src.handler.base_handler import BaseHandler
from src.handler.passthrough_handler import PassthroughHandler
from src.handler.model_provider import ProviderAdapter

class TestHandlerIntegration:
    """Integration tests for handler system."""

    def test_inheritance_and_overrides(self, mock_task_system, mock_memory_system):
        """Test that inheritance works correctly with method overrides."""
        # Create handlers with mocked dependencies
        with patch('src.handler.model_provider.ClaudeProvider'), \
             patch('src.handler.file_access.FileAccessManager'):
            base_handler = BaseHandler(mock_task_system, mock_memory_system)
            passthrough_handler = PassthroughHandler(mock_task_system, mock_memory_system)
            
            # Check base functionality is available in both
            assert hasattr(base_handler, 'register_tool')
            assert hasattr(passthrough_handler, 'register_tool')
            
            # Check that PassthroughHandler has specialized functionality
            assert not hasattr(base_handler, 'handle_query')
            assert hasattr(passthrough_handler, 'handle_query')
            
            # Check that both handlers have reset_conversation but implementations differ
            assert hasattr(base_handler, 'reset_conversation')
            assert hasattr(passthrough_handler, 'reset_conversation')
            
            # Reset conversation in both handlers
            base_handler.conversation_history = [{"role": "user", "content": "test"}]
            passthrough_handler.conversation_history = [{"role": "user", "content": "test"}]
            passthrough_handler.active_subtask_id = "test-id"
            
            base_handler.reset_conversation()
            passthrough_handler.reset_conversation()
            
            # Check that PassthroughHandler's implementation resets additional state
            assert passthrough_handler.active_subtask_id is None
    
    def test_tool_registration_and_execution(self, mock_task_system, mock_memory_system):
        """Test that tool registration and execution work across inheritance."""
        # Create a tool specification and executor
        tool_spec = {
            "name": "test_tool",
            "description": "Test tool",
            "input_schema": {
                "type": "object",
                "properties": {
                    "param": {"type": "string", "description": "Test parameter"}
                }
            }
        }
        tool_executor = MagicMock(return_value={"status": "success", "content": "Tool executed"})
        
        # Create handler with mocked dependencies
        with patch('handler.model_provider.ClaudeProvider') as mock_provider_class, \
             patch('handler.file_access.FileAccessManager'):
            # Mock provider to return a tool invocation response
            mock_provider = MagicMock()
            mock_provider.send_message.return_value = "Response with tool call"
            mock_provider.extract_tool_calls.return_value = {
                "content": "Using tool",
                "tool_calls": [
                    {"name": "test_tool", "parameters": {"param": "value"}}
                ],
                "awaiting_tool_response": False
            }
            mock_provider_class.return_value = mock_provider
            
            # Create handler and register tool
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            handler.model_provider = mock_provider
            handler.register_tool(tool_spec, tool_executor)
            
            # Handle a query that will trigger tool invocation
            result = handler.handle_query("Use test_tool")
            
            # Check that tool was executed
            tool_executor.assert_called_once_with({"param": "value"})
            
            # Check that result contains tool execution result
            assert result["content"] == "Tool executed"
    
    def test_direct_vs_subtask_tool_registration(self, mock_task_system, mock_memory_system):
        """Test the difference between direct and subtask tool registration."""
        with patch('src.handler.model_provider.ClaudeProvider'), \
             patch('src.handler.file_access.FileAccessManager'):
            # Create handler
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            
            # Test registerDirectTool
            direct_func = MagicMock(return_value={"status": "success", "content": "Direct tool executed"})
            direct_result = handler.registerDirectTool("directTool", direct_func)
            
            # Test registerSubtaskTool
            subtask_func = MagicMock(return_value={"status": "success", "content": "Subtask tool executed"})
            subtask_result = handler.registerSubtaskTool("subtaskTool", subtask_func)
            
            # Check registration results
            assert direct_result is True
            assert subtask_result is True
            
            # Check tool registrations
            assert "directTool" in handler.registered_tools
            assert "subtaskTool" in handler.registered_tools
            assert "directTool" in handler.tool_executors
            assert "subtaskTool" in handler.tool_executors
            
            # Check that direct tools have correct wrappers
            direct_wrapper = handler.tool_executors["directTool"]
            subtask_wrapper = handler.tool_executors["subtaskTool"]
            
            # Test direct tool wrapper with query
            direct_wrapper({"query": "test query", "file_context": ["file.py"]})
            direct_func.assert_called_with("test query", ["file.py"])
            
            # Test subtask tool wrapper with prompt
            subtask_wrapper({"prompt": "test prompt", "file_context": ["file.py"]})
            subtask_func.assert_called_with("test prompt", ["file.py"])
