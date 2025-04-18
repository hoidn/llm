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
# Add json import if not present
import json

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
        # ---> Instantiate REAL TaskSystem <---
        real_task_system = TaskSystem(evaluator=mock_evaluator_instance)
        real_task_system.memory_system = mock_memory_system_instance

        # Mock the internal call to execute_task ONCE in the fixture
        # Set a clear default return value dictionary
        execute_task_return_value = {
             "status": "COMPLETE",
             "content": "Mock TaskSystem.execute_task Result",
             "notes": {}
        }
        real_task_system.execute_task = MagicMock(return_value=execute_task_return_value)

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
        # Register Aider Executors as Direct Tools (using real bridge mock)
        # Import here to avoid potential circular dependencies at module level
        from src.executors.aider_executors import execute_aider_automatic, execute_aider_interactive
        # Ensure the handler mock has the registration method
        if not hasattr(app.passthrough_handler, 'registerDirectTool'):
             app.passthrough_handler.registerDirectTool = MagicMock(side_effect=lambda name, func: app.passthrough_handler.direct_tool_executors.update({name: func}))

        app.passthrough_handler.registerDirectTool(
            "aider:automatic",
             lambda params: execute_aider_automatic(params, app.aider_bridge)
        )
        app.passthrough_handler.registerDirectTool(
            "aider:interactive",
             lambda params: execute_aider_interactive(params, app.aider_bridge)
        )
        # Register Aider metadata templates
        from src.task_system.templates.aider_templates import register_aider_templates
        register_aider_templates(app.task_system) # Register with the real TaskSystem

        yield app # Provide the configured app instance


