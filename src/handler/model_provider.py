"""
// === IDL-CREATION-GUIDLINES === // Object Oriented: Use OO Design. // Design Patterns: Use Factory, Builder and Strategy patterns where possible // ** Complex parameters JSON : Use JSON where primitive params are not possible and document them in IDL like "Expected JSON format: { "key1": "type1", "key2": "type2" }" // == !! BEGIN IDL TEMPLATE !! === // === CODE-CREATION-RULES === // Strict Typing: Always use strict typing. Avoid using ambiguous or variant types. // Primitive Types: Favor the use of primitive types wherever possible. // Portability Mandate: Python code must be written with the intent to be ported to Java, Go, and JavaScript. Consider language-agnostic logic and avoid platform-specific dependencies. // No Side Effects: Functions should be pure, meaning their output should only be determined by their input without any observable side effects. // Testability: Ensure that every function and method is easily testable. Avoid tight coupling and consider dependency injection where applicable. // Documentation: Every function, method, and module should be thoroughly documented, especially if there's a nuance that's not directly evident from its signature. // Contractual Obligation: The definitions provided in this IDL are a strict contract. All specified interfaces, methods, and constraints must be implemented precisely as defined without deviation. // =======================

@module ModelProviderModule
// Dependencies: anthropic (example concrete dependency)
// Description: Defines the interface for interacting with Large Language Model (LLM) providers
//              and provides concrete implementations (e.g., for Claude). Handles sending
//              messages, managing system prompts, and processing tool calls.
module ModelProviderModule {

    // Abstract interface for all model provider adapters.
    interface ProviderAdapter {
        // @depends_on() // Abstract interface has no direct dependencies

        // Sends a message sequence to the LLM provider.
        // Preconditions:
        // - messages is a list of dictionaries, each with 'role' and 'content'.
        // - system_prompt is a string.
        // - tools is an optional list of tool specifications in the provider's format.
        // Expected JSON format for messages: [ { "role": "user|assistant", "content": "string" }, ... ]
        // Expected JSON format for tools: [ { "name": "string", "description": "string", "input_schema": { ... } }, ... ] (Provider specific)
        // Postconditions:
        // - Sends the request to the configured LLM API endpoint.
        // - Returns the raw response from the provider, which could be a string or a structured dictionary (often including content and tool call info).
        union<string, dict<string, Any>> send_message(
            list<dict<string, string>> messages,
            optional string system_prompt,
            optional list<dict<string, Any>> tools
        );

        // Extracts tool calls and content from the provider's response.
        // Preconditions:
        // - response is the raw response object/string received from `send_message`.
        // Postconditions:
        // - Parses the provider-specific response format.
        // - Returns a standardized dictionary containing the text content, a list of extracted tool calls (name, parameters), and a flag indicating if the model is awaiting a tool response.
        // Expected JSON format for return value: { "content": "string", "tool_calls": [ { "name": "string", "parameters": { ... } } ], "awaiting_tool_response": "boolean" }
        dict<string, Any> extract_tool_calls(union<string, dict<string, Any>> response);

        // Additional methods...
    };

    // Concrete implementation for the Anthropic Claude provider.
    interface ClaudeProvider extends ProviderAdapter {
        // @depends_on(anthropic) // Requires the anthropic library

        // Constructor
        // Preconditions:
        // - api_key is an optional string (uses ANTHROPIC_API_KEY env var if None).
        // - model is a string identifying the Claude model to use.
        // Postconditions:
        // - Initializes the Anthropic client if an API key is available.
        // - Sets the target model and default parameters.
        void __init__(optional string api_key, optional string model);

        // Sends messages to the Claude API.
        // Preconditions:
        // - messages is a list of dictionaries, each with 'role' and 'content'.
        // - system_prompt is a string.
        // - tools is an optional list of tool specifications in Anthropic format.
        // - temperature and max_tokens are optional overrides for default parameters.
        // Expected JSON format for messages: [ { "role": "user|assistant", "content": "string" }, ... ]
        // Expected JSON format for tools: [ { "name": "string", "description": "string", "input_schema": { ... } }, ... ]
        // Postconditions:
        // - Constructs the API request parameters.
        // - Calls the Anthropic client's `messages.create` method.
        // - Returns the Claude API response object (typically includes content, tool_calls, stop_reason).
        // - Returns a mock response string if the client was not initialized (no API key).
        // - Returns an error string on API call failure.
        union<string, dict<string, Any>> send_message(
            list<dict<string, string>> messages,
            optional string system_prompt,
            optional list<dict<string, Any>> tools,
            optional float temperature,
            optional int max_tokens
        );

        // Extracts tool calls and content from a Claude API response.
        // Preconditions:
        // - response is the raw response object/string received from the Claude API.
        // Postconditions:
        // - Parses the Claude response structure (content list, tool_calls, stop_reason).
        // - Returns a standardized dictionary as defined in ProviderAdapter.extract_tool_calls.
        // Expected JSON format for return value: { "content": "string", "tool_calls": [ { "name": "string", "parameters": { ... } } ], "awaiting_tool_response": "boolean" }
        dict<string, Any> extract_tool_calls(union<string, dict<string, Any>> response);

        // Additional methods...
    };
};
// == !! END IDL TEMPLATE !! ===

"""
import os
from typing import Dict, List, Optional, Union, Any

