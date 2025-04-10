# Handler Interfaces [Interface:Handler:1.0]

```typescript
/**
 * Base handler interface with common functionality
 * [Interface:BaseHandler:1.0]
 */
export interface BaseHandler {
    /**
     * Register a tool for use by the handler
     * @param tool_spec - Tool specification with name, description, and schema
     * @param executor_func - Function that implements the tool
     * @returns Boolean indicating success
     */
    register_tool(tool_spec: ToolDefinition, executor_func: Function): boolean;
    
    /**
     * Log debug information if debug mode is enabled
     * @param message - Debug message to log
     */
    log_debug(message: string): void;
    
    /**
     * Set debug mode
     * @param enabled - Whether debug mode should be enabled
     */
    set_debug_mode(enabled: boolean): void;
    
    /**
     * Reset conversation state
     */
    reset_conversation(): void;
    
    /**
     * Build system prompt from template and file context
     * @param template - Optional template to use
     * @param file_context - Optional file context to include
     * @returns Constructed system prompt
     */
    _build_system_prompt(template?: string, file_context?: string): string;
    
    /**
     * Get relevant files for a query
     * @param query - The query to find relevant files for
     * @returns List of relevant file paths
     */
    _get_relevant_files(query: string): string[];
    
    /**
     * Create file context from file paths
     * @param file_paths - List of file paths to include in context
     * @returns Formatted file context string
     */
    _create_file_context(file_paths: string[]): string;
    
    /**
     * Execute a tool by name with parameters
     * @param tool_name - Name of the tool to execute
     * @param tool_params - Parameters to pass to the tool
     * @returns Tool execution result or null if tool not found
     */
    _execute_tool(tool_name: string, tool_params: any): any;
}

/**
 * Primary Handler interface
 * Extends BaseHandler with provider-specific capabilities
 */
export interface Handler extends BaseHandler {
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

    /**
     * Execute command and return file paths
     * 
     * @param command - Shell command to execute
     * @returns Promise resolving to array of file paths
     */
    execute_file_path_command(command: string): Promise<string[]>;
    
    /**
     * Register command execution tool
     * Registers a tool for executing commands to find file paths
     * 
     * @returns Boolean indicating success
     */
    register_command_execution_tool(): boolean;
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
