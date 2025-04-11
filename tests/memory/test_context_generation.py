"""Tests for the context generation input class."""
import pytest
from memory.context_generation import ContextGenerationInput


class TestContextGenerationInput:
    """Tests for the ContextGenerationInput class."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        input_obj = ContextGenerationInput()
        
        assert input_obj.template_description == ""
        assert input_obj.template_type == ""
        assert input_obj.template_subtype == ""
        assert input_obj.inputs == {}
        assert input_obj.context_relevance == {}
        assert input_obj.inherited_context == ""
        assert input_obj.previous_outputs == []
    
    def test_init_with_values(self):
        """Test initialization with specific values."""
        inputs = {"param1": "value1", "param2": 42}
        relevance = {"param1": True, "param2": False}
        
        input_obj = ContextGenerationInput(
            template_description="Test description",
            template_type="test_type",
            template_subtype="test_subtype",
            inputs=inputs,
            context_relevance=relevance,
            inherited_context="Previous context",
            previous_outputs=["Output 1", "Output 2"]
        )
        
        assert input_obj.template_description == "Test description"
        assert input_obj.template_type == "test_type"
        assert input_obj.template_subtype == "test_subtype"
        assert input_obj.inputs == inputs
        assert input_obj.context_relevance == relevance
        assert input_obj.inherited_context == "Previous context"
        assert input_obj.previous_outputs == ["Output 1", "Output 2"]
    
    def test_auto_generate_relevance(self):
        """Test auto-generation of context relevance."""
        inputs = {"param1": "value1", "param2": 42}
        
        input_obj = ContextGenerationInput(
            template_description="Test",
            inputs=inputs
        )
        
        # Should auto-generate relevance for all inputs
        assert "param1" in input_obj.context_relevance
        assert "param2" in input_obj.context_relevance
        assert input_obj.context_relevance["param1"] is True
        assert input_obj.context_relevance["param2"] is True
    
    def test_from_legacy_format(self):
        """Test creation from legacy format."""
        legacy_input = {
            "taskText": "Test query",
            "inheritedContext": "Previous context",
            "previousOutputs": ["Output 1"]
        }
        
        input_obj = ContextGenerationInput.from_legacy_format(legacy_input)
        
        assert input_obj.template_description == "Test query"
        assert input_obj.inherited_context == "Previous context"
        assert input_obj.previous_outputs == ["Output 1"]
        assert input_obj.inputs == {}
