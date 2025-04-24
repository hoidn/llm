# Error Handling and Recovery Pattern [Pattern:Error:1.0]

**Canonical Reference:** This document is the authoritative description of the Error Handling and Recovery Pattern. All extended descriptions in other files should refer here.

**Intended Focus:** This document covers overall error detection, classification, and recovery strategies. For resource‑related cleanup details, see the "Resource Cleanup" subsection below. (For low‑level resource metrics, refer to [Pattern:ResourceManagement:1.0] and related docs.)

## 1. Pattern Definition

### 1.1 Purpose
Error handling pattern for the task execution system, focusing on three key concerns:
- Resource exhaustion detection and recovery
- Invalid output handling
- Progress failure management

### 1.2 Context
This pattern is used by:
- [Component:TaskSystem:1.0] for error detection
- [Component:Evaluator:1.0] for error recovery
- [Component:Handler:1.0] for resource monitoring

### 1.3 Core Elements
- Error Type System: See [Type:TaskSystem:TaskError:1.0]
- Recovery Protocols: See [Protocol:Tasks:Reparse:1.0]
- Resource Contracts: See [Contract:Resources:1.0]

## 2. Error Categories

### 2.1 Resource Exhaustion
Handled by [Protocol:Tasks:Reparse:1.0]

Resource exhaustion occurs when a task exceeds allocated system resources:
- **Type**: 'RESOURCE_EXHAUSTION'
- **Resources**: 'turns' | 'context' | 'output'
- **Metrics**: Contains usage and limit values
- **Recovery**: Attempt task decomposition

### 2.2 Task Failure
Related to [Contract:Tasks:TemplateSchema:1.0]

Task failures now include a standardized `reason` field for more specific categorization:

```typescript
type TaskFailureReason = 
  | 'context_retrieval_failure'    // Failure to retrieve context data
  | 'context_matching_failure'     // Failure in associative matching algorithm 
  | 'context_parsing_failure'      // Failure to parse or process retrieved context
  | 'xml_validation_failure'       // Output doesn't conform to expected XML schema
  | 'output_format_failure'        // Output doesn't meet format requirements
  | 'execution_timeout'            // Task execution exceeded time limits
  | 'execution_halted'             // Task execution was deliberately terminated
  | 'subtask_failure'              // A subtask failed, causing parent task failure
  | 'input_validation_failure'     // Input data didn't meet requirements
  | 'unexpected_error';            // Catch-all for truly unexpected errors
```

Task failures also include a structured details object that may contain error-specific information such as:
- partial_context: Any partial context that was retrieved before failure
- context_metrics: Metrics related to context retrieval
- violations: Specific validation rule violations
- partialResults: Results from steps that completed before failure
- failedStep: Index of the step that failed in a sequential task

### 2.3 Failure to Make Progress
Progress failures occur when a task cannot advance despite resources being available:
- **Type**: 'TASK_FAILURE'
- **Reason**: 'execution_halted'
- **Indicators**: Multiple rounds with no state change
- **Recovery**: Alternative approach or termination

### 2.4 Partial Results Handling

The system handles partial results differently depending on the source of the failure:

#### Atomic Tasks
- If an atomic task fails mid-execution (e.g., due to resource exhaustion or an internal error after starting generation), any output generated before the failure *may* be placed in the `content` field of the resulting `TaskError` object (or the `TaskResult` if status is `FAILED`).
- The `status: "FAILED"` clearly indicates the content is partial or incomplete.

#### S-expression Workflows
- For workflows defined using the S-expression DSL, partial results correspond to the values bound to variables using primitives like `bind` or `let` up to the point of failure.
- The execution environment state (the set of bound variables and their values) at the time of failure might be captured in the error details if feasible, but there's no automatic preservation of step-by-step outputs as previously defined for XML composites. Recovery logic within the S-expression or at a higher level would need to utilize this environment state if provided.
- The `accumulation_format` setting from `<context_management>` applies only to how *atomic tasks* handle their internal context during execution, not to how S-expression results are stored or passed.

#### Size Management
To prevent memory issues:
- Individual step outputs are kept reasonably sized
- When accumulated data becomes too large, older results may be summarized or truncated
- The system indicates when truncation has occurred

### 2.5 Output Format Validation

When a task specifies an output format using `<output_format type="json" schema="...">`, validation failures result in:

```typescript
{
  type: 'TASK_FAILURE',
  reason: 'output_format_failure',
  message: 'Expected output of type "array" but got "object"',
  details: {
    expectedType: "array",
    actualType: "object",
    originalOutput: "..." // The original output
  }
}
```

This error occurs when:
1. The task specifies an output format with `type="json"`
2. The output is successfully parsed as JSON
3. The parsed content doesn't match the specified schema type

The original output is preserved in the `partialOutput` field to allow for potential recovery or manual parsing. The error includes both the expected and actual types to aid in debugging and recovery.

## 3. Recovery Process

### 3.1 Detection Phase
See [Interface:Handler:ResourceMonitoring:1.0]

Error detection now includes identifying:
- Context retrieval failures
- Context matching failures
- Context parsing failures
- Output format validation failures

```typescript
function handleTaskError(error: TaskError) {
  if (error.type === 'RESOURCE_EXHAUSTION') {
    // Handle resource exhaustion based on resource type
    handleResourceExhaustion(error);
  } else if (error.type === 'TASK_FAILURE') {
    // Handle task failure based on reason
    if (error.reason.startsWith('context_')) {
      // Handle context-related failures
      handleContextFailure(error);
    } else if (error.reason === 'subtask_failure') {
      // Handle subtask failures, potentially using partial results
      handleSubtaskFailure(error);
    } else if (error.reason === 'output_format_failure') {
      // Handle output validation failures
      handleOutputFormatFailure(error);
    } else {
      // Handle other failures
      handleGeneralFailure(error);
    }
  }
}
```

