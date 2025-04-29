// == !! BEGIN IDL TEMPLATE !! ===
module src.sexp_evaluator.sexp_environment {

    // Interface for the S-expression evaluation environment.
    // Manages variable bindings during S-expression evaluation.
    // This environment is used exclusively for managing lexical scope
    // (variable bindings like `let`/`bind`) during the evaluation of S-expressions
    // by the SexpEvaluator. It is distinct from the simple parameter dictionary
    // used for substitution within atomic task bodies by the AtomicTaskExecutor.
    interface SexpEnvironment {
        // Constructor: Creates a new environment.
        // Preconditions:
        // - bindings is an optional dictionary of initial bindings.
        // - parent is an optional parent SexpEnvironment.
        void __init__(optional dict<string, Any> bindings, optional SexpEnvironment parent);

        // Finds a variable's value.
        // Preconditions: name is a symbol string.
        // Behavior: 
        // - Looks in current bindings, then recursively in parent.
        // @raises_error(condition="UnboundSymbolError", description="If symbol not found.")
        Any lookup(string name);

        // Defines a variable in the *current* environment scope.
        // Preconditions: name is a symbol string, value is the evaluated result.
        void define(string name, Any value);

        // Creates a new child environment extending this one.
        // Preconditions: bindings is a dictionary for the child scope.
        // Behavior:
        // - Creates a new child environment with the current environment set as its parent.
        // - Initializes the child's local bindings with the provided dictionary.
        // - This parent linkage is crucial for implementing lexical scoping, allowing functions (closures) defined in an outer scope to access variables from that scope even when called from a different scope.
        SexpEnvironment extend(dict<string, Any> bindings);
        
        // Returns a dictionary of all bindings in the current environment frame.
        // Does not include bindings from parent environments.
        dict<string, Any> get_local_bindings();
    };
};
// == !! END IDL TEMPLATE !! ===
