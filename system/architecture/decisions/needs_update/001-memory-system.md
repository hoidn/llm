# Architecture Decision Record: Memory System Design

## Context

The memory system needs to manage short-term task context and maintain a global index of file metadata, while delegating file access to direct tool usage. This ADR captures key decisions about responsibilities and interfaces.

## Related Documents
- See [Component:Memory:3.0] in components/memory/api/interfaces.md for interface specification
- See [Component:TaskSystem:1.0] in components/task-system/README.md for task execution details
- See [Interface:Handler:Tools:1.0] for file access tools

## Decisions

### Memory System Scope

1. **Component Responsibilities**
   - Maintains short-term task data context
   - Manages global file metadata index
   - Delegates file access to Handler tools
   - Does not handle file content storage or retrieval
   - Follows read-only context model (no updateContext capability)

2. **Memory Organization**
   - Working Memory includes only data context from associative matching
   - Global Index includes file paths and associated metadata strings
   - Clear separation between metadata indexing and file access

### Context Management

1. **Context Sources**
   - Short-term context comes from:
     * Associative matching results
     * Direct updates during task execution
   - Global index serves as bootstrap for associative matching
   - File content accessed via Handler tools when needed

2. **Context Control**
   - Associative matching uses global index for initial filtering
   - Actual file content accessed through Handler tools
   - Metadata strings provide search context without content storage

### Interface Design

1. **Global Index**
   - Simple map of file paths to metadata strings
   - Bulk updates only
   - No hierarchical organization
   - Serves as search bootstrap

2. **Associative Match Results**
   - Combines unstructured context with file matches
   - File matches include optional per-file metadata 
   - File paths used with Handler tools for content access

## Consequences

1. **Positive**
   - Simplified memory system responsibilities
   - Clear separation between metadata and content
   - More flexible file access via tools
   - Reduced system complexity

2. **Negative**
   - Requires tool support in Handler
   - May need optimization for large file sets
   - Potential context window pressure from file content

## Implementation Notes

1. Update Memory System interface to reflect simplified scope
2. Implement Handler file access tools
3. Ensure efficient global index updates
4. Review associative matching for new approach
