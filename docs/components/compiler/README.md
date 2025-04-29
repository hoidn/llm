# Compiler Component [Component:Compiler:1.0]

## Overview

The Compiler handles AST generation and transformation for task execution. It provides the infrastructure for parsing and processing task specifications.

## Core Responsibilities

1. **AST Generation**
   - Parse XML task specifications
   - Generate abstract syntax trees
   - Validate syntax and structure

2. **Transformation**
   - Transform ASTs for execution
   - Apply optimizations
   - Handle error recovery

3. **Operator Management**
   - Register and manage operators
   - Handle operator dependencies
   - Provide operator documentation

## Compiler Visualization

### Compilation Pipeline
The following diagram shows the compilation process:

```mermaid
flowchart LR
    A[Natural Language] --> B[Parse]
    B --> C[Validate]
    C --> D[Transform]
    D --> E[AST Generation]
    
    style A fill:#f9f,stroke:#333
    style E fill:#bfb,stroke:#333
```

The Compiler translates natural language inputs into structured Abstract Syntax Trees (ASTs) that can be executed by the system.

### AST Structure
This diagram illustrates the relationship between different node types:

```mermaid
graph TD
    AN[ASTNode] --> TN[TaskNode]
    AN --> FCN[FunctionCallNode]
    AN --> TPN[TemplateNode]
    TN --> ATN[AtomicTaskNode]
    TN --> STN[SequentialTaskNode]
    TN --> RTN[ReduceTaskNode]
    FCN --> ARN[ArgumentNode]
    
    classDef base fill:#f96,stroke:#333
    classDef derived fill:#bbf,stroke:#333
    classDef leaf fill:#bfb,stroke:#333
    
    class AN base
    class TN,FCN,TPN derived
    class ATN,STN,RTN,ARN leaf
```

The AST provides a structured representation of tasks that can be processed and executed by the Evaluator component.

## Key Interfaces

For detailed interface specifications, see:
- [Interface:Compiler:1.0] in `/components/compiler/api/interfaces.md`

## Integration Points

- **Task System**: Uses Compiler for task parsing
- **Evaluator**: Uses Compiler for reparse operations
- **Handler**: Used for LLM translation

For system-wide contracts, see [Contract:Integration:CompilerTask:1.0] in `/system/contracts/interfaces.md`.
# Compiler Component [Component:Compiler:1.0]

## Overview

In the current S-expression based architecture, the Compiler's primary role is **XML validation**. It ensures that *atomic task* definitions provided during registration conform to the established schema ([Contract:Tasks:TemplateSchema:1.0]).

Its previous role in generating Abstract Syntax Trees (ASTs) for workflow execution is now handled by the `SexpEvaluator` parsing S-expression strings.

## Core Responsibilities

1.  **Atomic Task XML Validation:** Validate XML structure and content against the defined schema during `TaskSystem.register_template`.
2.  **(Future Scope):** Potentially handle translation from Natural Language queries to S-expression workflows.
3.  **(Deprecated):** AST Generation for composite tasks or workflows.

## Key Interfaces

*(Review and simplify Interface:Compiler:1.0 - methods related to the old AST model are likely deprecated or need redefinition)*
For detailed interface specifications, see:
- [Interface:Compiler:1.0] in `/components/compiler/api/interfaces.md`

## Integration Points

*   **Task System**: Uses Compiler for XML schema validation during atomic task registration.
*   **(Future):** May interact with REPL/Dispatcher for NL-to-S-expression translation.
