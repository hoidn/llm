# Memory System Types [Type:Memory:3.0]

> **Note:** This document defines types specific to the internal implementation or unique interfaces of the Memory System. For shared system-wide types like `AssociativeMatchResult`, `MatchTuple`, and `ContextGenerationInput`, refer to the authoritative definitions in `/docs/system/contracts/types.md`.

```typescript
/**
 * Represents metadata associated with a file
 * Stored as an unstructured string for flexibility
 * [Type:Memory:FileMetadata:Local:1.0] // Marked as local
 */
type FileMetadata = string;

/**
 * Global index mapping file paths to their metadata
 * - Keys are absolute file paths
 * - Values are unstructured metadata strings
 *
 * The Memory System is responsible only for providing file metadata.
 * All file I/O operations are delegated to Handler tools.
 * The index serves as a bootstrap mechanism for associative matching.
 * [Type:Memory:GlobalIndex:Local:1.0] // Marked as local
 */
type GlobalIndex = Map<string, FileMetadata>;

// ## Removed Types (Now Defined Centrally) ##
// AssociativeMatchResult -> Defined in /docs/system/contracts/types.md
// FileMatch -> Replaced by MatchTuple, defined in /docs/system/contracts/types.md
// ContextGenerationInput -> Defined in /docs/system/contracts/types.md

/**
 * Git repository indexing options specific to memory system's index_git_repository method.
 * [Type:Memory:GitIndexingOptions:Local:1.0] // Marked as local
 */
interface GitIndexingOptions {
  /**
   * File patterns to include (glob format)
   */
  includePatterns?: string[];

  /**
   * File patterns to exclude (glob format)
   */
  excludePatterns?: string[];

  /**
   * Maximum file size to process in bytes
   */
  maxFileSize?: number;
}
```
