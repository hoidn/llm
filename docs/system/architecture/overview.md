# Architecture Overview

## Problem Statement and Goals

### Atomic Task Matching

The system uses a uniform, heuristic approach for template matching:

- Only atomic tasks have templates; composite tasks are created by combining atomic tasks
- Template matching is performed heuristically by user-defined associative matching tasks with fixed I/O signatures
- Matching logic is uniform for MVP (no operator-specific differences or versioning)
- System always selects the highest-scoring candidate template
- Optional "disable context" flag allows tasks to run without inherited context
- Task results may include optional success score in "notes" field for future adaptive scoring

```mermaid
flowchart TD
    A[User Input] --> B[Create ContextGenerationInput]
    B --> C{Context Disabled?}
    C -->|No| D[Include inheritedContext]
    C -->|Yes| E[Omit inheritedContext]
    D --> F[Call getRelevantContextFor]
    E --> F
    F --> G[Score Candidates]
    G --> H[Select Highest Score]
```

This document provides a high‑level overview of the system architecture. Detailed technical discussions have been moved into canonical files in the sub‑folders:

- **Patterns:** Core patterns such as Director‑Evaluator (implemented via S-expressions), Error Handling, and Resource Management (see files under `system/architecture/patterns/`).
– **Decisions (ADRs):** Architecture Decision Records on topics such as context management and memory system design (see `system/architecture/decisions/`).
– **Q&A and Open Questions:** Clarifications and unresolved issues (see `system/architecture/qa/` and `system/architecture/questions.md`).

## Document Map

**This folder contains:**
 - `overview.md`: This high‑level summary and navigation index.
 - `patterns/`: Detailed technical descriptions of core patterns.
 - `decisions/`: Architecture Decision Records (ADRs) with rationale and scope.
 - `qa/`: Frequently asked questions and clarifications.
 - `questions.md`: A list of open and unresolved architecture questions.

For full technical details on any topic, please refer to the canonical file listed above.

### System Goals
1. Primary Goals
- Provide reliable task automation through structured decomposition and execution
- Ensure consistent task processing despite resource constraints
- Enable robust error recovery without human intervention
- Maintain system coherence across task boundaries

2. Quality Goals
- Predictable resource usage through explicit tracking and limits
- Consistent behavior through standardized protocols and interfaces
- Extensible task handling via template-based architecture
- Maintainable system through clear component boundaries

3. Operational Goals
- Handle varying task complexities through dynamic decomposition
- Support diverse task types through flexible template system
- Preserve critical context across task boundaries
- Manage resources efficiently within defined constraints

### System Constraints

#### Resource Constraints
- Fixed context window size
- Limited turn counts
- Synchronous operation only
- File access via Handler tools only

#### Operational Constraints  
- One Handler per task execution
- Immutable Handler configuration
- No persistent state maintenance
- Template immutability during execution

## Core Patterns

### Director-Evaluator Pattern [Pattern:DirectorEvaluator:1.1]

The system implements a standardized mechanism for iterative refinement, primarily achieved using **S-expression DSL primitives** (like `bind`, `if`, potentially loops or recursion) to structure the flow between generation (Director) and evaluation (Evaluator) steps executed as **atomic tasks called from the S-expression**. This pattern enables structured iteration with feedback between steps.

*   **Implementation:** A workflow defined using S-expressions structures the iterative loop. It uses primitives like `bind` or `let` to pass data between the director atomic task call and the evaluator atomic task call. Conditionals (`if`) and potentially recursion manage iteration. Script execution is integrated via `(system:run_script ...)` primitive calls.
*   **Dynamic Trigger:** An atomic task (like a Director) can still potentially trigger evaluation dynamically by returning `CONTINUATION` status with a `subtask_request`. The `SexpEvaluator` handles spawning the evaluation subtask via `TaskSystem`.

For the complete specification, see [Pattern:DirectorEvaluator:1.1] in `system/architecture/patterns/director-evaluator.md`.

### Error Handling [Pattern:Error:1.0]
Defines how errors propagate and recover across component boundaries. See [Pattern:Error:1.0].

### Resource Management [Pattern:ResourceManagement:1.0]
Defines resource usage tracking (Handler-centric) and lifecycle. See [Pattern:ResourceManagement:1.0].

### Task Execution (S-expression based)
Workflows are defined and executed via S-expressions managed by the `SexpEvaluator`. Atomic steps within the workflow are executed by calling named atomic tasks via the `TaskSystem` and `AtomicTaskExecutor`.

## Delegation Mechanisms

The system provides a unified tool interface with distinct implementation mechanisms:

