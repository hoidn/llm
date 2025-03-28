# ADR 14: Operator Context Configuration [Summary]

## Status
Completed - Full version moved to completed_plans directory

## Context
Operators needed a standardized way to configure context management with sensible defaults for different operator types.

## Decision
Implemented a hybrid configuration approach where:
- Each operator type has specific default settings
- Explicit settings in `context_management` blocks override defaults
- Sequential tasks default to `notes_only` accumulation format
- Context inheritance and accumulation behaviors are configurable

## Consequences
- Reduced boilerplate in task definitions
- Improved memory efficiency with appropriate defaults
- Maintained flexibility through explicit overrides
- Standardized context management across operator types
