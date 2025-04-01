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
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-7-sonnet-20250219"):
        """
        Initialize Claude provider with API key and model.
        
        Args:
            api_key: Anthropic API key, defaults to ANTHROPIC_API_KEY environment variable
            model: Claude model to use, defaults to claude-3-7-sonnet
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        
        # Allow initialization without API key for testing
        if self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None
            print("Warning: No API key provided. Running in test/mock mode.")
        
        # Default parameters
        self.default_params = {
            "temperature": 0.7,
            "max_tokens": 4000
        }
    
    def send_message(self, 
                     messages: List[Dict[str, str]], 
                     system_prompt: str = "", 
                     tools: Optional[List[Dict[str, Any]]] = None,
                     temperature: Optional[float] = None,
                     max_tokens: Optional[int] = None) -> Union[str, Dict[str, Any]]:
        """
        Send messages to Claude API and get response.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            system_prompt: System prompt to provide instructions to Claude
            tools: Optional list of tool specifications in Anthropic format
            temperature: Temperature parameter (0-1), defaults to 0.7
            max_tokens: Maximum tokens in response, defaults to 4000
            
        Returns:
            Claude's response text or a dict with response and tool call info
        """
        # If no client (test mode), return a mock response
        if self.client is None:
            mock_response = f"Mock response for: {messages[-1]['content'] if messages else 'No message'}"
            if tools:
                mock_response += f"\n\nAvailable tools: {[t['name'] for t in tools]}"
            return mock_response
            
        try:
            # Build request parameters
            params = {
                "model": self.model,
                "system": system_prompt,
                "messages": messages,
                "temperature": temperature or self.default_params["temperature"],
                "max_tokens": max_tokens or self.default_params["max_tokens"]
            }
            
            # Add tools if provided
            if tools:
                params["tools"] = tools
            
            # Send request to Claude API
            response = self.client.messages.create(**params)
            
            # Check if response contains tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                # Return both the text and tool call information
                return {
                    "text": response.content[0].text if response.content else "",
                    "tool_calls": response.tool_calls
                }
            
            # Return just the text for regular responses
            return response.content[0].text if response.content else ""
        except Exception as e:
            # Basic error handling
            error_msg = f"Error calling Claude API: {str(e)}"
            print(error_msg)  # Log the error
            return error_msg
