# System Overview

## Architecture

This system implements a modular architecture for AI-assisted task execution with the following key components:

*   **Dispatcher:** Routes incoming requests (e.g., `/task` command) to either `SexpEvaluator` (for S-expressions) or `Handler` (for direct tool calls).
*   **SexpEvaluator:** Parses and executes S-expression workflows, manages DSL environment/scope, calls `TaskSystem` for atomic steps, calls `Handler` for direct tools.
*   **Task System**: Manages *atomic* task definitions (XML), orchestrates atomic task execution setup (`execute_atomic_template`), interfaces with `MemorySystem`.
*   **AtomicTaskExecutor**: Executes the body of a single atomic task, performs parameter substitution using passed `params`, calls `Handler`.
*   **Handler**: Provides LLM provider integration (`pydantic-ai`), resource enforcement (per atomic task), file I/O, direct tool execution.
*   **Memory System**: Manages context metadata and retrieval (read-only).
*   **Compiler**: Validates atomic task XML schema during registration. (Role may expand for NL->S-exp).

## System Architecture Visualization

### Component Relationship Diagram
The following diagram illustrates the high-level architecture and interaction between the key components:

```mermaid
graph TD
    User((User)) --> Dispatcher
    Dispatcher -->|S-expression| SexpEvaluator
    Dispatcher -->|Direct Tool Call| Handler
    SexpEvaluator --> TaskSystem --> AtomicTaskExecutor
    SexpEvaluator --> Handler((Handler Direct Tools))
    SexpEvaluator --> Memory((Memory System Context))
    TaskSystem --> Memory
    AtomicTaskExecutor --> Handler
    Handler --> ExternalTools[File System, APIs, Shell, pydantic-ai Agent]

    subgraph Core Execution
        SexpEvaluator
        TaskSystem
        AtomicTaskExecutor
        Handler
        Memory
    end

    classDef primary fill:#f96,stroke:#333,stroke-width:2px;
    classDef component fill:#bbf,stroke:#333,stroke-width:1px;
    class SexpEvaluator,TaskSystem,AtomicTaskExecutor,Handler,Memory component;
    class Dispatcher primary;
```

This visualization shows how the Dispatcher routes requests. S-expressions go to the SexpEvaluator, which orchestrates workflows, calling the TaskSystem to set up atomic tasks. The TaskSystem invokes the AtomicTaskExecutor to run the core atomic logic, which in turn calls the Handler for LLM/tool interaction. SexpEvaluator can also call Handler tools directly or request context from Memory.

### Component Responsibility Matrix

| Component          | Primary Responsibility                     | Resource Ownership          | Key Integration Points                      |
|--------------------|--------------------------------------------|-----------------------------|---------------------------------------------|
| Dispatcher         | Request Routing (Sexp vs Direct Tool)      | -                           | SexpEvaluator, Handler                      |
| SexpEvaluator      | S-expression Workflow Execution, DSL Scope | SexpEnvironment             | TaskSystem, Handler, MemorySystem           |
| Task System        | Atomic Task Definition Mgmt, Orchestration | Atomic Templates            | SexpEvaluator, AtomicTaskExecutor, Memory   |
| AtomicTaskExecutor | Atomic Task Body Execution, Substitution   | -                           | TaskSystem, Handler                         |
| Memory System      | Context Metadata & Retrieval (Read-Only)   | Global Index                | TaskSystem, SexpEvaluator                   |
| Handler            | LLM Interaction, File I/O, Direct Tools    | Turns, Context (per task)   | AtomicTaskExecutor, Dispatcher, SexpEvaluator |
| Compiler           | Atomic Task XML Validation (Registration)  | -                           | TaskSystem                                  |

Each component has distinct responsibilities and ownership boundaries, ensuring clean separation of concerns while enabling effective coordination through well-defined interfaces.

## Documentation Map

### Authoritative Sources

