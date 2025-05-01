# System-Wide Type Definitions [Type:System:1.0]

> This document is the authoritative source for system-wide shared types used across multiple components and defined in IDLs.

## Resource Management Types

```typescript
/**
 * Resource metrics tracking for Handler sessions
 * [Type:System:ResourceMetrics:1.0]
 */
interface ResourceMetrics {
    turns: {
        used: number; // NonNegativeInt
        limit: number; // PositiveInt
        lastTurnAt?: Date;
    };
    context: {
        used: number; // NonNegativeInt
        limit: number; // PositiveInt
        peakUsage: number; // NonNegativeInt
    };
}

/**
 * Resource limits configuration
 * [Type:System:ResourceLimits:1.0]
 */
interface ResourceLimits {
    maxTurns: number; // PositiveInt
    maxContextWindow: number; // PositiveInt (e.g., token count)
    warningThreshold: number; // Float between 0.0 and 1.0
    timeout?: number; // Optional PositiveInt (seconds)
}

/**
 * Individual match result with relevance information
 * [Type:System:MatchTuple:1.0]
 */
interface MatchTuple {
    path: string;  // Path to the matched item (e.g., file path)
    relevance: number;  // Relevance score (0.0 to 1.0)
    excerpt?: string;  // Optional excerpt from the matched content
}

/**
 * Result of associative matching operations (Memory System output)
 * [Type:System:AssociativeMatchResult:1.0]
 */
interface AssociativeMatchResult {
    context_summary: string;  // Summarized context information
    matches: MatchTuple[];  // List of matching items with relevance scores
    error?: string;  // Error message if the matching operation failed
}

```

## Error Types

```typescript
/**
 * Reasons for task failure
 * [Type:System:TaskFailureReason:1.0]
 */
type TaskFailureReason =
    | 'context_retrieval_failure'
    | 'context_matching_failure'
    | 'context_parsing_failure'
    | 'xml_validation_failure' // May become less relevant with Sexp focus
    | 'output_format_failure'
    | 'execution_timeout'
    | 'execution_halted'
    | 'subtask_failure'
    | 'input_validation_failure'
    | 'template_not_found' // Added common failure reason
    | 'tool_execution_error' // Added common failure reason
    | 'llm_error' // Added common failure reason
    | 'unexpected_error';

// Forward declaration for TaskError used within TaskFailureDetails
interface TaskErrorBase { message: string; content?: string; type: string; }

/**
 * Detailed information for task failures
 * [Type:System:TaskFailureDetails:1.0]
 */
interface TaskFailureDetails {
    partial_context?: any;
    context_metrics?: any;
    violations?: string[];
    subtaskRequest?: any; // Type: SubtaskRequest (defined below) - Use Any for simplicity if nesting is complex
    subtaskError?: TaskErrorBase; // Recursive TaskError structure
    nestingDepth?: number; // NonNegativeInt
    s_expression_environment?: Record<string, any>;
    failing_expression?: string;
    script_stdout?: string;
    script_stderr?: string;
    script_exit_code?: number;
}

/**
 * Standardized task error structure (Discriminated Union)
 * [Type:System:TaskError:1.0]
 */
type TaskError =
    | {
        type: 'RESOURCE_EXHAUSTION';
        resource: 'turns' | 'context' | 'output';
        message: string;
        metrics?: { used: number; limit: number; };
        content?: string;
    }
    | {
        type: 'TASK_FAILURE';
        reason: TaskFailureReason;
        message: string;
        content?: string;
        notes?: Record<string, any>;
        details?: TaskFailureDetails;
    }
    | {
        type: 'INVALID_OUTPUT';
        message: string;
        content?: string;
        violations?: string[];
    }
    | {
        type: 'VALIDATION_ERROR';
        message: string;
        path?: string;
        invalidModel?: boolean;
        content?: string; // Added content for consistency
    }
    | {
        type: 'XML_PARSE_ERROR'; // Keep for potential legacy XML handling
        message: string;
        location?: string;
        content?: string;
    };

```

## Context Management Types

