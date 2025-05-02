# tests/tools/test_anthropic_tools.py

import pytest
from unittest.mock import MagicMock, patch, call, ANY # Import ANY
import os

# Import functions and specifications under test
# Adjust path if your structure differs slightly
from src.tools import anthropic_tools
from src.handler.file_access import FileAccessManager # For mock spec
from pydantic import ValidationError # For testing validation

# --- Fixtures ---

@pytest.fixture
def mock_file_manager():
    """Provides a mock FileAccessManager instance."""
    mock = MagicMock(spec=FileAccessManager)
    # Default behavior: assume path is safe, file exists, return content
    # Make _is_path_safe readily available on the mock instance
    mock._is_path_safe = MagicMock(return_value=True)
    # Mock _resolve_path to simulate path normalization
    mock._resolve_path = MagicMock(side_effect=lambda p: f"/abs/{p}" if p else p)
    mock.read_file.return_value = "Initial file content.\nLine 2."
    mock.write_file.return_value = True
    mock.insert_content.return_value = True
    # Mock os.path functions used by tools or _normalize_path
    with patch('os.path.exists', return_value=True), \
         patch('os.path.isfile', return_value=True), \
         patch('os.path.getsize', return_value=100), \
         patch('os.path.abspath', side_effect=lambda p: f"/abs/{p}" if p else p): # Handle empty path case in abspath mock
        yield mock

# --- Tests for view ---

def test_view_success(mock_file_manager):
    """Test successful view operation."""
    result = anthropic_tools.view(mock_file_manager, file_path="test.txt")
    assert result == "Initial file content.\nLine 2."
    # Check read_file call on the MOCK instance using the relative path
    mock_file_manager.read_file.assert_called_once_with("test.txt", max_size=anthropic_tools.DEFAULT_MAX_FILE_SIZE)
    mock_file_manager._resolve_path.assert_called_once_with("test.txt")

def test_view_file_not_found(mock_file_manager):
    """Test view when file does not exist."""
    # Simulate file not found at the os level for this test
    with patch('os.path.exists', return_value=False):
        result = anthropic_tools.view(mock_file_manager, file_path="not_found.txt")
    assert "Error: File not found" in result
    assert "/abs/not_found.txt" in result
    # FileAccessManager.read_file should NOT be called if os.path.exists is False
    mock_file_manager.read_file.assert_not_called()
    mock_file_manager._resolve_path.assert_called_once_with("not_found.txt")

def test_view_too_large(mock_file_manager):
    """Test view when file is too large."""
    # Simulate file size check failing
    with patch('os.path.getsize', return_value=150 * 1024): # > DEFAULT_MAX_FILE_SIZE
         result = anthropic_tools.view(mock_file_manager, file_path="large.txt")
    assert "Error: File too large" in result
    assert "153600 bytes" in result # 150 * 1024
    assert f"limit: {anthropic_tools.DEFAULT_MAX_FILE_SIZE} bytes" in result
    mock_file_manager.read_file.assert_not_called() # Should fail before reading
    mock_file_manager._resolve_path.assert_called_once_with("large.txt")

def test_view_unsafe_path(mock_file_manager):
    """Test view with a path considered unsafe."""
    # Simulate _resolve_path raising ValueError for unsafe path
    mock_file_manager._resolve_path.side_effect = ValueError("Unsafe path detected")
    result = anthropic_tools.view(mock_file_manager, file_path="../etc/passwd")
    assert "Error: Invalid path: Unsafe path detected" in result
    mock_file_manager.read_file.assert_not_called()
    mock_file_manager._resolve_path.assert_called_once_with("../etc/passwd")

def test_view_invalid_input_empty_path(mock_file_manager):
    """Test view with empty file path causing validation error."""
    # Pydantic validation should catch this
    with pytest.raises(ValidationError):
         anthropic_tools.ViewInput(file_path="")

    # Test the function call directly to check its error handling
    result = anthropic_tools.view(mock_file_manager, file_path="") # Empty path
    assert "Error: Invalid input" in result
    assert "File path cannot be empty" in result # Check for Pydantic error message
    mock_file_manager.read_file.assert_not_called()
    # _resolve_path should not be called if validation fails first
    mock_file_manager._resolve_path.assert_not_called()


def test_view_with_line_range(mock_file_manager):
    """Test view with start and end line numbers."""
    mock_file_manager.read_file.return_value = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    result = anthropic_tools.view(mock_file_manager, file_path="range.txt", start_line=2, end_line=4)
    assert result == "Line 2\nLine 3\nLine 4" # Includes trailing newline of line 4
    mock_file_manager.read_file.assert_called_once_with("range.txt", max_size=anthropic_tools.DEFAULT_MAX_FILE_SIZE)
    mock_file_manager._resolve_path.assert_called_once_with("range.txt")

