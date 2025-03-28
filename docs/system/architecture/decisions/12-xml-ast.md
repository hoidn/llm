# Architecture Decision Record: Function-Based Template Model

## Status
Proposed

## Context
The current system architecture uses two different variable resolution mechanisms for tasks:

1. **Template Substitution** (`{{variable_name}}`) - Placeholders within text content that are replaced with values from the current lexical environment.

2. **Input Binding** (`<input name="data" from="previous_result"/>`) - Explicit binding of inputs to named environment variables.

This dual approach has created several issues:

- **Unclear Variable Scope**: Templates have implicit access to the caller's entire environment.
- **Inconsistent Binding Patterns**: Multiple ways to access variables leads to confusion.
- **Environment Leakage**: No clear boundaries between caller and callee contexts.
- **Implicit Dependencies**: Templates can access variables that aren't explicitly passed.
- **Complex Execution Model**: The Evaluator must handle different resolution mechanisms.
- **Difficult Reasoning**: It's hard to predict which variables a template might access.

This does not align with established programming language patterns where functions have explicit parameters and clear scope boundaries.

## Decision
We will adopt a clean function-based model for templates with the following simplifications:

1. **Templates as Function Definitions**: Each template will explicitly declare its parameters using a simple attribute.
   ```xml
   <template name="analyze_data" params="dataset,config">
     <task>
       <description>Analyze {{dataset}} using {{config}}</description>
     </task>
   </template>
   ```

2. **Function Calls with Positional Arguments**: Template invocation will use positional arguments.
   ```xml
   <call template="analyze_data">
     <arg>weather_data</arg>
     <arg>standard_config</arg>
   </call>
   ```

3. **Strict Scope Boundaries**: Templates can only access their parameters, not the caller's environment.

4. **Single Variable Resolution Mechanism**: Within templates, `{{...}}` only refers to declared parameters.

5. **Simplified Argument Handling**: Arguments are represented with a simplified structure.
   ```typescript
   interface ArgumentNode {
     type: "argument";
     value: string | ASTNode;  // String for variables/literals, ASTNode for nested
   }
   ```

6. **Implicit Template Registration**: Templates are automatically registered in the TaskLibrary during parsing.

## Consequences

### Positive
- **Clearer Mental Model**: Aligns with established function call semantics.
- **Predictable Behavior**: Templates can only access explicitly passed arguments.
- **Simplified Reasoning**: Easy to understand what variables a template needs.
- **Better Encapsulation**: Template internals are hidden from callers.
- **Reduced Verbosity**: Simplified parameter declaration and argument handling.
- **Streamlined Implementation**: Implicit template registration simplifies management.
- **Foundation for Extensions**: Creates a path to named arguments, default values, etc.

### Negative
- **Breaking Change**: Existing templates will need updates.
- **Migration Effort**: Need to identify parameters and update call sites.
- **Implementation Complexity**: Requires updates to parsing and execution.
- **Argument Ambiguity**: String arguments could be variable references or literals, requiring disambiguation.

### Migration Path
1. **Update XML Schema**: Add new elements for template definitions and calls.
2. **Identify Template Parameters**: For each template, identify required parameters.
3. **Add Parameter Declarations**: Update templates with explicit parameter lists.
4. **Convert Call Sites**: Replace current invocation patterns with `<call>` elements.
5. **Update Variable References**: Ensure templates only reference declared parameters.
6. **Deprecate Old Patterns**: Mark `from` attribute as deprecated during transition.

## Implementation Recommendations

### XML Schema Updates
- Add `<template>` with `name` and `params` attributes
- Add `<call>` and `<arg>` elements
- Deprecate the `from` attribute on `<input>` elements

### AST Structure Updates
```typescript
interface TemplateNode {
  type: "template";
  name: string;
  parameters: string[];  // Parameter names in order
  body: TaskNode;        // The actual task implementation
}

interface FunctionCallNode {
  type: "call";
  templateName: string;
  arguments: ArgumentNode[];  // Evaluated in caller's environment
}

interface ArgumentNode {
  type: "argument";
  value: string | ASTNode;  // String for variables/literals, ASTNode for nested
}
```

