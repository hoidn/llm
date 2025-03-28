# Architecture Decision Record: Sequential Context Management

## Status
Implemented (see ADR 14)

## Context
We need to separate context inheritance from data accumulation and provide a robust mechanism for step-by-step history tracking.

Currently, tasks either share context automatically or produce data that might or might not propagate. This leads to confusion when partial outputs are produced but we do not have a consistent mechanism to feed them into subsequent steps. Also, memory consumption can balloon if every subtask blindly appends data. 

## Decision
1. **Introduce `<context_management>`** for controlling context inheritance and accumulation in sequential tasks.  
2. **Add explicit outputtracking** in the Evaluator for each step of a sequential task.  
3. **Provide structured ways** to use task history in associative matching or subsequent steps.  
4. **Include step outputs** in error results for failed sequences.  
5. **Enforce resource limits** on total stored step data.

## Implementation
This ADR has been fully implemented as part of ADR 14 (Operator Context Configuration), which introduced a hybrid configuration approach with operator-specific defaults and explicit overrides:

| Operator Type | inherit_context | accumulate_data | accumulation_format | fresh_context |
|---------------|-----------------|-----------------|---------------------|---------------|
| sequential    | full            | true            | notes_only          | enabled       |

These defaults apply when no explicit context_management block is provided. When present, explicit settings override the defaults, providing both consistency and flexibility.

The implementation includes:
1. Default context settings for all operator types
2. XML schema support for the context_management block
3. Template processing with merged settings (defaults + overrides)
4. Evaluator integration for applying the final configuration
5. Partial results preservation in error handling

## Consequences
- **Cleaner separation of concerns** between inheritance and accumulation  
- **More flexible context management** through distinct modes (`inherit_context`, `accumulate_data`, etc.)  
- **Better step-by-step tracking** for partial outputs  
- **Predictable error output**: if step N fails, steps 1..N-1 remain visible  
- **Clear resource usage capping** for historical data

## Related
- [ADR 14 - Operator Context Configuration] for the complete implementation
- [Pattern:SequentialTask:2.0] in system/architecture/overview.md  
- [misc/operators.md] for structural usage  
- [system/contracts/protocols.md] for updated XSD schema  
- [components/task-system/impl/examples.md] for usage examples
