# ADR 17: Programmatic Task Invocation via Thin Wrappers

## Status

Implemented

## Context

The system needs a way to execute specific tasks programmatically, bypassing the natural language processing of passthrough mode. This is particularly important for:

1. Testing and debugging specific task templates
2. Providing a command-line interface for power users
3. Enabling scripting and automation
4. Supporting direct invocation of tools like Aider

## Decision

We will implement a `/task` command in the REPL that allows users to execute specific tasks directly, using a thin wrapper around the TaskSystem's `execute_subtask_directly` method and the Handler's direct tools.

The command will have the following syntax:

```
/task <type:subtype> [param1=value1] [param2=value2] [--flag]
```

The implementation will:

1. Parse the command arguments using `shlex` to handle quoted strings
2. Route the request to the appropriate executor based on the identifier
3. Support JSON parameter parsing for complex data structures
4. Provide a `--help` flag for discovering task parameters
5. Support a `--use-history` flag for including conversation history in context generation

## Consequences

### Positive

- Provides a direct way to execute specific tasks without natural language ambiguity
- Enables testing and debugging of individual task templates
- Supports power users who prefer command-line interfaces
- Facilitates scripting and automation
- Maintains consistent error handling with the rest of the system

### Negative

- Adds complexity to the REPL implementation
- Requires users to know specific task identifiers and parameters
- May lead to duplication of functionality between natural language and command-line interfaces

## Implementation Details

The implementation consists of three main components:

1. **REPL Command Handler**: Parses the command and displays results
2. **Dispatcher**: Routes requests to the appropriate executor
3. **TaskSystem Integration**: Executes template-based tasks via `execute_subtask_directly`

The dispatcher follows a precedence order for determining which executor to use:
- Templates take precedence over direct tools if both exist with the same identifier
- Direct tools are used if no matching template is found

Context determination follows a similar precedence order:
1. Explicit file context in the request
2. Template-defined file paths
3. Automatic context lookup via MemorySystem

## Alternatives Considered

### Alternative 1: XML-Based Task Invocation

We considered using an XML-based syntax similar to the internal task representation:

```
/task <task type="atomic" subtype="code_analysis">
  <param name="query">Find bugs</param>
  <param name="file_paths">["src/main.py"]</param>
</task>
```

This was rejected as too verbose for command-line use.

### Alternative 2: JSON-Based Task Invocation

We considered using a JSON-based syntax:

```
/task '{"type": "atomic", "subtype": "code_analysis", "params": {"query": "Find bugs"}}'
```

This was rejected as less readable and harder to type than the key-value approach.

### Alternative 3: Dedicated Task REPL

We considered implementing a separate REPL specifically for task execution:

```
/tasks
tasks> code_analysis query="Find bugs" file_paths=["src/main.py"]
```

This was rejected as adding unnecessary complexity compared to a single command.
