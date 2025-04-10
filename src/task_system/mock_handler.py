"""Mock Handler implementation for testing Task System integration.

This module provides a simple Handler implementation that follows the
expected interface and correctly implements the Hierarchical System Prompt
Pattern for testing.
"""
from typing import Dict, List, Any, Optional, Union

class MockHandler:
    """
    Mock Handler for testing Task System integration.
    
    This class provides a simplified implementation of the Handler interface
    for testing the integration with TaskSystem, particularly for system
    prompt handling.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the mock handler.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.base_system_prompt = self.config.get(
            "base_system_prompt", 
            "You are a helpful assistant that responds to user queries."
        )
        self.execution_history = []
    
    def _build_system_prompt(self, template_system_prompt=None, file_context=None) -> str:
        """
        Build the complete system prompt by combining base, template, and file context.
        
        Implements the Hierarchical System Prompt Pattern by combining:
        1. Base system prompt (universal behaviors)
        2. Template-specific system prompt (task-specific instructions)
        3. File context (relevant files for the current query)
        
        Args:
            template_system_prompt: Optional template-specific system prompt
            file_context: Optional file context string
            
        Returns:
            Complete system prompt
        """
        # Start with base system prompt
        system_prompt = self.base_system_prompt
        
        # Add template-specific system prompt if available
        if template_system_prompt:
            system_prompt = f"{system_prompt}\n\n===\n\n{template_system_prompt}"
        
        # Add file context if available
        if file_context:
            system_prompt = f"{system_prompt}\n\n===\n\nRelevant files:\n{file_context}"
        
        return system_prompt
    
    def execute_prompt(self, 
                      prompt: str, 
                      template_system_prompt: Optional[str] = None,
                      file_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a prompt with the given system prompt components.
        
        Args:
            prompt: The main prompt text
            template_system_prompt: Optional template-specific system prompt
            file_context: Optional file context string
            
        Returns:
            Result dictionary with status, content, and system prompt info
        """
        # Build the complete system prompt
        system_prompt = self._build_system_prompt(template_system_prompt, file_context)
        
        # Record the execution for testing
        execution_record = {
            "prompt": prompt,
            "template_system_prompt": template_system_prompt,
            "file_context": file_context,
            "system_prompt": system_prompt
        }
        self.execution_history.append(execution_record)
        
        # Return a mock result
        return {
            "status": "COMPLETE",
            "content": prompt,  # For testing, just echo the prompt
            "notes": {
                "system_prompt": system_prompt,
                "execution_record": execution_record
            }
        }
    
    def reset(self):
        """Reset the handler state."""
        self.execution_history = []