def test_view_with_invalid_line_range(mock_file_manager):
    """Test view with invalid line numbers."""
    mock_file_manager.read_file.return_value = "Line 1\nLine 2"
    # Test Pydantic validation first
    with pytest.raises(ValidationError):
        anthropic_tools.ViewInput(file_path="a.txt", start_line=0) # ge=1
    with pytest.raises(ValidationError):
        anthropic_tools.ViewInput(file_path="a.txt", end_line=0) # ge=1

    # Test function logic for range checks relative to content
    result_start_high = anthropic_tools.view(mock_file_manager, file_path="a.txt", start_line=3) # Only 2 lines
    assert "Error: Start line out of range: 3 (File has 2 lines)" in result_start_high
    result_end_high = anthropic_tools.view(mock_file_manager, file_path="a.txt", end_line=5) # Only 2 lines
    assert "Error: End line out of range: 5 (File has 2 lines)" in result_end_high
    result_start_gt_end = anthropic_tools.view(mock_file_manager, file_path="a.txt", start_line=2, end_line=1)
    assert "Error: Start line (2) must be less than or equal to end line (1)" in result_start_gt_end


# --- Tests for str_replace ---

def test_str_replace_success(mock_file_manager):
    """Test successful string replacement."""
    mock_file_manager.read_file.return_value = "Replace old string here, old string."
    result = anthropic_tools.str_replace(
        mock_file_manager, file_path="replace_me.txt", old_string="old string", new_string="new text", count=1 # Explicit count=1
    )
    assert result == "Successfully replaced 1 occurrence(s)"
    mock_file_manager.read_file.assert_called_once_with("replace_me.txt", max_size=None)
    # Check write_file call content
    mock_file_manager.write_file.assert_called_once_with("replace_me.txt", "Replace new text here, old string.", overwrite=True) # Overwrite is True for replace
    mock_file_manager._resolve_path.assert_called_once_with("replace_me.txt")

def test_str_replace_all_occurrences(mock_file_manager):
    """Test replacing all occurrences."""
    mock_file_manager.read_file.return_value = "old text old text old text"
    result = anthropic_tools.str_replace(
        mock_file_manager, file_path="replace_all.txt", old_string="old", new_string="new", count=-1
    )
    assert result == "Successfully replaced 3 occurrence(s)"
    mock_file_manager.write_file.assert_called_once_with("replace_all.txt", "new text new text new text", overwrite=True)
    mock_file_manager._resolve_path.assert_called_once_with("replace_all.txt")

def test_str_replace_no_match(mock_file_manager):
    """Test replacement when the old string is not found."""
    mock_file_manager.read_file.return_value = "Some other content."
    result = anthropic_tools.str_replace(
        mock_file_manager, file_path="no_match.txt", old_string="missing", new_string="new"
    )
    assert result == "No matches found for replacement"
    mock_file_manager.read_file.assert_called_once()
    mock_file_manager.write_file.assert_not_called()
    mock_file_manager._resolve_path.assert_called_once_with("no_match.txt")

def test_str_replace_invalid_input_empty_old(mock_file_manager):
    """Test str_replace with empty old_string."""
    # Pydantic validation should catch this
    with pytest.raises(ValidationError):
        anthropic_tools.StrReplaceInput(file_path="a.txt", old_string="", new_string="b")

    # Test function call
    result = anthropic_tools.str_replace(mock_file_manager, file_path="a.txt", old_string="", new_string="b")
    assert "Error: Invalid input" in result
    assert "Old string cannot be empty" in result
    mock_file_manager.read_file.assert_not_called()
    mock_file_manager.write_file.assert_not_called()
    mock_file_manager._resolve_path.assert_not_called()

def test_str_replace_file_access_error(mock_file_manager):
    """Test str_replace when file reading fails."""
    mock_file_manager.read_file.side_effect = IOError("Disk read error")
    result = anthropic_tools.str_replace(mock_file_manager, file_path="a.txt", old_string="a", new_string="b")
    assert "Error: Error processing file: Disk read error" in result
    mock_file_manager.read_file.assert_called_once()
    mock_file_manager.write_file.assert_not_called()
    mock_file_manager._resolve_path.assert_called_once_with("a.txt")


# --- Tests for create ---

def test_create_success_new_file(mock_file_manager):
    """Test creating a new file."""
    # Simulate file not existing initially
    with patch('os.path.exists', return_value=False), \
         patch('os.makedirs') as mock_makedirs:
        result = anthropic_tools.create(mock_file_manager, file_path="new_file.txt", content="New content.")
    assert result == "Successfully created file: /abs/new_file.txt"
    # FAM write_file should handle makedirs
    # mock_makedirs.assert_called_once_with(os.path.dirname("/abs/new_file.txt"), exist_ok=True)
    # Check that write_file was called correctly
    mock_file_manager.write_file.assert_called_once_with("new_file.txt", "New content.", overwrite=False)
    mock_file_manager._resolve_path.assert_called_once_with("new_file.txt")

