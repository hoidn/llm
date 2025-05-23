"""Common pytest fixtures for all tests."""
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_memory_system():
    """Create a mock memory system."""
    memory = MagicMock()
    memory.get_global_index.return_value = {}
    memory.update_global_index.return_value = None
    # Create a mock result object with matches attribute
    class MockResult:
        def __init__(self):
            self.context = "mock context"
            self.matches = [("file1.py", "mock metadata")]
    
    memory.get_relevant_context_for.return_value = MockResult()
    return memory

@pytest.fixture
def mock_task_system():
    """Create a mock task system."""
    task_system = MagicMock()
    task_system.execute_task.return_value = {
        "content": "mock response",
        "status": "COMPLETE",
        "notes": {}
    }
    task_system.register_template.return_value = None
    return task_system

@pytest.fixture
def mock_aider_model():
    """Create a mock Aider model."""
    model = MagicMock()
    model.send_completion.return_value = {"content": "Mock response"}
    return model

@pytest.fixture
def mock_aider_io():
    """Create a mock Aider IO."""
    io = MagicMock()
    io.yes = True
    return io

@pytest.fixture
def mock_aider_coder():
    """Create a mock Aider coder."""
    coder = MagicMock()
    coder.run.return_value = "Mock coder response"
    coder.aider_edited_files = ["/path/to/mock_file.py"]
    return coder

@pytest.fixture
def mock_aider_session():
    """Create a mock Aider session."""
    session = MagicMock()
    session.active = False
    session.start_session.return_value = {
        "status": "COMPLETE",
        "content": "Interactive session completed",
        "notes": {
            "files_modified": ["/path/to/mock_file.py"]
        }
    }
    session.terminate_session.return_value = {
        "status": "COMPLETE",
        "content": "Session terminated",
        "notes": {}
    }
    return session

@pytest.fixture
def mock_aider_automatic_handler():
    """Create a mock Aider automatic handler."""
    handler = MagicMock()
    handler.execute_task.return_value = {
        "status": "COMPLETE",
        "content": "Automatic task executed",
        "notes": {
            "files_modified": ["/path/to/mock_file.py"],
            "changes": [
                {"file": "/path/to/mock_file.py", "description": "Modified file"}
            ]
        }
    }
    return handler
