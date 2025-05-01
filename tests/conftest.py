import pytest
import os
import subprocess # For git_repo fixture
from unittest.mock import MagicMock, patch

# Import Pydantic models for fixtures
from src.system.models import (
    ContextGenerationInput,
    AssociativeMatchResult,
    MatchTuple,
    TaskResult,
    ReturnStatus,
    TaskError,
    TaskFailureReason,
    SubtaskRequest,
    ContextManagement, # Added for SubtaskRequest
    TaskType, # Added for SubtaskRequest
)

# --- Mock Core Components ---

@pytest.fixture
def mock_memory_system():
    """Provides a mock MemorySystem instance."""
    ms = MagicMock(name="MockMemorySystem")
    # Adjust MatchTuple mock to match Pydantic model (path, relevance, excerpt)
    ms.get_relevant_context_for.return_value = AssociativeMatchResult(
        context_summary="Mocked context summary",
        matches=[
            MatchTuple(path="/mock/file1.py", relevance=0.9, excerpt="mock excerpt 1"),
        ],
        error=None
    )
    ms.get_relevant_context_with_description.return_value = AssociativeMatchResult(
        context_summary="Mocked context summary via desc",
        matches=[
            MatchTuple(path="/mock/file_desc.py", relevance=0.8, excerpt="desc excerpt"),
        ],
        error=None
    )
    ms.global_index = { "/mock/file1.py": "mock metadata" }
    # Attach a mock handler if needed by components using this fixture
    # Note: Creates a dependency between fixtures. Consider alternatives if issues arise.
    # ms.handler = mock_base_handler() # Removed direct dependency for now
    return ms

@pytest.fixture
def mock_task_system():
    """Provides a mock TaskSystem instance."""
    ts = MagicMock(name="MockTaskSystem")
    ts.find_template.return_value = {"name": "mock_template", "type": "atomic", "params": {}}
    ts.execute_atomic_template.return_value = TaskResult(status="COMPLETE", content="Mock task success")
    # Adjust MatchTuple mock
    ts.generate_context_for_memory_system.return_value = AssociativeMatchResult(
        context_summary="Mock generated context",
        matches=[MatchTuple(path="/mock/gen_file.py", relevance=0.7, excerpt="gen excerpt")],
        error=None
    )
    ts.resolve_file_paths.return_value = (["/mock/resolved.py"], None)
    ts.find_matching_tasks.return_value = [{"task": {"name": "matched_task"}, "score": 0.9}]
    return ts

@pytest.fixture
def mock_base_handler():
    """Provides a mock BaseHandler instance."""
    handler = MagicMock(name="MockBaseHandler")
    handler.file_manager = MagicMock(name="MockFileManager")
    handler.file_manager.base_path = "/mock/handler/base"
    handler.file_manager.read_file.return_value = "Mock file content"
    handler.execute_file_path_command.return_value = ["/mock/cmd_file.py"]
    # Mock internal LLM call method result
    handler._execute_llm_call.return_value = TaskResult(status=ReturnStatus.COMPLETE, content="Mock LLM response")
    # Mock helper methods
    handler._create_file_context.return_value = "Mock created context string"
    handler._get_relevant_files.return_value = ["/mock/relevant_file.py"]
    handler._build_system_prompt.return_value = "Mock system prompt"
    handler._execute_tool.return_value = TaskResult(status=ReturnStatus.COMPLETE, content="Mock tool result")
    # Mock the agent instance if needed directly
    handler.agent = MagicMock(name="MockPydanticAgent")
    handler.agent.run_sync.return_value = MagicMock(output="Mock agent output")
    # Mock LLMInteractionManager if BaseHandler uses it
    handler.llm_manager = MagicMock(name="MockLLMInteractionManager")
    handler.llm_manager.execute_call.return_value = ("Mock LLM response", []) # Assuming (content, history) tuple
    return handler

@pytest.fixture
def mock_atomic_task_executor():
    """Provides a mock AtomicTaskExecutor instance."""
    executor = MagicMock(name="MockAtomicTaskExecutor")
    executor.execute_body.return_value = TaskResult(
        status=ReturnStatus.COMPLETE,
        content="Mock executor success",
        notes={"executor_note": "mock_value"}
    )
    return executor


# --- Mock Data Structures ---

