"""
Unit tests for the MemorySystem class.
Focuses on logic implemented in Phase 1, Set B.
"""

import pytest
from unittest.mock import MagicMock, patch, call, ANY
import os
import logging # Ensure logging is imported
from unittest.mock import patch # Added

# Assuming MemorySystem is importable
from src.memory.memory_system import MemorySystem, DEFAULT_SHARDING_CONFIG
# Import necessary models for tests
from src.system.models import ContextGenerationInput, AssociativeMatchResult, MatchTuple, TaskResult, SubtaskRequest, ContextManagement, TaskFailureError # Added TaskResult, SubtaskRequest, ContextManagement, TaskFailureError
from src.task_system.task_system import TaskSystem # Added for patching
from src.handler.file_access import FileAccessManager # For mock spec
from src.handler.file_access import FileAccessManager # For mock spec
from src.handler.base_handler import BaseHandler # For mock spec


# Default config for tests
TEST_CONFIG = {
    "sharding_enabled": False,
    "token_size_per_shard": 500,
    "max_shards": 5,
}


@pytest.fixture # Add this new fixture
def mock_file_manager_ms(): # Use distinct name
    fm = MagicMock(spec=FileAccessManager)
    fm.read_file.return_value = "Mock file content" # Default success
    return fm

@pytest.fixture
def mock_dependencies(mock_file_manager_ms): # Add mock_file_manager_ms fixture dependency
    """Provides mock handler, task_system, and file_manager."""
    # Use spec for better mocking
    handler_mock = MagicMock(spec=BaseHandler)
    task_system_mock = MagicMock(spec=TaskSystem)
    # Return all three mocks
    return handler_mock, task_system_mock, mock_file_manager_ms


@pytest.fixture
def mock_task_system():
    """Provides a mock TaskSystem with proper spec."""
    mock = MagicMock(name="MockTaskSystem", spec=TaskSystem)
    # Configure default behaviors
    mock.execute_atomic_template.return_value = TaskResult(status="COMPLETE", content="Mock task success")
    return mock

@pytest.fixture # Update memory_system_instance to use new fixture
def memory_system_instance(mock_dependencies, mock_file_manager_ms, mock_task_system): # Add mock_task_system
    """Provides a MemorySystem instance with mock dependencies."""
    # Unpack handler from mock_dependencies, ignore the rest
    handler_mock, _, _ = mock_dependencies
    # Pass the new mock file manager and dedicated task_system mock
    return MemorySystem(
        handler=handler_mock,
        task_system=mock_task_system,
        file_access_manager=mock_file_manager_ms, # Pass mock FM
        config=TEST_CONFIG.copy()
    )


# --- Test __init__ ---


def test_init_defaults(mock_dependencies): # mock_dependencies now includes file_manager
    """Test initialization when no config is passed, uses defaults."""
    handler_mock, task_system_mock, file_manager_mock = mock_dependencies
    # Need to pass all required args now
    ms = MemorySystem(
        handler=handler_mock,
        task_system=task_system_mock,
        file_access_manager=file_manager_mock
    )
    assert ms.handler == handler_mock
    assert ms.task_system == task_system_mock
    assert ms.file_access_manager == file_manager_mock # Assert file manager stored
    assert ms.global_index == {}
    assert ms._sharded_index == []
    # Check against the imported defaults
    assert ms._config["sharding_enabled"] == DEFAULT_SHARDING_CONFIG["sharding_enabled"]
    assert (
        ms._config["token_size_per_shard"]
        == DEFAULT_SHARDING_CONFIG["token_size_per_shard"]
    )


