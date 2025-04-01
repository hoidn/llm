# Evaluator Implementation Design

This document describes the implementation design of the Evaluator component.

## Lexical Environment Model

The Environment class implements lexical scoping for DSL variables through nested environments. This is strictly for variable binding and lookup - completely separate from template matching or context management:

- Maintains variable bindings at each scope level via `bindings` map
- Supports variable lookup through parent scopes via `outer` reference
- Creates child scopes with additional bindings via `extend` method
- Resolves variables through lexical chain with `find` method

```typescript
// Example Environment implementation
class Env implements Environment {
    constructor(public bindings: Record<string, any> = {}, public outer?: Environment) {}
    find(varName: string): any {
        return (varName in this.bindings)
            ? this.bindings[varName]
            : this.outer ? this.outer.find(varName) : throw new Error(`Variable ${varName} not found`);
    }
    extend(bindings: Record<string, any>): Environment {
        return new Env(bindings, this);
    }
}
```

## Nested Environment Model for Function Templates

Function calls create new environments with parameter bindings:

```typescript
// Function call evaluation
function evaluateFunctionCall(call: FunctionCallNode, env: Environment): Promise<any> {
  // 1. Lookup the template in the TaskLibrary
  const template = env.find("taskLibrary").get(call.templateName);
  
  // 2. Evaluate all arguments in the caller's environment
  const argValues = await Promise.all(
    call.arguments.map(arg => evaluateArgument(arg, env))
  );
  
  // 3. Create a new environment with parameter bindings
  const funcEnv = env.extend({});
  for (let i = 0; i < template.parameters.length; i++) {
    funcEnv.bindings[template.parameters[i]] = argValues[i];
  }
  
  // 4. Evaluate the template body in the new environment
  return evaluateTask(template.body, funcEnv);
}
```

This ensures proper variable scoping where templates can only access their explicitly declared parameters, not the caller's entire environment.

## Template Substitution Process

The Evaluator is solely responsible for resolving all template variables before passing tasks to the Handler. This template substitution phase occurs after task selection but before execution:

```typescript
// Template substitution in Evaluator
function resolveTemplateVariables(task: Task, env: Environment): Task {
  // Create a copy to avoid modifying the original
  const resolvedTask = {...task};
  
  // Apply appropriate substitution rules based on task type
  if (task.isFunctionTemplate && task.parameters) {
    // For function templates, create isolated environment with only parameters
    const funcEnv = new Environment({});
    for (const param of task.parameters) {
      funcEnv.bindings[param] = env.find(param);
    }
    resolvedTask.taskPrompt = substituteVariables(task.taskPrompt, funcEnv);
    if (resolvedTask.systemPrompt) {
      resolvedTask.systemPrompt = substituteVariables(task.systemPrompt, funcEnv);
    }
  } else {
    // For standard templates, use the full environment
    resolvedTask.taskPrompt = substituteVariables(task.taskPrompt, env);
    if (resolvedTask.systemPrompt) {
      resolvedTask.systemPrompt = substituteVariables(task.systemPrompt, env);
    }
  }
  
  return resolvedTask;
}
```

The Evaluator ensures that all placeholder substitutions (e.g., `{{variable_name}}`) are completed before dispatching to the Handler, ensuring all execution happens with fully resolved inputs. This includes resolving variables in both direct templates and function templates, with different resolution rules for each type. Associative matching tasks operate on the final, substituted task description.

## Function Call Processing

Function calls use direct parameter passing with lexical isolation:

1. **Template Lookup**: Retrieve template by name from TaskLibrary
2. **Argument Resolution**: For each argument in the caller's environment:
   - For string values: Try variable lookup first, fallback to literal value
   - For AST nodes: Recursively evaluate in caller's environment
3. **Fresh Environment Creation**: Create new environment with parameter bindings
   - Parameters explicitly bound to evaluated argument values
   - No implicit access to caller's variables
4. **Isolated Execution**: Execute template in this clean environment

This process maintains clean scope boundaries, preventing unintended variable access.

### Argument Resolution Strategy

For string arguments, a two-step resolution occurs:
```typescript
function resolveArgument(arg: string, env: Environment): any {
  // First try to find it as a variable in the environment
  try {
    return env.find(arg);
  } catch (e) {
    // If not found as a variable, treat as a literal
    return arg;
  }
}
```
This allows for passing both variable references and literal values as function arguments.

## Metacircular Approach

