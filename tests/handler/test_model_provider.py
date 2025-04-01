"""Tests for the provider adapters."""
import pytest
from unittest.mock import patch, MagicMock

from handler.model_provider import ProviderAdapter, ClaudeProvider

class TestProviderAdapter:
    """Tests for the ProviderAdapter."""
    
    def test_provider_adapter_interface(self):
        """Test that ProviderAdapter defines the expected interface."""
        assert hasattr(ProviderAdapter, 'send_message')
        assert hasattr(ProviderAdapter, 'extract_tool_calls')

class TestClaudeProvider:
    """Tests for the ClaudeProvider class."""
    
    def test_extract_tool_calls_official_format(self):
        """Test extracting tool calls in official format."""
        provider = ClaudeProvider(api_key="test_key")
        
        # Test with official Anthropic tool call format
        response = {
            "content": [{"type": "text", "text": "I'll use the test_tool"}],
            "tool_calls": [
                {"name": "test_tool", "input": {"param": "value"}}
            ]
        }
        
        result = provider.extract_tool_calls(response)
        
        assert "content" in result
        assert result["content"] == "I'll use the test_tool"
        assert "tool_calls" in result
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "test_tool"
        assert result["tool_calls"][0]["parameters"] == {"param": "value"}
        assert "awaiting_tool_response" in result
        assert result["awaiting_tool_response"] is False
    
    def test_extract_tool_calls_string_response(self):
        """Test extracting tool calls from string response."""
        provider = ClaudeProvider(api_key="test_key")
        
        # Test with string response
        response = "I'll use the test_tool with parameter value"
        
        result = provider.extract_tool_calls(response)
        
        assert "content" in result
        assert result["content"] == response
        assert "tool_calls" in result
        assert len(result["tool_calls"]) == 0  # No tool calls in string response
        assert "awaiting_tool_response" in result
        assert result["awaiting_tool_response"] is False
    
    def test_extract_tool_calls_awaiting_tool_response(self):
        """Test detecting when model is awaiting tool response."""
        provider = ClaudeProvider(api_key="test_key")
        
        # Test with response that indicates awaiting tool response
        response = {
            "content": [{"type": "text", "text": "I need to use a tool"}],
            "stop_reason": "tool_use"  # Anthropic's indicator for awaiting tool response
        }
        
        result = provider.extract_tool_calls(response)
        
        assert "content" in result
        assert result["content"] == "I need to use a tool"
        assert "tool_calls" in result
        assert len(result["tool_calls"]) == 0  # No specific tool calls yet
        assert "awaiting_tool_response" in result
        assert result["awaiting_tool_response"] is True  # Should detect awaiting response
    
    def test_extract_tool_calls_non_standard_format(self):
        """Test extracting tool calls from non-standard format."""
        provider = ClaudeProvider(api_key="test_key")
        
        # Test with a format from a different provider
        response = {
            "text": "I'll use a tool",
            "function_calls": [
                {"function": "test_tool", "arguments": {"param": "value"}}
            ]
        }
        
        # Should still extract and standardize
        result = provider.extract_tool_calls(response)
        
        assert "content" in result
        assert result["content"] == "I'll use a tool"
        assert "tool_calls" in result
        # Should be empty since we're not explicitly handling this format
        assert len(result["tool_calls"]) == 0
        assert "awaiting_tool_response" in result
        assert result["awaiting_tool_response"] is False
    
    def test_send_message_with_tools(self):
        """Test sending a message with tools."""
        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [{"type": "text", "text": "Response text"}]
            mock_client.messages.create.return_value = mock_response
            
            provider = ClaudeProvider(api_key="test_key")
            provider.client = mock_client
            
            messages = [{"role": "user", "content": "Test message"}]
            system_prompt = "You are a helpful assistant"
            tools = [
                {
                    "name": "test_tool",
                    "description": "Test tool",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "param": {"type": "string", "description": "Test parameter"}
                        }
                    }
                }
            ]
            
            response = provider.send_message(
                messages=messages,
                system_prompt=system_prompt,
                tools=tools
            )
            
            # Check response
            assert response == "Response text"
            
            # Check that client was called with correct parameters
            mock_client.messages.create.assert_called_once()
            call_args = mock_client.messages.create.call_args[1]
            
            assert call_args["model"] == provider.model
            assert call_args["system"] == system_prompt
            assert call_args["messages"] == messages
            assert "tools" in call_args
            assert call_args["tools"] == tools