### Tool Interface
What the LLM sees (when called via `AtomicTaskExecutor` -> `Handler`) or what the S-expression calls:
*   Consistent invocation pattern (e.g., `tools.readFile(...)` for LLM, `(system:run_script ...)` or `(call user:tool ...)` in S-exp).
*   Unified parameter schemas and error handling.

### Implementation Mechanisms

1.  **Direct Tools (Handler):**
    *   Synchronous execution by the Handler.
    *   No complex context management needed by the tool itself.
    *   Called directly by `Dispatcher` or `SexpEvaluator` primitives.
    *   Examples: File I/O, simple API calls, script execution (`system:run_script`).

2.  **Atomic Tasks (TaskSystem + AtomicTaskExecutor):**
    *   Defined via XML templates, managed by `TaskSystem`.
    *   Invoked programmatically via `SexpEvaluator` calling `TaskSystem.execute_atomic_template`.
    *   Execution involves `TaskSystem` setup, `AtomicTaskExecutor` body execution (incl. substitution), and `Handler` interaction (LLM calls, tool use within the task).
    *   Supports full context management features orchestrated by `TaskSystem`.
    *   Can return `CONTINUATION` status, handled by `SexpEvaluator` for subtask spawning.

See [Pattern:ToolInterface:1.0] for a detailed explanation.

## Component Architecture

The system consists of several core components working together:

### Dispatcher (Conceptual / Part of `main.py` or similar)
*   Routes incoming requests (e.g., from REPL `/task` command).
*   If input starts with `(`, routes to `SexpEvaluator`.
*   Otherwise, looks up identifier in Handler direct tools.

### SexpEvaluator [Component:SexpEvaluator:1.0]
S-expression workflow execution component.
*   Parses and executes S-expression strings.
*   Manages control flow (conditionals, binding, function calls, mapping) within the DSL.
*   Manages lexical environments (`SexpEnvironment`) for the S-expression DSL.
*   Calls `TaskSystem.execute_atomic_template` to run atomic task steps.
*   Calls Handler direct tools via primitives like `(system:run_script ...)`.
*   Handles `CONTINUATION` results from atomic tasks to implement subtask spawning.
*   Calls `MemorySystem` via primitives like `(get_context ...)`.

### Task System [Component:TaskSystem:1.0]
Atomic task management and orchestration component.
*   Manages atomic task template definitions (loading, validation, lookup via `find_template`).
*   Provides the `execute_atomic_template` interface for invoking atomic tasks programmatically (called by `SexpEvaluator`).
*   Determines context and prepares parameters for atomic tasks based on `SubtaskRequest` and template definitions.
*   Instantiates/configures Handlers for atomic task execution.
*   Instantiates and calls the `AtomicTaskExecutor`.
*   Interfaces with Memory System for context retrieval coordination.

### AtomicTaskExecutor [Component:AtomicExecutor:1.0]
Atomic task body execution component.
*   Receives parsed atomic task definition and resolved parameters (`params` dict) from Task System.
*   Performs final `{{parameter}}` substitution using **only** the provided `params`.
*   Constructs `HandlerPayload` and calls the Handler.
*   Returns the Handler's `TaskResult` to the Task System.

### Handler [Component:Handler:1.0]
LLM interface, resource tracking, and external interaction component.
*   Performs ALL file I/O operations.
*   Executes external commands (shell scripts).
*   Interacts with LLM providers (via `pydantic-ai`).
*   Manages resource usage tracking (turns, tokens) **per atomic task execution**.
*   Executes "Direct Tools" when called by Dispatcher or SexpEvaluator primitives.

### Memory System [Component:Memory:3.0]
Metadata management and context retrieval component.
*   Maintains global file metadata index (paths and descriptive strings).
*   Provides context via `getRelevantContextFor`.
*   Does NOT store file content, perform file operations, track resources, or rank matches.
*   Follows read-only context model.

### Compiler [Component:Compiler:1.0]
*   Primary role: Validates atomic task XML schema during registration (`TaskSystem.register_template`).
*   Future role: May handle initial Natural Language -> S-expression translation.
*   Does *not* generate ASTs for workflow execution.

See [Contract:Integration:TaskMemory:3.0] for memory integration specification.

## High-Level Interaction Flows

This section outlines the typical sequence of component interactions for key system operations, starting from the `Application` layer.

### 1. Handling a Natural Language Query (`Application.handle_query`)

This flow describes how a simple user query is processed in passthrough mode.

