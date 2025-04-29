"""
Unit and Integration tests for the GitRepositoryIndexer.
"""
import pytest
import os
import logging # Import logging
import subprocess # Needed for integration test fixture setup
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
    # NOTE: For integration tests, we might want the *real* text_extraction.
    # We'll handle this by potentially not patching globally or using specific patches.
    # For unit tests below, we still need the mocks.
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
from src.memory.indexers.git_repository_indexer import GitRepositoryIndexer, DEFAULT_INCLUDE_PATTERNS, DEFAULT_MAX_FILE_SIZE
# Import MemorySystem for integration tests
from src.memory.memory_system import MemorySystem


# --- Fixtures ---

@pytest.fixture
def mock_repo(mocker):
    """Fixture for a mocked git.Repo object (for unit tests)."""
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
    """Fixture for a mocked MemorySystem (for unit tests)."""
    mock = MagicMock() # spec=MemorySystem if available
    mock.update_global_index = MagicMock()
    return mock

@pytest.fixture
def unit_test_indexer(tmp_path):
    """Fixture for GitRepositoryIndexer instance for unit tests (mocks GitPython)."""
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


# --- Unit Test Cases ---

def test_indexer_init(tmp_path):
    """Unit Test: constructor initializes repo_path and defaults."""
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
    assert indexer_instance.include_patterns == DEFAULT_INCLUDE_PATTERNS
    assert indexer_instance.max_file_size == DEFAULT_MAX_FILE_SIZE


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
# Patch where splitext is looked up by the code under test
@patch('src.memory.indexers.git_repository_indexer.os.path.splitext')
def test_is_text_file(mock_splitext, mock_open_file, unit_test_indexer, file_path, file_content, expected):
    """Unit Test: text file detection logic."""
    # Configure mocks
    # FIX: Don't call the real splitext here as the patch is active.
    # Determine the expected return value based on the input file_path.
    # The real os.path.splitext returns a tuple: (root, ext)
    # Calculate the expected tuple *outside* the patch scope conceptually
    # This calculation happens *before* the mock is configured below.
    expected_root, expected_ext = os.path.splitext(file_path)
    expected_splitext_output = (expected_root, expected_ext)
    # Configure the mock passed into the test function to return the pre-calculated tuple
    mock_splitext.return_value = expected_splitext_output
    # --- End FIX ---

    mock_file_handle = mock_open_file.return_value # Get the mock file handle
    mock_file_handle.read.return_value = file_content # Make mock file return bytes

    # Act
    result = unit_test_indexer.is_text_file(file_path)

    # Assert
    assert result == expected
    # Check open was called correctly
    mock_open_file.assert_called_once_with(file_path, 'rb') # Check opened in binary mode
    # Check that the mock we configured was called by the implementation
    mock_splitext.assert_called_once_with(file_path)


@patch('os.path.getsize')
# Patch the specific functions within the module where create_metadata will look for them
@patch('src.memory.indexers.git_repository_indexer.text_extraction.extract_document_summary')
@patch('src.memory.indexers.git_repository_indexer.text_extraction.extract_identifiers_by_language')
def test_create_metadata(mock_extract_ids, mock_extract_summary, mock_getsize, unit_test_indexer, mock_repo, tmp_path):
    """Unit Test: metadata string creation formatting."""
    # Configure mocks
    repo_path_str = str(tmp_path)
    file_path = os.path.abspath(str(tmp_path / "subdir" / "my_code.py"))
    content = "def hello():\n  print('world')"
    mock_getsize.return_value = len(content)
    # Ensure the indexer's internal _git_repo is our mock_repo
    unit_test_indexer._git_repo = mock_repo # Directly set the mock repo instance
    mock_extract_summary.return_value = "Summary: A simple function."
    mock_extract_ids.return_value = ["hello"]

    # Act
    metadata = unit_test_indexer.create_metadata(file_path, content)

    # Assert
    assert isinstance(metadata, str)
    assert f"File: {os.path.relpath(file_path, unit_test_indexer.repo_path)}" in metadata
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
    mock_repo.iter_commits.assert_called_once_with(paths=file_path, max_count=1)
    mock_extract_summary.assert_called_once_with(content)
    mock_extract_ids.assert_called_once_with(content, lang='py') # Check lang derived from extension


# --- Integration Test Cases ---
# These tests use the 'git_repo' fixture defined in conftest.py

