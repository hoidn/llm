# Shared Data Structures (IDL)

This file defines common data structures used across multiple components in the system. These structures are referenced by various IDL files and should be implemented as Pydantic models in `src/system/types.py`.

```idl
// Core result type returned by many system operations
struct TaskResult {
    status: string;  // One of: "COMPLETE", "FAILED", "PENDING", "ERROR", "PARTIAL", "SUCCESS"
    content: optional string;  // Main result content or error message
    notes: optional dict<string, Any>;  // Additional metadata about the result
    files_modified: optional list<string>;  // List of files modified during the operation
    changes: optional list<dict<string, string>>;  // Detailed changes made to files
    error: optional string;  // Detailed error information if status is error/failed
}

// Input structure for context generation
struct ContextGenerationInput {
    query: string;  // The user query or task description
    template_id: optional string;  // Optional template identifier to use for context generation
    file_paths: optional list<string>;  // Specific file paths to include in context
    max_tokens: optional int;  // Maximum tokens to include in context
    additional_context: optional string;  // Any additional context to include
    
    // Method to get a value by key with optional default
    // This is a conceptual method that would be implemented in the Pydantic model
    Any get(string key, optional Any default);
}

// Result of associative matching operations
struct AssociativeMatchResult {
    context_summary: string;  // Summarized context information
    matches: list<MatchTuple>;  // List of matching items with relevance scores
    error: optional string;  // Error message if the matching operation failed
}

// Individual match result with relevance information
struct MatchTuple {
    path: string;  // Path to the matched item (e.g., file path)
    relevance: float;  // Relevance score (0.0 to 1.0)
    excerpt: optional string;  // Optional excerpt from the matched content
}
```

## Implementation Notes

These structures should be implemented as Pydantic models in `src/system/types.py`. When implementing:

1. Use appropriate Python types that correspond to the IDL types
2. Include proper type hints and docstrings
3. Add any necessary validation logic
4. Consider adding helper methods where appropriate (e.g., for the `get()` method in ContextGenerationInput)

Example implementation for TaskResult:

```python
from pydantic import BaseModel
from typing import Optional, Dict, List, Any

class TaskResult(BaseModel):
    """Result of a task execution.
    
    This model represents the standardized result format returned by task executors,
    handlers, and other components that perform operations.
    """
    status: str  # One of: "COMPLETE", "FAILED", "PENDING", "ERROR", "PARTIAL", "SUCCESS"
    content: Optional[str] = None  # Main result content or error message
    notes: Optional[Dict[str, Any]] = None  # Additional metadata about the result
    files_modified: Optional[List[str]] = None  # List of files modified during the operation
    changes: Optional[List[Dict[str, str]]] = None  # Detailed changes made to files
    error: Optional[str] = None  # Detailed error information if status is error/failed
```
