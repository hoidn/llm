# Architecture Decision Record: Error Taxonomy for Context Issues

## Status
Proposed

## Context
The current system error taxonomy consists of two primary error types: `RESOURCE_EXHAUSTION` and `TASK_FAILURE`. As we implement more sophisticated context management, we need clear error categorization for context-related failures to enable appropriate error handling and recovery strategies.

The current error system does not provide enough specificity for context-related failures, making it difficult to implement targeted recovery strategies or provide meaningful feedback to users and developers.

## Decision
We will enhance the error taxonomy by refining the existing `TASK_FAILURE` type with a standardized `reason` field and structured `details` object rather than introducing entirely new error types. This approach provides the necessary specificity while maintaining backward compatibility and simplicity.

## Specification

### Error Type Structure

```typescript
type TaskFailureReason = 
  | 'context_retrieval_failure'    // Failure to retrieve context data
  | 'context_matching_failure'     // Failure in associative matching algorithm 
  | 'context_parsing_failure'      // Failure to parse or process retrieved context
  | 'xml_validation_failure'       // Output doesn't conform to expected XML schema
  | 'output_format_failure'        // Output doesn't meet format requirements (non-XML)
  | 'execution_timeout'            // Task execution exceeded time limits
  | 'execution_halted'             // Task execution was deliberately terminated
  | 'subtask_failure'              // A subtask failed, causing parent task failure
  | 'input_validation_failure'     // Input data didn't meet requirements
  | 'unexpected_error';            // Catch-all for truly unexpected errors

type TaskError = 
    | { 
        type: 'RESOURCE_EXHAUSTION';
        resource: 'turns' | 'context' | 'output';
        message: string;
        metrics?: { used: number; limit: number; };
    }
    | { 
        type: 'TASK_FAILURE';
        reason: TaskFailureReason;
        message: string;
        details?: {
            partial_context?: any;
            context_metrics?: any;
            violations?: string[];
            partialResults?: any[];
            failedStep?: number;
            // Other reason-specific details as needed
        };
    };
```

### Error Handling Flow

Error handlers should first check the error type, then examine the reason field for TASK_FAILURE errors:

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
      // Handle subtask failures
      handleSubtaskFailure(error);
    } else {
      // Handle other failures
      handleGeneralFailure(error);
    }
  }
}
```

### Partial Results Handling

For failures that occur during multi-step operations, the system should preserve partial results in the `details.partialResults` field. This applies particularly to `subtask_failure` errors in sequential or reduce operations.

## Context Failure Definitions and Examples

### Context Retrieval Failure
Occurs when the Memory System cannot provide required context data due to storage or access issues.

**Example**:
```typescript
// Memory System's file index is corrupted or unavailable
return {
  type: 'TASK_FAILURE',
  reason: 'context_retrieval_failure',
  message: 'Failed to access memory system index',
  details: { error }
};
```

### Context Matching Failure
Occurs when associative matching runs but finds no relevant matches for a query that requires context.

**Example**:
```typescript
// No matches found for a task that needs specific context
return {
  type: 'TASK_FAILURE',
  reason: 'context_matching_failure',
  message: 'No relevant context found for Project X',
  details: { query: "Project X", availableProjects: ["Project Y", "Project Z"] }
};
```

### Context Parsing Failure
Occurs when context is retrieved but cannot be properly processed due to format issues.

**Example**:
```typescript
// Context was retrieved but not in expected format
return {
  type: 'TASK_FAILURE',
  reason: 'context_parsing_failure',
  message: 'Retrieved context is not valid JSON',
  details: { 
    context: contextResult.context.substring(0, 100) + '...',
    error: error.message
  }
};
```

## Consequences

### Positive
- Provides specific error categorization without introducing new error types
- Enables targeted recovery strategies for different failure modes
- Maintains backward compatibility with existing error handling
- Standardizes details objects for consistent error information
- Supports partial results preservation for failed multi-step operations

### Negative
- Requires updates to error handling code to check reason field
- May require additional documentation for error reasons
- Could lead to inconsistent usage if not properly enforced

## Implementation Guidelines

1. **Error Construction**:
   ```typescript
   function createTaskFailure(
     reason: TaskFailureReason, 
     message: string, 
     details?: any
   ): TaskError {
     return {
       type: 'TASK_FAILURE',
       reason,
       message,
       details
     };
   }
   ```

2. **Documentation Requirements**:
   - Each reason should be documented with examples
   - Recovery strategies should be suggested for each reason
   - Error handling hierarchy should be clearly documented

3. **Testing Requirements**:
   - Test each error reason with concrete examples
   - Verify error handling behavior for each reason
   - Ensure partial results are properly preserved

4. **Recovery Strategies**:
   - For context errors, consider retrying with different context parameters
   - For subtask failures, consider alternative task decomposition
   - For validation failures, attempt with simpler formats or requirements

## Relationships

This ADR builds upon:
- Context Management Standardization ADR
- Error Handling Pattern [Pattern:Error:1.0]

It will inform:
- Partial Results Policy (upcoming ADR)
- Evaluator-to-Director Feedback Flow (upcoming ADR)

## Examples

### Sequential Task Failure with Partial Results

```typescript
// A sequential task where the third step fails
const error = {
  type: 'TASK_FAILURE',
  reason: 'subtask_failure',
  message: 'Sequential task "Process Dataset" failed at step 3: Data validation',
  details: {
    failedStep: 2,
    stepCount: 5,
    partialResults: [
      { step: 0, output: "Data loaded successfully" },
      { step: 1, output: "Data transformed to required format" }
    ],
    stepError: {
      type: 'TASK_FAILURE',
      reason: 'input_validation_failure',
      message: 'Invalid data format in dataset'
    }
  }
};
```

### Context Generation Failure

```typescript
// Failure during associative matching
const error = {
  type: 'TASK_FAILURE',
  reason: 'context_matching_failure',
  message: 'Unable to find relevant context for code review task',
  details: {
    query: "Review recent changes to payment processing module",
    attempted_sources: ["codebase", "documentation"],
    partial_context: "Found general documentation about payment processing, but no specifics about recent changes."
  }
};
```

## Notes

The decision to enhance the existing error system rather than create new error types was made to:
1. Minimize breaking changes
2. Avoid unnecessary complexity
3. Ensure backward compatibility
4. Provide necessary specificity without overengineering

This approach follows the YAGNI principle while providing the flexibility needed for effective error handling in the evolving system architecture.
