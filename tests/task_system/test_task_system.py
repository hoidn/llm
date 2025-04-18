"""Tests for TaskSystem enhancements."""
import pytest
from unittest.mock import MagicMock, patch
from task_system.task_system import TaskSystem
from task_system.template_utils import resolve_function_calls as original_resolve_function_calls

# Import necessary types/classes for tests
from src.handler.base_handler import BaseHandler
from src.task_system.ast_nodes import SubtaskRequest
from src.system.errors import INPUT_VALIDATION_FAILURE


def patched_resolve_function_calls(text, task_system, env, **kwargs):
    return original_resolve_function_calls(text, task_system, env)

import pytest

@pytest.fixture(autouse=True)
def patch_resolve_function_calls(monkeypatch):
    monkeypatch.setattr("task_system.template_utils.resolve_function_calls", patched_resolve_function_calls)

class TestTaskSystemRegistration:
    """Tests for TaskSystem template registration and lookup."""
    
    def test_register_template(self):
        """Test registering a template."""
        task_system = TaskSystem()
        
        # Simple template
        template = {
            "type": "atomic",
            "subtype": "test",
            "name": "test_template",
            "description": "Test template"
        }
        
        task_system.register_template(template)
        
        # Verify template was stored by name
        assert "test_template" in task_system.templates
        
        # Verify template was indexed by type:subtype
        assert "atomic:test" in task_system.template_index
        assert task_system.template_index["atomic:test"] == "test_template"
    
    def test_register_template_without_name(self):
        """Test registering a template without a name."""
        task_system = TaskSystem()
        
        # Template without name
        template = {
            "type": "atomic",
            "subtype": "test",
            "description": "Test template"
        }
        
        task_system.register_template(template)
        
        # Template should be stored with generated name
        generated_name = "atomic_test"
        assert generated_name in task_system.templates
        assert task_system.template_index["atomic:test"] == generated_name
    
    def test_find_template_by_name(self):
        """Test finding a template by name."""
        task_system = TaskSystem()
        
        # Register a template
        template = {
            "type": "atomic",
            "subtype": "test",
            "name": "test_template",
            "description": "Test template"
        }
        
        task_system.register_template(template)
        
        # Find by name
        found = task_system.find_template("test_template")
        assert found is not None
        assert found["name"] == "test_template"
    
    def test_find_template_by_type_subtype(self):
        """Test finding a template by type:subtype."""
        task_system = TaskSystem()
        
        # Register a template
        template = {
            "type": "atomic",
            "subtype": "test",
            "name": "test_template",
            "description": "Test template"
        }
        
        task_system.register_template(template)
        
        # Find by type:subtype
        found = task_system.find_template("atomic:test")
        assert found is not None
        assert found["name"] == "test_template"
    
    def test_find_nonexistent_template(self):
        """Test finding a template that doesn't exist."""
        task_system = TaskSystem()
        
        # Find nonexistent template
        found = task_system.find_template("nonexistent")
        assert found is None


