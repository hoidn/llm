"""Basic end-to-end tests for the main module."""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock

@pytest.mark.integration
def test_main_initialization():
    """Test that main initializes all required components."""
    with patch('memory.memory_system.MemorySystem') as mock_memory_class, \
         patch('task_system.task_system.TaskSystem') as mock_task_class, \
         patch('repl.repl.Repl') as mock_repl_class, \
         patch('handler.passthrough_handler.PassthroughHandler') as mock_handler_class, \
         patch('task_system.templates.associative_matching.register_template') as mock_register:
        
        # Create mocks
        mock_memory = MagicMock()
        mock_task = MagicMock()
        mock_repl = MagicMock()
        mock_handler = MagicMock()
        
        # Setup returns
        mock_memory_class.return_value = mock_memory
        mock_task_class.return_value = mock_task
        mock_repl_class.return_value = mock_repl
        mock_handler_class.return_value = mock_handler
        
        # To avoid actually running the REPL
        mock_repl.start.side_effect = KeyboardInterrupt()
        
        # Import and run with mocks
        import main
        
        try:
            main.main()
        except KeyboardInterrupt:
            pass  # Expected due to our mock
        
        # Verify Application was created and components were initialized
        mock_memory_class.assert_called_once()
        mock_task_class.assert_called_once()
        mock_register.assert_called_once()
        mock_handler_class.assert_called_once()
        mock_repl_class.assert_called_once()
        mock_repl.start.assert_called_once()

@pytest.mark.integration
class TestApplication:
    """Tests for the Application class."""
    
    def test_application_init(self):
        """Test Application initialization."""
        with patch('memory.memory_system.MemorySystem') as mock_memory_class, \
             patch('task_system.task_system.TaskSystem') as mock_task_class, \
             patch('handler.passthrough_handler.PassthroughHandler') as mock_handler_class, \
             patch('task_system.templates.associative_matching.register_template') as mock_register:
            
            # Create mocks
            mock_memory = MagicMock()
            mock_task = MagicMock()
            mock_handler = MagicMock()
            
            # Setup returns
            mock_memory_class.return_value = mock_memory
            mock_task_class.return_value = mock_task
            mock_handler_class.return_value = mock_handler
            
            # Import and create application
            from main import Application
            app = Application()
            
            # Verify components were initialized
            assert app.memory_system == mock_memory
            assert app.task_system == mock_task
            assert app.passthrough_handler == mock_handler
            assert app.indexed_repositories == []
            
            # Verify register_template was called
            mock_register.assert_called_once_with(mock_task)
    
    def test_index_repository(self):
        """Test indexing a repository."""
        with patch('memory.memory_system.MemorySystem'), \
             patch('task_system.task_system.TaskSystem'), \
             patch('handler.passthrough_handler.PassthroughHandler'), \
             patch('task_system.templates.associative_matching.register_template'), \
             patch('memory.indexers.git_repository_indexer.GitRepositoryIndexer') as mock_indexer_class:
            
            # Create mock indexer
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.index_repository.return_value = {"file1.py": "metadata1"}
            
            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create .git directory to make it look like a git repo
                os.makedirs(os.path.join(temp_dir, ".git"))
                
                # Import and create application
                from main import Application
                app = Application()
                
                # Index repository
                result = app.index_repository(temp_dir)
                
                # Verify indexer was created and called
                mock_indexer_class.assert_called_once_with(temp_dir)
                mock_indexer.index_repository.assert_called_once_with(app.memory_system)
                
                # Verify result and indexed_repositories
                assert result is True
                assert temp_dir in app.indexed_repositories
    
    def test_handle_query(self):
        """Test handling a query."""
        with patch('memory.memory_system.MemorySystem'), \
             patch('task_system.task_system.TaskSystem'), \
             patch('handler.passthrough_handler.PassthroughHandler') as mock_handler_class, \
             patch('task_system.templates.associative_matching.register_template'):
            
            # Create mock handler
            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.handle_query.return_value = {"content": "response", "metadata": {}}
            
            # Import and create application
            from main import Application
            app = Application()
            
            # Handle query
            result = app.handle_query("test query")
            
            # Verify handler.handle_query was called
            mock_handler.handle_query.assert_called_once_with("test query")
            
            # Verify result
            assert result == {"content": "response", "metadata": {}}
    
    def test_reset_conversation(self):
        """Test resetting conversation."""
        with patch('memory.memory_system.MemorySystem'), \
             patch('task_system.task_system.TaskSystem'), \
             patch('handler.passthrough_handler.PassthroughHandler') as mock_handler_class, \
             patch('task_system.templates.associative_matching.register_template'):
            
            # Create mock handler
            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            
            # Import and create application
            from main import Application
            app = Application()
            
            # Reset conversation
            app.reset_conversation()
            
            # Verify handler.reset_conversation was called
            mock_handler.reset_conversation.assert_called_once()
