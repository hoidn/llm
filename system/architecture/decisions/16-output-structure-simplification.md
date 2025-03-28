# ADR 16: Output Structure Simplification

## Status
Accepted

## Context
The current system has multiple fields for task output:
- `content`: Primary output when task completes
- `partialOutput`/`incompleteContent`: Output from incomplete atomic tasks
- `notes`: Task metadata
- `partialResults`: Results from sequential task steps

This creates unnecessary complexity and ambiguity.

## Decision
We will simplify the output structure:

1. **Atomic Tasks**: Use only `content` and `notes` fields
   - `content`: Contains all output (complete or partial)
   - `notes`: Contains only metadata, never content
   - Task status indicates whether content is complete
   
2. **Sequential/Reduce Tasks**: Maintain existing structure with proper separation
   - Each step/input result contains content and metadata
   - Clear separation between task-level and step-level concerns

## Consequences

### Positive
- Simpler interface with fewer fields
- Clear separation between content and metadata
- Status code provides necessary completion information
- Consistent approach across task types
- Easier error handling and recovery

### Negative
- Requires updates to existing code checking for partialOutput
- Slightly less explicit about content completeness

## Implementation
For atomic tasks, the completion status is determined by the `status` field:
- `COMPLETE`: Content is final and complete
- `FAILED`: Content may be partial or incomplete
- `CONTINUATION`: Content is intermediate

This approach maintains the essential information while simplifying the structure.
