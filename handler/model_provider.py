"""
Model provider module for Anthropic Claude API integration.
"""
import os
from typing import Dict, List, Optional, Union

import anthropic

class ClaudeProvider:
    """
    Claude API integration for LLM interactions.
    """
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-sonnet-20240229"):
        """
        Initialize Claude provider with API key and model.
        
        Args:
            api_key: Anthropic API key, defaults to ANTHROPIC_API_KEY environment variable
            model: Claude model to use, defaults to claude-3-sonnet
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.")
        
        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
        # Default parameters
        self.default_params = {
            "temperature": 0.7,
            "max_tokens": 4000
        }
    
    def send_message(self, 
                     messages: List[Dict[str, str]], 
                     system_prompt: str = "", 
                     temperature: Optional[float] = None,
                     max_tokens: Optional[int] = None) -> str:
        """
        Send messages to Claude API and get response.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            system_prompt: System prompt to provide instructions to Claude
            temperature: Temperature parameter (0-1), defaults to 0.7
            max_tokens: Maximum tokens in response, defaults to 4000
            
        Returns:
            Claude's response text
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=messages,
                temperature=temperature or self.default_params["temperature"],
                max_tokens=max_tokens or self.default_params["max_tokens"]
            )
            return response.content[0].text
        except Exception as e:
            # Basic error handling
            error_msg = f"Error calling Claude API: {str(e)}"
            print(error_msg)  # Log the error
            return error_msg
