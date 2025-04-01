# Handler Types [Type:Handler:1.0]

```typescript
/**
 * Handler configuration parameters
 */
export interface HandlerConfig {
    maxTurns: number;             // Maximum turns allowed for this Handler
    maxContextWindowFraction: number; // Fraction of model's context window to use
    defaultModel?: string;        // Default LLM model to use
    baseSystemPrompt: string;     // Base system prompt for universal behaviors
}

/**
 * Payload sent to LLM provider
 */
export interface HandlerPayload {
    systemPrompt: string;         // Combined system-level instructions (base + template-specific)
    messages: Array<{             // Conversation history
        role: "user" | "assistant" | "system";
        content: string;
        timestamp?: Date;
    }>;
    context?: string;             // Context from Memory System
    tools?: ToolDefinition[];     // Available tools
    metadata?: {
        model: string;
        temperature?: number;
        maxTokens?: number;
        resourceUsage: ResourceMetrics;
    };
}

/**
 * Tool definition for LLM
 */
export interface ToolDefinition {
    name: string;
    description: string;
    parameters: {
        type: "object";
        properties: Record<string, {
            type: string;
            description: string;
        }>;
        required?: string[];
    };
}

/**
 * Resource metrics tracked by Handler
 */
export interface ResourceMetrics {
    turns: {
        used: number;
        limit: number;
        lastTurnAt: Date;
    };
    context: {
        used: number;
        limit: number;
    };
}
```

For related resource management patterns, see [Pattern:ResourceManagement:1.0].
