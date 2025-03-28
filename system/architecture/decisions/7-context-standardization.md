# Architecture Decision Record: Context Management Standardization

## Status
Proposed

## Context
The current system architecture has ambiguity regarding context management across different operator types. While sequential tasks have a well-defined context management structure, other operators like Reduce lack standardized context handling. This inconsistency creates several issues:

1. Unclear inheritance behavior for non-sequential operators
2. Ambiguity about whether to preserve partial results on failure
3. Undefined combinations of context inheritance, accumulation, and fresh context generation
4. Lack of clarity about how the "subset" inheritance mode works
5. Inconsistent behavior between operator types

The system needs standardized context management that works consistently across all operators while respecting their unique execution patterns.

## Decision
We will standardize context management across all operators using a three-dimensional model that explicitly controls:
1. Context inheritance from parent
2. Accumulation of outputs from previous steps
3. Generation of fresh context through associative matching

Additionally, we will support an orthogonal file-specific context mechanism:
4. Explicit file inclusion via `file_paths` that overrides standard context retrieval mechanisms

With one key constraint:
- Fresh context generation (`fresh_context="enabled"`) is mutually exclusive with context inheritance (`inherit_context="full"` or `inherit_context="subset"`)

This will be implemented through a unified XML schema structure that can be applied hierarchically within nested operators.

## Specification

### XML Schema for Context Management

```xml
<context_management>
    <!-- Controls parent context inheritance -->
    <inherit_context>full|none|subset</inherit_context>
    
    <!-- Controls accumulation of previous step outputs -->
    <accumulate_data>true|false</accumulate_data>
    <accumulation_format>notes_only|full_output</accumulation_format>
    
    <!-- Controls whether fresh context is generated via associative matching -->
    <fresh_context>enabled|disabled</fresh_context>
</context_management>
```

### Explicit File Path Specification

In addition to the standard context management model, tasks can explicitly specify files to include in their context:

```xml
<file_paths>
    <path>./src/main.py</path>
    <path>/absolute/path/file.txt</path>
</file_paths>
```

This feature operates orthogonally to the three-dimensional context model:
- Specified files are always included in the context, regardless of other settings
- When combined with `inherit_context="subset"`, the specified files become the subset
- When combined with `fresh_context="enabled"`, associative matching still runs but specified files are forcibly included

### Semantics

1. **inherit_context**:
   - `full`: Uses the entire parent context unchanged
   - `none`: Uses no parent context
   - `subset`: Filters parent context through associative matching based on task relevance

2. **accumulate_data**:
   - `true`: Preserves and accumulates outputs from previous steps
   - `false`: No accumulation between steps

3. **accumulation_format** (when accumulate_data is true):
   - `notes_only`: Only preserves summary information from previous steps
   - `full_output`: Preserves complete outputs from previous steps

4. **fresh_context**:
   - `enabled`: Performs associative matching to generate new context from global data
   - `disabled`: No new context generation, uses only inherited/accumulated context

### Context Management Constraints

To simplify the system and prevent context duplication, these settings must follow one key constraint:

- If `inherit_context` is set to "full" or "subset", then `fresh_context` must be "disabled"
- If `fresh_context` is set to "enabled", then `inherit_context` must be "none"

This constraint ensures that either a task inherits context from its parent (fully or partially) OR it generates fresh context via associative matching, but never both. This simplifies implementation and prevents potential duplication of context data.

### Subtype-Based Defaults

For atomic tasks, defaults differ based on the subtype:

- **standard**: Regular atomic tasks default to `inherit_context="full"` and `fresh_context="disabled"`
- **subtask**: Tasks created via CONTINUATION default to `inherit_context="none"` and `fresh_context="enabled"`

This distinction allows regular tasks to smoothly inherit context from their parent, while enabling subtasks to start with fresh, task-specific context.

### Application in Different Operators

#### Atomic Tasks
```xml
<task type="atomic">
    <context_management>
        <inherit_context>full|none|subset</inherit_context>
        <fresh_context>enabled|disabled</fresh_context>
    </context_management>
</task>
```

#### Sequential Tasks
```xml
<task type="sequential">
    <context_management>
        <inherit_context>full|none|subset</inherit_context>
        <accumulate_data>true|false</accumulate_data>
        <accumulation_format>notes_only|full_output</accumulation_format>
        <fresh_context>enabled|disabled</fresh_context>
    </context_management>
</task>
```

