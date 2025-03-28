# Error Handling Examples
    
This document contains examples of error handling in the Task System.
    
## Resource Exhaustion Handling
    
```typescript
try {
  const result = await taskSystem.executeTask(
    "process large dataset",
    memorySystem
  );
} catch (error) {
  if (error.type === 'RESOURCE_EXHAUSTION') {
    console.log('Resource limit exceeded:', error.resource);
    console.log('Usage metrics:', error.metrics);
    
    // Take appropriate recovery action based on resource type
    if (error.resource === 'turns') {
      console.log('Turn limit exceeded - consider task decomposition');
    } else if (error.resource === 'context') {
      console.log('Context window exceeded - consider reducing context size');
    }
  }
}
```
    
## Task Failure Handling
    
```typescript
// Example of error handling with simplified structure
try {
  const result = await taskSystem.executeTask(taskDefinition, memorySystem);
  // Success case: content is complete
  console.log("Task completed successfully:", result.content);
} catch (error) {
  if (error.type === 'RESOURCE_EXHAUSTION') {
    console.log(`Resource limit exceeded: ${error.resource}`);
  } else if (error.type === 'TASK_FAILURE') {
    // Access partial content directly from content field
    console.log(`Partial output before failure: ${error.content}`);
    console.log(`Execution stage: ${error.notes.executionStage || "unknown"}`);
    console.log(`Completion: ${error.notes.completionPercentage || 0}%`);
  }
}
```
    
## Subtask Failure Handling
    
```typescript
try {
  const result = await taskSystem.executeTask("analyze complex document");
  console.log("Analysis complete:", result.content);
} catch (error) {
  // Standard error types without complex partial results
  if (error.type === 'RESOURCE_EXHAUSTION') {
    console.log(`Resource limit exceeded: ${error.resource}`);
  } else if (error.type === 'TASK_FAILURE') {
    console.log(`Task failed: ${error.message}`);
    
    // If this was a subtask failure, the error contains the original request
    if (error.reason === 'subtask_failure') {
      console.log(`Failed subtask: ${error.details.subtaskRequest.description}`);
      
      // Access the original subtask request for potential retry
      const modifiedRequest = {
        ...error.details.subtaskRequest,
        description: `Retry: ${error.details.subtaskRequest.description} with simplified approach`
      };
      
      // Attempt recovery with modified request
      try {
        const recoveryResult = await taskSystem.executeTask(modifiedRequest);
        console.log("Recovery succeeded:", recoveryResult.content);
      } catch (recoveryError) {
        console.log("Recovery failed:", recoveryError.message);
      }
    }
  }
}
```
    
## Sequential Task Failure
    
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
        content: "Data loaded successfully: 1000 records",
        notes: { 
          recordCount: 1000, 
          status: "completed"
        }
      },
      { 
        stepIndex: 1, 
        content: "Data transformed to required format",
        notes: { 
          transformType: "normalization", 
          status: "completed"
        }
      }
    ]
  }
}
```
    
## Reduce Task Failure
    
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
      { 
        inputIndex: 0, 
        content: "Processed metrics for server 1",
        notes: { 
          status: "completed",
          serverName: "server-01",
          metricsCount: 250
        }
      },
      { 
        inputIndex: 1, 
        content: "Processed metrics for server 2",
        notes: { 
          status: "completed",
          serverName: "server-02",
          metricsCount: 180
        }
      }
    ]
  }
}
```
    
## Output Format Failure
    
```typescript
// Example error structure for output_format_failure
{
  type: 'TASK_FAILURE',
  reason: 'output_format_failure',
  message: 'Expected output of type "array" but got "object"',
  details: {
    expectedType: "array",
    actualType: "object",
    content: "..." // The original output in content field
  }
}
```
    
## Related Documentation
    
For more details, see:
- [Error Handling Pattern](../../../../system/architecture/patterns/errors.md)
- [ADR 8: Error Taxonomy](../../../../system/architecture/decisions/8-errors.md)
- [ADR 9: Partial Results Policy](../../../../system/architecture/decisions/completed/009-partial-results.md)
