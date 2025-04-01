# Hierarchical System Prompt Pattern [Pattern:SystemPrompt:1.0]

**Canonical Reference:** This document is the authoritative description of the Hierarchical System Prompt Pattern. All extended descriptions in other files should refer here.

## Purpose

Define a standardized approach for combining universal and task-specific system prompts for LLM interactions. This pattern addresses the need for both:
1. Universal behaviors common to all LLM instances (input/output conventions, tool use, etc.)
2. Task-specific behaviors defined in templates

## Pattern Description

The Hierarchical System Prompt pattern separates universal behaviors from task-specific instructions while ensuring consistent prompt construction across all LLM interactions.

### Core Elements

1. **Base System Prompt**
   - Defined in Handler configuration (`baseSystemPrompt`)
   - Contains universal behaviors applicable to all LLM instances:
     * Input/output conventions
     * Tool usage formats
     * General response guidelines
     * Error reporting formats
   - Maintained centrally for consistency

2. **Template-Specific System Prompt**
   - Defined in task templates (`systemPrompt`)
   - Contains task-specific instructions and behaviors:
     * Domain-specific knowledge
     * Task-specific formats
     * Specialized response guidelines
   - Extends rather than replaces the base system prompt

3. **Prompt Combination Mechanism**
   - Occurs during payload construction in the Handler
   - Uses a clear separator (`===`) between base and template-specific prompts
   - Preserves both sets of instructions in a hierarchical structure

### Implementation

```typescript
/**
 * Constructs a payload for the LLM using fully resolved content
 */
constructPayload(task: TaskTemplate): HandlerPayload {
  // Combine base and template-specific system prompts
  const combinedSystemPrompt = task.systemPrompt 
    ? `${this.baseSystemPrompt}\n\n===\n\n${task.systemPrompt}`
    : this.baseSystemPrompt;
    
  return {
    systemPrompt: combinedSystemPrompt,
    // ... other payload properties ...
  };
}
```

## Benefits

1. **Consistency**: Ensures universal behaviors are consistent across all LLM interactions
2. **Flexibility**: Allows templates to define task-specific behaviors
3. **Maintainability**: Centralizes universal behaviors for easier updates
4. **Clarity**: Provides clear separation between different types of instructions

## Implementation Considerations

1. **Prompt Length**: Monitor combined system prompt length to prevent excessive token usage
2. **Potential Conflicts**: Ensure template-specific prompts don't contradict universal behaviors
3. **Clear Separation**: Maintain clear visual separation between prompt sections
4. **Base Prompt Design**: Keep base prompt focused on truly universal behaviors

## Related Patterns

- [Pattern:ToolInterface:1.0] for universal tool usage conventions
- [Pattern:DirectorEvaluator:1.1] for specialized task execution flows
