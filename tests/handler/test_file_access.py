"""
Unit tests for the FileAccessManager class.
"""

import os
import pytest
import logging # Add import
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime
from unittest.mock import patch # Add patch

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

    with caplog.at_level(logging.ERROR): # Check for ERROR level logs
        read_content = file_manager.read_file(relative_path_unsafe)

    # Assertions
    assert read_content is None # Should return None on safety failure
    assert "Path safety check failed" in caplog.text # Check for the specific log message
    assert "is outside base" in caplog.text

    # Clean up the outside file
    outside_file.unlink()

# --- Test get_file_info ---

def test_get_file_info_success(file_manager, temp_dir):
    """Test getting info for an existing file."""
    file_path = temp_dir / "info_test.txt"
    content = "File info test."
    file_path.write_text(content, encoding='utf-8')
    # Get expected stats
    stat_result = file_path.stat()
    expected_size = stat_result.st_size
    expected_modified = datetime.fromtimestamp(stat_result.st_mtime).isoformat()

    info = file_manager.get_file_info("info_test.txt")

    assert isinstance(info, dict)
    assert "error" not in info
    assert info["path"] == str(file_path.resolve()) # Should be absolute path
    assert info["size"] == f"{expected_size} bytes"
    assert info["modified"] == expected_modified

def test_get_file_info_not_found(file_manager):
    """Test getting info for a non-existent file."""
    info = file_manager.get_file_info("non_existent_info.txt")
    assert isinstance(info, dict)
    assert "error" in info
    assert "not found" in info["error"].lower()

def test_get_file_info_directory(file_manager, temp_dir):
    """Test getting info for a directory."""
    dir_path = temp_dir / "info_dir"
    dir_path.mkdir()
    info = file_manager.get_file_info("info_dir")
    assert isinstance(info, dict)
    assert "error" in info
    assert "not a regular file" in info["error"].lower()

def test_get_file_info_outside_base_path_fails(file_manager, temp_dir, caplog):
    """Test getting info for a file outside the base path fails."""
    relative_path_unsafe = "../outside_info.txt"
    outside_file = temp_dir.parent / "outside_info.txt"
    outside_file.write_text("Outside info", encoding='utf-8')

    with caplog.at_level(logging.ERROR):
        info = file_manager.get_file_info(relative_path_unsafe)

    assert isinstance(info, dict)
    assert "error" in info
    assert "Access denied" in info["error"]
    assert "outside the allowed base directory" in info["error"]
    # Check log message from _is_path_safe
    assert "Path safety check failed" in caplog.text

    outside_file.unlink()

# --- Test write_file ---

def test_write_file_success_new(file_manager, temp_dir):
    """Test writing a new file successfully."""
    file_path_rel = "new_write.txt"
    file_path_abs = temp_dir / file_path_rel
    content = "Content for the new file."

    success = file_manager.write_file(file_path_rel, content)

    assert success is True
    assert file_path_abs.exists()
    assert file_path_abs.read_text(encoding='utf-8') == content

def test_write_file_success_overwrite_false_exists(file_manager, temp_dir):
    """Test writing fails if file exists and overwrite is False."""
    file_path_rel = "existing_write.txt"
    file_path_abs = temp_dir / file_path_rel
    initial_content = "Initial content."
    new_content = "New content."
    file_path_abs.write_text(initial_content, encoding='utf-8')

    success = file_manager.write_file(file_path_rel, new_content, overwrite=False)

    assert success is False # Should fail
    assert file_path_abs.read_text(encoding='utf-8') == initial_content # Content unchanged

def test_write_file_success_overwrite_true_exists(file_manager, temp_dir):
    """Test writing succeeds if file exists and overwrite is True."""
    file_path_rel = "overwrite_test.txt"
    file_path_abs = temp_dir / file_path_rel
    initial_content = "Initial content."
    new_content = "Overwritten content."
    file_path_abs.write_text(initial_content, encoding='utf-8')

    success = file_manager.write_file(file_path_rel, new_content, overwrite=True)

    assert success is True # Should succeed
    assert file_path_abs.read_text(encoding='utf-8') == new_content # Content updated

def test_write_file_creates_parent_dirs(file_manager, temp_dir):
    """Test writing creates necessary parent directories."""
    file_path_rel = "newdir/subdir/created.txt"
    file_path_abs = temp_dir / file_path_rel
    content = "Content in created subdir."

    success = file_manager.write_file(file_path_rel, content)

    assert success is True
    assert file_path_abs.exists()
    assert file_path_abs.read_text(encoding='utf-8') == content
    assert (temp_dir / "newdir").is_dir()
    assert (temp_dir / "newdir" / "subdir").is_dir()

def test_write_file_cannot_write_to_directory(file_manager, temp_dir):
    """Test writing fails if the target path is a directory."""
    dir_path_rel = "a_dir_to_write_to"
    dir_path_abs = temp_dir / dir_path_rel
    dir_path_abs.mkdir()
    content = "Trying to write to a directory."

    success = file_manager.write_file(dir_path_rel, content)

    assert success is False
    assert dir_path_abs.is_dir() # Should still be a directory