#### Reduce Tasks
```xml
<task type="reduce">
    <!-- Parent context management -->
    <context_management>
        <inherit_context>full|none|subset</inherit_context>
        <fresh_context>enabled|disabled</fresh_context>
    </context_management>
    
    <inner_task>
        <!-- Context for processing each input -->
        <context_management>
            <inherit_context>full|none|subset</inherit_context>
            <fresh_context>enabled|disabled</fresh_context>
        </context_management>
    </inner_task>
    
    <reduction_task>
        <!-- Context for combining results -->
        <context_management>
            <inherit_context>full|none|subset</inherit_context>
            <fresh_context>enabled|disabled</fresh_context>
        </context_management>
    </reduction_task>
</task>
```

### Standard Defaults by Operator Type

| Operator Type (Subtype) | inherit_context | accumulate_data | accumulation_format | fresh_context |
|-------------------------|-----------------|-----------------|---------------------|---------------|
| atomic (standard)       | full            | N/A             | N/A                 | disabled      |
| atomic (subtask)        | none            | N/A             | N/A                 | enabled       |
| sequential              | full            | true            | notes_only          | disabled      |
| reduce                  | none            | N/A             | N/A                 | enabled       |
| reduce.inner_task       | full            | N/A             | N/A                 | disabled      |
| reduce.reduction_task   | full            | N/A             | N/A                 | disabled      |

### Validation Rules

1. **Invalid Combinations**:
   - `inherit_context="none"` + `accumulate_data="false"` + `fresh_context="disabled"` results in no context at all, which should trigger a warning
   - When `accumulate_data="true"`, `accumulation_format` must be specified

2. **Required Fields**:
   - `inherit_context` is required in all context_management blocks
   - `fresh_context` is required in all context_management blocks
   - `accumulate_data` is required for sequential tasks
   - If `accumulate_data="true"`, then `accumulation_format` is required

### Context Extension vs. Merging

From ADR:002, we maintain the principle that the system uses **context extension** rather than context merging:

1. Tasks extend from parent context rather than merging multiple contexts
2. No complex merging algorithms are used
3. Context changes are additive, not transformative
4. This simpler model satisfies composition requirements while reducing complexity

### Fixed Configuration Timing

From ADR:005, we maintain that context management settings are fixed at template definition time:

1. Context settings cannot be dynamically modified during task execution
2. Settings remain consistent within a task/sequence
3. This provides predictable behavior and simplifies implementation

### Memory System Scope and Responsibilities

From ADR:005, we clarify that the Memory System:

1. Does not perform ranking or prioritization of matched files
2. Only provides associative matching based on the input structure
3. Returns matches without applying any sorting or relevance scoring
4. Delegates all ranking and selection decisions to the task implementers

### Backward Compatibility

To maintain backward compatibility with existing task definitions:

1. For existing sequential tasks that don't specify `fresh_context`:
   - Default to `fresh_context="enabled"`

2. For existing reduce tasks without context_management:
   - Apply the standard defaults shown in the table above
   - Do not require context_management blocks in existing templates

3. For existing atomic tasks:
   - Default to `inherit_context="full"` and `fresh_context="enabled"`

4. Migration path:
   - Update task templates gradually to include explicit context_management
   - Validate that applied defaults match expected behavior
   - Document any behavior changes in task execution

## Consequences

### Positive

1. **Consistency**: All operators use the same context management model
2. **Clarity**: Explicit control over all three dimensions of context
3. **Flexibility**: Different combinations support diverse workflow needs
4. **Extensibility**: Easy to extend to new operator types
5. **Simplicity**: Maintains extension over merging, reducing complexity

### Negative

1. **Verbosity**: More XML elements required for full specification
2. **Complexity**: More combinations to understand and document
3. **Implementation effort**: Need to update multiple components to support the model

## Implementation Guidelines

### Context Assembly Process

The Evaluator should implement context assembly as follows:

```typescript
function assembleContextForTask(task, parentContext, previousOutputs) {
  // 1. Construct base context input
  const contextInput: ContextGenerationInput = {
    taskText: task.description
  };
  
  // 2. Add parent context based on inheritance setting
  if (task.contextManagement.inheritContext !== 'none') {
    contextInput.inheritedContext = parentContext;
  }
  
  // 3. Add accumulated outputs if applicable
  if (task.contextManagement.accumulateData === true) {
    contextInput.previousOutputs = formatAccumulatedOutputs(
      previousOutputs,
      task.contextManagement.accumulationFormat
    );
  }
  
  // 4. Perform associative matching if fresh context is enabled
  if (task.contextManagement.freshContext === 'enabled') {
    return memorySystem.getRelevantContextFor(contextInput);
  } else {
    // 5. Otherwise, just use the assembled context without matching
    return {
      context: contextInput.inheritedContext || '',
      matches: []
    };
  }
}
```

