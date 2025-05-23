# System Documentation
    
This document provides the main entry point to all system documentation.
    
## System Overview
    
- [System README](./system/README.md) - High-level system overview and architecture
- [Architecture Overview](./system/architecture/overview.md) - Detailed architecture description
    
## Component Documentation
    
- [Component Index](./components/index.md) - Index of all system components
- [Task System](./components/task-system/README.md) - Task execution and management
- [Memory System](./components/memory/README.md) - Context management and retrieval
- [Evaluator](./components/evaluator/README.md) - Task execution and variable resolution
- [Compiler](./components/compiler/README.md) - Natural language to structured task translation
    
## Architecture Patterns
    
- [Pattern Index](./system/architecture/patterns/index.md) - Index of all architectural patterns
- [Director-Evaluator Pattern](./system/architecture/patterns/director-evaluator.md) - Iterative refinement pattern
- [Error Handling Pattern](./system/architecture/patterns/errors.md) - Error detection and recovery
- [Context Frame Pattern](./system/architecture/patterns/context-frames.md) - Context management model
- [Resource Management Pattern](./system/architecture/patterns/resource-management.md) - Resource tracking and limits
- [Tool Interface Pattern](./system/architecture/patterns/tool-interface.md) - Unified tool interface with different implementations
    
## Architecture Decisions
    
- [ADR Index](./system/architecture/decisions/index.md) - Index of all Architecture Decision Records
    
## Contracts and Integration
    
- [System Contracts](./system/contracts/interfaces.md) - Cross-component interfaces
    - [System Protocols](./system/contracts/protocols.md) - XML schema and protocols
    - [Resource Contracts](./system/contracts/resources.md) - Resource management contracts
    - [Integration Documentation](./system/integration/index.md) - Cross-component integration
    
## Questions and Answers

- [Q&A Index](./system/qa/index.md) - Index of questions and answers
- [Architecture Questions](./system/qa/architecture-questions.md) - High-level architecture questions
- [Component FAQ](./system/qa/component-faq.md) - Component-specific questions

## Implementation

- [Implementation Plan](./system/planning/implementation-plan.md) - Consolidated implementation priorities and timeline

## Cross-Reference Standard

This documentation uses a consistent cross-reference format:

- Types: `[Type:Component:Name:Version]` (e.g., `[Type:TaskSystem:TaskResult:1.0]`)
- Interfaces: `[Interface:Component:Name:Version]` (e.g., `[Interface:Memory:3.0]`)
- Contracts: `[Contract:Category:Name:Version]` (e.g., `[Contract:Integration:TaskMemory:3.0]`)
- Patterns: `[Pattern:Name:Version]` (e.g., `[Pattern:DirectorEvaluator:1.1]`)

Each reference points to an authoritative source document where the referenced entity is defined.
