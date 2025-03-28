# Context Management Examples
    
This document contains examples of context management in the Task System.
    
## Context Management Configuration
    
### Standard Context Management Structure
    
```xml
<task>
    <description>Task description</description>
    <context_management>
        <inherit_context>none|full|subset</inherit_context>
        <accumulate_data>true|false</accumulate_data>
        <accumulation_format>notes_only|full_output</accumulation_format>
        <fresh_context>enabled|disabled</fresh_context>
    </context_management>
    <inputs>
        <input name="input_name" from="source_var"/>
    </inputs>
</task>
```
    
### Context Management Patterns
    
#### Default Context Management
    
```xml
<!-- Example: Sequential Task with Default Context Management -->
<task type="sequential">
    <description>Process and analyze data</description>
    <!-- No context_management block - using defaults:
         inherit_context: full
         accumulate_data: true
         accumulation_format: notes_only
         fresh_context: enabled -->
    <steps>
        <task>
            <description>Load dataset</description>
            <inputs>
                <input name="data_file" from="csv_file_path"/>
            </inputs>
        </task>
        <task>
            <description>Filter invalid rows</description>
        </task>
    </steps>
</task>
```
    
#### Custom Context Management
    
```xml
<!-- Example: Sequential Task with Custom Context Management -->
<task type="sequential">
    <description>Process and analyze data</description>
    <context_management>
        <inherit_context>none</inherit_context>
        <accumulate_data>true</accumulate_data>
        <accumulation_format>full_output</accumulation_format>
        <fresh_context>enabled</fresh_context>
    </context_management>
    <steps>
        <task>
            <description>Load dataset</description>
            <inputs>
                <input name="data_file" from="csv_file_path"/>
            </inputs>
        </task>
        <task>
            <description>Filter invalid rows</description>
        </task>
    </steps>
</task>
```
    
## Context Inheritance Patterns
    
### Pattern 1: Clear All Context (Fresh Start)
    
```xml
<task type="atomic">
    <description>Start with completely fresh context</description>
    <context_management>
        <inherit_context>none</inherit_context>
        <accumulate_data>false</accumulate_data>
        <fresh_context>enabled</fresh_context>
    </context_management>
</task>
```
    
### Pattern 2: Rebuild Context While Preserving History
    
```xml
<task type="sequential">
    <description>Rebuild context while keeping step history</description>
    <context_management>
        <inherit_context>none</inherit_context>
        <accumulate_data>true</accumulate_data>
        <accumulation_format>notes_only</accumulation_format>
        <fresh_context>enabled</fresh_context>
    </context_management>
    <steps>
        <task>
            <description>First step</description>
        </task>
        <task>
            <description>Second step with fresh context but notes from first step</description>
        </task>
    </steps>
</task>
```
    
### Pattern 3: Complete Context Preservation
    
```xml
<task type="sequential">
    <description>Preserve all context</description>
    <context_management>
        <inherit_context>full</inherit_context>
        <accumulate_data>true</accumulate_data>
        <accumulation_format>full_output</accumulation_format>
        <fresh_context>disabled</fresh_context>
    </context_management>
    <steps>
        <task>
            <description>First step</description>
        </task>
        <task>
            <description>Second step with all context preserved</description>
        </task>
    </steps>
</task>
```
    
## File Path Examples
    
### Atomic Task with File Paths
    
```xml
<!-- Example: Atomic Task with File Paths -->
<task type="atomic">
    <description>Analyze the main source files</description>
    <context_management>
        <inherit_context>none</inherit_context>
        <fresh_context>disabled</fresh_context>
    </context_management>
    <file_paths>
        <path>./src/main.py</path>
        <path>./src/utils.py</path>
    </file_paths>
</task>
```
    
### Combining File Paths with Context Management
    
```xml
<!-- Example: Combining File Paths with fresh_context -->
<task type="atomic">
    <description>Analyze code with base context and specific files</description>
    <context_management>
        <inherit_context>none</inherit_context>
        <fresh_context>enabled</fresh_context>
    </context_management>
    <file_paths>
        <path>./src/main.py</path>
        <path>./src/utils.py</path>
    </file_paths>
</task>
```
    
## TypeScript Usage Example
    
```typescript
// Execute atomic task with specific file paths
const result = await taskSystem.executeTask(
  "<task type='atomic'><description>Analyze source files</description><file_paths><path>./src/main.py</path><path>./src/utils.py</path></file_paths></task>",
  memorySystem
);

// Create subtask request with file paths
return {
  status: "CONTINUATION",
  notes: {
    subtask_request: {
      type: "atomic",
      description: "Analyze specific modules",
      inputs: { level: "detailed" },
      context_management: { inherit_context: "subset" },
      file_paths: ["./src/main.py", "./src/utils.py"]
    }
  }
};
```
    
## Related Documentation
    
For more details, see:
- [Context Frame Pattern](../../../../system/architecture/patterns/context-frames.md)
- [ADR 14: Operator Context Configuration](../../../../system/architecture/decisions/completed/014-operator-ctx-config.md)
- [Context Management Implementation](../design.md#context-management-implementation)