def test_create_success_overwrite(mock_file_manager):
    """Test creating a file that exists with overwrite=True."""
    # Simulate file existing
    with patch('os.path.exists', return_value=True), \
         patch('os.makedirs') as mock_makedirs: # makedirs might still be called even if file exists
        result = anthropic_tools.create(mock_file_manager, file_path="existing.txt", content="Overwritten", overwrite=True)
    # The success message checks the absolute path, which is correct
    assert result == "Successfully overwritten file: /abs/existing.txt"
    # mock_makedirs.assert_called_once_with(os.path.dirname("/abs/existing.txt"), exist_ok=True)
    mock_file_manager.write_file.assert_called_once_with("existing.txt", "Overwritten", overwrite=True)
    mock_file_manager._resolve_path.assert_called_once_with("existing.txt")

def test_create_fail_exists_no_overwrite(mock_file_manager):
    """Test create fails if file exists and overwrite is False."""
    # Simulate file existing
    with patch('os.path.exists', return_value=True):
        result = anthropic_tools.create(mock_file_manager, file_path="existing.txt", content="Should fail", overwrite=False)
    assert "Error: File already exists" in result
    assert "Use overwrite=True" in result
    mock_file_manager.write_file.assert_not_called()
    mock_file_manager._resolve_path.assert_called_once_with("existing.txt")

def test_create_fail_write_error(mock_file_manager):
    """Test create fails if FileAccessManager.write_file returns False."""
    mock_file_manager.write_file.return_value = False # Simulate write failure
    # Simulate file not existing initially
    with patch('os.path.exists', return_value=False), \
         patch('os.makedirs'):
        result = anthropic_tools.create(mock_file_manager, file_path="write_fail.txt", content="abc")
    # The tool should propagate the failure, likely as a generic error if write_file doesn't provide details
    assert "Error: Error creating file" in result # Check for generic error message
    mock_file_manager.write_file.assert_called_once()
    mock_file_manager._resolve_path.assert_called_once_with("write_fail.txt")

def test_create_invalid_input_empty_path(mock_file_manager):
    """Test create with empty file path."""
    with pytest.raises(ValidationError):
        anthropic_tools.CreateInput(file_path="", content="abc")

    result = anthropic_tools.create(mock_file_manager, file_path="", content="abc")
    assert "Error: Invalid input" in result
    assert "File path cannot be empty" in result
    mock_file_manager.write_file.assert_not_called()
    mock_file_manager._resolve_path.assert_not_called()

# --- Tests for insert ---

def test_insert_success_middle(mock_file_manager):
    """Test successful insertion in the middle."""
    # Need to mock getsize for position validation
    with patch('os.path.getsize', return_value=6):
        result = anthropic_tools.insert(mock_file_manager, file_path="insert_here.txt", content="XYZ", position=3)
    assert result == "Successfully inserted content at position 3"
    # Check insert_content call on the MOCK instance
    mock_file_manager.insert_content.assert_called_once_with("insert_here.txt", "XYZ", 3)
    mock_file_manager._resolve_path.assert_called_once_with("insert_here.txt")

def test_insert_success_line_before(mock_file_manager):
    """Test successful insertion before a specific line."""
    mock_file_manager.read_file.return_value = "Line 1\nLine 2\nLine 3"
    result = anthropic_tools.insert(mock_file_manager, file_path="insert_line.txt", content="Inserted Line", line=2) # Insert before line 2
    assert result == "Successfully inserted content before line 2"
    # Calculate expected position (length of "Line 1\n")
    expected_pos = len("Line 1\n")
    mock_file_manager.insert_content.assert_called_once_with("insert_line.txt", "Inserted Line\n", expected_pos) # Check newline added
    mock_file_manager._resolve_path.assert_called_once_with("insert_line.txt")

def test_insert_success_line_after(mock_file_manager):
    """Test successful insertion after a specific line."""
    mock_file_manager.read_file.return_value = "Line 1\nLine 2\nLine 3"
    result = anthropic_tools.insert(mock_file_manager, file_path="insert_after.txt", content="Inserted After", line=2, after_line=True) # Insert after line 2
    assert result == "Successfully inserted content after line 2"
    # Calculate expected position (length of "Line 1\nLine 2\n")
    expected_pos = len("Line 1\nLine 2\n")
    # Check content includes newline added by the function
    mock_file_manager.insert_content.assert_called_once_with("insert_after.txt", "Inserted After\n", expected_pos)
    mock_file_manager._resolve_path.assert_called_once_with("insert_after.txt")