class TestTaskSystemExecution:
    """Tests for TaskSystem task execution."""
    
    def test_execute_task_with_validation(self):
        """Test executing a task with parameter validation."""
        task_system = TaskSystem()
        
        # Register a mock template
        template = {
            "type": "atomic",
            "subtype": "associative_matching",
            "name": "test_template",
            "parameters": {
                "query": {"type": "string", "required": True}
            }
        }
        
        task_system.register_template(template)
        
        # Mock the _execute_associative_matching method
        # Return a TaskResult object instead of a dictionary
        task_system._execute_associative_matching = MagicMock(return_value=TaskResult(
            status="COMPLETE",
            content="[]",
            notes={}
        ))
        
        # Execute with valid parameters
        result = task_system.execute_task("atomic", "associative_matching", {"query": "test"})
        
        assert result.status == "COMPLETE"
        task_system._execute_associative_matching.assert_called_once()
    
    def test_execute_task_with_function_calls(self):
        """Test executing a task with function calls in template fields."""
        # Create a TaskSystem instance
        task_system = TaskSystem()
        
        # Register a simple function template
        format_template = {
            "type": "atomic",
            "subtype": "format",
            "name": "format_greeting",
            "description": "Format a greeting for a person",
            "parameters": {
                "name": {"type": "string", "required": True},
                "formal": {"type": "boolean", "default": False}
            },
            "system_prompt": "{{formal ? 'Dear' : 'Hello'}}, {{name}}!"
        }
        task_system.register_template(format_template)
        
        # Register a template that calls the function
        caller_template = {
            "type": "atomic",
            "subtype": "caller",
            "name": "greeting_caller",
            "description": "Template that calls format_greeting",
            "parameters": {
                "person": {"type": "string", "required": True}
            },
            "system_prompt": "Greeting: {{format_greeting(name=person, formal=true)}}"
        }
        task_system.register_template(caller_template)
        
        # Mock the _execute_associative_matching method for both templates
        # First mock for the caller template
        task_system._execute_associative_matching = MagicMock(side_effect=[
            # Result from the main template execution
            TaskResult(
                status="COMPLETE",
                content="Template with call result",
                notes={}
            )
        ])
        
        # Create a separate mock for the function template execution
        original_execute = task_system.execute_task
        
        def mock_execute(*args, **kwargs):
            task_type = args[0]
            task_subtype = args[1]
            
            # If this is the format_greeting function call
            if task_type == "atomic" and task_subtype == "format":
                return TaskResult(
                    status="COMPLETE",
                    content="Dear, Test!",
                    notes={}
                )
            
            # Otherwise delegate to original implementation
            return original_execute(*args, **kwargs)
        
        # Use our mock function for task execution
        with patch.object(task_system, 'execute_task', side_effect=mock_execute):
            # Execute the caller template
            result = task_system.execute_task("atomic", "caller", {"person": "Test"})
            
            # Verify that the format_greeting function call was processed
            # and its result was included in the system_prompt
            executed_template = task_system._execute_associative_matching.call_args[0][0]
            assert "Greeting: Dear, Test!" in executed_template["system_prompt"]
            
            # Verify final result
            assert result["status"] == "COMPLETE"
            assert result["content"] == "Template with call result"
    
    def test_execute_task_with_variable_resolution(self):
        """Test executing a task with variable resolution."""
        task_system = TaskSystem()
        
        # Register a test template with variables in fields
        template = {
            "type": "atomic",
            "subtype": "var_test",
            "name": "variable_test",
            "description": "Test for {{user}}",
            "system_prompt": "Process query '{{query}}' with limit {{limit}}",
            "parameters": {
                "query": {"type": "string", "required": True},
                "user": {"type": "string", "default": "default_user"},
                "limit": {"type": "integer", "default": 10}
            }
        }
        
        task_system.register_template(template)
        
        # Mock the _execute_associative_matching method
        task_system._execute_associative_matching = MagicMock(return_value={
            "status": "COMPLETE",
            "content": "Test result"
        })
        
        # Execute task with inputs that will be used for variable resolution
        task_system.execute_task(
            "atomic", "var_test", 
            {"query": "search_query", "user": "test_user"}
        )
        
        # Verify that variables were resolved in the template
        template_arg = task_system._execute_associative_matching.call_args[0][0]
        assert template_arg["description"] == "Test for test_user"
        assert template_arg["system_prompt"] == "Process query 'search_query' with limit 10"
    
    def test_execute_task_with_invalid_parameters(self):
        """Test executing a task with invalid parameters."""
        task_system = TaskSystem()
        
        # Register a mock template
        template = {
            "type": "atomic",
            "subtype": "associative_matching",
            "name": "test_template",
            "parameters": {
                "query": {"type": "string", "required": True}
            }
        }
        
        task_system.register_template(template)
        
        # Execute with missing required parameter
        result = task_system.execute_task("atomic", "associative_matching", {})
        
        assert result["status"] == "FAILED"
        assert "PARAMETER_ERROR" in result["notes"]["error"]
    
    def test_execute_task_with_model_selection(self):
        """Test executing a task with model selection."""
        task_system = TaskSystem()
        
        # Register a mock template with model preferences
        template = {
            "type": "atomic",
            "subtype": "associative_matching",
            "name": "test_template",
            "parameters": {
                "query": {"type": "string", "required": True}
            },
            "model": {
                "preferred": "claude-3",
                "fallback": ["gpt-4"]
            }
        }
        
        task_system.register_template(template)
        
        # Mock the _execute_associative_matching method
        # Return a TaskResult object instead of a dictionary
        task_system._execute_associative_matching = MagicMock(return_value=TaskResult(
            status="COMPLETE",
            content="[]",
            notes={}
        ))
        
        # Execute with available models
        available_models = ["gpt-4"]  # Claude-3 not available
        result = task_system.execute_task(
            "atomic", "associative_matching", 
            {"query": "test"}, 
            available_models=available_models
        )
        
        assert result.status == "COMPLETE"
        assert result.notes["selected_model"] == "gpt-4"

    def test_execute_unknown_task(self):
        """Test executing an unknown task type."""
        task_system = TaskSystem()
        
        # Execute unknown task
        result = task_system.execute_task("unknown", "task", {})
        
        assert result["status"] == "FAILED"
        assert "Unknown task type" in result["content"]
        
    def test_execute_task_with_context_relevance(self):
        """Test execute_task with context relevance settings."""
        # Create TaskSystem in test mode
        task_system = TaskSystem()
        task_system.set_test_mode(True)
        
        # Create a template with context_relevance settings
        template = {
            "type": "test",
            "subtype": "relevance",
            "name": "test_relevance",
            "description": "Test template with context relevance",
            "parameters": {
                "important_param": {"type": "string", "required": True},
                "unimportant_param": {"type": "string", "required": False, "default": "default"}
            },
            "context_relevance": {
                "important_param": True,
                "unimportant_param": False
            }
        }
        
        # Register the template
        task_system.register_template(template)
        
        # Create mock memory system
        mock_memory = MagicMock()
        
        # Execute task
        result = task_system.execute_task(
            "test", "relevance", 
            {"important_param": "important value", "unimportant_param": "not important"},
            memory_system=mock_memory
        )
        
        # Verify memory system was called with correct context relevance
        mock_memory.get_relevant_context_for.assert_called_once()
        args = mock_memory.get_relevant_context_for.call_args[0]
        
        # Verify context relevance was passed correctly
        assert args[0].context_relevance["important_param"] is True
        assert args[0].context_relevance["unimportant_param"] is False
        
        # Verify result is successful
        assert result["status"] == "COMPLETE"


