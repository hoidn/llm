"""Integration tests for the /task command functionality."""
import pytest
import json
import io
import sys
from unittest.mock import patch, MagicMock, ANY, call

# Import REAL TaskSystem and its dependencies/types
from src.task_system.task_system import TaskSystem
from src.memory.memory_system import MemorySystem
from src.handler.passthrough_handler import PassthroughHandler # Or BaseHandler
from src.aider_bridge.bridge import AiderBridge
from src.evaluator.evaluator import Evaluator # Assuming this path
from src.memory.context_generation import ContextGenerationInput, AssociativeMatchResult
from src.task_system.ast_nodes import SubtaskRequest

@pytest.fixture
def app_instance():
    """Create an application instance with a REAL TaskSystem and mocked dependencies."""
    # Mock external dependencies deeply
    with patch('src.aider_bridge.bridge.AiderBridge') as MockAiderBridge, \
         patch('src.handler.passthrough_handler.PassthroughHandler') as MockHandler, \
         patch('src.memory.memory_system.MemorySystem') as MockMemorySystem, \
         patch('src.evaluator.evaluator.Evaluator') as MockEvaluator: # Mock Evaluator

        # Configure mock instances
        mock_aider_bridge_instance = MockAiderBridge.return_value
        mock_handler_instance = MockHandler.return_value
        mock_memory_system_instance = MockMemorySystem.return_value
        mock_evaluator_instance = MockEvaluator.return_value # Get mock evaluator instance

        # Configure mock MemorySystem methods
        mock_context_result = AssociativeMatchResult(
            context="Found relevant files",
            # Use 2-tuples (path, relevance) as expected by TaskSystem fix
            matches=[("/auto/lookup/path.py", "Auto found file"),
                     ("/history/context/path.py", "History-aware file")]
        )
        mock_memory_system_instance.get_relevant_context_for.return_value = mock_context_result

        # Configure mock AiderBridge methods
        mock_aider_bridge_instance.execute_automatic_task.return_value = {
            "status": "COMPLETE", "content": "Mock Aider Auto Result", "notes": {}
        }
        mock_aider_bridge_instance.start_interactive_session.return_value = {
            "status": "COMPLETE",
            "content": "Interactive session completed",
            "notes": {"session_summary": "Made changes to file1.py"}
        }
        # ... configure other mock bridge methods if needed ...

        # Configure mock Handler methods/attributes
        mock_handler_instance.direct_tool_executors = {}
        mock_handler_instance.registerDirectTool = lambda name, func: mock_handler_instance.direct_tool_executors.update({name: func})
        # Mock history retrieval for tests needing it
        mock_handler_instance.get_recent_history_as_string = MagicMock(return_value="Mock History String")

        # ---> Instantiate REAL TaskSystem <---
        # Pass the mock evaluator instance to the real TaskSystem constructor
        real_task_system = TaskSystem(evaluator=mock_evaluator_instance)
        # Inject the mock memory system
        real_task_system.memory_system = mock_memory_system_instance
        # Mock the internal call to execute_task to isolate execute_subtask_directly logic
        real_task_system.execute_task = MagicMock(return_value={
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result",
             "notes": {}
        })
        # Ensure find_template is also mocked on the real instance
        real_task_system.find_template = MagicMock(return_value=None) # Default to None

        # Create a class to simulate the Application structure
        class MockApp:
            def __init__(self):
                self.aider_bridge = mock_aider_bridge_instance
                self.passthrough_handler = mock_handler_instance
                self.task_system = real_task_system # <-- Use REAL TaskSystem instance
                self.memory_system = mock_memory_system_instance

        app = MockApp()

        # Register Aider Executors as Direct Tools (using real bridge mock)
        # Import here to avoid potential circular dependencies at module level
        from src.executors.aider_executors import execute_aider_automatic, execute_aider_interactive
        app.passthrough_handler.registerDirectTool(
            "aider:automatic",
             lambda params: execute_aider_automatic(params, app.aider_bridge)
        )
        app.passthrough_handler.registerDirectTool(
            "aider:interactive",
             lambda params: execute_aider_interactive(params, app.aider_bridge)
        )
        # ... register other tools ...

        yield app # Provide the configured app instance


