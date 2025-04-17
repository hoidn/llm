"""Unit tests for debug templates."""
import pytest
from unittest.mock import MagicMock

from src.task_system.templates.debug_templates import (
    DEBUG_ANALYZE_RESULTS_TEMPLATE,
    DEBUG_GENERATE_FIX_TEMPLATE,
    register_debug_templates
)


class TestDebugTemplateStructures:
    """Tests for the debug template structures."""

    def test_analyze_results_template_structure(self):
        """Test the structure of DEBUG_ANALYZE_RESULTS_TEMPLATE."""
        # Assert it's a dictionary
        assert isinstance(DEBUG_ANALYZE_RESULTS_TEMPLATE, dict)
        
        # Assert required keys exist
        required_keys = ["name", "type", "subtype", "description", "parameters", "output_format", "system_prompt"]
        for key in required_keys:
            assert key in DEBUG_ANALYZE_RESULTS_TEMPLATE, f"Missing required key: {key}"
        
        # Assert name is correct
        assert DEBUG_ANALYZE_RESULTS_TEMPLATE["name"] == "debug:analyze_test_results"
        
        # Assert type and subtype are correct
        assert DEBUG_ANALYZE_RESULTS_TEMPLATE["type"] == "atomic"
        assert DEBUG_ANALYZE_RESULTS_TEMPLATE["subtype"] == "debug_analysis"
        
        # Assert parameters contain expected keys with correct definitions
        parameters = DEBUG_ANALYZE_RESULTS_TEMPLATE["parameters"]
        assert "test_stdout" in parameters
        assert "test_stderr" in parameters
        assert "test_exit_code" in parameters
        
        # Check test_exit_code is required
        assert parameters["test_exit_code"]["required"] is True
        assert parameters["test_exit_code"]["type"] == "integer"
        
        # Check test_stdout and test_stderr are optional with defaults
        assert parameters["test_stdout"]["required"] is False
        assert "default" in parameters["test_stdout"]
        assert parameters["test_stderr"]["required"] is False
        assert "default" in parameters["test_stderr"]
        
        # Assert output_format is JSON with schema
        assert DEBUG_ANALYZE_RESULTS_TEMPLATE["output_format"]["type"] == "json"
        assert "schema" in DEBUG_ANALYZE_RESULTS_TEMPLATE["output_format"]
        assert len(DEBUG_ANALYZE_RESULTS_TEMPLATE["output_format"]["schema"]) > 0
        
        # Assert system_prompt is non-empty
        assert len(DEBUG_ANALYZE_RESULTS_TEMPLATE["system_prompt"]) > 0
        assert "Test Exit Code: {{ test_exit_code }}" in DEBUG_ANALYZE_RESULTS_TEMPLATE["system_prompt"]

    def test_generate_fix_template_structure(self):
        """Test the structure of DEBUG_GENERATE_FIX_TEMPLATE."""
        # Assert it's a dictionary
        assert isinstance(DEBUG_GENERATE_FIX_TEMPLATE, dict)
        
        # Assert required keys exist
        required_keys = ["name", "type", "subtype", "description", "parameters", "output_format", "system_prompt"]
        for key in required_keys:
            assert key in DEBUG_GENERATE_FIX_TEMPLATE, f"Missing required key: {key}"
        
        # Assert name is correct
        assert DEBUG_GENERATE_FIX_TEMPLATE["name"] == "debug:generate_fix"
        
        # Assert type and subtype are correct
        assert DEBUG_GENERATE_FIX_TEMPLATE["type"] == "atomic"
        assert DEBUG_GENERATE_FIX_TEMPLATE["subtype"] == "debug_fix_generation"
        
        # Assert parameters contain expected keys with correct definitions
        parameters = DEBUG_GENERATE_FIX_TEMPLATE["parameters"]
        assert "error_details" in parameters
        assert "code_context" in parameters
        
        # Check both parameters are required
        assert parameters["error_details"]["required"] is True
        assert parameters["error_details"]["type"] == "object"
        assert parameters["code_context"]["required"] is True
        assert parameters["code_context"]["type"] == "string"
        
        # Assert output_format is text
        assert DEBUG_GENERATE_FIX_TEMPLATE["output_format"]["type"] == "text"
        
        # Assert system_prompt is non-empty
        assert len(DEBUG_GENERATE_FIX_TEMPLATE["system_prompt"]) > 0
        assert "Error Details:" in DEBUG_GENERATE_FIX_TEMPLATE["system_prompt"]
        assert "Relevant Code Context:" in DEBUG_GENERATE_FIX_TEMPLATE["system_prompt"]
        assert "{{ error_details | tojson }}" in DEBUG_GENERATE_FIX_TEMPLATE["system_prompt"]
        assert "{{ code_context }}" in DEBUG_GENERATE_FIX_TEMPLATE["system_prompt"]


class TestDebugTemplateRegistration:
    """Tests for the debug template registration function."""

    def test_register_debug_templates(self):
        """Test the register_debug_templates function."""
        # Create a mock TaskSystem
        mock_task_system = MagicMock()
        
        # Call the registration function
        register_debug_templates(mock_task_system)
        
        # Assert register_template was called at least twice
        assert mock_task_system.register_template.call_count >= 2
        
        # Verify the templates were registered
        mock_task_system.register_template.assert_any_call(DEBUG_ANALYZE_RESULTS_TEMPLATE)
        mock_task_system.register_template.assert_any_call(DEBUG_GENERATE_FIX_TEMPLATE)

    def test_register_debug_templates_missing_method(self):
        """Test register_debug_templates with a TaskSystem missing the register_template method."""
        # Create a mock without register_template method
        mock_task_system = MagicMock(spec=[])
        
        # Call the registration function (should not raise exception)
        register_debug_templates(mock_task_system)
        
        # No assertions needed - function should handle this gracefully
