"""
Implementation of the SexpParser interface using the 'sexpdata' library.
Parses S-expression strings into Python Abstract Syntax Trees (ASTs).
"""

import sexpdata
from typing import Any
from sexpdata import Symbol # Import Symbol

# Import the custom error type
from src.system.errors import SexpSyntaxError

# Helper function to recursively convert common symbols
def _convert_common_symbols(item: Any) -> Any:
    """Recursively converts Symbol('true'), Symbol('false'), Symbol('nil') to Python types."""
    if isinstance(item, Symbol):
        val = item.value()
        if val == 'true':
            return True
        elif val == 'false':
            return False
        elif val == 'nil':
            return None
        else:
            # Keep other symbols as Symbol objects
            return item
    elif isinstance(item, list):
        # Recursively process lists
        return [_convert_common_symbols(sub_item) for sub_item in item]
    else:
        # Return other types (int, float, str, etc.) as is
        return item

class SexpParser:
    """
    Parses S-expression strings into Python ASTs (nested lists/tuples/atoms).

    Implements the contract defined in src/sexp_parser/SexpParser_IDL.md.
    Uses the 'sexpdata' library for the underlying parsing mechanism.
    Converts common symbols 'true', 'false', 'nil' to Python equivalents.
    """

    def parse_string(self, sexp_string: str) -> Any:
        """
        Parses an S-expression string into a Python representation (AST).

        Args:
            sexp_string: A string potentially containing an S-expression.

        Returns:
            The parsed AST, composed of nested lists, strings, numbers,
            booleans (True/False), None, and potentially other sexpdata.Symbol objects.

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
            raw_ast = sexpdata.loads(sexp_string)
            # Convert common symbols like true, false, nil
            converted_ast = _convert_common_symbols(raw_ast)
            return converted_ast
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
        "(list 1 \"hello\" true nil (nested 3.14 false))", # Added false
        "symbol",
        "\"a string\"",
        "123",
        "()", # Empty list
        "true", # Boolean symbol
        "nil", # Nil symbol
        "(missing paren", # Error case
        "(extra paren))", # Error case
        "(invalid'token)", # Error case - might depend on sexpdata behavior
        "(expr1) (expr2)", # Error case
    ]

    for s in test_strings:
        print(f"Parsing: {s}")
        try:
            ast = parser.parse_string(s)
            print(f"  AST: {ast} (Type: {type(ast)})")
            # Example: Check type of identifier
            if isinstance(ast, list) and ast:
                 if isinstance(ast[0], Symbol):
                     print(f"  Identifier type: {type(ast[0])}")
                 elif ast[0] is None:
                     print(f"  First element is None")


        except SexpSyntaxError as e:
            print(f"  Error: {e}")
        print("-" * 10)
