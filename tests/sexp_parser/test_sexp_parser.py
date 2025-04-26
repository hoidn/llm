"""
Unit tests for the SexpParser class.
"""

import pytest
from sexpdata import Symbol # Import Symbol for comparison

# Attempt to import the class and error under test
try:
    from src.sexp_parser.sexp_parser import SexpParser
    from src.system.errors import SexpSyntaxError
except ImportError:
    pytest.skip("Skipping sexp_parser tests, src.sexp_parser or src.system.errors not found or dependencies missing", allow_module_level=True)


@pytest.fixture
def parser():
    """Provides a SexpParser instance for tests."""
    return SexpParser()

# --- Test Valid S-expressions ---

def test_parse_simple_list(parser):
    """Test parsing a simple list with symbols and literals."""
    sexp_string = "(add 1 2)"
    expected_ast = [Symbol('add'), 1, 2]
    assert parser.parse_string(sexp_string) == expected_ast

def test_parse_nested_list(parser):
    """Test parsing nested lists."""
    sexp_string = "(list 1 (inner a b) 3)"
    expected_ast = [Symbol('list'), 1, [Symbol('inner'), Symbol('a'), Symbol('b')], 3]
    assert parser.parse_string(sexp_string) == expected_ast

def test_parse_different_atom_types(parser):
    """Test parsing various atomic types."""
    sexp_string = "(data 123 4.5 \"hello\" true false nil symbol-name)"
    # Expect Python types now due to conversion
    expected_ast = [
        Symbol('data'),
        123,
        4.5,
        "hello",
        True,            # Expect Python bool
        False,           # Expect Python bool
        None,            # Expect Python None
        Symbol('symbol-name') # Keep other symbols
    ]
    assert parser.parse_string(sexp_string) == expected_ast

def test_parse_string_literal(parser):
    """Test parsing a simple string literal."""
    sexp_string = "\"this is a string\""
    expected_ast = "this is a string"
    assert parser.parse_string(sexp_string) == expected_ast

def test_parse_integer_literal(parser):
    """Test parsing a simple integer literal."""
    sexp_string = "42"
    expected_ast = 42
    assert parser.parse_string(sexp_string) == expected_ast

def test_parse_float_literal(parser):
    """Test parsing a simple float literal."""
    sexp_string = "3.14159"
    expected_ast = 3.14159
    assert parser.parse_string(sexp_string) == expected_ast

def test_parse_symbol(parser):
    """Test parsing a simple symbol."""
    sexp_string = "my-symbol"
    expected_ast = Symbol('my-symbol')
    assert parser.parse_string(sexp_string) == expected_ast

def test_parse_true_symbol(parser):
    """Test parsing the 'true' symbol."""
    sexp_string = "true"
    expected_ast = True
    assert parser.parse_string(sexp_string) == expected_ast
    assert isinstance(parser.parse_string(sexp_string), bool)

def test_parse_false_symbol(parser):
    """Test parsing the 'false' symbol."""
    sexp_string = "false"
    expected_ast = False
    assert parser.parse_string(sexp_string) == expected_ast
    assert isinstance(parser.parse_string(sexp_string), bool)

def test_parse_nil_symbol(parser):
    """Test parsing the 'nil' symbol."""
    sexp_string = "nil"
    expected_ast = None
    assert parser.parse_string(sexp_string) == expected_ast

def test_parse_empty_list(parser):
    """Test parsing an empty list '()'."""
    sexp_string = "()"
    expected_ast = [] # sexpdata parses () as an empty list
    assert parser.parse_string(sexp_string) == expected_ast

def test_parse_list_with_only_nil(parser):
    """Test parsing '(nil)'."""
    sexp_string = "(nil)"
    # Expect list containing None now
    expected_ast = [None]
    assert parser.parse_string(sexp_string) == expected_ast

def test_parse_list_with_booleans(parser):
    """Test parsing list containing true/false."""
    sexp_string = "(list true false)"
    expected_ast = [Symbol('list'), True, False]
    assert parser.parse_string(sexp_string) == expected_ast

def test_parse_string_with_escapes(parser):
    """Test parsing string with escape characters."""
    sexp_string = "\"string with \\\"quotes\\\" and \\\\ backslash\""
    expected_ast = "string with \"quotes\" and \\ backslash"
    assert parser.parse_string(sexp_string) == expected_ast

# --- Test Invalid S-expressions ---

def test_parse_unbalanced_parentheses_missing_close(parser):
    """Test parsing with a missing closing parenthesis."""
    sexp_string = "(add 1 2"
    with pytest.raises(SexpSyntaxError) as excinfo:
        parser.parse_string(sexp_string)
    assert "Unbalanced parentheses" in str(excinfo.value)
    assert sexp_string in str(excinfo.value) # Ensure original string is in error

def test_parse_unbalanced_parentheses_extra_close(parser):
    """Test parsing with an extra closing parenthesis."""
    sexp_string = "(add 1 2))"
    with pytest.raises(SexpSyntaxError) as excinfo:
        parser.parse_string(sexp_string)
    # sexpdata raises ExpectNothing when there's extra content
    assert "Unexpected content after the main expression" in str(excinfo.value)
    assert sexp_string in str(excinfo.value)

def test_parse_invalid_token_unmatched_paren(parser):
    """Test parsing with unmatched parenthesis as invalid syntax."""
    # Change input to something guaranteed to be invalid syntax
    sexp_string = "(a b c" # Unmatched parenthesis
    with pytest.raises(SexpSyntaxError) as excinfo:
        parser.parse_string(sexp_string)
    # Check that it's the correct error type and contains the input
    assert isinstance(excinfo.value, SexpSyntaxError)
    assert "Unbalanced parentheses" in str(excinfo.value) # Check specific message
    assert sexp_string in str(excinfo.value)


def test_parse_multiple_expressions_without_list(parser):
    """Test parsing multiple top-level expressions without being in a list."""
    sexp_string = "(expr1) (expr2)"
    with pytest.raises(SexpSyntaxError) as excinfo:
        parser.parse_string(sexp_string)
    # sexpdata raises ExpectNothing after parsing the first expression
    assert "Unexpected content after the main expression" in str(excinfo.value)
    assert sexp_string in str(excinfo.value)

def test_parse_non_string_input(parser):
    """Test passing non-string input."""
    with pytest.raises(TypeError):
        parser.parse_string(123)
    with pytest.raises(TypeError):
        parser.parse_string(None)
    with pytest.raises(TypeError):
        parser.parse_string(["list", "is", "not", "string"])
