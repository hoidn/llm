# Compiler Requirements

This document outlines the high-level functional and non‑functional requirements for the Compiler component.

## Key Requirements Summary

### Task Understanding
- Parse task requirements and constraints from natural language
- Identify task type and complexity  
- Validate instruction completeness

### XML Schema Requirements
- Parse and validate `<task type="atomic" name="...">` elements and their children (e.g., `description`, `inputs`, `context_management`, `output_format`).
- Ensure required attributes like `name` and `type="atomic"` are present.
- Validate the structure and content of child elements according to the schema.
- Specify input/output formats using `<output_format>`.
- Support task validation criteria if defined.

### AST Structure  
- Node type definitions
- TemplateNode type for function definitions
  - name: Unique template identifier
  - parameters: Array of parameter names
  - body: TaskNode for implementation
  - returns: Optional type information
  
- FunctionCallNode type for invocations
  - templateName: Reference to registered template
  - arguments: Array of ArgumentNodes
  
- ArgumentNode type for function arguments
  - value: String (variable/literal) or nested AST node
  
- Tree validation rules
- Traversal requirements
  - Templates are registered, not traversed directly
  - Function calls trigger template lookup and execution
  - Arguments are evaluated in caller's environment

### Validation Rules
- Input format validation
- Schema compliance
- AST structure validation

## See Also

- [XML Schema Definition](../../../system/contracts/protocols.md)
- [Compiler Interface](../api/interfaces.md)
- [Function-Based Template Pattern](../../../system/architecture/decisions/completed/012-function-based-templates.md)
# Compiler Requirements (Revised)

This document outlines the high-level functional requirements for the Compiler component in the S-expression based architecture.

## Key Requirements Summary

### Atomic Task XML Validation
*   Validate XML strings representing atomic tasks against the official schema defined in [Contract:Tasks:TemplateSchema:1.0].
*   Report validation errors (e.g., missing required elements/attributes, incorrect types, invalid structure).
*   Report validation warnings for non-critical issues.
*   Integrate with `TaskSystem.register_template` to prevent invalid templates from being registered.

### (Future Scope) Natural Language to S-expression Translation
*   (If implemented) Parse natural language task descriptions or commands.
*   Translate the parsed input into a corresponding S-expression workflow string.
*   Handle ambiguity and potentially interact with the user or LLM for clarification.

### (Deprecated) AST Generation/Transformation
*   The Compiler is **no longer** responsible for generating or transforming Abstract Syntax Trees (ASTs) for workflow execution. This is handled by the `SexpEvaluator` for S-expressions.

## See Also
*   [XML Schema Definition](../../../system/contracts/protocols.md)
*   [Compiler Interface](../api/interfaces.md)
