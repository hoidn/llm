"""
Unit tests for the MemorySystem class.
Focuses on logic implemented in Phase 1, Set B.
"""

import pytest
from unittest.mock import MagicMock, patch, call
import os

# Assuming MemorySystem is importable
from src.memory.memory_system import MemorySystem, DEFAULT_SHARDING_CONFIG
# Import necessary models for tests
from src.system.models import ContextGenerationInput, AssociativeMatchResult, MatchTuple


# Default config for tests
TEST_CONFIG = {
    "sharding_enabled": False,
    "token_size_per_shard": 500,
    "max_shards": 5,
}


@pytest.fixture
def mock_dependencies():
    """Provides mock handler and task_system."""
    return MagicMock(), MagicMock()  # Mock handler, Mock task_system


@pytest.fixture
def memory_system(mock_dependencies):
    """Provides a MemorySystem instance with mock dependencies."""
    handler_mock, task_system_mock = mock_dependencies
    # Use TEST_CONFIG for a predictable starting state, overriding defaults
    return MemorySystem(
        handler=handler_mock, task_system=task_system_mock, config=TEST_CONFIG.copy()
    )


# --- Test __init__ ---


def test_init_defaults(mock_dependencies):
    """Test initialization when no config is passed, uses defaults."""
    handler_mock, task_system_mock = mock_dependencies
    ms = MemorySystem(
        handler=handler_mock, task_system=task_system_mock
    )  # No config passed
    assert ms.handler == handler_mock
    assert ms.task_system == task_system_mock
    assert ms.global_index == {}
    assert ms._sharded_index == []
    # Check against the imported defaults
    assert ms._config["sharding_enabled"] == DEFAULT_SHARDING_CONFIG["sharding_enabled"]
    assert (
        ms._config["token_size_per_shard"]
        == DEFAULT_SHARDING_CONFIG["token_size_per_shard"]
    )


def test_init_with_config(mock_dependencies):
    """Test initialization with custom config overrides defaults."""
    handler_mock, task_system_mock = mock_dependencies
    custom_config = {
        "sharding_enabled": True,
        "max_shards": 20,
        "custom_param": "value",
    }
    ms = MemorySystem(
        handler=handler_mock, task_system=task_system_mock, config=custom_config
    )
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


def test_get_global_index_empty(memory_system):
    """Test getting index when it's empty."""
    assert memory_system.get_global_index() == {}


def test_get_global_index_populated(memory_system):
    """Test getting index after updates."""
    # Use real absolute paths for realism if possible, or mocked ones
    abs_path1 = os.path.abspath("file1.py")
    abs_path2 = os.path.abspath("dir/file2.txt")
    test_index = {abs_path1: "meta1", abs_path2: "meta2"}
    memory_system.global_index = test_index  # Directly set internal state for test
    retrieved_index = memory_system.get_global_index()
    assert retrieved_index == test_index
    # Ensure it returns a copy
    retrieved_index["new_key"] = "new_value"
    assert "new_key" not in memory_system.global_index


# --- Test update_global_index ---


@patch("os.path.isabs")
def test_update_global_index_success(mock_isabs, memory_system):
    """Test updating index with valid absolute paths."""
    mock_isabs.return_value = True  # Assume all paths are absolute
    abs_path1 = "/path/to/file1.py"
    abs_path2 = "/another/path/file2.txt"
    initial_index = {abs_path1: "meta1"}
    update_data = {abs_path2: "meta2", abs_path1: "meta1_updated"}

    memory_system.global_index = initial_index.copy()  # Set initial state
    memory_system.update_global_index(update_data)

    # Check that the index is correctly updated/merged
    assert memory_system.global_index == {
        abs_path1: "meta1_updated",
        abs_path2: "meta2",
    }
    # Check that path validation was called for each key in update_data
    assert mock_isabs.call_count == len(update_data)


@patch("os.path.isabs")
def test_update_global_index_invalid_path(mock_isabs, memory_system):
    """Test updating index with a non-absolute path raises ValueError."""
    abs_path = "/path/to/file1.py"
    rel_path = "relative/file.txt"
    # Configure mock_isabs to return False only for the relative path
    mock_isabs.side_effect = lambda p: os.path.normpath(p) == os.path.normpath(abs_path)
    update_data = {abs_path: "meta1", rel_path: "meta_rel"}

    with pytest.raises(ValueError, match="Non-absolute paths provided"):
        memory_system.update_global_index(update_data)
    # Ensure validation was attempted on both paths before raising
    assert mock_isabs.call_count == len(update_data)