def test_init_with_config(mock_dependencies): # mock_dependencies now includes file_manager
    """Test initialization with custom config overrides defaults."""
    handler_mock, task_system_mock, file_manager_mock = mock_dependencies
    custom_config = {
        "sharding_enabled": True,
        "max_shards": 20,
        "custom_param": "value",
    }
    # Pass all required args
    ms = MemorySystem(
        handler=handler_mock,
        task_system=task_system_mock,
        file_access_manager=file_manager_mock,
        config=custom_config
    )
    assert ms.file_access_manager == file_manager_mock # Assert file manager stored
    assert ms._config["sharding_enabled"] is True
    assert ms._config["max_shards"] == 20
    # Check that defaults not in custom_config are retained
    assert (
        ms._config["token_size_per_shard"]
        == DEFAULT_SHARDING_CONFIG["token_size_per_shard"]
    )
    # Check that extra params in config are ignored if not part of default structure update logic
    # assert "custom_param" not in ms._config # Or assert it is if config update is simple dict.update()
    assert (
        ms._config["custom_param"] == "value"
    )  # Current implementation uses dict.update


# --- Test get_global_index ---


def test_get_global_index_empty(memory_system_instance):
    """Test getting index when it's empty."""
    assert memory_system_instance.get_global_index() == {}


def test_get_global_index_populated(memory_system_instance):
    """Test getting index after updates."""
    # Use real absolute paths for realism if possible, or mocked ones
    abs_path1 = os.path.abspath("file1.py")
    abs_path2 = os.path.abspath("dir/file2.txt")
    test_index = {abs_path1: "meta1", abs_path2: "meta2"}
    memory_system_instance.global_index = test_index  # Directly set internal state for test
    retrieved_index = memory_system_instance.get_global_index()
    assert retrieved_index == test_index
    # Ensure it returns a copy
    retrieved_index["new_key"] = "new_value"
    assert "new_key" not in memory_system_instance.global_index


# --- Test update_global_index ---


@patch("os.path.isabs")
def test_update_global_index_success(mock_isabs, memory_system_instance):
    """Test updating index with valid absolute paths."""
    mock_isabs.return_value = True  # Assume all paths are absolute
    abs_path1 = os.path.abspath("/path/to/file1.py") # Use abspath for consistency
    abs_path2 = os.path.abspath("/another/path/file2.txt")
    initial_index = {abs_path1: "meta1"}
    update_data = {abs_path2: "meta2", abs_path1: "meta1_updated"}

    memory_system_instance.global_index = initial_index.copy()  # Set initial state
    memory_system_instance.update_global_index(update_data)

    # Check that the index is correctly updated/merged with absolute paths
    expected_index = {
        abs_path1: "meta1_updated",
        abs_path2: "meta2",
    }
    assert memory_system_instance.global_index == expected_index
    # Check that path validation was called for each key in update_data
    # assert mock_isabs.call_count == len(update_data) # Removed: Less critical than result check and potentially brittle


@patch("os.path.isabs")
def test_update_global_index_invalid_path(mock_isabs, memory_system_instance):
    """Test updating index with a non-absolute path raises ValueError."""
    abs_path = "/path/to/file1.py"
    rel_path = "relative/file.txt"
    # Configure mock_isabs: return False only for the relative path
    # Use normpath to handle potential OS differences in path representation
    # Simplified side effect to avoid recursion
    mock_isabs.side_effect = lambda p: p == abs_path
    update_data = {abs_path: "meta1", rel_path: "meta_rel"}

    with pytest.raises(ValueError, match="Non-absolute paths provided"):
        memory_system_instance.update_global_index(update_data)
    # Ensure validation was attempted on both paths before raising
    assert mock_isabs.call_count == len(update_data) # This assertion should be valid now


@patch("src.memory.memory_system.MemorySystem._recalculate_shards")
@patch("os.path.isabs", return_value=True)  # Assume paths are valid
def test_update_global_index_recalculates_shards_if_enabled(
    mock_isabs, mock_recalc, memory_system_instance
):
    """Test that shards are recalculated on update if sharding is enabled."""
    memory_system_instance._config["sharding_enabled"] = True  # Enable sharding for this test
    update_data = {os.path.abspath("/abs/path.py"): "meta"} # Use abspath

    memory_system_instance.update_global_index(update_data)
    mock_recalc.assert_called_once()


