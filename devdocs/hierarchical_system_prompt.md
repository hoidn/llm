# Hierarchical System Prompt Pattern - Developer Guide

## Overview

The Hierarchical System Prompt Pattern solves a common problem when working with LLMs: how to combine universal behaviors (applicable to all interactions) with task-specific instructions (needed only for particular templates).

This guide explains how the pattern is implemented in our codebase and how to use it effectively.

## How It Works

The pattern uses a three-level hierarchy:

1. **Base System Prompt**: Universal behaviors and instructions applicable to all LLM interactions
2. **Template-Specific System Prompt**: Instructions specific to particular task templates
3. **File Context**: Relevant file information for the current query

The handler combines these levels at runtime with clear separators, ensuring the LLM properly distinguishes between different instruction types.

## Implementation Details

### Components

1. **BaseHandler._build_system_prompt()**: The core method that combines the prompts
2. **PassthroughHandler._find_matching_template()**: Finds the appropriate template for a query
3. **TaskSystem.find_matching_tasks()**: Scores and ranks templates based on similarity
4. **Template Definitions**: Templates with `system_prompt` fields containing task-specific instructions

### Prompt Construction Process

When a user query is received:
1. The handler finds the most appropriate template for the query
2. The base system prompt is combined with the template's system prompt (separated by `===`)
3. File context is appended if relevant files are found
4. The combined prompt is sent to the LLM

## Example

Here's a visualization of how the prompts are combined:

```
[BASE SYSTEM PROMPT]
You are a helpful assistant that responds to user queries.

===

[TEMPLATE-SPECIFIC SYSTEM PROMPT]
When finding relevant files, consider:
- Direct keyword matches
- Semantically similar terms
- Related programming concepts
- File types appropriate for the task

[FILE CONTEXT]
Relevant files:
File: main.py
```

## How to Use

### Creating Templates with System Prompts

Templates in `task_system/templates/` can include a `system_prompt` field:

```python
MY_TEMPLATE = {
    "type": "atomic",
    "subtype": "my_subtype",
    "description": "Description of what this template does",
    "system_prompt": """
    Template-specific instructions go here.
    Be as detailed as needed, but focus only on what's
    specific to this template.
    """,
    # Other template fields...
}
```

### Best Practices

1. **Keep Base Prompts Universal**
   - The base system prompt should contain only behaviors applicable to *all* interactions
   - Avoid task-specific instructions in the base prompt

2. **Make Template Prompts Focused**
   - Template system prompts should contain only instructions relevant to that specific template
   - Don't repeat instructions already in the base prompt

3. **Use Clear Language**
   - Be explicit about what behavior you want
   - Use consistent terminology across different prompts

4. **Test Different Combinations**
   - Use the interactive example script to experiment with different prompts
   - Verify that the LLM correctly follows both base and template instructions

## Benefits

- **Cleaner Separation of Concerns**: Universal behaviors vs. task-specific instructions
- **Better Maintainability**: Update base behaviors once instead of in every template
- **More Consistent Responses**: LLM follows both universal and specific instructions
- **Easier Template Development**: Focus only on what's unique to your template

## When to Use

Use the Hierarchical System Prompt Pattern when:
1. You need consistent base behaviors across all LLM interactions
2. Different tasks require different specialized instructions
3. You want to maintain a clean separation between universal and task-specific behaviors