### 3.2 Planning Phase
See [Component:Evaluator:1.0] for error handling.

Based on error type and reason, the system will surface appropriate error information:
- **Resource Exhaustion**: Complete resource metrics and context
- **Context Failures**: Context-related error details
- **Validation Errors**: Validation failure specifics
- **Subtask Failures**: Error details including partial execution data

### 3.3 Execution Phase
See [Protocol:Tasks:Reparse:1.0] for execution details.

Error handling involves:
- Preparing complete error context
- Including relevant partial execution data
- Surfacing errors through standard error flow
- Providing detailed diagnostics

#### Error Handling within Composite Tasks

When an error occurs within a sub-step (Director, Script execution, or Evaluator) of a composite task like director_evaluator_loop, the loop terminates immediately. The final TaskResult returned by the Evaluator for the entire loop node will have status: "FAILED". The notes.error field in this final result will contain a TaskError object, typically with reason: SUBTASK_FAILURE, indicating the failure occurred within a sub-step. The details of this top-level error object will include the original TaskResult or TaskError from the specific step that failed. Additionally, the notes.iteration_history field will contain the recorded results for all iterations up to and including the one where the failure occurred.

- **Associative Matching Failures:** If an associative matching task encounters an error—such as insufficient context or partial output—it will automatically trigger a retry. These errors will include any partial output and, if available, an optional success score (recorded in the task's `notes` field) to support future adaptive behavior.

#### Error Recovery Flow for Associative Matching

```mermaid
flowchart TD
    A[Associative Matching Task Initiated] --> B{Error Detected?}
    B -- Yes --> C[Trigger Automatic Retry]
    C --> D[Capture Partial Output & Success Score]
    D --> E[Reattempt Associative Matching]
    B -- No --> F[Proceed with Normal Execution]
```

### Subtask Failure Handling

When a subtask fails, the system provides a standardized error structure that preserves context and enables recovery:

```typescript
{
  type: 'TASK_FAILURE',
  reason: 'subtask_failure',
  message: 'Subtask "Process complex data" failed',
  details: {
    subtaskRequest: {
      type: 'atomic',
      description: 'Process complex data',
      inputs: { /* original inputs */ }
    },
    subtaskError: {
      type: 'TASK_FAILURE',
      reason: 'execution_halted',
      message: 'Failed to process data format'
    },
    nestingDepth: 2,
    partialOutput: "Partial processing results before failure"
  }
}
```

This standardized structure provides several benefits:
1. Complete error context preservation
2. Clear indication of which subtask failed
3. Access to the original subtask request for potential retry
4. Preservation of partial results for recovery

Example of parent task handling subtask failures:
```typescript
try {
  const result = await taskSystem.executeTask(complexTask);
} catch (error) {
  if (error.type === 'TASK_FAILURE' && error.reason === 'subtask_failure') {
    console.log(`Subtask failed: ${error.details.subtaskRequest.description}`);
    
    // Access the original subtask request for potential retry
    const modifiedRequest = {
      ...error.details.subtaskRequest,
      description: `Retry: ${error.details.subtaskRequest.description} with simplified approach`
    };
    
    // Use partial results if available
    if (error.details.partialOutput) {
      console.log(`Using partial output: ${error.details.partialOutput}`);
    }
    
    // Attempt recovery with modified request
    const recoveryResult = await taskSystem.executeTask(modifiedRequest);
  }
}
```

### 3.4 Validation Phase
Recovery validation includes:
- Verifying resource usage of recovery approach
- Ensuring progress is made
- Validating output structure and format
- Limiting recovery depth to prevent infinite loops

## 4. Pattern Examples
See components/task-system/impl/examples.md for concrete examples.

### Context Retrieval Failure Example
```typescript
// Memory System's file index is corrupted or unavailable
const error = {
  type: 'TASK_FAILURE',
  reason: 'context_retrieval_failure',
  message: 'Failed to access memory system index',
  details: { error: 'Index corruption detected' }
};

// Recovery involves alternative context strategy
const recovery = await evaluator.recoverFromContextFailure(error);
```

### S-expression Workflow Failure Example
```typescript
// Conceptual example - actual error structure may vary
try {
  // Invoking an S-expression workflow via TaskSystem/SExprEvaluator
  const result = await taskSystem.executeSExpression(
    '(bind x (call-atomic-task \'task-a\') (bind y (call-atomic-task \'task-b\' (input x)) (process y)))'
  );
} catch (error) {
  if (error.type === 'TASK_FAILURE') {
    console.log(`S-expression workflow failed: ${error.message}`);
    // Reason might be 'subtask_failure' if an atomic task failed,
    // or an S-expression specific reason like 'unbound_symbol'.
    console.log(`Reason: ${error.reason}`);

    // Details might contain the state of the S-expression environment
    // or the error from the failed atomic task.
    if (error.details?.s_expression_environment) {
      console.log('Environment at failure:', error.details.s_expression_environment);
      // Recovery might involve analyzing the environment and retrying
      // a part of the S-expression or an alternative path.
    } else if (error.details?.subtaskError) {
       console.log('Failed subtask error:', error.details.subtaskError);
       // Recovery might involve retrying the failed atomic task.
    }
  }
}
```

## 5. Known Limitations
- **Recovery Depth**: Limited to prevent infinite loops
- **Partial Result Size**: May be truncated for very large outputs
- **Stateful Recovery**: Not supported across sessions
- **Complex Dependencies**: Recovery may not work for deeply nested failures

## 6. Related Patterns
- [Pattern:ResourceManagement:1.0]
- [Pattern:TaskExecution:2.0]
