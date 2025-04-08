# Architecture Decision Record: Output Standardization

## Status
Proposed

## Context
The current system architecture allows tasks to return outputs in arbitrary text formats. While flexible, this approach has several limitations:

1. **Type Ambiguity**: When binding task outputs to variables, there's no reliable way to determine the intended data type.
2. **Structure Inconsistency**: Tasks that need to return complex data (lists, objects) lack a standardized format.
3. **Parsing Burden**: Downstream tasks must implement custom parsing logic to extract structured data.
4. **Error Proneness**: String-based data exchange is error-prone and difficult to validate.
5. **Poor Composability**: Without structured outputs, it's challenging to compose tasks effectively.

These issues hinder task composition, variable binding, and reliable data flow between tasks. As the system evolves toward a function-based model, the need for structured data exchange becomes increasingly important.

## Decision
We will implement an optional but well-supported JSON-based output standardization mechanism with the following characteristics:

1. **Optional JSON Declaration**: Templates can explicitly specify JSON output format using an `<output_format>` element.
   ```xml
   <task>
     <description>List files in directory</description>
     <output_format type="json" schema="string[]" />
   </task>
   ```

2. **Content Field for Output**: Structured outputs will remain in the TaskResult.content field, preserving the existing interface.

3. **Enhanced TaskResult interface with a `parsedContent` property to store parsed JSON data when content is successfully parsed as JSON.

4. **Added basic output format validation with specific error handling for format violations**:
   - Initial implementation focuses on basic type validation (object, array, string, number, boolean)
   - Error information includes the error type, message, and context about where the error occurred
   - More advanced schema validation may be added in the future if needed

5. **Backward Compatibility**: Free-text outputs will continue to be supported as the default option.

6. **Integration with Function Model**: For the function-based template model, a simplified `returns` attribute will provide type information.
   ```xml
   <template name="get_file_info" params="filepath" returns="object">
   ```

## Consequences

### Positive
1. **Type Safety**: Enables reliable binding of task outputs to variables with correct types.
2. **Structured Data Exchange**: Facilitates passing complex data between tasks.
3. **Basic Validation**: Ensures outputs match expected types.
4. **Enhanced Composition**: Improves task composition through predictable data formats.
5. **Language Integration**: Provides natural mapping to native types in the Evaluator.
6. **Backward Compatibility**: Existing templates continue to work without modification.

### Negative
1. **Some Type Ambiguity**: Basic type validation only; no property or structure validation.
2. **Performance Overhead**: JSON parsing adds computational overhead.
3. **Implementation Effort**: Requires updates to parser, evaluator, and error handling.

## Implementation Guidance

### JSON Detection Algorithm

The Evaluator will implement a JSON detection algorithm:

```typescript
function detectAndParseJson(content: string): { isParsed: boolean; value: any } {
  // Skip detection if clearly not JSON
  if (typeof content !== 'string') {
    return { isParsed: false, value: content };
  }
  
  const trimmed = content.trim();
  
  // Check for JSON-like patterns
  if (trimmed.startsWith('{') || 
      trimmed.startsWith('[') || 
      /^(true|false|null|\d)/.test(trimmed)) {
    try {
      const parsed = JSON.parse(trimmed);
      return { isParsed: true, value: parsed };
    } catch (e) {
      // Not valid JSON despite appearance
      return { isParsed: false, value: content };
    }
  }
  
  return { isParsed: false, value: content };
}
```

### Basic Type Validation

For type validation, we'll implement a lightweight validator focused on the core JSON types:

```typescript
function validateType(value: any, expectedType: string): boolean {
  if (expectedType === 'object') return typeof value === 'object' && value !== null;
  if (expectedType === 'array') return Array.isArray(value);
  if (expectedType === 'string') return typeof value === 'string';
  if (expectedType === 'number') return typeof value === 'number';
  if (expectedType === 'boolean') return typeof value === 'boolean';
  return false; // Unknown type
}
```

### Error Handling

Output validation errors will fit into the existing error taxonomy as a specific type of `TASK_FAILURE`:

```typescript
{
  type: 'TASK_FAILURE',
  reason: 'output_format_failure',
  message: `Expected output of type "${expectedType}" but got "${actualType}"`,
  details: {
    expectedType: expectedType,
    actualType: typeof value
  }
}
```

### TaskResult Extension

The TaskResult interface will be minimally extended:

```typescript
interface TaskResult {
  content: string;
  status: ReturnStatus;
  notes: {
    [key: string]: any;
  };
  // New field
  parsedContent?: any;  // Present if content was parsed as JSON
}
```

### AST Extensions

The AST will be extended with minimal changes to support output format declarations:

```typescript
interface TaskNode extends ASTNode {
  // Existing properties...
  outputFormat?: {
    type: "json" | "text";
    schema?: string;  // Basic type only: "object", "array", "string", etc.
  };
}

// Extension for function-based model
interface TemplateNode extends ASTNode {
  // Existing properties...
  returns?: string; // Simple type declaration
}
```

## Compatibility Considerations

### Template Evolution

Existing templates without output format declarations will continue to work as before. The Evaluator will attempt to auto-detect JSON even without explicit declarations.

### XML Schema Evolution

The `<output_format>` element will be added to the schema in a backward-compatible way, keeping it optional for all task types.

## Integration with Other Features

### Function-Based Template Model

This feature integrates with the proposed function-based template model through the `returns` attribute, which specifies a simple return type.

### Error Taxonomy

The new error type for output validation integrates with the existing error taxonomy from ADR 8 (Error Taxonomy for Context Issues), using the established pattern of specific failure reasons within the `TASK_FAILURE` type.

## Future Extensions

This initial implementation focuses on the core functionality. In the future, we may consider:

1. **Advanced Schema Validation**: Property-level validation for objects and item validation for arrays.
2. **Custom Validation Rules**: Additional validation beyond basic types.
3. **Schema Registry**: Central repository for common schema types.

However, these extensions will only be implemented if there's evidence of need based on real usage patterns.

## Related Decisions

- This builds on [ADR 8: Error Taxonomy for Context Issues] for error handling consistency.
- This complements the proposed "Function-Based Template Model" ADR for the `returns` attribute integration.

## Affected Documentation

After acceptance, these documents will need updates:

1. **system/contracts/protocols.md**: Add `<output_format>` to XML schema
2. **components/task-system/spec/types.md**: Add minimal interface extensions
3. **components/evaluator/README.md**: Document parsing and binding behavior
4. **components/task-system/spec/behaviors.md**: Define expected behaviors for outputs
5. **system/architecture/patterns/errors.md**: Add new error category
6. **components/task-system/impl/xml-processing.md**: Update validation rules
7. **system/README.md**: Update examples to demonstrate structured outputs
