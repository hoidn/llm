"""Tests for the GitRepositoryIndexer."""
import pytest
from unittest.mock import patch, mock_open, MagicMock
import os
import tempfile
from memory.indexers.git_repository_indexer import GitRepositoryIndexer

class TestGitRepositoryIndexer:
    """Tests for the GitRepositoryIndexer class."""

    def test_init(self):
        """Test GitRepositoryIndexer initialization."""
        repo_path = "/path/to/repo"
        indexer = GitRepositoryIndexer(repo_path)
        
        assert indexer.repo_path == repo_path
        assert indexer.max_file_size == 1_000_000
        assert indexer.include_patterns == ["**/*"]
        assert indexer.exclude_patterns == []

    def test_scan_repository(self):
        """Test scan_repository method."""
        with patch('glob.glob') as mock_glob:
            mock_glob.side_effect = lambda pattern, recursive: [
                '/path/to/repo/file1.py',
                '/path/to/repo/file2.txt',
                '/path/to/repo/dir'  # This is a directory
            ] if 'include' in pattern else ['/path/to/repo/file2.txt']
            
            with patch('os.path.isfile') as mock_isfile:
                mock_isfile.side_effect = lambda path: path != '/path/to/repo/dir'
                
                indexer = GitRepositoryIndexer('/path/to/repo')
                indexer.include_patterns = ['include_pattern']
                indexer.exclude_patterns = ['exclude_pattern']
                
                result = indexer.scan_repository()
                
                # Should include file1.py but not file2.txt (excluded) or dir (not a file)
                assert '/path/to/repo/file1.py' in result
                assert '/path/to/repo/file2.txt' not in result
                assert '/path/to/repo/dir' not in result

    def test_is_text_file_by_extension(self):
        """Test is_text_file method with file extension check."""
        indexer = GitRepositoryIndexer('/path/to/repo')
        
        # Test binary extensions
        for ext in ['.jpg', '.png', '.exe', '.zip']:
            with patch('os.path.splitext') as mock_splitext:
                mock_splitext.return_value = ('file', ext)
                assert not indexer.is_text_file(f'file{ext}')
        
        # No need to test content for binary extensions
        with patch('os.path.splitext') as mock_splitext, \
             patch('builtins.open', mock_open()) as mock_file:
            mock_splitext.return_value = ('file', '.jpg')
            assert not indexer.is_text_file('file.jpg')
            mock_file.assert_not_called()

    def test_is_text_file_by_content(self):
        """Test is_text_file method with content check."""
        indexer = GitRepositoryIndexer('/path/to/repo')
        
        # Test text file
        with patch('os.path.splitext') as mock_splitext, \
             patch('builtins.open', mock_open(read_data=b'This is text')) as mock_file:
            mock_splitext.return_value = ('file', '.txt')
            assert indexer.is_text_file('file.txt')
        
        # Test binary content
        with patch('os.path.splitext') as mock_splitext, \
             patch('builtins.open', mock_open(read_data=b'Text with \x00 null byte')) as mock_file:
            mock_splitext.return_value = ('file', '.txt')
            assert not indexer.is_text_file('file.txt')

    def test_create_metadata(self):
        """Test create_metadata method."""
        # This test requires the text_extraction module to be properly mocked
        # We'll test the high-level behavior
        
        with patch('memory.indexers.text_extraction.extract_document_summary') as mock_summary, \
             patch('memory.indexers.text_extraction.extract_identifiers_by_language') as mock_identifiers:
            
            mock_summary.return_value = "Summary: Test summary\n"
            mock_identifiers.return_value = ["func1", "Class1", "method1"]
            
            indexer = GitRepositoryIndexer('/path/to/repo')
            
            # Set up the test case
            file_path = '/path/to/repo/src/module.py'
            content = "def func1():\n    pass\n\nclass Class1:\n    def method1(self): pass"
            
            # Call the method
            metadata = indexer.create_metadata(file_path, content)
            
            # Check results
            assert "File: module.py" in metadata
            assert "Path: src/module.py" in metadata
            assert "Type: py" in metadata
            # The order of identifiers might be different, so check each one separately
            assert "func1" in metadata
            assert "Class1" in metadata
            assert "method1" in metadata

    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data='test content')
    @patch('glob.glob')
    def test_index_repository(self, mock_glob, mock_open, mock_getsize):
        """Test index_repository method."""
        # Setup mocks
        mock_glob.return_value = ['/path/to/repo/file.py']
        mock_getsize.return_value = 100  # Small file size
        
        # Create a mock memory system
        mock_memory = MagicMock()
        
        # Set up the indexer
        indexer = GitRepositoryIndexer('/path/to/repo')
        
        # Mock the is_text_file and create_metadata methods
        with patch.object(indexer, 'is_text_file', return_value=True), \
             patch.object(indexer, 'create_metadata', return_value="File metadata"), \
             patch('os.path.exists', return_value=True):  # Add this to make os.path.exists return True
            
            # Call the method
            result = indexer.index_repository(mock_memory)
            
            # Check the result
            assert '/path/to/repo/file.py' in result
            assert result['/path/to/repo/file.py'] == "File metadata"
            
            # Check that memory system was updated
            mock_memory.update_global_index.assert_called_once()
            
            # Check that memory system was updated
            mock_memory.update_global_index.assert_called_once_with({'/path/to/repo/file.py': "File metadata"})
    
    @pytest.mark.integration
    def test_with_real_files(self):
        """Test with real files in a temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            with open(os.path.join(temp_dir, "test.py"), "w") as f:
                f.write("def test_function():\n    return 'Hello, world!'\n")
            
            with open(os.path.join(temp_dir, "README.md"), "w") as f:
                f.write("# Test Repository\n\nThis is a test repository.\n")
            
            # Create binary file
            with open(os.path.join(temp_dir, "binary.bin"), "wb") as f:
                f.write(b"\x00\x01\x02\x03")
            
            # Create indexer
            indexer = GitRepositoryIndexer(temp_dir)
            
            # Create mock memory system
            mock_memory = MagicMock()
            
            # Index repository
            result = indexer.index_repository(mock_memory)
            
            # Check results
            assert len(result) >= 2  # At least test.py and README.md
            assert any("test.py" in path for path in result.keys())
            assert any("README.md" in path for path in result.keys())
            assert not any("binary.bin" in path for path in result.keys())  # Binary file should be skipped
