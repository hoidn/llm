"""
Unit tests for the GitRepositoryIndexer.
"""
import pytest
import os
import logging # Import logging
from unittest.mock import MagicMock, patch, mock_open, call, _is_instance_mock # Import _is_instance_mock for check
from datetime import datetime # Import datetime for mocking

# Assuming GitPython types are available for spec/isinstance checks
try:
    import git
    # Define text_extraction here or import appropriately
    # This assumes text_extraction is part of the indexer module or globally available
    # If text_extraction helpers are in a separate file like src/utils/text_extraction.py
    # you would patch 'src.memory.indexers.git_repository_indexer.text_extraction'
    # assuming the indexer imports it as 'text_extraction'.
    from src.memory.indexers import git_repository_indexer # Import module to potentially patch things inside it
    # Patch the text_extraction dependency within the indexer module *before* it's imported by the test subject
    # This ensures the indexer class uses the mock when instantiated.
    git_repository_indexer.text_extraction = MagicMock()
    git_repository_indexer.text_extraction.extract_document_summary = MagicMock(return_value="Mocked Summary")
    git_repository_indexer.text_extraction.extract_identifiers_by_language = MagicMock(return_value=["mock_id"])
    GIT_PYTHON_AVAILABLE = True
except ImportError:
    # Define dummy git type if GitPython not installed in test env
    class Repo: pass
    class Commit: pass
    git = MagicMock()
    git.Repo = Repo # Assign the dummy class to the mock attribute
    git.Commit = Commit
    # Define dummy text_extraction if needed
    text_extraction = MagicMock()
    text_extraction.extract_document_summary = MagicMock(return_value="Mocked Summary")
    text_extraction.extract_identifiers_by_language = MagicMock(return_value=["mock_id"])
    # Need to ensure the module under test can find text_extraction
    # The patching below targets where it's expected to be found by the indexer
    # If GitPython is missing, we also need to patch the import within the indexer module
    patch('src.memory.indexers.git_repository_indexer.git', git).start() # Patch git import
    patch('src.memory.indexers.git_repository_indexer.text_extraction', text_extraction).start() # Patch text_extraction import
    GIT_PYTHON_AVAILABLE = False


# Now import the class under test *after* potential patches
from src.memory.indexers.git_repository_indexer import GitRepositoryIndexer
# Assuming MemorySystem is importable for type hints if needed
# from src.memory.memory_system import MemorySystem

# --- Fixtures ---

@pytest.fixture
def mock_repo(mocker):
    """Fixture for a mocked git.Repo object."""
    # Use the actual git.Repo class for spec if available, otherwise None
    spec_target = git.Repo if GIT_PYTHON_AVAILABLE and not _is_instance_mock(git.Repo) else None
    mock = MagicMock(spec=spec_target)

    # Mock commit object
    spec_commit = git.Commit if GIT_PYTHON_AVAILABLE and not _is_instance_mock(git.Commit) else None
    mock_commit = MagicMock(spec=spec_commit)
    mock_commit.hexsha = "abcdef123456"

    # Mock the author object within the commit
    mock_author = MagicMock()
    mock_author.name = "Test Author"
    mock_commit.author = mock_author # Assign the mock author

    # Mock the datetime object within the commit object
    # Use a real datetime object for realistic behavior
    mock_dt = datetime.fromisoformat("2024-01-01T12:00:00+00:00")
    mock_commit.authored_datetime = mock_dt # Assign the real datetime

    # Mock iter_commits to return the mock commit
    mock.iter_commits.return_value = iter([mock_commit])
    return mock

@pytest.fixture
def mock_memory_system(mocker):
    """Fixture for a mocked MemorySystem."""
    mock = MagicMock() # spec=MemorySystem if available
    mock.update_global_index = MagicMock()
    return mock