```mermaid
sequenceDiagram
    participant User
    participant App as Application
    participant Handler as PassthroughHandler
    participant FCM as FileContextManager
    participant MS as MemorySystem
    participant FAM as FileAccessManager
    participant LLMM as LLMInteractionManager
    participant LLM as pydantic-ai Agent

    User->>App: handle_query(query)
    App->>Handler: handle_query(query)
    Handler->>FCM: get_relevant_files(query)
    FCM->>MS: get_relevant_context_for(input)
    MS-->>FCM: AssociativeMatchResult (paths)
    FCM-->>Handler: relevant_file_paths
    Handler->>FCM: create_file_context(paths)
    FCM->>FAM: read_file(path1)
    FAM-->>FCM: content1
    FCM->>FAM: read_file(path2)
    FAM-->>FCM: content2
    FCM-->>Handler: formatted_context_string
    Handler->>Handler: _build_system_prompt(...)
    Handler->>LLMM: execute_call(prompt=query, history, system_prompt, ...)
    LLMM->>LLM: run_sync(...)
    LLM-->>LLMM: LLM Response
    LLMM-->>Handler: Formatted Result (dict)
    Handler->>Handler: Update History
    Handler-->>App: TaskResult
    App-->>User: TaskResult (dict)
```

**Steps:**

1.  User sends query to `Application.handle_query`.
2.  `Application` delegates to `PassthroughHandler.handle_query`.
3.  `Handler` calls `FileContextManager.get_relevant_files` (inherited via `BaseHandler._get_relevant_files`).
4.  `FileContextManager` calls `MemorySystem.get_relevant_context_for` to find relevant file paths based on the query.
5.  `MemorySystem` returns paths in an `AssociativeMatchResult`.
6.  `Handler` calls `FileContextManager.create_file_context` (inherited via `BaseHandler._create_file_context`).
7.  `FileContextManager` uses `FileAccessManager` to read the content of the relevant files.
8.  `FileContextManager` returns a formatted string containing the file content.
9.  `Handler` builds the final system prompt using `BaseHandler._build_system_prompt`.
10. `Handler` calls `LLMInteractionManager.execute_call` (inherited via `BaseHandler._execute_llm_call`), passing the user query, conversation history, system prompt, etc.
11. `LLMInteractionManager` interacts with the configured `pydantic-ai` Agent.
12. `LLMInteractionManager` processes the response and returns a structured result dictionary to the `Handler`.
13. `Handler` updates its internal conversation history.
14. `Handler` returns the final `TaskResult` to `Application`.
15. `Application` returns the result dictionary to the caller.

### 2. Handling a Programmatic Task Command (`Application.handle_task_command`)

This flow describes how commands (like S-expressions or direct task/tool IDs) are executed.

#### 2a. S-Expression Workflow

```mermaid
sequenceDiagram
    participant User
    participant App as Application
    participant Dispatcher
    participant SexpEval as SexpEvaluator
    participant SexpEnv as SexpEnvironment
    participant MS as MemorySystem
    participant TS as TaskSystem
    participant Handler as BaseHandler

    User->>App: handle_task_command(sexp_string, ...)
    App->>Dispatcher: execute_programmatic_task(sexp_string, ...)
    Dispatcher->>SexpEval: evaluate_string(sexp_string)
    SexpEval->>SexpEval: Parse S-expression
    SexpEval->>SexpEnv: Create/Lookup Environment
    Note over SexpEval, SexpEnv: Recursive Evaluation (_eval)
    alt Primitive Call (e.g., get_context)
        SexpEval->>MS: get_relevant_context_for(...)
        MS-->>SexpEval: Result (e.g., paths)
    else Task Invocation (e.g., (call my-task ...))
        SexpEval->>TS: execute_atomic_template(...)
        TS-->>SexpEval: TaskResult
    else Tool Invocation (e.g., (system:read_files ...))
        SexpEval->>Handler: _execute_tool(...)
        Handler-->>SexpEval: TaskResult
    end
    SexpEval-->>Dispatcher: Final Result (Any)
    Dispatcher->>Dispatcher: Format as TaskResult if needed
    Dispatcher-->>App: TaskResult (dict)
    App-->>User: TaskResult (dict)
```

**Steps:**

