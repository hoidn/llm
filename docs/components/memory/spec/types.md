# Memory System Types [Type:Memory:3.0]

> This document is the authoritative source for Memory System specific types.

```typescript
/**
 * Represents metadata associated with a file
 * Stored as an unstructured string for flexibility
 * [Type:Memory:FileMetadata:3.0]
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
 * [Type:Memory:GlobalIndex:3.0]
 */
type GlobalIndex = Map<string, FileMetadata>;

/**
 * Represents a relevant file match from associative matching
 * - First element: Absolute file path
 * - Second element: Optional metadata string providing context for this specific match
 * [Type:Memory:FileMatch:3.0]
 */
type FileMatch = [string, string | undefined];

/**
 * The complete result of associative matching
 * [Type:Memory:AssociativeMatchResult:3.0]
 */
interface AssociativeMatchResult {
    /**
     * Unstructured data context relevant to the current task
     */
    context: string;
    
    /**
     * List of potentially relevant files with optional per-file context
     */
    matches: FileMatch[];
}

/**
 * Input structure for Memory System context requests.
 * Can be called with template context or a direct query.
 * [Type:Memory:ContextGenerationInput:4.0] // Version bumped due to change
 */
interface ContextGenerationInput {
    /** Optional: Template description */
    templateDescription?: string;
    /** Optional: Template type */
    templateType?: string;
    /** Optional: Template subtype */
    templateSubtype?: string;

    /** Optional: Explicit query string (used by Sexp get_context) */
    query?: string;

    /** Optional: Inputs to the task/template */
    inputs?: Record<string, any>;

    /** Optional: Context inherited from parent */
    inheritedContext?: string;
    /** Optional: String summarizing accumulated outputs */
    previousOutputs?: string;
}

/**
 * Git repository indexing options
 * [Type:Memory:GitIndexingOptions:3.0]
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

## Key Characteristics

### GlobalIndex
- Keys are absolute file paths
- Values are unstructured metadata strings
- No hierarchical organization
- Updated in bulk operations only

### AssociativeMatchResult
- Contains unstructured context data relevant to the current task
- Includes list of potentially relevant files with optional per-file context
- Does not include file contents, only paths and metadata

## Cross-References

For system-wide types, see [Type:System:1.0] in `/system/contracts/types.md`.