@pytest.fixture
def mock_context_generation_input():
    """Provides a mock ContextGenerationInput instance."""
    return ContextGenerationInput(
        query="mock query",
        # templateName="mock_template", # Removed, not in model
        templateDescription="mock description",
        inputs={"param": "value"}
    )

@pytest.fixture
def mock_associative_match_result():
    """Provides a mock AssociativeMatchResult instance."""
    return AssociativeMatchResult(
        context_summary="Mock context summary",
        matches=[
            MatchTuple(path="/mock/file1.py", relevance=0.9, excerpt="mock excerpt 1"),
            MatchTuple(path="/mock/file2.txt", relevance=0.8, excerpt="mock excerpt 2"),
        ],
        error=None
    )

@pytest.fixture
def mock_subtask_request():
    """Provides a mock SubtaskRequest instance."""
    return SubtaskRequest(
        task_id="mock-task-123", # Added task_id
        type=TaskType.atomic, # Use enum/literal
        # subtype="mock_subtype", # Removed, not in model
        name="mock_subtask_name",
        description="Mock subtask description",
        inputs={"sub_param": "sub_value"}
    )


# --- Mock External Dependencies ---

@pytest.fixture
def mock_run_subprocess(mocker):
    """Mocks subprocess.run."""
    # Use mocker fixture provided by pytest-mock
    return mocker.patch('subprocess.run')

# --- Mock Aider Components (Example) ---
# These might be needed if testing components that interact with AiderBridge

@pytest.fixture
def mock_aider_model():
    """Provides a mock Aider model instance."""
    return MagicMock(name="MockAiderModel")

@pytest.fixture
def mock_aider_io():
    """Provides a mock Aider IO instance."""
    return MagicMock(name="MockAiderIO")

@pytest.fixture
def mock_aider_coder():
    """Provides a mock Aider Coder instance."""
    coder = MagicMock(name="MockAiderCoder")
    coder.run.return_value = "Mock Aider run result" # Example return
    return coder

@pytest.fixture
def mock_aider_session(mock_aider_coder):
    """Provides a mock Aider Session instance."""
    session = MagicMock(name="MockAiderSession")
    session.coder = mock_aider_coder
    return session

@pytest.fixture
def mock_aider_automatic_handler():
    """Provides a mock Aider Automatic Handler instance."""
    handler = MagicMock(name="MockAiderAutomaticHandler")
    handler.execute_task.return_value = TaskResult(status=ReturnStatus.COMPLETE, content="Mock Aider auto result")
    return handler

# --- Integration Test Fixtures ---

@pytest.fixture(scope="function") # Use function scope for isolation
def git_repo(tmp_path):
    """
    Fixture to create a temporary Git repository for integration tests.

    Yields:
        tuple: (repo_path_str, add_file_func, commit_func)
               - repo_path_str: Absolute path to the temporary repo.
               - add_file_func: Function to add a file (path relative to repo root, content).
               - commit_func: Function to commit changes (commit message).
    """
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    repo_path_str = str(repo_path)

    try:
        # Initialize Git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=repo_path_str, check=True, capture_output=True)
        # Configure dummy user for commits
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path_str, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path_str, check=True)
        print(f"Initialized Git repo at: {repo_path_str}") # Debug print
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        pytest.skip(f"Git command failed, skipping integration tests: {e}")

    def add_file(relative_path: str, content: str | bytes):
        """Helper to add a file to the repo."""
        file_path = repo_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        mode = 'wb' if isinstance(content, bytes) else 'w'
        encoding = None if isinstance(content, bytes) else 'utf-8'
        with open(file_path, mode, encoding=encoding) as f:
            f.write(content)
        subprocess.run(["git", "add", str(file_path)], cwd=repo_path_str, check=True)
        print(f"Added file: {relative_path}") # Debug print

    def commit(message: str):
        """Helper to commit changes."""
        # Allow empty commits for initial setup if needed
        subprocess.run(["git", "commit", "--allow-empty", "-m", message], cwd=repo_path_str, check=True, capture_output=True)
        print(f"Committed: {message}") # Debug print

    # Initial commit to ensure the repo is not empty and branch exists
    commit("Initial repository setup")

    yield repo_path_str, add_file, commit

    # Cleanup happens automatically with tmp_path fixture
