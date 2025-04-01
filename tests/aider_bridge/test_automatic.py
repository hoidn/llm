"""Tests for the AiderBridge automatic mode functionality."""
import pytest
from unittest.mock import patch, MagicMock, call
import os

from aider_bridge.automatic import AiderAutomaticHandler
from aider_bridge.tools import register_automatic_tool

class TestAiderAutomaticHandler:
    """Tests for the AiderAutomaticHandler class."""
    
    def test_init(self, mock_memory_system):
        """Test initialization of AiderAutomaticHandler."""
        # Create a mock bridge
        bridge = MagicMock()
        bridge.aider_available = True
        
        # Create handler
        handler = AiderAutomaticHandler(bridge)
        
        # Check initial state
        assert handler.bridge == bridge
        assert handler.last_result is None
    
    def test_execute_task(self, mock_memory_system):
        """Test executing an automatic task."""
        # Create mock objects
        bridge = MagicMock()
        bridge.aider_available = True
        bridge.file_context = {"/path/to/file1.py", "/path/to/file2.py"}
        
        # Setup mock bridge execution
        bridge.execute_code_edit.return_value = {
            "status": "COMPLETE",
            "content": "Code changes applied successfully",
            "notes": {
                "files_modified": ["/path/to/file1.py"],
                "changes": [
                    {"file": "/path/to/file1.py", "description": "Added factorial function"}
                ]
            }
        }
        
        # Create handler
        handler = AiderAutomaticHandler(bridge)
        
        # Execute task
        result = handler.execute_task("Implement a factorial function")
        
        # Check result
        assert result["status"] == "COMPLETE"
        assert "Code changes applied successfully" in result["content"]
        assert "notes" in result
        assert "files_modified" in result["notes"]
        assert result["notes"]["files_modified"] == ["/path/to/file1.py"]
        assert "changes" in result["notes"]
        assert len(result["notes"]["changes"]) == 1
        assert result["notes"]["changes"][0]["file"] == "/path/to/file1.py"
        
        # Check that bridge method was called
        bridge.execute_code_edit.assert_called_once_with(
            "Implement a factorial function", 
            list(bridge.file_context)
        )
        
        # Check that last_result was stored
        assert handler.last_result is not None
    
    def test_execute_task_aider_not_available(self, mock_memory_system):
        """Test executing a task when Aider is not available."""
        # Create mock bridge
        bridge = MagicMock()
        bridge.aider_available = False
        
        # Create handler
        handler = AiderAutomaticHandler(bridge)
        
        # Execute task
        result = handler.execute_task("Implement a factorial function")
        
        # Check result
        assert result["status"] == "FAILED"
        assert "Aider is not available" in result["content"]
        assert "error" in result["notes"]
        assert "Aider dependency not installed" in result["notes"]["error"]
        
        # Bridge execute_code_edit should not be called
        bridge.execute_code_edit.assert_not_called()
    
    def test_execute_task_no_files(self, mock_memory_system):
        """Test executing a task with no files in context."""
        # Create mock bridge
        bridge = MagicMock()
        bridge.aider_available = True
        bridge.file_context = set()  # Empty file context
        bridge.get_context_for_query.return_value = []  # No relevant files found
        
        # Create handler
        handler = AiderAutomaticHandler(bridge)
        
        # Execute task
        result = handler.execute_task("Implement a factorial function")
        
        # Check result
        assert result["status"] == "FAILED"
        assert "No relevant files found" in result["content"]
        assert "error" in result["notes"]
        assert "No file context available" in result["notes"]["error"]
        
        # Check that get_context_for_query was called
        bridge.get_context_for_query.assert_called_once_with("Implement a factorial function")
        
        # Check that execute_code_edit was not called
        bridge.execute_code_edit.assert_not_called()
    
    def test_execute_task_with_error(self, mock_memory_system):
        """Test executing a task that results in an error."""
        # Create mock bridge
        bridge = MagicMock()
        bridge.aider_available = True
        bridge.file_context = {"/path/to/file1.py"}
        
        # Setup mock bridge execution with error
        bridge.execute_code_edit.return_value = {
            "status": "error",
            "content": "Failed to apply code changes",
            "notes": {
                "error": "Syntax error in code"
            }
        }
        
        # Create handler
        handler = AiderAutomaticHandler(bridge)
        
        # Execute task
        result = handler.execute_task("Implement a factorial function")
        
        # Check result
        assert result["status"] == "FAILED"
        assert "Failed to apply code changes" in result["content"]
        assert "error" in result["notes"]
        assert "Syntax error in code" in result["notes"]["error"]
        
        # Check that bridge method was called
        bridge.execute_code_edit.assert_called_once()
        
        # Check that last_result was stored
        assert handler.last_result is not None
    
    def test_execute_task_with_explicit_files(self, mock_memory_system):
        """Test executing a task with explicitly provided files."""
        # Create mock bridge
        bridge = MagicMock()
        bridge.aider_available = True
        
        # Setup mock bridge execution
        bridge.execute_code_edit.return_value = {
            "status": "COMPLETE",
            "content": "Code changes applied successfully",
            "notes": {
                "files_modified": ["/path/to/explicit_file.py"],
                "changes": [
                    {"file": "/path/to/explicit_file.py", "description": "Modified file"}
                ]
            }
        }
        
        # Create handler
        handler = AiderAutomaticHandler(bridge)
        
        # Execute task with explicit file context
        result = handler.execute_task(
            "Implement a factorial function", 
            ["/path/to/explicit_file.py"]
        )
        
        # Check result
        assert result["status"] == "COMPLETE"
        assert "Code changes applied successfully" in result["content"]
        
        # Check that bridge method was called with explicit files
        bridge.execute_code_edit.assert_called_once_with(
            "Implement a factorial function", 
            ["/path/to/explicit_file.py"]
        )
    
    def test_execute_task_exception(self, mock_memory_system):
        """Test executing a task that raises an exception."""
        # Create mock bridge
        bridge = MagicMock()
        bridge.aider_available = True
        bridge.file_context = {"/path/to/file1.py"}
        
        # Setup mock bridge execution to raise exception
        bridge.execute_code_edit.side_effect = Exception("Unexpected error")
        
        # Create handler
        handler = AiderAutomaticHandler(bridge)
        
        # Execute task
        result = handler.execute_task("Implement a factorial function")
        
        # Check result
        assert result["status"] == "FAILED"
        assert "Error executing task" in result["content"]
        assert "error" in result["notes"]
        assert "Unexpected error" in result["notes"]["error"]
        
        # Check that bridge method was called
        bridge.execute_code_edit.assert_called_once()
    
    def test_get_last_result(self, mock_memory_system):
        """Test getting the last execution result."""
        # Create mock bridge
        bridge = MagicMock()
        bridge.aider_available = True
        
        # Setup mock bridge execution
        test_result = {
            "status": "COMPLETE",
            "content": "Code changes applied successfully",
            "notes": {"files_modified": ["/path/to/file1.py"]}
        }
        bridge.execute_code_edit.return_value = test_result
        
        # Create handler
        handler = AiderAutomaticHandler(bridge)
        
        # Initially last_result should be None
        assert handler.get_last_result() is None
        
        # Execute task
        handler.execute_task("Implement a factorial function")
        
        # Now last_result should match the execution result
        assert handler.get_last_result() == test_result

