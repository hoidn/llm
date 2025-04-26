# Task System Interfaces

import { MemorySystem, FileMatch } from "../../memory/api/interfaces";

## References

- Core Types: See [Type:TaskSystem:1.0] (`/components/task-system/spec/types.md`)
- XML Schema: See [Contract:Tasks:TemplateSchema:1.0] (`/system/contracts/protocols.md`)

## Public Interfaces

### TaskSystem Interface
```typescript
/**
 * Core task execution interface
 * Uses types defined in [Type:TaskSystem:1.0]:
 * - TaskResult
 * - TaskTemplate
 * - TaskType
 * - AtomicTaskSubtype
 */
interface TaskSystem {
    executeTask(
        task: string,
        memory: MemorySystem,
        options?: {
            taskType?: TaskType;
            provider?: string;
            model?: string;
        }
    ): Promise<TaskResult>;

    // Validate a task definition
    validateTask(task: TaskDefinition): boolean;
    
    // Find matching tasks for input
    /**
     * findMatchingTasks
     *
     * Finds matching templates based on a provided input string.
     *
     * Note: Matching applies *only* to atomic task templates. The function evaluates the input
     * against atomic task templates using a heuristic scoring mechanism.
     * 
     * @param input - The natural language task description.
     * @param context - The MemorySystem instance providing context data.
     * @returns An array of matching atomic task templates with their associated scores.
     */
    findMatchingTasks(
        input: string,
        context: MemorySystem
    ): Promise<Array<{
        task: TaskDefinition;
        score: number;
        taskType: "atomic"; // Only atomic tasks participate in matching
        subtype?: AtomicTaskSubtype;
    }>>;
    
    // Register a task definition
    registerTask(taskDef: TaskDefinition): Promise<void>;
    
    // Execute a function-style task call
    executeCall(call: {
        taskName: string;
        arguments: any[];
    }, env?: Environment): Promise<any>;
    
    /**
     * Parse and validate task output against declared format
     * @param output - Raw task output
     * @param format - Optional output format specification
     * @returns Parsed output or the original if parsing fails
     */
    parseTaskOutput(output: string, format?: {
        type: "json" | "text";
        schema?: string;
    }): { isParsed: boolean; value: any };

    /**
     * Execute a Task System template workflow directly from a SubtaskRequest.
     * Bypasses the need for a CONTINUATION status from a Handler.
     * Primarily used for programmatic invocation (e.g., via /task command).
     *
     * @param request - The SubtaskRequest containing type ('atomic'), subtype, and **resolved** inputs, file_paths, context_management.
     * @returns Promise resolving to the final TaskResult of the atomic task execution.
     * @throws {Error} If request type is not 'atomic' or template not found.
     */
    execute_atomic_template(request: SubtaskRequest): Promise<TaskResult>;
}
```

### Memory System Interface [Interface:Memory:3.0]
```typescript
/**
 * Memory System Interface [Interface:Memory:3.0]
 * Focused on metadata management and context retrieval
 */
interface MemorySystem {
    /**
     * Get global file metadata index
     * @returns Promise resolving to the global index
     */
    getGlobalIndex(): Promise<GlobalIndex>;
    
    /**
     * Update global file metadata index
     * @param index New index to set
     * @returns Promise resolving when update is complete
     */
    updateGlobalIndex(index: GlobalIndex): Promise<void>;
    
    /**
     * Get relevant context for a task
     * @param input Context generation input
     * @returns Promise resolving to associative match result
     */
    getRelevantContextFor(input: ContextGenerationInput): Promise<AssociativeMatchResult>;
}
```

### Handler Interface
```typescript
/**
 * Types specific to Handler interface
 */
interface HandlerConfig {
    provider: string;  // e.g., "anthropic", "openai"
    maxTurns: number;
    maxContextWindowFraction: number;
    defaultModel?: string;
    systemPrompt: string;
    tools?: string[];  // Tool types needed ("file_access", "bash", etc.)
}

/**
 * Payload structure for LLM interactions
 * Provides a provider-agnostic representation of the LLM request
 */
interface HandlerPayload {
  systemPrompt: string;
  messages: Array<{
    role: "user" | "assistant" | "system";
    content: string;
    timestamp?: Date;
  }>;
  context?: string;        // Context from Memory System
  tools?: ToolDefinition[]; // Available tools
  metadata?: {
    model: string;
    temperature?: number;
    maxTokens?: number;
    resourceUsage: ResourceMetrics;
  };
}

/**
 * LLM interaction interface
 * Uses [Type:TaskSystem:ResourceMetrics:1.0], [Type:TaskSystem:ResourceLimits:1.0]
 */
interface Handler {
    /**
     * Execute a prompt with the LLM
     * @param payload - The HandlerPayload containing all interaction details
     * @returns Promise resolving to LLM response
     */
    executePrompt(payload: HandlerPayload): Promise<LLMResponse>;

    /**
     * Process LLM response and handle any tool calls
     * @param response - The raw LLM response
     * @returns Promise resolving to the processed content
     */
    processLLMResponse(response: LLMResponse): Promise<string>;

    /**
     * Register a direct tool that will be executed by the Handler
     * @param name - Unique tool name
     * @param handler - Function that implements the tool
     */
    registerDirectTool(name: string, handler: Function): void;

    /**
     * Register a subtask tool that will be implemented via CONTINUATION
     * @param name - Unique tool name
     * @param templateHints - Hints for template selection
     */
    registerSubtaskTool(name: string, templateHints: string[]): void;

    /**
     * Callback for handling agent input requests
     * @param prompt - The prompt to display to the user
     * @returns Promise resolving to user's input
     */
    onRequestInput: (prompt: string) => Promise<string>;
    
    /**
     * Create a new session for managing conversation state
     * @param config - Configuration for the session
     * @returns A new HandlerSession instance
     */
    createSession(config: HandlerConfig): HandlerSession;
}

/**
 * Session for managing conversation state
 */
interface HandlerSession {
    /**
     * Add a user message to the conversation
     * @param content - User message content
     */
    addUserMessage(content: string): void;
    
    /**
     * Add an assistant message to the conversation
     * @param content - Assistant message content
     */
    addAssistantMessage(content: string): void;
    
    /**
     * Construct a payload for LLM interaction
     * @returns The HandlerPayload for this session
     */
    constructPayload(): HandlerPayload;
    
    /**
     * Get current resource metrics for this session
     * @returns ResourceMetrics for turns and context window
     */
    getResourceMetrics(): ResourceMetrics;
}
```
