import pytest
from unittest.mock import MagicMock, patch

# Import the function under test
from src.task_system.file_path_resolver import resolve_paths_from_template

# Import necessary types/classes for mocking/data
from src.memory.memory_system import MemorySystem
from src.handler.base_handler import BaseHandler
from src.system.models import ContextGenerationInput, MatchItem, AssociativeMatchResult # Changed MatchTuple to MatchItem

# Add fixtures if needed (e.g., mock memory/handler)
@pytest.fixture
def mock_memory_system_fp(): # Use different name to avoid conflict if run together
    """Fixture for a mocked MemorySystem for file path tests."""
    mock_ms = MagicMock(spec=MemorySystem)
    # Ensure get_relevant_context_for is an AsyncMock
    mock_ms.get_relevant_context_for = AsyncMock()
    return mock_ms

@pytest.fixture
def mock_handler_fp(): # Use different name
    """Fixture for a mocked BaseHandler for file path tests."""
    handler = MagicMock(spec=BaseHandler)
    handler.execute_file_path_command.return_value = ["/path/from/command.py"]
    return handler

# Test resolving file paths using a command
def test_resolve_paths_command(mock_handler_fp):
    """Test resolving file paths using a command."""
    # Arrange
    expected_paths = ["/path/from/command.py"]
    # Configure the mock handler instance directly
    template = {
        "file_paths_source": {
            "type": "command",
            "command": "find . -name '*.py'"
        }
    }
    # Act
    paths, error = resolve_paths_from_template(template, None, mock_handler_fp) # Memory not needed here

    # Assert
    assert error is None
    assert paths == expected_paths
    # Verify the call on the mock handler instance
    mock_handler_fp.execute_file_path_command.assert_called_once_with("find . -name '*.py'")

# Test resolving file paths using a description
@pytest.mark.asyncio
async def test_resolve_paths_description(mock_memory_system_fp):
    """Test resolving file paths using a description."""
    # Arrange
    expected_path = "/matched/desc.go"
    template = {
        "description": "Find Go files", # Used if specific desc missing
        "file_paths_source": {
            "type": "description",
            "description": "Relevant Go source files" # Specific description
        }
    }
    # Configure the return value on the AsyncMock directly
    mock_memory_system_fp.get_relevant_context_for.return_value = AssociativeMatchResult(
        context_summary="Desc match",
        matches=[MatchItem(id=expected_path, content="mock content", relevance_score=0.9, content_type="file_content")], # Use MatchItem
        error=None
    )

    # Act
    paths, error = await resolve_paths_from_template(template, mock_memory_system_fp, None) # Handler not needed

    # Assert - Check the call on the mock created by 'with'
    mock_memory_system_fp.get_relevant_context_for.assert_awaited_once()
    call_args, call_kwargs = mock_memory_system_fp.get_relevant_context_for.call_args
    assert len(call_args) == 1
    assert isinstance(call_args[0], ContextGenerationInput)
    assert call_args[0].query == "Relevant Go source files" # Check the query used
    
    # Assert results outside the 'with' block
    assert error is None
    assert paths == [expected_path]

# Test resolving file paths using context_description
@pytest.mark.asyncio
async def test_resolve_paths_context_description(mock_memory_system_fp):
    """Test resolving file paths using context_description."""
    # Arrange
    expected_path = "/matched/context.rs"
    template = {
        "file_paths_source": {
            "type": "context_description",
            "context_query": "Find Rust files about parsing"
        }
    }
    
    # Configure the return value on the AsyncMock directly
    mock_memory_system_fp.get_relevant_context_for.return_value = AssociativeMatchResult(
        context_summary="Context match",
        matches=[MatchItem(id=expected_path, content="mock content", relevance_score=0.85, content_type="file_content")], # Use MatchItem
        error=None
    )
        
    # Act
    paths, error = await resolve_paths_from_template(template, mock_memory_system_fp, None) # Handler not needed

    # Assert - Check the call on the mock created by 'with'
    mock_memory_system_fp.get_relevant_context_for.assert_awaited_once()
    # Get the actual call arguments
    call_args, call_kwargs = mock_memory_system_fp.get_relevant_context_for.call_args
    # Assert the structure and relevant content of the ContextGenerationInput argument
    assert len(call_args) == 1
    assert isinstance(call_args[0], ContextGenerationInput)
    assert call_args[0].query == "Find Rust files about parsing" # Check the query used
    
    # Assert results outside the 'with' block
    assert error is None
    assert paths == [expected_path]

# Test resolving file paths using literal paths
@pytest.mark.asyncio
async def test_resolve_paths_literal():
    """Test resolving file paths using literal paths."""
    # Arrange
    expected_paths = ["/literal/a.txt", "/literal/b.txt"]
    template = {
        "file_paths": expected_paths # Literal paths at top level
    }
    # Act
    paths, error = await resolve_paths_from_template(template, None, None)

    # Assert
    assert error is None
    assert paths == expected_paths

    # Arrange - Literal paths inside source element
    template_in_source = {
        "file_paths_source": {
            "type": "literal",
            "path": expected_paths # Changed key to 'path'
        }
    }
    # Act
    paths_in_source, error_in_source = await resolve_paths_from_template(template_in_source, None, None)

    # Assert
    assert error_in_source is None
    assert paths_in_source == expected_paths

    # Arrange - Literal paths specified via file_paths_source with type literal but no path key
    template_literal_no_path = {
        "file_paths_source": { "type": "literal" }
    }
    # Act
    paths_no_path, error_no_path = await resolve_paths_from_template(template_literal_no_path, None, None)
    # Assert
    assert error_no_path is None
    assert paths_no_path == [] # Should default to empty list

# Test error handling for missing information
@pytest.mark.asyncio
async def test_resolve_paths_missing_info(mock_handler_fp):
    """Test error handling for missing information in resolve_paths_from_template."""
    # Command missing
    template_cmd = {"file_paths_source": {"type": "command"}}
    paths, error = await resolve_paths_from_template(template_cmd, None, mock_handler_fp)
    assert error == "Missing command in file_paths_source type 'command'"
    assert paths == []

    # Description missing
    template_desc = {"file_paths_source": {"type": "description"}}
    paths, error = await resolve_paths_from_template(template_desc, MagicMock(), None)
    assert error == "Missing description for file_paths_source type 'description'"
    assert paths == []

    # Context query missing
    template_ctx = {"file_paths_source": {"type": "context_description"}}
    paths, error = await resolve_paths_from_template(template_ctx, MagicMock(), None)
    assert error == "Missing context_query for file_paths_source type 'context_description'"
    assert paths == []

# Test handling of unknown source type
@pytest.mark.asyncio
async def test_resolve_paths_unknown_type():
    """Test handling of unknown source type."""
    template = {"file_paths_source": {"type": "magic"}}
    paths, error = await resolve_paths_from_template(template, None, None)
    assert error == "Unknown file_paths_source type: magic"
    assert paths == []