1.  User sends S-expression string via `Application.handle_task_command`.
2.  `Application` delegates to `Dispatcher.execute_programmatic_task`.
3.  `Dispatcher` identifies the input as an S-expression and calls `SexpEvaluator.evaluate_string`.
4.  `SexpEvaluator` parses the string and begins recursive evaluation (`_eval`) using `SexpEnvironment` for variable scope.
5.  During evaluation:
    *   **Special Forms** (`let`, `if`, `quote`, etc.) manipulate the environment or control flow.
    *   **Primitives** (`get_context`, `list`, etc.) execute built-in logic, potentially calling other components like `MemorySystem`.
    *   **Task/Tool Invocations** (`(call task-name ...)` or `(tool-name ...)`):
        *   `SexpEvaluator` resolves arguments.
        *   It calls `TaskSystem.execute_atomic_template` for atomic tasks OR `Handler._execute_tool` for direct tools.
        *   The called component executes the task/tool (potentially involving `AtomicTaskExecutor`, `Handler`, `LLMInteractionManager` as in Flow 1 for atomic tasks).
        *   The `TaskResult` is returned to `SexpEvaluator`.
6.  `SexpEvaluator` returns the final value of the S-expression to the `Dispatcher`.
7.  `Dispatcher` formats the result into a standard `TaskResult` dictionary if necessary.
8.  `Dispatcher` returns the result dictionary to `Application`.
9.  `Application` returns the result dictionary to the caller.

#### 2b. Direct Task/Tool Invocation

```mermaid
sequenceDiagram
    participant User
    participant App as Application
    participant Dispatcher
    participant TS as TaskSystem
    participant Handler as BaseHandler
    participant Executor as AtomicTaskExecutor

    User->>App: handle_task_command(identifier, params, ...)
    App->>Dispatcher: execute_programmatic_task(identifier, params, ...)
    Dispatcher->>TS: find_template(identifier)
    alt Template Found
        TS-->>Dispatcher: Template Definition
        Dispatcher->>TS: execute_atomic_template(SubtaskRequest(params))
        TS->>Executor: execute_body(template_def, params, handler_instance)
        Executor->>Handler: _execute_llm_call(...)
        Handler-->>Executor: TaskResult
        Executor-->>TS: TaskResult
        TS-->>Dispatcher: TaskResult
    else Tool Found
        Dispatcher->>Handler: tool_executors[identifier](params)
        Handler-->>Dispatcher: Tool Result (dict/TaskResult)
        Dispatcher->>Dispatcher: Format as TaskResult if needed
    else Not Found
        Dispatcher-->>Dispatcher: Create FAILED TaskResult
    end
    Dispatcher-->>App: TaskResult (dict)
    App-->>User: TaskResult (dict)
```

**Steps:**

1.  User sends task/tool identifier and parameters via `Application.handle_task_command`.
2.  `Application` delegates to `Dispatcher.execute_programmatic_task`.
3.  `Dispatcher` attempts to find an atomic template in `TaskSystem` using `find_template`.
4.  **If Template Found:**
    *   `Dispatcher` creates a `SubtaskRequest` with the parameters.
    *   `Dispatcher` calls `TaskSystem.execute_atomic_template`.
    *   `TaskSystem` prepares context, instantiates `AtomicTaskExecutor`, and calls `execute_body`.
    *   `AtomicTaskExecutor` performs parameter substitution and calls `Handler._execute_llm_call`.
    *   The `Handler` (via `LLMInteractionManager`) interacts with the LLM.
    *   The `TaskResult` propagates back up through `Executor` and `TaskSystem` to the `Dispatcher`.
5.  **If Template Not Found:**
    *   `Dispatcher` looks up the identifier in `Handler.tool_executors`.
    *   **If Tool Found:** `Dispatcher` calls the registered executor function directly with the parameters. The executor function runs (e.g., `SystemExecutorFunctions.execute_read_files` calls `FileAccessManager`). The result is returned to `Dispatcher`, which formats it as a `TaskResult` if needed.
    *   **If Tool Not Found:** `Dispatcher` creates a FAILED `TaskResult`.
6.  `Dispatcher` returns the final `TaskResult` dictionary to `Application`.
7.  `Application` returns the result dictionary to the caller.

## Component Integration

### Core Integration Patterns

#### SexpEvaluator ↔ TaskSystem
*   SexpEvaluator calls `TaskSystem.find_template` to check if an identifier is an atomic task.
*   SexpEvaluator calls `TaskSystem.execute_atomic_template` to run atomic steps, providing resolved arguments.

#### TaskSystem ↔ AtomicTaskExecutor
*   TaskSystem instantiates AtomicTaskExecutor.
*   TaskSystem calls `AtomicTaskExecutor.execute_body`, providing the parsed template, resolved parameters (`params` dict), context string, file list, and a Handler instance.

#### AtomicTaskExecutor ↔ Handler
*   AtomicTaskExecutor calls `Handler.executePrompt` (or similar) with the fully resolved payload.

#### TaskSystem ↔ MemorySystem
*   TaskSystem calls `MemorySystem.getRelevantContextFor` when preparing context for atomic tasks requiring fresh context.

