# Handler Types [Type:Handler:1.0]

> **Note:** Shared types like `HandlerConfig` and `ResourceMetrics` are defined centrally. Please refer to the authoritative definitions in `/docs/system/contracts/types.md`. This file defines types primarily used internally by the Handler component.

```typescript
// ## Removed Types (Now Defined Centrally) ##
// HandlerConfig -> Defined in /docs/system/contracts/types.md
// ResourceMetrics -> Defined in /docs/system/contracts/types.md

/**
 * Payload structure potentially used internally by the Handler before sending to the LLM service.
 * [Type:Handler:HandlerPayload:Local:1.0] // Marked as local
 */
export interface HandlerPayload {
    systemPrompt: string;         // Combined system-level instructions
    messages: Array<{             // Conversation history
        role: "user" | "assistant" | "system";
        content: string;
        timestamp?: Date;
    }>;
    context?: string;             // Context from Memory System
    tools?: ToolDefinition[];     // Available tools formatted for the specific LLM service/library
    metadata?: {
        model: string;
        temperature?: number;
        maxTokens?: number;
        // ResourceUsage is tracked but the definition comes from system types
        // resourceUsage: ResourceMetrics; // Use imported ResourceMetrics type
    };
}

/**
 * Tool definition structure potentially used internally by the Handler.
 * The actual registration format might depend on the LLM service/library.
 * [Type:Handler:ToolDefinition:Local:1.0] // Marked as local
 */
export interface ToolDefinition {
    name: string;
    description: string;
    parameters: { // Note: 'input_schema' in IDL, 'parameters' here. Align if necessary.
        type: "object";
        properties: Record<string, {
            type: string;
            description: string;
        }>;
        required?: string[];
    };
}

```

For related resource management patterns, see [Pattern:ResourceManagement:1.0].
For shared types, see `/docs/system/contracts/types.md`.