@patch("src.memory.memory_system.MemorySystem._recalculate_shards")
@patch("os.path.isabs", return_value=True)  # Assume paths are valid
def test_update_global_index_recalculates_shards_if_enabled(
    mock_isabs, mock_recalc, memory_system
):
    """Test that shards are recalculated on update if sharding is enabled."""
    memory_system._config["sharding_enabled"] = True  # Enable sharding for this test
    update_data = {"/abs/path.py": "meta"}

    memory_system.update_global_index(update_data)
    mock_recalc.assert_called_once()


@patch("src.memory.memory_system.MemorySystem._recalculate_shards")
@patch("os.path.isabs", return_value=True)  # Assume paths are valid
def test_update_global_index_does_not_recalculate_if_disabled(
    mock_isabs, mock_recalc, memory_system
):
    """Test that shards are not recalculated on update if sharding is disabled."""
    memory_system._config["sharding_enabled"] = False  # Ensure sharding is disabled
    update_data = {"/abs/path.py": "meta"}

    memory_system.update_global_index(update_data)
    mock_recalc.assert_not_called()


# --- Test enable_sharding ---


@patch("src.memory.memory_system.MemorySystem._recalculate_shards")
def test_enable_sharding_enables_and_recalculates(mock_recalc, memory_system):
    """Test enabling sharding sets flag and triggers recalculation."""
    memory_system._config["sharding_enabled"] = False  # Start disabled
    memory_system.enable_sharding(True)
    assert memory_system._config["sharding_enabled"] is True
    mock_recalc.assert_called_once()


@patch("src.memory.memory_system.MemorySystem._recalculate_shards")
def test_enable_sharding_disables_and_clears(mock_recalc, memory_system):
    """Test disabling sharding sets flag and clears shards list."""
    memory_system._config["sharding_enabled"] = True  # Start enabled
    memory_system._sharded_index = [{"/some/path": "meta"}]  # Add dummy shard data
    memory_system.enable_sharding(False)
    assert memory_system._config["sharding_enabled"] is False
    assert memory_system._sharded_index == []  # Check shards list is cleared
    mock_recalc.assert_not_called()  # Recalculate should not be called when disabling


# --- Test configure_sharding ---


@patch("src.memory.memory_system.MemorySystem._recalculate_shards")
def test_configure_sharding_updates_config_and_recalculates_if_enabled(
    mock_recalc, memory_system
):
    """Test configuring updates config and recalculates if sharding enabled."""
    memory_system._config["sharding_enabled"] = True  # Enable sharding
    memory_system.configure_sharding(max_shards=50, token_estimation_ratio=0.8)

    # Check specified values were updated
    assert memory_system._config["max_shards"] == 50
    assert memory_system._config["token_estimation_ratio"] == 0.8
    # Check other values remain from the initial TEST_CONFIG fixture
    assert (
        memory_system._config["token_size_per_shard"]
        == TEST_CONFIG["token_size_per_shard"]
    )
    mock_recalc.assert_called_once()


@patch("src.memory.memory_system.MemorySystem._recalculate_shards")
def test_configure_sharding_updates_config_no_recalculate_if_disabled(
    mock_recalc, memory_system
):
    """Test configuring updates config but doesn't recalculate if sharding disabled."""
    memory_system._config["sharding_enabled"] = False  # Disable sharding
    memory_system.configure_sharding(max_shards=50)
    assert memory_system._config["max_shards"] == 50
    mock_recalc.assert_not_called()


# --- Test Deferred Methods (Placeholders) ---


def test_index_git_repository_deferred(memory_system):
    """Verify deferred method has placeholder (logs warning, doesn't raise)."""
    with patch("logging.warning") as mock_log:
        memory_system.index_git_repository("/fake/repo")
        mock_log.assert_called_with(
            "index_git_repository called, but implementation is deferred."
        )


def test_get_relevant_context_with_description_deferred(memory_system):
    """Verify deferred method raises NotImplementedError."""
    with pytest.raises(
        NotImplementedError,
        match="get_relevant_context_with_description implementation deferred",
    ):
        memory_system.get_relevant_context_with_description("query", "desc")


def test_get_relevant_context_for_deferred(memory_system):
    """Verify deferred method raises NotImplementedError."""
    with pytest.raises(
        NotImplementedError, match="get_relevant_context_for implementation deferred"
    ):
        memory_system.get_relevant_context_for({"taskText": "some task"})