@pytest.fixture
def indexer(tmp_path):
    """Fixture for GitRepositoryIndexer instance pointing to a temp path."""
    # Create a dummy .git dir to simulate repo structure if needed by constructor
    git_dir = tmp_path / ".git"
    if not git_dir.exists(): # Ensure it doesn't already exist
         git_dir.mkdir()

    # Patch git.Repo call within the fixture's scope
    with patch('src.memory.indexers.git_repository_indexer.git.Repo') as mock_git_repo_constructor:
        # Determine the correct spec target based on whether git.Repo is real or mocked
        spec_target = git.Repo if GIT_PYTHON_AVAILABLE and not _is_instance_mock(git.Repo) else None
        # Create the mock return value *with the correct spec*
        mock_repo_instance = MagicMock(spec=spec_target)
        mock_git_repo_constructor.return_value = mock_repo_instance
        # Instantiate the indexer, which will call the patched constructor
        indexer_instance = GitRepositoryIndexer(repo_path=str(tmp_path))

    # Reset mocks for text_extraction for clean state per test
    # Access the potentially mocked text_extraction via the imported module object
    if hasattr(git_repository_indexer, 'text_extraction'): # Check if module exists (might not in ImportError case)
        git_repository_indexer.text_extraction.extract_document_summary.reset_mock()
        git_repository_indexer.text_extraction.extract_identifiers_by_language.reset_mock()
        git_repository_indexer.text_extraction.extract_document_summary.return_value="Mocked Summary"
        git_repository_indexer.text_extraction.extract_identifiers_by_language.return_value=["mock_id"]

    return indexer_instance


# --- Test Cases ---

def test_indexer_init(tmp_path):
    """Test constructor initializes repo_path."""
    repo_path_str = str(tmp_path)
     # Create a dummy .git dir if it doesn't exist for this specific test run
    git_dir = tmp_path / ".git"
    if not git_dir.exists():
         git_dir.mkdir()

    # Patch git.Repo for this specific test's instantiation
    with patch('src.memory.indexers.git_repository_indexer.git.Repo') as mock_git_repo_constructor:
        # Determine the correct spec target
        spec_target = git.Repo if GIT_PYTHON_AVAILABLE and not _is_instance_mock(git.Repo) else None
        mock_git_repo_constructor.return_value = MagicMock(spec=spec_target)
        indexer_instance = GitRepositoryIndexer(repo_path=repo_path_str)

    assert indexer_instance.repo_path == os.path.abspath(repo_path_str) # Should store absolute path
    # Assert default patterns/size if needed
    from src.memory.indexers.git_repository_indexer import DEFAULT_INCLUDE_PATTERNS, DEFAULT_MAX_FILE_SIZE
    assert indexer_instance.include_patterns == DEFAULT_INCLUDE_PATTERNS
    assert indexer_instance.max_file_size == DEFAULT_MAX_FILE_SIZE


@patch('glob.glob')
@patch('os.path.isfile')
def test_scan_repository(mock_isfile, mock_glob, indexer, tmp_path):
    """Test repository scanning with include/exclude patterns."""
    repo_path_str = str(tmp_path)
    # Configure glob to return potential paths
    # Simulate finding files and directories
    mock_glob.side_effect = lambda pattern, recursive=False: {
        os.path.join(repo_path_str, "**/*.py"): [str(tmp_path / 'a.py'), str(tmp_path / 'subdir' / 'b.py')],
        os.path.join(repo_path_str, "**/*.txt"): [str(tmp_path / 'c.txt')],
        os.path.join(repo_path_str, "subdir/*"): [str(tmp_path / 'subdir' / 'b.py'), str(tmp_path / 'subdir' / 'other_dir')], # Exclude pattern matches file and dir
        os.path.join(repo_path_str, "excluded_dir/**"): [str(tmp_path / 'excluded_dir' / 'e.txt')], # Exclude pattern matches file in dir
    }.get(pattern, []) # Return empty list if pattern not matched

    # Configure os.path.isfile and os.path.isdir
    def isfile_side_effect(p):
        # Make paths absolute for reliable comparison if needed
        abs_p = os.path.abspath(p)
        return abs_p.endswith('.py') or abs_p.endswith('.txt') or abs_p.endswith('e.txt')

    def isdir_side_effect(p):
        abs_p = os.path.abspath(p)
        # Check against absolute paths of expected directories
        return abs_p == os.path.abspath(str(tmp_path / 'subdir')) or \
               abs_p == os.path.abspath(str(tmp_path / 'subdir' / 'other_dir')) or \
               abs_p == os.path.abspath(str(tmp_path / 'excluded_dir'))

    mock_isfile.side_effect = isfile_side_effect
    # We also need to mock os.path.isdir for the exclusion logic
    with patch('os.path.isdir', side_effect=isdir_side_effect):
        # And os.walk for directory exclusion
        with patch('os.walk') as mock_walk:
            # Simulate os.walk finding e.txt inside excluded_dir
            # Ensure walk yields absolute paths if the code expects them
            excluded_dir_abs = os.path.abspath(str(tmp_path / 'excluded_dir'))
            mock_walk.return_value = iter([
                 (excluded_dir_abs, [], ['e.txt'])
            ])

            indexer.include_patterns = ["**/*.py", "**/*.txt"] # Example include
            indexer.exclude_patterns = ["subdir/*", "excluded_dir/**"] # Example exclude

            result = indexer.scan_repository()

    # Assertions
    # Check glob calls used the correct patterns relative to repo_path
    # Note: The exact calls depend on how many patterns are in include/exclude lists
    assert call(os.path.join(repo_path_str, "**/*.py"), recursive=True) in mock_glob.call_args_list
    assert call(os.path.join(repo_path_str, "**/*.txt"), recursive=True) in mock_glob.call_args_list
    assert call(os.path.join(repo_path_str, "subdir/*"), recursive=True) in mock_glob.call_args_list
    assert call(os.path.join(repo_path_str, "excluded_dir/**"), recursive=True) in mock_glob.call_args_list


    # Check expected files are returned (a.py, c.txt), excluding subdir/b.py and excluded_dir/e.txt
    expected_paths = {os.path.abspath(str(tmp_path / 'a.py')), os.path.abspath(str(tmp_path / 'c.txt'))}
    assert set(result) == expected_paths


