"""Integration tests for the /task command functionality."""
import pytest
import json
import io
import sys
from unittest.mock import patch, MagicMock, ANY, call
from memory.context_generation import ContextGenerationInput, AssociativeMatchResult

@pytest.fixture
def app_instance():
    """Create a mocked application instance for testing."""
    with patch('main.AiderBridge') as MockAiderBridge, \
         patch('main.PassthroughHandler') as MockHandler, \
         patch('main.TaskSystem') as MockTaskSystem, \
         patch('main.MemorySystem') as MockMemorySystem:
        
        # Configure mocks
        mock_aider_bridge_instance = MockAiderBridge.return_value
        mock_handler_instance = MockHandler.return_value
        mock_task_system_instance = MockTaskSystem.return_value
        mock_memory_system_instance = MockMemorySystem.return_value
        
        # Mock bridge methods
        mock_aider_bridge_instance.execute_automatic_task.return_value = {
            "status": "COMPLETE", 
            "content": "Automatic task executed successfully",
            "notes": {"files_modified": ["file1.py"]}
        }
        mock_aider_bridge_instance.start_interactive_session.return_value = {
            "status": "COMPLETE", 
            "content": "Interactive session completed",
            "notes": {"session_summary": "Made changes to file1.py"}
        }
        
        # Mock handler's direct tool dict
        mock_handler_instance.direct_tool_executors = {}
        mock_handler_instance.registerDirectTool = lambda name, func: mock_handler_instance.direct_tool_executors.update({name: func})
        
        # Mock task system methods
        mock_task_system_instance.find_template.return_value = {
            "name": "aider:automatic",
            "type": "aider",
            "subtype": "automatic",
            "description": "Execute Aider in automatic mode",
            "parameters": {
                "prompt": {"type": "string", "description": "Task description", "required": True},
                "file_context": {"type": "array", "description": "Files to include", "required": False}
            },
            "context_management": {"fresh_context": "enabled"}
        }
        mock_task_system_instance.execute_subtask_directly.return_value = {
            "status": "COMPLETE",
            "content": "Subtask executed successfully",
            "notes": {}
        }
        
        # Mock memory system methods
        mock_context_result = AssociativeMatchResult(
            context="Found relevant files",
            matches=[("src/main.py", "Main file", 0.9), ("src/utils.py", "Utilities", 0.8)]
        )
        mock_memory_system_instance.get_relevant_context_for.return_value = mock_context_result
        
        # Create a class to simulate the Application structure
        class MockApp:
            def __init__(self):
                self.aider_bridge = mock_aider_bridge_instance
                self.passthrough_handler = mock_handler_instance
                self.task_system = mock_task_system_instance
                self.memory_system = mock_memory_system_instance
                
                # Register Aider tools
                self.passthrough_handler.direct_tool_executors["aider:automatic"] = lambda params: \
                    self.aider_bridge.execute_automatic_task(
                        params.get("prompt", ""), 
                        json.loads(params.get("file_context", "[]")) if isinstance(params.get("file_context"), str) else params.get("file_context", [])
                    )
                self.passthrough_handler.direct_tool_executors["aider:interactive"] = lambda params: \
                    self.aider_bridge.start_interactive_session(
                        params.get("query", ""), 
                        json.loads(params.get("file_context", "[]")) if isinstance(params.get("file_context"), str) else params.get("file_context", [])
                    )
        
        app = MockApp()
        yield app


