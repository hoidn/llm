# Resource Tracking Implementation

## Turn Counting

```typescript
class TurnCounter {
  private used: number = 0;
  private limit: number;
  private lastTurnAt?: Date;
  
  constructor(limit: number) {
    this.limit = limit;
  }
  
  increment(): void {
    if (this.used >= this.limit) {
      throw new ResourceExhaustionError('turns', {
        used: this.used,
        limit: this.limit
      });
    }
    
    this.used++;
    this.lastTurnAt = new Date();
  }
  
  getMetrics(): TurnMetrics {
    return {
      used: this.used,
      limit: this.limit,
      lastTurnAt: this.lastTurnAt
    };
  }
}
```

## Context Window Management

```typescript
class ContextManager {
  private used: number = 0;
  private limit: number;
  private provider: ProviderAdapter;
  
  constructor(maxFraction: number, provider: ProviderAdapter, model: string) {
    const modelLimit = provider.getModelContextLimit(model);
    this.limit = Math.floor(modelLimit * maxFraction);
    this.provider = provider;
  }
  
  addContent(content: string): void {
    const tokens = this.provider.estimateTokens(content);
    
    if (this.used + tokens > this.limit) {
      throw new ResourceExhaustionError('context', {
        used: this.used,
        limit: this.limit
      });
    }
    
    this.used += tokens;
    
    if (this.used >= this.limit * 0.8) {
      // Emit warning at 80% usage
    }
  }
  
  getMetrics(): ContextMetrics {
    return {
      used: this.used,
      limit: this.limit
    };
  }
}
```

## Integration with HandlerSession

The HandlerSession integrates both tracking mechanisms:

1. **Turn Tracking**
   - Incremented in addAssistantMessage method
   - Not affected by user messages or tool responses
   - Checked before each LLM call

2. **Context Tracking**
   - Updated for all messages regardless of type
   - Includes system prompt and context
   - Checked before constructing payload

See [Pattern:ResourceManagement:1.0] for underlying principles.
