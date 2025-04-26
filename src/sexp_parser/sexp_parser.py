"""
Implementation of the SexpParser interface using the 'sexpdata' library.
Parses S-expression strings into Python Abstract Syntax Trees (ASTs).
"""

import sexpdata
from typing import Any

# Import the custom error type
from src.system.errors import SexpSyntaxError

class SexpParser:
    """
    Parses S-expression strings into Python ASTs (nested lists/tuples/atoms).

    Implements the contract defined in src/sexp_parser/SexpParser_IDL.md.
    Uses the 'sexpdata' library for the underlying parsing mechanism.
    """

    def parse_string(self, sexp_string: str) -> Any:
        """
        Parses an S-expression string into a Python representation (AST).

        Args:
            sexp_string: A string potentially containing an S-expression.

        Returns:
            The parsed AST, typically composed of nested lists, tuples,
            strings, numbers, booleans, None, and sexpdata.Symbol objects.

        Raises:
            SexpSyntaxError: If the input string contains syntax errors
                             (e.g., unbalanced parentheses, invalid tokens).
        """
        if not isinstance(sexp_string, str):
            # Add basic type check for clarity, although sexpdata might handle it
            raise TypeError("Input must be a string.")

        try:
            # sexpdata.loads parses the string into a nested structure
            # It typically uses lists for sequences and sexpdata.Symbol for identifiers.
            parsed_ast = sexpdata.loads(sexp_string)
            return parsed_ast
        except sexpdata.ExpectClosingBracket as e:
            # Catch specific sexpdata exceptions and wrap them in SexpSyntaxError
            raise SexpSyntaxError(
                message="S-expression syntax error: Unbalanced parentheses or brackets.",
                sexp_string=sexp_string,
                error_details=str(e)
            ) from e
        except sexpdata.ExpectNothing as e:
             raise SexpSyntaxError(
                message="S-expression syntax error: Unexpected content after the main expression.",
                sexp_string=sexp_string,
                error_details=str(e)
            ) from e
        except ValueError as e:
            # Catch potential ValueErrors from underlying parsing (e.g., invalid literals)
             raise SexpSyntaxError(
                message="S-expression syntax error: Invalid token or literal.",
                sexp_string=sexp_string,
                error_details=str(e)
            ) from e
        except Exception as e:
            # Catch any other unexpected errors during parsing
            raise SexpSyntaxError(
                message="An unexpected error occurred during S-expression parsing.",
                sexp_string=sexp_string,
                error_details=str(e)
            ) from e

# Example Usage (can be removed or kept for demonstration)
if __name__ == '__main__':
    parser = SexpParser()
    test_strings = [
        "(add 1 2)",
        "(list 1 \"hello\" true nil (nested 3.14))",
        "symbol",
        "\"a string\"",
        "123",
        "()", # Empty list
        "(missing paren", # Error case
        "(extra paren))", # Error case
        "(invalid'token)", # Error case
    ]

    for s in test_strings:
        print(f"Parsing: {s}")
        try:
            ast = parser.parse_string(s)
            print(f"  AST: {ast}")
            # Example: Check type of identifier
            if isinstance(ast, list) and ast:
                 if isinstance(ast[0], sexpdata.Symbol):
                     print(f"  Identifier type: {type(ast[0])}")

        except SexpSyntaxError as e:
            print(f"  Error: {e}")
        print("-" * 10)
