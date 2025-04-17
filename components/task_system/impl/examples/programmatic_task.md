# Programmatic Task Execution Examples

This document provides examples of using the `/task` command for programmatic task execution.

## Basic Usage

The `/task` command allows you to execute specific tasks directly, bypassing the natural language processing of passthrough mode:

```
/task <type:subtype> [param1=value1] [param2=value2] [--flag]
```

## Aider Automatic Examples

### With Explicit File Context

Execute Aider in automatic mode with explicitly specified files:

```
/task aider:automatic prompt="Add docstrings to all functions" file_context='["src/main.py", "src/utils.py"]'
```

This will:
1. Execute the `aider:automatic` task
2. Pass the prompt "Add docstrings to all functions"
3. Use only the explicitly specified files (`src/main.py` and `src/utils.py`)
4. Skip automatic context lookup since explicit context is provided

### With Automatic Context Lookup

Execute Aider in automatic mode without specifying files, triggering automatic context lookup:

```
/task aider:automatic prompt="Fix the error handling in the dispatcher"
```

This will:
1. Execute the `aider:automatic` task
2. Pass the prompt "Fix the error handling in the dispatcher"
3. Perform automatic context lookup to find relevant files
4. Use the files found by the automatic lookup

### With History Context

Execute Aider in automatic mode using conversation history for context:

```
/task aider:automatic prompt="Implement the feature we just discussed" --use-history
```

This will:
1. Execute the `aider:automatic` task
2. Pass the prompt "Implement the feature we just discussed"
3. Include recent conversation history in the context generation
4. Perform automatic context lookup with history awareness
5. Use the files found by the history-aware automatic lookup

## Using the Help Flag

Get detailed information about a task:

```
/task aider:automatic --help
```

This will display:
1. The task description
2. Available parameters with types and descriptions
3. Whether parameters are required or optional
4. Default values if specified

## Complex JSON Parameters

Pass complex data structures using JSON strings:

```
/task format:json value='{"users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]}' indent=4
```

This will:
1. Execute the `format:json` task
2. Parse the JSON string into a Python data structure
3. Format the JSON with an indent of 4 spaces

## Context Precedence Examples

### Template-Defined Context

If a template has `file_paths` defined and no explicit context is provided:

```
/task template:with-paths prompt="Analyze this code"
```

This will use the file paths defined in the template, skipping automatic lookup.

### Disabled Automatic Context

If a template has `fresh_context: disabled` and no explicit context is provided:

```
/task template:no-auto prompt="Process without context"
```

This will execute without any file context, skipping automatic lookup.

## Error Handling Examples

### Invalid JSON

```
/task aider:automatic prompt="Fix bugs" file_context='["unclosed_array"'
```

This will display an error about invalid JSON format.

### Unknown Task

```
/task nonexistent:task prompt="This will fail"
```

This will display an error that the task identifier was not found.

### Missing Required Parameter

```
/task aider:automatic
```

This will fail because the required `prompt` parameter is missing.
