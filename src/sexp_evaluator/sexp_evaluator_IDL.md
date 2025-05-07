// == !! BEGIN IDL TEMPLATE !! ===
module src.sexp_evaluator.sexp_evaluator {

    # @depends_on(src.task_system.task_system.TaskSystem) // To call execute_subtask_directly for atomic tasks
    # @depends_on(src.handler.base_handler.BaseHandler) // To call direct tools via tool_executors
    # @depends_on(src.memory.memory_system.MemorySystem) // To call get_relevant_context_for
    # @depends_on(src.sexp_evaluator.sexp_environment.SexpEnvironment) // Environment for evaluation
    # @depends_on(src.sexp_parser.SexpParser) // For parsing input string (conceptual dependency)
    # @depends_on(src.system.types.TaskResult) // Common return type

    // Interface for the S-expression DSL Evaluator.
    // Responsible for parsing and executing workflows defined in S-expression syntax.
    // This component is the exclusive mechanism for executing all workflow composition logic (sequences, conditionals, loops, etc.).
    // Note: This evaluator focuses on executing workflow logic, special forms, primitives
    // essential for control flow and system interaction (like `get_context`), and invoking
    // registered tasks/tools. Complex data preparation (e.g., multi-source string building,
    // complex list/dict manipulation) is expected to be handled by the calling Python code,
    // with data passed into the evaluation via the environment, rather than by implementing
    // numerous data manipulation primitives within this evaluator.
    interface SexpEvaluator {

        // Constructor: Initializes the S-expression evaluator.
        // Preconditions:
        // - task_system is a valid TaskSystem instance.
        // - handler is a valid BaseHandler instance.
        // - memory_system is a valid MemorySystem instance.
        // Postconditions:
        // - Evaluator is initialized with references to core system components.
        // - Internal parser might be initialized.
        void __init__(object task_system, object handler, object memory_system); // Args represent TaskSystem, BaseHandler, MemorySystem

        // Parses and evaluates an S-expression string within a given environment.
        // This is the main entry point for executing S-expression workflows.
        // Preconditions:
        // - sexp_string is a string containing the S-expression workflow.
        // - initial_env is an optional SexpEnvironment instance; a new root environment is created if None.
        // (+)   It is expected that the calling Python code will prepare any complex data structures
        // (+)   or strings required by the workflow and provide them via the `initial_env`.
        // Postconditions:
        // - Returns the final result of evaluating the S-expression. This is often the result of the last top-level expression evaluated.
        // - The result should ideally be formatted as a standard TaskResult dictionary by the calling layer (e.g., Dispatcher) if the S-expression doesn't explicitly create one.
        // - Returns a representation indicating failure if parsing or evaluation errors occur (details handled by caller).
        // Behavior:
        // - Parses the `sexp_string` into an S-expression AST using an internal parser. Handles parsing errors.
        // - Creates a root `SexpEnvironment` if `initial_env` is None.
        // - Calls the internal recursive `_eval` method on the parsed AST node(s) within the environment.
        // - Handles evaluation errors (e.g., unbound symbols, primitive misuse, errors from underlying calls).
        // (+) - The S-expression logic typically references variables bound in the `initial_env`
        // (+)   for complex inputs (like prompts built from multiple sources) rather than
        // (+)   performing complex data manipulation itself.
        // (+) - Supports anonymous function definition via `(lambda (params...) body...)` which creates
        // (+)   a first-class Closure object capturing the current lexical environment.
        // (+) - Supports application of these Closures, enabling lexical scoping.
        // @raises_error(condition="SexpSyntaxError", description="Raised by internal parser if the input string has invalid S-expression syntax.")
        // @raises_error(condition="SexpSyntaxError", description="Raised by internal parser if the input string has invalid S-expression syntax.")
        // @raises_error(condition="SexpEvaluationError", description="Raised by internal _eval if runtime errors occur during S-expression evaluation (e.g., unbound symbol, invalid arguments to primitive, type mismatch).")
        // @raises_error(condition="TaskError", description="Propagated if an underlying TaskSystem/Handler call invoked by the S-expression fails (e.g., RESOURCE_EXHAUSTION, TASK_FAILURE from atomic task).")
        Any evaluate_string(string sexp_string, optional object initial_env); // Arg represents SexpEnvironment