@pytest.mark.parametrize("file_path, file_content, expected", [
    ("test.py", b"print('hello')", True),
    ("test.txt", b"Simple text", True),
    ("archive.zip", b"PK\x03\x04", False), # Known binary signature
    ("image.jpg", b"\xFF\xD8\xFF", False), # Known binary signature
    ("unknown.bin", b"\x00\x01\x02\x00", False), # Null bytes
    ("no_extension", b"Just text", True),
    ("script.sh", b"#!/bin/bash\necho hello", True),
    ("utf16_file.txt", b'\xff\xfeh\x00e\x00l\x00l\x00o\x00', False), # UTF-16 BOM, fails utf-8/latin-1 decode
    ("empty_file.txt", b"", True), # Empty file is considered text
])
@patch('builtins.open', new_callable=mock_open)
# FIX: Patch where splitext is looked up by the code under test
@patch('src.memory.indexers.git_repository_indexer.os.path.splitext')
def test_is_text_file(mock_splitext, mock_open_file, indexer, file_path, file_content, expected):
    """Test text file detection logic."""
    # Configure mocks
    # Calculate the expected tuple *before* assigning to the mock
    # Call the *real* os.path.splitext to get the expected output for this file_path
    expected_splitext_output = os.path.splitext(file_path)
    # Configure the mock passed into the test function to return this pre-calculated tuple
    mock_splitext.return_value = expected_splitext_output
    # --- End FIX ---

    mock_file_handle = mock_open_file.return_value # Get the mock file handle
    mock_file_handle.read.return_value = file_content # Make mock file return bytes

    # Act
    result = indexer.is_text_file(file_path)

    # Assert
    assert result == expected
    mock_open_file.assert_called_once_with(file_path, 'rb') # Check opened in binary mode
    # Check that the mock we configured was called by the implementation
    mock_splitext.assert_called_once_with(file_path)


@patch('os.path.getsize')
# Patch where Repo is looked up by create_metadata - NOT NEEDED if _git_repo is set directly
# @patch('src.memory.indexers.git_repository_indexer.git.Repo')
# Patch the specific functions within the module where create_metadata will look for them
@patch('src.memory.indexers.git_repository_indexer.text_extraction.extract_document_summary')
@patch('src.memory.indexers.git_repository_indexer.text_extraction.extract_identifiers_by_language')
def test_create_metadata(mock_extract_ids, mock_extract_summary, mock_getsize, indexer, mock_repo, tmp_path):
    """Test metadata string creation."""
    # Configure mocks
    repo_path_str = str(tmp_path)
    file_path = os.path.abspath(str(tmp_path / "subdir" / "my_code.py"))
    content = "def hello():\n  print('world')"
    mock_getsize.return_value = len(content)
    # Ensure the indexer's internal _git_repo is our mock_repo
    indexer._git_repo = mock_repo # Directly set the mock repo instance
    mock_extract_summary.return_value = "Summary: A simple function."
    mock_extract_ids.return_value = ["hello"]

    # Act
    metadata = indexer.create_metadata(file_path, content)

    # Assert
    assert isinstance(metadata, str)
    assert f"File: {os.path.relpath(file_path, indexer.repo_path)}" in metadata
    assert "Filename: my_code.py" in metadata
    assert "Extension: .py" in metadata
    assert f"Size: {len(content)} bytes" in metadata
    assert "Summary: A simple function." in metadata
    assert "Identifiers: hello" in metadata
    # Check Git info from the mock_repo fixture
    assert "Commit: abcdef123456" in metadata # From mock_commit
    assert "Author: Test Author" in metadata
    assert "Date: 2024-01-01T12:00:00+00:00" in metadata

    # Check dependencies were called
    # git.Repo constructor should NOT be called here because we manually set indexer._git_repo
    # mock_GitRepo.assert_not_called() # No longer patching the constructor directly here
    mock_repo.iter_commits.assert_called_once_with(paths=file_path, max_count=1)
    mock_extract_summary.assert_called_once_with(content)
    mock_extract_ids.assert_called_once_with(content, lang='py') # Check lang derived from extension