def test_write_file_outside_base_path_fails(file_manager, temp_dir, caplog):
    """Test writing to a file outside the base path fails."""
    relative_path_unsafe = "../outside_write.txt"
    content = "Cannot write this."

    with caplog.at_level(logging.ERROR):
        success = file_manager.write_file(relative_path_unsafe, content)

    assert success is False
    assert not (temp_dir.parent / "outside_write.txt").exists()
    assert "Path safety check failed" in caplog.text

@patch('src.handler.file_access.os.makedirs')
def test_write_file_parent_dir_creation_fails(mock_makedirs, file_manager, temp_dir, caplog):
    """Test write failure if parent directory creation fails."""
    mock_makedirs.side_effect = OSError("Permission denied creating dir")
    file_path_rel = "uncreatable_dir/file.txt"
    content = "Some content."

    with caplog.at_level(logging.ERROR):
        success = file_manager.write_file(file_path_rel, content)

    assert success is False
    assert not (temp_dir / file_path_rel).exists()
    assert "Failed to create parent directory" in caplog.text
    assert "Permission denied creating dir" in caplog.text

@patch('builtins.open', side_effect=IOError("Disk full"))
def test_write_file_io_error(mock_open, file_manager, temp_dir, caplog):
    """Test write failure due to underlying IO error."""
    file_path_rel = "io_error_test.txt"
    content = "Content that fails."

    with caplog.at_level(logging.ERROR):
        success = file_manager.write_file(file_path_rel, content)

    assert success is False
    assert "Error writing to file" in caplog.text
    assert "Disk full" in caplog.text

# --- Test insert_content ---

def test_insert_content_success_start(file_manager, temp_dir):
    """Test inserting content at the beginning of a file."""
    file_path_rel = "insert_start.txt"
    file_path_abs = temp_dir / file_path_rel
    initial_content = "world!"
    insert_content = "Hello, "
    expected_content = "Hello, world!"
    file_path_abs.write_text(initial_content, encoding='utf-8')

    success = file_manager.insert_content(file_path_rel, insert_content, 0)

    assert success is True
    assert file_path_abs.read_text(encoding='utf-8') == expected_content

def test_insert_content_success_middle(file_manager, temp_dir):
    """Test inserting content in the middle of a file."""
    file_path_rel = "insert_middle.txt"
    file_path_abs = temp_dir / file_path_rel
    initial_content = "Hello !"
    insert_content = "world"
    expected_content = "Hello world!"
    # Position is byte offset, assume UTF-8
    position = len("Hello ".encode('utf-8'))
    file_path_abs.write_text(initial_content, encoding='utf-8')

    success = file_manager.insert_content(file_path_rel, insert_content, position)

    assert success is True
    assert file_path_abs.read_text(encoding='utf-8') == expected_content

def test_insert_content_success_end(file_manager, temp_dir):
    """Test inserting content at the end of a file."""
    file_path_rel = "insert_end.txt"
    file_path_abs = temp_dir / file_path_rel
    initial_content = "Hello, "
    insert_content = "world!"
    expected_content = "Hello, world!"
    position = len(initial_content.encode('utf-8'))
    file_path_abs.write_text(initial_content, encoding='utf-8')

    success = file_manager.insert_content(file_path_rel, insert_content, position)

    assert success is True
    assert file_path_abs.read_text(encoding='utf-8') == expected_content

def test_insert_content_file_not_found(file_manager, caplog):
    """Test inserting content into a non-existent file."""
    with caplog.at_level(logging.ERROR):
        success = file_manager.insert_content("non_existent_insert.txt", "content", 0)

    assert success is False
    assert "File not found or not a file" in caplog.text

def test_insert_content_invalid_position_negative(file_manager, temp_dir, caplog):
    """Test inserting content at a negative position."""
    file_path_rel = "insert_neg_pos.txt"
    file_path_abs = temp_dir / file_path_rel
    file_path_abs.write_text("abc", encoding='utf-8')

    with caplog.at_level(logging.ERROR):
        success = file_manager.insert_content(file_path_rel, "content", -1)

    assert success is False
    assert "Invalid position" in caplog.text

def test_insert_content_invalid_position_too_large(file_manager, temp_dir, caplog):
    """Test inserting content at a position beyond the file size."""
    file_path_rel = "insert_large_pos.txt"
    file_path_abs = temp_dir / file_path_rel
    initial_content = "abc"
    file_path_abs.write_text(initial_content, encoding='utf-8')
    position = len(initial_content.encode('utf-8')) + 1 # One byte past the end

    with caplog.at_level(logging.ERROR):
        success = file_manager.insert_content(file_path_rel, "content", position)

    assert success is False
    assert "Invalid position" in caplog.text

