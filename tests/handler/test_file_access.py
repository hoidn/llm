"""
Unit tests for the FileAccessManager class.
"""

import os
import pytest
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
    assert manager.base_path == str(temp_dir.resolve())

def test_init_without_base_path():
    """Test initialization without a base path (defaults to cwd)."""
    manager = FileAccessManager()
    assert manager.base_path == os.path.abspath(os.getcwd())

def test_init_with_nonexistent_base_path():
    """Test initialization with a non-existent base path (should still set path)."""
    non_existent_path = "/path/that/does/not/exist/hopefully"
    manager = FileAccessManager(base_path=non_existent_path)
    # The path is still resolved, even if it doesn't exist, as per current implementation
    assert manager.base_path == os.path.abspath(non_existent_path)

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
    assert info["path"] == str(file_path.resolve())
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
    assert info["path"] == str(file_path.resolve())
    assert info["size"] == f"{expected_size} bytes"
    assert abs(datetime.fromisoformat(info["modified"]) - expected_mtime).total_seconds() < 1
