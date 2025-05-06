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

    with caplog.at