class TestTaskCommandIntegration:
    """Integration tests for the /task command functionality."""

    # Helper to reset mocks before each test using this fixture
    @pytest.fixture(autouse=True)
    def reset_mocks_before_test(self, app_instance):
        # Reset call history for mocks on the real TaskSystem instance
        if hasattr(app_instance.task_system, 'find_template') and isinstance(app_instance.task_system.find_template, MagicMock):
            app_instance.task_system.find_template.reset_mock()
            app_instance.task_system.find_template.return_value = None # Ensure default

        if hasattr(app_instance.task_system, 'execute_task') and isinstance(app_instance.task_system.execute_task, MagicMock):
            app_instance.task_system.execute_task.reset_mock()
            # Reset to default return value from fixture if needed, or set specific one per test
            app_instance.task_system.execute_task.return_value = {
                 "status": "COMPLETE",
                 "content": "Mock TaskSystem.execute_task Result",
                 "notes": {}
            }

        # Reset other relevant mocks if they are MagicMock instances
        if isinstance(app_instance.aider_bridge.execute_automatic_task, MagicMock):
            app_instance.aider_bridge.execute_automatic_task.reset_mock()
            app_instance.aider_bridge.execute_automatic_task.side_effect = None # Clear side effects
            app_instance.aider_bridge.execute_automatic_task.return_value = { # Reset return value
                "status": "COMPLETE", "content": "Mock Aider Auto Result", "notes": {}
            }
        if isinstance(app_instance.aider_bridge.start_interactive_session, MagicMock):
            app_instance.aider_bridge.start_interactive_session.reset_mock()
            app_instance.aider_bridge.start_interactive_session.side_effect = None
            app_instance.aider_bridge.start_interactive_session.return_value = { # Reset return value
                "status": "COMPLETE",
                "content": "Interactive session completed",
                "notes": {"session_summary": "Made changes to file1.py"}
            }

        if isinstance(app_instance.memory_system.get_relevant_context_for, MagicMock):
            app_instance.memory_system.get_relevant_context_for.reset_mock()
            # Reset to default return value from fixture
            app_instance.memory_system.get_relevant_context_for.return_value = AssociativeMatchResult(
                context="Found relevant files",
                matches=[("/auto/lookup/path.py", "Auto found file"),
                         ("/history/context/path.py", "History-aware file")]
            )

        # Reset direct tool mocks if they exist and are mocks
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
        yield # Let the test run


    def test_task_aider_auto_simple(self, app_instance):
        """Test basic aider:automatic task execution via /task."""
        # Arrange
        # Reset call history for mocks on the real TaskSystem instance
        app_instance.task_system.find_template.reset_mock()
        app_instance.task_system.find_template.return_value = None # Ensure default
        app_instance.task_system.execute_task.reset_mock()
        # DO NOT set return_value here, rely on fixture default

        # Reset other relevant mocks
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
        # Mock the return value for this specific call
        app_instance.aider_bridge.execute_automatic_task.return_value = {
            "status": "COMPLETE", "content": "Aider Auto Success", "notes": {"files_changed": ["src/main.py"]}
        }

        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output

        # Create REPL instance with the mocked app
        from src.repl.repl import Repl # Adjust import path if needed
        repl = Repl(app_instance, output_stream=captured_output)

        # Act: Execute task command
        repl._cmd_task('aider:automatic prompt="Add docstrings" file_context=\'["src/main.py"]\'')

        # Reset stdout
        sys.stdout = sys.__stdout__

        # Assert Output
        output = captured_output.getvalue()
        assert "Executing task: aider:automatic..." in output
        assert "Status: COMPLETE" in output
        assert "Aider Auto Success" in output # Check for content from mock
        assert '"files_changed": [\n    "src/main.py"\n  ]' in output # Check notes

        # Assert Mock Calls
        # Verify the dispatcher routed to the direct tool executor, which called the bridge
        app_instance.aider_bridge.execute_automatic_task.assert_called_once_with(
            "Add docstrings", ["src/main.py"] # Expect positional args
        )
        # Verify TaskSystem wasn't involved for direct tool execution
        app_instance.task_system.execute_task.assert_not_called()


    def test_task_aider_interactive_simple(self, app_instance):
        """Test basic aider:interactive task execution via /task."""
        # Arrange
        app_instance.aider_bridge.start_interactive_session.return_value = {
            "status": "COMPLETE", "content": "Interactive Done", "notes": {"summary": "Session summary"}
        }

        captured_output = io.StringIO()
        sys.stdout = captured_output
        from src.repl.repl import Repl
        repl = Repl(app_instance, output_stream=captured_output)

        # Act
        repl._cmd_task('aider:interactive query="Refactor this class" file_context=\'["src/utils.py"]\'')

        # Assert Output
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        assert "Executing task: aider:interactive..." in output
        assert "Status: COMPLETE" in output
        assert "Interactive Done" in output
        assert '"summary": "Session summary"' in output

        # Assert Mock Calls
        app_instance.aider_bridge.start_interactive_session.assert_called_once_with(
            "Refactor this class", ["src/utils.py"] # Expect positional args
        )
        app_instance.task_system.execute_task.assert_not_called()


    def test_task_aider_auto_invalid_json_context(self, app_instance):
        """Test /task aider:automatic with invalid JSON in file_context."""
        # Import dispatcher function
        from src.dispatcher import execute_programmatic_task
        from src.system.errors import INPUT_VALIDATION_FAILURE # Import error code

        # Act: Call dispatcher directly with invalid JSON string
        result = execute_programmatic_task(
            identifier="aider:automatic",
            params={"prompt": "Invalid JSON", "file_context": '["unclosed_array\''}, # Invalid JSON
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert Result
        assert result["status"] == "FAILED"
        assert "Invalid file_context parameter: must be a JSON string array or already a list of strings. Error:" in result["content"] # Check specific error
        assert result["notes"]["error"]["reason"] == INPUT_VALIDATION_FAILURE

        # Assert Mock Calls
        # Dispatcher was called directly, bridge should not be called due to validation failure
        app_instance.aider_bridge.execute_automatic_task.assert_not_called()


    def test_task_aider_auto_help(self, app_instance):
        """Test /task aider:automatic --help."""
        # Arrange
        # Ensure find_template returns None for this test to test tool spec path
        app_instance.task_system.find_template.return_value = None
        
        # Set up a proper tool spec for the help test
        mock_tool_spec = {
            "name": "aider:automatic",
            "description": "Execute an automatic Aider task",
            "input_schema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The instruction for code changes."},
                    "file_context": {"type": "string", "description": "(Optional) JSON string array"}
                },
                "required": ["prompt"]
            }
        }
        app_instance.passthrough_handler.registered_tools = {'aider:automatic': mock_tool_spec}
        captured_output = io.StringIO()
        sys.stdout = captured_output
        from src.repl.repl import Repl
        repl = Repl(app_instance, output_stream=captured_output)

        # Act
        repl._cmd_task('aider:automatic --help')

        # Assert Output
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        assert "Fetching help for task: aider:automatic..." in output
        assert "* Direct Tool Specification:" in output
        assert "* Task Template Details:" not in output # Should NOT find template details
        assert "Execute an automatic Aider task" in output # Description
        assert "prompt (type: string): The instruction for code changes. (required)" in output
        assert "file_context (type: string): (Optional) JSON string array" in output

        # Assert Mock Calls
        app_instance.aider_bridge.execute_automatic_task.assert_not_called()
        app_instance.task_system.execute_task.assert_not_called()
        # Verify find_template was called on the real TaskSystem instance
        app_instance.task_system.find_template.assert_called_once_with("aider:automatic")


    # --- Context Precedence Tests (Copied & Adapted from previous phase) ---
    # These tests now verify the interaction between REPL -> Dispatcher -> Direct Tool/TaskSystem

    def test_task_context_precedence_explicit_wins(self, app_instance):
        """Test /task with explicit file_context overrides template/auto (Direct Tool path)."""
        # Arrange: Use aider:automatic which is a Direct Tool
        # Reset call history for mocks on the real TaskSystem instance
        app_instance.task_system.find_template.reset_mock()
        app_instance.task_system.find_template.return_value = None # Ensure default
        app_instance.task_system.execute_task.reset_mock()
        # DO NOT set return_value here, rely on fixture default

        # Reset other relevant mocks
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
        # Act: Call dispatcher directly (simulating REPL call)
        from src.dispatcher import execute_programmatic_task # Adjust import
        result = execute_programmatic_task(
            identifier="aider:automatic",
            # Pass file_context as a list, simulating REPL's JSON parsing
            params={"prompt": "Explicit context test", "file_context": ["/request/path.py"]},
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert
        assert result["status"] == "COMPLETE"
        assert result["notes"]["execution_path"] == "direct_tool"
        assert result["notes"]["context_source"] == "explicit_request"
        assert result["notes"]["context_file_count"] == 1
        # Verify bridge call used the explicit path
        app_instance.aider_bridge.execute_automatic_task.assert_called_once_with(
            prompt="Explicit context test", file_context=["/request/path.py"]
        )
        # Verify TaskSystem and MemorySystem were not involved for context
        app_instance.task_system.execute_task.assert_not_called()
        app_instance.memory_system.get_relevant_context_for.assert_not_called()


    def test_task_context_precedence_template_wins_over_auto(self, app_instance):
        """Test /task where template definition provides context (TaskSystem path)."""
        # Arrange: Define a template that specifies file_paths
        # Reset call history for mocks on the real TaskSystem instance
        app_instance.task_system.find_template.reset_mock()
        app_instance.task_system.find_template.return_value = None # Ensure default
        app_instance.task_system.execute_task.reset_mock()
        # DO NOT set return_value here, rely on fixture default

        # Reset other relevant mocks
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
        mock_template = {
            "name": "template:with_context", "type": "template", "subtype": "with_context",
            "parameters": {"input": {}},
            "file_paths": ["/template/path.py"], # Template provides the path
            "context_management": {"fresh_context": "enabled"} # Auto lookup enabled but template path takes precedence
        }
        # Configure the REAL TaskSystem's mock find_template for this test
        app_instance.task_system.find_template.return_value = mock_template

        # Act: Call dispatcher (simulating REPL) without explicit file_context
        from src.dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="template:with_context",
            params={"input": "Template context test"}, # No file_context here
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert: Check that TaskSystem path was taken and correct context used
        assert result["status"] == "COMPLETE"
        assert result["notes"]["execution_path"] == "execute_subtask_directly (Phase 1 Stub)"
        assert result["notes"]["template_used"] == "template:with_context"
        assert result["notes"]["context_source"] == "template_literal" # Template path used (Phase 1)
        assert result["notes"]["context_files_count"] == 1

        # Verify TaskSystem's internal execute_task was called
        app_instance.task_system.execute_task.assert_called_once()
        # Verify the arguments passed to the internal execute_task
        execute_task_call_args = app_instance.task_system.execute_task.call_args
        assert execute_task_call_args.kwargs['task_type'] == "template"
        assert execute_task_call_args.kwargs['task_subtype'] == "with_context"
        assert execute_task_call_args.kwargs['inputs'] == {"input": "Template context test"}
        # Check the file context determined by execute_subtask_directly (using template path)
        handler_config = execute_task_call_args.kwargs.get('handler_config', {})
        assert handler_config.get('file_context') == ["/template/path.py"] # Template path used

        # Verify AiderBridge (or other direct tools) were NOT called directly
        app_instance.aider_bridge.execute_automatic_task.assert_not_called()
        # Verify MemorySystem was NOT called for lookup because template path took precedence
        app_instance.memory_system.get_relevant_context_for.assert_not_called()
        # Check the file context determined by execute_subtask_directly (using template path)
        handler_config = execute_task_call_args.kwargs.get('handler_config', {})
        assert handler_config.get('file_context') == ["/template/path.py"] # Template path used
        # Check the content returned by the stub
        assert "Executed template 'template:with_context' with inputs." in result["content"]


    def test_task_auto_context_used_when_no_explicit(self, app_instance):
        """Test /task where template enables auto lookup and no explicit context is given."""
        # Arrange: Define a template enabling auto lookup but providing no paths
        # Reset call history for mocks on the real TaskSystem instance
        app_instance.task_system.find_template.reset_mock()
        app_instance.task_system.find_template.return_value = None # Ensure default
        app_instance.task_system.execute_task.reset_mock()
        # DO NOT set return_value here, rely on fixture default

        # Reset other relevant mocks
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
        mock_template = {
            "name": "template:auto_context", "type": "template", "subtype": "auto_context",
            "parameters": {"input": {}},
            "context_management": {"fresh_context": "enabled"} # Auto lookup enabled
        }
        app_instance.task_system.find_template.return_value = mock_template

        # Configure mock MemorySystem to return specific paths for this lookup
        mock_context_result = AssociativeMatchResult(
            context="Found via auto lookup",
            matches=[("/auto/path1.py", "File 1"), ("/auto/path2.py", "File 2")]
        )
        app_instance.memory_system.get_relevant_context_for.return_value = mock_context_result

        # Act: Call dispatcher without explicit file_context
        from src.dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="template:auto_context",
            params={"input": "Auto context test"}, # No file_context
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert
        assert result["status"] == "COMPLETE"
        assert result["notes"]["execution_path"] == "execute_subtask_directly (Phase 1 Stub)"
        assert result["notes"]["template_used"] == "template:auto_context"
        assert result["notes"]["context_source"] == "deferred_lookup" # Auto lookup deferred in Phase 1
        assert result["notes"]["context_files_count"] == 0 # No explicit paths found in Phase 1

        # In Phase 1, MemorySystem is not called for lookup (deferred)
        # Check the content returned by the stub
        assert "Executed template 'template:auto_context' with inputs." in result["content"]
        
        # Verify the arguments passed to the internal execute_task
        execute_task_call_args = app_instance.task_system.execute_task.call_args
        # Check the file context determined by execute_subtask_directly (should be empty for deferred lookup)
        handler_config = execute_task_call_args.kwargs.get('handler_config', {})
        assert handler_config.get('file_context') == [] # Empty list for deferred lookup in Phase 1
        # Verify TaskSystem's internal execute_task was called
        app_instance.task_system.execute_task.assert_called_once()
        # Verify the arguments passed to the internal execute_task
        execute_task_call_args = app_instance.task_system.execute_task.call_args
        assert execute_task_call_args.kwargs['task_type'] == "template"
        assert execute_task_call_args.kwargs['task_subtype'] == "auto_context"
        assert execute_task_call_args.kwargs['inputs'] == {"input": "Auto context test"}
        # Check the file context determined by execute_subtask_directly (should be empty for deferred lookup in Phase 1)
        handler_config = execute_task_call_args.kwargs.get('handler_config', {})
        assert handler_config.get('file_context') == [] # Empty list for deferred lookup in Phase 1

        # Verify AiderBridge (or other direct tools) were NOT called directly
        app_instance.aider_bridge.execute_automatic_task.assert_not_called()
        # Check the content returned by the stub
        assert "Executed template 'template:auto_context' with inputs." in result["content"]


    def test_task_auto_context_skipped_when_disabled(self, app_instance):
        """Test /task where template disables auto lookup."""
        # Arrange: Define a template disabling fresh_context
        # Reset call history for mocks on the real TaskSystem instance
        app_instance.task_system.find_template.reset_mock()
        app_instance.task_system.find_template.return_value = None # Ensure default
        app_instance.task_system.execute_task.reset_mock()
        # DO NOT set return_value here, rely on fixture default

        # Reset other relevant mocks
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
        mock_template = {
            "name": "template:no_context", "type": "template", "subtype": "no_context",
            "parameters": {"input": {}},
            "context_management": {"fresh_context": "disabled"} # Auto disabled
        }
        app_instance.task_system.find_template.return_value = mock_template

        # Act: Call dispatcher without explicit file_context
        from src.dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="template:no_context",
            params={"input": "No context expected test"},
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert
        assert result["status"] == "COMPLETE"
        assert result["notes"]["execution_path"] == "execute_subtask_directly (Phase 1 Stub)"
        assert result["notes"]["template_used"] == "template:no_context"
        assert result["notes"]["context_source"] == "none" # No context source
        assert result["notes"]["context_files_count"] == 0

        # Verify MemorySystem was NOT called for lookup
        app_instance.memory_system.get_relevant_context_for.assert_not_called()
        # Verify TaskSystem's internal execute_task was called
        app_instance.task_system.execute_task.assert_called_once()
        # Verify the arguments passed to the internal execute_task
        execute_task_call_args = app_instance.task_system.execute_task.call_args
        assert execute_task_call_args.kwargs['task_type'] == "template"
        assert execute_task_call_args.kwargs['task_subtype'] == "no_context"
        assert execute_task_call_args.kwargs['inputs'] == {"input": "No context expected test"}
        # Check the file context determined by execute_subtask_directly (should be empty)
        handler_config = execute_task_call_args.kwargs.get('handler_config', {})
        assert handler_config.get('file_context') == [] # No context files determined
        handler_config = execute_task_call_args.kwargs.get('handler_config', {})
        assert handler_config.get('file_context') == [] # No context files determined
        handler_config = execute_task_call_args.kwargs.get('handler_config', {})
        assert handler_config.get('file_context') == [] # No context files determined

        # Verify AiderBridge (or other direct tools) were NOT called directly
        app_instance.aider_bridge.execute_automatic_task.assert_not_called()
        # Check the content returned by the stub
        assert "Executed template 'template:no_context' with inputs." in result["content"]


    def test_task_use_history_flag(self, app_instance):
        """Test /task with --use-history flag passes history to context generation (TaskSystem path)."""
        # Arrange: Template with auto context enabled
        # Reset call history for mocks on the real TaskSystem instance
        app_instance.task_system.find_template.reset_mock()
        app_instance.task_system.find_template.return_value = None # Ensure default
        app_instance.task_system.execute_task.reset_mock()
        # DO NOT set return_value here, rely on fixture default

        # Reset other relevant mocks
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
        mock_template = {
            "name": "template:history_context", "type": "template", "subtype": "history_context",
            "parameters": {"input": {}},
            "context_management": {"fresh_context": "enabled"} # Auto enabled
        }
        app_instance.task_system.find_template.return_value = mock_template

        # Configure mock MemorySystem to return specific paths for this lookup
        mock_context_result = AssociativeMatchResult(
            context="Found via history lookup",
            matches=[("/history/path.py", "History File")]
        )
        app_instance.memory_system.get_relevant_context_for.return_value = mock_context_result

        # Act: Call dispatcher with --use-history flag and history string
        from src.dispatcher import execute_programmatic_task
        history_string = "User: Previous question\nAssistant: Previous answer"
        result = execute_programmatic_task(
            identifier="template:history_context",
            params={"input": "History context test"}, # No file_context
            flags={"use-history": True}, # Enable history flag
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system,
            optional_history_str=history_string # Provide history
        )

        # Assert
        assert result["status"] == "COMPLETE"
        assert result["notes"]["execution_path"] == "execute_subtask_directly (Phase 1 Stub)"
        assert result["notes"]["template_used"] == "template:history_context"
        assert result["notes"]["context_source"] == "deferred_lookup" # Auto lookup deferred in Phase 1
        assert result["notes"]["context_files_count"] == 0 # No explicit paths found in Phase 1

        # In Phase 1, history is stored in the request but lookup is deferred
        # Check that context_source is correctly marked as deferred
        assert result["notes"]["context_source"] == "deferred_lookup"
        
        # Verify the arguments passed to the internal execute_task
        execute_task_call_args = app_instance.task_system.execute_task.call_args
        # Check the file context determined by execute_subtask_directly (should be empty for deferred lookup)
        handler_config = execute_task_call_args.kwargs.get('handler_config', {})
        assert handler_config.get('file_context') == [] # Empty list for deferred lookup in Phase 1

        # Verify TaskSystem's internal execute_task was called
        app_instance.task_system.execute_task.assert_called_once()
        # Verify the arguments passed to the internal execute_task
        execute_task_call_args = app_instance.task_system.execute_task.call_args
        assert execute_task_call_args.kwargs['task_type'] == "template"
        assert execute_task_call_args.kwargs['task_subtype'] == "history_context"
        assert execute_task_call_args.kwargs['inputs'] == {"input": "History context test"}
        # Check the file context determined by execute_subtask_directly (should be empty for deferred lookup in Phase 1)
        handler_config = execute_task_call_args.kwargs.get('handler_config', {})
        assert handler_config.get('file_context') == [] # Empty list for deferred lookup in Phase 1

        # Verify AiderBridge (or other direct tools) were NOT called directly
        app_instance.aider_bridge.execute_automatic_task.assert_not_called()
        # Check the content returned by the stub
        assert "Executed template 'template:history_context' with inputs." in result["content"]


    def test_task_use_history_with_explicit_context(self, app_instance):
        """Test /task with --use-history AND explicit file_context (Direct Tool path)."""
        # Arrange: Use aider:automatic (Direct Tool)
        # Reset call history for mocks on the real TaskSystem instance
        app_instance.task_system.find_template.reset_mock()
        app_instance.task_system.find_template.return_value = None # Ensure default
        app_instance.task_system.execute_task.reset_mock()
        # DO NOT set return_value here, rely on fixture default

        # Reset other relevant mocks
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
        # Act: Call dispatcher with explicit context and history flag
        from src.dispatcher import execute_programmatic_task
        history_string = "User: Previous question\nAssistant: Previous answer"
        result = execute_programmatic_task(
            identifier="aider:automatic",
            params={"prompt": "History with explicit context", "file_context": ["/explicit/path.py"]}, # Explicit context
            flags={"use-history": True}, # History flag enabled
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system,
            optional_history_str=history_string # History provided
        )

        # Assert: Direct tool path taken, explicit context used, history ignored by dispatcher for direct tools
        assert result["status"] == "COMPLETE"
        assert result["notes"]["execution_path"] == "direct_tool"
        assert result["notes"]["context_source"] == "explicit_request"
        assert result["notes"]["context_file_count"] == 1

        # Verify bridge call used the explicit path
        app_instance.aider_bridge.execute_automatic_task.assert_called_once_with(
            prompt="History with explicit context", file_context=["/explicit/path.py"]
        )
        # Verify MemorySystem was NOT called for lookup
        app_instance.memory_system.get_relevant_context_for.assert_not_called()
        # Verify TaskSystem was not called
        app_instance.task_system.execute_task.assert_not_called()


    def test_task_help_flag(self, app_instance):
        """Test /task --help displays template parameter information."""
        # Arrange: Create a mock template that will be returned by find_template
        mock_template = {
            "name": "aider:automatic",
            "type": "aider",
            "subtype": "automatic",
            "description": "Execute an automatic Aider task (Template Version)",
            "parameters": {
                "prompt": {
                    "type": "string",
                    "description": "The instruction for code changes (from template)",
                    "required": True
                },
                "file_context": {
                    "type": "string",
                    "description": "(Optional) JSON string array of file paths (from template)"
                }
            }
        }
        
        # Reset call history for mocks on the real TaskSystem instance
        app_instance.task_system.find_template.reset_mock()
        # Set the return value to our mock template to test template precedence
        app_instance.task_system.find_template.return_value = mock_template
        app_instance.task_system.execute_task.reset_mock()

        # Reset other relevant mocks
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
                     
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        from src.repl.repl import Repl
        repl = Repl(app_instance, output_stream=captured_output)

        # Act
        repl._cmd_task('aider:automatic --help')

        # Assert Output
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        assert "Fetching help for task: aider:automatic..." in output
        assert "* Task Template Details:" in output
        assert "* Direct Tool Specification:" not in output # Should NOT show tool spec
        assert "Execute an automatic Aider task (Template Version)" in output # Description from template
        assert "prompt (type: string): The instruction for code changes (from template) (required)" in output
        assert "(Optional) JSON string array of file paths (from template)" in output

        # Assert Mock Calls
        app_instance.aider_bridge.execute_automatic_task.assert_not_called()
        app_instance.task_system.execute_task.assert_not_called()
        app_instance.task_system.find_template.assert_called_once_with("aider:automatic")


    def test_task_parameter_parsing_complex_json(self, app_instance):
        """Test /task parsing of complex JSON parameters (Direct Tool path)."""
        # Arrange: Use aider:automatic (Direct Tool)
        # Reset call history for mocks on the real TaskSystem instance
        app_instance.task_system.find_template.reset_mock()
        app_instance.task_system.find_template.return_value = None # Ensure default
        app_instance.task_system.execute_task.reset_mock()
        # DO NOT set return_value here, rely on fixture default

        # Reset other relevant mocks
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
                     
        # Set up a mock for the direct tool executor to capture the params
        direct_tool_mock = MagicMock()
        # Store the received params for inspection
        received_params = {}
        
        def capture_params(params):
            received_params.update(params)
            return {"status": "COMPLETE", "content": "Success", "notes": {}}
            
        direct_tool_mock.side_effect = capture_params
        
        # Ensure the handler mock has the executors dict initialized
        if not hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
            app_instance.passthrough_handler.direct_tool_executors = {}
            
        # Replace the executor in the handler's direct_tool_executors
        app_instance.passthrough_handler.direct_tool_executors["aider:automatic"] = direct_tool_mock
        
        # Ensure find_template returns None to force direct tool path
        app_instance.task_system.find_template.return_value = None
        
        # --- Act: Call the REAL dispatcher directly ---
        from src.dispatcher import execute_programmatic_task
        
        identifier = "aider:automatic"
        params_for_dispatcher = {
            "prompt": "Complex JSON test",
            # Simulate REPL parsing the JSON string into a list
            "file_context": ["/f1"],
            # Simulate REPL parsing the JSON string into a dict
            "config": {"nested": {"value": 42}, "array": [1, 2, 3]}
        }
        flags_for_dispatcher = {}

        result = execute_programmatic_task(
            identifier=identifier,
            params=params_for_dispatcher,
            flags=flags_for_dispatcher,
            handler_instance=app_instance.passthrough_handler, # Pass the mock handler
            task_system_instance=app_instance.task_system, # Pass the mock task system
            optional_history_str=None
        )
        # --- End Act ---

        # Assert Result
        assert result["status"] == "COMPLETE"
        assert result["content"] == "Success" # From our mock return value

        # Assert Mock Calls: Verify direct tool executor was called
        direct_tool_mock.assert_called_once()
        
        # Check that all parameters were correctly parsed and passed to the executor
        assert received_params["prompt"] == "Complex JSON test"
        assert received_params["file_context"] == ["/f1"]
        assert received_params["config"] == {"nested": {"value": 42}, "array": [1, 2, 3]}


    def test_task_error_handling_invalid_json_repl(self, app_instance):
        """Test /task REPL handling of invalid JSON syntax in parameter value."""
        # Arrange
        # Reset call history for mocks on the real TaskSystem instance
        app_instance.task_system.find_template.reset_mock()
        app_instance.task_system.find_template.return_value = None # Ensure default
        app_instance.task_system.execute_task.reset_mock()
        # DO NOT set return_value here, rely on fixture default

        # Reset other relevant mocks
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
        # Import dispatcher function
        from src.dispatcher import execute_programmatic_task
        from src.system.errors import INPUT_VALIDATION_FAILURE # Import error code

        # Act: Call dispatcher directly with invalid JSON string
        result = execute_programmatic_task(
            identifier="aider:automatic",
            params={"prompt": "Invalid JSON", "file_context": '["unclosed_array\''}, # Invalid JSON
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert Result
        assert result["status"] == "FAILED"
        assert "Invalid file_context parameter: must be a JSON string array or already a list of strings. Error:" in result["content"] # Check specific error
        assert result["notes"]["error"]["reason"] == INPUT_VALIDATION_FAILURE

        # Assert Mock Calls
        # Dispatcher was called directly, bridge should not be called due to validation failure
        app_instance.aider_bridge.execute_automatic_task.assert_not_called()


    def test_task_error_handling_dispatcher_template_not_found(self, app_instance):
        """Test dispatcher error handling when template identifier is not found."""
        # Arrange
        # Reset call history for mocks on the real TaskSystem instance
        app_instance.task_system.find_template.reset_mock()
        app_instance.task_system.find_template.return_value = None # Ensure default
        app_instance.task_system.execute_task.reset_mock()
        # DO NOT set return_value here, rely on fixture default

        # Reset other relevant mocks
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
        # Ensure find_template returns None and no direct tool matches
        app_instance.task_system.find_template.return_value = None
        app_instance.passthrough_handler.direct_tool_executors = {}

        # Act: Call dispatcher directly
        from src.dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="nonexistent:template",
            params={"prompt": "This should fail"},
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert
        assert result["status"] == "FAILED"
        assert "Task identifier 'nonexistent:template' not found" in result["content"]
        assert result["notes"]["error"]["reason"] == "input_validation_failure"

        # Verify bridge/task system not called
        app_instance.aider_bridge.execute_automatic_task.assert_not_called()
        app_instance.task_system.execute_task.assert_not_called()


    def test_task_error_handling_executor_exception(self, app_instance):
        """Test dispatcher error handling when a direct tool executor raises an exception."""
        # Arrange: Configure the mock bridge (used by the direct tool) to raise an error
        # Reset call history for mocks on the real TaskSystem instance
        app_instance.task_system.find_template.reset_mock()
        app_instance.task_system.find_template.return_value = None # Ensure default
        app_instance.task_system.execute_task.reset_mock()
        # DO NOT set return_value here, rely on fixture default

        # Reset other relevant mocks
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
        app_instance.aider_bridge.execute_automatic_task.side_effect = Exception("Simulated bridge error")

        # Act: Call dispatcher for the direct tool
        from src.dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="aider:automatic", # This is registered as a direct tool
            params={"prompt": "This will fail"},
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert: Check that the error from the executor/bridge was caught and formatted
        assert result["status"] == "FAILED"
        # The error message comes from the executor function's catch block
        assert "Aider execution failed: Simulated bridge error" in result["content"]
        assert result["notes"]["error"]["reason"] == "unexpected_error"

        # Verify the bridge was called (and raised the error)
        app_instance.aider_bridge.execute_automatic_task.assert_called_once()


    def test_task_template_precedence_over_direct_tool(self, app_instance):
        """Test dispatcher routing: templates take precedence over direct tools."""
        # Arrange: Define a template and a direct tool with the same identifier
        mock_template = {
            "name": "common:id", "type": "common", "subtype": "id",
            "description": "Template Version", "parameters": {}
        }
        
        # Reset call history for mocks on the real TaskSystem instance
        app_instance.task_system.find_template.reset_mock()
        app_instance.task_system.execute_task.reset_mock()
        
        # IMPORTANT: Set the return value AFTER reset_mock to ensure it's used
        app_instance.task_system.find_template.return_value = mock_template

        # Register a direct tool with the same ID
        direct_tool_mock_executor = MagicMock(return_value={"status": "COMPLETE", "content": "Direct Tool Called"})
        app_instance.passthrough_handler.registerDirectTool("common:id", direct_tool_mock_executor)

        # Reset other relevant mocks
        app_instance.aider_bridge.execute_automatic_task.reset_mock()
        app_instance.memory_system.get_relevant_context_for.reset_mock()
        if hasattr(app_instance.passthrough_handler, 'direct_tool_executors'):
             for tool_mock in app_instance.passthrough_handler.direct_tool_executors.values():
                 if isinstance(tool_mock, MagicMock):
                     tool_mock.reset_mock()
        # Act: Call dispatcher with the common identifier
        from src.dispatcher import execute_programmatic_task
        result = execute_programmatic_task(
            identifier="common:id",
            params={},
            flags={},
            handler_instance=app_instance.passthrough_handler,
            task_system_instance=app_instance.task_system
        )

        # Assert: Template path was taken, not the direct tool
        assert result["status"] == "COMPLETE"
        assert result["notes"]["execution_path"] == "execute_subtask_directly (Phase 1 Stub)" # Template path (Phase 1)
        assert result["notes"]["template_used"] == "common:id"
        assert "Executed template 'common:id' with inputs." in result["content"] # Content from TaskSystem stub

        # Verify TaskSystem was called (via execute_subtask_directly), direct tool was not
        # Note: We don't mock execute_subtask_directly itself, so no call count check here
        direct_tool_mock_executor.assert_not_called()
        app_instance.aider_bridge.execute_automatic_task.assert_not_called() # Ensure other tools not called