#### Interfaces
*   [Interface:TaskSystem:1.0] in `/components/task-system/api/interfaces.md`
*   [Interface:Memory:3.0] in `/components/memory/api/interfaces.md`
*   [Interface:SexpEvaluator:1.0] in `/src/sexp_evaluator/sexp_evaluator_IDL.md`
*   [Interface:AtomicTaskExecutor:1.0] in `/components/atomic_executor/api/interfaces.md`
*   [Interface:BaseHandler:1.0] in `/src/handler/base_handler_IDL.md`
*   [Interface:Compiler:1.0] in `/components/compiler/api/interfaces.md` (Review relevance)

#### Types
*   [Type:System:1.0] in `/system/contracts/types.md`
*   [Type:Memory:3.0] in `/components/memory/spec/types.md` (Local types only)
*   [Type:Handler:1.0] in `/components/handler/spec/types.md` (Local types only)

#### Contracts
*   [Contract:Integration:TaskMemory:3.0] in `/system/contracts/interfaces.md`
*   [Contract:Tasks:TemplateSchema:1.0] in `/system/contracts/protocols.md` (Atomic Tasks Only)
*   [Contract:Resources:1.0] in `/system/contracts/resources.md`

#### Patterns
*   [Pattern:Error:1.0] in `/system/architecture/patterns/errors.md`
*   [Pattern:ContextFrame:1.0] in `/system/architecture/patterns/context-frames.md`
*   [Pattern:DirectorEvaluator:1.1] in `/system/architecture/patterns/director-evaluator.md` (Implemented via S-expressions)
*   [Pattern:ResourceManagement:1.0] in `/system/architecture/patterns/resource-management.md`
*   [Pattern:ToolInterface:1.0] in `/system/architecture/patterns/tool-interface.md`


Each component has distinct responsibilities and ownership boundaries, ensuring clean separation of concerns while enabling effective coordination through well-defined interfaces.

## Documentation Map

### Authoritative Sources

#### Interfaces
- [Interface:TaskSystem:1.0] in `/components/task-system/api/interfaces.md`
- [Interface:Memory:3.0] in `/components/memory/api/interfaces.md`
- [Interface:SexpEvaluator:1.0] in `/src/sexp_evaluator/sexp_evaluator_IDL.md`
- [Interface:AtomicTaskExecutor:1.0] in `/components/atomic_executor/api/interfaces.md`
- [Interface:Compiler:1.0] in `/components/compiler/api/interfaces.md` (Review relevance)

#### Types
- [Type:System:1.0] in `/system/contracts/types.md`
- [Type:TaskSystem:1.0] in `/components/task-system/spec/types.md`
- [Type:Memory:3.0] in `/components/memory/spec/types.md`
// Evaluator types removed

#### Contracts
- [Contract:Integration:TaskSystem:1.0] in `/system/contracts/interfaces.md` (Review content)
- [Contract:Integration:TaskMemory:3.0] in `/system/contracts/interfaces.md`
- [Contract:Tasks:TemplateSchema:1.0] in `/system/contracts/protocols.md`
- [Contract:Resources:1.0] in `/system/contracts/resources.md`

#### Patterns
- [Pattern:Error:1.0] in `/system/architecture/patterns/errors.md`
- [Pattern:ContextFrame:1.0] in `/system/architecture/patterns/context-frames.md`
- [Pattern:DirectorEvaluator:1.1] in `/system/architecture/patterns/director-evaluator.md`
- [Pattern:ResourceManagement:1.0] in `/system/architecture/patterns/resource-management.md`

## Component Responsibilities

Each component has well-defined responsibilities and interfaces documented in their respective README files:

- [Task System](/components/task-system/README.md) - Manages atomic task definitions and execution setup.
- [SexpEvaluator](/src/sexp_evaluator/sexp_evaluator_IDL.md) - Executes S-expression workflows.
- [AtomicTaskExecutor](/components/atomic_executor/README.md) - Executes the body of atomic tasks.
- [Handler](/components/handler/README.md) - Handles LLM interaction, tools, file I/O.
- [Memory](/components/memory/README.md) - Manages context metadata.
- [Compiler](/components/compiler/README.md) - Handles initial parsing (if applicable).

For a comprehensive documentation map with navigation paths and references, see [Documentation Guide](/system/docs-guide.md).