# Skip integration tests if GitPython is not available
pytestmark = pytest.mark.skipif(not GIT_PYTHON_AVAILABLE, reason="GitPython not installed, skipping integration tests")

def test_integration_index_basic_repo(git_repo):
    """Integration Test: Index a basic repo with text files."""
    repo_path, add_file, commit = git_repo
    add_file("file1.py", "print('hello')")
    add_file("subdir/file2.txt", "some text content")
    commit("Initial commit")

    # Use real components
    memory_system = MemorySystem()
    indexer = GitRepositoryIndexer(repo_path=repo_path)
    # Use default include patterns (just *.py)
    indexer.include_patterns = ["**/*.py", "**/*.txt"] # Include both for this test

    # Act
    indexer.index_repository(memory_system=memory_system)

    # Assert
    index = memory_system.get_global_index()
    assert len(index) == 2
    path1 = os.path.join(repo_path, "file1.py")
    path2 = os.path.join(repo_path, "subdir", "file2.txt")
    assert path1 in index
    assert path2 in index
    assert "File: file1.py" in index[path1]
    assert "Extension: .py" in index[path1]
    assert "Commit: " in index[path1] # Check commit info is present
    assert "File: subdir/file2.txt" in index[path2]
    assert "Extension: .txt" in index[path2]

def test_integration_index_skips_binary(git_repo):
    """Integration Test: Ensure binary files are skipped."""
    repo_path, add_file, commit = git_repo
    add_file("script.py", "print('text')")
    add_file("image.jpg", b"\xFF\xD8\xFF\xE0") # Add binary content
    commit("Add text and binary")

    memory_system = MemorySystem()
    indexer = GitRepositoryIndexer(repo_path=repo_path)
    indexer.include_patterns = ["**/*"] # Include all initially

    # Act
    indexer.index_repository(memory_system=memory_system)

    # Assert
    index = memory_system.get_global_index()
    assert len(index) == 1 # Only script.py should be indexed
    path_py = os.path.join(repo_path, "script.py")
    path_jpg = os.path.join(repo_path, "image.jpg")
    assert path_py in index
    assert path_jpg not in index

def test_integration_index_skips_large_files(git_repo):
    """Integration Test: Ensure large files are skipped."""
    repo_path, add_file, commit = git_repo
    max_size = 50 # Set a small max size for testing
    add_file("small.txt", "small content")
    add_file("large.txt", "This content is definitely larger than fifty bytes to test skipping.")
    commit("Add small and large files")

    memory_system = MemorySystem()
    indexer = GitRepositoryIndexer(repo_path=repo_path)
    indexer.include_patterns = ["**/*.txt"]
    indexer.max_file_size = max_size # Override default

    # Act
    indexer.index_repository(memory_system=memory_system)

    # Assert
    index = memory_system.get_global_index()
    assert len(index) == 1 # Only small.txt should be indexed
    path_small = os.path.join(repo_path, "small.txt")
    path_large = os.path.join(repo_path, "large.txt")
    assert path_small in index
    assert path_large not in index

def test_integration_index_respects_patterns(git_repo):
    """Integration Test: Ensure include/exclude patterns are respected."""
    repo_path, add_file, commit = git_repo
    add_file("src/main.py", "main content")
    add_file("src/utils.py", "util content")
    add_file("tests/test_main.py", "test content")
    add_file("docs/readme.md", "doc content")
    add_file("build/output.log", "log content")
    commit("Add various files")

    memory_system = MemorySystem()
    indexer = GitRepositoryIndexer(repo_path=repo_path)
    # Configure patterns
    indexer.include_patterns = ["src/**/*.py", "docs/**/*.md"]
    indexer.exclude_patterns = ["build/*", "**/*utils*"] # Exclude build dir and anything with 'utils'

    # Act
    indexer.index_repository(memory_system=memory_system)

    # Assert
    index = memory_system.get_global_index()
    assert len(index) == 2 # Should index main.py and readme.md
    path_main = os.path.join(repo_path, "src", "main.py")
    path_utils = os.path.join(repo_path, "src", "utils.py")
    path_test = os.path.join(repo_path, "tests", "test_main.py")
    path_readme = os.path.join(repo_path, "docs", "readme.md")
    path_log = os.path.join(repo_path, "build", "output.log")

    assert path_main in index
    assert path_readme in index
    assert path_utils not in index # Excluded by pattern
    assert path_test not in index # Not included
    assert path_log not in index # Excluded by pattern
