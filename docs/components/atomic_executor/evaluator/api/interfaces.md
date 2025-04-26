# Evaluator Interfaces [Interface:Evaluator:1.0]

> This document is the authoritative source for the Evaluator public API.

## Overview

The Evaluator is responsible for AST execution, template variable substitution, and error recovery. It orchestrates the step-by-step execution of tasks and manages the environment for variable scoping.

## Core Interface

```typescript
/**
 * Evaluator interface for task execution
 * [Interface:Evaluator:1.0]
 */
interface Evaluator {
    /**
     * Evaluate an AST node in the given environment
     * 
     * @param node - The AST node to evaluate
     * @param env - The environment for variable resolution
     * @param reparse_depth - Optional depth for reparse operations
     * @returns Promise resolving to the evaluation result
     */
    eval(node: ASTNode, env: Environment, reparse_depth?: number): Promise<any>;
    
    /**
     * Handle reparse requests for failed tasks
     * 
     * @param node - The failed AST node
     * @param env - The environment for variable resolution
     * @param depth - Current reparse depth
     * @returns Promise resolving to the reparse result
     */
    handle_reparse(node: ASTNode, env: Environment, depth: number): Promise<any>;
    
    /**
     * Check if an operator is atomic
     * 
     * @param operator - The operator to check
     * @returns Whether the operator is atomic
     */
    is_atomic(operator: any): boolean;
    
    /**
     * Execute an LLM operation
     * 
     * @param operator - The operator to execute
     * @param env - The environment for variable resolution
     * @returns Promise resolving to the LLM result
     */
    execute_llm(operator: any, env: Environment): Promise<any>;
    
    /**
     * Apply an operator with arguments
     * 
     * @param operator - The operator to apply
     * @param args - The arguments to apply
     * @param env - The environment for variable resolution
     * @returns Promise resolving to the application result
     */
    apply(operator: any, args: any[], env: Environment): Promise<any>;
    
    /**
     * Resolve template variables in a string
     * 
     * @param template - The template string
     * @param env - The environment for variable resolution
     * @returns The resolved string
     */
    resolveTemplateVariables(template: string, env: Environment): string;
}
```

## Type References

For Evaluator specific types, see [Type:Evaluator:1.0] in `/components/evaluator/spec/types.md`.
For system-wide types, see [Type:System:1.0] in `/system/contracts/types.md`.

## Integration Points

- **Task System**: Uses Evaluator for task execution
- **Compiler**: Provides AST nodes for evaluation
- **Memory System**: Used for context retrieval
- **Handler**: Used for LLM interactions

## Contract References

For integration contract details, see [Contract:Integration:EvaluatorTask:1.0] in `/system/contracts/interfaces.md`.
