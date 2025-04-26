# AtomicTaskExecutor Interfaces [Interface:AtomicTaskExecutor:1.0]

> This document is the authoritative source for the AtomicTaskExecutor public API.

## Overview

The AtomicTaskExecutor executes the body of a pre-parsed atomic task, performing parameter substitution and invoking the Handler.

## Core Interface

```typescript
/**
 * Interface for the Atomic Task Executor.
 * Responsible for executing the body of a pre-parsed atomic XML task template.
 * [Interface:AtomicTaskExecutor:1.0]
 */
interface AtomicTaskExecutor {
    /**
     * Executes the body of a pre-parsed atomic task template.
     * Preconditions:
     * - `atomic_task_def` is a valid parsed representation of an atomic task template.
     * - `params` dictionary contains keys matching the atomic task's declared `<inputs>` names, with values being the fully evaluated results passed from the original invocation (e.g., S-expression `call`).
     * - `handler` is a valid BaseHandler instance.
     * @param atomic_task_def - A representation of the parsed atomic task XML.
     * @param params - A dictionary mapping declared input parameter names to their evaluated values.
     * @param handler - A valid BaseHandler instance to use for LLM/tool execution.
     * @returns Promise resolving to the TaskResult dictionary from the handler call.
     * @throws {ParameterMismatch} If substitution references a parameter not in `params`.
     * @throws {TaskError} Propagated from the handler call if execution fails.
     */
    execute_body(
        atomic_task_def: object, // Represents ParsedAtomicTask
        params: dict<string, Any>,
        handler: object // Represents BaseHandler
    ): Promise<dict<string, Any>>; // Represents TaskResult
}
```

## Type References

For system-wide types (like TaskResult), see [Type:System:1.0] in `/system/contracts/types.md`.

## Integration Points

- Invoked by **Task System**.
- Invokes **Handler**.
