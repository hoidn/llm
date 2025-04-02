"""Tests for the BaseHandler."""
import pytest
from unittest.mock import patch, MagicMock, call

from handler.base_handler import BaseHandler

class TestBaseHandler:
    """Tests for the BaseHandler class."""

    def test_init(self, mock_task_system, mock_memory_system):
        """Test BaseHandler initialization."""
        # Create BaseHandler
        handler = BaseHandler(mock_task_system, mock_memory_system)
        
        # Check that attributes were initialized correctly
        assert handler.task_system == mock_task_system
        assert handler.memory_system == mock_memory_system
        assert handler.conversation_history == []
        assert isinstance(handler.base_system_prompt, str)
        assert handler.debug_mode is False
        assert handler.registered_tools == {}
        assert handler.tool_executors == {}
        
    def test_register_tool(self, mock_task_system, mock_memory_system):
        """Test tool registration."""
        # Create BaseHandler
        handler = BaseHandler(mock_task_system, mock_memory_system)
        
        # Create a mock tool
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
        tool_function = MagicMock(return_value={"status": "success", "content": "Tool executed"})
        
        # Register the tool
        result = handler.register_tool(tool_spec, tool_function)
        
        # Check result and registration
        assert result is True
        assert "test_tool" in handler.registered_tools
        assert handler.registered_tools["test_tool"] == tool_spec
        assert handler.tool_executors["test_tool"] == tool_function
        
    def test_execute_tool(self, mock_task_system, mock_memory_system):
        """Test tool execution."""
        # Create BaseHandler
        handler = BaseHandler(mock_task_system, mock_memory_system)
        
        # Create a mock tool
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
        tool_function = MagicMock(return_value={"status": "success", "content": "Tool executed"})
        
        # Register the tool
        handler.register_tool(tool_spec, tool_function)
        
        # Execute the tool
        result = handler._execute_tool("test_tool", {"param": "value"})
        
        # Check result
        assert result["status"] == "success"
        assert result["content"] == "Tool executed"
        
        # Check that tool function was called with correct params
        tool_function.assert_called_once_with({"param": "value"})
        
    def test_create_file_context(self, mock_task_system, mock_memory_system):
        """Test file context creation."""
        # Mock file manager
        with patch('handler.file_access.FileAccessManager') as mock_file_manager_class:
            # Setup file manager mock
            mock_file_manager = MagicMock()
            mock_file_manager.read_file.side_effect = lambda path: f"Content of {path}" if path == "file1.py" else None
            mock_file_manager_class.return_value = mock_file_manager
            
            # Create handler
            handler = BaseHandler(mock_task_system, mock_memory_system)
            handler.file_manager = mock_file_manager
            
            # Get file context
            file_context = handler._create_file_context(["file1.py", "file2.py"])
            
            # Check file context
            assert "file1.py" in file_context
            assert "Content of file1.py" in file_context
            assert "file2.py" in file_context
            assert "could not be read" in file_context
            
    def test_get_relevant_files(self, mock_task_system, mock_memory_system):
        """Test getting relevant files from memory system."""
        # Setup memory system mock
        mock_memory_system.get_relevant_context_for.return_value = MagicMock(
            matches=[("file1.py", "metadata1"), ("file2.py", "metadata2")]
        )
        
        # Create handler
        handler = BaseHandler(mock_task_system, mock_memory_system)
        
        # Get relevant files
        relevant_files = handler._get_relevant_files("test query")
        
        # Check relevant files
        assert len(relevant_files) == 2
        assert "file1.py" in relevant_files
        assert "file2.py" in relevant_files
        
        # Check that memory system was called with correct input
        mock_memory_system.get_relevant_context_for.assert_called_once_with({
            "taskText": "test query",
            "inheritedContext": ""
        })

    def test_reset_conversation(self, mock_task_system, mock_memory_system):
        """Test conversation reset."""
        # Create handler
        handler = BaseHandler(mock_task_system, mock_memory_system)
        
        # Add some conversation history
        handler.conversation_history = [
            {"role": "user", "content": "test query"},
            {"role": "assistant", "content": "test response"}
        ]
        
        # Reset conversation
        handler.reset_conversation()
        
        # Check that conversation history was reset
        assert handler.conversation_history == []
        
    def test_set_debug_mode(self, mock_task_system, mock_memory_system, capsys):
        """Test setting debug mode."""
        # Create handler
        handler = BaseHandler(mock_task_system, mock_memory_system)
        
        # Initially debug mode should be off
        assert handler.debug_mode is False
        
        # Set debug mode on
        handler.set_debug_mode(True)
        
        # Check that debug mode was set
        assert handler.debug_mode is True
        
        # Log something and check output
        handler.log_debug("Debug message")
        captured = capsys.readouterr()
        assert "[DEBUG]" in captured.out
        assert "Debug message" in captured.out
        
        # Set debug mode off
        handler.set_debug_mode(False)
        
        # Check that debug mode was set
        assert handler.debug_mode is False
        
        # Log something and check no output
        handler.log_debug("Debug message")
        captured = capsys.readouterr()
        assert captured.out == ""
        
    def test_build_system_prompt(self, mock_task_system, mock_memory_system):
        """Test building hierarchical system prompts."""
        # Create handler
        handler = BaseHandler(mock_task_system, mock_memory_system)
        handler.base_system_prompt = "Base system prompt"
        
        # Test with base prompt only
        prompt1 = handler._build_system_prompt()
        assert prompt1 == "Base system prompt"
        
        # Test with template with system_prompt
        template = {"system_prompt": "Template-specific instructions"}
        prompt2 = handler._build_system_prompt(template)
        assert "Base system prompt" in prompt2
        assert "Template-specific instructions" in prompt2
        assert "===" in prompt2
        
        # Test with file context
        file_context = "File: test.py\nContent of test.py"
        prompt3 = handler._build_system_prompt(file_context=file_context)
        assert "Base system prompt" in prompt3
        assert "Relevant files:" in prompt3
        assert "File: test.py" in prompt3
        assert "===" in prompt3
        
        # Test with both template and file context
        prompt4 = handler._build_system_prompt(template, file_context)
        assert "Base system prompt" in prompt4
        assert "Template-specific instructions" in prompt4
        assert "Relevant files:" in prompt4
        assert "File: test.py" in prompt4
        assert prompt4.count("===") == 2
