"""
Unit tests for the FileAccessManager class.
"""

import os
import pytest
import logging # Add import
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime

# Attempt to import the class under test
try:
    from src.handler.file_access import FileAccessManager, DEFAULT_MAX_FILE_SIZE
except ImportError:
    pytest.skip("Skipping file_access tests, src.handler.file_access not found or dependencies missing", allow_module_level=True)

@pytest.fixture
def temp_dir():
    """Creates a temporary directory for test files."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def file_manager(temp_dir):
    """Creates a FileAccessManager instance using the temp directory as base."""
    return FileAccessManager(base_path=str(temp_dir))

# --- Test Initialization ---

def test_init_with_base_path(temp_dir):
    """Test initialization with an explicit base path."""
    manager = FileAccessManager(base_path=str(temp_dir))
    # Use realpath for comparison
    assert os.path.realpath(manager.base_path) == os.path.realpath(str(temp_dir.resolve()))

def test_init_without_base_path():
    """Test initialization without a base path (defaults to cwd)."""
    manager = FileAccessManager()
    assert manager.base_path == os.path.abspath(os.getcwd())

def test_init_with_nonexistent_base_path(caplog):
    """Test initialization with a non-existent base path (should still set path and log warning)."""
    non_existent_path = "/path/that/does/not/exist/hopefully"
    with caplog.at_level(logging.WARNING):
        manager = FileAccessManager(base_path=non_existent_path)
    # The path is still resolved, even if it doesn't exist, as per current implementation
    assert manager.base_path == os.path.abspath(non_existent_path)
    assert "does not exist or is not a directory" in caplog.text

# --- Test read_file ---

def test_read_file_success(file_manager, temp_dir):
    """Test reading a file successfully."""
    file_path = temp_dir / "test_read.txt"
    content = "Hello, world!\nThis is a test file."
    file_path.write_text(content, encoding='utf-8')

    read_content = file_manager.read_file("test_read.txt")
    assert read_content == content

def test_read_file_not_found(file_manager):
    """Test reading a non-existent file."""
    read_content = file_manager.read_file("non_existent_file.txt")
    assert read_content is None

def test_read_file_too_large(file_manager, temp_dir):
    """Test reading a file that exceeds the default max size."""
    file_path = temp_dir / "large_file.bin"
    # Create content slightly larger than the default limit
    large_content = b"A" * (DEFAULT_MAX_FILE_SIZE + 1)
    file_path.write_bytes(large_content)

    read_content = file_manager.read_file("large_file.bin")
    expected_error = f"File too large (size: {DEFAULT_MAX_FILE_SIZE + 1} bytes, limit: {DEFAULT_MAX_FILE_SIZE} bytes)"
    assert read_content == expected_error

def test_read_file_custom_max_size_success(file_manager, temp_dir):
    """Test reading a file within a custom max size."""
    file_path = temp_dir / "custom_size_test.txt"
    content = "Small file content."
    file_path.write_text(content, encoding='utf-8')
    custom_limit = len(content.encode('utf-8')) + 10 # Set limit larger than file

    read_content = file_manager.read_file("custom_size_test.txt", max_size=custom_limit)
    assert read_content == content

def test_read_file_custom_max_size_fail(file_manager, temp_dir):
    """Test reading a file exceeding a custom max size."""
    file_path = temp_dir / "custom_size_fail.txt"
    content = "This content will be too large."
    file_path.write_text(content, encoding='utf-8')
    custom_limit = 10 # Set limit smaller than file

    read_content = file_manager.read_file("custom_size_fail.txt", max_size=custom_limit)
    file_size = len(content.encode('utf-8'))
    expected_error = f"File too large (size: {file_size} bytes, limit: {custom_limit} bytes)"
    assert read_content == expected_error

def test_read_file_relative_path(file_manager, temp_dir):
    """Test reading a file using a relative path within the base."""
    sub_dir = temp_dir / "subdir"
    sub_dir.mkdir()
    file_path = sub_dir / "relative_test.txt"
    content = "Relative path test."
    file_path.write_text(content, encoding='utf-8')

    read_content = file_manager.read_file("subdir/relative_test.txt")
    assert read_content == content

def test_read_file_directory(file_manager, temp_dir):
    """Test attempting to read a directory."""
    dir_path = temp_dir / "a_directory"
    dir_path.mkdir()
    read_content = file_manager.read_file("a_directory")
    assert read_content is None # Should return None as it's not a file

def test_read_file_outside_base_path_fails(file_manager, temp_dir, caplog):
    """Test reading a file outside the base path fails due to safety check."""
    relative_path_unsafe = "../outside_read.txt"
    # Create a file outside the temp_dir to ensure it exists but is outside base
    outside_file = temp_dir.parent / "outside_read.txt"
    outside_file.write_text("Outside content", encoding='utf-8')

    with caplog.at_level(logging.ERROR):
        read_content = file_manager.read_file(relative_path_unsafe)

    assert read_content is None # Should fail safety check
    assert "Path safety check failed" in caplog.text
    # Clean up the outside file
    outside_file.unlink()


# --- Test get_file_info ---

def test_get_file_info_success(file_manager, temp_dir):
    """Test getting info for an existing file."""
    file_path = temp_dir / "info_test.txt"
    content = "File info test."
    file_path.write_text(content, encoding='utf-8')

    # Get expected values directly
    stat_result = file_path.stat()
    expected_size = stat_result.st_size
    expected_mtime = datetime.fromtimestamp(stat_result.st_mtime)

    info = file_manager.get_file_info("info_test.txt")

    assert "error" not in info
    # Use realpath for comparison
    assert os.path.realpath(info["path"]) == os.path.realpath(str(file_path.resolve()))
    assert info["size"] == f"{expected_size} bytes"
    # Compare timestamps loosely due to potential float precision differences
    assert abs(datetime.fromisoformat(info["modified"]) - expected_mtime).total_seconds() < 1

def test_get_file_info_not_found(file_manager):
    """Test getting info for a non-existent file."""
    info = file_manager.get_file_info("non_existent_info.txt")
    assert "error" in info
    assert "File not found" in info["error"]

def test_get_file_info_directory(file_manager, temp_dir):
    """Test getting info for a directory."""
    dir_path = temp_dir / "info_dir"
    dir_path.mkdir()
    info = file_manager.get_file_info("info_dir")
    assert "error" in info
    assert "not a regular file" in info["error"]

def test_get_file_info_relative_path(file_manager, temp_dir):
    """Test getting info using a relative path."""
    sub_dir = temp_dir / "info_subdir"
    sub_dir.mkdir()
    file_path = sub_dir / "relative_info.txt"
    content = "Relative info."
    file_path.write_text(content, encoding='utf-8')

    stat_result = file_path.stat()
    expected_size = stat_result.st_size
    expected_mtime = datetime.fromtimestamp(stat_result.st_mtime)

    info = file_manager.get_file_info("info_subdir/relative_info.txt")

    assert "error" not in info
    # Use realpath for comparison
    assert os.path.realpath(info["path"]) == os.path.realpath(str(file_path.resolve()))
    assert info["size"] == f"{expected_size} bytes"
    assert abs(datetime.fromisoformat(info["modified"]) - expected_mtime).total_seconds() < 1

def test_get_file_info_outside_base_path_fails(file_manager, temp_dir, caplog):
    """Test getting info for a file outside the base path fails due to safety check."""
    relative_path_unsafe = "../outside_info.txt"
    # Create a file outside the temp_dir to ensure it exists but is outside base
    outside_file = temp_dir.parent / "outside_info.txt"
    outside_file.write_text("Outside info", encoding='utf-8')

    with caplog.at_level(logging.ERROR):
        info = file_manager.get_file_info(relative_path_unsafe)

    assert "error" in info
    assert "Access denied" in info["error"] # Check for safety error message
    assert "Path safety check failed" in caplog.text
    # Clean up the outside file
    outside_file.unlink()


# --- NEW Tests for write_file ---

def test_write_file_creates_new_file(file_manager, temp_dir):
    """
    IDL Quote (write_file):
    - Postconditions: Returns true on success...
    - Behavior: Creates parent directories if needed. Writes content.
    """
    relative_path = "new_dir/new_file.txt"
    file_path = temp_dir / relative_path
    content = "Content for the new file."

    assert not file_path.exists() # Precondition: file doesn't exist
    assert not file_path.parent.exists() # Precondition: parent dir doesn't exist

    result = file_manager.write_file(relative_path, content, overwrite=False)

    assert result is True
    assert file_path.exists()
    assert file_path.is_file()
    assert file_path.parent.is_dir()
    assert file_path.read_text(encoding='utf-8') == content

def test_write_file_overwrites_existing(file_manager, temp_dir):
    """
    IDL Quote (write_file):
    - Postconditions: Returns true on success...
    - Behavior: Handles overwrite logic.
    """
    relative_path = "existing_file.txt"
    file_path = temp_dir / relative_path
    original_content = "Original content."
    new_content = "Overwritten content."
    file_path.write_text(original_content, encoding='utf-8') # Setup existing file

    result = file_manager.write_file(relative_path, new_content, overwrite=True)

    assert result is True
    assert file_path.exists()
    assert file_path.read_text(encoding='utf-8') == new_content # Check content updated

def test_write_file_no_overwrite_returns_false(file_manager, temp_dir):
    """
    IDL Quote (write_file):
    - Postconditions: Returns ... false on failure (e.g., ... file exists and overwrite=False).
    - Behavior: Handles overwrite logic.
    """
    relative_path = "existing_file_no_overwrite.txt"
    file_path = temp_dir / relative_path
    original_content = "Do not overwrite."
    file_path.write_text(original_content, encoding='utf-8') # Setup existing file

    result = file_manager.write_file(relative_path, "Attempted write", overwrite=False)

    assert result is False
    assert file_path.exists()
    assert file_path.read_text(encoding='utf-8') == original_content # Check content NOT changed

def test_write_file_path_is_directory(file_manager, temp_dir):
    """
    IDL Quote (write_file):
    - Postconditions: Returns ... false on failure ...
    - Behavior: Performs path safety check.
    """
    relative_path = "a_directory"
    dir_path = temp_dir / relative_path
    dir_path.mkdir() # Create a directory at the path

    result = file_manager.write_file(relative_path, "Content", overwrite=True)

    assert result is False # Should fail because path is a directory
    assert dir_path.is_dir() # Ensure it's still a directory

def test_write_file_outside_base_path_fails(file_manager, temp_dir, caplog):
    """
    IDL Quote (write_file):
    - Postconditions: Returns ... false on failure (e.g., path outside base...).
    - Behavior: Performs path safety check.
    """
    relative_path_unsafe = "../outside_write.txt"
    absolute_outside_path = temp_dir.parent / "outside_write.txt"

    assert not absolute_outside_path.exists()

    with caplog.at_level(logging.ERROR):
        result = file_manager.write_file(relative_path_unsafe, "Should not write")

    assert result is False
    assert not absolute_outside_path.exists()
    assert "Path safety check failed" in caplog.text # Check log message

def test_write_file_permission_error(file_manager, temp_dir, mocker):
    """
    IDL Quote (write_file):
    - Postconditions: Returns ... false on failure (e.g., ... permissions...).
    - Behavior: Handles exceptions.
    """
    relative_path = "permission_denied.txt"
    # Mock the 'open' builtin to raise PermissionError
    mock_open = mocker.patch("builtins.open", side_effect=PermissionError("Permission denied"))
    # Mock safety checks to allow reaching the open call
    mocker.patch.object(file_manager, '_is_path_safe', return_value=True)
    mocker.patch('os.path.exists', return_value=False) # Assume file doesn't exist
    mocker.patch('os.makedirs') # Assume parent dir creation works

    result = file_manager.write_file(relative_path, "Content")

    assert result is False
    # Check that open was called (or attempted)
    # The exact call depends on whether parent dirs needed creation
    mock_open.assert_called()


# --- NEW Tests for insert_content ---

def test_insert_content_success_middle(file_manager, temp_dir):
    """
    IDL Quote (insert_content):
    - Postconditions: Returns true on success...
    - Behavior: Reads existing content, inserts new content at position, writes back...
    """
    relative_path = "insert_test.txt"
    file_path = temp_dir / relative_path
    initial_content = "abcdef"
    insert_content = "XYZ"
    position = 3
    expected_content = "abcXYZdef"
    file_path.write_text(initial_content, encoding='utf-8')

    result = file_manager.insert_content(relative_path, insert_content, position)

    assert result is True
    # Read back as bytes to compare with internal logic
    assert file_path.read_bytes() == expected_content.encode('utf-8')

def test_insert_content_at_start(file_manager, temp_dir):
    """
    IDL Quote (insert_content):
    - Behavior: Reads existing content, inserts new content at position, writes back...
    """
    relative_path = "insert_start.txt"
    file_path = temp_dir / relative_path
    initial_content = "abcdef"
    insert_content = "XYZ"
    position = 0
    expected_content = "XYZabcdef"
    file_path.write_text(initial_content, encoding='utf-8')

    result = file_manager.insert_content(relative_path, insert_content, position)

    assert result is True
    assert file_path.read_bytes() == expected_content.encode('utf-8')

def test_insert_content_at_end(file_manager, temp_dir):
    """
    IDL Quote (insert_content):
    - Behavior: Reads existing content, inserts new content at position, writes back...
    """
    relative_path = "insert_end.txt"
    file_path = temp_dir / relative_path
    initial_content = "abcdef"
    insert_content = "XYZ"
    position = len(initial_content.encode('utf-8')) # Position 6 (byte length)
    expected_content = "abcdefXYZ"
    file_path.write_text(initial_content, encoding='utf-8')

    result = file_manager.insert_content(relative_path, insert_content, position)

    assert result is True
    assert file_path.read_bytes() == expected_content.encode('utf-8')

def test_insert_content_file_not_found(file_manager, caplog):
    """
    IDL Quote (insert_content):
    - Postconditions: Returns ... false on failure (e.g., ... file not found...).
    """
    relative_path = "non_existent_insert.txt"
    with caplog.at_level(logging.ERROR):
        result = file_manager.insert_content(relative_path, "XYZ", 0)
    assert result is False
    assert "File not found or not a file" in caplog.text

def test_insert_content_path_is_directory(file_manager, temp_dir, caplog):
    """
    IDL Quote (insert_content):
    - Postconditions: Returns ... false on failure (e.g., ... not a file...).
    """
    relative_path = "insert_dir"
    dir_path = temp_dir / relative_path
    dir_path.mkdir()

    with caplog.at_level(logging.ERROR):
        result = file_manager.insert_content(relative_path, "XYZ", 0)
    assert result is False
    assert "File not found or not a file" in caplog.text # Error because it's not a file

@pytest.mark.parametrize("position", [-1, 10]) # Test pos < 0 and pos > len
def test_insert_content_invalid_position(file_manager, temp_dir, position, caplog):
    """
    IDL Quote (insert_content):
    - Postconditions: Returns ... false on failure (e.g., ... invalid position...).
    - Preconditions: position is a non-negative integer within the file's bounds.
    """
    relative_path = "insert_pos_test.txt"
    file_path = temp_dir / relative_path
    initial_content = "abc" # Length 3 bytes
    file_path.write_text(initial_content, encoding='utf-8')

    with caplog.at_level(logging.ERROR):
        result = file_manager.insert_content(relative_path, "XYZ", position)

    assert result is False
    assert file_path.read_text(encoding='utf-8') == initial_content # Content unchanged
    assert "Invalid position" in caplog.text

def test_insert_content_outside_base_path_fails(file_manager, temp_dir, caplog):
    """
    IDL Quote (insert_content):
    - Postconditions: Returns ... false on failure (e.g., path outside base...).
    - Behavior: Performs path safety check.
    """
    relative_path_unsafe = "../outside_insert.txt"
    absolute_outside_path = temp_dir.parent / "outside_insert.txt"

    with caplog.at_level(logging.ERROR):
        result = file_manager.insert_content(relative_path_unsafe, "Should not insert", 0)

    assert result is False
    assert not absolute_outside_path.exists()
    assert "Path safety check failed" in caplog.text

def test_insert_content_permission_error_read(file_manager, temp_dir, mocker):
    """
    IDL Quote (insert_content):
    - Postconditions: Returns ... false on failure (e.g., ... permissions...).
    - Behavior: Handles exceptions.
    """
    relative_path = "read_permission_denied.txt"
    file_path = temp_dir / relative_path
    file_path.touch() # Create the file
    original_open = open # Store original open
    def open_mock(path, mode='r', *args, **kwargs):
        # Use file_manager's internal method to get the expected resolved path
        resolved_path = file_manager._resolve_path(relative_path)
        # Raise error only on read attempt for the target file
        if 'b' in mode and 'r' in mode and str(path) == resolved_path:
            raise PermissionError("Read permission denied")
        # Allow other calls (like potential writes if logic reached there)
        return original_open(path, mode, *args, **kwargs)

    mocker.patch("builtins.open", side_effect=open_mock)
    mocker.patch.object(file_manager, '_is_path_safe', return_value=True) # Assume path is safe

    result = file_manager.insert_content(relative_path, "Content", 0)
    assert result is False

def test_insert_content_permission_error_write(file_manager, temp_dir, mocker):
    """
    IDL Quote (insert_content):
    - Postconditions: Returns ... false on failure (e.g., ... permissions...).
    - Behavior: Handles exceptions.
    """
    relative_path = "write_permission_denied.txt"
    file_path = temp_dir / relative_path
    file_path.write_text("initial", encoding='utf-8') # Create file with initial content
    original_open = open # Store original open
    def open_mock(path, mode='r', *args, **kwargs):
        resolved_path = file_manager._resolve_path(relative_path)
        # Raise error only on write attempt for the target file
        if 'b' in mode and 'w' in mode and str(path) == resolved_path:
            raise PermissionError("Write permission denied")
        # Allow the initial read to succeed
        elif 'b' in mode and 'r' in mode and str(path) == resolved_path:
             return original_open(path, mode, *args, **kwargs)
        # Allow other calls
        return original_open(path, mode, *args, **kwargs)

    mocker.patch("builtins.open", side_effect=open_mock)
    mocker.patch.object(file_manager, '_is_path_safe', return_value=True) # Assume path is safe

    result = file_manager.insert_content(relative_path, "Content", 0)
    assert result is False
