# Sequential and Reduce Operator Specification

## Purpose
Define the structure and semantics of Sequential and Reduce operators for task composition and execution, specifying XML schemas and execution behaviors.

## Memory Structure
```typescript
shortTermMemory: {
    files: Map<string, WorkingFile>;
    dataContext: string;
}
```

## Sequential Operator

### Purpose
Execute a series of tasks with explicit dependencies. Maintains execution order while allowing parallel execution of independent inputs.

### Structure
```xml
<task type="sequential">
    <description>Analyze {{dataset_name}} using provided configuration</description>
    <context_management>
        <inherit_context>none</inherit_context>
        <accumulate_data>true</accumulate_data>
        <accumulation_format>notes_only</accumulation_format>
    </context_management>
    <steps>
        <task>
            <description>Load initial data</description>
            <inputs>
                <input name="data" from="raw_data"/>
            </inputs>
        </task>
        <task>
            <description>Apply configuration from {{config_profile}}</description>
            <inputs>
                <input name="config" from="default_config"/>
            </inputs>
        </task>
    </steps>
</task>
```

### Context Management

#### Operator Default Settings

Each operator type has specific default context management settings that apply when no explicit configuration is provided:

| Operator Type | inherit_context | accumulate_data | accumulation_format | fresh_context |
|---------------|-----------------|-----------------|---------------------|---------------|
| atomic        | full            | false           | notes_only          | enabled       |
| sequential    | full            | true            | notes_only          | enabled       |
| reduce        | none            | true            | notes_only          | enabled       |
| script        | full            | false           | notes_only          | disabled      |
| director_evaluator_loop | none  | true            | notes_only          | enabled       |

#### Context Management Dimensions

The system uses a standardized three-dimensional context management model:

1. **inherit_context**: An enumeration with allowed values:
   - **full** – the full parent context is passed unchanged
   - **none** – no parent context is inherited
   - **subset** – only a subset (as determined by task-specific rules) is inherited

2. **accumulate_data**: A boolean controlling whether outputs from prior steps are accumulated:
   - **true** – previous step outputs are accumulated
   - **false** – no accumulation of step outputs

3. **accumulation_format**: When accumulating data, specifies the storage format:
   - **notes_only** – only summary information is preserved
   - **full_output** – complete step outputs are preserved

4. **fresh_context**: Controls whether new context is generated via associative matching:
   - **enabled** – fresh context is generated
   - **disabled** – no fresh context is generated

#### Context Management Override

These dimensions can be explicitly configured through a standardized XML structure:

```xml
<context_management>
    <inherit_context>full|none|subset</inherit_context>
    <accumulate_data>true|false</accumulate_data>
    <accumulation_format>notes_only|full_output</accumulation_format>
    <fresh_context>enabled|disabled</fresh_context>
</context_management>
```

When the `<context_management>` block is present, its settings override the operator defaults. When it's omitted, the operator-specific defaults apply. This hybrid approach provides both consistency and flexibility.

Settings are merged during template loading, with explicit settings taking precedence over defaults. This ensures that task authors can rely on sensible defaults while still having the ability to customize context behavior when needed.

**Note:** Partial results are now preserved when subtasks fail, with the format determined by the `accumulation_format` setting.

### Execution Semantics
- Tasks execute in specified order
- For tasks with multiple inputs:
  - All input tasks execute in parallel
  - Parent task executes after all inputs complete
- Execution fails if:
  - Required task structure is missing/invalid
  - Any task execution fails (with failure context indicating which task)

## Reduce Operator

### Purpose
Process a list of named inputs through repeated application of inner task and reduction operations.

