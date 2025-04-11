"""Tests for the system prompt registry."""
import pytest
from system.prompt_registry import PromptRegistry


class TestPromptRegistry:
    """Tests for the PromptRegistry class."""
    
    def test_singleton_pattern(self):
        """Test that PromptRegistry implements the Singleton pattern."""
        registry1 = PromptRegistry()
        registry2 = PromptRegistry()
        
        assert registry1 is registry2
    
    def test_default_prompts(self):
        """Test that default prompts are initialized."""
        registry = PromptRegistry()
        
        assert "file_relevance" in registry.prompts
        assert registry.get_prompt("file_relevance") is not None
    
    def test_get_prompt(self):
        """Test getting prompts by key."""
        registry = PromptRegistry()
        
        # Existing prompt
        assert registry.get_prompt("file_relevance") is not None
        
        # Non-existent prompt
        assert registry.get_prompt("nonexistent_prompt") is None
    
    def test_set_prompt(self):
        """Test setting prompts."""
        registry = PromptRegistry()
        
        # Set a new prompt
        registry.set_prompt("test_prompt", "This is a test prompt")
        assert registry.get_prompt("test_prompt") == "This is a test prompt"
        
        # Update existing prompt
        registry.set_prompt("file_relevance", "Updated file relevance prompt")
        assert registry.get_prompt("file_relevance") == "Updated file relevance prompt"
    
    def test_has_prompt(self):
        """Test checking if a prompt exists."""
        registry = PromptRegistry()
        
        assert registry.has_prompt("file_relevance") is True
        assert registry.has_prompt("nonexistent_prompt") is False