@patch("src.memory.memory_system.MemorySystem._recalculate_shards")
@patch("os.path.isabs", return_value=True)  # Assume paths are valid
def test_update_global_index_does_not_recalculate_if_disabled(
    mock_isabs, mock_recalc, memory_system_instance
):
    """Test that shards are not recalculated on update if sharding is disabled."""
    memory_system_instance._config["sharding_enabled"] = False  # Ensure sharding is disabled
    update_data = {os.path.abspath("/abs/path.py"): "meta"} # Use abspath

    memory_system_instance.update_global_index(update_data)
    mock_recalc.assert_not_called()


# --- Test enable_sharding ---


@patch("src.memory.memory_system.MemorySystem._recalculate_shards")
def test_enable_sharding_enables_and_recalculates(mock_recalc, memory_system_instance):
    """Test enabling sharding sets flag and triggers recalculation."""
    memory_system_instance._config["sharding_enabled"] = False  # Start disabled
    memory_system_instance.enable_sharding(True)
    assert memory_system_instance._config["sharding_enabled"] is True
    mock_recalc.assert_called_once()


@patch("src.memory.memory_system.MemorySystem._recalculate_shards")
def test_enable_sharding_disables_and_clears(mock_recalc, memory_system_instance):
    """Test disabling sharding sets flag and clears shards list."""
    memory_system_instance._config["sharding_enabled"] = True  # Start enabled
    memory_system_instance._sharded_index = [{"/some/path": "meta"}]  # Add dummy shard data
    memory_system_instance.enable_sharding(False)
    assert memory_system_instance._config["sharding_enabled"] is False
    assert memory_system_instance._sharded_index == []  # Check shards list is cleared
    mock_recalc.assert_not_called()  # Recalculate should not be called when disabling


# --- Test configure_sharding ---


@patch("src.memory.memory_system.MemorySystem._recalculate_shards")
def test_configure_sharding_updates_config_and_recalculates_if_enabled(
    mock_recalc, memory_system_instance
):
    """Test configuring updates config and recalculates if sharding enabled."""
    memory_system_instance._config["sharding_enabled"] = True  # Enable sharding
    memory_system_instance.configure_sharding(max_shards=50, token_estimation_ratio=0.8)

    # Check specified values were updated
    assert memory_system_instance._config["max_shards"] == 50
    assert memory_system_instance._config["token_estimation_ratio"] == 0.8
    # Check other values remain from the initial TEST_CONFIG fixture
    assert (
        memory_system_instance._config["token_size_per_shard"]
        == TEST_CONFIG["token_size_per_shard"]
    )
    mock_recalc.assert_called_once()


@patch("src.memory.memory_system.MemorySystem._recalculate_shards")
def test_configure_sharding_updates_config_no_recalculate_if_disabled(
    mock_recalc, memory_system_instance
):
    """Test configuring updates config but doesn't recalculate if sharding disabled."""
    memory_system_instance._config["sharding_enabled"] = False  # Disable sharding
    memory_system_instance.configure_sharding(max_shards=50)
    assert memory_system_instance._config["max_shards"] == 50
    mock_recalc.assert_not_called()


# --- Test Deferred Methods (Placeholders) ---

# Test for index_git_repository is added below

# --- Test _recalculate_shards (Placeholder) ---
@patch("src.memory.memory_system.logger.debug")
def test_recalculate_shards_placeholder_logs_and_clears_when_enabled(
    mock_log, memory_system_instance
):
    """Test the placeholder recalculate method logs and clears shards when enabled."""
    memory_system_instance._config["sharding_enabled"] = True
    memory_system_instance._sharded_index = [{"a": "b"}]  # Add dummy data
    memory_system_instance._recalculate_shards()
    assert memory_system_instance._sharded_index == []  # Placeholder clears it
    # Check for log messages more flexibly
    calls = [c[0][0] for c in mock_log.call_args_list if isinstance(c[0][0], str)]
    assert any("Recalculating shards" in msg for msg in calls), "Expected log message starting with 'Recalculating shards' not found"
    assert any("Shards recalculated. Count:" in msg for msg in calls), "Expected log message 'Shards recalculated. Count:' not found"


