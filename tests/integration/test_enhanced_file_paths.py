"""Integration tests for Enhanced File Paths feature."""
import pytest
from unittest.mock import patch, MagicMock
import os
import tempfile

from task_system.task_system import TaskSystem
from memory.memory_system import MemorySystem
from handler.base_handler import BaseHandler

class TestEnhancedFilePathsIntegration:
    """Integration tests for the Enhanced File Paths feature."""
    
    @pytest.fixture
    def setup_environment(self):
        """Set up a test environment with files for integration testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            file_paths = []
            
            # Python files
            for i in range(3):
                file_path = os.path.join(temp_dir, f"test{i}.py")
                with open(file_path, "w") as f:
                    f.write(f"# Test file {i}\ndef test_func(): pass")
                file_paths.append(file_path)
            
            # Markdown files
            for i in range(2):
                file_path = os.path.join(temp_dir, f"doc{i}.md")
                with open(file_path, "w") as f:
                    f.write(f"# Documentation {i}\n\nTest content")
                file_paths.append(file_path)
            
            yield temp_dir, file_paths
    
    @pytest.fixture
    def mock_memory_system(self):
        """Create a mock memory system for testing."""
        memory_system = MagicMock(spec=MemorySystem)
        
        # Create mock result class with matches attribute
        class MockResult:
            def __init__(self, matches):
                self.matches = matches
                
        # Setup get_relevant_context_for to return Python files for "python" query
        def mock_get_context(input_data):
            query = input_data.get("taskText", "").lower()
            if "python" in query:
                return MockResult([("test0.py", 0.9), ("test1.py", 0.8)])
            elif "doc" in query or "markdown" in query:
                return MockResult([("doc0.md", 0.9), ("doc1.md", 0.8)])
            else:
                return MockResult([])
                
        memory_system.get_relevant_context_for.side_effect = mock_get_context
        
        # Forward get_relevant_context_with_description to get_relevant_context_for
        memory_system.get_relevant_context_with_description.side_effect = \
            lambda query, context_description: mock_get_context({"taskText": context_description})
        
        return memory_system
    
    @pytest.fixture
    def components(self, mock_memory_system, setup_environment):
        """Set up all components for integration testing."""
        temp_dir, file_paths = setup_environment
        
        # Create a real task system
        task_system = TaskSystem()
        
        # Create a mock handler
        handler = MagicMock(spec=BaseHandler)
        
        # Setup execute_file_path_command to return paths based on command
        def mock_execute_command(command):
            if "*.py" in command:
                return [p for p in file_paths if p.endswith(".py")]
            elif "*.md" in command:
                return [p for p in file_paths if p.endswith(".md")]
            else:
                return []
        
        handler.execute_file_path_command.side_effect = mock_execute_command
        
        # Setup _execute_tool to delegate to execute_file_path_command
        def mock_execute_tool(tool_name, input_data):
            if tool_name == "executeFilePathCommand" and "command" in input_data:
                paths = mock_execute_command(input_data["command"])
                return {
                    "status": "success",
                    "content": f"Found {len(paths)} files",
                    "metadata": {
                        "file_paths": paths,
                        "success": True
                    }
                }
            return None
            
        handler._execute_tool.side_effect = mock_execute_tool
        
        return task_system, mock_memory_system, handler, temp_dir
    
    def test_literal_source_integration(self, components):
        """Test integration with literal source type."""
        task_system, memory_system, handler, temp_dir = components
        
        # Create a template with literal file paths
        template = {
            "type": "atomic",
            "subtype": "test",
            "file_paths": [
                os.path.join(temp_dir, "test0.py"),
                os.path.join(temp_dir, "doc0.md")
            ],
            "file_paths_source": {"type": "literal"}
        }
        
        # Resolve file paths
        file_paths, error = task_system.resolve_file_paths(template, memory_system, handler)
        
        # Verify result
        assert len(file_paths) == 2
        assert os.path.join(temp_dir, "test0.py") in file_paths
        assert os.path.join(temp_dir, "doc0.md") in file_paths
        assert error is None
        
        # Verify no interactions with memory system or handler
        memory_system.get_relevant_context_with_description.assert_not_called()
        handler.execute_file_path_command.assert_not_called()
    
    def test_description_source_integration(self, components):
        """Test integration with description source type."""
        task_system, memory_system, handler, temp_dir = components
        
        # Create a template with description source
        template = {
            "type": "atomic",
            "subtype": "test",
            "description": "Main task description",
            "file_paths_source": {
                "type": "description",
                "value": "Find python files for testing"
            }
        }
        
        # Resolve file paths
        file_paths, error = task_system.resolve_file_paths(template, memory_system, handler)
        
        # Verify result
        assert len(file_paths) == 2
        assert "test0.py" in file_paths[0]
        assert "test1.py" in file_paths[1]
        assert error is None
        
        # Verify memory system was called correctly
        memory_system.get_relevant_context_with_description.assert_called_once()
    
    def test_command_source_integration(self, components):
        """Test integration with command source type."""
        task_system, memory_system, handler, temp_dir = components
        
        # Create a template with command source
        template = {
            "type": "atomic",
            "subtype": "test",
            "file_paths_source": {
                "type": "command",
                "value": "find . -name '*.md'"
            }
        }
        
        # For direct method testing, disable the _execute_tool method on the handler
        if hasattr(handler, "_execute_tool"):
            delattr(handler, "_execute_tool")
        
        # Resolve file paths
        file_paths, error = task_system.resolve_file_paths(template, memory_system, handler)
        
        # Verify result
        assert len(file_paths) == 2
        assert any(p.endswith(".md") for p in file_paths)
        assert error is None
        
        # Verify handler was called correctly
        handler.execute_file_path_command.assert_called_once()
        
    def test_execute_task_with_file_paths(self, components):
        """Test the execute_task method with file path resolution."""
        task_system, memory_system, handler, temp_dir = components
        
        # Create a simple test template
        template = {
            "type": "atomic",
            "subtype": "test",
            "name": "atomic_test",
            "description": "Test template",
            "file_paths_source": {
                "type": "command",
                "value": "find . -name '*.py'"
            }
        }
        
        # Register the template
        task_system.register_template(template)
        
        # Mock the resolve_file_paths method
        def mock_resolve_file_paths(template, memory_system, handler):
            return [os.path.join(temp_dir, "test0.py"), os.path.join(temp_dir, "test1.py")], None
        
        task_system.resolve_file_paths = mock_resolve_file_paths
        
        # Explicitly add execute_prompt method to the mock handler
        if not hasattr(handler, 'execute_prompt') or not callable(handler.execute_prompt):
            handler.execute_prompt = MagicMock(return_value={
                "status": "COMPLETE",
                "content": "Task executed",
                "notes": {}
            })
        
        # Execute the task
        result = task_system.execute_task("atomic", "test", {}, memory_system, handler=handler)
        
        # Verify result
        assert result["status"] == "COMPLETE"
        
        # Verify that execute_prompt was called with the right parameters
        handler.execute_prompt.assert_called_once()
        args, kwargs = handler.execute_prompt.call_args
        assert args[0] == "Test template"  # Description
        assert "Files: " in args[2]  # File context
