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

    def test_normalize_text(self):
        """Test normalizing text for scoring."""
        text = "The quick Brown Fox Jumps over the lazy DOG. 123 test456"
        result = associative_matching.normalize_text(text)
        
        # Should normalize case, remove stop words, keep words >= 3 chars
        assert "the" not in result  # Stop word removed
        assert "quick" in result
        assert "brown" in result
        assert "fox" in result
        assert "jumps" in result
        assert "over" not in result  # Stop word removed
        assert "lazy" in result
        assert "dog" in result
        assert "123" not in result  # Less than 3 chars
        assert "test456" in result

    @patch('task_system.templates.associative_matching.get_global_index')
    def test_score_files(self, mock_get_index):
        """Test scoring files based on query terms."""
        # Create sample metadata
        file_metadata = {
            "/path/file1.py": "File: file1.py\nType: py\nIdentifiers: process_data, load_config",
            "/path/file2.txt": "File: file2.txt\nType: txt\nPreview: Sample document about data processing",
            "/path/file3.md": "File: file3.md\nType: md\nHeadings: Configuration, Data Processing"
        }
        
        # Test with a query related to data processing
        query_terms = ["data", "process", "config"]
        
        scores = associative_matching.score_files(file_metadata, query_terms)
        
        # All files should have non-zero scores
        assert len(scores) == 3
        
        # Check if scoring order makes sense
        file_paths = [path for path, score in scores]
        
        # file1.py should be first since it has "process" and "config" in identifiers
        assert "/path/file1.py" == file_paths[0]
        
        # file3.md should be next since it has "config" in headings and "process" in heading
        assert "/path/file3.md" == file_paths[1]

    @patch('task_system.templates.associative_matching.get_global_index')
    def test_execute_template(self, mock_get_index):
        """Test executing the template with a query."""
        # Create sample metadata
        file_metadata = {
            "/path/file1.py": "File: file1.py\nType: py\nIdentifiers: process_data, load_config",
            "/path/file2.txt": "File: file2.txt\nType: txt\nPreview: Sample document about data processing",
            "/path/file3.md": "File: file3.md\nType: md\nHeadings: Configuration, Data Processing"
        }
        
        # Mock the global index retrieval
        mock_get_index.return_value = file_metadata
        
        # Create a mock memory system
        mock_memory = MagicMock()
        
        # Test with a simple query
        result = associative_matching.execute_template("data processing config", mock_memory)
        
        # Should return a list of file paths
        assert isinstance(result, list)
        assert all(isinstance(item, str) for item in result)
        assert len(result) == 3  # All files match in some way

        # Test with no matching files
        mock_get_index.return_value = {}
        result = associative_matching.execute_template("query", mock_memory)
        assert result == []

    def test_get_global_index(self):
        """Test getting the global index from different memory system implementations."""
        # Test with get_global_index method
        memory1 = MagicMock()
        memory1.get_global_index.return_value = {"file1": "metadata1"}
        result1 = associative_matching.get_global_index(memory1)
        assert result1 == {"file1": "metadata1"}
        
        # Test with global_index attribute
        memory2 = MagicMock()
        memory2.get_global_index = None
        memory2.global_index = {"file2": "metadata2"}
        result2 = associative_matching.get_global_index(memory2)
        assert result2 == {"file2": "metadata2"}
        
        # Test with neither method nor attribute
        memory3 = MagicMock()
        memory3.get_global_index = None
        memory3.global_index = None
        result3 = associative_matching.get_global_index(memory3)
        assert result3 == {}
