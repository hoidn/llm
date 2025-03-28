# Memory System 3.0 Consolidation Specification
> Ingest the information from this file, implement the Low-Level Tasks, and generate the code that will satisfy the High and Mid-Level Objectives.

## High-Level Objective

- Standardize Memory System references to version 3.0 throughout the codebase and documentation

## Mid-Level Objectives

- Update all documentation to consistently reference Memory System 3.0
- Ensure clear definition of interface boundaries between Memory System and Handler tools
- Standardize type definitions across all components
- Remove or update references to deprecated methods (particularly `updateContext`)

## Implementation Notes
- Focus on documentation updates rather than code changes
- Metadata format should remain unspecified to provide implementation flexibility
- Take a light approach to validation, focusing on basic type checking
- Maintain the read-only context model established in ADR-003
- Ensure clear separation between metadata management (Memory System) and file operations (Handler tools)

## Context

### Beginning context
- Documentation contains inconsistent references to Memory System 2.0 and 3.0
- Some documents reference deprecated methods like `updateContext` and `getContext`
- Unclear boundaries between Memory System and Handler responsibilities in some documents
- Inconsistent definitions of core types across components

### Ending context  
- All documentation consistently references Memory System 3.0
- Clear boundary definition between Memory System (metadata) and Handler (file operations)
- Standardized type definitions across all components
- No references to deprecated methods
- Updated architecture documentation reflecting the read-only context model

## Low-Level Tasks
> Ordered from start to finish

1. Create consolidated Memory System 3.0 reference document
```aider
Create a new reference document components/memory/REFERENCE.md that:
- Defines the canonical Memory System 3.0 interface
- Lists all standard type definitions (GlobalIndex, FileMetadata, FileMatch, etc.)
- Clearly states the read-only context model
- Defines the responsibility boundary between Memory System and Handler tools
- Documents the removal of updateContext capability
- Serves as the single source of truth for interface definitions
```

2. Update Task System documentation with consistent references
```aider
Update the following Task System documents to reference Memory System 3.0 consistently:
- components/task-system/spec/interfaces.md
- components/task-system/spec/behaviors.md
- components/task-system/impl/design.md

Remove any references to:
- updateContext method
- getContext method
- Memory System 2.0
- Any context persistence capabilities

Update type imports and interface references to match the canonical definitions.
```

3. Update architecture documentation with consistent references
```aider
Update the following architecture documents:
- system/architecture/overview.md
- system/architecture/decisions/001-memory-system-qa.md
- system/architecture/decisions/needs_update/001-memory-system.md

Ensure all references use Memory System 3.0 terminology.
Clarify that Memory System maintains a read-only approach to context.
Update any diagrams or flowcharts to reflect current architecture.
```

4. Update system contracts with consistent references
```aider
Update the following system contract documents:
- system/contracts/interfaces.md
- system/contracts/resources.md

Ensure [Contract:Integration:TaskMemory:3.0] is consistently referenced.
Verify interface definitions match the canonical reference.
Update any examples to reflect current architecture.
```

5. Create migration guidance document
```aider
Create a new document system/architecture/migrations/memory-system-2-to-3.md that:
- Summarizes changes from Memory System 2.0 to 3.0
- Provides guidance for updating code that used updateContext
- Explains the new read-only context model
- References ADR-003 for the architectural decision rationale
- Includes examples of proper Memory System 3.0 usage
```
