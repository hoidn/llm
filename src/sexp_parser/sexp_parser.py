"""
Implementation of the SexpParser interface using the 'sexpdata' library.
Parses S-expression strings into Python Abstract Syntax Trees (ASTs).
"""

import logging
from typing import Any
from io import StringIO
from sexpdata import load, Symbol, ExpectNothing, ExpectClosingBracket # Add specific sexpdata exceptions

# Import the custom error type
from src.system.errors import SexpSyntaxError # This is our custom error


class SexpParser:
    """
    Parses S-expression strings into Python ASTs (nested lists/tuples/atoms).

    Implements the contract defined in src/sexp_parser/SexpParser_IDL.md.
    Uses the 'sexpdata' library for the underlying parsing mechanism.
    Converts common symbols 'true', 'false', 'nil' to Python equivalents.
    """

    def parse_string(self, sexp_string: str) -> Any:
        """
        Parses a single S-expression from a string.

        Args:
            sexp_string: The string containing the S-expression.

        Returns:
            The parsed S-expression as a Python AST (nested lists/atoms),
            with common symbols converted.

        Raises:
            SexpSyntaxError: If the input string has syntax errors, is empty,
                             or contains unexpected content after the main expression.
            TypeError: If the input is not a string.
        """
        if not isinstance(sexp_string, str):
            # Add basic type check for clarity
            raise TypeError("Input must be a string.")

        logging.debug(f"Attempting to parse S-expression string: '{sexp_string}'")
        stripped_string = sexp_string.strip() # Use strip to handle leading/trailing whitespace
        
        # Explicitly check for empty input before attempting to parse
        if not stripped_string:
            logging.error("S-expression parsing failed: Input string is empty or contains only whitespace.")
            raise SexpSyntaxError(
                "Input string is empty or contains only whitespace.",
                sexp_string
            )
            
        sio = StringIO(stripped_string)

        try:
            # Configure parser for 'true' and 'false' symbols
            # Let 'nil' parse to its default '[]'
            parsed_expression = load(sio,
                                     nil='nil', # Keep default symbol for []
                                     true='true', # Map 'true' symbol to True
                                     false='false' # Map 'false' symbol to False
                                    )
            logging.debug(f"Raw parsed expression: {parsed_expression}")

            # Check if there's any non-whitespace content left in the stream
            remainder = sio.read().strip()
            if remainder:
                logging.error(f"Unexpected content after main expression: '{remainder}'")
                # Raise SexpSyntaxError directly for clarity and consistency
                raise SexpSyntaxError("Unexpected content after the main expression.", sexp_string, error_details=f"Trailing content: '{remainder}'")

            logging.debug(f"Raw parsed expression from sexpdata.load: {parsed_expression!r}")

            # --- START PARSER DEBUGGING ---
            # Recursively inspect if parsed_expression contains Quoted objects
            def inspect_parsed_node(p_node, depth=0):
                from sexpdata import Quoted as ParserQuoted # Import locally for this inspection
                if isinstance(p_node, ParserQuoted):
                    logging.debug(f"{'  '*depth}SexpParser: Found Quoted node: {p_node!r}")
                    logging.debug(f"{'  '*depth}SexpParser:   Type: {type(p_node)}, Class: {p_node.__class__}, Module: {getattr(p_node, '__module__', 'N/A')}")
                    logging.debug(f"{'  '*depth}SexpParser:   dir(node): {dir(p_node)}")
                    logging.debug(f"{'  '*depth}SexpParser:   hasattr(node, 'val'): {hasattr(p_node, 'val')}")
                    if hasattr(p_node, 'val'):
                        logging.debug(f"{'  '*depth}SexpParser:   node.val: {p_node.val!r}")
                elif isinstance(p_node, list):
                    for item in p_node:
                        inspect_parsed_node(item, depth + 1)
            
            if parsed_expression: # Ensure not None or empty before inspecting
                inspect_parsed_node(parsed_expression)
            # --- END PARSER DEBUGGING ---

            logging.debug(f"Successfully parsed AST: {parsed_expression}")
            return parsed_expression

        except StopIteration: # Raised by sexpdata.load if the stream is empty after stripping
             logging.error("S-expression parsing failed: Input string is empty or contains only whitespace.")
             raise SexpSyntaxError(
                 "Input string is empty or contains only whitespace.",
                 sexp_string
             ) from None
        except ExpectClosingBracket as e: # Catch specific bracket error
            logging.error(f"S-expression syntax error (Unbalanced Parentheses): {e}")
            raise SexpSyntaxError("S-expression syntax error: Unbalanced parentheses or brackets.", sexp_string, error_details=str(e)) from e
        except ExpectNothing as e:
             # This exception is raised by our check above if there's trailing content
             logging.error(f"S-expression parsing failed: Unexpected content after main expression. Details: {e}")
             raise SexpSyntaxError(
                 "Unexpected content after the main expression.", # Match test assertion
                 sexp_string,
                 error_details=str(e)
             ) from e
        except ValueError as e: # Keep for other potential parse errors
             # Catch specific syntax errors from sexpdata (e.g., unbalanced parens)
             logging.error(f"S-expression syntax error (ValueError): {e}")
             # Make the message more specific based on common sexpdata errors if possible
             msg = f"S-expression syntax error: {e}"
             # Add more specific checks if needed based on ValueError contents
             raise SexpSyntaxError(
                 msg,
                 sexp_string,
                 error_details=str(e)
             ) from e
        except AssertionError as e: # Catch AssertionError from sexpdata.loads for multiple expressions
             # This now primarily catches the case of >1 top-level expressions,
             # as the empty case (len=0) is handled before calling load.
             logging.error(f"S-expression syntax error (Multiple Expressions): {e}")
             raise SexpSyntaxError("Multiple top-level S-expressions found. Use (progn ...) or ensure single expression.", sexp_string, error_details=str(e)) from e
        except Exception as e: # Catch-all for truly unexpected issues
             logging.exception(f"Unexpected error during S-expression parsing or conversion: {e}")
             raise SexpSyntaxError(
                 f"An unexpected error occurred during S-expression parsing: {e}",
                 sexp_string,
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
        "(nil)", # List containing nil
        "(missing paren", # Error case
        "(extra paren))", # Error case
        "(invalid'token)", # Error case - might depend on sexpdata behavior
        "(expr1) (expr2)", # Error case
        "  ", # Empty string case
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
        except TypeError as e:
            print(f"  TypeError: {e}")
        print("-" * 10)
