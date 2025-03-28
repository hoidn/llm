"""Tests for the AssociativeMatchingTemplate."""
import pytest
from unittest.mock import patch, MagicMock
import task_system.templates.associative_matching as associative_matching

class TestAssociativeMatchingTemplate:
    """Tests for the AssociativeMatchingTemplate."""

    def test_template_structure(self):
        """Test the structure of the associative matching template."""
        template = associative_matching.ASSOCIATIVE_MATCHING_TEMPLATE
        
        assert template["type"] == "atomic"
        assert template["subtype"] == "associative_matching"
        assert "description" in template
        assert "inputs" in template
        assert "query" in template["inputs"]
        assert "context_management" in template
        assert template["context_management"]["inherit_context"] == "none"
        assert template["context_management"]["accumulate_data"] is False
        assert template["context_management"]["fresh_context"] == "disabled"
        assert "output_format" in template
        assert template["output_format"]["type"] == "json"
        assert template["output_format"]["schema"] == "string[]"

    def test_register_template(self, mock_task_system):
        """Test registering the template with the task system."""
        associative_matching.register_template(mock_task_system)
        
        mock_task_system.register_template.assert_called_once_with(
            associative_matching.ASSOCIATIVE_MATCHING_TEMPLATE
        )

    def test_create_xml_template(self):
        """Test creating the XML representation of the template."""
        xml = associative_matching.create_xml_template()
        
        assert "<task type=\"atomic\" subtype=\"associative_matching\">" in xml
        assert "<description>" in xml
        assert "<input name=\"query\">" in xml
        assert "<inherit_context>none</inherit_context>" in xml
        assert "<accumulate_data>false</accumulate_data>" in xml
        assert "<fresh_context>disabled</fresh_context>" in xml
        assert "<output_format type=\"json\" schema=\"string[]\" />" in xml
