"""Common pytest fixtures for all tests."""
import pytest
from unittest.mock import MagicMock

from src.system.models import AssociativeMatchResult, MatchTuple
from src.system.models import TaskResult

@pytest.fixture
def mock_memory_system():
    """Create a mock memory system."""
    memory = MagicMock()
    memory.get_global_index.return_value = {}
    memory.update_global_index.return_value = None
    
    # Return a proper AssociativeMatchResult Pydantic model
    memory.get_relevant_context_for.return_value = AssociativeMatchResult(
        context_summary="mock context",
        matches=[MatchTuple(path="file1.py", relevance=0.9, excerpt="mock metadata")]
    )
    return memory

@pytest.fixture
def mock_context_generation_input():
    """Create a mock ContextGenerationInput."""
    from src.system.models import ContextGenerationInput
    return ContextGenerationInput(
        templateDescription="test query",
        inputs={"query": "test query"},
        inheritedContext=None
    )

@pytest.fixture
def mock_associative_match_result():
    """Create a mock AssociativeMatchResult."""
    from src.system.models import AssociativeMatchResult, MatchTuple
    return AssociativeMatchResult(
        context_summary="Test context summary",
        matches=[
            MatchTuple(path="file1.py", relevance=0.9, excerpt="rel1"),
            MatchTuple(path="file2.py", relevance=0.8, excerpt="rel2")
        ]
    )

@pytest.fixture
def mock_task_system():
    """Create a mock task system."""
    task_system = MagicMock()
    task_system.execute_task.return_value = TaskResult(
        content="mock response",
        status="COMPLETE",
        notes={}
    )
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
def mock_run_subprocess(mocker):
    """Mock subprocess.Popen for Aider subprocess execution."""
    mock_popen = mocker.patch('subprocess.Popen')
    mock_process = MagicMock()
    mock_process.wait.return_value = 0  # Simulate successful completion
    mock_process.poll.return_value = None  # Process is running
    mock_popen.return_value = mock_process
    return mock_popen

@pytest.fixture
def mock_aider_automatic_handler():
    """Create a mock Aider automatic handler."""
    handler = MagicMock()
    handler.execute_task.return_value = TaskResult(
        status="COMPLETE",
        content="Automatic task executed",
        notes={
            "files_modified": ["/path/to/mock_file.py"],
            "changes": [
                {"file": "/path/to/mock_file.py", "description": "Modified file"}
            ]
        }
    )
    return handler
