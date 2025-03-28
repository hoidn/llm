# Basic Task Execution Examples
    
This document contains examples of basic Task System initialization and execution.
    
## Task System Initialization
    
```typescript
// Initialize TaskSystem
const taskSystem = new TaskSystem({
  maxTurns: 10,
  maxContextWindowFraction: 0.8,
  systemPrompt: "Default system prompt"
});

// Register handlers
taskSystem.onError((error) => {
  console.error('Task error:', error);
});

taskSystem.onWarning((warning) => {
  console.warn('XML validation warning:', warning.message);
});
```
    
## Task Execution
    
```typescript
// Execute task
const result = await taskSystem.executeTask(
  "analyze data",
  memorySystem
);

// Check XML parsing status
if (!result.outputs.some(output => output.wasXMLParsed)) {
  console.warn("XML parsing failed, using fallback string output");
}
```
    
## Task Management
    
```typescript
const taskDef: TaskDefinition = {
  name: "process_data",
  type: "atomic",
  provider: "anthropic",
  model: "claude-3-sonnet",
  body: {
    type: "atomic",
    content: `<task>
      <description>Process data using specific format</description>
      <inputs>
        <input name="raw_data">
          <description>Load and validate input data</description>
          <expected_output>
            Validated data in standard format:
            - Field validations complete
            - Type conversions applied
            - Missing values handled
          </expected_output>
        </input>
      </inputs>
      <expected_output>
        Processed data meeting format requirements:
        - Correct structure
        - Valid field types
        - Complete required fields
      </expected_output>
    </task>`
  },
  metadata: {
    isManualXML: true,
    disableReparsing: true
  }
};

// Register the task
await taskSystem.registerTask(taskDef);

// Validate task
const validation = taskSystem.validateTask(taskDef);

if (!validation.valid) {
  console.warn('Task validation warnings:', validation.warnings);
}

// Find matching tasks
const matches = await taskSystem.findMatchingTasks(
  "analyze peak patterns",
  memorySystem
);

console.log('Found matching tasks:', 
  matches.map(m => ({
    score: m.score,
    type: m.task.type,
    name: m.task.name
  }))
);
```
    
## Resource Management
    
```typescript
// Configure with resource limits
const taskSystem = new TaskSystem({
  maxTurns: 5,
  maxContextWindowFraction: 0.5,
  systemPrompt: "Resource-constrained execution"
});

try {
  const result = await taskSystem.executeTask(
    "process large dataset",
    memorySystem
  );
} catch (error) {
  if (error.type === 'RESOURCE_EXHAUSTION') {
    console.log('Resource limit exceeded:', error.resource);
    console.log('Usage metrics:', error.metrics);
  }
}
```
    
## Related Documentation
    
For more details, see:
- [Task System Interfaces](../../api/interfaces.md)
- [Resource Management Implementation](../resource-management.md)
- [Task Type Definitions](../../spec/types.md)
