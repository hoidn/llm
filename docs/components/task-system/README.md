# Task System Component [Component:TaskSystem:1.0]

## Overview

The Task System orchestrates LLM task execution through structured XML templates and handlers. It provides template-based task definition, resource tracking, and an XML-based interface with the LLM.

## Core Responsibilities

1. **Task Execution**
   - Process task requests
   - Manage task execution flow
   - Handle task delegation and composition

2. **Template Management**
   - Register and validate templates
   - Support function-based templates
   - Enable template matching and selection

3. **Resource Coordination**
   - Coordinate resource tracking with Handler
   - Manage subtask spawning and nesting
   - Handle context management across tasks
   - Executes specific, registered template workflows programmatically when invoked directly (e.g., via `execute_subtask_directly`).

## Process Visualization

### Task Execution Workflow
The following diagram illustrates the typical task execution flow:

```mermaid
flowchart LR
    A[Task Request] --> B[Template Selection]
    B --> C[Resource Allocation]
    C --> D[Context Resolution]
    D --> E[Handler Creation]
    E --> F[Task Execution]
    F --> G[Result Processing]
    
    style A fill:#f9f,stroke:#333
    style F fill:#bbf,stroke:#333
    style G fill:#bfb,stroke:#333
```

The Task System manages the complete lifecycle from initial request through template selection, resource allocation, and execution via the Handler. It also supports direct execution of registered workflows.

### Component Integration
The Task System interacts with other components during execution:

```mermaid
sequenceDiagram
    participant User
    participant TS as Task System
    participant MS as Memory System
    participant EV as Evaluator
    participant HD as Handler
    
    User->>TS: Execute Task
    TS->>MS: Get Relevant Context
    MS-->>TS: Return Context
    TS->>EV: Process Template
    EV->>HD: Execute with LLM
    HD-->>EV: Return Result
    EV-->>TS: Return Processed Result
    TS-->>User: Return Task Result
```

This sequence shows how the Task System coordinates between components to fulfill execution requests while maintaining clear responsibility boundaries.

## Programmatic Task Execution

The TaskSystem provides the `execute_subtask_directly` method for programmatic task execution:

```python
def execute_subtask_directly(self, request: SubtaskRequest) -> TaskResult:
    """
    Executes a Task System template workflow directly from a SubtaskRequest.

    Args:
        request: The SubtaskRequest defining the task to run.

    Returns:
        The final TaskResult of the workflow.
    """
```

This method is used by the Dispatcher to execute tasks programmatically via the `/task` command. It handles:

1. Template lookup based on the task identifier
2. Context determination (explicit, template-defined, or automatic)
3. Environment setup for task execution
4. Task execution via the appropriate handler
5. Result formatting and error handling

The context determination follows a precedence order:
1. Explicit file paths in the request
2. Template-defined file paths
3. Automatic context lookup via MemorySystem (if enabled)

For more details on programmatic task execution, see the [Programmatic Task Examples](../task_system/impl/examples/programmatic_task.md).

## Key Interfaces

For detailed interface specifications, see:
- [Interface:TaskSystem:1.0] in `/components/task-system/api/interfaces.md`
- [Type:TaskSystem:1.0] in `/components/task-system/spec/types.md`

## Integration Points

- **Memory System**: Used for context retrieval via [Interface:Memory:3.0]
- **Handler**: Used for LLM interactions and resource enforcement
- **Evaluator**: Used for task execution and error recovery
- **Compiler**: Used for task parsing and transformation
- **Dispatcher**: Used for programmatic task routing

## Architecture

The system manages task execution through isolated Handler instances, with one Handler per task to enforce resource limits and manage LLM interactions. Task definitions use an XML-based template system that supports both manual and LLM-generated structures.

For system-wide contracts, see [Contract:Integration:TaskSystem:1.0] in `/system/contracts/interfaces.md`.