class TestTaskCommandIntegration:
    """Integration tests for the /task command functionality."""
    
    def test_task_aider_auto_simple(self, app_instance):
        """Test basic aider:automatic task execution."""
        # ---> START ADDED CODE <---
        # Reset mocks on the real TaskSystem instance for isolation
        app_instance.task_system.find_template.reset_mock(return_value=None) # Reset and set default return
        app_instance.task_system.execute_task.reset_mock(return_value={ # Reset and set default return
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result",
             "notes": {}
        })
        app_instance.aider_bridge.execute_automatic_task.reset_mock() # Reset other relevant mocks
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        # ---> END ADDED CODE <---

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
        assert "Mock Aider Auto Result" in output
        
        # Verify the correct method was called with correct parameters
        app_instance.aider_bridge.execute_automatic_task.assert_called_once_with(
            "Add docstrings", ["src/main.py"]
        )
    
    def test_task_context_precedence_explicit_wins(self, app_instance):
        """Test that explicit file_context takes precedence over template and auto context."""
        # Arrange: No template override - use fixture's default (find_template returns None)
        # This ensures we test the direct tool path with explicit context
        # ---> START ADDED CODE <---
        # Reset mocks on the real TaskSystem instance for isolation
        app_instance.task_system.find_template.reset_mock(return_value=None)
        app_instance.task_system.execute_task.reset_mock(return_value={
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result",
             "notes": {}
        })
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        # ---> END ADDED CODE <---
        # DELETE THIS LINE: app_instance.task_system.execute_subtask_directly.reset_mock()

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
        # ---> START ADDED CODE <---
        app_instance.task_system.find_template.reset_mock(return_value=None)
        app_instance.task_system.execute_task.reset_mock(return_value={
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result", # Default mock result
             "notes": {}
        })
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        # ---> END ADDED CODE <---

        # Arrange: Template has explicit path, auto enabled, no request path
        mock_template = {
            "name": "aider:automatic", "type": "aider", "subtype": "automatic",
            "parameters": {"prompt": {}, "file_context": {}},
            "file_paths": ["/template/path.py"],  # Template explicit path
            "context_management": {"fresh_context": "enabled"}  # Auto enabled
        }
        # Override the default None return value for this specific test
        app_instance.task_system.find_template.return_value = mock_template # Set return value on the mock
        # DELETE THIS BLOCK: app_instance.task_system.execute_subtask_directly.return_value = { ... }
        # We now rely on the mocked execute_task *inside* the real execute_subtask_directly

        # Act: Call *without* explicit file_context param
        from dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="aider:automatic",
            params={"prompt": "Template context test"},  # No file_context
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert: Check that TaskSystem path was taken
        assert result["status"] == "COMPLETE"
        # Verify TaskSystem's internal execute_task was called (via dispatcher -> execute_subtask_directly)
        app_instance.task_system.execute_task.assert_called_once()
        # Verify the arguments passed to the internal execute_task
        execute_task_call_args = app_instance.task_system.execute_task.call_args
        assert execute_task_call_args.kwargs['task_type'] == "aider"
        assert execute_task_call_args.kwargs['task_subtype'] == "automatic"
        assert execute_task_call_args.kwargs['inputs'] == {"prompt": "Template context test"}
        # Check the file context determined by execute_subtask_directly (using template path)
        handler_config = execute_task_call_args.kwargs.get('handler_config', {})
        assert handler_config.get('file_context') == ["/template/path.py"] # Template path used

        # Verify AiderBridge was NOT called directly by the dispatcher
        app_instance.aider_bridge.execute_automatic_task.assert_not_called()
        # Check the content returned by the mocked TaskSystem.execute_task method
        assert "Mock TaskSystem.execute_task Result" in result["content"]
        # Check notes added by dispatcher/execute_subtask_directly
        assert result["notes"]["context_source"] == "template_defined"
        assert result["notes"]["context_files_count"] == 1
        assert result["notes"]["template_used"] == "aider:automatic"
    
    def test_task_auto_context_used_when_no_explicit(self, app_instance):
        """Test that automatic context lookup is used when no explicit context is provided."""
        # Arrange: Template has no file_paths, auto enabled
        mock_template = {
            "name": "aider:automatic", "type": "aider", "subtype": "automatic",
            "parameters": {"prompt": {}, "file_context": {}},
            "context_management": {"fresh_context": "enabled"}  # Auto enabled
        }
        # ---> START ADDED CODE <---
        app_instance.task_system.find_template.reset_mock(return_value=None)
        app_instance.task_system.execute_task.reset_mock(return_value={
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result", # Default mock result
             "notes": {}
        })
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        # ---> END ADDED CODE <---

        # Arrange: Template has no file_paths, auto enabled
        mock_template = {
            "name": "aider:automatic", "type": "aider", "subtype": "automatic",
            "parameters": {"prompt": {}, "file_context": {}},
            "context_management": {"fresh_context": "enabled"}  # Auto enabled
        }
        # Override the default None return value for this specific test
        app_instance.task_system.find_template.return_value = mock_template # Set return value on the mock

        # Mock context result for memory system
        mock_context_result = AssociativeMatchResult(
            context="Found relevant files",
            matches=[("/auto/lookup/path.py", "Auto found file", 0.9)]
        )
        app_instance.memory_system.get_relevant_context_for.return_value = mock_context_result
        # DELETE THIS BLOCK: app_instance.task_system.execute_subtask_directly.return_value = { ... }
        # We now rely on the mocked execute_task *inside* the real execute_subtask_directly

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

        # Assert TaskSystem's internal execute_task was called
        app_instance.task_system.execute_task.assert_called_once()
        # Verify AiderBridge was NOT called directly by the dispatcher
        app_instance.aider_bridge.execute_automatic_task.assert_not_called()

        # Verify the arguments passed to the internal execute_task
        execute_task_call_args = app_instance.task_system.execute_task.call_args
        assert execute_task_call_args.kwargs['task_type'] == "aider"
        assert execute_task_call_args.kwargs['task_subtype'] == "automatic"
        assert execute_task_call_args.kwargs['inputs'] == {"prompt": "Auto context test"}
        # Check the file context determined by execute_subtask_directly (using auto lookup)
        handler_config = execute_task_call_args.kwargs.get('handler_config', {})
        assert handler_config.get('file_context') == ["/auto/lookup/path.py"] # Auto path used

        # Verify the final result content (comes from the mocked TaskSystem.execute_task method)
        assert "Mock TaskSystem.execute_task Result" in result["content"]
        # Check notes added by dispatcher/execute_subtask_directly
        assert result["notes"]["context_source"] == "automatic_lookup"
        assert result["notes"]["context_files_count"] == 1 # Matches mock memory result
        assert result["notes"]["template_used"] == "aider:automatic"
    
    def test_task_auto_context_skipped_when_disabled(self, app_instance):
        """Test that automatic context lookup is skipped when fresh_context is disabled."""
        # Arrange: Template has fresh_context: disabled
        mock_template = {
            "name": "aider:automatic", "type": "aider", "subtype": "automatic",
            "parameters": {"prompt": {}, "file_context": {}},
            "context_management": {"fresh_context": "disabled"}  # Auto disabled
        }
        # ---> START ADDED CODE <---
        app_instance.task_system.find_template.reset_mock(return_value=None)
        app_instance.task_system.execute_task.reset_mock(return_value={
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result", # Default mock result
             "notes": {}
        })
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        # ---> END ADDED CODE <---

        # Arrange: Template has fresh_context: disabled
        mock_template = {
            "name": "aider:automatic", "type": "aider", "subtype": "automatic",
            "parameters": {"prompt": {}, "file_context": {}},
            "context_management": {"fresh_context": "disabled"}  # Auto disabled
        }
        # Override the default None return value for this specific test
        app_instance.task_system.find_template.return_value = mock_template # Set return value on the mock
        # DELETE THIS LINE: app_instance.task_system.execute_subtask_directly.reset_mock()
        # DELETE THIS BLOCK: app_instance.task_system.execute_subtask_directly.return_value = { ... }

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
        # Assert TaskSystem's internal execute_task was called
        app_instance.task_system.execute_task.assert_called_once()
        # Verify AiderBridge was NOT called directly by the dispatcher
        app_instance.aider_bridge.execute_automatic_task.assert_not_called()
        # Verify MemorySystem was NOT called for context lookup
        app_instance.memory_system.get_relevant_context_for.assert_not_called()

        # Verify the arguments passed to the internal execute_task
        execute_task_call_args = app_instance.task_system.execute_task.call_args
        assert execute_task_call_args.kwargs['task_type'] == "aider"
        assert execute_task_call_args.kwargs['task_subtype'] == "automatic"
        assert execute_task_call_args.kwargs['inputs'] == {"prompt": "No context expected test"}
        # Check the file context determined by execute_subtask_directly (should be empty)
        handler_config = execute_task_call_args.kwargs.get('handler_config', {})
        assert handler_config.get('file_context') == [] # No context files determined

        # Verify the final result content (comes from the mocked TaskSystem.execute_task method)
        assert "Mock TaskSystem.execute_task Result" in result["content"]
        # Check notes added by dispatcher/execute_subtask_directly
        assert result["notes"]["context_source"] == "none"
        assert result["notes"]["context_files_count"] == 0
        assert result["notes"]["template_used"] == "aider:automatic"
    
    def test_task_use_history_flag(self, app_instance):
        """Test that --use-history flag passes history to context generation."""
        # Arrange: Template with auto context enabled
        mock_template = {
            "name": "aider:automatic", "type": "aider", "subtype": "automatic",
            "parameters": {"prompt": {}, "file_context": {}},
            "context_management": {"fresh_context": "enabled"}  # Auto enabled
        }
        # Override the default None return value for this specific test
        app_instance.task_system.find_template = MagicMock(return_value=mock_template)
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        
        # ---> START ADDED CODE <---
        app_instance.task_system.find_template.reset_mock(return_value=None)
        app_instance.task_system.execute_task.reset_mock(return_value={
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result", # Default mock result
             "notes": {}
        })
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        # ---> END ADDED CODE <---

        # Arrange: Template with auto context enabled
        mock_template = {
            "name": "aider:automatic", "type": "aider", "subtype": "automatic",
            "parameters": {"prompt": {}, "file_context": {}},
            "context_management": {"fresh_context": "enabled"}  # Auto enabled
        }
        # Override the default None return value for this specific test
        app_instance.task_system.find_template.return_value = mock_template # Set return value on the mock
        app_instance.memory_system.get_relevant_context_for.reset_mock() # Already reset above, but safe to repeat
        app_instance.aider_bridge.execute_automatic_task.reset_mock() # Already reset above, but safe to repeat

        # Mock context result for memory system
        mock_context_result = AssociativeMatchResult(
            context="Found relevant files with history",
            # Use 2-tuples (path, relevance) as expected by TaskSystem fix
            matches=[("/auto/lookup/path.py", "Auto found file"), # Keep original mock paths
                     ("/history/context/path.py", "History-aware file")]
        )
        app_instance.memory_system.get_relevant_context_for.return_value = mock_context_result
        # DELETE THIS BLOCK: app_instance.task_system.execute_subtask_directly.return_value = { ... }

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

        # Assert TaskSystem's execute_subtask_directly was called (via dispatcher)
        # We can't directly assert on execute_subtask_directly anymore as it's the real method.
        # Instead, we assert that the *mocked* execute_task inside it was called.
        app_instance.task_system.execute_task.assert_called_once()

        # Verify AiderBridge was NOT called directly by the dispatcher
        app_instance.aider_bridge.execute_automatic_task.assert_not_called()

        # Verify MemorySystem WAS called for context lookup
        app_instance.memory_system.get_relevant_context_for.assert_called_once()
        # Verify history was passed to context generation
        context_input_arg = app_instance.memory_system.get_relevant_context_for.call_args[0][0]
        assert isinstance(context_input_arg, ContextGenerationInput)
        # Check query derivation (should use the 'prompt' from params)
        assert context_input_arg.template_description == "History context test"
        assert context_input_arg.history_context is not None
        assert "User: What files handle task execution?" in context_input_arg.history_context

        # Verify the SubtaskRequest passed to the *mocked* execute_task contained the history-aware paths
        # The call to execute_task happens *inside* execute_subtask_directly
        execute_task_call_args = app_instance.task_system.execute_task.call_args
        # Check keyword arguments passed to execute_task
        assert execute_task_call_args.kwargs['task_type'] == "aider"
        assert execute_task_call_args.kwargs['task_subtype'] == "automatic"
        assert execute_task_call_args.kwargs['inputs'] == {"prompt": "History context test"}
        # Check the file context determined by execute_subtask_directly and passed via handler_config
        handler_config = execute_task_call_args.kwargs.get('handler_config', {})
        # The file_paths should reflect the result of the memory system lookup
        assert handler_config.get('file_context') == ["/auto/lookup/path.py", "/history/context/path.py"] # Check paths from mock AssociativeMatchResult

        # ---> START MODIFIED ASSERTIONS <---
        # Verify the final result content (comes from the mocked TaskSystem.execute_task)
        assert "Mock TaskSystem.execute_task Result" in result["content"]
        # Verify notes added by execute_subtask_directly
        assert result["notes"]["context_source"] == "automatic_lookup"
        assert result["notes"]["context_files_count"] == 2 # Matches count from mock memory result
        assert result["notes"]["template_used"] == "aider:automatic" # Check template name was added
        # ---> END MODIFIED ASSERTIONS <---
    
    def test_task_use_history_with_explicit_context(self, app_instance):
        """Test that --use-history works with explicit file_context (history passed but lookup skipped)."""
        # ---> START ADDED CODE <---
        app_instance.task_system.find_template.reset_mock(return_value=None)
        app_instance.task_system.execute_task.reset_mock(return_value={
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result",
             "notes": {}
        })
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        # ---> END ADDED CODE <---

        # Arrange (No specific template needed, testing direct tool path)

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
        # ---> START ADDED CODE <---
        app_instance.task_system.find_template.reset_mock(return_value=None)
        app_instance.task_system.execute_task.reset_mock(return_value={
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result",
             "notes": {}
        })
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        # ---> END ADDED CODE <---

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
        # Override the default None return value for this specific test
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
        # ---> START ADDED CODE <---
        app_instance.task_system.find_template.reset_mock(return_value=None)
        app_instance.task_system.execute_task.reset_mock(return_value={
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result",
             "notes": {}
        })
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        # ---> END ADDED CODE <---

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
        # ---> START ADDED CODE <---
        app_instance.task_system.find_template.reset_mock(return_value=None)
        app_instance.task_system.execute_task.reset_mock(return_value={
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result",
             "notes": {}
        })
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        # ---> END ADDED CODE <---

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
        # ---> START ADDED CODE <---
        app_instance.task_system.find_template.reset_mock(return_value=None)
        app_instance.task_system.execute_task.reset_mock(return_value={
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result",
             "notes": {}
        })
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        # ---> END ADDED CODE <---

        # Arrange: Template not found (already handled by reset_mock above)
        # app_instance.task_system.find_template = MagicMock(return_value=None) # No longer needed

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
        # ---> START ADDED CODE <---
        app_instance.task_system.find_template.reset_mock(return_value=None)
        app_instance.task_system.execute_task.reset_mock(return_value={
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result",
             "notes": {}
        })
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        # ---> END ADDED CODE <---

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
        # ---> START ADDED CODE <---
        app_instance.task_system.find_template.reset_mock(return_value=None)
        app_instance.task_system.execute_task.reset_mock(return_value={
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result", # Default mock result
             "notes": {}
        })
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        # ---> END ADDED CODE <---

        # Arrange: Set find_template to return the mock template for this test
        app_instance.task_system.find_template.return_value = mock_template
        # DELETE THIS LINE: app_instance.task_system.execute_subtask_directly.reset_mock()
        # DELETE THIS BLOCK: app_instance.task_system.execute_subtask_directly.return_value = { ... }

        # Add a direct tool with the same name
        direct_tool_mock = MagicMock(return_value={"status": "COMPLETE", "content": "Direct tool executed"})
        app_instance.passthrough_handler.direct_tool_executors["duplicate:identifier"] = direct_tool_mock
        app_instance.passthrough_handler.direct_tool_executors["duplicate:identifier"].reset_mock() # Reset this mock too
        
        # Act: Call with the duplicate identifier
        from dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="duplicate:identifier",
            params={"test": "value"},
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert: Template was used (TaskSystem.execute_task was called), not direct tool
        assert result["status"] == "COMPLETE"
        app_instance.task_system.execute_task.assert_called_once() # Check internal mock call
        direct_tool_mock.assert_not_called() # Check direct tool mock was not called
        assert "Mock TaskSystem.execute_task Result" in result["content"] # Check content from internal mock
        assert result["notes"]["template_used"] == "duplicate:identifier" # Check notes
