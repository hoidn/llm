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
        // - Handles different node types:
        //   - Literals (string, number, bool, null): Return the value directly.
        //   - Symbols: Look up the symbol in the `env`. Raise error if unbound.
        //   - Lists: Treat as function/primitive call:
        //     - Identify the operator (first element).
        //     - If operator is a special form/primitive (`let`, `if`, `map`, `list`, `get_context`): Execute specific primitive logic.
        //       - `(let ((sym expr)...) body...)` / `(bind sym expr)`: Evaluate expr, bind to sym in new/current scope, evaluate body.
        //       - `(if cond then else)`: Evaluate cond, then evaluate/return then or else branch.
        //       - `(map task_expr list_expr)`: Evaluate list_expr, iterate, bind item, evaluate task_expr in nested scope, collect results.
        //       - `(list item...)`: Evaluate items, return list.
        //       - `(get_context option...)`: Evaluate option values, call MemorySystem.get_relevant_context_for, return file paths.
        //     - Otherwise (general invocation `(<identifier> <arg>*)`):
        //       1. Evaluate identifier symbol to get `target_id`.
        //       2. Initialize empty `named_args` dictionary, `context_override` dict, `files_override` list.
        //       3. Iterate through remaining list elements (`<arg>*`):
        //          a. If element is a list `(key value_expression)` and `key` is a symbol *not* named 'context' or 'files': Evaluate `value_expression` and store result in `named_args[key_symbol]`.
        //          b. If element is a list `(context ...)`: Parse the inner pairs (e.g., `(inherit_context none)`) and store in `context_override`.
        //          c. If element is a list `(files ...)`: Evaluate the inner expression (should yield a list of strings) and store in `files_override`.
        //          d. Else (assume positional arg - **Note: Discouraged for task/tool calls**): Evaluate the element and add to a `positional_args` list (use with caution).
        //       4. Look up `target_id` in `Handler.tool_executors` then `TaskSystem.find_template` (atomic only).
        //       5. If Direct Tool: Call executor function, passing `named_args` (potentially merging with positional args based on tool signature - requires convention).
        //       6. If Atomic Template: Construct `SubtaskRequest`, populating `inputs` from `named_args`, `context_management` from `context_override`, `file_paths` from `files_override`. Call `TaskSystem.execute_atomic_template(request, env)`.
        //       7. Return result.
        // @raises_error(...) // Various evaluation errors
        // Any _eval(Any node, object env); // Arg represents SexpEnvironment
    };

    // Interface for the S-expression evaluation environment.
    // Manages variable bindings *exclusively* for the duration of an S-expression evaluation. It is distinct from the core Environment potentially used by the AtomicTaskExecutor.
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
