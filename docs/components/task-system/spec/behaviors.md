# Task System Behaviors

This document describes the runtime behaviors of the Task System.

## Overview

The Task System manages atomic task definitions (XML) and orchestrates the setup for their execution when requested by components like the SexpEvaluator.

## Core Behaviors

### Atomic Template Management
- **Registration (`register_template`):** Validates atomic task XML against the schema ([Contract:Tasks:TemplateSchema:1.0]) and stores valid definitions, indexed by name and type/subtype. Ensures parameter declarations are present.
- **Lookup (`find_template`):** Retrieves atomic task definitions by name or type/subtype.
- **Matching (`find_matching_tasks`):** Finds relevant atomic task templates based on natural language input using similarity scoring (e.g., for user query routing).

### Atomic Task Execution Orchestration (`execute_atomic_template`)
- **Invocation:** Called by `SexpEvaluator` (or potentially Dispatcher) with a `SubtaskRequest` containing resolved inputs, file paths, and context overrides. **Does not receive or use an `SexpEnvironment`.**
- **Setup:**
    - Finds the specified atomic template.
    - Determines final context settings (merging request/template overrides with defaults).
    - Fetches fresh context via `MemorySystem` if required by settings.
    - Prepares the parameter dictionary (`params`) directly from `request.inputs`.
    - Instantiates/configures a `Handler` with appropriate resource limits.
    - Instantiates the `AtomicTaskExecutor`.
- **Delegation:** Calls `AtomicTaskExecutor.execute_body(template_def, params, handler)`.
- **Result Handling:** Receives `TaskResult`/`TaskError` from the executor, adds metadata (template used, context source), and returns it to the caller (`SexpEvaluator`).

### Handler Lifecycle Coordination (for Atomic Tasks)
- The Task System ensures a properly configured `Handler` instance (potentially cached or newly created) is provided to the `AtomicTaskExecutor` for each `execute_atomic_template` call.
- It sets the resource limits on the Handler based on the specific atomic task being executed.

### XML Processing (Atomic Tasks)
- **During Registration:** Parses and validates atomic task XML definitions against the schema. Errors prevent registration.
- **During Execution Setup:** Uses the *parsed* template definition when calling `AtomicTaskExecutor`. Flags like `manual_xml` or `disable_reparsing` are part of the definition passed to the executor/handler.
- **Output Format Validation:** The responsibility for validating the final output against `<output_format>` might lie with the TaskSystem *after* `execute_body` returns, or potentially within the `AtomicTaskExecutor` itself (TBD).

### S-expression Workflow Execution (Not TaskSystem)
- Workflows are executed by the **SexpEvaluator**.
- The SexpEvaluator calls `TaskSystem.execute_atomic_template` to run individual atomic steps.
- TaskSystem is *not* responsible for managing S-expression control flow, environments, or error recovery *within* the workflow.

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

### Error Detection & Propagation
- **Setup Errors:** Detects errors during `execute_atomic_template` setup (e.g., template not found, context retrieval failure from MemorySystem) and returns a `TaskError`.
- **Execution Errors:** Receives `TaskError` (e.g., `RESOURCE_EXHAUSTION`, `TASK_FAILURE` from Handler/Tool) propagated from `AtomicTaskExecutor`.
- **Propagation:** Forwards received/generated `TaskError` objects to the caller (`SexpEvaluator`).

### Recovery Delegation
- The Task System itself does **not** implement retry or complex recovery logic for failed atomic tasks.
- It provides the complete `TaskError` context to the calling `SexpEvaluator`, which is responsible for handling recovery within the S-expression workflow if desired.

## Context Management

### Context Management Orchestration (for Atomic Tasks)
- **Determines Settings:** Calculates the final effective context management settings for an atomic task by merging `SubtaskRequest` overrides, template definitions, and subtype defaults (request > template > defaults).
- **Enforces Constraints:** Validates the final settings (e.g., mutual exclusivity of `fresh_context` and `inherit_context`).
- **Fetches Context:** Calls `MemorySystem.getRelevantContextFor` if `fresh_context` is enabled.
- **Prepares Context:** Assembles the context information (summary, file paths) to be passed via the `AtomicTaskExecutor` to the `Handler`. (Actual file reading is done by Handler).
- **File Path Precedence:** Uses `request.file_paths` if provided, otherwise uses template `<file_paths>`.

### File Operations
- Memory System: Manages ONLY metadata (file paths and descriptive strings)
- Handler: Performs ALL file I/O operations (reading, writing, deletion)
- For Anthropic models: Handler configures computer use tools
- All file content access is always handled by the Handler, never the Memory System

## Programmatic Atomic Task Invocation (`execute_atomic_template`)

This method defines the Task System's runtime interface for executing atomic tasks.

*   **Invocation:** Called by `SexpEvaluator` using `execute_atomic_template(request)`. **No `env` parameter.**
*   **Input:** `SubtaskRequest` with `type='atomic'` and **resolved** inputs, file_paths, and context_management settings.
*   **Execution:** Orchestrates the setup (template lookup, context prep, Handler config) and delegates body execution to `AtomicTaskExecutor`.
*   **Parameter Handling:** Uses `request.inputs` directly as the parameter dictionary for `AtomicTaskExecutor`. No substitution occurs here.
*   **Context Determination:** Follows the precedence rules: request overrides > template settings > defaults. Calls MemorySystem if `fresh_context` is enabled.
*   **History Integration:** History is not automatically included by `execute_atomic_template`. If history is needed for context lookup (`MemorySystem.getRelevantContextFor`), the caller (`SexpEvaluator`) must include it when constructing the `ContextGenerationInput` (likely via an S-expression primitive like `get-context`).

## Integration Behaviors

### Memory System Integration
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
