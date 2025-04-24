# Task System Behaviors

This document describes the runtime behaviors of the Task System.

## Overview

The Task System is responsible for managing LLM task execution, including:
 - Template matching and management,
 - Lifecycle handling for Handlers,
 - XML processing with graceful degradation, and
 - Error detection and recovery.

## Core Behaviors

### Template Management (Atomic Tasks)
- Atomic task templates are defined in XML, stored, and validated against the schema in [Contract:Tasks:TemplateSchema:1.0].
- The system matches natural language descriptions (e.g., from `SubtaskRequest` or S-expression `call-atomic-task`) to candidate *atomic* task templates using associative matching and scoring.
- Only atomic task templates participate in this template matching process. Composite workflows are defined explicitly in S-expressions.
- Templates are validated against the XML schema during loading.

### Template Variable Substitution
- The Evaluator is solely responsible for all template variable substitution.
- This includes resolving all {{variable_name}} placeholders before passing tasks to Handlers.
- Different resolution rules apply for function templates vs. standard templates.
- Variable resolution errors are detected early and handled at the Evaluator level.

### Handler Lifecycle (for Atomic Tasks)
- A new Handler is created for each *atomic task execution* (invoked via `execute_subtask_directly`) with an immutable configuration.
- The Handler enforces resource limits (turn counts, context window limits) for that specific atomic task execution, as described in [Pattern:ResourceManagement:1.0].
- Handlers receive fully resolved content (template variables substituted) for the atomic task body.
- Each Handler maintains its own session with isolated resource tracking for the duration of the atomic task.

### XML Processing (Atomic Tasks)
- XML definitions for atomic tasks are parsed and validated against the schema.
- Warnings may be generated for non-critical issues.
- Parsing failures result in errors during template loading.
- Flags like `manual_xml` and `disable_reparsing` control Handler behavior for the atomic task.
- Output format validation (`output_format` element) is performed on the result of the atomic task execution.

## Task Execution

### Atomic Task Execution
- The Task System executes atomic tasks via the `execute_subtask_directly` method, typically called by the S-expression evaluator.
- It finds the appropriate atomic template, resolves inputs using the provided environment, prepares context based on `<context_management>` settings, and invokes a Handler.
- Returns a `TaskResult` (containing `content`, `status`, `notes`) or throws a `TaskError`.
- Handles resource exhaustion errors signaled by the Handler.

### S-expression Workflow Execution
- Workflows involving multiple steps, conditionals, loops, or mapping are defined using the S-expression DSL.
- These are invoked via a dedicated entry point (e.g., triggered by a `/task` command containing S-expressions).
- An S-expression Evaluator component parses and executes the DSL.
- The S-expression Evaluator calls `TaskSystem.execute_subtask_directly` to run the atomic task steps within the workflow.
- It manages the execution flow, variable bindings, and error handling for the workflow logic.

### Output Format Handling
- Format declaration via `<output_format>` element with required `type` attribute
- Supported format types:
  * "json" - Structured JSON data
  * "text" - Plain text (default)
- Optional `schema` attribute for type validation:
  * "object" - JSON object
  * "array" or "[]" - JSON array
  * "string[]" - Array of strings
  * "number" - Validates as numeric value
  * "boolean" - Validates as boolean value
- Automatic JSON detection:
  * Attempts to parse content as JSON when type="json"
  * Adds parsed content to TaskResult as parsedContent property
  * Falls back to original string content if parsing fails
  * Records parse errors in notes.parseError when applicable
- Type validation process (initial implementation):
  * Basic type checking against schema attribute (e.g., "object", "array")
  * Simple error structure for type mismatches with error_type, message, and location
  * Preserves original content in error details
  * More comprehensive schema validation may be implemented in future phases

## Error Handling

### Error Detection
- Resource exhaustion detection (turns, context, output)
- XML parsing and validation errors
- Output format validation errors
- Task execution failures
- Progress monitoring

### Error Response
- Standard error type system with TaskError interface
- Detailed error information with reason codes
- Partial results preservation according to task type
- Clear error messages and locations
- Resource usage metrics in error responses

