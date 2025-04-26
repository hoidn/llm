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
        //       2. Initialize empty dictionary `resolved_named_args = {}`.
        //       3. Initialize `resolved_files = None`, `resolved_context_settings = None`.
        //       4. Iterate through remaining list elements (`<arg>*`) after the identifier:
        //          a. If element is a list `(key value_expression)` and `key` is a symbol:
        //             i.   Evaluate `value_expression` recursively using `eval(value_expression, env)`. Let the result be `evaluated_value`.
        //             ii.  Get the string name of the `key` symbol (e.g., "arg1"). Let this be `arg_name`.
        //             iii. If `arg_name` is "files": Set `resolved_files = evaluated_value` (ensure it's a list of strings).
        //             iv.  Else if `arg_name` is "context": Set `resolved_context_settings = evaluated_value` (ensure it's a dictionary matching context settings).
        //             v.   Else (regular named argument): Store `resolved_named_args[arg_name] = evaluated_value`.
        //          b. Else (treat as positional argument - **Note: Discouraged for task/tool calls**): Evaluate the element and add to a temporary list (handle with care or disallow for task/tool calls).
        //       5. Look up `target_id` in `Handler.tool_executors` then `TaskSystem.find_template` (atomic only).
        //       6. If Direct Tool: Call executor function, passing `resolved_named_args` (potentially merging with positional args based on tool signature - requires convention).
        //       7. If Atomic Template:
        //          a. Construct the `SubtaskRequest` object.
        //          b. Set `request.inputs = resolved_named_args`.
        //          c. Set `request.file_paths = resolved_files` if it's not None.
        //          d. Set `request.context_management = resolved_context_settings` if it's not None.
        //          e. Call `TaskSystem.execute_atomic_template(request)`.
        //       8. Return result.
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