The system's evaluator is a "metacircular evaluator," meaning:
> The interpreter (Evaluator) uses LLM-based operations as its basic building blocks, while the LLM also uses the DSL or AST from the evaluator for self-decomposition tasks.

In practice, this means:  
- The Evaluator calls an LLM to run "atomic" tasks or to do "decomposition."  
- The LLM might generate or refine structured XML tasks that, in turn, the Evaluator must interpret again.  
- This cycle repeats until the tasks can be successfully executed without exceeding resource or output constraints.

Because of this, the Evaluator is partially "self-hosting": it leverages the same LLM to break down tasks that can't be executed directly.

## Context Management Implementation

The Evaluator manages all dimensions of the context management model:

### Standard Three-Dimensional Model
1. **Inherited Context**: The parent task's context, controlled by `inherit_context` setting ("full", "none", or "subset").
2. **Accumulated Data**: The step-by-step outputs collected during sequential execution, controlled by `accumulate_data` setting.
3. **Fresh Context**: New context generated via associative matching, controlled by `fresh_context` setting.

### Explicit File Inclusion
In addition to the standard model, the Evaluator supports explicit file inclusion through the `file_paths` feature:
- Files specified via `file_paths` are always included in context
- This operates orthogonally to the three-dimensional model
- File retrieval is delegated to Handler tools
- File content is formatted with XML tags indicating source paths

These dimensions are configured through the standardized context management XML structure:
```xml
<context_management>
    <inherit_context>full|none|subset</inherit_context>
    <accumulate_data>true|false</accumulate_data>
    <accumulation_format>notes_only|full_output</accumulation_format>
    <fresh_context>enabled|disabled</fresh_context>
</context_management>
```

When contexts are needed, the Evaluator decides which dimensions to include based on these settings.

## Associative Matching Invocation

When executing a sequential task step with `<inherit_context>none</inherit_context>` but `<accumulate_data>true</accumulate_data>` and `<fresh_context>enabled</fresh_context>`, the Evaluator:
1. Calls `MemorySystem.getRelevantContextFor()` with prior steps' partial results
2. Merges the returned `AssociativeMatchResult` into the next step's environment
3. Maintains complete separation from the Handler's resource management

### Evaluator Responsibilities for Associative Matching

* **Initiation**: The Evaluator is the *sole* caller of `MemorySystem.getRelevantContextFor()`.
* **Sequential History**: It retrieves partial outputs from `SequentialHistory` (the step-by-step data structure it maintains).
* **Context Merging**: If the step is configured for accumulation, the Evaluator incorporates the match results into the upcoming step's environment.
* **Error Handling**: Any failure to retrieve context (e.g., a memory system error) is handled through the existing `TASK_FAILURE` or resource-related error flow. No new error category is introduced.
* **No Handler Involvement**: The Handler does not participate in the retrieval or assembly of this context data, beyond tracking resource usage at a high level.

## Sequential Task History

When evaluating sequential tasks, the Evaluator implements the Sequential Task Management pattern [Pattern:SequentialTask:2.0] as defined in the system architecture. This includes:

- Maintaining explicit task history for each sequential operation
- Preserving step outputs until task completion or failure
- Implementing resource-aware storage with potential summarization
- Including partial results in error responses for failed sequences

The Evaluator is responsible for tracking this history independent of the Handler's resource management and implementing the appropriate accumulation behavior based on the task's context_management configuration.

## Subtask Spawning Implementation

The Evaluator implements the subtask tool mechanism as defined in [Pattern:ToolInterface:1.0], using the CONTINUATION status internally. From the LLM's perspective, these appear as tools but are implemented using the subtask spawning protocol.

Key responsibilities of the Evaluator in this pattern:
- Handling CONTINUATION requests from subtask tool calls
- Managing context according to the specified configuration
- Coordinating script execution when required
- Passing evaluation results back to the Director

When creating subtasks with explicit file paths:
```typescript
// The file_paths field takes precedence over associative matching
subtask_request = {
  type: "atomic",
  description: "Analyze specific modules",
  inputs: { /* parameters */ },
  context_management: { inherit_context: "subset" },
  file_paths: ["/src/main.py", "/src/utils.py"]
}
```
The Evaluator ensures these files are fetched and included in the subtask's context before execution.

## Tool Interface Integration

When the LLM invokes a subtask-based tool:
1. The Handler transforms this into a CONTINUATION with SubtaskRequest
2. The Evaluator receives and processes this request
3. Template selection occurs via associative matching
4. Execution follows the subtask spawning protocol
5. Results are returned to the parent task
