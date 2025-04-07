# Architecture Decision Record: Enhanced File Paths Specification

## Status
Proposed

## Context
The current system architecture provides a mechanism for specifying explicit file paths to include in task context through the `<file_paths>` element. While effective for scenarios where the specific files are known in advance, this approach lacks flexibility for several common use cases:

1. **Dynamic File Discovery**: Users often need to include files based on patterns or search criteria that are most easily expressed as shell commands (e.g., `find`, `grep`).

2. **Decoupled Context Specification**: Users sometimes need to provide a focused natural language description for context retrieval that is separate from the main task description.

3. **Workflow Integration**: Tasks operating within larger workflows may need to adapt their context based on the output of previous operations.

The current implementation only supports explicitly listing file paths, requiring users to manually determine relevant files before task execution. This creates friction in workflows where file sets are dynamic or determined through other means.

## Decision
We will enhance the `<file_paths>` element with a `source` attribute that supports three methods for specifying context files:

1. **literal** (default): The current approach of explicitly listing file paths
2. **command**: A bash command that outputs file paths (one per line)
3. **description**: A natural language description specifically for context-focused associative matching

This enhancement builds on the existing functionality while maintaining backward compatibility and conceptual clarity. Each source type provides a different method for achieving the same goal: determining which files to include in the task's context.

## Specification

### XML Schema Extension

```xml
<xs:element name="file_paths" minOccurs="0">
  <xs:complexType>
    <xs:choice>
      <xs:sequence>
        <xs:element name="path" type="xs:string" maxOccurs="unbounded"/>
      </xs:sequence>
      <xs:element name="command" type="xs:string"/>
      <xs:element name="description" type="xs:string"/>
    </xs:choice>
    <xs:attribute name="source" use="optional" default="literal">
      <xs:simpleType>
        <xs:restriction base="xs:string">
          <xs:enumeration value="literal"/>
          <xs:enumeration value="command"/>
          <xs:enumeration value="description"/>
        </xs:restriction>
      </xs:simpleType>
    </xs:attribute>
  </xs:complexType>
</xs:element>
```

### Interface Extensions

The `SubtaskRequest` and `BaseTaskDefinition` interfaces will be extended with a new optional `file_paths_source` field:

```typescript
/**
 * Optional source for generating file paths to include in context.
 * Takes precedence over file_paths array when provided with type 'command' or 'description'.
 */
file_paths_source?: {
  /**
   * Source type for file paths:
   * - 'literal': Use explicit file_paths array (default behavior)
   * - 'command': Execute bash command to generate file paths
   * - 'description': Use natural language description for context-specific matching
   */
  type: 'literal' | 'command' | 'description';
  
  /**
   * Value depends on type:
   * - For 'command': Bash command to execute
   * - For 'description': Natural language description
   * - For 'literal': Ignored (use file_paths array instead)
   */
  value: string;
};
```

### Memory System Interface Extension

The Memory System interface will be extended with two method enhancements:

```typescript
/**
 * Get relevant context for a task
 * 
 * @param input - The ContextGenerationInput containing task context
 * @param contextDescription - Optional separate description specifically for context matching
 * @returns Promise resolving to associative match result
 */
getRelevantContextFor(
  input: ContextGenerationInput, 
  contextDescription?: string
): Promise<AssociativeMatchResult>;

/**
 * Execute command to get file paths
 * 
 * @param command - The bash command to execute
 * @returns Promise resolving to array of file paths
 */
getFilePathsFromCommand(command: string): Promise<string[]>;
```

### Usage Examples

#### Literal Paths (Default Behavior)
```xml
<file_paths source="literal">
  <path>./src/main.py</path>
  <path>/absolute/path/file.txt</path>
</file_paths>
```

#### Command-Generated Paths
```xml
<file_paths source="command">
  <command>find ./src -name "*.py" | grep -v "__pycache__"</command>
</file_paths>
```

#### Description-Based Paths
```xml
<file_paths source="description">
  <description>Find all Python files related to authentication</description>
</file_paths>
```

## Implementation Requirements

### Component Responsibilities

1. **Task System**:
   - Parse the enhanced `<file_paths>` element with source attribute
   - Pass the appropriate information to the Memory System
   - Integrate file paths into the task's context

2. **Memory System**:
   - Implement the new `getFilePathsFromCommand` method
   - Support the extended `getRelevantContextFor` with optional contextDescription
   - Handle all three source types appropriately

3. **Handler**:
   - Ensure command execution is performed securely
   - Apply appropriate resource limits to command execution

### Security Considerations

1. **Command Execution**:
   - Commands must be validated and sanitized before execution
   - Execution should be limited to read-only operations
   - Resource limits (execution time, memory usage) should be enforced
   - Consider restricting command execution to a safe subset of bash

2. **Error Handling**:
   - Failed commands should produce appropriate error messages
   - Invalid file paths should be reported but not prevent execution
   - Command timeouts should be handled gracefully

## Consequences

### Positive

1. **Enhanced Flexibility**: Users can specify context files through multiple methods, matching their workflow needs.

2. **Workflow Integration**: Tasks can integrate with shell commands, making them more powerful in automated workflows.

3. **Decoupled Context Specification**: Users can provide targeted context descriptions separate from the main task description.

4. **Reduced Manual Work**: Eliminates the need to manually determine and list file paths in many scenarios.

5. **Backward Compatibility**: Existing templates continue to work without modification, as the default behavior remains unchanged.

### Negative

1. **Implementation Complexity**: Adds complexity to the context assembly process and requires new methods in the Memory System.

2. **Security Considerations**: Command execution introduces security concerns that must be carefully addressed.

3. **Performance Impact**: Command execution may introduce latency in task initialization.

4. **Learning Curve**: Users must learn about the new capabilities and how to use them effectively.

## Migration Strategy

1. **Backward Compatibility**: The `source` attribute defaults to "literal", ensuring existing templates continue to work without modification.

2. **Gradual Adoption**: Users can adopt the new capabilities as needed, with no requirement to update existing templates.

3. **Documentation Updates**: Update documentation with examples of when and how to use each source type.

4. **Versioning**: This change represents a minor version increment as it adds functionality without breaking existing code.

## Related Documents

- [Pattern:ContextFrame:1.0] for the overall context management model
- [Contract:Tasks:TemplateSchema:1.0] for XML schema definition
- [Interface:Memory:3.0] for Memory System interface definition
- [ADR 14: Operator Context Configuration] for context management configuration
