# ADR 17: Input-Output Binding Model

## Status
Proposed

## Context
The system needs a clear and consistent approach to binding outputs from function calls and task executions to variables for later reference. The current implementation has several limitations:

1. **Implicit vs. Explicit Binding**: There's ambiguity about whether function results are automatically stored in the environment.
2. **Array Access Patterns**: The system lacks standardized syntax for accessing array elements in variable references.
3. **JSON Parsing Behavior**: It's unclear how JSON parsing errors are handled and reported.
4. **Error Propagation**: The error handling for format validation needs standardization.

These issues create confusion about how data flows between tasks and how results should be referenced.

## Decision
We will implement a consistent input-output binding model with the following characteristics:

1. **Explicit Result Binding**:
   - Function call results are returned but not automatically stored in the environment
   - Results must be explicitly bound to variables when needed for later reference
   - Sequential tasks automatically maintain a `step_results` array containing each step's result

2. **Enhanced Variable Resolution**:
   - Support for array indexing syntax: `array[0]`
   - Support for object property access: `object.property`
   - Nested access patterns: `object.array[0].property`

3. **JSON Parsing Behavior**:
   - Automatic parsing when `output_format type="json"` is specified
   - Parsed content stored in `parsedContent` property of TaskResult
   - Original string content preserved in `content` property
   - Parse errors recorded in `notes.parseError`

4. **Simplified Error Structure**:
   - Basic type validation against schema attribute
   - Error information includes type, message, and location
   - Original content preserved in error details

## Consequences

### Positive
1. **Clear Data Flow**: Explicit binding makes data flow between tasks more transparent.
2. **Flexible Access Patterns**: Array indexing and property access enable more complex data manipulation.
3. **Robust Error Handling**: Standardized error reporting for parsing and validation issues.
4. **Backward Compatibility**: Existing templates continue to work without modification.

### Negative
1. **Slightly More Verbose**: Explicit binding requires additional code in some cases.
2. **Learning Curve**: Developers need to understand when explicit binding is required.

## Implementation Guidance

### Variable Resolution Algorithm

The Environment.find method will be extended to support array indexing and property access:

```typescript
Environment.prototype.find = function(name) {
  // Support for array indexing syntax (e.g., array[0])
  if (name.includes('[') && name.endsWith(']')) {
    const openBracket = name.indexOf('[');
    const baseName = name.substring(0, openBracket);
    const indexStr = name.substring(openBracket + 1, name.length - 1);
    
    // Find the base object
    const baseObj = this.find(baseName);
    
    // Access array element
    const index = parseInt(indexStr, 10);
    if (Array.isArray(baseObj) && index >= 0 && index < baseObj.length) {
      return baseObj[index];
    }
    throw new Error(`Invalid array access: ${name}`);
  }
  
  // Support for dot notation (e.g., object.property)
  if (name.includes('.')) {
    const parts = name.split('.');
    let current = this.find(parts[0]);
    
    for (let i = 1; i < parts.length; i++) {
      if (current === null || current === undefined) {
        throw new Error(`Cannot access property of undefined: ${parts[i-1]}`);
      }
      
      // Handle nested array access
      if (parts[i].includes('[')) {
        const nestedParts = parts[i].split('[');
        const propName = nestedParts[0];
        const indexStr = nestedParts[1].substring(0, nestedParts[1].length - 1);
        const index = parseInt(indexStr, 10);
        
        current = current[propName];
        if (Array.isArray(current) && index >= 0 && index < current.length) {
          current = current[index];
        } else {
          throw new Error(`Invalid nested array access: ${parts[i]}`);
        }
      } else {
        current = current[parts[i]];
      }
    }
    
    return current;
  }
  
  // Base case: direct variable lookup
  if (name in this.bindings) {
    return this.bindings[name];
  } else if (this.outer) {
    return this.outer.find(name);
  }
  
  throw new Error(`Variable not found: ${name}`);
};
```

### Explicit Binding Examples

Sequential task with explicit binding:
```xml
<task type="sequential">
  <steps>
    <!-- Step 1: Get data and bind result -->
    <task>
      <description>Get data and store result</description>
      <code>
        const data = await getData();
        env.bindings.set("result_data", data);
        return { content: JSON.stringify(data), status: "COMPLETE" };
      </code>
    </task>
    
    <!-- Step 2: Use explicitly bound result -->
    <call template="process_data">
      <arg>result_data</arg>
    </call>
  </steps>
</task>
```

Using automatic step_results array:
```xml
<task type="sequential">
  <steps>
    <!-- Step 1: Get data -->
    <task>
      <description>Get data</description>
      <!-- Output stored in step_results[0] -->
    </task>
    
    <!-- Step 2: Access previous step result -->
    <call template="process_data">
      <arg>step_results[0].parsedContent</arg>
    </call>
  </steps>
</task>
```

### Error Handling

JSON parsing errors will be recorded in the TaskResult structure:

```typescript
{
  content: "Original unparsed content",
  status: "COMPLETE",
  notes: {
    parseError: "Failed to parse JSON: Unexpected token at position 42"
  }
}
```

Type validation errors will use the existing error taxonomy:

```typescript
{
  type: 'TASK_FAILURE',
  reason: 'output_format_failure',
  message: 'Expected output of type "array" but got "object"',
  details: {
    expectedType: "array",
    actualType: "object",
    location: "result validation"
  }
}
```

## Related Decisions

- This builds on [ADR 12: Function-Based Template Model] for function calling semantics.
- This complements [ADR 13: Output Standardization] for JSON output handling.

## Affected Components

- Task System: Variable resolution and binding
- Evaluator: Function call execution and result handling
- Memory System: Context management with structured data
