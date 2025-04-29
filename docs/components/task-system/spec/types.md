# Task System Types [Type:TaskSystem:1.0]

> **Note:** Most types related to task execution (`TaskResult`, `SubtaskRequest`, `EvaluationResult`, `ContextManagement`, etc.) are defined centrally as system-wide types. Please refer to the authoritative definitions in `/docs/system/contracts/types.md`.
> This file is kept for context but contains no active local type definitions.

## Type References

For system-wide types, see `[Type:System:1.0]` in `/docs/system/contracts/types.md`, which includes:
- TaskResult
- SubtaskRequest (for invoking atomic tasks)
- EvaluationResult (specialized TaskResult)
- TaskType (`atomic`)
- AtomicTaskSubtype enums
- ReturnStatus enum (`COMPLETE`, `CONTINUATION`, `FAILED`)
- ContextManagement interface
- TaskError types

## Cross-References

- For XML schema definitions, see [Contract:Tasks:TemplateSchema:1.0] in `/docs/system/contracts/protocols.md`
- For TaskSystem interfaces, see `/docs/components/task-system/spec/interfaces.md`
- For public API surface, see [Interface:TaskSystem:1.0] in `/docs/components/task-system/api/interfaces.md`

// ## Removed Types (Now Defined Centrally or Deprecated) ##
// TaskResult -> Defined in /docs/system/contracts/types.md
// BaseTaskDefinition -> Deprecated (Internal/XML concept)
// TaskTemplate -> Deprecated (Internal/XML concept)
// SubtaskRequest -> Defined in /docs/system/contracts/types.md
// EvaluationResult -> Defined in /docs/system/contracts/types.md