class TestTaskCommandIntegration:
    """Integration tests for the /task command functionality."""
    
    def test_task_aider_auto_simple(self, app_instance):
        """Test basic aider:automatic task execution."""
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Create REPL instance with the mocked app
        from repl.repl import Repl
        repl = Repl(app_instance, output_stream=captured_output)
        
        # Execute task command
        repl._cmd_task('aider:automatic prompt="Add docstrings" file_context=\'["src/main.py"]\'')
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        # Verify output contains success message
        output = captured_output.getvalue()
        assert "Status: COMPLETE" in output
        assert "Automatic task executed successfully" in output
        
        # Verify the correct method was called with correct parameters
        app_instance.aider_bridge.execute_automatic_task.assert_called_once_with(
            "Add docstrings", ["src/main.py"]
        )
    
    def test_task_context_precedence_explicit_wins(self, app_instance):
        """Test that explicit file_context takes precedence over template and auto context."""
        # Arrange: Template allows auto-lookup but explicit context is provided
        mock_template = {
            "name": "aider:automatic", "type": "aider", "subtype": "automatic",
            "parameters": {"prompt": {}, "file_context": {}},
            "file_paths": ["/template/path.py"],  # Template path exists
            "context_management": {"fresh_context": "enabled"}  # Auto enabled
        }
        app_instance.task_system.find_template = MagicMock(return_value=mock_template)
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()

        # Act: Call with explicit file_context param
        from dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="aider:automatic",
            params={"prompt": "Explicit context test", "file_context": '["/request/path.py"]'},
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert
        assert result["status"] == "COMPLETE"
        app_instance.memory_system.get_relevant_context_for.assert_not_called()  # Auto lookup skipped
        app_instance.aider_bridge.execute_automatic_task.assert_called_once_with(
            "Explicit context test", ["/request/path.py"]  # Explicit request path used
        )
    
    def test_task_context_precedence_template_wins_over_auto(self, app_instance):
        """Test that template file_paths takes precedence over automatic context lookup."""
        # Arrange: Template has explicit path, auto enabled, no request path
        mock_template = {
            "name": "aider:automatic", "type": "aider", "subtype": "automatic",
            "parameters": {"prompt": {}, "file_context": {}},
            "file_paths": ["/template/path.py"],  # Template explicit path
            "context_management": {"fresh_context": "enabled"}  # Auto enabled
        }
        app_instance.task_system.find_template = MagicMock(return_value=mock_template)
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()

        # Act: Call *without* explicit file_context param
        from dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="aider:automatic",
            params={"prompt": "Template context test"},  # No file_context
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert
        assert result["status"] == "COMPLETE"
        app_instance.memory_system.get_relevant_context_for.assert_not_called()  # Auto lookup skipped
        app_instance.aider_bridge.execute_automatic_task.assert_called_once_with(
            "Template context test", ["/template/path.py"]  # Template path used
        )
    
    def test_task_auto_context_used_when_no_explicit(self, app_instance):
        """Test that automatic context lookup is used when no explicit context is provided."""
        # Arrange: Template has no file_paths, auto enabled
        mock_template = {
            "name": "aider:automatic", "type": "aider", "subtype": "automatic",
            "parameters": {"prompt": {}, "file_context": {}},
            "context_management": {"fresh_context": "enabled"}  # Auto enabled
        }
        app_instance.task_system.find_template = MagicMock(return_value=mock_template)
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        
        # Mock context result
        mock_context_result = AssociativeMatchResult(
            context="Found relevant files",
            matches=[("/auto/lookup/path.py", "Auto found file", 0.9)]
        )
        app_instance.memory_system.get_relevant_context_for.return_value = mock_context_result

        # Act: Call without explicit context
        from dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="aider:automatic",
            params={"prompt": "Auto context test"},  # No file_context
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert
        assert result["status"] == "COMPLETE"
        app_instance.memory_system.get_relevant_context_for.assert_called_once()  # Auto lookup performed
        app_instance.aider_bridge.execute_automatic_task.assert_called_once_with(
            "Auto context test", ["/auto/lookup/path.py"]  # Auto-found path used
        )
    
    def test_task_auto_context_skipped_when_disabled(self, app_instance):
        """Test that automatic context lookup is skipped when fresh_context is disabled."""
        # Arrange: Template has fresh_context: disabled
        mock_template = {
            "name": "aider:automatic", "type": "aider", "subtype": "automatic",
            "parameters": {"prompt": {}, "file_context": {}},
            "context_management": {"fresh_context": "disabled"}  # Auto disabled
        }
        app_instance.task_system.find_template = MagicMock(return_value=mock_template)
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()

        # Act: Call without explicit context
        from dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="aider:automatic",
            params={"prompt": "No context expected test"},
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert
        assert result["status"] == "COMPLETE"
        app_instance.memory_system.get_relevant_context_for.assert_not_called()  # Auto lookup skipped
        app_instance.aider_bridge.execute_automatic_task.assert_called_once_with(
            "No context expected test", []  # No context files passed
        )
    
    def test_task_use_history_flag(self, app_instance):
        """Test that --use-history flag passes history to context generation."""
        # Arrange: Template with auto context enabled
        mock_template = {
            "name": "aider:automatic", "type": "aider", "subtype": "automatic",
            "parameters": {"prompt": {}, "file_context": {}},
            "context_management": {"fresh_context": "enabled"}  # Auto enabled
        }
        app_instance.task_system.find_template = MagicMock(return_value=mock_template)
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        
        # Mock context result
        mock_context_result = AssociativeMatchResult(
            context="Found relevant files with history",
            matches=[("/history/context/path.py", "History-aware file", 0.9)]
        )
        app_instance.memory_system.get_relevant_context_for.return_value = mock_context_result

        # Act: Call with --use-history flag
        from dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="aider:automatic",
            params={"prompt": "History context test"},  # No file_context
            flags={"use-history": True},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system,
            optional_history_str="User: What files handle task execution?\nAssistant: The dispatcher.py file."
        )

        # Assert
        assert result["status"] == "COMPLETE"
        
        # Verify history was passed to context generation
        context_input_arg = app_instance.memory_system.get_relevant_context_for.call_args[0][0]
        assert isinstance(context_input_arg, ContextGenerationInput)
        assert context_input_arg.history_context is not None
        assert "User: What files handle task execution?" in context_input_arg.history_context
        
        app_instance.aider_bridge.execute_automatic_task.assert_called_once_with(
            "History context test", ["/history/context/path.py"]  # History-aware path used
        )
    
    def test_task_use_history_with_explicit_context(self, app_instance):
        """Test that --use-history works with explicit file_context (history passed but lookup skipped)."""
        # Arrange
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()

        # Act: Call with --use-history flag AND explicit file_context
        from dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="aider:automatic",
            params={"prompt": "History with explicit context", "file_context": '["/explicit/path.py"]'},
            flags={"use-history": True},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system,
            optional_history_str="User: What files handle task execution?\nAssistant: The dispatcher.py file."
        )

        # Assert
        assert result["status"] == "COMPLETE"
        app_instance.memory_system.get_relevant_context_for.assert_not_called()  # Auto lookup skipped
        app_instance.aider_bridge.execute_automatic_task.assert_called_once_with(
            "History with explicit context", ["/explicit/path.py"]  # Explicit path used
        )
    
    def test_task_help_flag(self, app_instance):
        """Test that --help flag displays template parameter information."""
        # Arrange: Template with detailed parameters
        mock_template = {
            "name": "aider:automatic", "type": "aider", "subtype": "automatic",
            "description": "Execute Aider in automatic mode",
            "parameters": {
                "prompt": {
                    "type": "string", 
                    "description": "Task description", 
                    "required": True
                },
                "file_context": {
                    "type": "array", 
                    "description": "Files to include", 
                    "required": False
                }
            }
        }
        app_instance.task_system.find_template = MagicMock(return_value=mock_template)
        
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Create REPL instance with the mocked app
        from repl.repl import Repl
        repl = Repl(app_instance, output_stream=captured_output)
        
        # Execute task command with --help
        repl._cmd_task('aider:automatic --help')
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        # Verify output contains help information
        output = captured_output.getvalue()
        assert "Help for 'aider:automatic'" in output
        assert "Description: Execute Aider in automatic mode" in output
        assert "prompt (type: string): Task description (required)" in output
        assert "file_context (type: array): Files to include (optional)" in output
    
    def test_task_parameter_parsing_complex_json(self, app_instance):
        """Test parsing of complex JSON parameters."""
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Create REPL instance with the mocked app
        from repl.repl import Repl
        repl = Repl(app_instance, output_stream=captured_output)
        
        # Execute task command with complex JSON
        complex_command = 'aider:automatic prompt="Complex JSON test" config=\'{"nested": {"value": 42}, "array": [1, 2, 3]}\''
        repl._cmd_task(complex_command)
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        # Verify the correct parameters were parsed
        app_instance.aider_bridge.execute_automatic_task.assert_called_once()
        call_args = app_instance.aider_bridge.execute_automatic_task.call_args[0]
        assert call_args[0] == "Complex JSON test"  # prompt
        
        # Check that the config parameter was correctly passed to the tool executor
        # This is more complex to verify since we're mocking at a higher level
        # We'd need to inspect what was passed to the lambda in direct_tool_executors
        
        # Verify output contains success message
        output = captured_output.getvalue()
        assert "Status: COMPLETE" in output
    
    def test_task_error_handling_invalid_json(self, app_instance):
        """Test error handling for invalid JSON parameters."""
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Create REPL instance with the mocked app
        from repl.repl import Repl
        repl = Repl(app_instance, output_stream=captured_output)
        
        # Execute task command with invalid JSON
        invalid_command = 'aider:automatic prompt="Invalid JSON" file_context=\'["unclosed_array"\''
        repl._cmd_task(invalid_command)
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        # Verify output contains error message
        output = captured_output.getvalue()
        assert "Error" in output
        assert "JSON" in output
    
    def test_task_error_handling_template_not_found(self, app_instance):
        """Test error handling when template is not found."""
        # Arrange: Template not found
        app_instance.task_system.find_template = MagicMock(return_value=None)
        
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Create REPL instance with the mocked app
        from repl.repl import Repl
        repl = Repl(app_instance, output_stream=captured_output)
        
        # Execute task command with non-existent template
        repl._cmd_task('nonexistent:template prompt="This should fail"')
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        # Verify output contains error message
        output = captured_output.getvalue()
        assert "Error" in output or "FAILED" in output
        assert "not found" in output.lower()
    
    def test_task_error_handling_executor_exception(self, app_instance):
        """Test error handling when executor raises an exception."""
        # Arrange: Executor raises exception
        app_instance.aider_bridge.execute_automatic_task.side_effect = Exception("Simulated executor error")
        
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Create REPL instance with the mocked app
        from repl.repl import Repl
        repl = Repl(app_instance, output_stream=captured_output)
        
        # Execute task command that will cause an exception
        repl._cmd_task('aider:automatic prompt="This should cause an error"')
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        # Verify output contains error message
        output = captured_output.getvalue()
        assert "Error" in output or "FAILED" in output
        assert "Simulated executor error" in output
    
    def test_task_template_precedence_over_direct_tool(self, app_instance):
        """Test that templates take precedence over direct tools with the same name."""
        # Arrange: Same identifier exists as both template and direct tool
        mock_template = {
            "name": "duplicate:identifier", 
            "type": "duplicate", 
            "subtype": "identifier",
            "description": "Template version"
        }
        app_instance.task_system.find_template = MagicMock(return_value=mock_template)
        app_instance.task_system.execute_subtask_directly.reset_mock()
        
        # Add a direct tool with the same name
        direct_tool_mock = MagicMock(return_value={"status": "COMPLETE", "content": "Direct tool executed"})
        app_instance.passthrough_handler.direct_tool_executors["duplicate:identifier"] = direct_tool_mock
        
        # Act: Call with the duplicate identifier
        from dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="duplicate:identifier",
            params={"test": "value"},
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert: Template was used, not direct tool
        assert result["status"] == "COMPLETE"
        app_instance.task_system.execute_subtask_directly.assert_called_once()
        direct_tool_mock.assert_not_called()