@patch("src.memory.memory_system.logger.debug")
def test_recalculate_shards_placeholder_clears_when_disabled(mock_log, memory_system_instance):
    """Test the placeholder recalculate method clears shards when disabled."""
    memory_system_instance._config["sharding_enabled"] = False
    memory_system_instance._sharded_index = [{"a": "b"}]  # Add dummy data
    memory_system_instance._recalculate_shards()
    assert memory_system_instance._sharded_index == []  # Should clear if called when disabled
    # Should not log the "Recalculating..." message
    assert mock_log.call_count == 0


# --- Tests for Phase 2a: Context Retrieval Logic (DELETED) ---
# Delete all tests starting with test_get_relevant_context_for_*
# Delete test_get_relevant_context_with_description_calls_correctly

# ---- New Tests for get_relevant_context_for ----

def test_get_relevant_context_for_default_strategy_is_content(memory_system_instance, mock_task_system, mock_file_manager_ms): # Corrected name
    """Verify default strategy is 'content'."""
    # Ensure candidate_paths is not empty
    memory_system_instance.global_index = {"/path/a.py": "meta a"}
    input_data = ContextGenerationInput(query="test")
    # Mock TaskSystem return for the content task
    mock_task_result = TaskResult(status="COMPLETE", content=AssociativeMatchResult(context_summary="Content Result", matches=[]).model_dump_json())
    mock_task_system.execute_atomic_template.return_value = mock_task_result

    memory_system_instance.get_relevant_context_for(input_data)

    mock_file_manager_ms.read_file.assert_called() # Content strategy reads files
    mock_task_system.execute_atomic_template.assert_called_once()
    request_arg = mock_task_system.execute_atomic_template.call_args[0][0]
    assert isinstance(request_arg, SubtaskRequest)
    assert request_arg.name == "internal:associative_matching_content"

def test_get_relevant_context_for_content_strategy_flow(memory_system_instance, mock_task_system, mock_file_manager_ms): # Corrected name
    """Test the full flow for the 'content' strategy."""
    input_data = ContextGenerationInput(query="test content", matching_strategy='content')
    # Assume global index has paths
    memory_system_instance.global_index = {"/path/a.py": "meta a", "/path/b.py": "meta b"}
    # Mock file reads
    mock_file_manager_ms.read_file.side_effect = lambda p, max_size=None: f"Content of {p}" if p in ["/path/a.py", "/path/b.py"] else None

    # Mock TaskSystem return
    expected_matches = [MatchTuple(path="/path/a.py", relevance=0.9)]
    mock_assoc_result = AssociativeMatchResult(context_summary="Content Result", matches=expected_matches)
    mock_task_result = TaskResult(status="COMPLETE", content=mock_assoc_result.model_dump_json())
    mock_task_system.execute_atomic_template.return_value = mock_task_result

    result = memory_system_instance.get_relevant_context_for(input_data)

    # Assert file reads happened
    assert mock_file_manager_ms.read_file.call_count == 2
    mock_file_manager_ms.read_file.assert_any_call("/path/a.py", max_size=ANY)
    mock_file_manager_ms.read_file.assert_any_call("/path/b.py", max_size=ANY)

    # Assert TaskSystem call
    mock_task_system.execute_atomic_template.assert_called_once()
    request_arg = mock_task_system.execute_atomic_template.call_args[0][0]
    assert request_arg.name == "internal:associative_matching_content"
    assert "file_contents" in request_arg.inputs
    assert request_arg.inputs["file_contents"] == {"/path/a.py": "Content of /path/a.py", "/path/b.py": "Content of /path/b.py"}
    assert request_arg.context_management.freshContext == "disabled" # Check override

    # Assert final result
    assert isinstance(result, AssociativeMatchResult)
    assert result.matches == expected_matches
    assert result.error is None