class TestAiderBridgeAutomatic:
    """Tests for the automatic mode methods in AiderBridge."""
    
    def test_create_automatic_handler(self, mock_memory_system):
        """Test creating an automatic handler."""
        # Create AiderBridge
        from aider_bridge.bridge import AiderBridge
        bridge = AiderBridge(mock_memory_system)
        
        # Create automatic handler
        with patch('aider_bridge.automatic.AiderAutomaticHandler') as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            
            handler = bridge.create_automatic_handler()
            
            # Check result
            assert handler == mock_handler
            mock_handler_class.assert_called_once_with(bridge)
    
    def test_execute_automatic_task(self, mock_memory_system):
        """Test executing an automatic task."""
        # Create AiderBridge
        from aider_bridge.bridge import AiderBridge
        bridge = AiderBridge(mock_memory_system)
        
        # Mock handler
        mock_handler = MagicMock()
        mock_handler.execute_task.return_value = {"status": "COMPLETE", "content": "Task executed"}
        
        # Execute automatic task
        with patch.object(bridge, 'create_automatic_handler') as mock_create_handler:
            mock_create_handler.return_value = mock_handler
            
            result = bridge.execute_automatic_task("Implement a factorial function", ["/path/to/file.py"])
            
            # Check result
            assert result == {"status": "COMPLETE", "content": "Task executed"}
            
            # Check that methods were called
            mock_create_handler.assert_called_once()
            mock_handler.execute_task.assert_called_once_with(
                "Implement a factorial function", 
                ["/path/to/file.py"]
            )

