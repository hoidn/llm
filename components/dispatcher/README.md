# Dispatcher Component [Component:Dispatcher:1.0]

## Overview

The Dispatcher component routes programmatic task requests to the appropriate executor based on the task identifier. It serves as the central routing mechanism for the `/task` command, determining whether to execute a task via a direct tool or a template-based subtask.

## Core Responsibilities

1. **Request Routing**
   - Determine the appropriate executor for a task identifier
   - Route requests to either direct tools or template-based subtasks
   - Enforce precedence rules when identifiers exist in multiple registries

2. **Parameter Processing**
   - Parse and validate task parameters
   - Handle JSON string conversion for complex parameters
   - Process command flags (e.g., `--use-history`)

3. **Context Management**
   - Determine file context based on precedence rules
   - Coordinate with MemorySystem for automatic context lookup
   - Handle history context when `--use-history` flag is present

4. **Error Handling**
   - Catch and format errors from various execution paths
   - Provide consistent error reporting in TaskResult format
   - Log detailed error information for debugging

## Execution Flow

```mermaid
flowchart TD
    A[Receive Task Request] --> B{Identifier in\nHandler Tools?}
    B -->|Yes| C{Identifier in\nTaskSystem Templates?}
    B -->|No| D{Identifier in\nTaskSystem Templates?}
    C -->|Yes| E[Use Template\n(Templates take precedence)]
    C -->|No| F[Use Direct Tool]
    D -->|Yes| E
    D -->|No| G[Return Not Found Error]
    E --> H[Execute via TaskSystem]
    F --> I[Execute via Handler]
    H --> J[Return TaskResult]
    I --> J
    G --> J
```

## Context Determination

The Dispatcher follows a strict precedence order for determining file context:

1. **Explicit Context**: If `file_context` parameter is provided in the request
2. **Template Context**: If the template has `file_paths` defined
3. **Automatic Context**: If fresh context is enabled, query MemorySystem

This precedence ensures that explicit user choices always override automatic behavior.

## Integration Points

- **REPL**: Receives task requests via the `/task` command
- **Handler**: Executes direct tools
- **TaskSystem**: Executes template-based subtasks
- **MemorySystem**: Provides automatic context lookup

## Usage

The Dispatcher is used primarily through the `execute_programmatic_task` function:

```python
def execute_programmatic_task(
    identifier: str,
    params: Dict[str, Any],
    flags: Dict[str, bool],
    handler_instance: BaseHandler,
    task_system_instance: TaskSystem,
    optional_history_str: Optional[str] = None
) -> TaskResult:
    """Routes a programmatic task request to the appropriate executor."""
```

This function is called by the REPL's `/task` command handler to execute programmatic tasks.

## Error Handling

The Dispatcher provides comprehensive error handling:

- **TaskError**: Structured errors with reason codes and details
- **JSONDecodeError**: When parsing JSON parameters fails
- **Unexpected Exceptions**: Caught and formatted as TaskError

All errors are returned in a consistent TaskResult format with appropriate status and notes.
