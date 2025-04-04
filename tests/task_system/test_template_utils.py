"""Tests for template utility functions."""
import pytest
from task_system.template_utils import (
    resolve_parameters,
    ensure_template_compatibility,
    get_preferred_model
)

class TestResolveParameters:
    """Tests for the resolve_parameters function."""
    
    def test_standard_parameters(self):
        """Test resolving parameters with valid inputs."""
        template = {
            "parameters": {
                "query": {"type": "string", "required": True},
                "max_results": {"type": "integer", "default": 10}
            }
        }
        
        args = {"query": "test query"}
        result = resolve_parameters(template, args)
        
        assert result["query"] == "test query"
        assert result["max_results"] == 10  # Default value applied
    
    def test_all_parameters_provided(self):
        """Test when all parameters are provided by the caller."""
        template = {
            "parameters": {
                "query": {"type": "string", "required": True},
                "max_results": {"type": "integer", "default": 10}
            }
        }
        
        args = {"query": "test query", "max_results": 20}
        result = resolve_parameters(template, args)
        
        assert result["query"] == "test query"
        assert result["max_results"] == 20  # User-provided value used instead of default
    
    def test_missing_required_parameter(self):
        """Test error when required parameter is missing."""
        template = {
            "parameters": {
                "query": {"type": "string", "required": True},
                "max_results": {"type": "integer", "default": 10}
            }
        }
        
        args = {}  # Missing required 'query' parameter
        
        with pytest.raises(ValueError) as excinfo:
            resolve_parameters(template, args)
        
        assert "Missing required parameter: query" in str(excinfo.value)
    
    def test_type_validation_string(self):
        """Test type validation for string parameters."""
        template = {
            "parameters": {
                "query": {"type": "string", "required": True}
            }
        }
        
        # Invalid type: number instead of string
        args = {"query": 123}
        
        with pytest.raises(ValueError) as excinfo:
            resolve_parameters(template, args)
        
        assert "expected type 'string'" in str(excinfo.value)
    
    def test_type_validation_integer(self):
        """Test type validation for integer parameters."""
        template = {
            "parameters": {
                "count": {"type": "integer", "required": True}
            }
        }
        
        # Invalid type: string instead of integer
        args = {"count": "10"}
        
        with pytest.raises(ValueError) as excinfo:
            resolve_parameters(template, args)
        
        assert "expected type 'integer'" in str(excinfo.value)
    
    def test_backward_compatibility(self):
        """Test backward compatibility with templates without parameters."""
        template = {}  # No parameters defined
        args = {"query": "test", "max_results": 5}
        
        # Should return args as-is
        result = resolve_parameters(template, args)
        
        assert result == args


class TestEnsureTemplateCompatibility:
    """Tests for the ensure_template_compatibility function."""
    
    def test_minimal_template_enhancement(self):
        """Test enhancing a minimal template with required fields."""
        minimal_template = {
            "type": "atomic",
            "subtype": "test"
        }
        
        enhanced = ensure_template_compatibility(minimal_template)
        
        # Check that all required fields were added
        assert "name" in enhanced
        assert enhanced["name"] == "atomic_test"
        assert "parameters" in enhanced
        assert "model" in enhanced
        assert "returns" in enhanced
    
    def test_convert_inputs_to_parameters(self):
        """Test converting legacy 'inputs' to structured 'parameters'."""
        legacy_template = {
            "type": "atomic",
            "subtype": "test",
            "inputs": {
                "query": "Search query",
                "limit": "Maximum results"
            }
        }
        
        enhanced = ensure_template_compatibility(legacy_template)
        
        # Check that inputs were converted to parameters
        assert "parameters" in enhanced
        assert "query" in enhanced["parameters"]
        assert enhanced["parameters"]["query"]["type"] == "string"
        assert enhanced["parameters"]["query"]["description"] == "Search query"
        assert enhanced["parameters"]["query"]["required"] is True
    
    def test_simple_model_to_structured(self):
        """Test converting simple string model to structured format."""
        template = {
            "type": "atomic",
            "subtype": "test",
            "model": "claude-3"
        }
        
        enhanced = ensure_template_compatibility(template)
        
        # Check that model was converted to structured format
        assert isinstance(enhanced["model"], dict)
        assert enhanced["model"]["preferred"] == "claude-3"
        assert "fallback" in enhanced["model"]
    
    def test_preserve_existing_fields(self):
        """Test that existing fields are preserved."""
        template = {
            "type": "atomic",
            "subtype": "test",
            "name": "custom_name",
            "description": "Custom description",
            "parameters": {
                "custom": {"type": "string"}
            }
        }
        
        enhanced = ensure_template_compatibility(template)
        
        # Check that existing fields were preserved
        assert enhanced["name"] == "custom_name"
        assert enhanced["description"] == "Custom description"
        assert "custom" in enhanced["parameters"]


class TestGetPreferredModel:
    """Tests for the get_preferred_model function."""
    
    def test_preferred_model_available(self):
        """Test when preferred model is available."""
        template = {
            "model": {
                "preferred": "claude-3",
                "fallback": ["gpt-4", "llama-3"]
            }
        }
        
        available_models = ["claude-3", "gpt-4", "llama-3"]
        model = get_preferred_model(template, available_models)
        
        assert model == "claude-3"
    
    def test_fallback_model_selection(self):
        """Test fallback selection when preferred is unavailable."""
        template = {
            "model": {
                "preferred": "claude-3",
                "fallback": ["gpt-4", "llama-3"]
            }
        }
        
        available_models = ["gpt-4", "llama-3"]  # claude-3 not available
        model = get_preferred_model(template, available_models)
        
        assert model == "gpt-4"  # First fallback
    
    def test_second_fallback_selection(self):
        """Test second fallback selection."""
        template = {
            "model": {
                "preferred": "claude-3",
                "fallback": ["gpt-4", "llama-3"]
            }
        }
        
        available_models = ["llama-3"]  # Only second fallback available
        model = get_preferred_model(template, available_models)
        
        assert model == "llama-3"
    
    def test_default_when_no_match(self):
        """Test default behavior when no matches exist."""
        template = {
            "model": {
                "preferred": "claude-3",
                "fallback": ["gpt-4", "llama-3"]
            }
        }
        
        available_models = ["other-model"]  # No matches
        model = get_preferred_model(template, available_models)
        
        assert model == "other-model"  # Default to first available
    
    def test_string_model_preference(self):
        """Test with simple string model preference."""
        template = {
            "model": "claude-3"
        }
        
        available_models = ["claude-3", "gpt-4"]
        model = get_preferred_model(template, available_models)
        
        assert model == "claude-3"