#### SexpEvaluator ↔ Handler
*   SexpEvaluator primitives (e.g., `system:run_script`) may directly invoke Handler's direct tool executors.

#### SexpEvaluator ↔ MemorySystem
*   SexpEvaluator primitives (e.g., `get_context`) may directly invoke `MemorySystem.getRelevantContextFor`.

See system/contracts/interfaces.md for detailed contract specifications.

### Resource Ownership
*   **Handler**: Owns resource tracking (turns, tokens) for the duration of a single atomic task execution it handles.
*   **SexpEvaluator**: Manages the `SexpEnvironment` (DSL variable scope). May track overall workflow execution time or steps.
*   **Memory system**: Owns context metadata storage.
*   **Task system**: Coordinates Handler instantiation and configuration with limits for atomic tasks.

See system/contracts/resources.md for the resource model.

### System-Wide Protocols
*   S-expression DSL for workflow definition.
*   XML for *atomic* task template definition.
*   Standard error propagation (`TaskError`).
*   Resource usage tracking (Handler-based).
*   Context management (Hybrid model: defaults + overrides).

---

*(Self-correction: The original text included sections for Function-Based Template Pattern, Sequential Task Management, and Subtask Spawning Mechanism here. These are now either deprecated (XML function templates) or better described within the main component descriptions or dedicated pattern files. Removing them from this high-level overview improves clarity)*

## Error Handling Philosophy

To ensure predictable component interactions and simplify error management, this project adheres to the following error propagation strategy:

1.  **Prefer Returning FAILED TaskResult:** Components (like `TaskSystem`, `BaseHandler`, Tool Executors) should primarily signal recoverable errors or expected failures by returning a `TaskResult` object (or dictionary conforming to its structure) with `status='FAILED'`.
2.  **Structured Error in Notes:** When returning a FAILED `TaskResult`, the `notes` dictionary MUST contain an `error` key. The value associated with `error` SHOULD be a structured error object (like `TaskFailureError` or its variants, serialized to a dictionary if needed) containing at least `type`, `reason`, and `message` fields, and optionally `details`.
3.  **Limit Raising Exceptions:** Raising exceptions (like `TaskError` subclasses or standard Python exceptions) across public component API boundaries should be reserved for:
    *   Truly *exceptional* or *unrecoverable* system states (e.g., configuration errors during initialization, critical dependency failures).
    *   Situations where immediate termination of the current control flow is required and cannot be reasonably handled by returning a FAILED status.
4.  **Document Raised Exceptions:** Any exception that *can* be raised across a component's public boundary MUST be documented in its IDL using `@raises_error`.
5.  **Orchestrator Responsibility:** Caller components (Orchestrators like `Dispatcher`, `SexpEvaluator`) are responsible for handling both returned FAILED `TaskResult` objects and documented exceptions from the components they call, formatting them consistently before propagating further (See Implementation Rule 8.x).

This approach promotes clearer contracts, centralizes error handling logic in callers, and makes component behavior more predictable.

## Error Handling Philosophy

To ensure predictable component interactions and simplify error management, this project adheres to the following error propagation strategy:

1.  **Prefer Returning FAILED TaskResult:** Components (like `TaskSystem`, `BaseHandler`, Tool Executors) should primarily signal recoverable errors or expected failures by returning a `TaskResult` object (or dictionary conforming to its structure) with `status='FAILED'`.
2.  **Structured Error in Notes:** When returning a FAILED `TaskResult`, the `notes` dictionary MUST contain an `error` key. The value associated with `error` SHOULD be a structured error object (like `TaskFailureError` or its variants, serialized to a dictionary if needed) containing at least `type`, `reason`, and `message` fields, and optionally `details`.
3.  **Limit Raising Exceptions:** Raising exceptions (like `TaskError` subclasses or standard Python exceptions) across public component API boundaries should be reserved for:
    *   Truly *exceptional* or *unrecoverable* system states (e.g., configuration errors during initialization, critical dependency failures).
    *   Situations where immediate termination of the current control flow is required and cannot be reasonably handled by returning a FAILED status.
4.  **Document Raised Exceptions:** Any exception that *can* be raised across a component's public boundary MUST be documented in its IDL using `@raises_error`.
5.  **Orchestrator Responsibility:** Caller components (Orchestrators like `Dispatcher`, `SexpEvaluator`) are responsible for handling both returned FAILED `TaskResult` objects and documented exceptions from the components they call, formatting them consistently before propagating further (See Implementation Rule 8.x).

This approach promotes clearer contracts, centralizes error handling logic in callers, and makes component behavior more predictable.
