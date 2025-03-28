# Evaluator Types [Type:Evaluator:1.0]

> This document is the authoritative source for Evaluator specific types.

```typescript
/**
 * AST Node interface
 * [Type:Evaluator:ASTNode:1.0]
 */
interface ASTNode {
    type: string;
    content: string;
    children?: ASTNode[];
    metadata?: Record<string, any>;
    operatorType?: string;
    outputFormat?: {
        type: "json" | "text";
        schema?: string;  // Basic type: "object", "array", "string", etc.
    };
}

/**
 * Lexical Environment for variable scoping
 * Responsible only for variable bindings and lookups
 * [Type:Evaluator:Environment:1.0]
 */
interface Environment {
    /**
     * Current variable bindings at this scope level
     */
    bindings: Record<string, any>;
    
    /**
     * Reference to outer/parent environment for lexical lookup chain
     */
    outer?: Environment;
    
    /**
     * Perform a lexical lookup for varName in this environment chain
     * @param varName Variable name to look up
     * @returns The variable value if found
     * @throws Error if variable not found in this or any outer environment
     */
    find(varName: string): any;
    
    /**
     * Create a new child environment with additional bindings
     * @param bindings New variable bindings to add
     * @returns A new Environment with the added bindings
     */
    extend(bindings: Record<string, any>): Environment;
}

/**
 * Function Call interface
 * [Type:Evaluator:FunctionCall:1.0]
 */
interface FunctionCall extends ASTNode {
    funcName: string;
    args: ASTNode[];
}

/**
 * Operator Specification
 * [Type:Evaluator:OperatorSpec:1.0]
 */
interface OperatorSpec {
    type: string;
    subtype?: string;
    inputs: Record<string, string>;
    disableReparsing?: boolean;
}

/**
 * Sequential History tracking
 * [Type:Evaluator:SequentialHistory:1.0]
 */
interface SequentialHistory {
    outputs: TaskOutput[];
    metadata: {
        startTime: Date;
        currentStep: number;
        resourceUsage: any;
    };
}

/**
 * Task Output tracking
 * [Type:Evaluator:TaskOutput:1.0]
 */
interface TaskOutput {
    stepId: string;  // or step index
    notes: any;      // Task notes field (always preserved, may include partial results)
    timestamp: Date;
}
```

## Cross-References

For system-wide types, see [Type:System:1.0] in `/system/contracts/types.md`.
For Task System types, see [Type:TaskSystem:1.0] in `/components/task-system/spec/types.md`.