# --- Tests for execute_subtask_directly (Phase 1) ---

@pytest.fixture
def task_system_for_direct(mock_memory_system): # Reuse memory system fixture if needed
    """Fixture for TaskSystem specifically for testing execute_subtask_directly."""
    ts = TaskSystem()
    # Link a mock handler via a mock memory system
    mock_handler = MagicMock(spec=BaseHandler)
    mock_handler.execute_file_path_command = MagicMock(return_value=["cmd_file1.txt"])
    mock_memory_system.handler = mock_handler # Link handler to memory system
    ts.memory_system = mock_memory_system # Link memory system to task system
    return ts

@pytest.fixture
def base_env():
    """Fixture for a base Environment."""
    from task_system.template_utils import Environment
    return Environment({})

def test_exec_direct_template_not_found(task_system_for_direct, base_env):
    """Test execute_subtask_directly when the template doesn't exist."""
    request = SubtaskRequest(type="nonexistent", subtype="task", inputs={})
    result = task_system_for_direct.execute_subtask_directly(request, base_env)
    assert result.status == "FAILED"
    assert "Template not found" in result.content
    assert result.notes["error"]["reason"] == INPUT_VALIDATION_FAILURE

def test_exec_direct_context_from_request(task_system_for_direct, base_env):
    """Test context determination using file_paths from the SubtaskRequest."""
    template = {"name": "test_req_ctx", "type": "atomic", "subtype": "req"}
    task_system_for_direct.register_template(template)
    request_files = ["req_file1.py", "req_file2.md"]
    request = SubtaskRequest(type="atomic", subtype="req", inputs={}, file_paths=request_files)

    result = task_system_for_direct.execute_subtask_directly(request, base_env)

    assert result.status == "COMPLETE" # Phase 1 stub returns COMPLETE
    assert result.notes["context_source"] == "explicit_request"
    assert result.notes["context_files_count"] == 2
    assert result.notes["determined_context_files"] == request_files

def test_exec_direct_context_from_template_literal(task_system_for_direct, base_env):
    """Test context determination using literal file_paths from the template."""
    template_files = ["tmpl_file1.py", "tmpl_file2.md"]
    template = {"name": "test_tmpl_lit", "type": "atomic", "subtype": "lit", "file_paths": template_files}
    task_system_for_direct.register_template(template)
    request = SubtaskRequest(type="atomic", subtype="lit", inputs={}) # No paths in request

    result = task_system_for_direct.execute_subtask_directly(request, base_env)

    assert result.status == "COMPLETE"
    assert result.notes["context_source"] == "template_literal"
    assert result.notes["context_files_count"] == 2
    assert result.notes["determined_context_files"] == template_files

def test_exec_direct_context_request_overrides_template(task_system_for_direct, base_env):
    """Test that request file_paths override template literal file_paths."""
    template_files = ["tmpl_file1.py"]
    template = {"name": "test_override", "type": "atomic", "subtype": "override", "file_paths": template_files}
    task_system_for_direct.register_template(template)
    request_files = ["req_file1.py", "req_file2.md"] # Different paths
    request = SubtaskRequest(type="atomic", subtype="override", inputs={}, file_paths=request_files)

    result = task_system_for_direct.execute_subtask_directly(request, base_env)

    assert result.status == "COMPLETE"
    assert result.notes["context_source"] == "explicit_request" # Request takes precedence
    assert result.notes["context_files_count"] == 2
    assert result.notes["determined_context_files"] == request_files

