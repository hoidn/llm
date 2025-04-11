"""Tests for template-aware context generation."""
import pytest
from unittest.mock import patch, MagicMock

from memory.context_generation import ContextGenerationInput
from memory.memory_system import MemorySystem
from handler.base_handler import BaseHandler
from system.prompt_registry import registry as prompt_registry

class TestContextGeneration:
    """Tests for template-aware context generation."""
    
    def test_context_generation_input_creation(self):
        """Test creating a ContextGenerationInput object."""
        # Create a basic input
        context_input = ContextGenerationInput(
            template_description="Test template",
            template_type="atomic",
            template_subtype="test",
            inputs={"query": "test query", "max_results": 10},
            context_relevance={"query": True, "max_results": False}
        )
        
        # Verify fields
        assert context_input.template_description == "Test template"
        assert context_input.template_type == "atomic"
        assert context_input.template_subtype == "test"
        assert context_input.inputs["query"] == "test query"
        assert context_input.inputs["max_results"] == 10
        assert context_input.context_relevance["query"] is True
        assert context_input.context_relevance["max_results"] is False
    
    def test_from_legacy_format(self):
        """Test creating from legacy format."""
        legacy_input = {
            "taskText": "legacy query",
            "inheritedContext": "inherited context"
        }
        
        context_input = ContextGenerationInput.from_legacy_format(legacy_input)
        
        assert context_input.template_description == "legacy query"
        assert context_input.inherited_context == "inherited context"
    
    def test_memory_system_context_retrieval(self):
        """Test context retrieval with ContextGenerationInput."""
        # Create mocks
        mock_handler = MagicMock()
        mock_handler.determine_relevant_files.return_value = [
            ("file1.py", "Relevant to query"),
            ("file2.py", "Contains related functionality")
        ]
        
        # Create memory system with mock handler
        memory_system = MemorySystem(handler=mock_handler)
        memory_system.global_index = {
            "file1.py": "metadata1", 
            "file2.py": "metadata2"
        }
        
        # Create context input
        context_input = ContextGenerationInput(
            template_description="Test query",
            inputs={"param1": "value1", "param2": "value2"},
            context_relevance={"param1": True, "param2": False}
        )
        
        # Get relevant context
        result = memory_system.get_relevant_context_for(context_input)
        
        # Verify handler was called with context input
        mock_handler.determine_relevant_files.assert_called_once()
        args = mock_handler.determine_relevant_files.call_args[0]
        assert args[0] == context_input  # First arg should be context_input
        
        # Verify result
        assert hasattr(result, "matches")
        assert len(result.matches) == 2
        assert result.matches[0][0] == "file1.py"
    
    def test_base_handler_determine_relevant_files(self):
        """Test determine_relevant_files with ContextGenerationInput."""
        # Create mocks
        mock_task_system = MagicMock()
        mock_memory_system = MagicMock()
        mock_provider = MagicMock()
        
        # Setup provider response
        mock_provider.send_message.return_value = """[
            {"path": "file1.py", "relevance": "Relevant to query"},
            {"path": "file2.py", "relevance": "Contains related code"}
        ]"""
        
        # Create handler
        with patch('system.prompt_registry.registry') as mock_registry:
            # Setup mock registry
            mock_registry.get_prompt.return_value = "Test prompt"
            
            # Create handler with mocks
            handler = BaseHandler(mock_task_system, mock_memory_system)
            handler.model_provider = mock_provider
            
            # Create context input
            context_input = ContextGenerationInput(
                template_description="Test query",
                inputs={"param1": "value1", "param2": "value2"},
                context_relevance={"param1": True, "param2": False}
            )
            
            # Create file metadata
            file_metadata = {
                "file1.py": "metadata1",
                "file2.py": "metadata2",
                "file3.py": "metadata3"
            }
            
            # Call determine_relevant_files
            result = handler.determine_relevant_files(context_input, file_metadata)
            
            # Verify registry was used
            mock_registry.get_prompt.assert_called_once_with("file_relevance")
            
            # Verify provider was called with correctly formatted message
            mock_provider.send_message.assert_called_once()
            args = mock_provider.send_message.call_args[0]
            assert len(args) == 0  # No positional args
            kwargs = mock_provider.send_message.call_args[1]
            messages = kwargs["messages"]
            assert len(messages) == 1
            assert messages[0]["role"] == "user"
            
            # Verify message includes query and relevant input (param1)
            message_content = messages[0]["content"]
            assert "Test query" in message_content
            assert "param1: value1" in message_content
            assert "param2" not in message_content
            
            # Verify system prompt was used
            assert kwargs["system_prompt"] == "Test prompt"
            
            # Verify result parsing
            assert len(result) == 2
            assert result[0][0] == "file1.py"
            assert result[0][1] == "Relevant to query"
            assert result[1][0] == "file2.py"
            assert result[1][1] == "Contains related code"