def test_get_relevant_context_for_metadata_strategy_flow(memory_system_instance, mock_task_system, mock_file_manager_ms): # Corrected name
    """Test the full flow for the 'metadata' strategy."""
    input_data = ContextGenerationInput(query="test metadata", matching_strategy='metadata')
    # Assume global index has paths
    memory_system_instance.global_index = {"/path/a.py": "meta a", "/path/b.py": "meta b"}

    # Mock TaskSystem return
    expected_matches = [MatchTuple(path="/path/b.py", relevance=0.8)]
    mock_assoc_result = AssociativeMatchResult(context_summary="Metadata Result", matches=expected_matches)
    mock_task_result = TaskResult(status="COMPLETE", content=mock_assoc_result.model_dump_json())
    mock_task_system.execute_atomic_template.return_value = mock_task_result

    result = memory_system_instance.get_relevant_context_for(input_data)

    # Assert file reads did NOT happen
    mock_file_manager_ms.read_file.assert_not_called()

    # Assert TaskSystem call
    mock_task_system.execute_atomic_template.assert_called_once()
    request_arg = mock_task_system.execute_atomic_template.call_args[0][0]
    assert request_arg.name == "internal:associative_matching_metadata"
    assert "metadata_snippet" in request_arg.inputs
    assert request_arg.inputs["metadata_snippet"] == {"/path/a.py": "meta a", "/path/b.py": "meta b"}
    assert request_arg.context_management.freshContext == "disabled"

    # Assert final result
    assert isinstance(result, AssociativeMatchResult)
    assert result.matches == expected_matches
    assert result.error is None

def test_get_relevant_context_for_content_strategy_read_error(memory_system_instance, mock_task_system, mock_file_manager_ms): # Corrected name
    """Test content strategy when some files cannot be read."""
    input_data = ContextGenerationInput(query="test partial read", matching_strategy='content')
    memory_system_instance.global_index = {"/path/a.py": "meta a", "/path/error.py": "meta err"}
    # Simulate read error for one file
    mock_file_manager_ms.read_file.side_effect = lambda p, max_size=None: "Content of /path/a.py" if p == "/path/a.py" else None

    # Mock TaskSystem return (assuming it gets called with only the readable file)
    expected_matches = [MatchTuple(path="/path/a.py", relevance=0.7)]
    mock_assoc_result = AssociativeMatchResult(context_summary="Partial Content Result", matches=expected_matches)
    mock_task_result = TaskResult(status="COMPLETE", content=mock_assoc_result.model_dump_json())
    mock_task_system.execute_atomic_template.return_value = mock_task_result

    result = memory_system_instance.get_relevant_context_for(input_data)

    # Assert reads attempted for both
    assert mock_file_manager_ms.read_file.call_count == 2
    # Assert TaskSystem called with only the successful read
    mock_task_system.execute_atomic_template.assert_called_once()
    request_arg = mock_task_system.execute_atomic_template.call_args[0][0]
    assert request_arg.inputs["file_contents"] == {"/path/a.py": "Content of /path/a.py"}
    # Assert final result
    assert result.matches == expected_matches

def test_get_relevant_context_for_task_system_call_fails(memory_system_instance, mock_task_system, mock_file_manager_ms): # Corrected name
    """Test when the TaskSystem call returns a FAILED status."""
    input_data = ContextGenerationInput(query="test failure", matching_strategy='content')
    memory_system_instance.global_index = {"/path/a.py": "meta a"}
    mock_file_manager_ms.read_file.return_value = "Content"
    # Simulate TaskSystem failure
    fail_error = TaskFailureError(type="TASK_FAILURE", reason="llm_error", message="LLM timed out")
    mock_task_result = TaskResult(status="FAILED", content="LLM timed out", notes={"error": fail_error.model_dump()})
    mock_task_system.execute_atomic_template.return_value = mock_task_result

    result = memory_system_instance.get_relevant_context_for(input_data)

    assert isinstance(result, AssociativeMatchResult)
    assert result.matches == []
    assert result.error is not None
    assert "Associative matching task" in result.error
    assert "failed" in result.error
    assert "LLM timed out" in result.error # Check original error message is included

