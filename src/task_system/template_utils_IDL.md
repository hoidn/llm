// == !! BEGIN IDL TEMPLATE !! ===
module src.task_system.template_utils {

    // Represents an environment for variable resolution with lexical scoping.
    // Used for managing variable bindings during template processing and function calls.
    interface Environment {

        // Constructor: Initializes an environment.
        // Preconditions:
        // - bindings is an optional dictionary of initial variable bindings.
        // - parent is an optional parent Environment instance for lexical scoping.
        // Postconditions:
        // - Environment object is created with the specified bindings and parent link.
        void __init__(optional dict<string, Any> bindings, optional Environment parent);

        // Finds a variable's value within the current environment or its ancestors.
        // Supports simple names, dot notation (obj.prop), and array indexing (arr[0]).
        // Preconditions:
        // - name is a string representing the variable name or access path.
        // Postconditions:
        // - Returns the value associated with the name/path if found.
        // Behavior:
        // - Searches bindings in the current environment.
        // - If not found, recursively searches parent environments.
        // - Parses dot notation and array indexing to access nested values.
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Raised if the variable name or path cannot be resolved in the environment hierarchy.")
        // @raises_error(condition="INPUT_VALIDATION_FAILURE", description="Raised if the access path (dots, brackets) is invalid or accesses a non-existent property/index.")
        Any find(string name);

        // Creates a new child environment inheriting from this one.
        // Preconditions:
        // - bindings is a dictionary of variable bindings specific to the new child environment.
        // Postconditions:
        // - Returns a new Environment instance whose parent is the current instance.
        // Behavior:
        // - The new environment contains the provided bindings.
        // - Lookups in the child environment will fall back to the parent (this instance) if a variable is not found locally.
        Environment extend(dict<string, Any> bindings);
    };

    // Note: Utility functions like substitute_variables, resolve_function_calls, etc.,
    // are considered internal implementation details of the components that use them
    // (e.g., TemplateProcessor, Evaluator) and are not part of this IDL interface specification.
    // Their essential behavior is described in the methods of the components that rely on them.
};
// == !! END IDL TEMPLATE !! ===