# --- Test _recalculate_shards (Placeholder) ---
@patch("logging.debug")
def test_recalculate_shards_placeholder_logs_and_clears_when_enabled(
    mock_log, memory_system
):
    """Test the placeholder recalculate method logs and clears shards when enabled."""
    memory_system._config["sharding_enabled"] = True
    memory_system._sharded_index = [{"a": "b"}]  # Add dummy data
    memory_system._recalculate_shards()
    assert memory_system._sharded_index == []  # Placeholder clears it
    mock_log.assert_any_call("Recalculating shards (logic TBD)...")
    mock_log.assert_any_call("Shards recalculated. Count: 0")


@patch("logging.debug")
def test_recalculate_shards_placeholder_clears_when_disabled(mock_log, memory_system):
    """Test the placeholder recalculate method clears shards when disabled."""
    memory_system._config["sharding_enabled"] = False
    memory_system._sharded_index = [{"a": "b"}]  # Add dummy data
    memory_system._recalculate_shards()
    assert memory_system._sharded_index == []  # Should clear if called when disabled
    # Should not log the "Recalculating..." message
    assert mock_log.call_count == 0


# --- Tests for Phase 2a: Context Retrieval Logic ---

# Use the existing 'memory_system' fixture

def test_get_relevant_context_for_no_matches(memory_system):
    """Verify behavior when no metadata matches the query."""
    # Setup: Ensure index has data that *won't* match
    memory_system.update_global_index({
        os.path.abspath("/path/to/file1.py"): "metadata about python code",
        os.path.abspath("/path/to/file2.txt"): "text file description",
    })
    input_data = ContextGenerationInput(query="non_existent_keyword")

    result = memory_system.get_relevant_context_for(input_data)

    assert isinstance(result, AssociativeMatchResult)
    assert result.matches == []
    assert "Found 0 potential matches" in result.context_summary # Check summary text
    assert result.error is None

def test_get_relevant_context_for_query_match(memory_system):
    """Verify matching based on the 'query' field."""
    # Setup: Add specific metadata to match
    path1 = os.path.abspath("/path/file1.py")
    meta1 = "Relevant python code for feature_x"
    path2 = os.path.abspath("/path/other.txt")
    meta2 = "Some other text"
    memory_system.update_global_index({
        path1: meta1,
        path2: meta2,
    })
    # Use case-insensitive matching for robustness if implemented
    input_data = ContextGenerationInput(query="feature_x") # Lowercase query

    result = memory_system.get_relevant_context_for(input_data)

    assert isinstance(result, AssociativeMatchResult)
    assert len(result.matches) == 1
    # MatchTuple should follow Pydantic model: path, relevance, excerpt
    expected_match = MatchTuple(path=path1, relevance=1.0) # Placeholder relevance
    assert result.matches[0].path == expected_match.path
    assert result.matches[0].relevance == expected_match.relevance
    assert "Found 1 potential matches" in result.context_summary
    assert result.error is None

def test_get_relevant_context_for_template_description_match(memory_system):
    """Verify matching based on templateDescription if query is absent."""
    path1 = os.path.abspath("/path/template_match.py")
    meta1 = "Code related to user authentication"
    memory_system.update_global_index({path1: meta1})
    input_data = ContextGenerationInput(
        templateDescription="Handle user login and authentication flow",
        inputs={"user_id": 123} # Input potentially used if logic combines them
    )

    result = memory_system.get_relevant_context_for(input_data)

    assert isinstance(result, AssociativeMatchResult)
    assert len(result.matches) == 1
    expected_match = MatchTuple(path=path1, relevance=1.0)
    assert result.matches[0].path == expected_match.path
    assert result.matches[0].relevance == expected_match.relevance
    assert result.error is None

def test_get_relevant_context_for_query_precedence(memory_system):
    """Verify 'query' takes precedence over templateDescription."""
    path_query = os.path.abspath("/path/query_match.js")
    meta_query = "JavaScript for query processing"
    path_template = os.path.abspath("/path/template_match.py")
    meta_template = "Python for template logic"
    memory_system.update_global_index({
        path_query: meta_query,
        path_template: meta_template
    })
    # Both query and templateDesc are provided
    input_data = ContextGenerationInput(
        query="javascript query", # Should match this
        templateDescription="Logic related to python templates" # Should be ignored
    )

    result = memory_system.get_relevant_context_for(input_data)

    assert isinstance(result, AssociativeMatchResult)
    assert len(result.matches) == 1
    # Should match based on query, not templateDescription
    expected_match = MatchTuple(path=path_query, relevance=1.0)
    assert result.matches[0].path == expected_match.path
    assert result.matches[0].relevance == expected_match.relevance
    assert result.error is None

