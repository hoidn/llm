# Handler Interfaces [Interface:Handler:1.0]

```typescript
/**
 * Primary Handler interface
 */
export interface Handler {
    /**
     * Execute a task with the LLM
     * Note: All template variables should be resolved before calling
     * 
     * @param task - The resolved TaskTemplate containing system prompt and task prompt
     * @returns Promise resolving to TaskResult
     */
    executeTask(task: TaskTemplate): Promise<TaskResult>;
    
    /**
     * Execute a prompt with the LLM
     * Note: All template variables should be resolved before calling
     * 
     * @param taskPrompt - Task-specific input (fully resolved)
     * @param templateSystemPrompt - Optional template-specific system prompt to combine with base
     * @returns Promise resolving to TaskResult
     */
    executePrompt(
        taskPrompt: string,
        templateSystemPrompt?: string
    ): Promise<TaskResult>;
    
    /**
     * Process a raw query in passthrough mode
     * Creates or continues a subtask while maintaining conversation state
     * 
     * @param query - The raw user query
     * @returns Promise resolving to TaskResult
     */
    handlePassthroughQuery(query: string): Promise<TaskResult>;

    /**
     * Register a direct tool that will be executed by the Handler
     * 
     * @param name - Unique tool name
     * @param handler - Function that implements the tool
     */
    registerDirectTool(name: string, handler: Function): void;

    /**
     * Register a subtask tool that will be implemented via CONTINUATION
     * 
     * @param name - Unique tool name
     * @param templateHints - Hints for template selection
     */
    registerSubtaskTool(name: string, templateHints: string[]): void;

    /**
     * Add a tool response to the session
     * Used for adding subtask results to parent tasks
     * 
     * @param toolName - Name of the tool that produced the response
     * @param response - The tool response content
     */
    addToolResponse(toolName: string, response: string): void;

    /**
     * Get current resource metrics
     * 
     * @returns ResourceMetrics object with current usage
     */
    getResourceMetrics(): ResourceMetrics;

    /**
     * Set callback for handling user input requests
     * 
     * @param callback - Function to call when user input is requested
     */
    onRequestInput(callback: (prompt: string) => Promise<string>): void;
}

/**
 * Session management interface
 */
export interface HandlerSession {
    /**
     * Add a user message to the conversation
     * 
     * @param content - Message content
     */
    addUserMessage(content: string): void;
    
    /**
     * Add an assistant message to the conversation
     * Increments turn counter
     * 
     * @param content - Message content
     */
    addAssistantMessage(content: string): void;
    
    /**
     * Add a tool response to the conversation
     * Does not increment turn counter
     * 
     * @param toolName - Name of tool that generated the response
     * @param content - Tool response content
     */
    addToolResponse(toolName: string, content: string): void;
    
    /**
     * Construct payload for LLM request
     * 
     * @param task - Optional TaskTemplate to provide template-specific system prompt
     * @returns HandlerPayload object
     */
    constructPayload(task?: TaskTemplate): HandlerPayload;
    
    /**
     * Get current resource metrics
     * 
     * @returns ResourceMetrics object with current usage
     */
    getResourceMetrics(): ResourceMetrics;
}
```

For other relevant interfaces, see:
- [Type:Handler:1.0] for handler-specific type definitions
- [Type:TaskSystem:TaskResult:1.0] for the TaskResult structure
- [Pattern:ToolInterface:1.0] for tool interface patterns
