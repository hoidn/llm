# Resource Management Pattern [Pattern:ResourceManagement:1.0]

**Canonical Reference:** This document is the authoritative description of the Resource Management Pattern. All extended descriptions in other files should refer here.

## Purpose & Constraints
This document defines the resource management strategy for the task execution system. It covers:
 - Memory Hierarchy
 - Resource Tracking (turn counts, context window, token usage)
 - Warning Thresholds (e.g. 80% limits)
 - Cleanup Procedures

**Note:** Warning signals are purely informative; hard limits trigger termination.

## Core Components

### Memory Hierarchy
1. **Long‑term Memory:** Stores data and procedures; accessed via the Memory System (read‑only during task execution).
2. **Working Memory:** The active computation space (task‑specific context) managed through Environment objects; cleared after task completion.
3. **Context Frames:** Capture complete execution environments (bindings and working memory) using a minimal‑context extension pattern.

### Resource Tracking

The Handler is responsible for:
 - Tracking turn counts and enforcing limits.
 - Monitoring context window usage (tokens) with warning thresholds (e.g. 80%) and hard limits.
 - Reporting resource metrics for error handling.

### Resource Tracking

#### Handler Responsibility
- One Handler per task execution
- Creates a HandlerSession to manage conversation state
- Tracks resource usage through session:
  * Turn counts (incremented for assistant messages)
  * Message history (all user and assistant messages)
  * Context window size (including all conversation history)
  * Token usage and peak usage statistics
- Enforces resource limits at session level
- Manages clean termination
- Structures complete interaction payload via HandlerPayload

#### Session Management
- Maintains complete conversation history
- Tracks message timestamps and roles
- Manages turn counting (assistant messages only)
- Constructs provider-agnostic payloads
- Provides resource metrics for monitoring
- Enforces limits based on configuration

### Context Management

#### Window Management
- Token-based calculation
- Explicit size monitoring
- Fraction-based limits
- No content optimization
- Warning thresholds at 80%
- Hard limits with error handling

#### Context Preservation

- The nested Environment model ensures that each child task gets its own context.
- Proper chaining of environments prevents context leakage.
- InheritedContext and any built-in objects (like TaskLibrary) persist unchanged in the chain.
- Context frames capture environments
- Minimal required context per task
- Associative memory mediation
- Clean extension mechanism

## Resource Configuration

### Default Configuration
- Base resource limits
- Warning thresholds
- Default turn counts
- Context window limits

### Per-Task Overrides
- Task-specific limits
- Custom thresholds
- Resource constraints
- Performance targets

## Script Execution Resource Management

- Script tasks (type="script") are executed by the Handler.
- The Handler captures stdout, stderr, and exitCode for script tasks.
- A non-zero exitCode is treated as a TASK_FAILURE error.

Example interface:
```typescript
interface ScriptTaskResult {
    stdout: string;
    stderr: string;
    exitCode: number;
}
```

## Interactions

### With Memory System [Component:Memory:3.0]
- Maintains global file metadata index
- Provides associative matching services
- Manages read-only context retrieval
- No file content operations (delegated to Handler)

### With Task System [Component:TaskSystem:1.0]
- Creates/manages Handlers
- Enforces resource limits
- Manages task execution
- Handles resource errors

### With Handler [Component:Handler:1.0]
- Tracks resource usage
- Enforces limits
- Manages session lifecycle
- Reports resource metrics

## Implementation Requirements

### Resource Tracking
```typescript
// Resource metrics definition moved to spec/types.md
// See [Type:ResourceMetrics:1.0] for the complete interface
```

### Handler Configuration
```typescript
interface HandlerConfig {
    maxTurns: number;
    maxContextWindowFraction: number;
    warningThreshold: number;
    defaultModel?: string;
    systemPrompt: string;
}
```

## Error Handling

### Resource Exhaustion
- Immediate task termination
- Clean resource release
- Error surfacing with metrics
- No automatic retry

### Context Overflow
- Token limit enforcement
- Warning at threshold
- Clean termination
- Context metrics reported

### Progress Failure
- Resource accounting completion
- State cleanup
- Error propagation
- Recovery guidance

### Sequential Task Resources

For **sequential** tasks, the Evaluator maintains a step-by-step record of partial results and history, often called `SequentialHistory`. This history is **not** tracked against the Handler's context window limits. Instead:

- **Evaluator** owns the entire sequential history for multi-step tasks.
- **Handler** continues to track standard resource usage (turns, tokens).
- Because the sequential history is purely textual or metadata that the Evaluator stores separately, it does not consume the Handler's context window.
- If the task is configured to accumulate data (`<accumulate_data>true</accumulate_data>`), the Evaluator may pass prior step outputs into `MemorySystem.getRelevantContextFor()`.
- The Evaluator maintains a SequentialHistory for sequential (type="sequential") tasks.
- The SequentialHistory (holding step outputs and metadata) is not counted against the Handler’s context window limits.
- Accumulated outputs are retained for the entire sequential task execution loop and then discarded (or archived) once the sequence completes.

Example interface:
```typescript
interface SequentialHistory {
    outputs: TaskOutput[];
    metadata: { startTime: Date; currentStep: number; resourceUsage: ResourceMetrics; };
}
interface TaskOutput {
    stepId: string;
    output: string;
    notes: string;
    timestamp: Date;
}
```
- This separation ensures Handler resource metrics stay consistent and the Evaluator can keep any relevant partial outputs for as long as needed.
- Once the sequential task completes (success or failure), the Evaluator discards (or archives) the sequential history to free memory.

This design ensures a clean boundary between higher-level multi-step results (owned by the Evaluator) and resource usage constraints (handled by the Handler).

## Related Patterns
- [Pattern:Error:1.0] - Error handling strategy
- [Pattern:TaskExecution:1.0] - Task execution flow
