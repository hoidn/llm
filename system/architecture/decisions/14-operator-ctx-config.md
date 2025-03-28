# Architecture Decision Record: Context Management Settings Configuration

## Status
Proposed

## Context
The system's architecture defines a three-dimensional context management model that controls:
1. Context inheritance from parent tasks
2. Accumulation of outputs from previous steps
3. Generation of fresh context through associative matching

We need to determine how these settings should be configured in the system - whether through operator attributes at the code/AST level, explicitly in template XML, or through a hybrid approach.

This decision impacts:
- Template authoring experience
- System flexibility and extensibility
- Runtime behavior predictability
- Backward compatibility
- Implementation complexity

## Decision
We will implement a hybrid approach where:

1. Each operator type (atomic, sequential, reduce, etc.) defines sensible defaults for context management settings
2. Template XML can explicitly override these defaults using a `<context_management>` block
3. The system will merge operator defaults with explicit XML settings at template loading time
4. Validation of combined settings will occur during template registration rather than execution

### Configuration Structure

Operator defaults will be defined in code:

```typescript
// Example for Sequential operator
const SEQUENTIAL_DEFAULTS = {
  inheritContext: "full",
  accumulateData: true,
  accumulationFormat: "notes_only",
  freshContext: "enabled"
};

// Example for Atomic operator
const ATOMIC_DEFAULTS = {
  inheritContext: "full",
  accumulateData: false,  // N/A but defined for consistency
  accumulationFormat: null, // N/A
  freshContext: "enabled"
};
```

XML templates can override these defaults:

```xml
<task type="sequential">
  <description>Process data in steps</description>
  <context_management>
    <inherit_context>none</inherit_context>
    <accumulate_data>true</accumulate_data>
    <accumulation_format>full_output</accumulation_format>
    <fresh_context>disabled</fresh_context>
  </context_management>
  <steps>
    <!-- Tasks defined here -->
  </steps>
</task>
```

### Standard Operator Defaults

| Operator Type (Subtype) | inherit_context | accumulate_data | accumulation_format | fresh_context |
|-------------------------|-----------------|-----------------|---------------------|---------------|
| atomic (standard)       | full            | N/A             | N/A                 | disabled      |
| atomic (subtask)        | none            | N/A             | N/A                 | enabled       |
| sequential              | full            | true            | notes_only          | disabled      |
| reduce                  | none            | N/A             | N/A                 | enabled       |
| reduce.inner_task       | full            | N/A             | N/A                 | disabled      |
| reduce.reduction_task   | full            | N/A             | N/A                 | disabled      |
| script                  | full            | N/A             | N/A                 | disabled      |

### Validation Rules

1. **Mutual Exclusivity**:
   - `fresh_context="enabled"` cannot be combined with `inherit_context="full"` or `inherit_context="subset"`
   - If `inherit_context` is set to "full" or "subset", then `fresh_context` must be "disabled"
   - If `fresh_context` is "enabled", then `inherit_context` must be "none"

2. **Subtype Context Rules**:
   - The `subtype` attribute affects default context settings but not validation rules
   - Explicit context settings in XML always override subtype-based defaults
   - Mutual exclusivity constraint is enforced regardless of subtype

3. **Default Selection Logic**:
   - Context management defaults are determined by operator type + subtype
   - For atomic tasks, defaults differ between "standard" and "subtask" subtypes
   - For CONTINUATION-based subtasks, the "subtask" subtype is automatically applied

4. **Invalid Combinations**:
   - `inherit_context="none"` + `accumulate_data="false"` + `fresh_context="disabled"` results in no context at all, which should trigger a warning

### Implementation Process

1. During template loading:
   - Parse XML template
   - Determine operator type
   - Apply operator defaults
   - Override with any explicit settings from XML
   - Validate the combined settings
   - Store the final settings with the task template

2. During execution:
   - Use the stored settings to control context flow
   - No additional runtime resolution required
   - Consistent behavior for each task type

## Consequences

### Positive
1. **Flexible Configuration:** Tasks can customize their context behavior without changing code
2. **Sensible Defaults:** Common patterns work without verbose configuration
3. **Explicit when Needed:** Context behavior can be made explicit for complex tasks
4. **Template Evolution:** Context management can evolve without code changes
5. **Validation at Source:** Configuration errors are caught during template loading
6. **Documentation Value:** XML configuration serves as self-documentation
7. **LLM Compatibility:** LLM-generated templates can include explicit context settings

### Negative
1. **Implementation Complexity:** More complex merging and validation logic required
2. **Documentation Burden:** Need to clearly document operator defaults and override rules
3. **Validation Complexity:** Must validate combined settings rather than just explicit ones
4. **Learning Curve:** Users need to understand both defaults and override mechanisms
5. **Potential Inconsistency:** Different tasks of the same type could behave differently

## Implementation Requirements

1. **Operator Registry:** Define default settings for each operator type
2. **XML Schema Updates:** Ensure schema validates all context management combinations
3. **Merge Logic:** Implement logic to combine defaults with explicit settings
4. **Validation Rules:** Define validation rules for combined settings
5. **Error Messages:** Create clear error messages for invalid combinations
6. **Documentation:** Document operator defaults and override rules

## Migration Strategy

1. **Backward Compatibility:** Existing templates without explicit context management blocks will continue to work with operator defaults
2. **Graceful Degradation:** Invalid combinations will be detected at load time with clear error messages
3. **Documentation Updates:** Update documentation to explain the hybrid approach
4. **Example Templates:** Provide examples of common override patterns

## Related Decisions

- [ADR 7: Context Management Standardization]
- [ADR 11: Subtask Spawning Mechanism]

## Open Questions

1. Should we allow partial overrides, or require all settings to be specified when overriding?
2. Should we introduce additional validation for operator-specific constraints (e.g., certain operators might have restricted combinations)?
3. How should we handle future additions to the context management model?

## Conclusion

The hybrid approach provides a balance between consistency and flexibility. It offers sensible defaults while enabling explicit customization when needed. This approach aligns with the system's current architecture while providing a clear path for evolution.