```typescript
/**
 * Defines context management settings using the standardized three-dimensional model.
 * Used by TaskSystem and Handlers.
 * Note: fresh_context="enabled" cannot be combined with inherit_context="full" or "subset"
 * [Type:System:ContextManagement:1.0]
 */
interface ContextManagement {
    /** Controls whether parent context is inherited */
    inheritContext: 'full' | 'none' | 'subset';

    /** Controls whether outputs from prior steps are accumulated */
    accumulateData: boolean;

    /** Controls what information is preserved during sequential task execution */
    accumulationFormat: 'full_output' | 'notes_only';

    /** Controls whether new context is fetched via associative matching */
    freshContext: 'enabled' | 'disabled';
}

/**
 * Default context management settings for atomic tasks invoked as subtasks
 * [Type:System:SubtaskContextDefaults:1.0]
 */
const SUBTASK_CONTEXT_DEFAULTS: ContextManagement = {
    inheritContext: 'subset',
    accumulateData: false,
    accumulationFormat: 'notes_only',
    freshContext: 'enabled'
};

/**
 * Input structure for Memory System context requests.
 * Used by TaskSystem and SexpEvaluator to request context.
 * [Type:System:ContextGenerationInput:5.0] // Incremented version
 */
interface ContextGenerationInput {
    /** Optional: Template description */
    templateDescription?: string;
    /** Optional: Template type */
    templateType?: string; // e.g., "atomic"
    /** Optional: Template subtype */
    templateSubtype?: string; // e.g., "standard", "evaluator"

    /** Optional: Explicit query string (used by Sexp get_context or direct query) */
    query?: string;

    /** Optional: Inputs provided to the task/template */
    inputs?: Record<string, any>;

    /** Optional: Context inherited from parent task/environment */
    inheritedContext?: string;
    /** Optional: String summarizing accumulated outputs from previous steps */
    previousOutputs?: string;

    /**
     * Optional: Strategy for associative matching. Defaults to 'content' if omitted.
     * 'content': Retrieve full file content for LLM analysis (default).
     * 'metadata': Use pre-generated metadata strings for LLM analysis.
     */
    matching_strategy?: 'content' | 'metadata';
}
```

## Task Execution Types

```typescript
/**
 * Task execution status enum
 * [Type:System:ReturnStatus:1.0]
 */
type ReturnStatus = "COMPLETE" | "CONTINUATION" | "FAILED";

/**
 * Core task type enum (now only atomic defined in XML/registered directly)
 * Composition handled by S-expression DSL.
 * [Type:System:TaskType:1.0]
 */
type TaskType = "atomic";

/**
 * Atomic task subtype enum
 * [Type:System:AtomicTaskSubtype:1.0]
 */
type AtomicTaskSubtype = "standard" | "subtask" | "director" | "evaluator" | "associative_matching"; // Added matching

/**
 * Handler configuration parameters
 * [Type:System:HandlerConfig:1.0]
 */
interface HandlerConfig {
    provider: string;  // e.g., "anthropic", "openai"
    maxTurns: number; // PositiveInt
    maxContextWindowFraction: number; // Float between 0.0 and 1.0
    defaultModel?: string;
    systemPrompt: string; // Base system prompt
    tools?: string[];  // Tool types needed ("file_access", "bash", etc.) - Informational
}

/**
 * Task execution result structure returned by TaskSystem and Handlers.
 * [Type:System:TaskResult:1.0] // Renamed from TaskSystem specific
 */
interface TaskResult {
    /** Output content from the task execution. Complete or partial. */
    content: string;
    /** Execution status of the task. */
    status: ReturnStatus; // COMPLETE, CONTINUATION, FAILED
    /** Optional free-form criteria description (e.g., for evaluator selection) */
    criteria?: string;
    /** Parsed content if output was successfully parsed (e.g., JSON). */
    parsedContent?: any;
    /** Task-level metadata about execution, resource usage, errors etc. */
    notes: {
        dataUsage?: string;
        successScore?: number; // Optional score (0.0-1.0)
        parseError?: string; // Present when parsing `content` fails
        error?: TaskError; // Embed structured error info here instead of just message?
        [key: string]: any; // Allow extension
    };
}

/**
 * Subtask Request structure used by Dispatcher and SexpEvaluator to invoke tasks via TaskSystem.
 * Based on src/task_system/task_system_IDL.md execute_atomic_template args.
 * [Type:System:SubtaskRequest:1.0]
 */
interface SubtaskRequest {
    /** Type of subtask ('atomic' is the only directly executable type now) */
    type: TaskType; // Should be "atomic"

    /** Name or identifier of the specific atomic template to execute */
    name: string; // Added 'name' field based on how execute_atomic_template finds templates

    /** Description of the subtask (for logging/context) */
    description?: string; // Made optional as name is primary identifier

    /** Input parameters for the subtask */
    inputs: Record<string, any>;

    /** Optional hints for template selection (less relevant now with direct name lookup) */
    template_hints?: string[];

    /** Optional context management overrides */
    context_management?: Partial<ContextManagement>; // Use Partial for overrides

    /** Optional maximum nesting depth override */
    max_depth?: number; // PositiveInt

    /**
     * Specific files to include in subtask context.
     * Takes precedence over context management fetching for these specific files.
     */
    file_paths?: string[];
}

/**
 * Specialized result structure potentially returned by 'evaluator' subtype tasks.
 * Extends the base TaskResult with evaluation-specific notes.
 * [Type:System:EvaluationResult:1.0]
 */
interface EvaluationResult extends TaskResult {
    notes: TaskResult['notes'] & { // Intersect with base notes type
        success: boolean;        // Whether the evaluation passed
        feedback: string;        // Human-readable feedback message
        details?: {              // Optional structured details
            metrics?: Record<string, number>;
            violations?: string[];
            suggestions?: string[];
            [key: string]: any;
        };
        [key: string]: any; // Allow other notes inherited from TaskResult['notes']
    };
}

```