### TaskLibrary Enhancements
- Automatic registration of templates during parsing
- Lookup functionality for template resolution during function calls
- Validation for parameter count matching argument count
- Proper error handling for missing templates or parameters

/**
 * Argument Resolution Algorithm
 * 
 * 1. For each argument in function call:
 *    a. If argument is string:
 *       i. Try to resolve as variable in caller's environment
 *       ii. If variable exists, use its value
 *       iii. If not, use string as literal value
 *    b. If argument is ASTNode:
 *       i. Recursively evaluate node in caller's environment
 * 
 * 2. Create new environment with parameter-to-argument bindings:
 *    a. Bind each parameter name to its corresponding evaluated argument
 * 
 * 3. Execute template body in new environment:
 *    a. Template can only access explicitly passed parameters
 *    b. No implicit access to caller's environment
 */

### Evaluator Updates
- Implement clean environment creation for each call
- Update variable resolution to only check parameters
- Add proper argument evaluation in caller's context

### Component Interactions
- **Compiler**: Parse templates and function calls into AST nodes, automatically registering templates
- **TaskLibrary**: Store templates and provide lookup functionality
- **Evaluator**: Handle function invocation, argument evaluation, and scope management

## AST Containment Relationships

The new node types integrate with the existing AST structure as follows:

### Hierarchy Integration
All new node types (`TemplateNode`, `FunctionCallNode`, `ArgumentNode`) implement the base `ASTNode` interface, ensuring consistent traversal and evaluation.

### Containment Rules
1. **TemplateNode**
   - Contains a `TaskNode` as its body (any task type)
   - Is stored in the TaskLibrary, not directly in the AST
   - Cannot be contained within other nodes (only top-level)

2. **FunctionCallNode**
   - Can appear anywhere a `TaskNode` might appear
   - Can be contained within:
     - Sequential task steps
     - Reduce operations
     - Nested inputs
     - Other composite structures
   - Contains an array of `ArgumentNode` elements

3. **ArgumentNode**
   - Can only appear as children of `FunctionCallNode`
   - May contain a string (variable reference or literal) or a nested `ASTNode`
   - When containing a nested node, that node is evaluated before being passed as an argument

### Legal Placement Rules
- `<template>` definitions must be at the top level of a template file
- `<call>` elements can appear anywhere a `<task>` element is valid
- `<arg>` elements can only appear as direct children of `<call>` elements

### Traversal Implications
When traversing the AST:
- `TemplateNode` instances are not traversed directly (they exist in the TaskLibrary)
- When a `FunctionCallNode` is encountered, the evaluator:
  1. Looks up the template by name in the TaskLibrary
  2. Evaluates all argument nodes in the current environment
  3. Creates a new environment with parameters bound to argument values
  4. Traverses and evaluates the template's body in this new environment

A template's body can be any task type (atomic, sequential, reduce, etc.), allowing function-based templates to define both simple and complex operations. This enables function composition across all task types in the system, not just atomic tasks.

## Affected Documentation

The following documents will need updates after this ADR is accepted:

1. **Core Contract Documents**
   - `system/contracts/protocols.md` (XML schema)

2. **Type Definition Documents**
   - `components/task-system/spec/types.md` (AST node types)

3. **Implementation Documents**
   - `components/compiler/README.md` (parsing approach)
   - `components/evaluator/README.md` (execution model)
   - `components/task-system/impl/xml-processing.md` (validation rules)

4. **Pattern Documents**
   - `system/architecture/patterns/context-frames.md` (scope rules)

5. **Overview Documents**
   - `system/README.md` and `system/architecture/overview.md` (high-level descriptions)

## Related Decisions
- This builds on [ADR 7: Context Management Standardization]
- This complements [ADR 11: Subtask Spawning Mechanism]
