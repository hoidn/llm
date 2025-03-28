# Task System Behaviors

This document describes the runtime behaviors of the Task System.

## Overview

The Task System is responsible for managing LLM task execution, including:
 - Template matching and management,
 - Lifecycle handling for Handlers,
 - XML processing with graceful degradation, and
 - Error detection and recovery.

## Core Behaviors

### Template Management
- Task templates are stored and validated against the XML schema defined in [Contract:Tasks:TemplateSchema:1.0].
- The system matches both natural language inputs and AST nodes to candidate templates (up to 5 candidates), using numeric scoring.
- Templates can define any task type, but only atomic task templates participate in the template matching process.
- Each template is validated against the XML schema with warnings for non-critical issues.

### Template Variable Substitution
- The Evaluator is solely responsible for all template variable substitution.
- This includes resolving all {{variable_name}} placeholders before passing tasks to Handlers.
- Different resolution rules apply for function templates vs. standard templates.
- Variable resolution errors are detected early and handled at the Evaluator level.

### Handler Lifecycle
- A new Handler is created for each task execution with an immutable configuration.
- The Handler enforces resource limits (turn counts, context window limits) as described in [Pattern:ResourceManagement:1.0].
- Handlers receive fully resolved content with no remaining template variables.
- Each Handler maintains its own session with isolated resource tracking.

### XML Processing
- Basic structural validation is performed, with warnings generated for non‑critical issues.
- In cases of partial XML parsing failure, the original content is preserved and error details are included in the task notes.
- The system supports manual XML tasks with the `isManualXML` flag.
- Output format validation is performed when the `output_format` element is present.

## Task Execution

### Standard Task Execution
- Process tasks using appropriate templates
- Return both output and notes sections in TaskResult structure
- Surface errors for task failure or resource exhaustion
- Support specialized execution paths for reparsing and memory tasks
- Implement lenient XML output parsing with fallback to single string
- Generate warnings for malformed XML without blocking execution
- Include 'data usage' section in task notes as specified by system prompt

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
- Type validation process:
  * Validates parsed content against schema attribute
  * Generates error if type mismatch occurs
  * Preserves original content in error details

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

### Context Management Behaviors
- Hybrid configuration approach with operator-specific defaults
- Three-dimensional model with inherit_context, accumulate_data, and fresh_context
- Explicit file selection via file_paths element
- Operator-specific default settings:
  * atomic: inherit_context="full", fresh_context="disabled"
  * sequential: inherit_context="full", accumulate_data="true", fresh_context="disabled"
  * reduce: inherit_context="none", accumulate_data="true", fresh_context="enabled"
  * script: inherit_context="full", accumulate_data="false", fresh_context="disabled"
  * director_evaluator_loop: inherit_context="none", accumulate_data="true", fresh_context="enabled"
- Subtask defaults: inherit_context="subset", fresh_context="enabled"

### File Operations
- Memory System: Manages ONLY metadata (file paths and descriptive strings)
- Handler: Performs ALL file I/O operations (reading, writing, deletion)
- For Anthropic models: Handler configures computer use tools
- All file content access is always handled by the Handler, never the Memory System

## Integration Behaviors

### Memory System Integration
- Context accessed via async getRelevantContextFor
- File metadata accessed via GlobalIndex
- Existing context preserved during task execution
- Structure/parsing handled by associative memory tasks
- Context clearing and regeneration handled through context_management settings

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