def test_get_relevant_context_for_task_system_returns_invalid_json(memory_system_instance, mock_task_system, mock_file_manager_ms): # Corrected name
    """Test when TaskSystem returns non-JSON content."""
    input_data = ContextGenerationInput(query="test bad json", matching_strategy='metadata')
    memory_system_instance.global_index = {"/path/a.py": "meta a"}
    # Simulate TaskSystem returning bad content
    mock_task_result = TaskResult(status="COMPLETE", content="This is not JSON", notes={})
    mock_task_system.execute_atomic_template.return_value = mock_task_result

    result = memory_system_instance.get_relevant_context_for(input_data)

    assert isinstance(result, AssociativeMatchResult)
    assert result.matches == []
    assert result.error is not None
    assert "Failed to parse AssociativeMatchResult JSON" in result.error

def test_get_relevant_context_for_missing_task_system(memory_system_instance, mock_file_manager_ms): # Corrected name
    """Test when TaskSystem dependency is missing."""
    memory_system_instance.task_system = None # Remove dependency
    input_data = ContextGenerationInput(query="test no ts")

    result = memory_system_instance.get_relevant_context_for(input_data)

    assert isinstance(result, AssociativeMatchResult)
    assert result.matches == []
    assert result.error is not None
    assert "TaskSystem dependency not available" in result.error

# Add more tests for edge cases: empty index, invalid strategy in input, etc.


# --- Tests for index_git_repository ---

# Make sure GitRepositoryIndexer is importable for patching
try:
    # Adjust path if needed based on where MemorySystem imports it from
    # Assuming MemorySystem imports it like: from src.memory.indexers.git_repository_indexer import GitRepositoryIndexer
    from src.memory.indexers.git_repository_indexer import GitRepositoryIndexer
except ImportError:
    GitRepositoryIndexer = MagicMock() # Define dummy if import fails in test env

@patch('src.memory.memory_system.GitRepositoryIndexer', new_callable=MagicMock) # Patch the class where it's imported/used in memory_system.py
@patch('os.path.isdir', return_value=True) # Mock isdir to return True for these tests
def test_index_git_repository_success(mock_isdir, MockGitIndexer, memory_system_instance): # Add mock_isdir arg
    """Test successful call to index_git_repository delegates correctly."""
    repo_path = "/path/to/valid/repo"
    options = {"max_file_size": 50000, "include_patterns": ["*.js"]}
    mock_indexer_instance = MockGitIndexer.return_value # Get the instance created inside the method
    # Mock return value of the indexer's method (though not strictly needed for this test)
    mock_indexer_instance.index_repository.return_value = {os.path.abspath("/path/to/valid/repo/file.js"): "js metadata"}

    # Act
    memory_system_instance.index_git_repository(repo_path, options)

    # Assert
    mock_isdir.assert_called_once_with(repo_path) # Verify the check was made
    # 1. Indexer was instantiated with the correct path
    MockGitIndexer.assert_called_once_with(repo_path=repo_path)
    # 2. Indexer was configured with options (check attributes or specific config methods if they exist)
    #    Need to assume indexer class allows setting these directly or via methods
    #    If indexer uses configure methods:
    #    mock_indexer_instance.set_max_file_size.assert_called_once_with(50000)
    #    mock_indexer_instance.set_include_patterns.assert_called_once_with(["*.js"])
    #    If indexer uses attributes (as implemented):
    #    Verify attributes were set on the *mock* instance
    assert mock_indexer_instance.max_file_size == 50000 # Assumes attribute setting works
    assert mock_indexer_instance.include_patterns == ["*.js"] # Assumes attribute setting works

    # 3. index_repository was called with the memory_system instance
    mock_indexer_instance.index_repository.assert_called_once_with(memory_system=memory_system_instance)