@patch.object(GitRepositoryIndexer, 'scan_repository')
@patch.object(GitRepositoryIndexer, 'is_text_file')
@patch.object(GitRepositoryIndexer, 'create_metadata')
@patch('builtins.open', new_callable=mock_open)
@patch('os.path.getsize')
def test_index_repository_success(mock_getsize, mock_open_file, mock_create_metadata, mock_is_text_file, mock_scan_repo, indexer, mock_memory_system, tmp_path):
    """Test successful repository indexing orchestration."""
    # Configure mocks
    file1_path = os.path.abspath(str(tmp_path / 'file1.py'))
    file2_path = os.path.abspath(str(tmp_path / 'file2.txt'))
    file3_path = os.path.abspath(str(tmp_path / 'binary.dat')) # Should be skipped
    mock_scan_repo.return_value = [file1_path, file2_path, file3_path]
    # is_text_file returns True for .py and .txt, False for .dat
    mock_is_text_file.side_effect = lambda p: p.endswith('.py') or p.endswith('.txt')
    # getsize returns valid sizes
    mock_getsize.return_value = 100
    # create_metadata returns mock metadata
    mock_create_metadata.side_effect = lambda p, c: f"metadata_for_{os.path.basename(p)}"
    # mock file reading
    mock_open_file.return_value.__enter__.return_value.read.return_value = "file content" # Ensure mock file is context manager

    # Act
    result_index = indexer.index_repository(mock_memory_system)

    # Assert
    mock_scan_repo.assert_called_once()
    # Check is_text_file called for all scanned files
    assert mock_is_text_file.call_count == 3
    # Check create_metadata called only for text files
    assert mock_create_metadata.call_count == 2
    mock_create_metadata.assert_any_call(file1_path, "file content")
    mock_create_metadata.assert_any_call(file2_path, "file content")
    # Check memory system updated with correct data (absolute paths)
    expected_update_arg = {
        file1_path: "metadata_for_file1.py",
        file2_path: "metadata_for_file2.txt"
    }
    mock_memory_system.update_global_index.assert_called_once_with(expected_update_arg)
    # Check return value matches the updated index
    assert result_index == expected_update_arg

@patch.object(GitRepositoryIndexer, 'scan_repository')
@patch.object(GitRepositoryIndexer, 'is_text_file')
@patch('os.path.getsize')
@patch('builtins.open', new_callable=mock_open, read_data="content") # ADDED: Mock open to prevent read error
def test_index_repository_skips_large_files(mock_open_file, mock_getsize, mock_is_text_file, mock_scan_repo, indexer, mock_memory_system, tmp_path):
    """Test that large files are skipped."""
    file_small_path = os.path.abspath(str(tmp_path / 'small.py'))
    file_large_path = os.path.abspath(str(tmp_path / 'large.py'))
    mock_scan_repo.return_value = [file_small_path, file_large_path]
    mock_is_text_file.return_value = True # Both are text files
    # Configure sizes
    mock_getsize.side_effect = lambda p: 500 if 'small' in p else indexer.max_file_size + 100

    # Act
    indexer.index_repository(mock_memory_system)

    # Assert memory system was updated only with the small file
    mock_memory_system.update_global_index.assert_called_once()
    update_arg = mock_memory_system.update_global_index.call_args[0][0]
    assert file_small_path in update_arg
    assert file_large_path not in update_arg
    # Assert open was called for the small file but not the large one (due to size check)
    mock_open_file.assert_called_once_with(file_small_path, 'r', encoding='utf-8', errors='ignore')


# Add more tests for error handling (e.g., git command errors in create_metadata,
# file read errors in index_repository)