### Structure
```xml
<task type="reduce">
    <description>Reduction operation description</description>
    <initial_value>
        <!-- Initial accumulator value -->
    </initial_value>
    <inputs>
        <input name="dataset1">Value 1</input>
        <input name="dataset2">Value 2</input>
        <input name="dataset3">Value 3</input>
    </inputs>
    <inner_task>
        <description>Processing for each input</description>
        <inputs>
            <input name="current_data">
                <!-- Current input being processed -->
            </input>
            <input name="metadata">
                <!-- Additional input needed for processing -->
                <task>
                    <description>Load metadata for processing</description>
                </task>
            </input>
        </inputs>
    </inner_task>
    <reduction_task>
        <description>Combine current result with accumulator</description>
        <inputs>
            <input name="current_result">
                <!-- Result from inner_task -->
            </input>
            <input name="accumulator">
                <!-- Current accumulated value -->
            </input>
            <input name="original_input">
                <!-- Original input being processed -->
            </input>
        </inputs>
    </reduction_task>
</task>
```

### Execution Semantics
- For each named input:
  1. Execute inner_task with:
     - Current input
     - Any additional specified inputs
     - When both inheritance and accumulation are enabled in a reduce operator, a basic inheritance model is used without merging accumulated outputs. Advanced dual-context tracking is deferred to future iterations.
  2. Execute reduction_task with:
     - Current inner_task result
     - Current accumulator value
     - Original input
  3. Result becomes new accumulator value
- Maintains strict ordering of input processing
- Context changes managed by memory system
- Execution fails if:
  - Required task structure is missing/invalid 
  - Any inner_task execution fails (with failure context indicating which input)
  - Any reduction_task execution fails (with failure context indicating current state)

## Integration Points

### With Memory System
- System maintains execution context via shortTermMemory
- Files and data context available to all tasks
- Context changes managed by memory system, not tasks

### With Task System
- Responsible for generating valid XML
- Manages task decomposition on failure
- Handles task library matching

## Dependencies
- Error types defined in errorspec.md
- Memory system must handle context
- Task system must support XML generation

## Constraints
- Tasks cannot modify context directly
- XML structure must encode all input dependencies
- All inputs must have unique names within their scope
- Inner tasks can specify multiple inputs

## Subtask Spawning Integration

The Task System supports dynamic subtask spawning through a standardized mechanism:

```typescript
interface SubtaskRequest {
  // Required fields
  type: TaskType;                      // Type of subtask to spawn
  description: string;                 // Description of the subtask
  inputs: Record<string, any>;         // Input parameters for the subtask
  
  // Optional fields
  template_hints?: string[];           // Hints for template selection
  context_management?: {               // Override default context settings
    inherit_context?: 'full' | 'none' | 'subset';
    accumulate_data?: boolean;
    accumulation_format?: 'notes_only' | 'full_output';
    fresh_context?: 'enabled' | 'disabled';
  };
  max_depth?: number;                  // Override default max nesting depth
  subtype?: string;                    // Optional subtype for atomic tasks
}
```

### Context Management Defaults

Subtasks have specific default context management settings:

| Setting | Default Value | Description |
|---------|---------------|-------------|
| inherit_context | subset | Inherits only relevant context from parent |
| accumulate_data | false | Does not accumulate previous step outputs |
| accumulation_format | notes_only | Stores only summary information |
| fresh_context | enabled | Generates new context via associative matching |

These defaults can be overridden through explicit configuration in the SubtaskRequest.

### Data Flow

Subtask spawning uses direct parameter passing rather than environment variables:

1. Parent task returns with `status: "CONTINUATION"` and a `subtask_request` in its notes
2. System validates the request and selects an appropriate template
3. Subtask executes with inputs from the request
4. Subtask result is passed back to the parent task when execution resumes

This approach ensures clear data dependencies and improves debug visibility.

### Depth Control

To prevent infinite recursion and resource exhaustion:

1. **Maximum Nesting Depth**: Default limit of 5 levels of nested subtasks
2. **Cycle Detection**: Prevention of tasks spawning identical subtasks
3. **Resource Tracking**: Monitoring of total resource usage across the subtask chain
4. **Timeout Enforcement**: Overall time limits for the complete subtask chain

These mechanisms ensure that subtask spawning remains controlled and resource-efficient.
