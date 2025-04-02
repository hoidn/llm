# Handler Behaviors [Behavior:Handler:1.0]

## Core Behaviors

### LLM Interaction

1. **Provider Abstraction**
   - Handler abstracts provider-specific details
   - Each provider requires a specific adapter
   - Common payload structure transformed as needed

2. **Conversation Management**
   - One Handler per task execution
   - Complete conversation history maintained
   - Messages tracked with roles and timestamps
   - Clear session lifecycle (init → execute → cleanup)
   
3. **System Prompt Management**
   - System prompts follow a hierarchical model:
     * The base system prompt (from Handler configuration) provides universal behaviors
     * Template-specific system prompts (if present) extend the base prompt
     * The Handler combines these prompts during payload construction
     * See [Pattern:SystemPrompt:1.0] for details on the hierarchical system prompt pattern

### Resource Management

1. **Turn Counting**
   - Turns incremented for all LLM responses
   - User messages do not increment turn count
   - Tool responses do not increment turn count
   - Turn limits enforced at Handler level

2. **Context Window Management**
   - Token counting uses heuristic estimation
   - Context includes all conversation history and inputs
   - Warnings generated at 80% of limit
   - Hard limit enforced with appropriate errors

3. **Resource Reporting**
   - Current metrics accessible via getResourceMetrics()
   - Metrics included in error responses
   - Clean termination on resource exhaustion

### Tool Execution

1. **Direct Tools**
   - Executed synchronously by Handler
   - Results returned directly to LLM
   - No continuation mechanism

2. **Subtask Tools**
   - Return CONTINUATION status
   - Include subtask_request in notes
   - Structured according to [Pattern:SubtaskSpawning:1.0]

3. **User Input Tools**
   - Standard tool for requesting user input
   - Uses callback pattern for integration
   - Results added to conversation history

### Tool Registration Behavior

1. **Direct Tool Registration**
   ```typescript
   registerDirectTool(name: string, executor: Function): void;
   ```
   - Executor function called synchronously when tool is invoked
   - Results returned directly to LLM conversation
   - No context switching or continuation mechanism
   - Suitable for simple operations (file I/O, API calls)

2. **Subtask Tool Registration**
   ```typescript
   registerSubtaskTool(name: string, templateHints: string[]): void;
   ```
   - When invoked, returns CONTINUATION status with subtask_request
   - Template hints used for associative matching
   - Execution delegated to Task System
   - Suitable for complex operations requiring LLM reasoning

3. **Unified Tool Registration**
   ```typescript
   register_tool(tool_spec: ToolDefinition, executor_func: Function): boolean;
   ```
   - Modern registration method supporting standardized tool specifications
   - Works with provider-specific tool formats (Anthropic, OpenAI)
   - Returns success/failure status for error handling
   - Preferred method for new tool implementations

Both direct and subtask tools appear identical to the LLM but follow different execution paths:
- Direct tools: Handler → Executor → Response
- Subtask tools: Handler → CONTINUATION → Task System → Subtask → Response

### Passthrough Mode

1. **Query Processing**
   - Accept raw text queries without AST compilation
   - Wrap queries in subtasks for context management
   - Maintain conversation state between queries

2. **Context Integration**
   - Apply standard context management settings
   - Enable file relevance for each query
   - Preserve history within the subtask

### Error Handling

1. **Resource Exhaustion**
   - Clean termination with metrics
   - Clear error structure with resource type
   - No automatic retry attempts

2. **Tool Execution Errors**
   - Wrapped in standard error structure
   - Propagated to caller
   - Include context when available

For implementation guidance, see `/components/handler/impl/`.