import anthropic

class ProviderAdapter:
    """Base adapter interface for model providers.
    
    This interface defines methods that all provider adapters should implement.
    Specific providers will have their own adapter implementations.
    """
    
    def send_message(self, 
                     messages: List[Dict[str, str]], 
                     system_prompt: str = "", 
                     tools: Optional[List[Dict[str, Any]]] = None) -> Union[str, Dict[str, Any]]:
        """Send a message to the model provider.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            system_prompt: System prompt to provide instructions to the model
            tools: Optional list of tool specifications
            
        Returns:
            Model's response (format depends on provider)
        """
        raise NotImplementedError("Subclasses must implement send_message")
    
    def extract_tool_calls(self, response: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Extract tool calls from a response into a standardized format.
        
        Args:
            response: Raw response from the provider API
            
        Returns:
            Dict with standardized tool call information:
            {
                "content": str,  # Text content from the response
                "tool_calls": [  # List of tool calls (empty if none)
                    {
                        "name": str,      # Tool name
                        "parameters": {},  # Tool parameters
                    },
                    ...
                ],
                "awaiting_tool_response": bool  # Whether the model is waiting for a tool response
            }
        """
        raise NotImplementedError("Subclasses must implement extract_tool_calls")

class ClaudeProvider(ProviderAdapter):
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
            "temperature": 0.3,
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
            if hasattr(response, 'content') and response.content:
                if isinstance(response.content, list) and len(response.content) > 0:
                    if hasattr(response.content[0], 'text'):
                        return response.content[0].text
            
            # Fallback for other response formats
            return "Response processed successfully"
        except Exception as e:
            # Basic error handling
            error_msg = f"Error calling Claude API: {str(e)}"
            print(error_msg)  # Log the error
            return error_msg
            
    def extract_tool_calls(self, response: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Extract tool calls from a response into a standardized format.
        
        Args:
            response: Raw response from the Claude API
            
        Returns:
            Dict with standardized tool call information:
            {
                "content": str,  # Text content from the response
                "tool_calls": [  # List of tool calls (empty if none)
                    {
                        "name": str,      # Tool name
                        "parameters": {},  # Tool parameters
                    },
                    ...
                ],
                "awaiting_tool_response": bool  # Whether the model is waiting for a tool response
            }
        """
        # Initialize the standardized response format
        result = {
            "content": "",
            "tool_calls": [],
            "awaiting_tool_response": False
        }
        
        # Handle string responses (no tool calls)
        if isinstance(response, str):
            result["content"] = response
            return result
            
        # Handle Claude's structured response format
        if isinstance(response, dict):
            # Extract content text
            if "text" in response:
                result["content"] = response["text"]
            elif "content" in response and isinstance(response["content"], list):
                # Extract text from content array
                for item in response["content"]:
                    if isinstance(item, dict) and item.get("type") == "text":
                        result["content"] = item.get("text", "")
                        break
            
            # Extract tool calls
            if "tool_calls" in response:
                for tool_call in response["tool_calls"]:
                    if isinstance(tool_call, dict):
                        # Handle Anthropic's format
                        name = tool_call.get("name", "")
                        parameters = tool_call.get("input", {})
                        
                        if name:
                            result["tool_calls"].append({
                                "name": name,
                                "parameters": parameters
                            })
            
            # Check if model is awaiting tool response
            # Claude indicates this with stop_reason="tool_use"
            if response.get("stop_reason") == "tool_use":
                result["awaiting_tool_response"] = True
        
        return result
