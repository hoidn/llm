"""Tests for system types including TaskResult."""
import pytest
from pydantic import ValidationError

from src.system.types import TaskResult, TaskStatus


class TestTaskResult:
    """Tests for TaskResult Pydantic model."""
    
    def test_initialization(self):
        """Test basic initialization with valid data."""
        # Test with minimal required fields
        result = TaskResult(status="COMPLETE", content="Test content")
        assert result.status == "COMPLETE"
        assert result.content == "Test content"
        assert result.notes == {}
        
        # Test with all fields
        result_full = TaskResult(
            status="SUCCESS",
            content="Full test content",
            notes={"files_modified": ["file1.py"], "changes": [{"file": "file1.py", "description": "Changed function"}]}
        )
        assert result_full.status == "SUCCESS"
        assert result_full.content == "Full test content"
        assert "files_modified" in result_full.notes
        assert result_full.notes["files_modified"] == ["file1.py"]
    
    def test_validation(self):
        """Test validation of TaskResult fields."""
        # Test with invalid status
        with pytest.raises(ValidationError):
            TaskResult(status="INVALID_STATUS", content="Test")
        
        # Test with missing required field
        with pytest.raises(ValidationError):
            TaskResult(status="COMPLETE")  # missing content
        
        # Test with invalid notes type
        with pytest.raises(ValidationError):
            TaskResult(status="COMPLETE", content="Test", notes="not a dict")
    
    def test_model_dump(self):
        """Test model_dump method."""
        result = TaskResult(
            status="COMPLETE", 
            content="Test content",
            notes={"key": "value"}
        )
        
        dumped = result.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["status"] == "COMPLETE"
        assert dumped["content"] == "Test content"
        assert dumped["notes"] == {"key": "value"}