@patch.object(GitRepositoryIndexer, 'scan_repository')
@patch.object(GitRepositoryIndexer, 'is_text_file', return_value=True) # Assume text
@patch('os.path.getsize', return_value=100) # Assume valid size
@patch('builtins.open', new_callable=mock_open, read_data="content") # ADDED: Mock open
@patch.object(GitRepositoryIndexer, 'create_metadata') # Mock create_metadata
def test_index_repository_handles_create_metadata_error(mock_create_meta, mock_open_ctx, mock_getsize, mock_is_text, mock_scan, indexer, mock_memory_system, tmp_path, caplog):
    """Test that errors during create_metadata are handled and logged."""
    file1 = os.path.abspath(str(tmp_path / "file1.py"))
    file2 = os.path.abspath(str(tmp_path / "file2.py")) # This one will cause error
    file3 = os.path.abspath(str(tmp_path / "file3.py"))
    mock_scan.return_value = [file1, file2, file3]
    # Make create_metadata raise error for file2
    mock_create_meta.side_effect = lambda p, c: f"meta_{os.path.basename(p)}" if p != file2 else Exception("Git history missing")

    # Set log level before the test
    caplog.set_level(logging.ERROR)
    result_index = indexer.index_repository(mock_memory_system)

    # Assert file2 caused an error log - check records directly
    # FIX: Check levelname and message content more robustly
    error_record_found = False
    for record in caplog.records:
        if record.levelname == 'ERROR' and f"Error processing file {file2}" in record.message and "Git history missing" in record.message:
            error_record_found = True
            break
    assert error_record_found, f"Expected ERROR log for {file2} not found in caplog records: {caplog.text}"
    # --- End FIX ---

    # Assert memory system only updated with file1 and file3
    expected_update = {
        file1: "meta_file1.py",
        file3: "meta_file3.py",
    }
    mock_memory_system.update_global_index.assert_called_once_with(expected_update)
    assert result_index == expected_update
    # Check open was called for all files (before create_metadata error)
    assert mock_open_ctx.call_count == 3


@patch.object(GitRepositoryIndexer, 'scan_repository')
@patch.object(GitRepositoryIndexer, 'is_text_file', return_value=True) # Assume text
@patch('os.path.getsize', return_value=100) # Assume valid size
@patch('builtins.open', new_callable=mock_open) # Mock open initially
@patch.object(GitRepositoryIndexer, 'create_metadata') # Mock create_metadata
def test_index_repository_handles_read_error(mock_create_meta, mock_open_func, mock_getsize, mock_is_text, mock_scan, indexer, mock_memory_system, tmp_path, caplog):
    """Test that errors during file reading are handled and logged."""
    file1 = os.path.abspath(str(tmp_path / "file1.py")) # This one will fail read
    file2 = os.path.abspath(str(tmp_path / "file2.py"))
    mock_scan.return_value = [file1, file2]
    mock_create_meta.side_effect = lambda p, c: f"meta_{os.path.basename(p)}"

    # Configure open mock to only fail for file1
    original_mock_open = mock_open_func.side_effect # Store original side effect if any
    def open_side_effect(path, mode, encoding=None, errors=None):
        if path == file1:
            raise IOError("Permission denied")
        else:
            # Return a mock that can be read for file2
            m = MagicMock()
            m.read.return_value = "content for file2"
            # Make it usable with 'with' statement
            m.__enter__.return_value = m
            m.__exit__.return_value = None
            return m
            # If original_mock_open had a side effect, call it for other paths
            # elif callable(original_mock_open):
            #     return original_mock_open(path, mode, encoding=encoding, errors=errors)
            # else: # Default mock_open behavior
            #     return mock_open()(path, mode, encoding=encoding, errors=errors)

    mock_open_func.side_effect = open_side_effect

    with caplog.at_level(logging.WARNING): # Capture warnings as well
        result_index = indexer.index_repository(mock_memory_system)

    # Assert file1 caused an error log (might be warning or error depending on implementation)
    assert "Could not read file" in caplog.text # Check for the specific warning/error message
    assert file1 in caplog.text
    assert "Permission denied" in caplog.text
    # Assert memory system only updated with file2
    expected_update = {
        file2: "meta_file2.py",
    }
    mock_memory_system.update_global_index.assert_called_once_with(expected_update)
    assert result_index == expected_update
    # Ensure create_metadata was not called for the failed file
    mock_create_meta.assert_called_once_with(file2, "content for file2")
