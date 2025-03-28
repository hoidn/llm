# Provider Integration

## Provider Adapter Pattern

The Handler uses the adapter pattern to support multiple LLM providers:

```typescript
// Base provider interface
interface ProviderAdapter {
    complete(payload: HandlerPayload): Promise<LLMResponse>;
    estimateTokens(text: string): number;
    getModelContextLimit(model: string): number;
}

// Implementation for specific providers
class AnthropicAdapter implements ProviderAdapter {
    // Implementation details
}

class OpenAIAdapter implements ProviderAdapter {
    // Implementation details
}

// Factory for creating appropriate adapter
function createAdapter(provider: string): ProviderAdapter {
    switch (provider) {
        case 'anthropic': return new AnthropicAdapter();
        case 'openai': return new OpenAIAdapter();
        default: throw new Error(`Unsupported provider: ${provider}`);
    }
}
```

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
