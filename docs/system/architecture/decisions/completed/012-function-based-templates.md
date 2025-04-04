# ADR 12: Function-Based Template Model

## Status
Accepted

## Context
The system needed a cleaner approach to variable scoping and parameter passing between tasks. The previous model allowed implicit access to parent environment variables through `{{variable_name}}` syntax, which created unclear dependencies and made reasoning about scope difficult.

## Decision
Implement a function-based template model with explicit parameter declarations:

1. **Template Definition**
   - Templates explicitly declare parameters using a `params` attribute
   - Each template has its own lexical scope containing only its parameters
   - Templates are registered in a central TaskLibrary

2. **Function Calling**
   - Function calls use positional arguments evaluated in the caller's context
   - Arguments can be literals, variable references, or nested expressions
   - A new environment is created for each function call with bindings for parameters
   - No implicit access to the caller's environment is allowed

3. **XML Representation**
   ```xml
   <!-- Template definition -->
   <template name="analyze_data" params="dataset,config">
     <task>
       <description>Analyze {{dataset}} using {{config}}</description>
     </task>
   </template>

   <!-- Function call -->
   <call template="analyze_data">
     <arg>weather_data</arg>
     <arg>standard_config</arg>
   </call>
   ```

### Function Call Syntax Options

The system supports two equivalent syntaxes for function calls:

1. **XML-based syntax**:
   ```xml
   <call template="analyze_data">
     <arg>weather_data</arg>
     <arg>standard_config</arg>
   </call>
   ```

2. **Template-level syntax** (within variable substitution fields):
   ```
   {{analyze_data(weather_data, standard_config)}}
   ```

Both syntaxes are translated to the same internal representation (FunctionCallNode) and follow identical execution semantics, parameter binding, and environment handling. The template-level syntax provides a more natural way to embed function calls within text content, while the XML syntax offers more explicit structure for standalone function calls.

This dual-syntax approach balances architectural purity with practical usability. By translating template-level function calls to the standard AST structure, we maintain a single execution path while offering a more user-friendly syntax for common use cases.

## Consequences
- **Positive**
  - Clear data dependencies between components
  - Improved reasoning about variable scope
  - Better encapsulation of implementation details
  - Foundation for more advanced functional patterns
  - Explicit parameter documentation

- **Negative**
  - Slightly more verbose syntax
  - Migration effort for existing templates
  - Additional parsing complexity

## Implementation
The implementation includes:
- New AST node types: TemplateNode, FunctionCallNode, ArgumentNode
- Environment extension mechanism for creating child scopes
- Parameter binding during function calls
- Argument resolution strategy for variable references vs. literals

The full ADR with implementation details has been moved outside the docs/ tree to save space.
