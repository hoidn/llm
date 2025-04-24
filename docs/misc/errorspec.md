# Error Type Hierarchy and Handling Design

## Purpose
Define the core error types that enable control flow and task adaptation in the intelligent task execution system.

## Error Categories

### 1. Resource Exhaustion
- **Purpose**: Signal when system resource limits are exceeded
- **Characteristics**:
  - Parameterized resource type and limits (e.g., turns, context window)
  - Clear threshold for triggering
  - No partial results preserved
- **Control Flow Impact**: 
  - Signals that task requires more resources than available

### 2. Task Failure
- **Purpose**: Signal that a task cannot be completed as attempted
- **Characteristics**:
  - Generic failure mechanism using `TASK_FAILURE` type with specific `reason` codes.
  - Can originate from atomic task execution failures or S-expression evaluation errors (e.g., unbound symbol, primitive misuse, type mismatch).
  - Partial results policy depends on origin (see below).
- **Control Flow Impact**:
  - Task execution terminates.
  - Control returns to the calling context (e.g., parent S-expression form, top-level invoker).

## Error Handling Principles

### 1. Separation of Concerns
- Errors purely signal failure conditions.
- No recovery logic embedded within error objects themselves.
- Error objects generally don't track progress, but may contain partial results or state information in their `details` or `content` fields depending on the error type and origin (see below).

### 2. Control Flow
- Resource Exhaustion → Task too large
- Task Failure → Termination
- No retry logic in components

### 3. Context Independence
- Errors primarily signal the failure condition, not the full execution state.
- Partial results from failed *atomic* tasks are stored in the 'content' field (indicated by FAILED status). Intermediate results within S-expression workflows might be preserved via explicit binding (e.g., using `bind` or `let`), and the error details might capture some environment state if feasible.
- Error reporting is separate from the core context management mechanism.

### Missing Argument Handling
When a task attempts to resolve an input, the evaluator first performs template substitution on any placeholders in the form `{{variable_name}}` within the task definition—using values from its current lexical environment. Additionally, if an `<input>` element specifies a `from` attribute, the evaluator binds that input using the value associated with that environment variable. If a required binding is missing, the evaluator returns a standard `TASK_FAILURE` error with a message such as "Missing required input: variable_name."

## Integration Points

All components use the standardized error types (`TaskError`).
In particular:
 - The Handler component detects resource exhaustion (turns, context window, output size) during LLM interaction and signals a `RESOURCE_EXHAUSTION` error.
 - The S-expression evaluator detects runtime errors during DSL execution (e.g., unbound symbols, incorrect primitive usage) and signals `TASK_FAILURE`.
 - The Task System signals `TASK_FAILURE` for issues like template lookup failures or input validation errors.
 - The Memory System signals `TASK_FAILURE` for context operation issues (retrieval, matching, parsing) with appropriate `reason` codes.

## Design Decisions & Rationale

1. Minimal Error Categories
   - Only essential control flow signals
   - Clear mapping to system behaviors
   - Simplified error handling

2. Stateless Error Design
   - Separates control flow from state
   - Clean component boundaries
   - Simplified recovery

3. No Complex Recovery
   - Decomposition as consequence not strategy
   - Simplified control flow
   - Clear system behavior

## Context Operation Failures

Context operation failures (retrieval, matching, parsing) originating from `MemorySystem` calls are reported as `TASK_FAILURE` with specific `reason` codes (e.g., `context_retrieval_failure`, `context_matching_failure`, `context_parsing_failure`). Partial context data might be preserved in the error's `details` field if available before the failure occurred.

## Dependencies
- Task system must detect resource limits

## Script Execution Errors
Script execution errors (e.g., non-zero exit codes, timeouts) detected by the Handler during direct tool execution (like `system:run_script`) are signaled as `TASK_FAILURE`. The error object includes script output (stdout, stderr, exit code) in its `details` or `notes`, allowing the calling S-expression workflow or Evaluator to inspect the results and make downstream decisions. The error itself terminates the script execution step.
