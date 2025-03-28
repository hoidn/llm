# Architecture Decision Record: Partial Results Policy

## Status
Proposed

## Context
When multi-step operations fail partway through execution, the system needs a consistent approach to handling partial results. Currently, there is no standardized way to preserve and represent partial work, which limits error reporting and debugging capabilities.

## Decision
We will implement a standardized partial results policy with these principles:

1. **Uniform structure** across task types
2. **Task-level granularity** for partial results tracking
3. **Ephemeral storage** (in-memory only)
4. **Minimal complexity** for the MVP implementation
5. **Limited recovery** through simple retries only (no reparsing for MVP)

## Specification

### Representation by Task Type

#### Atomic Tasks
```typescript
interface TaskResult {
    content: string;
    status: ReturnStatus;
    notes: {
        partialOutput?: string;  // Partial results stored here
        [key: string]: any;
    };
}
```

#### Sequential Tasks
```typescript
{
    type: 'TASK_FAILURE',
    reason: 'subtask_failure',
    message: 'Sequential task failed at step X',
    details: {
        failedStep: number;
        totalSteps: number;
        partialResults: {
            stepIndex: number;
            output: string;
            notes?: any;
        }[];
    }
}
```

#### Reduce Tasks
```typescript
{
    type: 'TASK_FAILURE',
    reason: 'subtask_failure',
    message: 'Reduce task failed processing input X',
    details: {
        failedInputIndex: number;
        totalInputs: number;
        processedInputs: number[];
        currentAccumulator: any;
        partialResults: {
            inputIndex: number;
            result: any;
        }[];
    }
}
```

### Result Format

The format depends on the task's `accumulation_format` setting:

- **notes_only**: Only summary information from each step
- **full_output**: Complete output (with reasonable size limits)

### Recovery for MVP

For the MVP, recovery is limited to simple retries for transient failures. More complex recovery mechanisms are not included in the MVP.

## Size Management

To prevent memory issues:
- Individual step outputs should be kept reasonably sized
- When accumulated data becomes too large, older results may be summarized or truncated
- The system should indicate when truncation has occurred

## Consequences

### Positive
- Consistent approach across task types
- Improved debugging and error analysis
- Minimal memory overhead
- Simpler error handling in MVP

### Negative
- Limited recovery options in MVP
- Potential information loss due to size management
- No persistence for long-running operations

## Examples

### Sequential Task Failure
```typescript
{
  type: 'TASK_FAILURE',
  reason: 'subtask_failure',
  message: 'Sequential task "Process Dataset" failed at step 3',
  details: {
    failedStep: 2,
    totalSteps: 5,
    partialResults: [
      { 
        stepIndex: 0, 
        output: "Data loaded successfully", 
        notes: { recordCount: 1000 }
      },
      { 
        stepIndex: 1, 
        output: "Data transformed to required format"
      }
    ]
  }
}
```

### Reduce Task Failure
```typescript
{
  type: 'TASK_FAILURE',
  reason: 'subtask_failure',
  message: 'Reduce task "Aggregate metrics" failed processing input 2',
  details: {
    failedInputIndex: 2,
    totalInputs: 5,
    processedInputs: [0, 1],
    currentAccumulator: { totalCount: 1500, averageValue: 42.3 },
    partialResults: [
      { inputIndex: 0, result: "Processed metrics for server 1" },
      { inputIndex: 1, result: "Processed metrics for server 2" }
    ]
  }
}
```

## Related Documents
- Error Taxonomy for Context Issues ADR
- Context Management Standardization ADR
- [Pattern:Error:1.0]
