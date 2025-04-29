# Compiler Interfaces [Interface:Compiler:1.0]

> This document is the authoritative source for the Compiler public API.

## Overview

The Compiler handles AST generation and transformation for task execution. It provides the infrastructure for parsing and processing task specifications.

## Core Interface

```typescript
/**
 * Compiler interface for AST generation and transformation
 * [Interface:Compiler:1.0]
 */
interface Compiler {
    /**
     * Parse XML into an AST
     * 
     * @param xml - The XML to parse
     * @returns The parsed AST node
     */
    parse(xml: string): ASTNode;
    
    /**
     * Parse an operator from XML
     * 
     * @param xml_operator - The XML operator to parse
     * @returns The parsed operator
     */
    parse_operator(xml_operator: string): Operator;
    
    /**
     * Generate initial AST from query
     * 
     * @param query - The natural language query
     * @returns The bootstrapped AST node
     */
    bootstrap(query: string): ASTNode;
    
    /**
     * Reparse failed task with error context
     * 
     * @param failed_task - The failed task
     * @param error - The execution error
     * @returns Promise resolving to the reparsed AST node
     */
    reparse(failed_task: string, error: ExecutionError): Promise<ASTNode>;
    
    /**
     * Translate prompt to XML using LLM
     * 
     * @param prompt - The prompt to translate
     * @returns Promise resolving to the translated XML element
     */
    llm_translate(prompt: string): Promise<Element>;
}
```

## Type References

For system-wide types, see [Type:System:1.0] in `/system/contracts/types.md`.
For Evaluator types, see [Type:Evaluator:1.0] in `/components/evaluator/spec/types.md`.

## Integration Points

- **Task System**: Uses Compiler for task parsing
- **Evaluator**: Uses Compiler for reparse operations
- **Handler**: Used for LLM translation

## Contract References

For integration contract details, see [Contract:Integration:CompilerTask:1.0] in `/system/contracts/interfaces.md`.
# Compiler Interfaces [Interface:Compiler:1.0] (Simplified)

> This document is the authoritative source for the Compiler public API, reflecting its current primary role.

## Overview

The Compiler handles validation of atomic task XML definitions. Its role in AST generation for workflows is superseded by the SexpEvaluator.

## Core Interface (Conceptual)

```typescript
/**
 * Simplified Compiler interface focused on validation.
 * Actual implementation might vary.
 * [Interface:Compiler:1.0]
 */
interface Compiler {
    /**
     * Validate an XML string representing an atomic task against the schema.
     *
     * @param xml_string - The XML string to validate.
     * @returns Validation result (e.g., boolean or object with errors/warnings).
     * @throws {XMLSchemaError} If validation fails catastrophically.
     */
    validate_atomic_task_xml(xml_string: string): ValidationResult; // Define ValidationResult structure

    /**
     * (Future Scope) Translate natural language prompt to S-expression.
     *
     * @param prompt - The natural language prompt.
     * @returns Promise resolving to the translated S-expression string.
     */
    // llm_translate_to_sexp?(prompt: string): Promise<string>;
}

// Define helper types if needed
interface ValidationResult {
    isValid: boolean;
    errors?: string[];
    warnings?: string[];
}
```

## Integration Points

*   **Task System**: Uses `validate_atomic_task_xml` during template registration.

## Deprecated Methods (from previous designs)
*   `parse(xml)` - AST parsing now handled by SexpEvaluator for S-expressions.
*   `parse_operator(xml)` - Related to old AST model.
*   `bootstrap(query)` - Related to old AST model.
*   `reparse(failed_task, error)` - Reparsing logic may shift or be removed.
