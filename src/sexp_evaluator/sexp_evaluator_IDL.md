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
        // Postconditions:
        // - Returns the final result of evaluating the S-expression. This is often the result of the last top-level expression evaluated.
        // - The result should ideally be formatted as a standard TaskResult dictionary by the calling layer (e.g., Dispatcher) if the S-expression doesn't explicitly create one.
        // - Returns a representation indicating failure if parsing or evaluation errors occur (details handled by caller).
        // Behavior:
        // - Parses the `sexp_string` into an S-expression AST using an internal parser. Handles parsing errors.
        // - Creates a root `SexpEnvironment` if `initial_env` is None.
        // - Calls the internal recursive `_eval` method on the parsed AST node(s) within the environment.
        // - Handles evaluation errors (e.g., unbound symbols, primitive misuse, errors from underlying calls).
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
        //   - Lists: Delegates processing to `_eval_list` to determine if it's a special form, primitive call, function/task/tool invocation, or invalid.
        // - **Guideline:** Focuses on returning the value; the *application* of functions/operators happens within the logic called by `_eval_list`.
        //     - **Dispatch Order & Explicitness:** Follows a strict dispatch order:
        //   1. Check if operator is a symbol matching a **Special Form** (`if`, `let`, `bind`, `progn`, `quote`, `lambda`, `defatom`). If yes, execute special form logic (which handles its own argument evaluation or definition).
        //   2. Else, check if operator is a symbol matching a **Primitive** (`list`, `get_context`). If yes, execute primitive logic (which evaluates necessary arguments internally).
        //   3. Else (operator is not a special form or primitive symbol, OR operator is a complex expression like another list): Evaluate the operator expression itself using `_eval`. Let the result be `evaluated_operator`.
        //      a. If `evaluated_operator` is a **Closure object** (a function created by `lambda`): Trigger the **Function Application** process:
        //          i.   Evaluate the argument expressions (`<arg1>`, `<arg2>`, ...) provided in the *call* within the *current calling environment*.
        //          ii.  Create a *new environment frame* for the function execution.
        //          iii. Link the new frame's parent to the environment **captured within the Closure object** (this provides lexical scope).
        //          iv.  Bind the function's formal parameter names (from the Closure) to the evaluated argument values in the new frame. Check for correct argument count.
        //          v.   Evaluate the function's body expression(s) (from the Closure) sequentially within the new environment frame.
        //          vi.  The result of the last body expression is the result of the function application. Return this result.
        //      b. Else, if `evaluated_operator` is a **known Task/Tool name string**, delegate to `_handle_invocation` (passing the *name* and *unevaluated* args from the original list).
        //      c. Else, if `evaluated_operator` is a **Python callable** (but not a Closure, e.g., a built-in function exposed directly), delegate to `_handle_invocation` (passing the *callable* and *unevaluated* args).
        //      d. Else, if `evaluated_operator` is a symbol but **not recognized** as executable (special form, primitive, task, tool, Closure, callable), raise an "Undefined function or task" error.
        //      e. Else (e.g., `evaluated_operator` is a non-callable value like a list or number), raise a "Cannot apply non-callable operator" error.
        // - `(lambda (param...) body...)`: **Special Form.** Creates and returns a first-class function object (a Closure). Does *not* evaluate the parameter list or body immediately. The returned Closure captures the parameter list (symbols), the body AST nodes, and the current lexical environment (the environment where the lambda expression itself was evaluated). This captured environment enables lexical scoping when the function is later applied.
        // - `(defatom task-name (params ...) (instructions ...) ...)`: **Special Form.** Defines a new atomic task template.
        //     - Parses its *unevaluated* arguments to extract the task name (Symbol), parameter definitions (`(params (p1 type?) ...)`), instructions string (`(instructions "...")`), and optional key-value pairs (e.g., `(subtype "subtask")`, `(description "...")`).
        //     - Constructs a template dictionary conforming to the atomic task structure.
        //     - Registers the template globally with the `TaskSystem` via `TaskSystem.register_template`.
        //     - Raises `SexpEvaluationError` if syntax is invalid or registration fails.
        //     - Returns the `task-name` Symbol upon success.
        //     - **Note:** This definition is global for the current session/evaluator instance. It does not currently support lexical scoping for task definitions.
        
        // **Note on Closures:** A Closure is a runtime object representing a function created by `lambda` (or potentially `define` if added later). It bundles the function's code (parameter list and body AST) with a reference to the environment where it was defined, enabling lexical scoping. It is a first-class value that can be passed around, stored in variables, and invoked later.
        
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

        // Creates a new child environment extending this one.
        // Preconditions: bindings is a dictionary for the child scope.
        SexpEnvironment extend(dict<string, Any> bindings);
    };
};
// == !! END IDL TEMPLATE !! ===