# --- Tests for _determine_context_for_direct_execution ---

def test_determine_context_from_request(task_system_for_direct):
    """Test context determination using file_paths from the SubtaskRequest."""
    template = {"name": "test_req_ctx", "type": "atomic", "subtype": "req"}
    request_files = ["req_file1.py", "req_file2.md"]
    request = SubtaskRequest(type="atomic", subtype="req", inputs={}, file_paths=request_files)

    file_paths, context_source, error = task_system_for_direct._determine_context_for_direct_execution(request, template)

    assert file_paths == request_files
    assert context_source == "explicit_request"
    assert error is None

def test_determine_context_from_template_literal(task_system_for_direct):
    """Test context determination using literal file_paths from the template."""
    template_files = ["tmpl_file1.py", "tmpl_file2.md"]
    template = {"name": "test_tmpl_lit", "type": "atomic", "subtype": "lit", "file_paths": template_files}
    request = SubtaskRequest(type="atomic", subtype="lit", inputs={})  # No paths in request

    file_paths, context_source, error = task_system_for_direct._determine_context_for_direct_execution(request, template)

    assert file_paths == template_files
    assert context_source == "template_literal"
    assert error is None

def test_determine_context_from_template_command(task_system_for_direct):
    """Test context determination using a command source from the template."""
    command = "git ls-files *.py"
    expected_cmd_files = ["cmd_file1.txt"]  # From mock handler setup
    template = {
        "name": "test_tmpl_cmd",
        "type": "atomic",
        "subtype": "cmd",
        "file_paths_source": {"type": "command", "command": command}
    }
    
    # Mock the handler's command execution method linked via memory_system
    mock_handler = task_system_for_direct.memory_system.handler
    mock_handler.execute_file_path_command.return_value = expected_cmd_files
    
    request = SubtaskRequest(type="atomic", subtype="cmd", inputs={})

    file_paths, context_source, error = task_system_for_direct._determine_context_for_direct_execution(request, template)

    assert file_paths == expected_cmd_files
    assert context_source == "template_command"
    assert error is None
    mock_handler.execute_file_path_command.assert_called_once_with(command)

def test_determine_context_command_error(task_system_for_direct):
    """Test context determination when command execution fails."""
    command = "invalid-command"
    error_msg = "Command failed"
    template = {
        "name": "test_tmpl_cmd_err",
        "type": "atomic",
        "subtype": "cmd_err",
        "file_paths_source": {"type": "command", "command": command}
    }
    
    # Mock the handler's command execution method to raise an error
    mock_handler = task_system_for_direct.memory_system.handler
    mock_handler.execute_file_path_command.side_effect = Exception(error_msg)
    
    request = SubtaskRequest(type="atomic", subtype="cmd_err", inputs={})

    file_paths, context_source, error = task_system_for_direct._determine_context_for_direct_execution(request, template)

    assert file_paths == []
    assert context_source == "template_command_error"
    assert error is not None
    assert error_msg in error
    mock_handler.execute_file_path_command.assert_called_once_with(command)

def test_determine_context_deferred_lookup(task_system_for_direct):
    """Test context determination with deferred lookup."""
    template = {
        "name": "test_defer",
        "type": "atomic",
        "subtype": "defer",
        "file_paths_source": {"type": "description"},  # Source type requiring lookup
        "context_management": {"fresh_context": "enabled"}  # Auto lookup enabled
    }
    request = SubtaskRequest(type="atomic", subtype="defer", inputs={})

    file_paths, context_source, error = task_system_for_direct._determine_context_for_direct_execution(request, template)

    assert file_paths == []
    assert context_source == "deferred_lookup"
    assert error is None

def test_determine_context_no_sources(task_system_for_direct):
    """Test context determination with no sources available."""
    template = {"name": "test_no_ctx", "type": "atomic", "subtype": "noctx"}
    request = SubtaskRequest(type="atomic", subtype="noctx", inputs={})

    file_paths, context_source, error = task_system_for_direct._determine_context_for_direct_execution(request, template)

    assert file_paths == []
    assert context_source == "none"
    assert error is None

