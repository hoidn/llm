# S-expression Evaluator Implementation Design

This document describes the implementation design of the S-expression Evaluator component.

## S-expression Lexical Environment Model

The Environment class implements lexical scoping for S-expression variables and function definitions through nested environments:

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

## Function Call Evaluation (S-expression)

S-expression function calls (to user-defined functions or XML templates) create new environments with parameter bindings:

```typescript
```typescript
// Conceptual S-expression evaluation loop
async function evaluateSExpr(expr: SExpr, env: Environment): Promise<any> {
  if (isAtom(expr)) {
    return env.lookup(expr); // Or handle literals
  } else if (isList(expr)) {
    const operator = expr[0];
    const args = expr.slice(1);

    if (isSpecialForm(operator)) {
      return evaluateSpecialForm(operator, args, env); // e.g., if, bind, let, define
    } else {
      // Function call
      const func = await evaluateSExpr(operator, env); // Evaluate the operator itself
      const evaluatedArgs = await Promise.all(args.map(arg => evaluateSExpr(arg, env)));

      if (isPrimitive(func)) {
        return func.execute(evaluatedArgs, env); // Primitives might need env
      } else if (isUserFunction(func)) {
        // 1. Create new environment extending func's closure env
        const funcEnv = func.closureEnv.extend({});
        // 2. Bind parameters to evaluatedArgs
        bindParameters(func.params, evaluatedArgs, funcEnv);
        // 3. Evaluate function body in the new environment
        return await evaluateSExpr(func.body, funcEnv);
      } else if (isAtomicTaskTemplate(func)) {
         // Handle calling an XML atomic task template
         const subtaskRequest = createSubtaskRequest(func.name, evaluatedArgs);
         // Call Task System to execute the atomic task
         return await taskSystem.execute_subtask_directly(subtaskRequest, env); // Pass caller env for {{}} substitution
      } else {
        throw new Error(`Not a function: ${operator}`);
      }
    }
  }
}
```

This ensures proper lexical scoping for S-expression functions and isolates execution environments for calls to both S-expression functions and XML atomic task templates.

## Template Substitution Process (Handled by Task System)

The S-expression Evaluator itself does *not* handle the `{{variable_name}}` substitution within atomic task XML templates.

When the S-expression evaluator invokes an atomic task via `TaskSystem.execute_subtask_directly(request, env)`, it passes the *current S-expression environment* (`env`). The Task System component is then responsible for:
1. Retrieving the atomic task's XML template definition.
2. Using the provided S-expression environment (`env`) to resolve all `{{...}}` placeholders within the template's fields (like `<instructions>`, `<system>`, etc.).
3. Passing the fully resolved atomic task content to the Handler for execution.

This keeps the concerns separate: the S-expression Evaluator manages the DSL environment and workflow, while the Task System manages the specifics of preparing and executing individual atomic tasks based on their XML definitions and the calling environment.

## S-expression Function Call Processing

Function calls within the S-expression DSL follow the evaluation logic described earlier:
1.  **Function Lookup**: Find the function definition (S-expression `define` or XML `<template>`) in the current environment or Task System library.
2.  **Argument Evaluation**: Evaluate each argument expression in the *caller's* S-expression environment.
3.  **New Environment**: Create a fresh lexical environment for the function execution.
4.  **Parameter Binding**: Bind the evaluated argument values to the function's parameter names in the new environment.
5.  **Body Execution**: Evaluate the function's body (S-expression code or invoking the atomic task from an XML template) within this new environment.

This ensures lexical isolation.

### Template-Level Function Calls (`{{...}}`) - Deprecated?

The `{{function_name(...)}}` syntax within atomic task template fields is likely **deprecated** or has limited use. Complex logic and function composition should now be handled by the S-expression DSL itself. Simple data formatting might still use placeholders, but calls requiring execution logic belong in the S-expression layer.

### Argument Resolution Strategy (S-expression)

Arguments in S-expression function calls are *always* evaluated first in the caller's environment before being passed.
- `(my-func variable)`: `variable` is looked up in the environment, and its *value* is passed.
- `(my-func "literal string")`: The literal string `"literal string"` is passed.
- `(my-func (+ 1 2))`: The expression `(+ 1 2)` is evaluated (to `3`), and the value `3` is passed.

## Metacircular Approach (S-expression Context)

The system retains a metacircular aspect:
> The S-expression Evaluator orchestrates workflows and calls atomic tasks. Some atomic tasks involve LLM calls (via the Handler). An LLM called by an atomic task might generate S-expression code as output, which could then be evaluated by the S-expression Evaluator in a subsequent step.

In practice, this means:
- The S-expression Evaluator executes DSL code.
- DSL code calls atomic tasks (e.g., `(call-atomic-task 'generate-code' ...)`).
- The `generate-code` atomic task invokes an LLM (via Handler) which might return S-expression code as a string.
- Subsequent S-expression code could parse and evaluate this generated code `(eval (parse generated_code_string))`.
- This cycle allows LLMs to generate executable workflow fragments.

The S-expression Evaluator leverages atomic tasks (which may use LLMs) as building blocks, and the output of those blocks can be fed back into the Evaluator.

## Context Management Implementation (via Task System & Primitives)

The S-expression Evaluator itself does not directly manage the three-dimensional context model (`inherit_context`, `accumulate_data`, `fresh_context`). Instead:

-   **Context for Atomic Tasks**: When the S-expression Evaluator calls `TaskSystem.execute_subtask_directly`, the Task System component is responsible for preparing the context for that *specific atomic task execution* based on its effective `<context_management>` settings (defaults merged with overrides from XML and the `SubtaskRequest`). The Task System calls `MemorySystem.getRelevantContextFor` if `fresh_context` is enabled.
-   **Context within S-expression**: The S-expression workflow can explicitly manage context using dedicated primitives:
    *   `(get-context query-details)`: A primitive that likely calls `MemorySystem.getRelevantContextFor` directly, allowing the S-expression to fetch fresh context based on dynamic inputs or descriptions. The result (context string, matches) would be bound to a variable.
    *   `(bind current-context (get-context ...))`: Fetch context and store it.
    *   `(call-atomic-task 'my-task' (context current-context) ...)`: Pass fetched context explicitly to an atomic task (potentially overriding its default context handling, depending on primitive design).
-   **Explicit File Inclusion**: Can be handled either by:
    *   Specifying `file_paths` in the `SubtaskRequest` when calling `TaskSystem.execute_subtask_directly`.
    *   Having an S-expression primitive like `(read-file path)` that uses the Handler's file access tools.

The responsibility is split: Task System handles context prep for individual atomic tasks based on static/semi-static configuration; the S-expression DSL provides primitives for dynamic context fetching and manipulation within the workflow.

## Associative Matching Invocation

Associative matching (`MemorySystem.getRelevantContextFor`) is invoked either:
1.  By the **Task System** when preparing context for an atomic task if its effective `fresh_context` setting is `enabled`.
2.  Directly by the **S-expression Evaluator** when executing a primitive like `(get-context ...)`.

## Sequential Task History / State Management

Explicit sequential task history (as previously defined for XML sequences) is **removed**. State management within an S-expression workflow relies on:
-   **Lexical Scoping**: Variables bound with `let` are local.
-   **Explicit Binding**: Using `bind` (or similar) to capture the result of one step and pass it to the next.
    ```scheme
    (bind result1 (call-atomic-task 'step1' ...)
      (bind result2 (call-atomic-task 'step2' (input result1))
        (process result2)))
    ```
-   **Accumulators (if needed)**: For reduce-like patterns, state can be passed through recursive calls or dedicated loop primitives.

The S-expression environment holds the state, not a separate history object managed by the Evaluator. Resource management for large intermediate results needs to be considered in the DSL design or handled manually within the workflow.

## Subtask Spawning Implementation (Handling CONTINUATION)

The S-expression Evaluator handles the `CONTINUATION` status when returned by an atomic task it invoked via `TaskSystem.execute_subtask_directly`.

1.  **Detection**: If `execute_subtask_directly` returns a `TaskResult` with `status: "CONTINUATION"` and a valid `subtask_request` in its `notes`.
2.  **Validation**: The Evaluator validates the `subtask_request` (structure, depth limits, cycle detection).
3.  **Invocation**: The Evaluator recursively calls itself or `TaskSystem.execute_subtask_directly` with the new `subtask_request`. It passes the appropriate S-expression environment.
4.  **Result Handling**: The result of the spawned subtask is returned to the point in the S-expression evaluation where the `CONTINUATION` was received. This result can then be bound or used by subsequent S-expression forms.

This allows atomic tasks (potentially involving LLMs) to dynamically request further sub-processing, which is then orchestrated by the S-expression Evaluator. Context for the dynamically spawned subtask is determined by its own request/template settings, following the standard rules. Explicit `file_paths` in the `subtask_request` take precedence.

## Tool Interface Integration (Primitives)

Direct tools (like file access, shell commands) are exposed to the S-expression workflow via dedicated primitives (e.g., `(system:run_script ...)`, `(read-file ...)`).
- The S-expression Evaluator executes these primitives.
- The primitive implementation typically calls the corresponding **Handler** tool execution method.
- Results are returned directly to the S-expression evaluator.

Subtask-based tools (LLM-to-LLM delegation) are implemented using the `CONTINUATION` mechanism described above. An atomic task acts as the "tool" interface for the LLM, returning `CONTINUATION` to trigger the actual subtask execution orchestrated by the S-expression Evaluator.
