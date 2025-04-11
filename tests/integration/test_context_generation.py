"""Integration tests for template-aware context generation."""
import pytest
from unittest.mock import patch, MagicMock
import os
import tempfile

from memory.context_generation import ContextGenerationInput as RealContextGenerationInput
from src.task_system.templates.context_examples import (
    INCLUDE_ALL_TEMPLATE,
    SELECTIVE_CONTEXT_TEMPLATE,
    COMPLEX_CONTEXT_TEMPLATE
)

class TestTemplateAwareContextGeneration:
    """Integration tests for template-aware context generation."""
    
    @pytest.fixture
    def components(self):
        """Set up components for testing."""
        from src.memory.memory_system import MemorySystem
        from src.task_system.task_system import TaskSystem
        from src.handler.base_handler import BaseHandler
        
        # Create components
        task_system = TaskSystem()
        memory_system = MagicMock()
        handler = MagicMock()
        
        # Register test templates
        task_system.register_template(INCLUDE_ALL_TEMPLATE)
        task_system.register_template(SELECTIVE_CONTEXT_TEMPLATE)
        task_system.register_template(COMPLEX_CONTEXT_TEMPLATE)
        
        # Print template registration status
        print(f"Templates registered: {list(task_system.templates.keys())}")
        print(f"Template index: {task_system.template_index}")
        
        return task_system, memory_system, handler
    
    def test_inclusive_context_template(self, components):
        """Test template that includes all inputs in context."""
        task_system, memory_system, handler = components
        
        # Set up memory_system mock to capture context input
        context_input_capture = {}
        def capture_context_input(input_data):
            nonlocal context_input_capture
            print(f"CAPTURE CALLED: {type(input_data)}")
            if isinstance(input_data, RealContextGenerationInput):
                context_input_capture = {
                    "template_description": input_data.template_description,
                    "inputs": input_data.inputs,
                    "context_relevance": input_data.context_relevance
                }
                print(f"CAPTURED DATA: {context_input_capture}")
            else:
                print(f"Input data is not RealContextGenerationInput: {type(input_data)}")
            # Return a mock result
            mock_result = MagicMock()
            mock_result.matches = [("file1.py", "metadata1")]
            return mock_result
            
        memory_system.get_relevant_context_for.side_effect = capture_context_input
        
        # Execute the task
        inputs = {
            "query": "authentication",
            "filter_type": "python",
            "max_results": 5
        }
        task_system.execute_task("atomic", "inclusive_context", inputs, memory_system)
        
        # Verify context input
        assert "inputs" in context_input_capture
        assert context_input_capture["inputs"]["query"] == "authentication"
        assert context_input_capture["inputs"]["filter_type"] == "python"
        assert context_input_capture["inputs"]["max_results"] == 5
        
        # Verify all inputs included in context_relevance
        assert "context_relevance" in context_input_capture
        assert context_input_capture["context_relevance"]["query"] is True
        assert context_input_capture["context_relevance"]["filter_type"] is True
        assert context_input_capture["context_relevance"]["max_results"] is True
    
    def test_selective_context_template(self, components):
        """Test template that selectively includes inputs in context."""
        task_system, memory_system, handler = components
        
        # Set up memory_system mock to capture context input
        context_input_capture = {}
        def capture_context_input(input_data):
            nonlocal context_input_capture
            print(f"CAPTURE CALLED: {type(input_data)}")
            if isinstance(input_data, RealContextGenerationInput):
                context_input_capture = {
                    "template_description": input_data.template_description,
                    "inputs": input_data.inputs,
                    "context_relevance": input_data.context_relevance
                }
                print(f"CAPTURED DATA: {context_input_capture}")
            else:
                print(f"Input data is not RealContextGenerationInput: {type(input_data)}")
            # Return a mock result
            mock_result = MagicMock()
            mock_result.matches = [("file1.py", "metadata1")]
            return mock_result
            
        memory_system.get_relevant_context_for.side_effect = capture_context_input
        
        # Execute the task
        inputs = {
            "main_query": "user authentication",
            "secondary_topics": ["login", "security"],
            "excluded_topics": ["password reset"],
            "max_results": 15
        }
        task_system.execute_task("atomic", "selective_context", inputs, memory_system)
        
        # Verify context input
        assert "inputs" in context_input_capture
        assert context_input_capture["inputs"]["main_query"] == "user authentication"
        assert "login" in context_input_capture["inputs"]["secondary_topics"]
        assert "password reset" in context_input_capture["inputs"]["excluded_topics"]
        assert context_input_capture["inputs"]["max_results"] == 15
        
        # Verify selective inclusion in context_relevance
        assert "context_relevance" in context_input_capture
        assert context_input_capture["context_relevance"]["main_query"] is True
        assert context_input_capture["context_relevance"]["secondary_topics"] is True
        assert context_input_capture["context_relevance"]["excluded_topics"] is True
        assert context_input_capture["context_relevance"]["max_results"] is False
    
    def test_complex_context_template(self, components):
        """Test template with complex structured inputs."""
        task_system, memory_system, handler = components
        
        # Set up memory_system mock to capture context input
        context_input_capture = {}
        def capture_context_input(input_data):
            nonlocal context_input_capture
            print(f"CAPTURE CALLED: {type(input_data)}")
            if isinstance(input_data, RealContextGenerationInput):
                context_input_capture = {
                    "template_description": input_data.template_description,
                    "inputs": input_data.inputs,
                    "context_relevance": input_data.context_relevance
                }
                print(f"CAPTURED DATA: {context_input_capture}")
            else:
                print(f"Input data is not RealContextGenerationInput: {type(input_data)}")
            # Return a mock result
            mock_result = MagicMock()
            mock_result.matches = [("file1.py", "metadata1")]
            return mock_result
            
        memory_system.get_relevant_context_for.side_effect = capture_context_input
        
        # Execute the task
        inputs = {
            "project_info": {
                "name": "auth_service",
                "language": "python",
                "version": "2.1.0"
            },
            "search_patterns": [
                {"pattern": "authenticate\\(.*\\)", "importance": "high"},
                {"pattern": "validate_token", "importance": "medium"}
            ],
            "output_format": "markdown"
        }
        task_system.execute_task("atomic", "complex_context", inputs, memory_system)
        
        # Verify context input
        assert "inputs" in context_input_capture
        assert context_input_capture["inputs"]["project_info"]["name"] == "auth_service"
        assert len(context_input_capture["inputs"]["search_patterns"]) == 2
        assert context_input_capture["inputs"]["search_patterns"][0]["pattern"] == "authenticate\\(.*\\)"
        assert context_input_capture["inputs"]["output_format"] == "markdown"
        
        # Verify selective inclusion in context_relevance
        assert "context_relevance" in context_input_capture
        assert context_input_capture["context_relevance"]["project_info"] is True
        assert context_input_capture["context_relevance"]["search_patterns"] is True
        assert context_input_capture["context_relevance"]["output_format"] is False
    
    def test_handler_receives_context_input(self, components):
        """Test that handler receives the ContextGenerationInput object directly."""
        task_system, memory_system, handler = components
        
        # Set up handler mock to capture the input to determine_relevant_files
        context_input_capture = None
        def capture_handler_input(context_input, file_metadata):
            nonlocal context_input_capture
            print(f"HANDLER CAPTURE CALLED: {type(context_input)}")
            context_input_capture = context_input
            if hasattr(context_input, 'template_description'):
                print(f"HANDLER CAPTURED: {context_input.template_description}")
            return [("file1.py", "metadata1")]
            
        handler.determine_relevant_files.side_effect = capture_handler_input
        memory_system.handler = handler
        memory_system.get_global_index.return_value = {"file1.py": "metadata1"}
        
        # Create a mock that correctly passes through to the handler
        def get_relevant_context_for(input_data):
            if hasattr(memory_system, "handler") and memory_system.handler:
                file_metadata = memory_system.get_global_index()
                matches = memory_system.handler.determine_relevant_files(input_data, file_metadata)
                result = MagicMock()
                result.matches = matches
                return result
                
        memory_system.get_relevant_context_for.side_effect = get_relevant_context_for
        
        # Execute the task
        inputs = {"query": "authentication"}
        task_system.execute_task("atomic", "inclusive_context", inputs, memory_system)
        
        # Verify handler received ContextGenerationInput
        assert context_input_capture is not None
        assert isinstance(context_input_capture, RealContextGenerationInput)
        assert context_input_capture.template_description == INCLUDE_ALL_TEMPLATE["description"]
        assert context_input_capture.inputs["query"] == "authentication"
