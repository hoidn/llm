"""Basic end-to-end tests for the main module."""
import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.integration
def test_main_initialization():
    """Test that main initializes all required components."""
    with patch('memory.memory_system.MemorySystem') as mock_memory_class, \
         patch('task_system.task_system.TaskSystem') as mock_task_class, \
         patch('repl.repl.Repl') as mock_repl_class, \
         patch('memory.indexers.git_repository_indexer.GitRepositoryIndexer') as mock_indexer_class, \
         patch('task_system.templates.associative_matching.register_template') as mock_register:
        
        # Create mocks
        mock_memory = MagicMock()
        mock_task = MagicMock()
        mock_repl = MagicMock()
        mock_indexer = MagicMock()
        
        # Setup returns
        mock_memory_class.return_value = mock_memory
        mock_task_class.return_value = mock_task
        mock_repl_class.return_value = mock_repl
        mock_indexer_class.return_value = mock_indexer
        
        # To avoid actually running the REPL
        mock_repl.start.side_effect = KeyboardInterrupt()
        
        # Import and run with mocks
        import main
        
        try:
            main.main()
        except KeyboardInterrupt:
            pass  # Expected due to our mock
        
        # Verify all components were initialized
        mock_memory_class.assert_called_once()
        mock_task_class.assert_called_once()
        mock_register.assert_called_once_with(mock_task)
        mock_indexer_class.assert_called_once()
        mock_indexer.index_repository.assert_called_once_with(mock_memory)
        mock_repl_class.assert_called_once_with(mock_task, mock_memory)
        mock_repl.start.assert_called_once()
