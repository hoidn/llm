# Task System Public API [Interface:TaskSystem:1.0]

> This document is the authoritative source for the Task System public API.

## Overview

The Task System provides task execution, template management, and resource tracking services. It orchestrates the execution of tasks through structured XML templates and handlers.

## Core Interface

```typescript
/**
 * Primary task execution interface
 * [Interface:TaskSystem:1.0]
 */
interface TaskSystem {
    /**
     * Execute a task with the given parameters
     * 
     * @param task - The task to execute (XML string or task description)
     * @param memory - The Memory System instance
     * @param options - Optional execution options
     * @returns Promise resolving to the task result
     */
    executeTask(
        task: string,
        memory: MemorySystem,
        options?: {
            taskType?: TaskType;
            provider?: string;
            model?: string;
        }
    ): Promise<TaskResult>;

    /**
     * Validate a task template
     * 
     * @param template - The template to validate
     * @returns Whether the template is valid
     */
    validateTemplate(template: TaskTemplate): boolean;
    
    /**
     * Find matching templates based on input
     * 
     * Note: Matching applies *only* to atomic task templates.
     * 
     * @param input - The natural language task description
     * @param memory - The Memory System instance
     * @returns Promise resolving to matching templates with scores
     */
    findMatchingTasks(
        input: string,
        memory: MemorySystem
    ): Promise<Array<{
        template: TaskTemplate;
        score: number;
        taskType: TaskType;
    }>>;
    
    /**
     * Register a template in the TaskLibrary
     * 
     * @param template - The template to register
     * @returns Promise resolving to registration result
     */
    registerTemplate(template: TemplateNode): Promise<void>;
    
    /**
     * Execute a function call
     * 
     * @param call - The function call to execute
     * @param env - The environment for argument evaluation
     * @returns Promise resolving to the function result
     */
    executeCall(call: FunctionCallNode, env: Environment): Promise<TaskResult>;

    /**
     * Execute a Task System template workflow directly from a SubtaskRequest.
     * Bypasses the need for a CONTINUATION status from a Handler.
     * Primarily used for programmatic invocation (e.g., via /task command).
     *
     * @param request - The SubtaskRequest containing type, subtype, inputs, etc.
     * @param env - The environment for execution.
     * @returns Promise resolving to the final TaskResult of the workflow.
     */
    execute_subtask_directly(request: SubtaskRequest, env: Environment): Promise<TaskResult>;
}
```

## Type References

For Task System specific types, see [Type:TaskSystem:1.0] in `/components/task-system/spec/types.md`.
For system-wide types, see [Type:System:1.0] in `/system/contracts/types.md`.

## Integration Points

- **Memory System**: Used for context retrieval via [Interface:Memory:3.0]
- **Handler**: Used for LLM interactions and resource enforcement
- **Evaluator**: Used for task execution and error recovery
- **Compiler**: Used for task parsing and transformation

## Contract References

For XML schema definitions, see [Contract:Tasks:TemplateSchema:1.0] in `/system/contracts/protocols.md`.
For integration contract details, see [Contract:Integration:TaskSystem:1.0] in `/system/contracts/interfaces.md`.
