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
        //
        // **AST Representation and Type Conversions:**
        // The parser transforms the S-expression string into a Python-based Abstract Syntax Tree (AST). The `sexpdata` library is used as the underlying parsing mechanism, with specific configurations applied:
        // *   **Literals:**
        //     *   S-expression symbols `true` and `false` are parsed directly into Python boolean literals `True` and `False`, respectively.
        //     *   The S-expression symbol `nil` is parsed into the Python `None` literal. (Note: An empty S-expression list `()` also parses to an empty Python list `[]`).
        //     *   String literals (e.g., `"hello"`) are parsed into Python strings (e.g., `'hello'`).
        //     *   Numeric literals (e.g., `123`, `3.14`) are parsed into Python `int` or `float` types.
        // *   **Symbols:** Unquoted identifiers (e.g., `my-variable`, `+`) are parsed into `sexpdata.Symbol` objects. For example, the S-expression `foo` becomes `Symbol('foo')`.
        // *   **Lists:** S-expression lists (e.g., `(a b c)`) are parsed into Python lists, where each element is recursively parsed according to these rules. For example, `(add 1 true)` becomes `[Symbol('add'), 1, True]`.
        // *   **Quoted Expressions:**
        //     *   The short-form quote (e.g., `'foo`) is typically equivalent to `(quote foo)`.
        //     *   The `(quote <expression>)` special form is handled by the `SexpEvaluator`. The parser will represent `(quote foo)` as an AST like `[Symbol('quote'), Symbol('foo')]`. The `SexpEvaluator`'s `quote` handler then returns the `Symbol('foo')` part unevaluated.
        // *   **Error Handling:** Malformed S-expressions will cause the parser to raise a `SexpSyntaxError`.
        // @raises_error(condition="SexpSyntaxError", description="Raised if the input string is not a well-formed S-expression.")
        Any parse_string(string sexp_string);

    };
};
// == !! END IDL TEMPLATE !! ===
