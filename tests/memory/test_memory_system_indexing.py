"""Tests for the MemorySystem git repository indexing."""
import pytest
from unittest.mock import patch, MagicMock
from memory.memory_system import MemorySystem

class TestMemorySystemIndexing:
    """Tests for the MemorySystem git repository indexing."""
    
    def test_index_git_repository(self):
        """Test memory system integration with GitRepositoryIndexer."""
        with patch('memory.indexers.git_repository_indexer.GitRepositoryIndexer') as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.index_repository.return_value = {"file1.py": "metadata1"}
            
            memory_system = MemorySystem()
            memory_system.index_git_repository("/path/to/repo")
            
            mock_indexer_class.assert_called_once_with("/path/to/repo")
            mock_indexer.index_repository.assert_called_once_with(memory_system)
            
            # Check that the global index was updated
            assert memory_system.get_global_index() == {"file1.py": "metadata1"}