def test_get_relevant_context_for_multiple_matches(memory_system):
    """Verify multiple files can be matched."""
    path1 = os.path.abspath("/proj/common_feature.py")
    meta1 = "shared code for common_feature"
    path2 = os.path.abspath("/proj/specific/impl_common.txt")
    meta2 = "notes about common_feature implementation"
    path3 = os.path.abspath("/proj/other.java")
    meta3 = "unrelated java code"
    memory_system.update_global_index({
        path1: meta1,
        path2: meta2,
        path3: meta3,
    })
    input_data = ContextGenerationInput(query="common_feature")

    result = memory_system.get_relevant_context_for(input_data)

    assert isinstance(result, AssociativeMatchResult)
    assert len(result.matches) == 2
    # Check if both expected matches are present (order might vary)
    match_paths = {m.path for m in result.matches}
    assert match_paths == {path1, path2}
    assert "Found 2 potential matches" in result.context_summary
    assert result.error is None

# Use patch.object on the class itself
@patch.object(MemorySystem, 'get_relevant_context_for')
def test_get_relevant_context_with_description_calls_correctly(mock_get_relevant_context_for, memory_system):
    """Verify get_relevant_context_with_description constructs input and calls main method."""
    # Setup mock return value from the mocked get_relevant_context_for
    mock_return = AssociativeMatchResult(context_summary="Mocked Result", matches=[], error=None)
    mock_get_relevant_context_for.return_value = mock_return

    query_text = "Main task query (should be ignored by this method)"
    context_desc = "Specific description for context lookup" # This should become the query

    # Call the method under test
    result = memory_system.get_relevant_context_with_description(query_text, context_desc)

    # Assert the result is what the mock returned
    assert result == mock_return
    # Assert the mock was called exactly once
    mock_get_relevant_context_for.assert_called_once()

    # Check the arguments passed to the mocked method
    # call_args is a tuple, first element is args tuple, second is kwargs dict
    # In this case, it's called like method(self, input_arg)
    # So call_args[0] should be (self_instance, input_arg)
    # We only care about input_arg
    assert len(mock_get_relevant_context_for.call_args.args) == 2 # self and input_data
    input_arg = mock_get_relevant_context_for.call_args.args[1]

    assert isinstance(input_arg, ContextGenerationInput)
    assert input_arg.query == context_desc # Crucial check: context_desc became the query
    assert input_arg.templateDescription is None # Or default value if model has one
    assert input_arg.inputs is None # Or default value

def test_get_relevant_context_for_case_insensitive_match(memory_system):
    """Verify matching is case-insensitive."""
    path1 = os.path.abspath("/path/case_test.py")
    meta1 = "Metadata with MixedCaseKeyword"
    memory_system.update_global_index({path1: meta1})
    input_data = ContextGenerationInput(query="mixedcasekeyword") # Lowercase query

    result = memory_system.get_relevant_context_for(input_data)

    assert len(result.matches) == 1
    assert result.matches[0].path == path1

    input_data_upper = ContextGenerationInput(query="MIXEDCASEKEYWORD") # Uppercase query
    result_upper = memory_system.get_relevant_context_for(input_data_upper)
    assert len(result_upper.matches) == 1
    assert result_upper.matches[0].path == path1

def test_get_relevant_context_for_no_query_or_description(memory_system):
    """Verify behavior when neither query nor templateDescription is provided."""
    memory_system.update_global_index({os.path.abspath("/path/some_file.py"): "some metadata"})
    input_data = ContextGenerationInput(inputs={"some": "input"}) # Only inputs

    result = memory_system.get_relevant_context_for(input_data)

    assert isinstance(result, AssociativeMatchResult)
    assert result.matches == []
    assert "No search criteria provided" in result.context_summary
    assert "No query or templateDescription provided" in result.error

# Test sharding path still uses global index for now
@patch('logging.debug')
def test_get_relevant_context_for_sharding_enabled_uses_global_index_phase2a(mock_log, memory_system):
    """Verify sharding path uses global index in Phase 2a."""
    path1 = os.path.abspath("/path/shard_test.py")
    meta1 = "Keyword for sharding test"
    memory_system.update_global_index({path1: meta1})
    memory_system.enable_sharding(True) # Enable sharding

    input_data = ContextGenerationInput(query="sharding test")
    result = memory_system.get_relevant_context_for(input_data)

    # Check that matching still worked
    assert len(result.matches) == 1
    assert result.matches[0].path == path1
    # Check that the debug log indicates global index was used despite sharding being enabled
    mock_log.assert_any_call("Sharding enabled, but using global index for Phase 2a matching.")