        // Internal recursive evaluation method (conceptual - might not be public interface).
        // Preconditions:
        // - node is a parsed S-expression AST node (e.g., symbol, string, number, list).
        // - env is the current SexpEnvironment for evaluation.
        // Postconditions:
        // - Returns the evaluated value of the node.
        // Behavior:
        // - This function's primary goal is to determine the value represented by the AST node.
        // - Handles different node types:
        //   - Literals (string, number, bool, null, empty list): Return the value directly.
        //   - Symbols: Look up the symbol in the `env`. Raise error if unbound.
        //   - Lists: 
        //     - If the list starts with the symbol `lambda`: This is a **lambda definition**. `_eval` directly handles this. It parses the parameter list (expecting symbols) and body expressions. It then creates a `Closure` object, capturing the current `env` as the definition environment, and returns this `Closure`. The parameters and body are *not* evaluated at this stage.
        //     - Otherwise (not a `lambda` definition): Delegates processing to `_eval_list_form`.
        // - **Guideline:** `_eval` focuses on determining the value of a node. The application of functions/operators is primarily handled by `_apply_operator`, which is called by `_eval_list_form`.
        //
        // - **`_eval_list_form` Behavior:**
        //   - Takes a non-empty list (that is not a `lambda` definition) and the current environment.
        //   - Evaluates the first element of the list (the operator expression) using `self._eval` to get the `resolved_operator`.
        //   - If the `op_expr_node` (first element) is a symbol that matches a **Special Form** (e.g., `if`, `let`, `defatom`, `loop` - *excluding* `lambda` which is handled by `_eval` directly), it calls the special form's handler method. Special forms manage their own argument evaluation.
        //   - Otherwise (operator is not a special form symbol), it calls `self._apply_operator(resolved_operator, arg_expr_nodes, calling_env, original_call_expr_str)`.
        //
        // - **`_apply_operator` Behavior (Conceptual - this logic is within SexpEvaluator):**
        //   - Takes the `resolved_operator`, the list of *unevaluated* argument expressions (`arg_expr_nodes`), the `calling_env`, and the original call string.
        //   - **Dispatch Order:**
        //     1. If `resolved_operator` is a **`Closure` object**:
        //        a. Check arity (number of parameters vs. number of provided argument expressions).
        //        b. Evaluate each `arg_expr_node` in the `calling_env` to get `evaluated_args`.
        //        c. Create a new environment frame (`call_frame_env`) whose parent is the `Closure`'s captured `definition_env`.
        //        d. Bind the `Closure`'s parameter symbols to the `evaluated_args` in `call_frame_env`.
        //        e. Evaluate the `Closure`'s body expressions sequentially in `call_frame_env`. The result of the last body expression is returned.
        //     2. Else, if `resolved_operator` is a **string (name of a primitive, task, or tool)**:
        //        a. If it's a **Primitive** (e.g., "list", "get_context", "eq?", "null?", "set!", "+", "-"): Call the primitive's applier method (e.g., `_apply_list_primitive`). Primitive appliers are responsible for evaluating their own arguments from `arg_expr_nodes` as needed.
        //        b. If it's an **Atomic Task name**: Call `_invoke_task_system`. This invoker will evaluate arguments from `arg_expr_nodes` before creating the `SubtaskRequest`.
        //        c. If it's a **Handler Tool name**: Call `_invoke_handler_tool`. This invoker will evaluate arguments from `arg_expr_nodes` before calling the handler's tool executor.
        //        d. Else (name not recognized): Raise "Unrecognized operator" error.
        //     3. Else, if `resolved_operator` is a **Python callable (but not a `Closure`)**:
        //        a. Evaluate each `arg_expr_node` in the `calling_env` to get `evaluated_args`.
        //        b. Call the Python callable with these `evaluated_args`.
        //     4. Else (e.g., `resolved_operator` is a number or a list that's not a closure): Raise "Cannot apply non-callable" error.
        //
        // - `(lambda (param...) body...)`: **Special Form (handled by `_eval`).** Creates and returns a first-class function object (a `Closure`). Does *not* evaluate the parameter list or body immediately. The returned `Closure` captures the parameter list (symbols), the body AST nodes, and the current lexical environment (the environment where the `lambda` expression itself was evaluated). This captured environment enables lexical scoping when the function is later applied.
        // - `(defatom task-name (params ...) (instructions ...) ...)`: **Special Form.** Defines a new atomic task template.
        //     - Parses its *unevaluated* arguments to extract the task name (Symbol), parameter definitions (`(params (p1 type?) ...)`), instructions string (`(instructions "...")`), and optional key-value pairs (e.g., `(subtype "subtask")`, `(description "...")`, `(model "...")`, and `(history_config (quote ((setting1 val1)...)))` to specify default history management behavior for the defined atomic task).
        //     - Constructs a template dictionary conforming to the atomic task structure.
        //     - Registers the template globally with the `TaskSystem` via `TaskSystem.register_template`.
        //     - Raises `SexpEvaluationError` if syntax is invalid or registration fails.
        //     - Returns the `task-name` Symbol upon success.
        //     - **Note:** This definition is global for the current session/evaluator instance. It does not currently support lexical scoping for task definitions.
        // - `(loop <count-expr> <body-expr>)`: **Special Form.** Executes a body expression a fixed number of times.
        //   - **Syntax:** `(loop <count-expr> <body-expr>)`
        //   - **Argument Processing:** Evaluates `<count-expr>` *once*. Expects a non-negative integer result (`n`). Raises `SexpEvaluationError` if the result is not a valid count (non-integer or negative).
        //   - **Behavior:** Evaluates `<body-expr>` exactly `n` times sequentially in the *current* environment.
        //   - **Returns:** The result of the *last* evaluation of `<body-expr>`. If `n` is 0, returns `nil` (represented as `[]` in Python).
        //   - **Errors:** Raises `SexpEvaluationError` if argument count is not exactly 2. Propagates `SexpEvaluationError` from evaluation of `<count-expr>` or `<body-expr>`. Raises `SexpEvaluationError` if count is invalid.
        //
        // - `(director-evaluator-loop ...)`: **Special Form.** Implements the Director-Executor-Evaluator-Controller pattern for iterative workflows.
        //   - **Syntax:** See ADR_director_evaluator_loop.md for full syntax details.
        //   - **Argument Processing:** Evaluates configuration expressions and function expressions as specified in the ADR.
        //   - **Behavior:** Executes the Director-Executor-Evaluator-Controller cycle up to max-iterations times, with each phase function receiving appropriate inputs.
        //     Within each phase function's execution, a special variable `*loop-config*` is bound in the environment. This variable holds an association list (list of pairs) containing the loop's configuration: `(list (list 'max-iterations <max-iter-value>) (list 'initial-director-input <initial-input-value>))`. This allows phase functions to inspect the loop's setup.
        //   - **Returns:** The final result as determined by the controller's 'stop' decision or the last execution result if max iterations is reached.
        //   - **Errors:** Raises `SexpEvaluationError` for various validation failures or if any phase function raises an error.
        //
        // **Note on Closures:** A Closure is a runtime object representing a function created by `lambda` (or potentially `define` if added later). It bundles the function's code (parameter list and body AST) with a reference to the environment where it was defined, enabling lexical scoping. It is a first-class value that can be passed around, stored in variables, and invoked later.
         //
          //
        // - `(get-field <object-or-dict-expr> <field-name-expr>)`: **Primitive.**
        //   - **Action:** Extracts a field or attribute from an object or dictionary.
        //   - **Argument Processing:** Evaluates `<object-or-dict-expr>` to get the target object/dictionary. Evaluates `<field-name-expr>` to get the field name (string or symbol).
        //   - **Behavior:** If the target is a dictionary, performs a key lookup. If the target is an object, performs an attribute lookup. Handles Pydantic models.
        //   - **Returns:** The value of the field/attribute. Returns `None` (or `nil`) if the field/attribute is not found (for demo purposes, actual primitive might error).
        //   - **Raises:** `SexpEvaluationError` if arguments are invalid or access fails unexpectedly.
        // - `(string=? <str1-expr> <str2-expr>)`: **Primitive.**
        //   - **Action:** Compares two strings for equality.
        //   - **Argument Processing:** Evaluates both `<str1-expr>` and `<str2-expr>`.
        //   - **Behavior:** Checks if the two evaluated strings are identical.
        //   - **Returns:** `true` if the strings are equal, `false` otherwise.
        //   - **Raises:** `SexpEvaluationError` if arguments do not evaluate to strings.
        // - `(log-message <expr1> <expr2> ...)`: **Primitive.**
        //   - **Action:** Logs a message to the system's logger (typically at INFO level).
        //   - **Argument Processing:** Evaluates all argument expressions.
        //   - **Behavior:** Converts evaluated arguments to strings and concatenates them with spaces. Logs the resulting string.
        //   - **Returns:** The logged string (or `nil`).
        //   - **Raises:** `SexpEvaluationError` if argument evaluation fails (though the primitive itself tries to be robust).
        // - `(get_context (key1 value_expr1) (key2 value_expr2) ...)`: **Primitive.**
        //   - **Action:** Retrieves relevant context from the MemorySystem.
        //   - **Argument Processing:** Parses `(key value_expr)` pairs. Evaluates each `value_expr`. Recognizes keys like `query`, `history`, `inputs`, `matching_strategy`, etc., corresponding to `ContextGenerationInput` v5.0 fields. Validates argument structure and types.
        //   - **Behavior:** Constructs a `ContextGenerationInput` object from the evaluated arguments. Calls `MemorySystem.get_relevant_context_for` with this object.
        //   - **Returns:** A list of relevant file path strings extracted from the `AssociativeMatchResult`.
        //   - **Raises:** `SexpEvaluationError` if arguments are invalid, context retrieval fails, or `MemorySystem` returns an error.
        // - `(eq? <expr1> <expr2>)` or `(equal? <expr1> <expr2>)`: **Primitive.**
        //   - **Action:** Compares two evaluated expressions for equality.
        //   - **Argument Processing:** Evaluates `<expr1>` and `<expr2>`.
        //   - **Behavior:** Performs Python's `==` comparison on the evaluated values. Symbols are compared by their string values.
        //   - **Returns:** `true` if values are equal, `false` otherwise.
        //   - **Raises:** `SexpEvaluationError` for arity issues or errors during argument evaluation.
        // - `(null? <expr>)` or `(nil? <expr>)`: **Primitive.**
        //   - **Action:** Checks if an evaluated expression is null/nil.
        //   - **Argument Processing:** Evaluates `<expr>`.
        //   - **Behavior:** Considers Python `None` or an empty list `[]` as null.
        //   - **Returns:** `true` if the value is null, `false` otherwise.
        //   - **Raises:** `SexpEvaluationError` for arity issues or errors during argument evaluation.
        // - `(set! <symbol> <new-value-expr>)`: **Primitive.**
        //   - **Action:** Updates the value of an *existing* variable in the current or an ancestor scope.
        //   - **Argument Processing:** `<symbol>` must be a literal symbol. Evaluates `<new-value-expr>`.
        //   - **Behavior:** Searches for `<symbol>` up the environment chain and updates the first binding found.
        //   - **Returns:** The `new-value`.
        //   - **Raises:** `SexpEvaluationError` if `<symbol>` is not a symbol, is unbound, or for arity issues/evaluation errors.
        // - `(+ <num-expr1> <num-expr2> ...)`: **Primitive.**
        //   - **Action:** Adds numbers. N-ary.
        //   - **Argument Processing:** Evaluates all `<num-expr>` arguments.
        //   - **Behavior:** Sums the evaluated numbers. If no arguments, returns 0. Promotes to float if any argument is float.
        //     Note on Boolean Arguments: Due to the S-expression parser's behavior of converting S-expression `true` and `false` symbols to Python `True` and `False` booleans, and Python's `bool` type being a subclass of `int` (`True` is 1, `False` is 0), this primitive will treat Python boolean arguments as their integer equivalents (1 or 0) in arithmetic operations. If stricter type checking disallowing booleans is required, it must be explicitly handled within the primitive's logic beyond standard numeric type checks.
        //   - **Returns:** The sum (integer or float).
        //   - **Raises:** `SexpEvaluationError` if any argument is not a number or for evaluation errors.
        // - `(- <num-expr1> <optional-num-expr2>)`: **Primitive.**
        //   - **Action:** Subtracts numbers or negates a single number.
        //   - **Argument Processing:** Evaluates argument(s).
        //   - **Behavior:** If one argument, returns its negation. If two arguments, returns `num1 - num2`. Promotes to float.
        //     Note on Boolean Arguments: Due to the S-expression parser's behavior of converting S-expression `true` and `false` symbols to Python `True` and `False` booleans, and Python's `bool` type being a subclass of `int` (`True` is 1, `False` is 0), this primitive will treat Python boolean arguments as their integer equivalents (1 or 0) in arithmetic operations. If stricter type checking disallowing booleans is required, it must be explicitly handled within the primitive's logic beyond standard numeric type checks.
        //   - **Returns:** The result (integer or float).
        //   - **Raises:** `SexpEvaluationError` for arity issues, if arguments are not numbers, or for evaluation errors.
        // - `(and expr1 expr2 ...)`: **Special Form.** Evaluates expressions sequentially from left to right.
        //   - **Behavior:** If any expression evaluates to a falsey value (Python `False`, `None`, `0`, empty sequence/mapping, etc.),
        //     evaluation stops immediately, and that falsey value is returned. If all expressions evaluate to truthy values,
        //     the value of the *last* expression is returned. If no expressions are provided (`(and)`), it returns `true`.
        //   - **Returns:** The determined value (could be any type, or `true`).
        //   - **Raises:** `SexpEvaluationError` if any argument evaluation fails before a short-circuit condition is met.
        // - `(or expr1 expr2 ...)`: **Special Form.** Evaluates expressions sequentially from left to right.
        //   - **Behavior:** If any expression evaluates to a truthy value, evaluation stops immediately, and that truthy value is returned.
        //     If all expressions evaluate to falsey values, the value of the *last* expression is returned.
        //     If no expressions are provided (`(or)`), it returns `false`.
        //   - **Returns:** The determined value (could be any type, or `false`).
        //   - **Raises:** `SexpEvaluationError` if any argument evaluation fails before a short-circuit condition is met.
        // - `(not <expr>)`: **Primitive.**
        //   - **Action:** Performs logical negation.
        //   - **Argument Processing:** Evaluates `<expr>`.
        //   - **Behavior:** Returns `true` if `<expr>` evaluates to a falsey value (Python `False`, `None`, `0`, empty string/list/dict), and `false` otherwise.
        //   - **Returns:** `true` or `false`.
        //   - **Raises:** `SexpEvaluationError` for arity issues or errors during argument evaluation.
        //
        // - Parses the `args` list, expecting `(key_symbol value_expression)` pairs. **Note: `args` contains *unevaluated* argument expressions.**
        // - **Crucially, evaluates each `value_expression` using `_eval` within this handler** to get the actual argument values.
        // - Handles conversion of quoted list-of-pairs for `context` or `inputs` arguments after evaluation.
        // - **Guideline (Defensive Check):** Although primary validation relies on correct dispatch from `_eval_list`, this function should ideally perform basic structural checks on the format of `args` before proceeding.
        // - If `operator_target` is a string, looks up and calls the corresponding TaskSystem task or Handler tool.
        // - If `operator_target` is a callable, invokes it (handling function application scope if closures are implemented).
        // - Returns the result, ensuring TaskResult format for task/tool calls.
        //       - Note: Arguments to primitives like `get_context` that expect complex data (e.g., `inputs`, `context` settings) should receive that data correctly constructed, often using `(list ...)` or `(quote ...)` within the calling S-expression.
        //       5. Look up `target_id` first in `Handler.tool_executors`, then in `TaskSystem.find_template` (for **atomic** templates **only**).
        //       6. If Direct Tool: Call executor function, passing `resolved_named_args` (potentially merging with positional args based on tool signature - requires convention).
        //       7. If Atomic Template:
        //          a. Construct the `SubtaskRequest` object.
        //          b. Set `request.inputs = resolved_named_args`.
        //          c. Set `request.file_paths = resolved_files` if it's not None.
        //          d. Set `request.context_management = resolved_context_settings` if it's not None.
        //          e. Call `TaskSystem.execute_atomic_template(request)`.
        //       8. Return result.
        //       
        // Note: Complex patterns requiring loops or sophisticated state management (like Director-Evaluator)
        // must be implemented using combinations of S-expression primitives like `let`/`bind` and `if`,
        // potentially involving recursive S-expression structures or dedicated loop primitives if available.
        // This evaluator does not handle XML composite types.
        // @raises_error(...) // Various evaluation errors
        // Any _eval(Any node, object env); // Arg represents SexpEnvironment
         // @raises_error(condition="SexpEvaluationError", description="Raised for invalid loop count, or errors during body evaluation.")
    };

