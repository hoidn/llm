# AtomicTaskExecutor Component [Component:Evaluator:1.0]

## Overview

The AtomicTaskExecutor is responsible for executing the body of a single, pre-parsed atomic task defined in XML. It handles parameter substitution and invokes the appropriate Handler for LLM interaction or tool execution.

*(Note: This component does *not* handle S-expression evaluation, task composition, or template lookup. Those are managed by the SexpEvaluator and TaskSystem respectively.)*

## Core Responsibilities

1.  **Atomic Task Execution:** Executes the core logic defined within an atomic task's XML definition.
2.  **Parameter Substitution:** Performs `{{parameter_name}}` substitution within prompts/descriptions using only the explicitly passed parameters.
3.  **Handler Invocation:** Constructs the final payload and invokes the appropriate Handler method (e.g., `executePrompt`) for the LLM call.
4.  **Output Handling:** May perform basic output parsing or validation based on the atomic task's `<output_format>` specification.

## AtomicTaskExecutor Visualization

### Parameter Substitution Process
The following diagram illustrates how `{{variable_name}}` substitution works when an *atomic task* is executed:

```mermaid
flowchart TD
    A[TaskSystem calls AtomicTaskExecutor.execute_body] --> B(Receive Parsed Atomic Task Def & Parameter Dictionary)
    B --> C[Substitute {{params}} in Template Body using ONLY provided Params Dict]
    C --> D[Pass Resolved Content to Handler]
    D --> E[Handler Executes LLM/Tool]
    E --> F[Return TaskResult]

    classDef process fill:#bbf,stroke:#333
    classDef external fill:#bfb,stroke:#333

    class B,C,D process
    class E external
```
The AtomicTaskExecutor receives a flat dictionary of parameters and uses only those for substitution.

### Execution Context (Simplified)
The execution context for the AtomicTaskExecutor is simple:

```mermaid
graph TD
    Params[Parameter Bindings (Dictionary)]

    classDef params fill:#f96,stroke:#333
    class Params params
```
It does not involve nested environments or lexical scoping lookup.

## Key Interfaces

For detailed interface specifications, see:
- [Interface:AtomicTaskExecutor:1.0] in `src/atomic_executor/atomic_executor_IDL.md` (formerly evaluator IDL)

## Integration Points

- **Task System**: Instantiates and calls the AtomicTaskExecutor (`execute_body`) to run the core logic of an atomic task. Provides the parsed task definition and parameter dictionary.
- **Handler**: Invoked by the AtomicTaskExecutor to perform the actual LLM interaction or tool execution. Receives the fully resolved prompts and context.

For system-wide contracts, see [Contract:Integration:EvaluatorTask:1.0] in `/system/contracts/interfaces.md` (Note: This contract name might need updating if it specifically refers to the old Evaluator role).
