# AtomicTaskExecutor Component [Component:AtomicExecutor:1.0]

## Overview

The AtomicTaskExecutor is responsible **only** for executing the body of a single, pre-parsed atomic task defined in XML. It handles parameter substitution using explicitly passed values and invokes the appropriate Handler for LLM interaction or tool execution.

*(Note: This component does **not** handle S-expression evaluation, task composition, complex environment management, or template lookup. Those are managed by the SexpEvaluator and TaskSystem respectively.)*

## Core Responsibilities

1.  **Atomic Task Body Execution:** Executes the core logic defined within an atomic task's XML definition (e.g., prompts, system messages).
2.  **Parameter Substitution:** Performs `{{parameter_name}}` substitution within the task body using **only** the explicitly passed `params` dictionary.
3.  **Handler Invocation:** Constructs the final payload (e.g., `HandlerPayload`) using the resolved task body and context provided by the `TaskSystem`, then invokes the appropriate Handler method (e.g., `executePrompt`).
4.  **Output Handling:** Returns the `TaskResult` received from the Handler back to the `TaskSystem`. May perform basic output parsing/validation based on the atomic task's `<output_format>` specification if integrated here (or confirm if this is done by TaskSystem *after* execution).

## Key Interfaces

For detailed interface specifications, see:
- [Interface:AtomicTaskExecutor:1.0] in `atomic_executor/api/interfaces.md` (or corresponding IDL file).

## Integration Points

- **Task System**: Instantiates and calls the AtomicTaskExecutor (`execute_body`) to run the core logic of an atomic task. Provides the parsed task definition and parameter dictionary.
- **Handler**: Invoked by the AtomicTaskExecutor to perform the actual LLM interaction or tool execution. Receives the fully resolved prompts and context.

## Architectural Note

This component represents a significant simplification from previous "Evaluator" concepts. Its sole focus is the execution of a single atomic task's resolved body, separating it cleanly from workflow orchestration (SexpEvaluator) and task/template management (TaskSystem).
# AtomicTaskExecutor Component [Component:AtomicExecutor:1.0]

## Overview

The AtomicTaskExecutor is responsible **only** for executing the body of a single, pre-parsed atomic task defined in XML. It handles parameter substitution using explicitly passed values and invokes the appropriate Handler for LLM interaction or tool execution.

*(Note: This component does **not** handle S-expression evaluation, task composition, complex environment management, or template lookup. Those are managed by the SexpEvaluator and TaskSystem respectively.)*

## Core Responsibilities

1.  **Atomic Task Body Execution:** Executes the core logic defined within an atomic task's XML definition (e.g., prompts, system messages).
2.  **Parameter Substitution:** Performs `{{parameter_name}}` substitution within the task body using **only** the explicitly passed `params` dictionary received from the TaskSystem.
3.  **Handler Invocation:** Constructs the final payload (e.g., `HandlerPayload`) using the resolved task body and context provided by the `TaskSystem`, then invokes the appropriate Handler method (e.g., `executePrompt`).
4.  **Output Handling:** Returns the `TaskResult` received from the Handler back to the `TaskSystem`. May perform basic output parsing/validation based on the atomic task's `<output_format>` specification (Responsibility TBD: Could be TaskSystem post-execution).

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
- [Interface:AtomicTaskExecutor:1.0] in `atomic_executor/api/interfaces.md` (or corresponding IDL file `src/executors/atomic_executor_IDL.md`).

## Integration Points

- **Task System**: Instantiates and calls the AtomicTaskExecutor (`execute_body`) to run the core logic of an atomic task. Provides the parsed task definition and parameter dictionary.
- **Handler**: Invoked by the AtomicTaskExecutor to perform the actual LLM interaction or tool execution. Receives the fully resolved prompts and context.

## Architectural Note

This component represents a significant simplification from previous "Evaluator" concepts. Its sole focus is the execution of a single atomic task's resolved body, separating it cleanly from workflow orchestration (SexpEvaluator) and task/template management (TaskSystem).
