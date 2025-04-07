"""Tests for the template processor."""
import pytest
from unittest.mock import MagicMock, patch

from task_system.template_utils import Environment
from task_system.template_processor import TemplateProcessor


class TestTemplateProcessor:
    """Tests for the TemplateProcessor class."""
    
    @pytest.fixture
    def mock_task_system(self):
        """Create a mock task system."""
        mock_ts = MagicMock()
        
        # Mock resolve_function_calls to append "[PROCESSED]" to the content
        def mock_resolve_function_calls(text, ts, env):
            if isinstance(text, str) and "{{" in text:
                return text.replace("{{", "[PROCESSED]{{")
            return text
            
        mock_ts.resolve_function_calls = mock_resolve_function_calls
        
        return mock_ts
    
    @pytest.fixture
    def processor(self, mock_task_system):
        """Create a template processor."""
        with patch('task_system.template_processor.resolve_function_calls', 
                  side_effect=mock_task_system.resolve_function_calls):
            return TemplateProcessor(mock_task_system)
    
    @pytest.fixture
    def template(self):
        """Create a test template."""
        return {
            "name": "test_template",
            "type": "atomic",
            "subtype": "test",
            "description": "Test template with {{var}} and {{func(arg)}}",
            "system_prompt": "System prompt with {{var}}",
            "taskPrompt": "Task prompt with {{func(arg)}}",
            "custom_field": "Custom field with {{var}} and {{func(arg)}}",
            "non_template_field": "Regular field without templates"
        }
    
    @pytest.fixture
    def environment(self):
        """Create a test environment."""
        return Environment({
            "var": "variable_value",
            "arg": "argument_value"
        })
    
    def test_get_fields_to_process(self, processor, template):
        """Test getting fields to process."""
        fields = processor.get_fields_to_process(template)
        
        # Standard fields should be included
        assert "system_prompt" in fields
        assert "description" in fields
        assert "taskPrompt" in fields
        
        # Custom field with templates should be included
        assert "custom_field" in fields
        
        # Field without templates should not be included
        assert "non_template_field" not in fields
        
        # Type and subtype should not be processed
        assert "type" not in fields
        assert "subtype" not in fields
    
    def test_process_template(self, processor, template, environment):
        """Test processing a template."""
        processed = processor.process_template(template, environment)
        
        # Original template should not be modified
        assert template["description"] == "Test template with {{var}} and {{func(arg)}}"
        
        # Variables should be substituted
        assert "variable_value" in processed["description"]
        assert "variable_value" in processed["system_prompt"]
        assert "variable_value" in processed["custom_field"]
        
        # Function calls should be processed
        assert "[PROCESSED]{{func(arg)}}" in processed["description"]
        assert "[PROCESSED]{{func(arg)}}" in processed["taskPrompt"]
        assert "[PROCESSED]{{func(arg)}}" in processed["custom_field"]
        
        # Non-template fields should remain unchanged
        assert processed["non_template_field"] == "Regular field without templates"
        assert processed["type"] == "atomic"
        assert processed["subtype"] == "test"
    
    def test_process_template_with_empty_fields(self, processor, environment):
        """Test processing a template with empty or missing fields."""
        template = {
            "name": "minimal_template",
            "type": "atomic",
            "subtype": "minimal"
        }
        
        processed = processor.process_template(template, environment)
        
        # Should not add missing fields
        assert "description" not in processed
        assert "system_prompt" not in processed
        
        # Should not modify non-string fields
        template_with_dict = {
            "name": "dict_field_template",
            "type": "atomic",
            "subtype": "dict_field",
            "parameters": {"param1": "value1"}
        }
        
        processed = processor.process_template(template_with_dict, environment)
        assert processed["parameters"] == {"param1": "value1"}
    
    def test_end_to_end_processing(self, mock_task_system):
        """Test end-to-end template processing."""
        # Create a real processor with mocked function resolution
        processor = TemplateProcessor(mock_task_system)
        
        # Create a template with both variables and function calls
        template = {
            "name": "end_to_end",
            "type": "atomic",
            "subtype": "test",
            "description": "Template with {{var}} and {{func(var)}}",
            "system_prompt": "System {{func(system_var)}}"
        }
        
        # Create environment
        env = Environment({"var": "test_value", "system_var": "system_value"})
        
        # Mock substitute_variables to replace {{var}} with the value
        def mock_substitute(text, env):
            if isinstance(text, str):
                for key, value in env.bindings.items():
                    text = text.replace(f"{{{{var}}}}", "test_value")
                    text = text.replace(f"{{{{system_var}}}}", "system_value")
            return text
            
        # Mock resolve_function_calls
        def mock_resolve(text, ts, env):
            if isinstance(text, str):
                text = text.replace("{{func(var)}}", "FUNCTION_RESULT")
                text = text.replace("{{func(system_var)}}", "SYSTEM_FUNCTION_RESULT")
            return text
        
        # Apply the mocks
        with patch('task_system.template_processor.substitute_variables', 
                  side_effect=mock_substitute):
            with patch('task_system.template_processor.resolve_function_calls', 
                      side_effect=mock_resolve):
                
                # Process the template
                processed = processor.process_template(template, env)
                
                # Check results
                assert "test_value" in processed["description"]
                assert "FUNCTION_RESULT" in processed["description"]
                assert "SYSTEM_FUNCTION_RESULT" in processed["system_prompt"]