class TestAutomaticToolRegistration:
    """Tests for the automatic tool registration."""
    
    def test_register_automatic_tool(self):
        """Test registering the automatic tool."""
        # Create mock objects
        handler = MagicMock(spec=["registerSubtaskTool"])
        handler.registerSubtaskTool = MagicMock()
        
        aider_bridge = MagicMock()
        aider_bridge.execute_automatic_task = MagicMock()
        
        # Register tool
        result = register_automatic_tool(handler, aider_bridge)
        
        # Check result
        assert result["status"] == "success"
        assert result["name"] == "aiderAutomatic"
        assert result["type"] == "subtask"
        
        # Check that tool was registered
        handler.registerSubtaskTool.assert_called_once()
        tool_name, tool_func = handler.registerSubtaskTool.call_args[0]
        assert tool_name == "aiderAutomatic"
        assert callable(tool_func)
    
    def test_register_automatic_tool_snake_case(self):
        """Test registering with snake_case method name."""
        # Create mock objects
        handler = MagicMock(spec=["register_subtask_tool"])
        handler.register_subtask_tool = MagicMock()
        # Make sure the camelCase version doesn't exist
        if hasattr(handler, "registerSubtaskTool"):
            del handler.registerSubtaskTool
        
        aider_bridge = MagicMock()
        
        # Register tool
        result = register_automatic_tool(handler, aider_bridge)
        
        # Check result
        assert result["status"] == "success"
        
        # Check that tool was registered using snake_case method
        handler.register_subtask_tool.assert_called_once()
    
    def test_register_automatic_tool_handler_error(self):
        """Test registering when handler doesn't support tool registration."""
        # Create mock objects
        handler = MagicMock()
        # Remove both registration methods
        if hasattr(handler, "registerSubtaskTool"):
            del handler.registerSubtaskTool
        if hasattr(handler, "register_subtask_tool"):
            del handler.register_subtask_tool
        
        aider_bridge = MagicMock()
        
        # Register tool
        result = register_automatic_tool(handler, aider_bridge)
        
        # Check result
        assert result["status"] == "error"
        assert "does not support" in result["message"]
    
    def test_automatic_tool_function(self):
        """Test the tool function created during registration."""
        # Create mock objects
        handler = MagicMock(spec=["registerSubtaskTool"])
        handler.registerSubtaskTool = MagicMock()
        
        aider_bridge = MagicMock()
        aider_bridge.execute_automatic_task = MagicMock()
        
        # Register tool
        register_automatic_tool(handler, aider_bridge)
        
        # Get tool function
        assert handler.registerSubtaskTool.called, "registerSubtaskTool was not called"
        tool_func = handler.registerSubtaskTool.call_args[0][1]
        
        # Call tool function
        tool_func("Implement a factorial function", ["/path/to/file.py"])
        
        # Check that bridge method was called
        aider_bridge.execute_automatic_task.assert_called_once_with(
            "Implement a factorial function", 
            ["/path/to/file.py"]
        )
    
    def test_register_aider_tools_includes_automatic(self):
        """Test that register_aider_tools includes automatic tool."""
        # Create mock objects
        handler = MagicMock(spec=["registerDirectTool", "registerSubtaskTool"])
        aider_bridge = MagicMock()
        
        # Register tools
        with patch('aider_bridge.tools.register_interactive_tool') as mock_register_interactive, \
             patch('aider_bridge.tools.register_automatic_tool') as mock_register_automatic:
            
            mock_register_interactive.return_value = {"status": "success", "name": "aiderInteractive"}
            mock_register_automatic.return_value = {"status": "success", "name": "aiderAutomatic"}
            
            # Call the function
            from aider_bridge.tools import register_aider_tools
            results = register_aider_tools(handler, aider_bridge)
            
            # Check results
            assert "interactive" in results, "Interactive tool registration result missing"
            assert "automatic" in results, "Automatic tool registration result missing"
            assert results["interactive"]["status"] == "success", "Interactive tool registration failed"
            assert results["automatic"]["status"] == "success", "Automatic tool registration failed"
            
            # Verify both registration functions were called
            mock_register_interactive.assert_called_once_with(handler, aider_bridge)
            mock_register_automatic.assert_called_once_with(handler, aider_bridge)
