# Task System Types [Type:TaskSystem:1.0]

> This document is the authoritative source for Task System specific types.

## Core Types

```typescript
/**
 * Task execution result
 * [Type:TaskSystem:TaskResult:1.0]
 */
interface TaskResult {
    /**
     * Output content from the task execution.
     * Contains complete output if status is COMPLETE.
     * May contain partial output if status is FAILED or CONTINUATION.
     */
    content: string;
    
    /**
     * Execution status of the task.
     * COMPLETE: Task finished successfully, content is complete
     * CONTINUATION: Task needs additional steps, content may be partial
     * FAILED: Task encountered an error, content may be partial
     */
    status: ReturnStatus;
    
    /**
     * Optional free-form description used for dynamic evaluation template selection.
     */
    criteria?: string;
    
    /**
     * Parsed content if output was successfully parsed as JSON.
     */
    parsedContent?: any;
    
    /**
     * Task-level metadata about execution, resource usage, and status.
     * Contains ONLY metadata, never content.
     */
    notes: {
        dataUsage?: string;
        successScore?: number;
        parseError?: string;  // Present when JSON parsing fails
        [key: string]: any;
    };
}

/**
 * Base task definition interface
 * [Type:TaskSystem:BaseTaskDefinition:1.0]
 */
interface BaseTaskDefinition {
    description: string;
    type: TaskType;
    subtype?: string;
    
    /**
     * Specific files to include in task context.
     * These files will always be included regardless of other context settings.
     * Paths can be absolute or relative to repo root.
     * Invalid paths will generate warnings but execution will continue.
     * Only used when file_paths_source is not provided or has type 'literal'.
     */
    file_paths?: string[];
    
    /**
     * Optional source for generating file paths to include in context.
     * Takes precedence over file_paths array when provided with type 'command', 'description', or 'context_description'.
     */
    file_paths_source?: {
        /**
         * Source type for file paths:
         * - 'literal': Use explicit file_paths array (default behavior)
         * - 'command': Execute bash command to generate file paths
         * - 'description': Use natural language description for context-specific matching
         * - 'context_description': Use separate query string for context lookup
         */
        type: 'literal' | 'command' | 'description' | 'context_description';

        /** Value used for command execution */
        command?: string;
        /** Value used for description-based matching */
        description?: string;
        /** Value used for context_description query */
        context_query?: string;
        // 'literal' type uses the main file_paths array
    };
    
    context_management?: ContextManagement;
    inputs?: Record<string, any>;
}

/**
 * Task Template Interface
 * [Type:TaskSystem:TaskTemplate:1.0]
 * 
 * Any task type (atomic, sequential, reduce, script, etc.) can be defined as a template.
 * However, only atomic task templates participate in the template matching process.
 * Composite tasks can be either defined directly, defined as templates, or 
 * constructed by combining multiple atomic task templates.
 */
interface TaskTemplate {
    readonly taskPrompt: string;      // Maps to <instructions> in schema
    readonly systemPrompt?: string;   // Maps to <system> in schema; extends base system prompt
    readonly provider?: string;       // Maps to <provider> in schema
    readonly model?: string;          // Maps to <model> in schema
    readonly inputs?: Record<string, string>;
    readonly isManualXML?: boolean;   // Maps to <manual_xml> in schema
    readonly disableReparsing?: boolean; // Maps to <disable_reparsing> in schema
    readonly taskType?: TaskType;     // The type of task this template defines
    readonly atomicSubtype?: AtomicTaskSubtype; // Only for atomic task templates
}

/**
 * Represents a sequential task which has its own context management block
 * and multiple steps of subtasks.
 * [Type:TaskSystem:SequentialTask:1.0]
 */
interface SequentialTask extends BaseTaskDefinition {
    type: 'sequential';
    contextManagement: ContextManagement;
    steps: BaseTaskDefinition[];
}

/**
 * Represents a function call expression
 * [Type:TaskSystem:FunctionCallNode:1.0]
 */
interface FunctionCallNode {
    type: "call";
    templateName: string;
    arguments: ArgumentNode[];  // Evaluated in caller's environment
}

/**
 * Represents an argument to a function call
 * [Type:TaskSystem:ArgumentNode:1.0]
 */
interface ArgumentNode {
    type: "argument";
    value: string | any;  // String for variables/literals, object for nested
}

/**
 * Represents a template node in the AST
 * [Type:TaskSystem:TemplateNode:1.0]
 */
interface TemplateNode {
    name: string;
    parameters: string[];
    returns?: string;
    body: BaseTaskDefinition;
}

/**
 * Subtask Request - Used for LLM-to-LLM delegation via continuation
 * [Type:TaskSystem:SubtaskRequest:1.0]
 */
interface SubtaskRequest {
    /** Type of subtask to spawn */
    type: TaskType;
    
    /** Description of the subtask */
    description: string;
    
    /** Input parameters for the subtask */
    inputs: Record<string, any>;
    
    /** Optional hints for template selection */
    template_hints?: string[];
    
    /** Optional context management overrides */
    context_management?: {
        inherit_context?: 'full' | 'none' | 'subset';
        accumulate_data?: boolean;
        accumulation_format?: 'notes_only' | 'full_output';
        fresh_context?: 'enabled' | 'disabled';
    };
    
    /** Optional maximum nesting depth override */
    max_depth?: number;
    
    /** Optional subtype for atomic tasks */
    subtype?: string;
  
    /** 
     * Specific files to include in subtask context.
     * These files will always be included regardless of other context settings.
     * Paths can be absolute or relative to repo root.
     * Invalid paths will generate warnings but execution will continue.
     */
    file_paths?: string[];
}

/**
 * Specialized result structure for evaluator feedback
 * [Type:TaskSystem:EvaluationResult:1.0]
 */
interface EvaluationResult extends TaskResult {
    notes: {
        success: boolean;        // Whether the evaluation passed
        feedback: string;        // Human-readable feedback message
        details?: {              // Optional structured details
            metrics?: Record<string, number>; // Optional evaluation metrics
            violations?: string[];            // Specific validation failures
            suggestions?: string[];           // Suggested improvements
            [key: string]: any;               // Extension point
        };
        scriptOutput?: {         // Present when script execution is involved
            stdout: string;      // Standard output from script
            stderr: string;      // Standard error output from script
            exitCode: number;    // Exit code from script
        };
    };
}

/**
 * Script execution configuration
 * [Type:TaskSystem:ScriptExecution:1.0]
 */
interface ScriptExecution {
    command: string;
    timeout?: number;
    inputs: Record<string, string>;
}

/**
 * Represents the result of executing a script task
 * [Type:TaskSystem:ScriptTaskResult:1.0]
 */
interface ScriptTaskResult extends TaskResult {
    stdout: string;
    stderr: string;
    exitCode: number;
}
```

## Type References

For system-wide types, see [Type:System:1.0] in `/system/contracts/types.md`, which includes:
- TaskType and AtomicTaskSubtype enums
- ReturnStatus enum
- ContextManagement interface
- TaskError types
- ResourceMetrics interface

## Cross-References

- For XML schema definitions, see [Contract:Tasks:TemplateSchema:1.0] in `/system/contracts/protocols.md`
- For interface implementations, see `/components/task-system/spec/interfaces.md`
- For public API surface, see [Interface:TaskSystem:1.0] in `/components/task-system/api/interfaces.md`
