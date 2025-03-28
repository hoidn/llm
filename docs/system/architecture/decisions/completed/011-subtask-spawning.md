# ADR 11: Subtask Spawning Mechanism (Summary)

## Status
Accepted

## Context
The system needed a standardized mechanism for dynamic task creation and composition. Previous implementations of continuation-based task spawning were inconsistent across components, with varying approaches to context management, parameter passing, and error handling.

## Decision
Implement a standardized subtask spawning mechanism with the following key features:

1. **Standardized Request Structure**: A well-defined `SubtaskRequest` interface with required fields (type, description, inputs) and optional fields (template_hints, context_management, max_depth, subtype).

2. **Direct Parameter Passing**: All data flow uses direct parameter passing rather than environment variables, ensuring clear dependencies and improved testability.

3. **Context Management Integration**: Default settings with optional overrides following the hybrid approach from ADR 14:
   - `inherit_context: subset` (default)
   - `accumulate_data: false` (default)
   - `accumulation_format: notes_only` (default)
   - `fresh_context: enabled` (default)

4. **Depth Control**: Maximum nesting depth (default: 5) and cycle detection to prevent infinite recursion.

5. **Error Handling**: Standardized error structure that preserves the complete error context, allowing for potential recovery strategies.

6. **Resource Protection**: Resource tracking across the entire subtask chain to prevent exhaustion.

## Consequences
- Consistent subtask spawning behavior across all components
- Clear data flow with explicit dependencies
- Controlled resource usage with protection against infinite recursion
- Improved error handling with context preservation
- Flexible context management with sensible defaults

The full ADR has been moved to ../../../../completed_plans/ for space efficiency.
