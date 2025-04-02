# Provider Integration

## Provider Adapter Pattern

The Handler uses the adapter pattern to support multiple LLM providers:

```typescript
// Base provider adapter interface
interface ProviderAdapter {
    // Send a message to the provider with optional tools
    send_message(messages: Array<Message>, systemPrompt: string, tools?: Array<ToolDefinition>): Promise<any>;
    
    // Extract tool calls from provider responses in a standardized format
    extract_tool_calls(response: any): StandardizedToolCallResponse;
    
    // Estimate token count for a string
    estimate_tokens(text: string): number;
    
    // Get context window limit for a model
    get_model_context_limit(model: string): number;
}

// Provider-specific implementations
class ClaudeAdapter implements ProviderAdapter {
    // Implementation details for Anthropic Claude
}

class OpenAIAdapter implements ProviderAdapter {
    // Implementation details for OpenAI models
}

// Factory for creating appropriate adapter
function createAdapter(provider: string, config: ProviderConfig): ProviderAdapter {
    switch (provider) {
        case 'anthropic': return new ClaudeAdapter(config);
        case 'openai': return new OpenAIAdapter(config);
        default: throw new Error(`Unsupported provider: ${provider}`);
    }
}
```

This pattern completely encapsulates provider-specific behaviors behind a consistent interface, ensuring that provider differences are isolated from the rest of the system.

## Key Integration Points

1. **Payload Transformation**
   - Transform standard HandlerPayload to provider-specific format
   - Handle message history formatting differences
   - Adapt tool definitions to provider capabilities

2. **Response Processing**
   - Extract content from provider-specific responses
   - Handle tool calls or function calls per provider
   - Normalize error responses

3. **Resource Estimation**
   - Implement provider-specific token counting when available
   - Fall back to heuristics when exact counting unavailable
   - Configure model-specific context limits

## Provider-Specific Features

Each provider adapter should implement:
- Token counting (exact or estimated)
- Tool/function calling support
- Error handling and normalization
- Context window size calculation

For additional details, see each provider's API documentation.
