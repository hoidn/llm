# System Components [Index]

This document provides an index of all system components and their primary responsibilities.

## Component Catalog

| Component Name | Primary Responsibility | Key Interfaces | Documentation Links |
|----------------|------------------------|----------------|---------------------|
| Task System | Orchestrates task execution through structured templates | [Interface:TaskSystem:1.0](./task-system/api/interfaces.md) | [README](./task-system/README.md) |
| Evaluator | Controls AST processing and execution | [Interface:Evaluator:1.0](./evaluator/api/interfaces.md) | [README](./evaluator/README.md) |
| Memory System | Provides context management and associative matching | [Interface:Memory:3.0](./memory/api/interfaces.md) | [README](./memory/README.md) |
| Compiler | Translates natural language to XML/AST | [Interface:Compiler:1.0](./compiler/api/interfaces.md) | [README](./compiler/README.md) |
| Handler | Manages LLM interactions and resource tracking | [Interface:Handler:1.0] | - |

## Component Responsibilities

### Task System
- Coordinates task execution via Handlers
- Manages task templates and matching
- Interfaces with Memory System
- Processes XML input/output

### Evaluator
- Controls AST processing and execution
- Manages failure recovery
- Tracks resource usage
- Handles reparse/decomposition requests

### Memory System
- Maintains global file metadata index
- Provides context retrieval through associative matching
- Follows read-only context model
- Delegates file operations to Handler tools

### Compiler
- Translates natural language to XML/AST
- Validates XML against schema
- Handles task transformation
- Manages template validation

### Handler
- Performs LLM interactions
- Tracks resource usage (turns, tokens)
- Manages file I/O operations
- Provides tool interface for LLM

## Navigation

- [System Overview](../system/README.md)
- [Architecture Overview](../system/architecture/overview.md)
- [Pattern Index](../system/architecture/patterns/index.md)
- [ADR Index](../system/architecture/decisions/index.md)
