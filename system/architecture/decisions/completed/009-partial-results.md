# ADR 9: Partial Results Policy (Summary)

## Status
Accepted and Implemented

## Context
When multi-step operations fail partway through execution, the system needs a standardized approach for preserving and exposing partial results. This is particularly important for sequential and reduce tasks where significant work may have been completed before failure.

## Decision
We will implement a standardized approach for preserving partial results across different task types:

1. **Atomic Tasks**: Store partial content in `notes.partialOutput`
2. **Sequential Tasks**: Store step-by-step outputs in `details.partialResults` with metadata
3. **Reduce Tasks**: Store processed input results and current accumulator state

The format of preserved partial results will be controlled by the task's `accumulation_format` setting:
- `notes_only`: Only summary information (default for memory efficiency)
- `full_output`: Complete outputs (with size limits)

## Consequences
- Improved debugging and recovery capabilities
- Consistent error structures across task types
- Memory usage management through format control
- Ability to resume or recover from partial execution

## Implementation Notes
- All partial results storage is ephemeral (in-memory only)
- Size limits prevent memory issues with large partial outputs
- Recovery is limited to simple retries in the MVP
- Error structures are consistent with the error taxonomy in ADR 8

## Related Documents
- Full ADR: ../../../../completed_plans/adr9-partial-results.md
- Error Handling: ../patterns/errors.md