def test_exec_direct_context_from_template_command_success(task_system_for_direct, base_env):
    """Test context determination using a command source from the template (success)."""
    command = "git ls-files *.py"
    expected_cmd_files = ["cmd_file1.txt"] # From mock handler setup
    template = {
        "name": "test_tmpl_cmd",
        "type": "atomic",
        "subtype": "cmd",
        "file_paths_source": {"type": "command", "command": command}
    }
    task_system_for_direct.register_template(template)
    request = SubtaskRequest(type="atomic", subtype="cmd", inputs={})

    # Mock the handler's command execution method linked via memory_system
    mock_handler = task_system_for_direct.memory_system.handler
    mock_handler.execute_file_path_command.return_value = expected_cmd_files

    result = task_system_for_direct.execute_subtask_directly(request, base_env)

    assert result.status == "COMPLETE"
    mock_handler.execute_file_path_command.assert_called_once_with(command)
    assert result.notes["context_source"] == "template_command"
    assert result.notes["context_files_count"] == 1
    assert result.notes["determined_context_files"] == expected_cmd_files
    assert "context_error" not in result.notes

def test_exec_direct_context_from_template_command_error(task_system_for_direct, base_env):
    """Test context determination using a command source from the template (error)."""
    command = "invalid-command"
    error_msg = "Command failed"
    template = {
        "name": "test_tmpl_cmd_err",
        "type": "atomic",
        "subtype": "cmd_err",
        "file_paths_source": {"type": "command", "command": command}
    }
    task_system_for_direct.register_template(template)
    request = SubtaskRequest(type="atomic", subtype="cmd_err", inputs={})

    # Mock the handler's command execution method to raise an error
    mock_handler = task_system_for_direct.memory_system.handler
    mock_handler.execute_file_path_command.side_effect = Exception(error_msg)

    result = task_system_for_direct.execute_subtask_directly(request, base_env)

    assert result.status == "COMPLETE" # Phase 1 stub still completes
    mock_handler.execute_file_path_command.assert_called_once_with(command)
    assert result.notes["context_source"] == "template_command_error"
    assert result.notes["context_files_count"] == 0
    assert result.notes["determined_context_files"] == []
    assert "context_error" in result.notes
    assert error_msg in result.notes["context_error"]

def test_exec_direct_context_from_template_command_no_handler(task_system_for_direct, base_env):
    """Test command source when handler is missing."""
    command = "some-command"
    template = {
        "name": "test_tmpl_cmd_noh",
        "type": "atomic",
        "subtype": "cmd_noh",
        "file_paths_source": {"type": "command", "command": command}
    }
    task_system_for_direct.register_template(template)
    request = SubtaskRequest(type="atomic", subtype="cmd_noh", inputs={})

    # Break the handler link
    task_system_for_direct.memory_system.handler = None

    result = task_system_for_direct.execute_subtask_directly(request, base_env)

    assert result.status == "COMPLETE" # Phase 1 stub still completes
    assert result.notes["context_source"] == "template_command_error"
    assert result.notes["context_files_count"] == 0
    assert "context_error" in result.notes
    assert "Handler or method not available" in result.notes["context_error"]


def test_exec_direct_no_explicit_context(task_system_for_direct, base_env):
    """Test case where no explicit context is provided in request or template."""
    template = {"name": "test_no_ctx", "type": "atomic", "subtype": "noctx"}
    task_system_for_direct.register_template(template)
    request = SubtaskRequest(type="atomic", subtype="noctx", inputs={})

    result = task_system_for_direct.execute_subtask_directly(request, base_env)

    assert result.status == "COMPLETE"
    assert result.notes["context_source"] == "none"
    assert result.notes["context_files_count"] == 0
    assert result.notes["determined_context_files"] == []

def test_exec_direct_automatic_lookup_deferred(task_system_for_direct, base_env):
    """Test that automatic context lookup is deferred in Phase 1."""
    template = {
        "name": "test_defer",
        "type": "atomic",
        "subtype": "defer",
        "file_paths_source": {"type": "description"} # Source type requiring lookup
    }
    task_system_for_direct.register_template(template)
    request = SubtaskRequest(type="atomic", subtype="defer", inputs={})

    # Mock the memory system method that *would* be called
    task_system_for_direct.memory_system.get_relevant_context_for = MagicMock()

    result = task_system_for_direct.execute_subtask_directly(request, base_env)

    assert result.status == "COMPLETE"
    # Verify the automatic lookup method was NOT called
    task_system_for_direct.memory_system.get_relevant_context_for.assert_not_called()
    assert result.notes["context_source"] == "deferred_lookup" # Check source indicates deferral
    assert result.notes["context_files_count"] == 0
