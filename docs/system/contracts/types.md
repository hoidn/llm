# System-Wide Type Definitions [Type:System:1.0]

> This document is the authoritative source for system-wide shared types.

## Resource Management Types

```typescript
/**
 * Resource metrics tracking for Handler sessions
 * [Type:System:ResourceMetrics:1.0]
 */
interface ResourceMetrics {
    turns: {
        used: number;
        limit: number;
        lastTurnAt: Date;
    };
    context: {
        used: number;
        limit: number;
        peakUsage: number;
    };
}

/**
 * Resource limits configuration
 * [Type:System:ResourceLimits:1.0]
 */
interface ResourceLimits {
    maxTurns: number;
    maxContextWindow: number;
    warningThreshold: number;
    timeout?: number;
}
```

## Error Types

```typescript
/**
 * Standardized task error structure
 * [Type:System:TaskError:1.0]
 */
type TaskError = 
    | { 
        type: 'RESOURCE_EXHAUSTION';
        resource: 'turns' | 'context' | 'output';
        message: string;
        metrics?: { used: number; limit: number; };
        content?: string;  // May contain partial output before exhaustion
    }
    | { 
        type: 'TASK_FAILURE';
        reason: TaskFailureReason;
        message: string;
        content?: string;  // Contains partial output if available
        notes?: Record<string, any>;  // Contains task metadata
        details?: {
            // Common fields for any failure
            partial_context?: any; // Context data retrieved before failure
            context_metrics?: any; // Metrics related to context operations
            violations?: string[]; // e.g., Schema validation violations

            // Fields for subtask failures (within atomic or S-expression)
            subtaskRequest?: SubtaskRequest; // The request that failed
            subtaskError?: TaskError;       // The actual error from the subtask
            nestingDepth?: number;          // Depth at which subtask failed

            // Fields for S-expression evaluation failures
            s_expression_environment?: Record<string, any>; // Environment state at failure
            failing_expression?: string; // The S-expression form that failed

            // Fields for script execution failures
            script_stdout?: string;
            script_stderr?: string;
            script_exit_code?: number;

            // Other error-specific details can be added here
        };
    }
    | {
        type: 'INVALID_OUTPUT'; // Kept for cases where output is structurally invalid (e.g., malformed XML/JSON) before format validation
        message: string;
        content?: string;  // The invalid output
        violations?: string[];
    }
    | { 
        type: 'VALIDATION_ERROR';
        message: string;
        path?: string;
        invalidModel?: boolean;
    }
    | { 
        type: 'XML_PARSE_ERROR';
        message: string;
        location?: string;
        content?: string;  // The unparseable content
    };

/**
 * Reasons for task failure
 * [Type:System:TaskFailureReason:1.0]
 */
type TaskFailureReason = 
    | 'context_retrieval_failure'
    | 'context_matching_failure'
    | 'context_parsing_failure'
    | 'xml_validation_failure'
    | 'output_format_failure'
    | 'execution_timeout'
    | 'execution_halted'
    | 'subtask_failure'
    | 'input_validation_failure'
    | 'unexpected_error';
```

## Context Management Types

```typescript
/**
 * Defines context management settings using the standardized three-dimensional model.
 * Note: fresh_context="enabled" cannot be combined with inherit_context="full" or "subset"
 * [Type:System:ContextManagement:1.0]
 */
interface ContextManagement {
    /**
     * Controls whether parent context is inherited
     * - full: Complete inheritance of parent context
     * - none: No inheritance from parent
     * - subset: Selective inheritance based on relevance
     */
    inheritContext: 'full' | 'none' | 'subset';
    
    /**
     * Controls whether outputs from prior steps are accumulated
     */
    accumulateData: boolean;
    
    /**
     * Controls what information is preserved during sequential task execution:
     * - notes_only: Only the notes field is preserved (default)
     * - full_output: Both content and notes fields are preserved
     */
    accumulationFormat: 'full_output' | 'notes_only';
    
    /**
     * Controls whether new context is fetched via associative matching
     * - enabled: Fresh context is retrieved for this task
     * - disabled: No fresh context retrieval
     */
    freshContext: 'enabled' | 'disabled';
}

/**
 * Default context management settings for atomic tasks invoked as subtasks
 * (e.g., via CONTINUATION or `call-atomic-task` with subtype='subtask')
 * [Type:System:SubtaskContextDefaults:1.0]
 */
const SUBTASK_CONTEXT_DEFAULTS: ContextManagement = {
    inheritContext: 'subset', // Changed default based on typical subtask usage
    accumulateData: false,
    accumulationFormat: 'notes_only',
    freshContext: 'enabled'
};
```

## Task Execution Types

```typescript
/**
 * Task execution status
 * [Type:System:ReturnStatus:1.0]
 */
type ReturnStatus = "COMPLETE" | "CONTINUATION" | "FAILED";

/**
 * Core task type (now only atomic defined in XML)
 * [Type:System:TaskType:1.0]
 */
type TaskType = "atomic"; // Composition handled by S-expression DSL
// Script execution is likely invoked via an S-expression primitive e.g., (system:run_script ...)

/**
 * Atomic task subtypes
 * [Type:System:AtomicTaskSubtype:1.0]
 */
type AtomicTaskSubtype = "standard" | "subtask" | "director" | "evaluator";

/**
 * Handler configuration
 * [Type:System:HandlerConfig:1.0]
 */
interface HandlerConfig {
    provider: string;  // e.g., "anthropic", "openai"
    maxTurns: number;
    maxContextWindowFraction: number;
    defaultModel?: string;
    systemPrompt: string;
    tools?: string[];  // Tool types needed ("file_access", "bash", etc.)
}
```

## Cross-References

- For XML schema definitions, see [Contract:Tasks:TemplateSchema:1.0] in `/system/contracts/protocols.md`
- For Memory System types, see [Type:Memory:3.0] in `/components/memory/spec/types.md`
- For Task System types, see [Type:TaskSystem:1.0] in `/components/task-system/spec/types.md`
- For resource management contracts, see [Contract:Resources:1.0] in `/system/contracts/resources.md`
