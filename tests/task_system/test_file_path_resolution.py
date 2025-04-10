"""Tests for file path resolution in Task System."""
import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, List, Any, Optional, Tuple

from task_system.task_system import TaskSystem

class TestFilePathResolution:
    """Tests for file path resolution functionality in TaskSystem."""
    
    @pytest.fixture
    def mock_memory_system(self):
        """Fixture for mock memory system."""
        memory_system = MagicMock()
        
        # Setup mock for get_relevant_context_with_description
        context_result = MagicMock()
        context_result.matches = [
            ("file1.py", 0.9),
            ("file2.py", 0.8)
        ]
        memory_system.get_relevant_context_with_description.return_value = context_result
        
        return memory_system
    
    @pytest.fixture
    def mock_handler(self):
        """Fixture for mock handler."""
        handler = MagicMock()
        
        # Setup mock for execute_file_path_command
        handler.execute_file_path_command.return_value = ["file3.py", "file4.py"]
        
        # Setup mock for _execute_tool
        tool_result = {
            "status": "success",
            "content": "Found 2 files",
            "metadata": {
                "file_paths": ["file5.py", "file6.py"],
                "success": True
            }
        }
        handler._execute_tool.return_value = tool_result
        
        return handler
    
    @pytest.fixture
    def task_system(self):
        """Fixture for TaskSystem instance."""
        return TaskSystem()
    
    def test_resolve_file_paths_literal(self, task_system, mock_memory_system, mock_handler):
        """Test resolving file paths with literal source."""
        # Create template with literal file paths
        template = {
            "file_paths": ["explicit1.py", "explicit2.py"],
            "file_paths_source": {"type": "literal"}
        }
        
        # Resolve file paths
        file_paths, error = task_system.resolve_file_paths(template, mock_memory_system, mock_handler)
        
        # Verify result
        assert len(file_paths) == 2
        assert "explicit1.py" in file_paths
        assert "explicit2.py" in file_paths
        assert error is None
        
        # Verify no interactions with memory system or handler
        mock_memory_system.get_relevant_context_with_description.assert_not_called()
        mock_handler.execute_file_path_command.assert_not_called()
    
    def test_resolve_file_paths_description(self, task_system, mock_memory_system, mock_handler):
        """Test resolving file paths with description source."""
        # Create template with description source
        template = {
            "description": "Main task",
            "file_paths_source": {
                "type": "description",
                "value": "Find Python files for authentication"
            }
        }
        
        # Resolve file paths
        file_paths, error = task_system.resolve_file_paths(template, mock_memory_system, mock_handler)
        
        # Verify result
        assert len(file_paths) == 2
        assert "file1.py" in file_paths
        assert "file2.py" in file_paths
        assert error is None
        
        # Verify memory system was called correctly
        mock_memory_system.get_relevant_context_with_description.assert_called_once_with(
            query="Main task",
            context_description="Find Python files for authentication"
        )
        
        # Verify no interactions with handler
        mock_handler.execute_file_path_command.assert_not_called()
    
    def test_resolve_file_paths_command(self, task_system, mock_memory_system, mock_handler):
        """Test resolving file paths with command source."""
        # Create template with command source
        template = {
            "file_paths_source": {
                "type": "command",
                "value": "find . -name '*.py'"
            }
        }
        
        # For this test, remove the _execute_tool method from the mock handler
        # to force it to use the direct method
        if hasattr(mock_handler, "_execute_tool"):
            delattr(mock_handler, "_execute_tool")
        
        # Resolve file paths
        file_paths, error = task_system.resolve_file_paths(template, mock_memory_system, mock_handler)
        
        # Verify result
        assert len(file_paths) == 2
        assert "file3.py" in file_paths
        assert "file4.py" in file_paths
        assert error is None
        
        # Verify handler was called correctly
        mock_handler.execute_file_path_command.assert_called_once_with("find . -name '*.py'")
        
        # Verify no interactions with memory system
        mock_memory_system.get_relevant_context_with_description.assert_not_called()
    
    """This test already correctly tests tool-based execution."""
    def test_resolve_file_paths_tool_based(self, task_system, mock_memory_system, mock_handler):
        """Test resolving file paths with tool-based execution."""
        # Create template with command source
        template = {
            "file_paths_source": {
                "type": "command",
                "value": "find . -name '*.py'"
            }
        }
        
        # Reset mock for execute_file_path_command (it shouldn't be called)
        mock_handler.execute_file_path_command.reset_mock()
        
        # Resolve file paths
        file_paths, error = task_system.resolve_file_paths(template, mock_memory_system, mock_handler)
        
        # Verify result
        assert len(file_paths) == 2
        assert "file5.py" in file_paths
        assert "file6.py" in file_paths
        assert error is None
        
        # Verify tool execution was called correctly
        mock_handler._execute_tool.assert_called_once_with(
            "executeFilePathCommand", 
            {"command": "find . -name '*.py'"}
        )
        
        # Verify direct method was not called (since tool execution succeeded)
        mock_handler.execute_file_path_command.assert_not_called()
    
    def test_error_handling_description(self, task_system, mock_memory_system, mock_handler):
        """Test error handling with description source."""
        # Setup memory system to raise exception
        mock_memory_system.get_relevant_context_with_description.side_effect = Exception("Test error")
        
        # Create template with description source
        template = {
            "file_paths_source": {
                "type": "description",
                "value": "Error test"
            }
        }
        
        # Resolve file paths
        file_paths, error = task_system.resolve_file_paths(template, mock_memory_system, mock_handler)
        
        # Verify result
        assert len(file_paths) == 0  # No paths should be returned
        assert error is not None
        assert "Test error" in error
    
    def test_error_handling_command(self, task_system, mock_memory_system, mock_handler):
        """Test error handling with command source."""
        # Setup handler to raise exception
        mock_handler._execute_tool.side_effect = Exception("Tool error")
        mock_handler.execute_file_path_command.side_effect = Exception("Command error")
        
        # Create template with command source
        template = {
            "file_paths_source": {
                "type": "command",
                "value": "error_command"
            }
        }
        
        # Resolve file paths
        file_paths, error = task_system.resolve_file_paths(template, mock_memory_system, mock_handler)
        
        # Verify result
        assert len(file_paths) == 0  # No paths should be returned
        assert error is not None
        assert "error_command" in error
        assert any(x in error for x in ["Tool error", "Command error"])
