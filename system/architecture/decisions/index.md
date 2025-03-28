# Architecture Decision Records [Index]

This document provides an index of all Architecture Decision Records (ADRs) in the system. ADRs document significant architectural decisions, their context, and consequences.

## ADR Status Table

| ADR Number & Title | Status | File Link | Related ADRs | Affected Components |
|-------------------|--------|-----------|--------------|---------------------|
| ADR 1: Memory System Design | Completed | [001-memory-system.md](./needs_update/001-memory-system.md) | ADR 3 | Memory System |
| ADR 3: Remove Context Update Capability | Completed | [003-memory-context-update.md](./needs_update/003-memory-context-update.md) | ADR 1 | Memory System |
| ADR 4: Sequential Context Management | Implemented | [004-sequential-context-management.md](./needs_update/004-sequential-context-management.md) | ADR 7, ADR 14 | Task System, Evaluator |
| ADR 6: Context Types | Draft | [006-context-types.md](./006-context-types.md) | ADR 2, ADR 5 | Memory System, Task System |
| ADR 7: Context Management Standardization | Proposed | [7-context-standardization.md](./7-context-standardization.md) | ADR 2, ADR 5 | All Components |
| ADR 8: Error Taxonomy for Context Issues | Proposed | [8-errors.md](./8-errors.md) | - | All Components |
| ADR 9: Partial Results Policy | Accepted | [9-partial-results.md](./9-partial-results.md) | ADR 8 | Task System, Evaluator |
| ADR 10: Evaluator-to-Director Feedback Flow | Accepted | [010-evaluator-director.md](./completed/010-evaluator-director.md) | - | Evaluator, Task System |
| ADR 11: Subtask Spawning Mechanism | Accepted | [11-subtask-spawning.md](./11-subtask-spawning.md) | ADR 7, ADR 8 | Task System, Evaluator |
| ADR 12: Function-Based Template Model | Accepted | [012-function-based-templates.md](./completed/012-function-based-templates.md) | ADR 7 | Task System, Compiler |
| ADR 13: JSON Output Standardization | Accepted | [013-json-output.md](./completed/013-json-output.md) | ADR 8 | Task System, Evaluator |
| ADR 14: Operator Context Configuration | Accepted | [14-operator-ctx-config.md](./14-operator-ctx-config.md) | ADR 7 | Task System |
| ADR 15: Notes Field Standardization | Accepted | [15-notes-field-standardization.md](./15-notes-field-standardization.md) | ADR 9 | Task System, Evaluator |
| ADR 16: Output Structure Simplification | Accepted | [16-output-structure-simplification.md](./16-output-structure-simplification.md) | ADR 15 | Task System, Evaluator |

## ADR Status Definitions

- **Proposed**: Initial proposal, under discussion
- **Accepted**: Decision approved, implementation planned
- **Implemented**: Decision fully implemented in the system
- **Completed**: Decision implemented and documentation finalized
- **Superseded**: Replaced by a newer ADR (reference provided)
- **Deprecated**: No longer relevant but kept for historical context

## Navigation

- [System Overview](../../README.md)
- [Architecture Overview](../overview.md)
- [Pattern Index](../patterns/index.md)
- [Component Index](../../../components/index.md)