### Recovery Delegation
- No automatic retry attempts
- Delegates recovery to Evaluator
- Provides complete error context
- Includes notes for recovery guidance

## Context Management

### Context Management Behaviors (for Atomic Tasks)
- Context for atomic task execution is determined by the `<context_management>` settings in its XML template or overridden by the `SubtaskRequest`.
- Follows the hybrid configuration approach: explicit settings override defaults based on the atomic task's `subtype`.
- Uses the three-dimensional model (inherit_context, accumulate_data, fresh_context).
- Supports explicit file inclusion via `<file_paths>` or `file_paths` in `SubtaskRequest`.
- Default settings per atomic task subtype (refer to table in `protocols.md`):
    * `standard`: inherit=full, fresh=disabled
    * `subtask`: inherit=subset, fresh=enabled
    * `director`/`evaluator`: inherit=full, fresh=disabled
    * `aider_*`: inherit=subset, fresh=enabled
- The mutual exclusivity constraint between `fresh_context` and `inherit_context` is enforced.

### File Operations
- Memory System: Manages ONLY metadata (file paths and descriptive strings)
- Handler: Performs ALL file I/O operations (reading, writing, deletion)
- For Anthropic models: Handler configures computer use tools
- All file content access is always handled by the Handler, never the Memory System

## Programmatic Task Invocation (Atomic Tasks)

The Task System supports direct invocation of registered *atomic* task templates, primarily used by the S-expression evaluator.

*   **Invocation:** Uses the `execute_subtask_directly(request, env)` method.
*   **Input:** Takes a `SubtaskRequest` object defining the target *atomic* task (type must be 'atomic', subtype, description, inputs, optional context overrides, file_paths).
*   **Execution:** Finds the corresponding *atomic* template based on the request's description/subtype. It then prepares context, resolves inputs using the provided S-expression environment (`env`), and executes the atomic task using a Handler. It does *not* execute a complex workflow itself.
*   **Context Determination:** Context for the atomic task execution is determined based on the effective context settings (request overrides merged with template definition) with the following precedence:
    1.  Files specified in `request.file_paths` (if provided).
    2.  Files specified via the matched template's `file_paths` / `file_paths_source` definition.
    3.  Automatic context lookup via `MemorySystem.get_relevant_context_for` if the effective `context_management.fresh_context` setting is `enabled`. The query basis for this lookup uses the `request.description` or relevant inputs.
*   **History Integration:** If the S-expression workflow needs to include history in the context lookup for an atomic task, it should construct the `ContextGenerationInput` appropriately when calling a context-fetching primitive (e.g., `(get-context ...)`), potentially passing history from its own environment. The `execute_subtask_directly` method itself doesn't automatically inject history unless it's part of the context determined by the steps above.

## Integration Behaviors

### Memory System Integration (for Atomic Tasks)
- Context for atomic tasks is accessed via `MemorySystem.getRelevantContextFor` when `fresh_context` is enabled.
- File metadata might be accessed via `MemorySystem.getGlobalIndex` if needed by specific tasks or context generation logic.
- Context preparation (clearing, inheriting, generating fresh) for an atomic task is handled based on its effective `context_management` settings before execution.

### Tool Interface
- Unified tool system with consistent patterns
- Direct tools: Handler-managed operations with fixed APIs
- Subtask tools: LLM-to-LLM interactions via CONTINUATION
- Script execution: External command execution with input/output capture
- User input: Standardized tool for interactive input requests

### Subtask Spawning
- Request validation with type, description, and inputs
- Context management with defaults or explicit configuration
- Depth control to prevent infinite recursion (default: 5 levels)
- Error handling with standardized error structures
- Direct parameter passing for clear data flow

## Related Documentation

For implementation details, see:
- [Design Implementation](../impl/design.md)
- [Resource Management Implementation](../impl/resource-management.md)
- [XML Processing Implementation](../impl/xml-processing.md)
- [Implementation Examples](../impl/examples/)
