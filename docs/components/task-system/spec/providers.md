# LLM Provider Support

## Overview

The system supports multiple LLM providers through a configuration-based approach. This document defines the provider integration model and capabilities.

## Provider Configuration

Providers are configured at the Handler level and can be overridden at task execution time:

```typescript
// System-level default provider
const taskSystem = new TaskSystem({
    provider: "anthropic",  // Default provider
    // Other configuration
});

// Task-level provider override
const result = await taskSystem.executeTask(
    taskDefinition,
    memorySystem,
    { provider: "openai" }  // Override for this task
);
```

## Supported Providers

The system currently supports the following providers:

| Provider | Models | Tool Support |
|----------|--------|-------------|
| anthropic | claude-3-opus, claude-3-sonnet, claude-3-haiku | file_access, bash, text_editor |
| openai | gpt-4, gpt-3.5-turbo | file_access, function_calling |

## Tool Abstractions

Tools are referenced using provider-agnostic identifiers:

| Tool ID | Description | Provider Implementations |
|---------|-------------|--------------------------|
| file_access | Read/write file operations | Anthropic: computer_20250124, OpenAI: custom functions |
| bash | Execute shell commands | Anthropic: bash_20250124, OpenAI: code_interpreter |
| text_editor | Text editing capabilities | Anthropic: text_editor_20250124, OpenAI: n/a |

## Provider Selection

The system selects providers based on the following precedence:

1. Task execution override (`options.provider`)
2. Task template provider (`template.provider`)
3. Task system default provider (`config.provider`)

## Resource Standardization

All providers use a consistent resource model:

- Turn counting follows the same pattern across providers
- Context window is measured as a fraction of the model's maximum context
- Resource exhaustion handling is provider-agnostic

## Implementation Guidelines

When implementing provider-specific handlers:

1. Tool mappings should be handled internally within the provider implementation
2. Provider-specific behaviors should not leak into task definitions
3. Resource tracking should maintain consistent metrics across providers
4. Error handling should map provider-specific errors to standard system errors
