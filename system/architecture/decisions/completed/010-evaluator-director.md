# ADR 10: Evaluator-to-Director Feedback Flow [Summary]

## Status
Accepted

## Context
The system needed a standardized approach for feedback flow between Director and Evaluator components, replacing ad-hoc environment variable usage with direct parameter passing.

## Decision
1. Replace environment variable references (e.g., `last_evaluator_output`) with direct parameter passing
2. Add a dedicated `director_evaluator_loop` task type
3. Update XML schema and type definitions
4. Standardize the Director-Evaluator pattern with both dynamic and static variants

## Consequences
### Positive
- Clearer data flow between components
- Improved testability with explicit dependencies
- Better support for iterative refinement processes
- Consistent XML schema for both variants

### Negative
- Required updates to existing documentation and code
- Slightly more verbose XML structure

## Implementation
The implementation included:
- Adding `director_evaluator_loop` task type to TaskType enum
- Creating DirectorEvaluatorLoopTask interface
- Standardizing EvaluationResult structure
- Updating XML schema with new elements
- Removing environment variable references

See the full ADR for complete implementation details.