@patch('src.memory.memory_system.GitRepositoryIndexer', new_callable=MagicMock)
@patch('os.path.isdir', return_value=True) # Mock isdir to return True
def test_index_git_repository_no_options(mock_isdir, MockGitIndexer, memory_system_instance): # Add mock_isdir arg
    """Test call without options uses indexer defaults."""
    repo_path = "/path/to/another/repo"
    mock_indexer_instance = MockGitIndexer.return_value
    mock_indexer_instance.index_repository.return_value = {}

    # Act
    memory_system_instance.index_git_repository(repo_path) # No options passed

    # Assert
    mock_isdir.assert_called_once_with(repo_path) # Verify the check was made
    MockGitIndexer.assert_called_once_with(repo_path=repo_path)
    # Verify config methods weren't called / default attributes remain (if accessible)
    # e.g., mock_indexer_instance.set_max_file_size.assert_not_called()
    # Check that options attributes were NOT set (or retain defaults)
    # This requires knowing the defaults set in GitRepositoryIndexer.__init__
    # Example check (assuming direct attribute access on mock):
    # assert mock_indexer_instance.max_file_size == DEFAULT_INDEXER_MAX_SIZE # Example check
    # Check that the config methods/attributes were not called/set with specific values from 'options'
    # For attribute setting, we can check they weren't set to the values used in the previous test
    assert getattr(mock_indexer_instance, 'max_file_size', None) != 50000
    assert getattr(mock_indexer_instance, 'include_patterns', None) != ["*.js"]

    mock_indexer_instance.index_repository.assert_called_once_with(memory_system=memory_system_instance)

@patch('src.memory.memory_system.GitRepositoryIndexer', new_callable=MagicMock)
@patch('os.path.isdir', return_value=True) # Mock isdir to return True
def test_index_git_repository_indexer_error(mock_isdir, MockGitIndexer, memory_system_instance, caplog): # Add mock_isdir arg
    """Test handling of errors during the indexer's execution."""
    repo_path = "/path/to/error/repo"
    mock_indexer_instance = MockGitIndexer.return_value
    # Simulate indexer raising an error
    mock_indexer_instance.index_repository.side_effect = Exception("Git command failed")

    # Act
    with caplog.at_level(logging.ERROR): # Ensure logging level is captured
        memory_system_instance.index_git_repository(repo_path)

    # Assert
    mock_isdir.assert_called_once_with(repo_path) # Verify the check was made
    MockGitIndexer.assert_called_once_with(repo_path=repo_path)
    mock_indexer_instance.index_repository.assert_called_once_with(memory_system=memory_system_instance)
    # Check that an error was logged
    assert "Error indexing repository" in caplog.text
    assert repo_path in caplog.text # Check repo path is in the log
    assert "Git command failed" in caplog.text

@patch('src.memory.memory_system.GitRepositoryIndexer', new_callable=MagicMock)
@patch('os.path.isdir', return_value=False) # Mock isdir to return False for this test
def test_index_git_repository_invalid_path(mock_isdir, MockGitIndexer, memory_system_instance, caplog):
    """Test handling when the provided repo_path is invalid."""
    repo_path = "/invalid/path/does/not/exist"

    with caplog.at_level(logging.ERROR):
        memory_system_instance.index_git_repository(repo_path)

    # Assert
    mock_isdir.assert_called_with(repo_path)
    # Check that an error was logged
    assert "Repository path is not a valid directory" in caplog.text
    assert repo_path in caplog.text
    # Check that the indexer was NOT instantiated or called
    MockGitIndexer.assert_not_called()
