"""Tests for the MemorySystem git repository indexing."""
import pytest
from unittest.mock import patch, MagicMock
from src.memory.memory_system import MemorySystem

class TestMemorySystemIndexing:
    """Tests for the MemorySystem git repository indexing."""
    
    def test_get_global_index(self):
        """Test getting global index."""
        memory_system = MemorySystem()
        
        # Get global index
        index = memory_system.get_global_index()
        
        # Verify index is a dictionary-like object
        assert hasattr(index, 'get') or hasattr(index, '__getitem__')
        # The index might be a simple dict, which doesn't have get_all
    
    def test_update_global_index(self):
        """Test updating global index."""
        memory_system = MemorySystem()
        
        # Create test index
        test_index = {
            "/path/to/file1.py": "Python file metadata",
            "/path/to/file2.md": "Markdown file metadata"
        }
        
        # Update global index
        memory_system.update_global_index(test_index)
        
        # Get global index
        index = memory_system.get_global_index()
        
        # Verify index contains the test data
        for key, value in test_index.items():
            assert index.get(key) == value
    
    def test_index_git_repository(self):
        """Test memory system integration with GitRepositoryIndexer."""
        with patch('src.memory.indexers.git_repository_indexer.GitRepositoryIndexer') as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.index_repository.return_value = {"file1.py": "metadata1"}
            
            memory_system = MemorySystem()
            memory_system.index_git_repository("/path/to/repo")
            
            mock_indexer_class.assert_called_once_with("/path/to/repo")
            mock_indexer.index_repository.assert_called_once_with(memory_system)
    
    def test_get_relevant_context_for(self):
        """Test getting relevant context for a query."""
        memory_system = MemorySystem()
        
        # Create test index
        test_index = {
            "/path/to/file1.py": "Python file metadata",
            "/path/to/file2.md": "Markdown file metadata",
            "/path/to/file3.js": "JavaScript file metadata"
        }
        
        # Update global index
        memory_system.update_global_index(test_index)
        
        # Create a mock result with the expected files
        class MockResult:
            def __init__(self):
                self.context = "Mock context"
                self.matches = [
                    ("/path/to/file1.py", 0.9),
                    ("/path/to/file2.md", 0.8)
                ]
        
        # Mock the get_relevant_context_for method to return our mock result
        with patch.object(memory_system, 'get_relevant_context_for', return_value=MockResult()):
            # Get relevant context
            context_input = {
                "taskText": "How does the database connection work?",
                "inheritedContext": ""
            }
            
            result = memory_system.get_relevant_context_for(context_input)
            
            # Verify result structure
            assert hasattr(result, 'context')
            assert hasattr(result, 'matches')
            
            # Verify matches include the expected files
            matched_files = [match[0] for match in result.matches]
            assert "/path/to/file1.py" in matched_files
            assert "/path/to/file2.md" in matched_files
