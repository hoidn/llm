# Memory System Interfaces [Interface:Memory:3.0]

> This document is the authoritative source for the Memory System public API.

## Overview

The Memory System provides metadata management and associative matching services for task execution. It follows a read-only context model with no direct file operations.

**IMPORTANT: The Memory System manages ONLY metadata about files (paths and descriptive strings).
It does NOT perform any file I/O operations - all file reading, writing, and deletion
is handled exclusively by Handler tools.**

**NOTE: As of version 3.0, the Memory System follows a read-only context model.
The updateContext method has been removed to enforce better architectural boundaries.**

## Interface Methods

```typescript
/**
 * Memory System Interface [Interface:Memory:3.0]
 */
interface MemorySystem {
    /**
     * Get global file metadata index
     * @returns Promise resolving to the global index
     */
    getGlobalIndex(): Promise<GlobalIndex>;
    
    /**
     * Update global file metadata index
     * @param index New index to set
     * @returns Promise resolving when update is complete
     */
    updateGlobalIndex(index: GlobalIndex): Promise<void>;
    
    /**
     * Index a git repository and update the global index
     * 
     * @param repoPath - Path to the git repository
     * @param options - Optional indexing configuration
     * @returns Promise resolving when indexing is complete
     */
    indexGitRepository(repoPath: string, options?: GitIndexingOptions): Promise<void>;
    
    /**
     * Get relevant context for a task
     * 
     * The Memory System does NOT perform ranking or prioritization of matches.
     * It only provides associative matching based on the input structure.
     * It does NOT read file contents - it only returns file paths and metadata.
     *
     * @param input - The ContextGenerationInput containing task context
     * @returns Promise resolving to associative match result
     * @throws {INVALID_INPUT} If the input structure is malformed or missing required fields
     */
    getRelevantContextFor(input: ContextGenerationInput): Promise<AssociativeMatchResult>;
}
```

## Integration Points

- **Handler**: Uses file paths from AssociativeMatchResult to read files via tools
- **Task System**: Uses Memory System for context retrieval during task execution
- **Evaluator**: Coordinates context retrieval for task execution

## Type References

For Memory System specific types, see [Type:Memory:3.0] in `/components/memory/spec/types.md`.
For system-wide types, see [Type:System:1.0] in `/system/contracts/types.md`.

## Contract References

For integration contract details, see [Contract:Integration:TaskMemory:3.0] in `/system/contracts/interfaces.md`.
