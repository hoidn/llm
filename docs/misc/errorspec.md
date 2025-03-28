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
  - Generic failure mechanism
  - No internal categorization
  - No partial results preserved
- **Control Flow Impact**:
  - Task terminates
  - Control returns to parent task/evaluator

## Error Handling Principles

### 1. Separation of Concerns
- Errors purely signal failure conditions
- No recovery logic in error objects
- No state/progress tracking
- No partial results

### 2. Control Flow
- Resource Exhaustion → Task too large
- Task Failure → Termination
- No retry logic in components

### 3. Context Independence  
- Errors do not carry execution state.
- No partial results in errors.
- Clean separation from context management.

### Missing Argument Handling
When a task attempts to resolve an input, the evaluator first performs template substitution on any placeholders in the form `{{variable_name}}` within the task definition—using values from its current lexical environment. Additionally, if an `<input>` element specifies a `from` attribute, the evaluator binds that input using the value associated with that environment variable. If a required binding is missing, the evaluator returns a standard `TASK_FAILURE` error with a message such as "Missing required input: variable_name."

## Integration Points

All components in the unified task-execution system use the same generic error signaling.
In particular:
 - The Task System (and its unified execution component) detects resource exhaustion and signals a generic `TASK_FAILURE` with attached metadata.
 - The Memory System continues to provide context without carrying error state.

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

In scenarios where a task step calls `MemorySystem.getRelevantContextFor()` (or otherwise attempts context assembly), any failure is reported as a standard `TASK_FAILURE`.
Partial results are not preserved; on any failure, intermediate data is discarded.

In short, "context operation failures" are reported solely as `TASK_FAILURE`, and no partial sub-task outputs are retained.

## Dependencies
- Task system must detect resource limits

## Script Execution Errors
Script execution errors (e.g. non-zero exit codes) are captured and passed along to the evaluator for downstream decision-making rather than causing an immediate task failure.
- Evaluator must handle control flow
- Memory system must maintain context