### Dual Context Tracking

From ADR:005, we maintain dual context tracking when both inheritance and accumulation are active:

1. "Regular" inherited context and "accumulated" context are tracked separately
2. These can be concatenated for use but remain distinct types of input
3. This allows for clean separation between different context sources

### "subset" Mode Implementation

The "subset" mode should be implemented in the following way:

1. When `inherit_context="subset"`, the Evaluator still includes the parent context in the ContextGenerationInput
2. The Memory System's associative matching is responsible for filtering the parent context based on relevance to the task
3. This filtered context is then combined with any accumulated data and fresh context (if enabled)

### Input Structure for Associative Matching

From ADR:005, we clarify the structure of input to getRelevantContextFor():

```typescript
interface ContextGenerationInput {
  taskText: string;              // Always included - the task description
  inheritedContext?: string;     // Included based on inherit_context setting
  previousOutputs?: string;      // Included if accumulate_data is true
}
```

Each section has standardized headings from system configuration, allowing the Memory System to properly identify and process different context components.

### Memory Operation Error Handling

From ADR:002, we maintain a simple error handling approach for memory operations:

1. Memory operations that fail should be retried once
2. If retry fails, surface an informative error
3. Ensure that error propagation follows the standard error taxonomy

### Warning Behavior

From ADR:002, we maintain that resource warning thresholds are purely informative:

1. Warnings do not affect execution flow
2. They serve as indicators of approaching limits
3. Only hard limits trigger execution changes
4. This maintains a clear separation between warnings and errors

### Partial Results Handling

When a subtask fails within an operator:

1. For Sequential tasks with `accumulate_data="true"`:
   - All outputs from completed steps should be preserved
   - These should be included in the error result's `notes.partialResults` field
   - This allows higher-level tasks to handle partial success appropriately

2. For Reduce tasks:
   - If any inner_task fails, the partial results up to that point should be preserved
   - The error should include which input caused the failure
   - No automatic retry should be attempted

## Relationship to Existing ADRs

This ADR partially supersedes but incorporates key principles from:

1. **ADR:002-context-management**:
   - Preserves: Extension vs. merging, warning behavior, memory operation error handling
   - Enhances: Context selection with explicit fresh_context control
   - Replaces: Ambiguous context inheritance for non-sequential operators

2. **ADR:005-context-handling**:
   - Preserves: Dual context tracking, memory system scope limitations, configuration timing
   - Enhances: Operator-specific context support with standardized model
   - Replaces: Limited context inheritance descriptions

Both ADRs remain valuable for historical context and rationale but should be read in conjunction with this standardization ADR for current implementation guidance.

## Examples

### Basic Sequential Task

```xml
<task type="sequential">
    <description>Process data in steps</description>
    <context_management>
        <inherit_context>full</inherit_context>
        <accumulate_data>true</accumulate_data>
        <accumulation_format>notes_only</accumulation_format>
        <fresh_context>enabled</fresh_context>
    </context_management>
    <steps>
        <!-- Steps definition -->
    </steps>
</task>
```

### Isolated Sequential Task

```xml
<task type="sequential">
    <description>Process data in isolation</description>
    <context_management>
        <inherit_context>none</inherit_context>
        <accumulate_data>true</accumulate_data>
        <accumulation_format>full_output</accumulation_format>
        <fresh_context>enabled</fresh_context>
    </context_management>
    <steps>
        <!-- Steps definition -->
    </steps>
</task>
```

### Reduce with Custom Context

```xml
<task type="reduce">
    <description>Process multiple inputs</description>
    <context_management>
        <inherit_context>subset</inherit_context>
        <fresh_context>enabled</fresh_context>
    </context_management>
    <inner_task>
        <context_management>
            <inherit_context>none</inherit_context>
            <fresh_context>disabled</fresh_context>
        </context_management>
        <!-- Inner task definition -->
    </inner_task>
    <reduction_task>
        <context_management>
            <inherit_context>full</inherit_context>
            <fresh_context>enabled</fresh_context>
        </context_management>
        <!-- Reduction task definition -->
    </reduction_task>
</task>
```

### Minimal Context Atomic Task

```xml
<task type="atomic">
    <description>Simple transformation</description>
    <context_management>
        <inherit_context>none</inherit_context>
        <fresh_context>disabled</fresh_context>
    </context_management>
    <!-- Task definition -->
</task>
```

## Related Documents

- [Pattern:ContextFrame:1.0] - Context frame patterns
- [ADR:002-context-management] - Initial context management decisions
- [ADR:005-context-handling] - Context handling clarifications
- [ADR:004-sequential-context-management] - Sequential task context management
