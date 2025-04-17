# REPL Component [Component:REPL:1.0]

## Overview

The REPL (Read-Eval-Print Loop) component provides an interactive command-line interface for users to interact with the system. It supports both passthrough mode (for direct LLM interaction) and programmatic task execution.

## Core Functionality

1. **Interactive Query Processing**
   - Process natural language queries in passthrough mode
   - Maintain conversation state between queries
   - Display relevant context files and responses

2. **Command Handling**
   - Process special commands prefixed with `/`
   - Support for system configuration and control
   - Execute programmatic tasks via the `/task` command

3. **Repository Indexing**
   - Index git repositories for context retrieval
   - Manage indexed repositories for the session

## Commands

The REPL supports the following commands:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/mode [passthrough\|standard]` | Set or show current mode |
| `/index REPO_PATH` | Index a git repository |
| `/reset` | Reset conversation state |
| `/verbose [on\|off]` | Toggle verbose mode |
| `/debug [on\|off]` | Toggle debug mode for tool selection |
| `/test-aider [interactive\|automatic]` | Test Aider tool integration |
| `/task <type:subtype> [params] [flags]` | Execute a specific task programmatically |
| `/exit` | Exit the REPL |

## The `/task` Command

The `/task` command provides a way to execute specific tasks programmatically, bypassing the natural language processing of passthrough mode.

### Syntax

```
/task <type:subtype> [param1=value1] [param2='["json", "value"]'] [--flag1] [--flag2]
```

### Parameters

- `<type:subtype>`: The task identifier (e.g., `aider:automatic`)
- `param=value`: Task parameters as key-value pairs
- `param='["json", "value"]'`: JSON parameters (must be quoted)
- `--flag`: Boolean flags (e.g., `--use-history`, `--help`)

### Examples

```
# Execute Aider in automatic mode with explicit file context
/task aider:automatic prompt="Add docstrings to functions" file_context='["src/main.py", "src/utils.py"]'

# Get help for a specific task
/task aider:automatic --help

# Use conversation history for context
/task aider:automatic prompt="Fix the bugs we discussed" --use-history
```

### Special Flags

- `--help`: Display help information for the specified task
- `--use-history`: Include recent conversation history for context generation

### JSON Parameter Handling

For parameters that require complex data structures, you can pass JSON strings:

```
/task some:task config='{"nested": {"value": 42}, "array": [1, 2, 3]}'
```

The JSON will be automatically parsed into the appropriate Python data structure.

## Context Handling

The `/task` command supports three methods of context determination, in order of precedence:

1. **Explicit Context**: Provided via the `file_context` parameter
2. **Template Context**: Defined in the task template's `file_paths` field
3. **Automatic Context**: Generated via the Memory System if enabled

When using `--use-history`, the recent conversation history is included in the context generation process, which can improve the relevance of automatically determined files.

## Integration Points

- **TaskSystem**: For template-based task execution
- **Dispatcher**: For routing task requests
- **MemorySystem**: For context retrieval
- **AiderBridge**: For code editing capabilities