    // Interface for the S-expression evaluation environment.
    // **Note:** This environment is used *exclusively* for managing lexical scope
    // (variable bindings like `let`/`bind`) during the evaluation of S-expressions
    // by the SexpEvaluator. It is distinct from the simple parameter dictionary
    // used for substitution within atomic task bodies by the AtomicTaskExecutor.
    // Manages variable bindings during S-expression evaluation.
    interface SexpEnvironment {
        // Constructor: Creates a new environment.
        // Preconditions:
        // - bindings is an optional dictionary of initial bindings.
        // - parent is an optional parent SexpEnvironment.
        void __init__(optional dict<string, Any> bindings, optional SexpEnvironment parent);

        // Finds a variable's value.
        // Preconditions: name is a symbol string.
        // Behavior: Looks in current bindings, then recursively in parent.
        // @raises_error(condition="UnboundSymbolError", description="If symbol not found.")
        Any lookup(string name);

        // Defines a variable in the *current* environment scope.
        // Preconditions: name is a symbol string, value is the evaluated result.
        void define(string name, Any value);

        // Sets the value of an *existing* variable in the current or an ancestor scope.
        // Preconditions:
        // - name is a symbol string representing an existing, bound variable.
        // - value is the new evaluated result for the variable.
        // Behavior:
        // - Searches for the variable 'name' starting from the current environment
        //   and going up the parent chain. The first binding found is updated.
        // - This allows modification of variables in outer scopes, as used by `set!`.
        // @raises_error(condition="UnboundSymbolError", description="If symbol 'name' is not found in any accessible scope.")
        void set_value_in_scope(string name, Any value);

        // Creates a new child environment extending this one.
        // Preconditions: bindings is a dictionary for the child scope.
        SexpEnvironment extend(dict<string, Any> bindings);
    };
};
// == !! END IDL TEMPLATE !! ===