def test_insert_content_outside_base_path_fails(file_manager, temp_dir, caplog):
    """Test inserting content into a file outside the base path fails."""
    relative_path_unsafe = "../outside_insert.txt"
    outside_file = temp_dir.parent / "outside_insert.txt"
    outside_file.write_text("Initial outside", encoding='utf-8')

    with caplog.at_level(logging.ERROR):
        success = file_manager.insert_content(relative_path_unsafe, "inserted", 0)

    assert success is False
    assert outside_file.read_text(encoding='utf-8') == "Initial outside" # Unchanged
    assert "Path safety check failed" in caplog.text

    outside_file.unlink()

@patch('builtins.open', side_effect=IOError("Read failed"))
def test_insert_content_read_error(mock_open_read_fail, file_manager, temp_dir, caplog):
    """Test insert failure if reading the existing file fails."""
    # Need to make the file exist first so it tries to open
    file_path_rel = "insert_read_fail.txt"
    file_path_abs = temp_dir / file_path_rel
    file_path_abs.touch() # Create empty file

    # Mock 'open' to fail on the first read attempt
    mock_open_read_fail.side_effect = IOError("Read failed")

    with caplog.at_level(logging.ERROR):
        success = file_manager.insert_content(file_path_rel, "content", 0)

    assert success is False
    assert "Error reading existing file" in caplog.text
    assert "Read failed" in caplog.text

# --- Test list_directory ---

def test_list_directory_success(file_manager, temp_dir):
    """Test listing contents of a directory successfully."""
    # Arrange: Create files and a subdirectory
    (temp_dir / "file1.txt").touch()
    (temp_dir / "file2.py").touch()
    sub_dir = temp_dir / "subdir"
    sub_dir.mkdir()
    (sub_dir / "subfile.log").touch()
    expected_contents = sorted(["file1.txt", "file2.py", "subdir"])

    # Act
    result = file_manager.list_directory(".") # List base directory

    # Assert
    assert isinstance(result, list)
    assert sorted(result) == expected_contents

def test_list_directory_subdir_success(file_manager, temp_dir):
    """Test listing contents of a subdirectory."""
    # Arrange
    sub_dir = temp_dir / "subdir"
    sub_dir.mkdir()
    (sub_dir / "subfile1.log").touch()
    (sub_dir / "subfile2.dat").touch()
    expected_contents = sorted(["subfile1.log", "subfile2.dat"])

    # Act
    result = file_manager.list_directory("subdir")

    # Assert
    assert isinstance(result, list)
    assert sorted(result) == expected_contents

def test_list_directory_empty(file_manager, temp_dir):
    """Test listing an empty directory."""
    # Arrange
    empty_dir = temp_dir / "empty_dir"
    empty_dir.mkdir()

    # Act
    result = file_manager.list_directory("empty_dir")

    # Assert
    assert isinstance(result, list)
    assert result == []

def test_list_directory_not_found(file_manager, caplog):
    """Test listing a non-existent path."""
    with caplog.at_level(logging.WARNING):
        result = file_manager.list_directory("non_existent_dir")

    assert isinstance(result, dict)
    assert "error" in result
    assert "Path not found" in result["error"]
    assert "Path not found" in caplog.text

def test_list_directory_is_file(file_manager, temp_dir, caplog):
    """Test listing a path that is a file, not a directory."""
    # Arrange
    file_path = temp_dir / "a_file.txt"
    file_path.touch()

    with caplog.at_level(logging.WARNING):
        result = file_manager.list_directory("a_file.txt")

    assert isinstance(result, dict)
    assert "error" in result
    assert "Path is not a valid directory" in result["error"]
    assert "Path is not a directory" in caplog.text

@patch('src.handler.file_access.os.listdir', side_effect=PermissionError("Permission denied"))
def test_list_directory_permission_error(mock_listdir, file_manager, temp_dir, caplog):
    """Test listing when os.listdir raises PermissionError."""
    # Arrange: Need a directory to attempt listing
    target_dir = temp_dir / "restricted_dir"
    target_dir.mkdir()

    with caplog.at_level(logging.ERROR):
        result = file_manager.list_directory("restricted_dir")

    assert isinstance(result, dict)
    assert "error" in result
    assert "Permission denied or OS error" in result["error"]
    assert "Error listing directory" in caplog.text
    assert "Permission denied" in caplog.text
    mock_listdir.assert_called_once_with(str(target_dir.resolve()))

def test_list_directory_outside_base(file_manager, temp_dir, caplog):
    """Test listing a directory outside the allowed base path."""
    # Arrange: Create a directory outside the base to ensure it exists
    outside_dir = temp_dir.parent / "outside_dir_list"
    outside_dir.mkdir(exist_ok=True) # Create if not exists

    with caplog.at_level(logging.ERROR):
        result = file_manager.list_directory("../outside_dir_list")

    assert isinstance(result, dict)
    assert "error" in result
    assert "Access denied" in result["error"]
    assert "outside the allowed base directory" in result["error"]
    assert "Path safety check failed" in caplog.text

    # Clean up
    outside_dir.rmdir()
