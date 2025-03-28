# Handler Component [Component:Handler:1.0]

## Overview

The Handler manages LLM interactions, resource tracking, and tool execution. It serves as the direct interface to LLM providers while enforcing system constraints.

## Core Responsibilities

1. **LLM Interaction Management**
   - Execute prompts through provider-specific adapters
   - Manage conversation history and message formatting
   - Track resource usage (turns, context window)

2. **Resource Enforcement**
   - Monitor turn counts and context window usage
   - Enforce limits with appropriate error handling
   - Generate warnings at specified thresholds (80%)

3. **Tool Execution**
   - Provide unified tool interface to LLMs
   - Execute direct tools synchronously
   - Transform subtask requests into CONTINUATION signals

4. **Passthrough Mode**
   - Process raw queries without AST compilation
   - Maintain conversation state within subtasks
   - Apply standard context management to non-AST queries

4. **Session Management**
   - Maintain isolated execution environments for tasks
   - Track conversation state and history
   - Ensure clean resource release after execution

## Key Interfaces

- **executePrompt**: Submit prompts to the LLM and process responses
- **registerDirectTool**: Register synchronous tools for direct execution
- **registerSubtaskTool**: Register tools implemented via subtask continuation
- **addToolResponse**: Add tool responses to conversation history

For detailed specifications, see:
- [Interface:Handler:1.0] in `/components/handler/spec/interfaces.md`
- [Pattern:ResourceManagement:1.0] in `/system/architecture/patterns/resource-management.md`
- [Pattern:ToolInterface:1.0] in `/system/architecture/patterns/tool-interface.md`

For a comprehensive map of all system documentation, see [Documentation Guide](/system/docs-guide.md).
