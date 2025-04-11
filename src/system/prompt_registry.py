"""Registry for system prompts used throughout the application."""
from typing import Dict, Any, Optional


class PromptRegistry:
    """Registry for system prompts.
    
    Provides a centralized store for system prompts used by LLMs.
    """
    
    _instance = None
    
    def __new__(cls):
        """Implement the Singleton pattern."""
        if cls._instance is None:
            cls._instance = super(PromptRegistry, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the prompt registry with default prompts."""
        self.prompts = {
            "file_relevance": """You are a file relevance assistant. Your task is to select files that are relevant to a user's query.
Examine the metadata of each file and determine which files would be most useful to address the query.

Return ONLY a JSON array of objects with the following format:
[{"path": "path/to/file1.py", "relevance": "Reason this file is relevant"}, ...]

Include only files that are truly relevant to the query. 
The "relevance" field should briefly explain why the file is relevant to the query.

Do not include explanations or other text in your response, just the JSON array."""
        }
    
    def get_prompt(self, key: str) -> Optional[str]:
        """Get a prompt by key.
        
        Args:
            key: Prompt identifier
            
        Returns:
            Prompt text or None if not found
        """
        return self.prompts.get(key)
    
    def set_prompt(self, key: str, prompt: str) -> None:
        """Set a prompt.
        
        Args:
            key: Prompt identifier
            prompt: Prompt text
        """
        self.prompts[key] = prompt
    
    def has_prompt(self, key: str) -> bool:
        """Check if a prompt exists.
        
        Args:
            key: Prompt identifier
            
        Returns:
            True if prompt exists, False otherwise
        """
        return key in self.prompts


# Singleton instance for easy access
registry = PromptRegistry()
