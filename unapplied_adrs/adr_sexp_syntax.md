**Draft ADR: S-Expression Syntax & Evaluation for Programmatic Workflows**

**Status:** Proposed

**Context:**

*   The current `/task type:subtype param=value` command (ADR 17 foundation) allows direct invocation of registered tools and templates but lacks the ability to define multi-step workflows or data pipelines programmatically within the command itself.
*   Use cases like `plan -> map instructions -> map aider` require composing multiple task calls, passing results between them, and iterating over data.
*   Expressing such workflows using alternative proposals like complex JSON structures within parameters was deemed potentially too verbose and cumbersome for command-line use.
*   A concise, compositional syntax is desired for defining these programmatic workflows on the fly.

**Decision:**

1.  Implement support for executing programmatic workflows defined using an **S-expression syntax** (inspired by Lisp/Scheme) passed as an argument to the `/task` command.
2.  Introduce a dedicated **`SExprEvaluator`** component responsible for parsing the S-expression string into an Abstract Syntax Tree (AST) and evaluating that AST.
3.  Introduce a corresponding **`SExprEnvironment`** class to manage variable bindings and lexical scoping *during S-expression evaluation*.
4.  Define and implement a core set of **built-in primitive operators** within the `SExprEvaluator`:
    *   `call`: To invoke existing Handler Direct Tools or TaskSystem Templates.
    *   `bind`: To store intermediate results in named variables within the evaluation scope.
    *   `map`: To apply a task expression to each item in a list.
    *   `get_context`: To dynamically retrieve file context from the `MemorySystem`.
5.  Adapt the REPL and Dispatcher to recognize S-expression input and route it to the `SExprEvaluator`.

**Specification:**

1.  **Syntax:**
    *   Workflows are represented as S-expressions: nested lists enclosed in parentheses `()`.
    *   The first element of a list is typically an operator/primitive symbol.
    *   Supported basic data types within expressions:
        *   **Symbols:** Unquoted sequences of characters representing variables or operators (e.g., `my_var`, `call`, `+`).
        *   **Strings:** Enclosed in double quotes `"..."`.
        *   **Numbers:** Integers (`123`) and potentially floats (`45.6`).
        *   **Lists:** Nested `()` structures.
    *   Example: `(bind result (call math:add (x 10) (y 5)))`

2.  **Parsing:**
    *   The `SExprEvaluator` (or a helper module) must include a parser to transform the input S-expression string into an internal AST.
    *   The target AST structure will likely be nested Python tuples or lists, e.g., `('bind', 'result', ('call', 'math:add', ('x', 10), ('y', 5)))`.
    *   Specific parser implementation (library or custom) is not dictated here, only the requirement.

3.  **`SExprEvaluator` Component:**
    *   **Responsibility:** Takes a parsed S-expression AST node and an `SExprEnvironment`, evaluates the node, and returns the result.
    *   **Core Method:** `eval(node, environment)` recursively evaluates AST nodes.
    *   **Dependencies:** Needs access to the `Handler` instance (for Direct Tool lookup) and the `TaskSystem` instance (for template lookup, `execute_subtask_directly`, and `MemorySystem` access).

4.  **`SExprEnvironment` Component:**
    *   **Responsibility:** Manages variable bindings during S-expression evaluation.
    *   **Features:** Supports nested scopes (parent pointers), `define(name, value)` for `bind`, and `lookup(name)` for variable resolution within the S-expression context.

5.  **Primitive Definitions:**
    *   **`(call identifier <arg>*)`:**
        *   Evaluates each `<arg>` expression recursively using `eval`.
        *   Parses evaluated args into positional and named arguments (e.g., `(x 10)` becomes named `x=10`).
        *   Looks up `identifier`: Checks `Handler.direct_tool_executors` then `TaskSystem.find_template`.
        *   If Direct Tool: Calls the executor function with evaluated args.
        *   If Template: Constructs `SubtaskRequest` (populating `inputs` from evaluated args, potentially `file_paths` if a `(files ...)` arg is present and evaluated). Calls `TaskSystem.execute_subtask_directly(request)`.
        *   Returns the raw result from the tool or the `TaskResult` from the TaskSystem.
    *   **`(bind symbol expression)`:**
        *   Evaluates `expression` using `eval`.
        *   Stores the result in the *current* `SExprEnvironment` scope associated with the unevaluated `symbol`.
        *   Returns the evaluated result.
    *   **`(map task_expression list_expression)`:**
        *   Evaluates `list_expression` (must result in an iterable list).
        *   For each `item` in the list:
            *   Creates a *new nested* `SExprEnvironment` extending the current one.
            *   Defines a special symbol (e.g., `item`) in the nested environment bound to the current list item value.
            *   Evaluates the `task_expression` (typically a `call`) in the nested environment.
        *   Returns a list containing the results of evaluating `task_expression` for each item.
    *   **`(get_context <option>*)`:**
        *   Options are key-value pairs, e.g., `(query "...")`, `(history my_hist_var)`.
        *   Evaluates the *value* expression for each option key (e.g., evaluates `my_hist_var` to get the history string).
        *   Constructs a `ContextGenerationInput` object using the evaluated option values.
        *   Calls `TaskSystem.memory_system.get_relevant_context_for(context_input)`.
        *   Returns the list of file paths (`AssociativeMatchResult.matches`).

6.  **Integration with `/task`:**
    *   `Repl._cmd_task`: Detects if the primary argument starts with `'(`. If so, passes the entire S-expression string to the dispatcher.
    *   `dispatcher.execute_programmatic_task`: Adds a check for S-expression input. If detected, instantiates/calls `SExprEvaluator.eval` instead of performing the tool/template lookup itself. The evaluator's final result is formatted into a `TaskResult`.

7.  **Error Handling:**
    *   The parser should raise specific syntax errors.
    *   The evaluator should raise errors for unbound symbols, incorrect primitive usage, type mismatches (e.g., non-list passed to `map`), and propagate errors from underlying `call` operations.
    *   The dispatcher catches errors from the evaluator and formats them into a standard `TaskResult` with `status: "FAILED"`.

**Consequences:**

*   **Positive:**
    *   Provides a powerful, concise, and compositional way to define programmatic workflows.
    *   Enables on-the-fly workflow definition via the REPL.
    *   Leverages existing task execution primitives (`call` integrates with Handler/TaskSystem).
    *   Creates a foundation for a more fully-featured embedded DSL.
*   **Negative:**
    *   Requires implementation of a new parser and evaluator component.
    *   S-expression syntax has a learning curve for developers unfamiliar with Lisp/Scheme.
    *   Debugging S-expression evaluation can be more complex than debugging sequential Python or XML.
    *   Increases the complexity of the overall system compared to only having pre-defined templates/tools.

**Alternatives Considered:**

*   **JSON Structured Arguments:** More familiar syntax, uses built-in parser, but potentially more verbose and less elegant for composition. Dispatcher becomes the workflow engine.
*   **Pre-defined Workflow Templates:** Simplest approach, but lacks flexibility for on-the-fly workflow definition.

**Related Documents:**

*   ADR 17: Programmatic Task Invocation via Thin Wrappers (Provides `execute_subtask_directly` and Direct Tool concepts used by `call`)
*   PRDs related to workflow execution.
*   `TaskSystem`, `Handler`, `MemorySystem` interface/behavior documents.

