# ADR 17: Template-Aware Context Generation

## Status
Accepted

## Context
The previous context generation mechanism relied primarily on a single string parameter (`taskText`) for associative matching. This approach limited the system's ability to leverage the rich template structure and multiple inputs that the architecture is designed to support.

## Decision
We will enhance the context generation process to be template-aware and support arbitrary inputs through an expanded `ContextGenerationInput` interface that includes template information and all task inputs.

The Memory System will use this expanded input structure to perform more relevant context matching that considers both the template metadata and all available inputs.

Additionally, we will add mechanisms for templates to specify which inputs are relevant for context matching and how they should be combined:

1. `<context_relevance>` element with boolean inclusion for each input
2. `<context_assembly>` element for guidance on combining elements for matching

## Rationale
1. **Template Relevance**: A template's description often contains the most valuable information about what files might be relevant.
2. **Multi-Input Support**: Templates can have any number of inputs of any type, all of which may contain information relevant to context matching.
3. **Comprehensive Matching**: Using both template metadata and inputs allows for more accurate context retrieval.
4. **Simplicity**: Using a boolean inclusion model for relevance provides clear guidance without introducing ambiguous levels of importance.
5. **Flexibility**: This approach supports both simple string-based queries and complex structured inputs.

## Implementation
The specific algorithm for combining template information and inputs for context matching is left as an implementation detail, allowing different Memory System implementations to optimize based on their capabilities.

However, implementations should adhere to these guidelines:
1. The template description should be a primary factor in context matching
2. All inputs marked with `include="true"` should be considered
3. Type conversions should be handled appropriately for non-string inputs
4. The implementation should respect the context management settings (inheritContext, accumulateData, freshContext)

## Consequences

### Positive
- More accurate context retrieval due to comprehensive matching
- Better support for complex templates with multiple inputs
- Improved flexibility for different types of tasks
- Future-proof design that can accommodate new template types and input formats
- Clear binary decision model for input relevance

### Negative
- Increased complexity in the Memory System implementation
- Potential performance impact from processing more complex inputs
- Requires updates to existing interfaces and templates

## Related Documents
- [Pattern:ContextFrame:1.0] in system/architecture/patterns/context-frames.md
- [Interface:Memory:3.0] in components/memory/api/interfaces.md
- [ADR 14: Operator Context Configuration] in system/architecture/decisions/14-operator-ctx-config.md
