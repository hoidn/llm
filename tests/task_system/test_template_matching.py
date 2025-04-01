"""Tests for template matching in TaskSystem."""
import pytest
from unittest.mock import patch, MagicMock

from task_system.task_system import TaskSystem

class TestTemplateMatching:
    """Tests for template matching functionality in TaskSystem."""
    
    def test_calculate_similarity_score(self):
        """Test calculating similarity score between texts."""
        task_system = TaskSystem()
        
        # Test identical texts
        score1 = task_system._calculate_similarity_score(
            "Find relevant files for query",
            "Find relevant files for query"
        )
        assert score1 == 1.0
        
        # Test similar texts
        score2 = task_system._calculate_similarity_score(
            "Find files related to this query",
            "Find relevant files for query"
        )
        assert 0 < score2 < 1.0
        
        # Test dissimilar texts
        score3 = task_system._calculate_similarity_score(
            "Create a new task",
            "Find relevant files for query"
        )
        assert score3 < score2
    
    def test_find_matching_tasks(self, mock_memory_system):
        """Test finding matching tasks for input text."""
        task_system = TaskSystem()
        
        # Register test templates
        task_system.templates = {
            "atomic:associative_matching": {
                "type": "atomic",
                "subtype": "associative_matching",
                "description": "Find relevant files for the given query"
            },
            "atomic:standard": {
                "type": "atomic",
                "subtype": "standard",
                "description": "Process data and generate report"
            },
            "sequential:test": {
                "type": "sequential",
                "description": "Sequential task that should not be matched"
            }
        }
        
        # Test with matching query
        matches1 = task_system.find_matching_tasks("Find files for my query", mock_memory_system)
        assert len(matches1) > 0
        assert matches1[0]["task"]["subtype"] == "associative_matching"
        
        # Test with different query
        matches2 = task_system.find_matching_tasks("Generate a report from my data", mock_memory_system)
        assert len(matches2) > 0
        assert matches2[0]["task"]["subtype"] == "standard"
        
        # Verify all returned matches are atomic tasks
        for match in matches1 + matches2:
            assert match["taskType"] == "atomic"
