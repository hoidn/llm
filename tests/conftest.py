"""Common pytest fixtures for all tests."""
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_memory_system():
    """Create a mock memory system."""
    memory = MagicMock()
    memory.get_global_index.return_value = {}
    memory.update_global_index.return_value = None
    memory.get_relevant_context_for.return_value = {
        "context": "mock context",
        "matches": [("file1.py", "mock metadata")]
    }
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
