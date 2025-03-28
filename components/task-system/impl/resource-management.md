# Resource Management Implementation

> **Further Reading:** For an architectural overview of resource management principles, see [Pattern:ResourceManagement:1.0](../../../system/architecture/patterns/resource-management.md).

## Overview

The Resource Management implementation follows these core principles:
- No resource usage prediction
- No task decomposition optimization
- Handler-based resource tracking
- Clear resource ownership boundaries

## Resource Tracking Implementation

### Turn Counter Management

#### Implementation Details
- Per-Handler turn tracking
- Atomic increment operations
- Strict limit enforcement
- No cross-Handler pooling

#### Turn Management Rules
- Turn tracking owned by Handler instance
- Turn limit passed during Handler initialization
- Interactive sessions count against turn limits

#### Usage Tracking
```typescript
// Using canonical ResourceMetrics definition from spec/types.md
// See [Type:TaskSystem:ResourceMetrics:1.0]

class TurnCounter {
  private metrics: ResourceMetrics['turns'];
  
  increment(): void {
    if (this.metrics.used >= this.metrics.limit) {
      throw new ResourceExhaustionError('turns');
    }
    this.metrics.used++;
    this.metrics.lastTurnAt = new Date();
  }
}
```

### Context Window Management

#### Size Tracking
- Token-based calculation
- Window size monitoring
- Fraction-based limits
- No content optimization

#### Implementation
```typescript
// Using canonical ResourceMetrics definition from spec/types.md
// See [Type:TaskSystem:ResourceMetrics:1.0]

class ContextManager {
  private metrics: ResourceMetrics['context'];
  
  addContent(content: string): void {
    const tokens = this.countTokens(content);
    if (this.metrics.used + tokens > this.metrics.limit) {
      throw new ResourceExhaustionError('context');
    }
    this.metrics.used += tokens;
    this.metrics.peakUsage = Math.max(this.metrics.peakUsage, this.metrics.used);
  }
}
```

#### Monitoring
- Continuous token tracking
- Peak usage recording
- Threshold warnings
- Limit enforcement

## Resource Cleanup

### Handler Termination
- Clean session shutdown
- Resource accounting completion
- Metric collection
- No state preservation

### Memory Management
- Context cleanup
- Reference clearing
- Memory release
- State invalidation

## Integration with Handler

### Session Implementation

```typescript
/**
 * Implementation of session-based resource management
 */
class HandlerSession {
  private systemPrompt: string;
  private messages: Message[] = [];
  private turnCounter: TurnCounter;
  private contextManager: ContextManager;
  private config: HandlerConfig;
  
  constructor(config: HandlerConfig) {
    this.config = config;
    this.systemPrompt = config.systemPrompt;
    this.turnCounter = new TurnCounter({
      limit: config.maxTurns,
      used: 0,
      lastTurnAt: new Date()
    });
    this.contextManager = new ContextManager({
      limit: Math.floor(config.maxContextWindowFraction * this.getModelMaxTokens(config.defaultModel)),
      used: 0,
      peakUsage: 0
    });
  }
  
  addUserMessage(content: string): void {
    this.messages.push({ 
      role: "user", 
      content, 
      timestamp: new Date() 
    });
    this.contextManager.addContent(content);
    // No turn increment for user messages
  }
  
  addAssistantMessage(content: string): void {
    this.messages.push({ 
      role: "assistant", 
      content, 
      timestamp: new Date() 
    });
    this.contextManager.addContent(content);
    this.turnCounter.increment(); // Increment turn counter for assistant responses
  }
  
  /**
   * Constructs a payload for the LLM using fully resolved content
   * @param task The resolved task template with all variables already substituted
   * @returns A complete HandlerPayload ready for LLM submission
   */
  constructPayload(task: TaskTemplate): HandlerPayload {
    // Note: All template variables should already be resolved by the Evaluator
    return {
      systemPrompt: this.systemPrompt,
      messages: [...this.messages, { 
        role: "user", 
        content: task.taskPrompt, // Already fully resolved
        timestamp: new Date()
      }],
      context: this.contextManager.getCurrentContext(),
      tools: this.getAvailableTools(),
      metadata: {
        model: this.config.defaultModel,
        resourceUsage: this.getResourceMetrics()
      }
    };
  }
  
  getResourceMetrics(): ResourceMetrics {
    return {
      turns: this.turnCounter.getMetrics(),
      context: this.contextManager.getMetrics()
    };
  }
  
  private getModelMaxTokens(model: string): number {
    // Return model-specific token limits
    // Implementation details omitted
    const modelTokenLimits = {
      "claude-3-opus": 200000,
      "claude-3-sonnet": 180000,
      "claude-3-haiku": 150000,
      "gpt-4": 128000,
      "gpt-4-turbo": 128000,
      "gpt-3.5-turbo": 16000
    };
    
    return modelTokenLimits[model] || 100000; // Default fallback
  }
  
  private getAvailableTools(): ToolDefinition[] {
    // Return registered tools
    // Implementation details omitted
    return []; // Placeholder - actual implementation would return registered tools
  }
}
```

## Integration Points

### Memory System
- Read-only metadata access
- Global index management
- Associative matching services
- No file operations or content storage
- Clear interface boundaries with Handler tools

### Error Handling
- Resource exhaustion detection
- Clean termination
- Metric reporting
- State cleanup

## Related Documentation

For more examples, see:
- [Basic Execution Examples](./examples/basic-execution.md#resource-management)
- [Error Handling Examples](./examples/error-handling.md#resource-exhaustion-handling)
