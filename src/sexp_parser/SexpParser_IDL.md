// == !! BEGIN IDL TEMPLATE !! ===
module src.sexp_parser {

    # @depends_on_type(builtins.Any) // Represents the nested list/tuple AST structure
    # @depends_on_type(errors.SexpSyntaxError) // Custom error type

    // Interface for parsing S-expression strings into an Abstract Syntax Tree (AST).
    interface SexpParser {

        // Parses an S-expression string into a Python representation (AST).
        // Preconditions:
        // - sexp_string is a string potentially containing an S-expression.
        // Postconditions:
        // - On success, returns the parsed AST. The AST is typically composed of nested Python lists,
        //   strings, numbers (int/float), booleans, None, and potentially custom Symbol objects
        //   (depending on the underlying library, e.g., sexpdata.Symbol).
        // - Raises SexpSyntaxError if the input string contains syntax errors (e.g., unbalanced parentheses, invalid tokens).
        // Behavior:
        // - Uses an underlying S-expression parsing library (e.g., sexpdata) to parse the input string.
        // - Maps the parsed S-expression elements to corresponding Python types.
        // - Provides clear error messages indicating the location and nature of syntax errors.
        // Expected Output AST Structure (Conceptual Example for "(call task-a (arg1 (+ 1 2)))"):
        //   ['call', 'task-a', ['arg1', ['+', 1, 2]]]
        //   (Actual representation might use tuples or specific Symbol objects instead of strings for identifiers)
        // @raises_error(condition="SexpSyntaxError", description="Raised if the input string is not a well-formed S-expression.")
        Any parse_string(string sexp_string);

    };
};
// == !! END IDL TEMPLATE !! ===