def test_insert_fail_no_position_or_line(mock_file_manager):
    """Test insert fails if neither position nor line is given."""
    result = anthropic_tools.insert(mock_file_manager, file_path="a.txt", content="abc")
    assert "Error: Must specify either position or line" in result
    mock_file_manager.insert_content.assert_not_called()
    # Path normalization might still happen before the check
    mock_file_manager._resolve_path.assert_called_once_with("a.txt")


def test_insert_fail_both_position_and_line(mock_file_manager):
    """Test insert fails if both position and line are given."""
    result = anthropic_tools.insert(mock_file_manager, file_path="a.txt", content="abc", position=1, line=1)
    assert "Error: Cannot specify both position and line" in result
    mock_file_manager.insert_content.assert_not_called()
    mock_file_manager._resolve_path.assert_called_once_with("a.txt")

def test_insert_fail_invalid_position_negative(mock_file_manager):
    """Test insert fails with negative position."""
    with pytest.raises(ValidationError):
        anthropic_tools.InsertInput(file_path="a.txt", content="abc", position=-1)

    result = anthropic_tools.insert(mock_file_manager, file_path="a.txt", content="abc", position=-1)
    assert "Error: Invalid input" in result
    assert "Position cannot be negative" in result # Check specific validation message if possible
    mock_file_manager.insert_content.assert_not_called()
    mock_file_manager._resolve_path.assert_not_called() # Validation fails first

def test_insert_fail_invalid_position_out_of_bounds(mock_file_manager):
    """Test insert fails if position is out of bounds."""
    # Need getsize mock
    with patch('os.path.getsize', return_value=3): # File size is 3
        result = anthropic_tools.insert(mock_file_manager, file_path="a.txt", content="def", position=4) # Position 4 is invalid
    assert "Error: Position 4 is out of bounds (max: 3)" in result
    mock_file_manager.insert_content.assert_not_called()
    mock_file_manager._resolve_path.assert_called_once_with("a.txt")


def test_insert_fail_invalid_line(mock_file_manager):
    """Test insert fails if line number is out of bounds."""
    mock_file_manager.read_file.return_value = "Line 1\nLine 2" # 2 lines
    # Test line 0 (Pydantic validation)
    with pytest.raises(ValidationError):
        anthropic_tools.InsertInput(file_path="a.txt", content="abc", line=0) # ge=1

    # Test function call for line 0
    result0 = anthropic_tools.insert(mock_file_manager, file_path="a.txt", content="abc", line=0)
    assert "Error: Invalid input" in result0 # Pydantic error

    # Test line 4 (too high, logic check)
    result4 = anthropic_tools.insert(mock_file_manager, file_path="a.txt", content="abc", line=4)
    assert "Error: Line 4 is out of bounds (File has 2 lines, max allowed: 2)" in result4 # Max allowed is num_lines if after_line=False
    mock_file_manager.insert_content.assert_not_called()

    # Test line 3 after_line=True (valid)
    mock_file_manager.insert_content.reset_mock()
    result_after = anthropic_tools.insert(mock_file_manager, file_path="a.txt", content="abc", line=3, after_line=True)
    assert "Successfully inserted" in result_after
    mock_file_manager.insert_content.assert_called_once()

    # Test line 4 after_line=True (invalid)
    mock_file_manager.insert_content.reset_mock()
    result_after_invalid = anthropic_tools.insert(mock_file_manager, file_path="a.txt", content="abc", line=4, after_line=True)
    assert "Error: Line 4 is out of bounds (File has 2 lines, max allowed: 3)" in result_after_invalid
    mock_file_manager.insert_content.assert_not_called()


def test_insert_fail_file_not_found(mock_file_manager):
    """Test insert fails if the target file is not found."""
    # Simulate file not existing
    with patch('os.path.exists', return_value=False):
        result = anthropic_tools.insert(mock_file_manager, file_path="not_found.txt", content="abc", position=0)
    assert "Error: File not found" in result
    mock_file_manager.insert_content.assert_not_called()
    mock_file_manager._resolve_path.assert_called_once_with("not_found.txt")

def test_insert_fail_file_access_error(mock_file_manager):
    """Test insert fails if FileAccessManager.insert_content returns False."""
    mock_file_manager.insert_content.return_value = False # Simulate insert failure
    # Need getsize mock
    with patch('os.path.getsize', return_value=10):
        result = anthropic_tools.insert(mock_file_manager, file_path="insert_fail.txt", content="abc", position=0)
    assert "Error: Error processing file" in result # Check for generic failure message
    mock_file_manager.insert_content.assert_called_once()
    mock_file_manager._resolve_path.assert_called_once_with("insert_fail.txt")
