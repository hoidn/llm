"""
Unit tests for the SexpEvaluator.
"""

import pytest
import re # Import re for regular expression matching in error messages
import logging
from unittest.mock import MagicMock, call, ANY, patch
from src.sexp_evaluator.sexp_evaluator import SexpEvaluator
from src.sexp_evaluator.sexp_environment import SexpEnvironment
from src.system.errors import SexpSyntaxError, SexpEvaluationError # Remove TaskError import from here
from src.system.models import (
    TaskResult, SubtaskRequest, ContextGenerationInput, AssociativeMatchResult,
    MatchTuple, TaskFailureError, ContextManagement, TaskError # Import TaskError model here
)
from src.sexp_parser.sexp_parser import SexpParser

# Import Quoted for debugging
from sexpdata import Quoted as TestQuotedFromSexpdata, Symbol as TestFileSymbol
# Use print for tests if logging isn't captured early enough
print(f"CRITICAL TestSexpEvaluator: Imported Quoted type: {type(TestQuotedFromSexpdata)}, id: {id(TestQuotedFromSexpdata)}, module: {getattr(TestQuotedFromSexpdata, '__module__', 'N/A')}")

# Import Symbol if parser uses it, otherwise use str
try:
    from sexpdata import Symbol
except ImportError:
    Symbol = str # Fallback to string if sexpdata not installed or parser uses strings

# --- Fixtures ---

@pytest.fixture
def mock_task_system(mocker):
    """Mock TaskSystem dependency."""
    mock = MagicMock()
    mock.find_template.return_value = None # Default: template not found
    # Default: successful atomic task execution
    mock.execute_atomic_template.return_value = TaskResult(
        status="COMPLETE", content="Atomic Task Result", notes={}
    )
    return mock

@pytest.fixture
def mock_handler(mocker):
    """Mock BaseHandler dependency."""
    mock = MagicMock()
    mock.tool_executors = {} # Default: no tools registered
    # Default: successful tool execution
    mock._execute_tool.return_value = TaskResult(
        status="COMPLETE", content="Direct Tool Result", notes={}
    )
    return mock

@pytest.fixture
def mock_memory_system(mocker):
    """Mock MemorySystem dependency."""
    mock = MagicMock()
    # Default: successful context retrieval
    mock.get_relevant_context_for.return_value = AssociativeMatchResult(
        context_summary="Mock context summary",
        matches=[MatchTuple(path="/mock/file.py", relevance=0.9)], # Use correct model
        error=None
    )
    return mock

@pytest.fixture
def mock_parser(mocker):
    """Mock SexpParser dependency."""
    mock = MagicMock()
    mock.parse_string.return_value = None # Default: will be overridden in tests
    return mock

@pytest.fixture
def evaluator(mock_task_system, mock_handler, mock_memory_system, mock_parser, mocker):
    """Fixture for SexpEvaluator instance with mocked parser."""
    import logging
    logging.critical("Creating evaluator fixture")
    # Patch the SexpParser instantiation within the evaluator's init
    with patch('src.sexp_evaluator.sexp_evaluator.SexpParser', return_value=mock_parser):
         evaluator_instance = SexpEvaluator(
             task_system=mock_task_system,
             handler=mock_handler,
             memory_system=mock_memory_system
         )
    logging.critical(f"Created evaluator fixture. PRIMITIVE_APPLIERS keys: {list(evaluator_instance.PRIMITIVE_APPLIERS.keys())}")
    return evaluator_instance

# --- Test Cases ---

# Literals
@pytest.mark.parametrize("sexp_string, expected_ast, expected_result", [
    ('"hello"', "hello", "hello"),
    ('123', 123, 123),
    ('3.14', 3.14, 3.14),
    ('true', True, True), # Assuming parser handles bools
    ('false', False, False),
    ('nil', None, None), # Assuming parser handles nil
    # Test literal list evaluation (if parser returns lists for literals)
    # ('(1 2 3)', [1, 2, 3], [1, 2, 3]), # This depends heavily on parser behavior for non-call lists
])
def test_eval_literal(evaluator, mock_parser, sexp_string, expected_ast, expected_result):
    """Test evaluation of literal values."""
    mock_parser.parse_string.return_value = expected_ast
    result = evaluator.evaluate_string(sexp_string)
    assert result == expected_result
    mock_parser.parse_string.assert_called_once_with(sexp_string)

# Symbol Lookup
def test_eval_symbol_lookup_success(evaluator, mock_parser):
    """Test successful lookup of a defined symbol."""
    env = SexpEnvironment()
    env.define("my_var", 42)
    symbol_node = Symbol("my_var") if Symbol != str else "my_var"
    mock_parser.parse_string.return_value = symbol_node
    result = evaluator.evaluate_string("my_var", initial_env=env)
    assert result == 42

def test_eval_symbol_lookup_fail(evaluator, mock_parser):
    """Test failure when looking up an undefined symbol."""
    symbol_node = Symbol("undefined_var") if Symbol != str else "undefined_var"
    mock_parser.parse_string.return_value = symbol_node
    # Fix: Update match pattern to be less specific or use re.escape
    with pytest.raises(SexpEvaluationError, match="Unbound symbol"):
        evaluator.evaluate_string("undefined_var") # Use default empty env

# Primitive: list
def test_eval_primitive_list(evaluator, mock_parser):
    """Test the (list ...) primitive."""
    list_sym = Symbol("list") if Symbol != str else "list"
    a_sym = Symbol("a") if Symbol != str else "a"
    true_sym = Symbol("true") if Symbol != str else "true" # Assuming parser returns symbols/strings for bools
    mock_parser.parse_string.return_value = [list_sym, 1, a_sym, [list_sym, true_sym]]
    env = SexpEnvironment()
    env.define("a", "hello")
    env.define("true", True) # Define true if parser doesn't handle it
    result = evaluator.evaluate_string("(list 1 a (list true))", initial_env=env)
    assert result == [1, "hello", [True]] # Expect evaluated items

# Primitive: let (Test Scoping)
def test_eval_primitive_let_scoping(evaluator, mock_parser):
    """Test 'let' for creating nested scopes and accessing bindings."""
    let_sym = Symbol("let") if Symbol != str else "let"
    x_sym = Symbol("x") if Symbol != str else "x"
    y_sym = Symbol("y") if Symbol != str else "y"
    # Sexp: (let ((x 10) (y 20)) y) -> 20
    mock_parser.parse_string.return_value = [let_sym, [[x_sym, 10], [y_sym, 20]], y_sym]
    result = evaluator.evaluate_string("(let ((x 10) (y 20)) y)")
    assert result == 20

def test_eval_primitive_let_uses_outer_scope_for_values(evaluator, mock_parser):
    """Test that 'let' binding values are evaluated in the outer scope."""
    let_sym = Symbol("let") if Symbol != str else "let"
    x_sym = Symbol("x") if Symbol != str else "x"
    y_sym = Symbol("y") if Symbol != str else "y"
    # Sexp: (let ((x 10)) (let ((y x)) y)) -> 10
    mock_parser.parse_string.return_value = [let_sym, [[x_sym, 10]], [let_sym, [[y_sym, x_sym]], y_sym]]
    result = evaluator.evaluate_string("(let ((x 10)) (let ((y x)) y))")
    assert result == 10

# Primitive: bind
def test_eval_primitive_bind(evaluator, mock_parser):
    """Test 'bind' for defining variables in the current scope."""
    bind_sym = Symbol("bind") if Symbol != str else "bind"
    my_var_sym = Symbol("my_var") if Symbol != str else "my_var"
    # Sexp: (bind my_var 100)
    mock_parser.parse_string.return_value = [bind_sym, my_var_sym, 100]
    env = SexpEnvironment()
    result = evaluator.evaluate_string("(bind my_var 100)", initial_env=env)
    assert result == 100
    assert env.lookup("my_var") == 100 # Check that it was defined in the passed env

# Primitive: if
@pytest.mark.parametrize("condition_val, expected_branch", [(True, "then_branch"), (False, "else_branch")])
def test_eval_primitive_if(evaluator, mock_parser, condition_val, expected_branch):
    """Test the 'if' special form."""
    if_sym = Symbol("if") if Symbol != str else "if"
    cond_sym = Symbol("condition") if Symbol != str else "condition"
    env = SexpEnvironment()
    env.define("condition", condition_val)
    mock_parser.parse_string.return_value = [if_sym, cond_sym, "then_branch", "else_branch"]
    result = evaluator.evaluate_string('(if condition "then_branch" "else_branch")', initial_env=env)
    assert result == expected_branch

# Primitive: get_context
def test_eval_primitive_get_context(evaluator, mock_parser, mock_memory_system):
    """Test the (get_context ...) primitive."""
    get_context_sym = Symbol("get_context")
    query_sym = Symbol("query")
    inputs_sym = Symbol("inputs")
    file_sym = Symbol("file")
    quote_sym = Symbol("quote")

    sexp_str = '(get_context (query "find stuff") (inputs (quote ((file "/a.py")))))'
    # AST: [get_context, [query, "find stuff"], [inputs, [quote, [[file, "/a.py"]]]]]
    ast = [
        get_context_sym,
        [query_sym, "find stuff"],
        [inputs_sym, [quote_sym, [[file_sym, "/a.py"]]]]
    ]
    mock_parser.parse_string.return_value = ast
    
    expected_context_input = ContextGenerationInput(
        query="find stuff",
        inputs={"file": "/a.py"} 
    )
    mock_memory_system.get_relevant_context_for.return_value = AssociativeMatchResult(
        context_summary="Mocked context", matches=[MatchTuple(path="/mock/file.py", relevance=1.0)]
    )

    result = evaluator.evaluate_string(sexp_str)

    mock_memory_system.get_relevant_context_for.assert_called_once_with(expected_context_input)
    call_args, _ = mock_memory_system.get_relevant_context_for.call_args
    assert call_args[0].matching_strategy is None # Default matching strategy

    assert result == ["/mock/file.py"]

def test_eval_primitive_get_context_failure(evaluator, mock_parser, mock_memory_system):
    """Test get_context when memory system returns an error."""
    get_context_sym = Symbol("get_context")
    query_sym = Symbol("query")
    sexp_str = '(get_context (query "find stuff"))'
    ast = [get_context_sym, [query_sym, "find stuff"]]
    mock_parser.parse_string.return_value = ast
    
    mock_memory_system.get_relevant_context_for.return_value = AssociativeMatchResult(
        context_summary="", matches=[], error="Database connection failed"
    )

    # Simplified regex pattern to be more flexible
    expected_error_pattern = re.compile(
        r"Context retrieval failed \(MemorySystem error\).*"
        r"Expression:.*\[Symbol\('get_context'\).*\[Symbol\('query'\).*'find stuff'\].*"
        r"Details:.*Database connection failed", 
        re.DOTALL
    )
    with pytest.raises(SexpEvaluationError, match=expected_error_pattern) as excinfo:
        evaluator.evaluate_string(sexp_str)
    # No need for the separate assert on error_details if the regex covers it.
    # However, if you want to be very specific about the error_details attribute:
    assert excinfo.value.error_details == "Database connection failed"


def test_eval_primitive_get_context_with_content_strategy(evaluator, mock_parser, mock_memory_system):
    """Test get_context with explicit content strategy."""
    get_context_sym = Symbol("get_context")
    query_sym = Symbol("query")
    strategy_sym = Symbol("matching_strategy")

    sexp_str = "(get_context (query \"q\") (matching_strategy \"content\"))" # Use string literal 'content'
    # AST: [get_context, [query, "q"], [matching_strategy, "content"]]
    ast = [
        get_context_sym,
        [query_sym, "q"],
        [strategy_sym, "content"] # Pass as string literal
    ]
    mock_parser.parse_string.return_value = ast
    
    expected_context_input = ContextGenerationInput(query="q", matching_strategy='content')
    mock_memory_system.get_relevant_context_for.return_value = AssociativeMatchResult(
        context_summary="Mock context summary",
        matches=[]
    )

    evaluator.evaluate_string(sexp_str)
    mock_memory_system.get_relevant_context_for.assert_called_once_with(expected_context_input)

def test_eval_primitive_get_context_with_metadata_strategy(evaluator, mock_parser, mock_memory_system):
    """Test get_context with explicit metadata strategy."""
    get_context_sym = Symbol("get_context")
    query_sym = Symbol("query")
    strategy_sym = Symbol("matching_strategy")

    sexp_str = "(get_context (query \"q\") (matching_strategy \"metadata\"))" # Use string literal 'metadata'
    ast = [
        get_context_sym,
        [query_sym, "q"],
        [strategy_sym, "metadata"] # Pass as string literal
    ]
    mock_parser.parse_string.return_value = ast
    
    expected_context_input = ContextGenerationInput(query="q", matching_strategy='metadata')
    mock_memory_system.get_relevant_context_for.return_value = AssociativeMatchResult(
        context_summary="Mock context summary",
        matches=[]
    )

    evaluator.evaluate_string(sexp_str)
    mock_memory_system.get_relevant_context_for.assert_called_once_with(expected_context_input)

def test_eval_primitive_get_context_invalid_strategy_value_evaluated(evaluator, mock_parser):
    """Test get_context with an invalid strategy value (after evaluation)."""
    get_context_sym = Symbol("get_context")
    query_sym = Symbol("query")
    strategy_sym = Symbol("matching_strategy")
    
    # Sexp: (get_context (query "q") (matching_strategy "invalid_string_literal"))
    # This string literal "invalid_string_literal" will be the evaluated value.
    sexp_str = '(get_context (query "q") (matching_strategy "invalid_string_literal"))'
    ast = [
        get_context_sym,
        [query_sym, "q"],
        [strategy_sym, "invalid_string_literal"] # Pass as string literal
    ]
    mock_parser.parse_string.return_value = ast

    with pytest.raises(SexpEvaluationError, match="Invalid value for 'matching_strategy'. Expected 'content' or 'metadata', got: 'invalid_string_literal'"):
        evaluator.evaluate_string(sexp_str)

def test_eval_primitive_get_context_invalid_strategy_type_evaluated(evaluator, mock_parser):
    """Test get_context with an invalid strategy type (e.g., number, after evaluation)."""
    get_context_sym = Symbol("get_context")
    query_sym = Symbol("query")
    strategy_sym = Symbol("matching_strategy")

    sexp_str = "(get_context (query \"q\") (matching_strategy 123))"
    ast = [
        get_context_sym,
        [query_sym, "q"],
        [strategy_sym, 123] # Number literal
    ]
    mock_parser.parse_string.return_value = ast

    with pytest.raises(SexpEvaluationError, match="Invalid value for 'matching_strategy'. Expected 'content' or 'metadata', got: 123"):
         evaluator.evaluate_string(sexp_str)


# Invocation: Atomic Task
def test_eval_invoke_atomic_task(evaluator, mock_parser, mock_task_system):
    """Test invoking a registered atomic task."""
    task_name = "my_atomic_task"
    task_sym = Symbol(task_name) if Symbol != str else task_name
    arg1_sym = Symbol("arg1") if Symbol != str else "arg1"
    arg2_sym = Symbol("arg2") if Symbol != str else "arg2"
    # Mock TaskSystem to recognize this template
    mock_task_system.find_template.return_value = {"name": task_name, "type": "atomic"} # Minimal def

    # Sexp: (my_atomic_task (arg1 "value1") (arg2 123))
    mock_parser.parse_string.return_value = [task_sym, [arg1_sym, "value1"], [arg2_sym, 123]]

    result = evaluator.evaluate_string('(my_atomic_task (arg1 "value1") (arg2 123))')

    # Assert TaskSystem was called correctly
    mock_task_system.execute_atomic_template.assert_called_once()
    call_args, call_kwargs = mock_task_system.execute_atomic_template.call_args
    assert len(call_args) == 1
    request_arg = call_args[0]
    assert isinstance(request_arg, SubtaskRequest)
    assert request_arg.name == task_name
    assert request_arg.type == "atomic"
    assert request_arg.inputs == {"arg1": "value1", "arg2": 123}
    assert request_arg.file_paths is None
    assert request_arg.context_management is None

    # Assert result is from the mock TaskSystem call (converted back to object)
    assert isinstance(result, TaskResult)
    assert result.status == "COMPLETE"
    assert result.content == "Atomic Task Result"

def test_eval_invoke_atomic_task_with_files_and_context(evaluator, mock_parser, mock_task_system):
    """Test invoking atomic task passing 'files' and 'context' args."""
    task_name = "task_with_context"
    task_sym = Symbol(task_name) if Symbol != str else task_name
    files_sym = Symbol("files") if Symbol != str else "files"
    context_sym = Symbol("context") if Symbol != str else "context"
    list_sym = Symbol("list") if Symbol != str else "list"
    # Add quote symbol
    quote_sym = Symbol("quote") if Symbol != str else "quote"

    mock_task_system.find_template.return_value = {"name": task_name, "type": "atomic"}

    # Sexp: (task_with_context (files (list "/a.txt" "/b.txt")) (context (quote ((inheritContext "none") (freshContext "disabled")))))
    mock_parser.parse_string.return_value = [
        task_sym,
        [files_sym, [list_sym, "/a.txt", "/b.txt"]],
        # Use quote around the literal list of pairs structure
        [context_sym, [quote_sym,
                       [[Symbol('inheritContext'), "none"],
                        [Symbol('freshContext'), "disabled"]]]]
    ]
    # Mock the result from execute_atomic_template
    mock_task_system.execute_atomic_template.return_value = TaskResult(status="COMPLETE", content="Context task done")

    result = evaluator.evaluate_string('(task_with_context ...)') # Test string content doesn't matter

    assert isinstance(result, TaskResult)
    assert result.status == "COMPLETE"
    # Assert mock call with correct SubtaskRequest structure
    mock_task_system.execute_atomic_template.assert_called_once()
    call_args, call_kwargs = mock_task_system.execute_atomic_template.call_args
    assert len(call_args) == 1
    request = call_args[0]
    assert isinstance(request, SubtaskRequest)
    assert request.name == task_name
    assert request.inputs == {}
    assert request.file_paths == ["/a.txt", "/b.txt"]
    assert request.context_management is not None
    # Check that the evaluated+converted dict was used to create the ContextManagement object
    assert isinstance(request.context_management, ContextManagement)
    assert request.context_management.inheritContext == "none"
    assert request.context_management.freshContext == "disabled"

# Invocation: Direct Tool
def test_eval_invoke_direct_tool(evaluator, mock_parser, mock_handler):
    """Test invoking a registered direct tool."""
    tool_name = "my_direct_tool"
    tool_sym = Symbol(tool_name) if Symbol != str else tool_name
    param_sym = Symbol("param") if Symbol != str else "param"
    # Mock Handler to have this tool
    mock_tool_executor = MagicMock(return_value=TaskResult(status="COMPLETE", content="Tool Success")) # Mock the executor function if needed
    mock_handler.tool_executors = {tool_name: mock_tool_executor} # Store the function itself

    # Sexp: (my_direct_tool (param "data"))
    mock_parser.parse_string.return_value = [tool_sym, [param_sym, "data"]]

    result = evaluator.evaluate_string('(my_direct_tool (param "data"))')

    # Assert Handler._execute_tool was called correctly
    mock_handler._execute_tool.assert_called_once_with(tool_name, {"param": "data"})
    # Assert result is from the mock handler call (converted back to object)
    assert isinstance(result, TaskResult)
    assert result.status == "COMPLETE"
    assert result.content == "Direct Tool Result"

# Invocation: Not Found
def test_eval_invoke_not_found(evaluator, mock_parser, mock_task_system, mock_handler):
    """Test failure when invoking an unknown identifier."""
    unknown_id = "unknown_command"
    unknown_sym = Symbol(unknown_id) if Symbol != str else unknown_id
    mock_parser.parse_string.return_value = [unknown_sym]
    # Ensure mocks return None/empty
    mock_task_system.find_template.return_value = None
    mock_handler.tool_executors = {}

    # Match the expected error message for unknown task/tool
    with pytest.raises(SexpEvaluationError, match=f"Unbound symbol or unrecognized operator: {unknown_id}"):
        evaluator.evaluate_string(f"({unknown_id})")

def test_eval_special_form_quote_atom(evaluator, mock_parser):
    """Test quoting atomic values."""
    quote_sym = Symbol("quote") if Symbol != str else "quote"
    foo_sym = Symbol("foo") if Symbol != str else "foo"

    # Test quoting a symbol
    mock_parser.parse_string.return_value = [quote_sym, foo_sym]
    result = evaluator.evaluate_string("(quote foo)")
    # Should return the symbol itself, not its value
    assert isinstance(result, Symbol if 'Symbol' in locals() else str)
    assert (result.value() if isinstance(result, Symbol) else result) == "foo"

    # Test quoting a string
    mock_parser.parse_string.return_value = [quote_sym, "hello"]
    result = evaluator.evaluate_string('(quote "hello")')
    assert result == "hello"

    # Test quoting a number
    mock_parser.parse_string.return_value = [quote_sym, 123]
    result = evaluator.evaluate_string('(quote 123)')
    assert result == 123

def test_eval_special_form_quote_list(evaluator, mock_parser):
    """Test quoting lists."""
    quote_sym = Symbol("quote") if Symbol != str else "quote"
    a_sym = Symbol("a") if Symbol != str else "a"
    b_sym = Symbol("b") if Symbol != str else "b"
    c_sym = Symbol("c") if Symbol != str else "c"
    list_sym = Symbol("list") if Symbol != str else "list" # Example symbol within list

    # Test quoting a simple list of symbols
    mock_parser.parse_string.return_value = [quote_sym, [a_sym, b_sym, c_sym]]
    result = evaluator.evaluate_string("(quote (a b c))")
    assert isinstance(result, list)
    assert len(result) == 3
    # Check elements are symbols (or strings if Symbol not used)
    assert (result[0].value() if isinstance(result[0], Symbol) else result[0]) == "a"
    assert (result[1].value() if isinstance(result[1], Symbol) else result[1]) == "b"
    assert (result[2].value() if isinstance(result[2], Symbol) else result[2]) == "c"

    # Test quoting a nested list
    mock_parser.parse_string.return_value = [quote_sym, [a_sym, [list_sym, b_sym], c_sym]]
    result = evaluator.evaluate_string("(quote (a (list b) c))")
    assert isinstance(result, list)
    assert len(result) == 3
    assert (result[0].value() if isinstance(result[0], Symbol) else result[0]) == "a"
    assert isinstance(result[1], list)
    assert (result[1][0].value() if isinstance(result[1][0], Symbol) else result[1][0]) == "list"
    assert (result[1][1].value() if isinstance(result[1][1], Symbol) else result[1][1]) == "b"
    assert (result[2].value() if isinstance(result[2], Symbol) else result[2]) == "c"

def test_eval_special_form_quote_prevents_evaluation(evaluator, mock_parser):
    """Test that quote prevents evaluation of symbols inside it."""
    quote_sym = Symbol("quote") if Symbol != str else "quote"
    let_sym = Symbol("let") if Symbol != str else "let"
    x_sym = Symbol("x") if Symbol != str else "x"

    # Sexp: (let ((x 10)) (quote x))
    mock_parser.parse_string.return_value = [let_sym, [[x_sym, 10]], [quote_sym, x_sym]]
    result = evaluator.evaluate_string("(let ((x 10)) (quote x))")
    # Should return the symbol 'x', not the value 10
    assert isinstance(result, Symbol if 'Symbol' in locals() else str)
    assert (result.value() if isinstance(result, Symbol) else result) == "x"

def test_eval_special_form_quote_errors(evaluator, mock_parser):
    """Test errors for quote."""
    quote_sym = Symbol("quote") if Symbol != str else "quote"
    a_sym = Symbol("a") if Symbol != str else "a"
    b_sym = Symbol("b") if Symbol != str else "b"

    # No arguments
    mock_parser.parse_string.return_value = [quote_sym]
    with pytest.raises(SexpEvaluationError, match="'quote' requires exactly one argument"):
        evaluator.evaluate_string("(quote)")

    # Too many arguments
    mock_parser.parse_string.return_value = [quote_sym, a_sym, b_sym]
    with pytest.raises(SexpEvaluationError, match="'quote' requires exactly one argument"):
        evaluator.evaluate_string("(quote a b)")

# Error Handling
def test_evaluate_string_syntax_error(evaluator, mock_parser):
    """Test propagation of SexpSyntaxError from parser."""
    mock_parser.parse_string.side_effect = SexpSyntaxError("Bad syntax", "(invalid", "details")
    with pytest.raises(SexpSyntaxError):
        evaluator.evaluate_string("(invalid")

def test_evaluate_string_task_error_propagation(evaluator, mock_parser, mock_task_system):
    """Test propagation of TaskError from underlying TaskSystem call."""
    task_name = "failing_task"
    task_sym = Symbol(task_name) if Symbol != str else task_name
    mock_parser.parse_string.return_value = [task_sym]
    mock_task_system.find_template.return_value = {"name": task_name, "type": "atomic"}
    # Configure TaskSystem mock to raise RuntimeError (or SexpEvaluationError directly)
    mock_task_system.execute_atomic_template.side_effect = RuntimeError("Simulated task timeout")

    # Expect the SexpEvaluationError wrapper
    with pytest.raises(SexpEvaluationError) as excinfo:
        evaluator.evaluate_string(f"({task_name})")

    # Check the wrapped exception details
    assert "Simulated task timeout" in str(excinfo.value) # Check wrapped message

# Implicit Progn (Sequence at top level)
def test_evaluate_string_implicit_progn(evaluator, mock_parser):
    """Test evaluation of a sequence of top-level expressions (SHOULD FAIL PARSING)."""
    bind_sym = Symbol("bind") if Symbol != str else "bind"
    x_sym = Symbol("x") if Symbol != str else "x"
    y_sym = Symbol("y") if Symbol != str else "y"
    # Sexp: (bind x 10) (bind y 20) y
    # Mock parser to simulate invalid input (multiple expressions)
    # This depends on the SexpParser raising SexpSyntaxError for multiple expressions now.
    mock_parser.parse_string.side_effect = SexpSyntaxError(
        "Multiple top-level S-expressions found.", "(bind x 10) (bind y 20) y"
    )

    # Assert that SexpSyntaxError is raised by the parser
    with pytest.raises(SexpSyntaxError, match="Multiple top-level S-expressions found"):
        evaluator.evaluate_string("(bind x 10) (bind y 20) y")


# --- Test Class for defatom ---
# Use the existing 'evaluator' fixture which has mocks injected
class TestSexpEvaluatorDefatom:

    def test_defatom_basic_registration(self, evaluator, mock_parser, mock_task_system):
        """Test basic defatom registration with minimal arguments."""
        task_name = "my-task"
        task_sym = Symbol(task_name)
        params_sym = Symbol("params")
        p1_sym = Symbol("p1")
        str_sym = Symbol("str") # Placeholder type
        instructions_sym = Symbol("instructions")

        sexp_ast = [
            Symbol("defatom"),
            task_sym,
            [params_sym, [p1_sym, str_sym]],
            [instructions_sym, "inst {{p1}}"]
        ]
        mock_parser.parse_string.return_value = sexp_ast

        expected_template_dict = {
            "name": task_name,
            "type": "atomic",
            "subtype": "standard", # Default
            "description": f"Dynamically defined task: {task_name}", # Default
            "params": {"p1": {"description": "Parameter p1"}},
            "instructions": "inst {{p1}}",
            # "model": None # Ensure not present if not specified # This line was problematic
        }
        # Clear model if it exists from optional args test
        # if "model" in expected_template_dict: del expected_template_dict["model"] # This was also problematic


        mock_task_system.register_template.return_value = True # Simulate success

        result = evaluator.evaluate_string(f"(defatom {task_name} ...)") # String content doesn't matter due to mock

        # Remove 'model' from expected_template_dict if it's None and not in the actual call
        # This is a common pattern if the production code omits None values during dict creation
        # For this specific test, 'model' should not be in the dict if not specified.
        # The production code for defatom does:
        # if "model" in optional_args_map: template_dict["model"] = optional_args_map["model"]
        # So if not in optional_args_map, it's not added.
        # The original expected_template_dict was correct in omitting "model": None.

        mock_task_system.register_template.assert_called_once_with(expected_template_dict)
        assert isinstance(result, Symbol)
        assert result.value() == task_name

    def test_defatom_with_optional_args(self, evaluator, mock_parser, mock_task_system):
        """Test defatom registration with optional arguments."""
        task_name = "fancy"
        task_sym = Symbol(task_name)
        params_sym = Symbol("params")
        a_sym = Symbol("a")
        any_sym = Symbol("any")
        b_sym = Symbol("b")
        int_sym = Symbol("int")
        instructions_sym = Symbol("instructions")
        subtype_sym = Symbol("subtype")
        description_sym = Symbol("description")
        model_sym = Symbol("model")

        sexp_ast = [
            Symbol("defatom"),
            task_sym,
            [params_sym, [a_sym, any_sym], [b_sym, int_sym]],
            [instructions_sym, "Do {{a}} {{b}}"],
            [subtype_sym, "subtask"],
            [description_sym, "Desc"],
            [model_sym, "claude"]
        ]
        mock_parser.parse_string.return_value = sexp_ast

        expected_template_dict = {
            "name": task_name,
            "type": "atomic",
            "subtype": "subtask",
            "description": "Desc",
            "params": {
                "a": {"description": "Parameter a"},
                "b": {"description": "Parameter b"}
            },
            "instructions": "Do {{a}} {{b}}",
            "model": "claude"
        }

        mock_task_system.register_template.return_value = True

        result = evaluator.evaluate_string(f"(defatom {task_name} ...)")

        mock_task_system.register_template.assert_called_once_with(expected_template_dict)
        assert isinstance(result, Symbol)
        assert result.value() == task_name

    def test_defatom_invocation_after_definition(self, evaluator, mock_parser, mock_task_system):
        """Test invoking a task immediately after defining it with defatom."""
        def_task_name = "task-a"
        def_task_sym = Symbol(def_task_name)
        params_sym = Symbol("params")
        x_sym = Symbol("x")
        str_sym = Symbol("str")
        instructions_sym = Symbol("instructions")
        progn_sym = Symbol("progn")

        defatom_ast = [
            Symbol("defatom"),
            def_task_sym,
            [params_sym, [x_sym, str_sym]],
            [instructions_sym, "Run {{x}}"]
        ]
        invocation_ast = [def_task_sym, [x_sym, "val"]]
        sexp_ast = [progn_sym, defatom_ast, invocation_ast] # Use progn to sequence

        mock_parser.parse_string.return_value = sexp_ast

        # Mock registration success
        mock_task_system.register_template.return_value = True
        
        expected_template_dict_for_registration = {
            "name": def_task_name, "type": "atomic", "subtype": "standard",
            "description": f"Dynamically defined task: {def_task_name}",
            "params": {"x": {"description": "Parameter x"}},
            "instructions": "Run {{x}}",
            # "model": None # Should not be present if not specified
        }

        # Mock find_template to return the definition *after* registration is called
        # This is what the SexpEvaluator's _invoke_task_system will use
        expected_template_dict_for_find = {
            "name": def_task_name, "type": "atomic", "subtype": "standard",
            "description": f"Dynamically defined task: {def_task_name}",
            "params": {"x": {"description": "Parameter x"}}, # Params might or might not be here depending on find_template's detail
            "instructions": "Run {{x}}",
            # "model": None # Should not be present if not specified
        }
        mock_task_system.find_template.side_effect = lambda name: expected_template_dict_for_find if name == def_task_name else None


        # Mock invocation result
        mock_invocation_result = TaskResult(status="COMPLETE", content="Task A Done")
        mock_task_system.execute_atomic_template.return_value = mock_invocation_result

        result = evaluator.evaluate_string(f"(progn (defatom {def_task_name} ...) ({def_task_name} ...))")

        # Assert registration happened
        mock_task_system.register_template.assert_called_once_with(expected_template_dict_for_registration)

        # Assert invocation happened correctly
        mock_task_system.execute_atomic_template.assert_called_once()
        call_args, _ = mock_task_system.execute_atomic_template.call_args
        request = call_args[0]
        assert isinstance(request, SubtaskRequest)
        assert request.name == def_task_name
        assert request.inputs == {"x": "val"}

        # Assert final result is the invocation result
        assert result == mock_invocation_result

    def test_defatom_missing_args(self, evaluator, mock_parser):
        """Test defatom with too few arguments."""
        sexp_ast = [Symbol("defatom"), Symbol("name")] # Only name
        mock_parser.parse_string.return_value = sexp_ast
        with pytest.raises(SexpEvaluationError, match=r"'defatom' requires at least name, params, and instructions"):
            evaluator.evaluate_string("(defatom name)")

    def test_defatom_name_not_symbol(self, evaluator, mock_parser):
        """Test defatom with a non-symbol task name."""
        sexp_ast = [Symbol("defatom"), "name", [Symbol("params")], [Symbol("instructions"), ""]] # Name is string
        mock_parser.parse_string.return_value = sexp_ast
        with pytest.raises(SexpEvaluationError, match=r"'defatom' task name must be a Symbol"):
            evaluator.evaluate_string('(defatom "name" ...)')

    def test_defatom_missing_params(self, evaluator, mock_parser):
        """Test defatom without a (params ...) definition."""
        sexp_ast = [Symbol("defatom"), Symbol("name"), [Symbol("instructions"), "inst"]] # Missing params
        mock_parser.parse_string.return_value = sexp_ast
        # Fix: Match the actual error message from the length check
        with pytest.raises(SexpEvaluationError, match=r"'defatom' requires at least name, params, and instructions arguments. Got 2."):
            evaluator.evaluate_string("(defatom name (instructions ...))")

    def test_defatom_invalid_params_format(self, evaluator, mock_parser):
        """Test defatom with invalid format within (params ...)."""
        # Case 1: params value is not a list
        sexp_ast_not_list = [
            Symbol("defatom"), Symbol("name"),
            [Symbol("params"), "bad"], # params value is string
            [Symbol("instructions"), "inst"]
        ]
        mock_parser.parse_string.return_value = sexp_ast_not_list
        with pytest.raises(SexpEvaluationError, match=r"Invalid parameter definition format"):
             evaluator.evaluate_string("(defatom name (params \"bad\") ...)")

        # Case 2: item inside params list is not a list or symbol
        sexp_ast_invalid_item = [
            Symbol("defatom"), Symbol("name"),
            [Symbol("params"), [Symbol("p1")], "bad-item"], # "bad-item" is not a list
             [Symbol("instructions"), "inst"]
        ]
        mock_parser.parse_string.return_value = sexp_ast_invalid_item
        with pytest.raises(SexpEvaluationError, match=r"Invalid parameter definition format"):
             evaluator.evaluate_string("(defatom name (params ((p1)) \"bad-item\") ...)")

        # Case 3: item inside params list is list but doesn't start with symbol
        sexp_ast_invalid_subitem = [
            Symbol("defatom"), Symbol("name"),
            [Symbol("params"), [123, Symbol("type")]], # Starts with number
             [Symbol("instructions"), "inst"]
        ]
        mock_parser.parse_string.return_value = sexp_ast_invalid_subitem
        with pytest.raises(SexpEvaluationError, match=r"Invalid parameter definition format"):
             evaluator.evaluate_string("(defatom name (params ((123 type))) ...)")


    def test_defatom_missing_instructions(self, evaluator, mock_parser):
        """Test defatom without an (instructions ...) definition."""
        sexp_ast = [Symbol("defatom"), Symbol("name"), [Symbol("params"), [Symbol("p1")]]] # Missing instructions
        mock_parser.parse_string.return_value = sexp_ast
        # Fix: Match the actual error message from the length check
        with pytest.raises(SexpEvaluationError, match=r"'defatom' requires at least name, params, and instructions arguments. Got 2."):
            evaluator.evaluate_string("(defatom name (params (p1)))")

    def test_defatom_instructions_not_string(self, evaluator, mock_parser):
        """Test defatom where instructions value is not a string."""
        sexp_ast = [
            Symbol("defatom"), Symbol("name"),
            [Symbol("params"), [Symbol("p1")]],
            [Symbol("instructions"), [Symbol("list"), "bad"]] # Value is a list
        ]
        mock_parser.parse_string.return_value = sexp_ast
        with pytest.raises(SexpEvaluationError, match=r"'defatom' requires an \(instructions \"string\"\) definition"):
            evaluator.evaluate_string("(defatom name (params (p1)) (instructions (list \"bad\")))")

    def test_defatom_invalid_optional_arg_format(self, evaluator, mock_parser):
        """Test defatom with an optional arg value that's not a string literal."""
        sexp_ast = [
            Symbol("defatom"), Symbol("name"),
            [Symbol("params"), [Symbol("p1")]],
            [Symbol("instructions"), "inst"],
            [Symbol("subtype"), [Symbol("list"), "bad"]] # Subtype value is a list
        ]
        mock_parser.parse_string.return_value = sexp_ast
        with pytest.raises(SexpEvaluationError, match=r"Value for optional argument 'subtype'.*must be a string"):
            evaluator.evaluate_string("(defatom name ... (subtype (list \"bad\")))")

    def test_defatom_unknown_optional_arg(self, evaluator, mock_parser):
        """Test defatom with an unknown optional argument key."""
        sexp_ast = [
            Symbol("defatom"), Symbol("name"),
            [Symbol("params"), [Symbol("p1")]],
            [Symbol("instructions"), "inst"],
            [Symbol("badkey"), "value"] # Unknown key
        ]
        mock_parser.parse_string.return_value = sexp_ast
        with pytest.raises(SexpEvaluationError, match=r"Unknown optional argument 'badkey'"):
            evaluator.evaluate_string("(defatom name ... (badkey \"value\"))")

    def test_defatom_registration_failure_exception(self, evaluator, mock_parser, mock_task_system):
        """Test defatom when TaskSystem.register_template raises an exception."""
        sexp_ast = [
            Symbol("defatom"), Symbol("my-task"),
            [Symbol("params"), [Symbol("p1")]],
            [Symbol("instructions"), "inst"]
        ]
        mock_parser.parse_string.return_value = sexp_ast
        mock_task_system.register_template.side_effect = ValueError("Mock registration error")

        with pytest.raises(SexpEvaluationError, match=r"Failed to register template.*Mock registration error"):
            evaluator.evaluate_string("(defatom my-task ...)")
        mock_task_system.register_template.assert_called_once() # Ensure it was called

    def test_defatom_registration_failure_false(self, evaluator, mock_parser, mock_task_system):
        """Test defatom when TaskSystem.register_template returns False."""
        sexp_ast = [
            Symbol("defatom"), Symbol("my-task"),
            [Symbol("params"), [Symbol("p1")]],
            [Symbol("instructions"), "inst"]
        ]
        mock_parser.parse_string.return_value = sexp_ast
        mock_task_system.register_template.return_value = False # Simulate non-exception failure

        with pytest.raises(SexpEvaluationError, match=r"TaskSystem failed to register template.*returned False"):
            evaluator.evaluate_string("(defatom my-task ...)")
        mock_task_system.register_template.assert_called_once() # Ensure it was called

# --- Tests for 'loop' Special Form ---
# Use a class to group loop tests if preferred, or keep them at module level
# Assuming Symbol is imported as S for brevity
S = Symbol if 'Symbol' in locals() else str

def test_eval_special_form_loop_basic_execution(evaluator, mock_parser, mock_handler):
    """Test loop executes body the correct number of times."""
    sexp_str = "(loop 3 (mock_task (arg \"val\")))" # Pass args to mock_task
    # AST: ['loop', 3, ['mock_task', ['arg', 'val']]]
    ast = [S('loop'), 3, [S('mock_task'), [S('arg'), 'val']]]
    mock_parser.parse_string.return_value = ast

    # Mock the tool executor function directly
    mock_executor_func = MagicMock(return_value=TaskResult(status="COMPLETE", content="mock result"))
    mock_handler.tool_executors = {"mock_task": mock_executor_func}

    # Mock the _execute_tool method on the handler instance used by the evaluator
    # This is needed because _invoke_target_by_name calls handler._execute_tool
    mock_handler._execute_tool.return_value = TaskResult(status="COMPLETE", content="mock result")

    result = evaluator.evaluate_string(sexp_str)

    # Assertions
    # Check the call count on the actual executor function or the _execute_tool mock
    assert mock_handler._execute_tool.call_count == 3
    mock_handler._execute_tool.assert_called_with('mock_task', {'arg': 'val'}) # Check last call args

    # The result of evaluate_string should be the TaskResult object from the last call
    assert isinstance(result, TaskResult)
    assert result.status == "COMPLETE"
    assert result.content == "mock result"

def test_eval_special_form_loop_zero_count(evaluator, mock_parser, mock_handler):
    """Test loop with count 0 executes body 0 times and returns nil ([])."""
    sexp_str = "(loop 0 (mock_task))"
    ast = [S('loop'), 0, [S('mock_task')]]
    mock_parser.parse_string.return_value = ast
    mock_executor_func = MagicMock(return_value="should not be called")
    mock_handler.tool_executors = {"mock_task": mock_executor_func}
    mock_handler._execute_tool.return_value = "should not be called" # Also mock the wrapper call

    result = evaluator.evaluate_string(sexp_str)

    # Assertions
    assert result == [] # Should return nil
    mock_handler._execute_tool.assert_not_called()
    # mock_executor_func.assert_not_called() # This mock is on tool_executors, not directly called by loop
                                         # _execute_tool is the boundary here.

def test_eval_special_form_loop_count_expression(evaluator, mock_parser, mock_handler):
    """Test loop where the count is an expression."""
    # Assuming '+' primitive is implemented or mocked to work
    sexp_str = "(loop (+ 1 1) (mock_task))"
    # AST needs '+' primitive structure
    ast = [S('loop'), [S('+'), 1, 1], [S('mock_task')]]
    mock_parser.parse_string.return_value = ast
    mock_executor_func = MagicMock(return_value=TaskResult(status="COMPLETE", content="mock result"))
    mock_handler.tool_executors = {"mock_task": mock_executor_func}
    mock_handler._execute_tool.return_value = TaskResult(status="COMPLETE", content="mock result")

    # Mock the evaluation of the count expression if '+' isn't implemented
    # Patch the _eval method within the evaluator instance
    original_eval = evaluator._eval
    def eval_side_effect(node, env):
        if node == [S('+'), 1, 1]:
            return 2 # Simulate '+' evaluation result
        # IMPORTANT: Call the original _eval for other nodes
        return original_eval(node, env)

    with patch.object(evaluator, '_eval', side_effect=eval_side_effect) as mock_eval_internal:
        result = evaluator.evaluate_string(sexp_str)

    # Assertions
    assert mock_handler._execute_tool.call_count == 2
    assert isinstance(result, TaskResult) # Check result type

def test_eval_special_form_loop_body_uses_environment(evaluator, mock_parser):
    """Test loop body executes in the correct environment and can cause side effects."""
    sexp_str = "(let ((x 0)) (loop 3 (bind x (+ x 1))))"
    # AST: ['let', [['x', 0]], ['loop', 3, ['bind', 'x', ['+', 'x', 1]]]]
    ast = [S('let'), [[S('x'), 0]], [S('loop'), 3, [S('bind'), S('x'), [S('+'), S('x'), 1]]]]
    mock_parser.parse_string.return_value = ast

    # Mock the evaluation of '+' primitive
    original_eval = evaluator._eval
    def eval_side_effect(node, env):
        if isinstance(node, list) and len(node) > 0 and isinstance(node[0], Symbol) and node[0].value() == '+':
            # Simulate simple addition: eval args and sum
            val1 = eval_side_effect(node[1], env)
            val2 = eval_side_effect(node[2], env)
            if isinstance(val1, int) and isinstance(val2, int):
                return val1 + val2
            raise SexpEvaluationError("Mock '+' only supports integers")
        # IMPORTANT: Call the original _eval for other nodes
        return original_eval(node, env)

    with patch.object(evaluator, '_eval', side_effect=eval_side_effect) as mock_eval_internal:
        result = evaluator.evaluate_string(sexp_str)

    # Assertions
    # The loop returns the result of the last (bind x (+ x 1)) which is the new value of x
    assert result == 3

def test_eval_special_form_loop_returns_last_body_result(evaluator, mock_parser):
    """Test loop returns the result of the final body evaluation."""
    sexp_str = "(loop 3 (+ 10 1))" # Body returns 11 each time
    ast = [S('loop'), 3, [S('+'), 10, 1]]
    mock_parser.parse_string.return_value = ast

    # Mock the evaluation of '+' primitive
    original_eval = evaluator._eval
    def eval_side_effect(node, env):
        if node == [S('+'), 10, 1]:
            return 11
        return original_eval(node, env)

    with patch.object(evaluator, '_eval', side_effect=eval_side_effect) as mock_eval_internal:
        result = evaluator.evaluate_string(sexp_str)

    # Assertions
    assert result == 11

def test_eval_special_form_loop_error_wrong_arg_count_few(evaluator, mock_parser):
    """Test loop fails with too few arguments."""
    sexp_str = "(loop 1)"
    ast = [S('loop'), 1]
    mock_parser.parse_string.return_value = ast

    with pytest.raises(SexpEvaluationError, match="Loop requires exactly 2 arguments"):
        evaluator.evaluate_string(sexp_str)

def test_eval_special_form_loop_error_wrong_arg_count_many(evaluator, mock_parser):
    """Test loop fails with too many arguments."""
    sexp_str = "(loop 1 (body) (extra))"
    ast = [S('loop'), 1, [S('body')], [S('extra')]]
    mock_parser.parse_string.return_value = ast

    with pytest.raises(SexpEvaluationError, match="Loop requires exactly 2 arguments"):
        evaluator.evaluate_string(sexp_str)

def test_eval_special_form_loop_error_count_expr_eval_fails(evaluator, mock_parser):
    """Test loop fails if count expression evaluation errors."""
    sexp_str = "(loop (undefined) (body))"
    ast = [S('loop'), [S('undefined')], [S('body')]]
    mock_parser.parse_string.return_value = ast

    # NameError from lookup should be wrapped in SexpEvaluationError
    # Simplified regex pattern to be more flexible
    expected_error_pattern = re.compile(
        r"Error evaluating loop count expression:.*Unbound symbol.*undefined.*"
        r"Expression:.*\[Symbol\('loop'\).*\[Symbol\('undefined'\)\].*\[Symbol\('body'\)\].*", 
        re.DOTALL
    )
    with pytest.raises(SexpEvaluationError, match=expected_error_pattern):
        evaluator.evaluate_string(sexp_str)

def test_eval_special_form_loop_error_count_not_integer(evaluator, mock_parser):
    """Test loop fails if count evaluates to non-integer."""
    sexp_str_str = "(loop \"two\" (body))"
    ast_str = [S('loop'), "two", [S('body')]]
    mock_parser.parse_string.return_value = ast_str
    expected_error_pattern_str = re.compile(
        r"Loop count must evaluate to an integer.*"
        r"Expression:.*\[Symbol\('loop'\).*'two'.*\[Symbol\('body'\)\].*",
        re.DOTALL
    )
    with pytest.raises(SexpEvaluationError, match=expected_error_pattern_str):
        evaluator.evaluate_string(sexp_str_str)

    sexp_str_list = "(loop (list 1) (body))"
    ast_list = [S('loop'), [S('list'), 1], [S('body')]]
    mock_parser.parse_string.return_value = ast_list
    # Need to mock 'list' primitive evaluation
    original_eval = evaluator._eval
    def eval_side_effect(node, env):
        if isinstance(node, list) and len(node) > 0 and isinstance(node[0], Symbol) and node[0].value() == 'list':
            return [eval_side_effect(arg, env) for arg in node[1:]] # Simulate list primitive result
        return original_eval(node, env)

    expected_error_pattern_list = re.compile(
        r"Loop count must evaluate to an integer.*"
        r"Expression:.*loop.*list.*body.*",
        re.DOTALL
    )
    with patch.object(evaluator, '_eval', side_effect=eval_side_effect):
        with pytest.raises(SexpEvaluationError, match=expected_error_pattern_list):
            evaluator.evaluate_string(sexp_str_list)

def test_eval_special_form_loop_error_count_negative(evaluator, mock_parser):
    """Test loop fails if count evaluates to negative integer."""
    sexp_str = "(loop -2 (body))"
    ast = [S('loop'), -2, [S('body')]]
    mock_parser.parse_string.return_value = ast
    expected_error_pattern = re.compile(
        r"Loop count must be non-negative.*"
        r"Expression:.*\[Symbol\('loop'\).*-2.*\[Symbol\('body'\)\].*",
        re.DOTALL
    )
    with pytest.raises(SexpEvaluationError, match=expected_error_pattern):
        evaluator.evaluate_string(sexp_str)

def test_eval_special_form_loop_error_body_eval_fails(evaluator, mock_parser, mock_handler):
    """Test loop fails if body evaluation errors during iteration."""
    sexp_str = "(loop 3 (progn (mock_ok) (fail_sometimes)))"
    # AST: ['loop', 3, ['progn', ['mock_ok'], ['fail_sometimes']]]
    ast = [S('loop'), 3, [S('progn'), [S('mock_ok')], [S('fail_sometimes')]]] # Original expression for error
    mock_parser.parse_string.return_value = ast

    # Mock 'mock_ok' to succeed
    mock_ok_executor = MagicMock(return_value=TaskResult(status="COMPLETE", content="OK"))
    mock_fail_executor = MagicMock() # Will configure side effect later
    
    # Ensure tool_executors has the functions, not the MagicMock instances directly if that's the pattern
    mock_handler.tool_executors = {
        "mock_ok": mock_ok_executor, # This should be the callable
        "fail_sometimes": mock_fail_executor # This should be the callable
    }
    # Mock the _execute_tool wrapper to call these executors
    def execute_tool_side_effect(tool_name, params):
        if tool_name == "mock_ok":
            return mock_ok_executor(params)
        if tool_name == "fail_sometimes":
            return mock_fail_executor(params)
        raise ValueError(f"Unexpected tool: {tool_name}")
    mock_handler._execute_tool.side_effect = execute_tool_side_effect


    # Mock 'fail_sometimes' executor to fail on the second call using side_effect
    body_expr_for_error_str = str([S('progn'), [S('mock_ok')], [S('fail_sometimes')]])
    fail_error = SexpEvaluationError(
        "Intentional body failure from test",
        expression=body_expr_for_error_str, # This should be the expression that failed
        error_details="Test-induced failure in body"
    )
    call_count_fail_sometimes = 0
    def fail_side_effect_func(*args, **kwargs): # Changed name to avoid conflict
        nonlocal call_count_fail_sometimes
        call_count_fail_sometimes += 1
        if call_count_fail_sometimes == 2: # Fail on the second call to fail_sometimes
            raise fail_error
        return TaskResult(status="COMPLETE", content="OK from fail_sometimes") 

    mock_fail_executor.side_effect = fail_side_effect_func

    expected_error_pattern = re.compile(
        # Line 1 of message (start of outer error's message, which includes start of e_body's message)
        r"Error during loop iteration 2/3: Intentional body failure from test"
        # Line 2 of message (e_body.expression part)
        r"\s*Expression: '\[Symbol\('progn'\), \[Symbol\('mock_ok'\)\], \[Symbol\('fail_sometimes'\)\]\]'"
        # Line 3 of message (e_body.error_details part)
        r"\s*Details: Test-induced failure in body"
        # Line 4: The "Expression: '...'" part from the SexpEvaluationError in _eval_loop_form itself
        r"\s*Expression: '\[Symbol\('loop'\), 3, \[Symbol\('progn'\), \[Symbol\('mock_ok'\)\], \[Symbol\('fail_sometimes'\)\]\]\]'"
        # Line 5: The "Details: ..." part from the SexpEvaluationError in _eval_loop_form itself
        r"\s*Details: Failed on body_expr='\[Symbol\('progn'\), \[Symbol\('mock_ok'\)\], \[Symbol\('fail_sometimes'\)\]\]'\. Original detail: Test-induced failure in body",
        re.DOTALL
    )
    with pytest.raises(SexpEvaluationError, match=expected_error_pattern):
        evaluator.evaluate_string(sexp_str)

    # Verify mock_ok was called twice (once in iteration 1 and once in iteration 2 before failure)
    assert mock_ok_executor.call_count == 2
    # Verify fail_sometimes was called twice (failed on the second)
    assert mock_fail_executor.call_count == 2


# --- New Unit Tests for Refactored Internal Methods ---

class TestSexpEvaluatorInternals:

    def test_eval_list_form_dispatches_special_form(self, evaluator, mocker):
        """Test _eval_list_form correctly dispatches to a special form handler."""
        env = SexpEnvironment()
        expr_list = [Symbol("if"), Symbol("true"), 1, 0] # AST for (if true 1 0)
        original_expr_str_expected = str(expr_list) 
        arg_exprs_for_handler = expr_list[1:] # [Symbol("true"), 1, 0]

        # Create a new mock for the handler function itself
        mock_if_handler_function = mocker.MagicMock(return_value="if_result")
        
        # Temporarily replace the entry in the evaluator's dispatch table
        original_handler = evaluator.SPECIAL_FORM_HANDLERS.get('if')
        evaluator.SPECIAL_FORM_HANDLERS['if'] = mock_if_handler_function
        
        try:
            # Call _eval_list_form directly for this internal test
            result = evaluator._eval_list_form(expr_list, env) 
        
            assert result == "if_result"
            # Assert that the new mock function (placed in the dispatch table) was called
            mock_if_handler_function.assert_called_once_with(
                arg_exprs_for_handler, env, original_expr_str_expected
            )
        finally:
            # Restore original handler if it existed, otherwise remove the mock
            if original_handler:
                evaluator.SPECIAL_FORM_HANDLERS['if'] = original_handler
            elif 'if' in evaluator.SPECIAL_FORM_HANDLERS: # Check if key exists before del
                del evaluator.SPECIAL_FORM_HANDLERS['if']


    def test_eval_list_form_evaluates_operator_and_applies(self, evaluator, mocker):
        """Test _eval_list_form evaluates operator then calls _apply_operator for non-special forms."""
        env = SexpEnvironment()
        op_expr_node = Symbol("my_func_sym") # Operator is a symbol that needs evaluation
        arg_expr_nodes = [10, Symbol("var_a")]
        expr_list = [op_expr_node] + arg_expr_nodes # (my_func_sym 10 var_a)
        original_expr_str = str(expr_list)

        env.define("var_a", 20) # For evaluating one of the args later

        # Mock _eval:
        # - op_expr_node ("my_func_sym") should evaluate to a resolved operator (e.g., a string name or a Closure)
        # - Arguments (10, Symbol("var_a")) will be evaluated by _apply_operator or its delegates
        resolved_operator_mock = "resolved_func_name_or_closure"
        mock_internal_eval = mocker.patch.object(evaluator, '_eval', return_value=resolved_operator_mock)
        
        # Mock _apply_operator, which should be called after op_expr_node is evaluated
        mock_apply_op = mocker.patch.object(evaluator, '_apply_operator', return_value="apply_result")

        result = evaluator._eval_list_form(expr_list, env)
        assert result == "apply_result"
        
        # _eval should be called once to resolve the operator expression
        mock_internal_eval.assert_called_once_with(op_expr_node, env)
        
        # _apply_operator should be called with the resolved operator and *unevaluated* arg expressions
        mock_apply_op.assert_called_once_with(
            resolved_operator_mock, # The result of _eval(op_expr_node, env)
            arg_expr_nodes,         # The list of *unevaluated* argument expressions
            env,                    # The calling environment
            original_expr_str       # The string representation of the original call
        )

    def test_apply_operator_dispatches_primitive(self, evaluator, mocker):
        env = SexpEnvironment()
        original_call_expr_str = "(list 1 2)"
        arg_expr_nodes = [1, 2] # Unevaluated argument expressions for the primitive

        # Create a new mock for the applier function
        mock_list_applier_function = mocker.MagicMock(return_value="list_applied")
        
        # Temporarily replace the entry in the evaluator's dispatch table
        original_applier = evaluator.PRIMITIVE_APPLIERS.get('list')
        evaluator.PRIMITIVE_APPLIERS['list'] = mock_list_applier_function
        
        try:
            result = evaluator._apply_operator("list", arg_expr_nodes, env, original_call_expr_str)
            assert result == "list_applied"
            # Primitive applier receives unevaluated arg expressions, current env, and original call string
            mock_list_applier_function.assert_called_once_with(arg_expr_nodes, env, original_call_expr_str)
        finally:
            if original_applier:
                evaluator.PRIMITIVE_APPLIERS['list'] = original_applier
            elif 'list' in evaluator.PRIMITIVE_APPLIERS: # Check if key exists
                del evaluator.PRIMITIVE_APPLIERS['list']


    def test_apply_operator_dispatches_task(self, evaluator, mock_task_system, mocker):
        env = SexpEnvironment()
        task_name = "my_atomic_task"
        original_call_expr_str = f"({task_name} (p 1))"
        arg_expr_nodes = [[Symbol("p"), 1]] # Unevaluated argument expressions for the task

        template_def_mock = {"name": task_name, "type": "atomic"}
        mock_task_system.find_template.return_value = template_def_mock
        
        mock_invoke_task = mocker.patch.object(evaluator, '_invoke_task_system', return_value=TaskResult(status="COMPLETE", content="task_done"))

        result = evaluator._apply_operator(task_name, arg_expr_nodes, env, original_call_expr_str)

        assert result.content == "task_done"
        mock_task_system.find_template.assert_called_once_with(task_name)
        # Invoker receives task_name, template_def, unevaluated arg_expr_nodes, env, and original_call_expr_str
        mock_invoke_task.assert_called_once_with(
            task_name, 
            template_def_mock, 
            arg_expr_nodes, 
            env, 
            original_call_expr_str
        )

    def test_apply_operator_dispatches_tool(self, evaluator, mock_handler, mocker):
        env = SexpEnvironment()
        tool_name = "my_direct_tool"
        original_call_expr_str = f"({tool_name} (arg 'foo'))"
        arg_expr_nodes = [[Symbol("arg"), Symbol("'foo")]] # Unevaluated argument expressions

        mock_handler.tool_executors = {tool_name: MagicMock()} # Tool must exist
        mock_invoke_tool = mocker.patch.object(evaluator, '_invoke_handler_tool', return_value=TaskResult(status="COMPLETE", content="tool_done"))

        result = evaluator._apply_operator(tool_name, arg_expr_nodes, env, original_call_expr_str)
        
        assert result.content == "tool_done"
        # Invoker receives tool_name, unevaluated_arg_expr_nodes, env, and original_call_expr_str
        mock_invoke_tool.assert_called_once_with(tool_name, arg_expr_nodes, env, original_call_expr_str)

    def test_apply_operator_calls_python_callable(self, evaluator, mocker):
        env = SexpEnvironment()
        original_call_expr_str = "(py_func 10 (add x 5))"
        # Unevaluated argument expressions
        arg_expr_nodes = [10, [Symbol("add"), Symbol("x"), 5]] 
        
        # Mock _eval for argument evaluation phase within _apply_operator for callables
        def eval_side_effect_for_callable_args(node, e_env):
            if node == 10: return 10
            if node == [Symbol("add"), Symbol("x"), 5]: return 7 # Simulate (add x 5) -> 7
            raise ValueError(f"Unexpected node for _eval mock in callable args: {node}")
        
        mocker.patch.object(evaluator, '_eval', side_effect=eval_side_effect_for_callable_args)
        
        mock_callable_obj = MagicMock(return_value="callable_result")
        
        result = evaluator._apply_operator(mock_callable_obj, arg_expr_nodes, env, original_call_expr_str)

        assert result == "callable_result"
        # Assert callable was called with *evaluated* args
        mock_callable_obj.assert_called_once_with(10, 7) # (10, result of _eval for (add x 5))

    def test_apply_operator_error_unrecognized_name(self, evaluator):
        with pytest.raises(SexpEvaluationError, match="Operator 'unknown_op' is not a callable primitive, task, or tool."):
            evaluator._apply_operator("unknown_op", [], SexpEnvironment(), "(unknown_op)")

    def test_apply_operator_error_non_callable(self, evaluator):
        with pytest.raises(SexpEvaluationError, match="Cannot apply non-callable/non-closure operator: 123"):
            evaluator._apply_operator(123, [], SexpEnvironment(), "(123)") 

    # --- Tests for Invocation Helpers (_invoke_task_system, _invoke_handler_tool) ---
    # These tests verify that the invocation helpers correctly parse and evaluate arguments.

    @pytest.mark.parametrize("helper_method_name, underlying_system_mock_name, target_name, template_def_if_task", [
        ("_invoke_task_system", "task_system", "my_task", {"name": "my_task", "type": "atomic"}), # Pass actual system attribute name
        ("_invoke_handler_tool", "handler", "my_tool", None)
    ])
    def test_invocation_helper_full_args_parsing_and_evaluation(
        self, evaluator, mocker, helper_method_name, underlying_system_mock_name, target_name, template_def_if_task
    ):
        """Test invocation helpers parse keys and evaluate value expressions for all arg types."""
        env = SexpEnvironment()
        original_expr_str = f"({target_name} (p1 v1_expr) (files files_expr) (context context_expr))"
        
        # Unevaluated argument expressions (key-value_expr pairs)
        unevaluated_arg_exprs_for_helper = [
            [Symbol("p1"), Symbol("v1_expr_node")],
            [Symbol("files"), Symbol("files_expr_node")],
            [Symbol("context"), Symbol("context_expr_node")]
        ]

        # Mock self._eval to control how value expressions are evaluated by the helper
        def eval_side_effect_for_helper_values(node, e_env):
            if node == Symbol("v1_expr_node"): return "evaluated_v1"
            if node == Symbol("files_expr_node"): return ["/f1.txt", "/f2.txt"]
            # Simulate (quote ((inherit "none") (fresh "enabled"))) -> [[S('inherit'),"none"], [S('fresh'),"enabled"]]
            if node == Symbol("context_expr_node"): return [[Symbol("inheritContext"), "none"], [Symbol("freshContext"), "enabled"]] 
            raise ValueError(f"Unexpected node for _eval mock: {node}")
        mocker.patch.object(evaluator, '_eval', side_effect=eval_side_effect_for_helper_values)

        # Get the actual system mock (e.g., evaluator.task_system or evaluator.handler)
        system_underlying_mock = getattr(evaluator, underlying_system_mock_name)

        if helper_method_name == "_invoke_task_system":
            mock_system_call = mocker.patch.object(system_underlying_mock, 'execute_atomic_template', return_value=TaskResult(status="COMPLETE", content="mock content"))
        else: # _invoke_handler_tool
            mock_system_call = mocker.patch.object(system_underlying_mock, '_execute_tool', return_value=TaskResult(status="COMPLETE", content="mock content"))
            if target_name not in evaluator.handler.tool_executors: # Ensure tool exists for handler
                 evaluator.handler.tool_executors[target_name] = MagicMock()


        helper_method_to_call = getattr(evaluator, helper_method_name)
        
        if helper_method_name == "_invoke_task_system":
            helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs_for_helper, env, original_expr_str)
        else: # _invoke_handler_tool
            helper_method_to_call(target_name, unevaluated_arg_exprs_for_helper, env, original_expr_str)

        mock_system_call.assert_called_once()
        
        if helper_method_name == "_invoke_task_system":
            request = mock_system_call.call_args[0][0]
            assert request.inputs == {"p1": "evaluated_v1"}
            assert request.file_paths == ["/f1.txt", "/f2.txt"]
            assert request.context_management == ContextManagement(inheritContext="none", freshContext="enabled")
        else: # _invoke_handler_tool
            called_tool_name, called_params = mock_system_call.call_args[0]
            assert called_tool_name == target_name
            assert called_params == {
                "p1": "evaluated_v1",
                "files": ["/f1.txt", "/f2.txt"],
                "context": {"inheritContext": "none", "freshContext": "enabled"} 
            }

    @pytest.mark.parametrize("helper_method_name, underlying_system_mock_name, target_name, template_def_if_task", [
        ("_invoke_task_system", "task_system", "task_only_named", {"name": "task_only_named", "type": "atomic"}),
        ("_invoke_handler_tool", "handler", "tool_only_named", None)
    ])
    def test_invocation_helper_only_named_params(
        self, evaluator, mocker, helper_method_name, underlying_system_mock_name, target_name, template_def_if_task
    ):
        env = SexpEnvironment()
        original_expr_str = f"({target_name} (p1 v1_expr))"
        unevaluated_arg_exprs_for_helper = [[Symbol("p1"), Symbol("v1_expr_node")]]

        mocker.patch.object(evaluator, '_eval', return_value="evaluated_v1") 
        
        system_underlying_mock = getattr(evaluator, underlying_system_mock_name)
        if helper_method_name == "_invoke_task_system":
            mock_system_call = mocker.patch.object(system_underlying_mock, 'execute_atomic_template', return_value=TaskResult(status="COMPLETE", content="mock content"))
        else:
            mock_system_call = mocker.patch.object(system_underlying_mock, '_execute_tool', return_value=TaskResult(status="COMPLETE", content="mock content"))
            if target_name not in evaluator.handler.tool_executors:
                 evaluator.handler.tool_executors[target_name] = MagicMock()

        helper_method_to_call = getattr(evaluator, helper_method_name)
        if helper_method_name == "_invoke_task_system":
            helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs_for_helper, env, original_expr_str)
        else:
            helper_method_to_call(target_name, unevaluated_arg_exprs_for_helper, env, original_expr_str)

        mock_system_call.assert_called_once()
        if helper_method_name == "_invoke_task_system":
            request = mock_system_call.call_args[0][0]
            assert request.inputs == {"p1": "evaluated_v1"}
            assert request.file_paths is None
            assert request.context_management is None
        else:
            called_tool_name, called_params = mock_system_call.call_args[0]
            assert called_tool_name == target_name
            assert called_params == {"p1": "evaluated_v1"}


    @pytest.mark.parametrize("helper_method_name, target_name, template_def_if_task", [
        ("_invoke_task_system", "task_bad_files", {"name": "task_bad_files", "type": "atomic"}),
        ("_invoke_handler_tool", "tool_bad_files", None) 
    ])
    def test_invocation_helper_invalid_files_type(
        self, evaluator, mocker, helper_method_name, target_name, template_def_if_task
    ):
        env = SexpEnvironment()
        original_expr_str = f"({target_name} (files \"not-a-list\"))"
        unevaluated_arg_exprs_for_helper = [[Symbol("files"), Symbol("str_node")]]
        
        mocker.patch.object(evaluator, '_eval', return_value="not-a-list") 
        
        helper_method_to_call = getattr(evaluator, helper_method_name)
        
        expected_error_match_key = "files"
        expected_error_match_target = target_name
        expected_error_match = rf"'{expected_error_match_key}' argument for (task|tool) '{expected_error_match_target}' must evaluate to a list of strings"

        with pytest.raises(SexpEvaluationError, match=expected_error_match):
            if helper_method_name == "_invoke_task_system":
                helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs_for_helper, env, original_expr_str)
            else:
                 helper_method_to_call(target_name, unevaluated_arg_exprs_for_helper, env, original_expr_str)


    @pytest.mark.parametrize("helper_method_name, target_name, template_def_if_task", [
        ("_invoke_task_system", "task_bad_context", {"name": "task_bad_context", "type": "atomic"}),
        ("_invoke_handler_tool", "tool_bad_context", None) 
    ])
    def test_invocation_helper_invalid_context_type(
        self, evaluator, mocker, helper_method_name, target_name, template_def_if_task
    ):
        env = SexpEnvironment()
        original_expr_str = f"({target_name} (context \"not-a-dict-or-list\"))"
        unevaluated_arg_exprs_for_helper = [[Symbol("context"), Symbol("str_node")]]
        
        mocker.patch.object(evaluator, '_eval', return_value="not-a-dict-or-list")
        
        helper_method_to_call = getattr(evaluator, helper_method_name)
        
        expected_error_match_key = "context"
        expected_error_match_target = target_name
        expected_error_match = rf"'{expected_error_match_key}' argument for (task|tool) '{expected_error_match_target}' must evaluate to a dictionary or a list of pairs"

        with pytest.raises(SexpEvaluationError, match=expected_error_match):
            if helper_method_name == "_invoke_task_system":
                helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs_for_helper, env, original_expr_str)
            else:
                helper_method_to_call(target_name, unevaluated_arg_exprs_for_helper, env, original_expr_str)

    @pytest.mark.parametrize("helper_method_name, target_name, template_def_if_task, invalid_arg_expr, err_match_detail", [
        ("_invoke_task_system", "t", {"name":"t","type":"atomic"}, Symbol("not-a-list"), "Expected \\(key_symbol value_expression\\)"),
        ("_invoke_handler_tool", "h", None, Symbol("not-a-list"), "Expected \\(key_symbol value_expression\\)"),
        ("_invoke_task_system", "t", {"name":"t","type":"atomic"}, [Symbol("key-only")], "Expected \\(key_symbol value_expression\\)"),
        ("_invoke_handler_tool", "h", None, [Symbol("key-only")], "Expected \\(key_symbol value_expression\\)"),
        ("_invoke_task_system", "t", {"name":"t","type":"atomic"}, [123, Symbol("value_node")], "Expected \\(key_symbol value_expression\\)"),
        ("_invoke_handler_tool", "h", None, [123, Symbol("value_node")], "Expected \\(key_symbol value_expression\\)"),
    ])
    def test_invocation_helper_invalid_arg_pair_format(
        self, evaluator, mocker, helper_method_name, target_name, template_def_if_task, invalid_arg_expr, err_match_detail
    ):
        env = SexpEnvironment()
        original_expr_str = f"({target_name} {invalid_arg_expr})" 
        unevaluated_arg_exprs_for_helper = [invalid_arg_expr]
        
        mocker.patch.object(evaluator, '_eval', return_value="dummy_eval_result")
        
        helper_method_to_call = getattr(evaluator, helper_method_name)
        
        with pytest.raises(SexpEvaluationError, match=err_match_detail):
            if helper_method_name == "_invoke_task_system":
                helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs_for_helper, env, original_expr_str)
            else:
                helper_method_to_call(target_name, unevaluated_arg_exprs_for_helper, env, original_expr_str)


# --- Tests for Lambda and Closures ---

# Import Closure class for isinstance checks if it's accessible
# If not, tests will rely on attribute checking (duck typing)
try:
    from src.sexp_evaluator.sexp_closure import Closure
    CLOSURE_CLASS_AVAILABLE = True
except ImportError:
    CLOSURE_CLASS_AVAILABLE = False
    Closure = object # Placeholder if not importable, use object to avoid NameError on isinstance

class TestSexpEvaluatorLambdaClosures:

    def test_lambda_definition_creates_closure(self, evaluator, mock_parser):
        """Test that (lambda (params) body) evaluates to a Closure object."""
        sexp_str = "(lambda (x) (+ x 1))"
        
        params_ast = [S('x')]
        body_expr_ast = [S('+'), S('x'), 1] 
        
        lambda_ast = [S('lambda'), params_ast, body_expr_ast] 
        
        mock_parser.parse_string.return_value = lambda_ast
        
        def_env = SexpEnvironment(parent=None)
        result = evaluator.evaluate_string(sexp_str, initial_env=def_env)

        assert hasattr(result, 'params_ast'), "Result missing 'params_ast'"
        assert hasattr(result, 'body_ast'), "Result missing 'body_ast'"
        assert hasattr(result, 'definition_env'), "Result missing 'definition_env'"
        
        if CLOSURE_CLASS_AVAILABLE:
            assert isinstance(result, Closure), f"Result is not a Closure object, got {type(result)}"

        assert result.params_ast == params_ast, "Closure params mismatch"
        assert result.body_ast == [body_expr_ast], "Closure body mismatch"
        assert result.definition_env is def_env, "Closure definition environment mismatch"
        mock_parser.parse_string.assert_called_once_with(sexp_str)

    def test_lambda_application_basic(self, evaluator, mock_parser):
        """Test basic application of a lambda-defined closure."""
        sexp_str = "((lambda (x) (+ x 10)) 5)"

        lambda_params_ast = [S('x')]
        lambda_body_expr_ast = [S('+'), S('x'), 10]
        lambda_expr_ast = [S('lambda'), lambda_params_ast, lambda_body_expr_ast]
        
        application_ast = [lambda_expr_ast, 5]
        mock_parser.parse_string.return_value = application_ast
        
        original_eval = evaluator._eval
        def eval_side_effect(node, env):
            if node == lambda_body_expr_ast and env.lookup('x') == 5: 
                 return 15 
            return original_eval(node, env)

        with patch.object(evaluator, '_eval', side_effect=eval_side_effect) as mock_internal_eval:
            result = evaluator.evaluate_string(sexp_str)
            assert result == 15

            assert any(call_args[0] == lambda_expr_ast for call_args, _ in mock_internal_eval.call_args_list), \
                "Lambda expression was not evaluated."

            assert any(call_args[0] == 5 for call_args, _ in mock_internal_eval.call_args_list), \
                "Argument '5' was not evaluated."

            body_eval_call_found = False
            for call_args_tuple in mock_internal_eval.call_args_list:
                node_arg, env_arg = call_args_tuple[0] 
                if node_arg == lambda_body_expr_ast:
                    try:
                        if env_arg.lookup('x') == 5: 
                            body_eval_call_found = True
                            break
                    except NameError:
                        pass 
            assert body_eval_call_found, "Closure body was not evaluated with correct parameter binding."


    def test_lambda_lexical_scope_capture(self, evaluator, mock_parser):
        """Test that closures capture their definition environment (lexical scope)."""
        sexp_str = "(let ((y 10)) ((lambda (x) (+ x y)) 5))"

        y_sym = S('y')
        x_sym = S('x')
        plus_sym = S('+')
        lambda_sym = S('lambda')
        let_sym = S('let')

        lambda_expr_ast = [lambda_sym, [x_sym], [plus_sym, x_sym, y_sym]]
        application_inner_ast = [lambda_expr_ast, 5]
        
        let_ast = [let_sym, [[y_sym, 10]], application_inner_ast]
        mock_parser.parse_string.return_value = let_ast

        original_eval = evaluator._eval
        def eval_side_effect(node, env):
            if isinstance(node, list) and len(node) == 3 and node[0] == plus_sym and node[1] == x_sym and node[2] == y_sym:
                val_x = env.lookup(x_sym.value())
                val_y = env.lookup(y_sym.value())
                if val_x == 5 and val_y == 10:
                    return 15 
            return original_eval(node, env)

        with patch.object(evaluator, '_eval', side_effect=eval_side_effect):
            result = evaluator.evaluate_string(sexp_str)
            assert result == 15

    def test_lambda_higher_order_function_create(self, evaluator, mock_parser):
        """Test creating a function that returns another function (closure)."""
        sexp_str = "(let ((adder (lambda (n) (lambda (x) (+ n x))))) ((adder 10) 5))"
        
        adder_sym, n_sym, x_sym, plus_sym, lambda_sym, let_sym = \
            S('adder'), S('n'), S('x'), S('+'), S('lambda'), S('let')

        inner_lambda_ast = [lambda_sym, [x_sym], [plus_sym, n_sym, x_sym]]
        outer_lambda_ast = [lambda_sym, [n_sym], inner_lambda_ast]
        
        adder_call_ast = [adder_sym, 10]
        full_application_ast = [adder_call_ast, 5]
        
        let_ast = [let_sym, [[adder_sym, outer_lambda_ast]], full_application_ast]
        mock_parser.parse_string.return_value = let_ast

        original_eval = evaluator._eval
        def eval_side_effect(node, env):
            if isinstance(node, list) and len(node) == 3 and node[0] == plus_sym and node[1] == n_sym and node[2] == x_sym:
                val_n = env.lookup(n_sym.value()) 
                val_x = env.lookup(x_sym.value()) 
                if val_n == 10 and val_x == 5:
                    return 15
            return original_eval(node, env)

        with patch.object(evaluator, '_eval', side_effect=eval_side_effect):
            result = evaluator.evaluate_string(sexp_str)
            assert result == 15

    def test_lambda_arity_mismatch_too_few_args(self, evaluator, mock_parser):
        """Test error when a closure is called with too few arguments."""
        sexp_str = "((lambda (a b) (+ a b)) 1)" 
        
        lambda_expr_ast = [S('lambda'), [S('a'), S('b')], [S('+'), S('a'), S('b')]]
        application_ast = [lambda_expr_ast, 1]
        mock_parser.parse_string.return_value = application_ast
        
        with pytest.raises(SexpEvaluationError, match="Arity mismatch: Closure expects 2 arguments, got 1"):
            evaluator.evaluate_string(sexp_str)

    def test_lambda_arity_mismatch_too_many_args(self, evaluator, mock_parser):
        """Test error when a closure is called with too many arguments."""
        sexp_str = "((lambda (a) a) 1 2)" 
        
        lambda_expr_ast = [S('lambda'), [S('a')], S('a')]
        application_ast = [lambda_expr_ast, 1, 2]
        mock_parser.parse_string.return_value = application_ast
        
        with pytest.raises(SexpEvaluationError, match="Arity mismatch: Closure expects 1 arguments, got 2"):
            evaluator.evaluate_string(sexp_str)

    def test_lambda_definition_invalid_param_list_not_list(self, evaluator, mock_parser):
        """Test error if lambda parameter definition is not a list."""
        sexp_str = "(lambda x x)" 
        mock_parser.parse_string.return_value = [S('lambda'), S('x'), S('x')]
        with pytest.raises(SexpEvaluationError, match="Lambda parameter definition must be a list of symbols."):
            evaluator.evaluate_string(sexp_str)

    def test_lambda_definition_invalid_param_not_symbol(self, evaluator, mock_parser):
        """Test error if a lambda parameter is not a symbol."""
        sexp_str = "(lambda (1) 1)" 
        mock_parser.parse_string.return_value = [S('lambda'), [1], 1]
        with pytest.raises(SexpEvaluationError, match="Lambda parameters must be symbols, got <class 'int'>: 1"):
            evaluator.evaluate_string(sexp_str)
            
    def test_lambda_definition_no_body(self, evaluator, mock_parser):
        """Test error if lambda has no body expressions."""
        sexp_str = "(lambda (x))"
        mock_parser.parse_string.return_value = [S('lambda'), [S('x')]]
        with pytest.raises(SexpEvaluationError, match="'lambda' requires a parameter list and at least one body expression."):
            evaluator.evaluate_string(sexp_str)

    def test_lambda_recursive_closure(self, evaluator, mock_parser):
        """Test a recursive closure (e.g., factorial) using standard let and lambda."""
        sexp_str = "(let ((fact-body (lambda (self n) (if (= n 0) 1 (* n (self self (- n 1))))))) (fact-body fact-body 3))"
        
        fact_body_s, self_s, n_s, if_s, eq_s, mul_s, sub_s = \
            S('fact-body'), S('self'), S('n'), S('if'), S('='), S('*'), S('-')
        lambda_s, let_s = S('lambda'), S('let')

        recursive_call_ast = [self_s, self_s, [sub_s, n_s, 1]] 
        if_body_ast = [if_s, [eq_s, n_s, 0], 1, [mul_s, n_s, recursive_call_ast]]

        fact_lambda_ast = [lambda_s, [self_s, n_s], if_body_ast] 

        let_binding_ast = [[fact_body_s, fact_lambda_ast]]
        final_call_ast = [fact_body_s, fact_body_s, 3] 
        full_ast = [let_s, let_binding_ast, final_call_ast]
        
        mock_parser.parse_string.return_value = full_ast

        original_eval = evaluator._eval
        memo_eval_calls = [] 

        def eval_side_effect(node, env):
            memo_eval_calls.append((node, id(env))) 

            if isinstance(node, list) and len(node) > 0:
                op_sym_node = node[0]
                if isinstance(op_sym_node, Symbol):
                    op_name = op_sym_node.value()

                    if op_name == '=': 
                        val_n_node = node[1]
                        val_0_node = node[2]
                        # Evaluate arguments for '=' using the side_effect itself to ensure symbols are resolved
                        val_n = eval_side_effect(val_n_node, env)
                        val_0 = eval_side_effect(val_0_node, env)
                        return val_n == val_0
                    
                    if op_name == '-': 
                        val_n_node = node[1]
                        val_1_node = node[2]
                        val_n = eval_side_effect(val_n_node, env)
                        val_1 = eval_side_effect(val_1_node, env)
                        return val_n - val_1
                    
                    if op_name == '*': 
                        val_n_node = node[1]
                        # node[2] is the recursive call list: (self self (- n 1))
                        # This list itself needs to be evaluated by the main SexpEvaluator logic
                        val_n = eval_side_effect(val_n_node, env) 
                        val_rec_result = original_eval(node[2], env) # Use original_eval for the call
                        return val_n * val_rec_result
            
            return original_eval(node, env)

        with patch.object(evaluator, '_eval', side_effect=eval_side_effect):
            result = evaluator.evaluate_string(sexp_str)
            assert result == 6 

    def test_closure_retains_definition_env_even_if_outer_var_is_rebound(self, evaluator, mock_parser):
        """Test that a closure uses its definition-time environment, not the call-time one
           if an outer variable it captured is later rebound in the scope from which the
           closure was *returned* but before the closure is *called*.
        """
        sexp_str = "(let ((outer-val 10)) (let ((my-closure (lambda () outer-val))) (bind outer-val 20) (my-closure)))"

        let_s, lambda_s, bind_s = S('let'), S('lambda'), S('bind')
        outer_val_s, my_closure_s = S('outer-val'), S('my-closure')

        closure_def_ast = [lambda_s, [], outer_val_s]
        closure_call_ast = [my_closure_s]
        rebind_ast = [bind_s, outer_val_s, 20]

        # Corrected inner let structure: (let (bindings) body1 body2 ...)
        inner_let_bindings = [[my_closure_s, closure_def_ast]]
        # progn is implicit for let body, so rebind_ast and closure_call_ast are sequential body forms
        inner_let_ast = [let_s, inner_let_bindings, rebind_ast, closure_call_ast] 

        outer_let_bindings = [[outer_val_s, 10]]
        # Outer let body is just the inner_let_ast
        full_ast = [let_s, outer_let_bindings, inner_let_ast] 
        
        mock_parser.parse_string.return_value = full_ast
        
        result = evaluator.evaluate_string(sexp_str)
        assert result == 10

    def test_closure_returned_from_function_retains_lexical_scope(self, evaluator, mock_parser):
        """
        Test that closures created by a 'maker' function at different times
        with different captured values maintain their distinct lexical environments.
        """
        sexp_str = """
        (let ((maker (lambda (captured_val) 
                       (lambda () captured_val)))) 
          (let ((closure_A (maker 100))
                (closure_B (maker 200)))
            (list (closure_A) (closure_B))))
        """
        
        let_s, lambda_s, list_s = S('let'), S('lambda'), S('list')
        maker_s, captured_val_s = S('maker'), S('captured_val')
        closure_A_s, closure_B_s = S('closure_A'), S('closure_B')

        returned_closure_body_ast = captured_val_s
        returned_closure_ast = [lambda_s, [], returned_closure_body_ast]

        maker_lambda_ast = [lambda_s, [captured_val_s], returned_closure_ast]

        maker_call_A_ast = [maker_s, 100]
        maker_call_B_ast = [maker_s, 200]

        closure_A_call_ast = [closure_A_s]
        closure_B_call_ast = [closure_B_s]
        
        list_call_ast = [list_s, closure_A_call_ast, closure_B_call_ast]

        inner_let_bindings = [[closure_A_s, maker_call_A_ast], [closure_B_s, maker_call_B_ast]]
        inner_let_ast = [let_s, inner_let_bindings, list_call_ast]
        
        outer_let_bindings = [[maker_s, maker_lambda_ast]]
        full_ast = [let_s, outer_let_bindings, inner_let_ast]

        mock_parser.parse_string.return_value = full_ast
        
        result = evaluator.evaluate_string(sexp_str)
        assert result == [100, 200]

# --- Tests for eq? ---
def test_primitive_eq_numbers_equal(evaluator, mock_parser):
    sexp_str = "(eq? 1 1)"
    ast = [Symbol('eq?'), 1, 1]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True
    
    sexp_str = "(eq? 1.0 1.0)"
    ast = [Symbol('eq?'), 1.0, 1.0]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True

    sexp_str = "(eq? 1 1.0)"
    ast = [Symbol('eq?'), 1, 1.0]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True

    sexp_str = "(eq? 0 0.0)"
    ast = [Symbol('eq?'), 0, 0.0]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True

def test_primitive_eq_numbers_unequal(evaluator, mock_parser):
    sexp_str = "(eq? 1 2)"
    ast = [Symbol('eq?'), 1, 2]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is False

    sexp_str = "(eq? 1.0 1.1)"
    ast = [Symbol('eq?'), 1.0, 1.1]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is False

def test_primitive_eq_strings_equal(evaluator, mock_parser):
    sexp_str = '(eq? "hello" "hello")'
    ast = [Symbol('eq?'), "hello", "hello"]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True

    sexp_str = '(eq? "" "")'
    ast = [Symbol('eq?'), "", ""]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True

def test_primitive_eq_strings_unequal(evaluator, mock_parser):
    sexp_str = '(eq? "hello" "world")'
    ast = [Symbol('eq?'), "hello", "world"]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is False

    sexp_str = '(eq? "Hello" "hello")'
    ast = [Symbol('eq?'), "Hello", "hello"]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is False 

def test_primitive_eq_booleans_equal(evaluator, mock_parser):
    sexp_str = "(eq? true true)"
    ast = [Symbol('eq?'), True, True]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True

    sexp_str = "(eq? false false)"
    ast = [Symbol('eq?'), False, False]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True

def test_primitive_eq_booleans_unequal(evaluator, mock_parser):
    sexp_str = "(eq? true false)"
    ast = [Symbol('eq?'), True, False]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is False

def test_primitive_eq_symbols_equal(evaluator, mock_parser):
    sexp_str = "(eq? (quote foo) (quote foo))"
    ast = [Symbol('eq?'), [Symbol('quote'), Symbol('foo')], [Symbol('quote'), Symbol('foo')]]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True
    
    env = SexpEnvironment(bindings={'a': Symbol('id1'), 'b': Symbol('id1')})
    sexp_str_env = "(eq? a b)"
    ast_env = [Symbol('eq?'), Symbol('a'), Symbol('b')]
    mock_parser.parse_string.return_value = ast_env
    assert evaluator.evaluate_string(sexp_str_env, env) is True

def test_primitive_eq_symbols_unequal(evaluator, mock_parser):
    sexp_str = "(eq? (quote foo) (quote bar))"
    ast = [Symbol('eq?'), [Symbol('quote'), Symbol('foo')], [Symbol('quote'), Symbol('bar')]]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is False

    env = SexpEnvironment(bindings={'a': Symbol('id1'), 'b': Symbol('id2')})
    sexp_str_env = "(eq? a b)"
    ast_env = [Symbol('eq?'), Symbol('a'), Symbol('b')]
    mock_parser.parse_string.return_value = ast_env
    assert evaluator.evaluate_string(sexp_str_env, env) is False

def test_primitive_eq_none_equal(evaluator, mock_parser):
    sexp_str = "(eq? nil nil)"
    ast = [Symbol('eq?'), None, None] # Assuming nil parses to None
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True 
    
    env_with_none = SexpEnvironment(bindings={"my_none": None})
    sexp_str_env = "(eq? my_none nil)"
    ast_env = [Symbol('eq?'), Symbol('my_none'), None]
    mock_parser.parse_string.return_value = ast_env
    assert evaluator.evaluate_string(sexp_str_env, env_with_none) is True

def test_primitive_eq_lists_equal_structurally(evaluator, mock_parser):
    # Test 1: Simple lists of literals
    sexp_str_simple = "(eq? (list 1 2) (list 1 2))"
    ast_simple = [Symbol('eq?'), [Symbol('list'), 1, 2], [Symbol('list'), 1, 2]]
    mock_parser.parse_string.return_value = ast_simple # Set mock for this call
    assert evaluator.evaluate_string(sexp_str_simple) is True
    
    # Test 2: Nested lists with quoted symbols
    # S-expression: (eq? (list (list (quote a)) (quote b)) (list (list (quote a)) (quote b)))
    sexp_str_complex = "(eq? (list (list (quote a)) (quote b)) (list (list (quote a)) (quote b)))"
    # AST for the above S-expression
    ast_complex = [
        Symbol('eq?'),
        [Symbol('list'), [Symbol('list'), [Symbol('quote'), Symbol('a')]], [Symbol('quote'), Symbol('b')]],
        [Symbol('list'), [Symbol('list'), [Symbol('quote'), Symbol('a')]], [Symbol('quote'), Symbol('b')]]
    ]
    mock_parser.parse_string.return_value = ast_complex # Set mock for this call
    assert evaluator.evaluate_string(sexp_str_complex) is True
    
    # Test 3: Empty lists
    sexp_str_empty1 = "(eq? (list) (list))"
    ast_empty1 = [Symbol('eq?'), [Symbol('list')], [Symbol('list')]]
    mock_parser.parse_string.return_value = ast_empty1 # Set mock for this call
    assert evaluator.evaluate_string(sexp_str_empty1) is True
    
    # Test 4: Quoted empty lists '()
    # '() is parsed by sexpdata as an empty list []. (quote ()) is parsed as [Symbol('quote'), []]
    # The S-expression (eq? '() '()) is parsed as [Symbol('eq?'), [], []] by sexpdata if nil=None is not set.
    # If nil='nil' (current SexpParser default), then '() still parses to [].
    # If the SexpParser is configured to treat nil as None, then '() would still be [].
    # The (quote form) is the explicit way.
    sexp_str_empty2 = "(eq? (quote ()) (quote ()))"
    ast_empty2 = [Symbol('eq?'), [Symbol('quote'), []], [Symbol('quote'), []]]
    mock_parser.parse_string.return_value = ast_empty2 # Set mock for this call
    assert evaluator.evaluate_string(sexp_str_empty2) is True

def test_primitive_eq_lists_unequal_structurally(evaluator, mock_parser):
    sexp_str = "(eq? (list 1 2) (list 1 3))"
    ast = [Symbol('eq?'), [Symbol('list'), 1, 2], [Symbol('list'), 1, 3]]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is False

    sexp_str = "(eq? (list 1 2) (list 1))"
    ast = [Symbol('eq?'), [Symbol('list'), 1, 2], [Symbol('list'), 1]]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is False

    sexp_str = "(eq? (list) (list 1))"
    ast = [Symbol('eq?'), [Symbol('list')], [Symbol('list'), 1]]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is False

def test_primitive_eq_different_types_unequal(evaluator, mock_parser):
    sexp_str = '(eq? "1" 1)'
    ast = [Symbol('eq?'), "1", 1]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is False

    sexp_str = "(eq? true (quote true))"
    ast = [Symbol('eq?'), True, [Symbol('quote'), Symbol('true')]]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is False 

    sexp_str = "(eq? nil false)"
    ast = [Symbol('eq?'), None, False]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is False

    sexp_str = "(eq? (list 1) 1)"
    ast = [Symbol('eq?'), [Symbol('list'), 1], 1]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is False

def test_primitive_eq_arity_errors(evaluator, mock_parser):
    sexp_str = "(eq? 1)"
    ast = [Symbol('eq?'), 1]
    mock_parser.parse_string.return_value = ast
    with pytest.raises(SexpEvaluationError, match="'eq\\?' requires exactly two arguments"):
        evaluator.evaluate_string(sexp_str)

    sexp_str = "(eq? 1 2 3)"
    ast = [Symbol('eq?'), 1, 2, 3]
    mock_parser.parse_string.return_value = ast
    with pytest.raises(SexpEvaluationError, match="'eq\\?' requires exactly two arguments"):
        evaluator.evaluate_string(sexp_str)

    sexp_str = "(eq?)"
    ast = [Symbol('eq?')]
    mock_parser.parse_string.return_value = ast
    with pytest.raises(SexpEvaluationError, match="'eq\\?' requires exactly two arguments"):
        evaluator.evaluate_string(sexp_str)

# --- Tests for null? (and nil?) ---
def test_primitive_null_is_true_for_none(evaluator, mock_parser):
    sexp_str = "(null? nil)"
    ast = [Symbol('null?'), None]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True 
    
    env_with_none = SexpEnvironment(bindings={"my_val": None})
    sexp_str_env = "(null? my_val)"
    ast_env = [Symbol('null?'), Symbol('my_val')]
    mock_parser.parse_string.return_value = ast_env
    assert evaluator.evaluate_string(sexp_str_env, env_with_none) is True

    sexp_str_alias = "(nil? nil)"
    ast_alias = [Symbol('nil?'), None]
    mock_parser.parse_string.return_value = ast_alias
    assert evaluator.evaluate_string(sexp_str_alias) is True 

def test_primitive_null_is_true_for_empty_list(evaluator, mock_parser):
    sexp_str = "(null? (list))"
    ast = [Symbol('null?'), [Symbol('list')]]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True

    sexp_str = "(null? '())"
    ast = [Symbol('null?'), [Symbol('quote'), []]]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True 

    sexp_str_alias = "(nil? (list))"
    ast_alias = [Symbol('nil?'), [Symbol('list')]]
    mock_parser.parse_string.return_value = ast_alias
    assert evaluator.evaluate_string(sexp_str_alias) is True 

def test_primitive_null_is_false_for_non_nulls(evaluator, mock_parser):
    test_cases = [
        ("(null? 0)", [Symbol('null?'), 0]),
        ("(null? 1)", [Symbol('null?'), 1]),
        ('(null? "")', [Symbol('null?'), ""]),
        ('(null? "text")', [Symbol('null?'), "text"]),
        ("(null? true)", [Symbol('null?'), True]),
        ("(null? false)", [Symbol('null?'), False]),
        ("(null? (quote a_symbol))", [Symbol('null?'), [Symbol('quote'), Symbol('a_symbol')]]),
        ("(null? (list 1))", [Symbol('null?'), [Symbol('list'), 1]]),
    ]
    for sexp_str, ast in test_cases:
        mock_parser.parse_string.return_value = ast
        assert evaluator.evaluate_string(sexp_str) is False

def test_primitive_null_arity_errors(evaluator, mock_parser):
    sexp_str = "(null?)"
    ast = [Symbol('null?')]
    mock_parser.parse_string.return_value = ast
    with pytest.raises(SexpEvaluationError, match="'null\\?' requires exactly one argument"):
        evaluator.evaluate_string(sexp_str)

    sexp_str = "(null? nil nil)"
    ast = [Symbol('null?'), None, None]
    mock_parser.parse_string.return_value = ast
    with pytest.raises(SexpEvaluationError, match="'null\\?' requires exactly one argument"):
        evaluator.evaluate_string(sexp_str)

def test_primitive_null_with_get_field_missing(evaluator, mock_parser):
    sexp_str = "(null? (get-field (list) \"non_existent_key\"))"
    ast = [Symbol('null?'), [Symbol('get-field'), [Symbol('list')], "non_existent_key"]]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) is True

# --- Tests for set! ---
def test_primitive_set_bang_updates_local_var(evaluator, mock_parser):
    env = SexpEnvironment(bindings={'x': 10})
    sexp_str = "(set! x 20)"
    ast = [Symbol('set!'), Symbol('x'), 20]
    mock_parser.parse_string.return_value = ast
    result = evaluator.evaluate_string(sexp_str, env)
    assert result == 20
    assert env.lookup('x') == 20

def test_primitive_set_bang_updates_parent_var(evaluator, mock_parser):
    parent_env = SexpEnvironment(bindings={'y': 100})
    child_env = parent_env.extend({})
    sexp_str = "(set! y 200)"
    ast = [Symbol('set!'), Symbol('y'), 200]
    mock_parser.parse_string.return_value = ast
    result = evaluator.evaluate_string(sexp_str, child_env)
    assert result == 200
    assert parent_env.lookup('y') == 200
    assert child_env.lookup('y') == 200 

def test_primitive_set_bang_updates_grandparent_var(evaluator, mock_parser):
    grandparent_env = SexpEnvironment(bindings={'z': 50})
    parent_env = grandparent_env.extend({})
    child_env = parent_env.extend({})
    sexp_str = "(set! z 500)"
    ast = [Symbol('set!'), Symbol('z'), 500]
    mock_parser.parse_string.return_value = ast
    result = evaluator.evaluate_string(sexp_str, child_env)
    assert result == 500
    assert grandparent_env.lookup('z') == 500

def test_primitive_set_bang_error_unbound_symbol(evaluator, mock_parser):
    env = SexpEnvironment()
    sexp_str = "(set! unbound_var 10)"
    ast = [Symbol('set!'), Symbol('unbound_var'), 10]
    mock_parser.parse_string.return_value = ast
    with pytest.raises(SexpEvaluationError, match="Cannot 'set!' unbound symbol: unbound_var"):
        evaluator.evaluate_string(sexp_str, env)

def test_primitive_set_bang_arity_errors(evaluator, mock_parser):
    sexp_str = "(set! x)"
    ast = [Symbol('set!'), Symbol('x')]
    mock_parser.parse_string.return_value = ast
    with pytest.raises(SexpEvaluationError, match="'set!' requires exactly two arguments"):
        evaluator.evaluate_string(sexp_str)

    sexp_str = "(set! x 1 2)"
    ast = [Symbol('set!'), Symbol('x'), 1, 2]
    mock_parser.parse_string.return_value = ast
    with pytest.raises(SexpEvaluationError, match="'set!' requires exactly two arguments"):
        evaluator.evaluate_string(sexp_str)

def test_primitive_set_bang_error_target_not_symbol(evaluator, mock_parser):
    sexp_str = '(set! "x" 10)'
    ast = [Symbol('set!'), "x", 10]
    mock_parser.parse_string.return_value = ast
    with pytest.raises(SexpEvaluationError, match="'set!' first argument must be a symbol"):
        evaluator.evaluate_string(sexp_str)

    sexp_str = "(set! 10 10)"
    ast = [Symbol('set!'), 10, 10]
    mock_parser.parse_string.return_value = ast
    with pytest.raises(SexpEvaluationError, match="'set!' first argument must be a symbol"):
        evaluator.evaluate_string(sexp_str)

# --- Tests for + ---
def test_primitive_add_various_cases(evaluator, mock_parser):
    test_cases = [
        ("(+ 1 2)", [Symbol('+'), 1, 2], 3),
        ("(+ 1.0 2.5)", [Symbol('+'), 1.0, 2.5], 3.5),
        ("(+ 1 2.5)", [Symbol('+'), 1, 2.5], 3.5),
        ("(+ 10 20 30 40)", [Symbol('+'), 10, 20, 30, 40], 100),
        ("(+ 5)", [Symbol('+'), 5], 5),
        ("(+)", [Symbol('+')], 0),
        ("(+ -1 1)", [Symbol('+'), -1, 1], 0),
    ]
    for sexp_str, ast, expected in test_cases:
        mock_parser.parse_string.return_value = ast
        assert evaluator.evaluate_string(sexp_str) == expected

def test_primitive_add_error_non_numeric(evaluator, mock_parser):
    sexp_str1 = '(+ 1 "two")'
    ast1 = [Symbol('+'), 1, "two"]
    mock_parser.parse_string.return_value = ast1 # Set mock for the first call
    with pytest.raises(SexpEvaluationError, match="must be a number"):
        evaluator.evaluate_string(sexp_str1)
    
    # Boolean values are valid for arithmetic in Python (True is 1, False is 0)
    sexp_str2 = "(+ true 1)"
    ast2 = [Symbol('+'), True, 1] # SexpParser converts 'true' to Python True
    mock_parser.parse_string.return_value = ast2 # Set mock for the second call
    # True (1) + 1 = 2
    assert evaluator.evaluate_string(sexp_str2) == 2

# --- Tests for - ---
def test_primitive_subtract_various_cases(evaluator, mock_parser):
    test_cases = [
        ("(- 10 3)", [Symbol('-'), 10, 3], 7),
        ("(- 10.5 3.0)", [Symbol('-'), 10.5, 3.0], 7.5),
        ("(- 10 3.5)", [Symbol('-'), 10, 3.5], 6.5),
        ("(- 5)", [Symbol('-'), 5], -5),
        ("(- 0 5)", [Symbol('-'), 0, 5], -5),
        ("(- -5 -2)", [Symbol('-'), -5, -2], -3),
    ]
    for sexp_str, ast, expected in test_cases:
        mock_parser.parse_string.return_value = ast
        assert evaluator.evaluate_string(sexp_str) == expected

def test_primitive_subtract_arity_errors(evaluator, mock_parser):
    sexp_str = "(-)"
    ast = [Symbol('-')]
    mock_parser.parse_string.return_value = ast
    with pytest.raises(SexpEvaluationError, match="'-' requires one or two numeric arguments"):
        evaluator.evaluate_string(sexp_str)

    sexp_str = "(- 1 2 3)"
    ast = [Symbol('-'), 1, 2, 3]
    mock_parser.parse_string.return_value = ast
    with pytest.raises(SexpEvaluationError, match="'-' requires one or two numeric arguments"):
        evaluator.evaluate_string(sexp_str)

def test_primitive_subtract_error_non_numeric(evaluator, mock_parser):
    sexp_str1 = '(- 10 "three")'
    ast1 = [Symbol('-'), 10, "three"]
    mock_parser.parse_string.return_value = ast1 # Set mock for the first call
    with pytest.raises(SexpEvaluationError, match="must be a number"):
        evaluator.evaluate_string(sexp_str1)
    
    # Boolean values are valid for arithmetic in Python (True is 1, False is 0)
    sexp_str2 = "(- true)"
    ast2 = [Symbol('-'), True] # SexpParser converts 'true' to Python True
    mock_parser.parse_string.return_value = ast2 # Set mock for the second call
    # - True (-1)
    assert evaluator.evaluate_string(sexp_str2) == -1
    
    sexp_str3 = "(- 10 false)" 
    ast3 = [Symbol('-'), 10, False] # SexpParser converts 'false' to Python False
    mock_parser.parse_string.return_value = ast3 # Set mock for the third call
    # 10 - False (0) = 10
    assert evaluator.evaluate_string(sexp_str3) == 10

# --- Tests for string-append ---
def test_string_append_no_args(evaluator, mock_parser):
    """Test (string-append) returns an empty string."""
    sexp_str = "(string-append)"
    ast = [Symbol('string-append')]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) == ""

def test_string_append_one_arg(evaluator, mock_parser):
    """Test (string-append "hello") returns "hello"."""
    sexp_str = '(string-append "hello")'
    ast = [Symbol('string-append'), "hello"]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) == "hello"

def test_string_append_multiple_args(evaluator, mock_parser):
    """Test (string-append "hello" " " "world" "!") returns "hello world!"."""
    sexp_str = '(string-append "hello" " " "world" "!")'
    ast = [Symbol('string-append'), "hello", " ", "world", "!"]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) == "hello world!"

def test_string_append_with_empty_string_args(evaluator, mock_parser):
    """Test (string-append "a" "" "b") returns "ab"."""
    sexp_str = '(string-append "a" "" "b")'
    ast = [Symbol('string-append'), "a", "", "b"]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) == "ab"

def test_string_append_with_evaluated_args(evaluator, mock_parser):
    """Test arguments are evaluated before concatenation."""
    sexp_str = '(let ((x "foo") (y "bar")) (string-append x y))'
    let_sym = Symbol('let') if Symbol != str else 'let'
    x_sym = Symbol('x') if Symbol != str else 'x'
    y_sym = Symbol('y') if Symbol != str else 'y'
    string_append_sym = Symbol('string-append') if Symbol != str else 'string-append'
    
    ast = [let_sym, [[x_sym, "foo"], [y_sym, "bar"]], [string_append_sym, x_sym, y_sym]]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) == "foobar"

def test_string_append_error_non_string_arg(evaluator, mock_parser):
    """Test SexpEvaluationError is raised if an argument is not string, symbol, number, or nil."""
    # Test with a list, which should not be convertible
    sexp_str = '(string-append "hello" (list 1 2))'
    # AST generation for (list 1 2)
    list_call_ast = [Symbol('list'), 1, 2]
    ast = [Symbol('string-append'), "hello", list_call_ast]
    mock_parser.parse_string.return_value = ast
    
    original_eval = evaluator._eval
    def eval_side_effect_for_list(node, env):
        if node == list_call_ast:
            return [1, 2] 
        return original_eval(node, env)

    with patch.object(evaluator, '_eval', side_effect=eval_side_effect_for_list):
        with pytest.raises(SexpEvaluationError, match="must be a string, symbol, number, or nil. Got <class 'list'>"):
            evaluator.evaluate_string(sexp_str)

def test_string_append_error_evaluation_fails(evaluator, mock_parser):
    """Test SexpEvaluationError from argument evaluation propagates."""
    sexp_str = '(string-append "a" undefined-symbol)'
    ast = [Symbol('string-append'), "a", Symbol('undefined-symbol')]
    mock_parser.parse_string.return_value = ast
    with pytest.raises(SexpEvaluationError, match="Unbound symbol"):
        evaluator.evaluate_string(sexp_str)

# --- Tests for director-evaluator-loop ---

def test_minimal_quoted_eval(evaluator, mock_parser):
    """Test direct evaluation of a Quoted object to diagnose AttributeError."""
    logging.critical(f"Minimal Test: Quoted type in test: {type(TestQuotedFromSexpdata)}, id: {id(TestQuotedFromSexpdata)}, module: {getattr(TestQuotedFromSexpdata, '__module__', 'N/A')}")
    
    # Create a Quoted object exactly as sexpdata.load would for "'foo"
    quoted_node = TestQuotedFromSexpdata(TestFileSymbol('test_sym'))
    
    logging.debug(f"Minimal Test: Created quoted_node: {quoted_node!r}, type: {type(quoted_node)}")
    logging.debug(f"Minimal Test: dir(quoted_node): {dir(quoted_node)}")
    logging.debug(f"Minimal Test: hasattr(quoted_node, 'val'): {hasattr(quoted_node, 'val')}")

    # Directly call _eval on the evaluator instance from the fixture
    try:
        result = evaluator._eval(quoted_node, SexpEnvironment())
        assert result == TestFileSymbol('test_sym') # Expect the inner symbol
        logging.info("Minimal Test: Successfully evaluated direct Quoted node.")
    except AttributeError as e:
        logging.exception("Minimal Test: AttributeError during direct _eval of Quoted node.")
        pytest.fail(f"Minimal test failed with AttributeError: {e}")
    except Exception as e:
        logging.exception(f"Minimal Test: Unexpected error during direct _eval: {e}")
        pytest.fail(f"Minimal test failed with unexpected error: {e}")

def test_director_loop_syntax_missing_clauses(evaluator, mock_parser):
    sexp_string = "(director-evaluator-loop (max-iterations 1))"
    # Simulate parser returning only the provided clauses
    mock_parser.parse_string.return_value = [Symbol("director-evaluator-loop"), [Symbol("max-iterations"), 1]]
    with pytest.raises(SexpEvaluationError, match="Missing required clauses: controller, director, evaluator, executor, initial-director-input"):
        evaluator.evaluate_string(sexp_string)

def test_director_loop_max_iterations_not_number(evaluator, mock_parser):
    sexp_string = """
    (director-evaluator-loop 
      (max-iterations "one") 
      (initial-director-input (quote "start"))
      (director (lambda (i it) i)) 
      (executor (lambda (p it) p)) 
      (evaluator (lambda (e p it) e)) 
      (controller (lambda (f p e it) (list 'stop e))))
    """
    # Construct AST based on the S-expression string
    mock_parser.parse_string.return_value = [
        Symbol("director-evaluator-loop"),
        [Symbol("max-iterations"), "one"], # "one" is a string, not a number
        [Symbol("initial-director-input"), [Symbol("quote"), "start"]],
        [Symbol("director"), [Symbol("lambda"), [Symbol("i"), Symbol("it")], Symbol("i")]],
        [Symbol("executor"), [Symbol("lambda"), [Symbol("p"), Symbol("it")], Symbol("p")]],
        [Symbol("evaluator"), [Symbol("lambda"), [Symbol("e"), Symbol("p"), Symbol("it")], Symbol("e")]],
        [Symbol("controller"), [Symbol("lambda"), [Symbol("f"), Symbol("p"), Symbol("e"), Symbol("it")], 
                                [Symbol("list"), [Symbol("quote"), Symbol("stop")], Symbol("e")]]]
    ]
    with pytest.raises(SexpEvaluationError, match="'max-iterations' must evaluate to a non-negative integer"):
        evaluator.evaluate_string(sexp_string)

def test_director_loop_phase_fn_not_callable(evaluator, mock_parser):
    sexp_string = """
    (director-evaluator-loop 
      (max-iterations 1) 
      (initial-director-input (quote "start"))
      (director 123) 
      (executor (lambda (p it) p)) 
      (evaluator (lambda (e p it) e)) 
      (controller (lambda (f p e it) (list 'stop e))))
    """
    mock_parser.parse_string.return_value = [
        Symbol("director-evaluator-loop"),
        [Symbol("max-iterations"), 1],
        [Symbol("initial-director-input"), [Symbol("quote"), "start"]],
        [Symbol("director"), 123], # director expression evaluates to 123 (a number)
        [Symbol("executor"), [Symbol("lambda"), [Symbol("p"), Symbol("it")], Symbol("p")]],
        [Symbol("evaluator"), [Symbol("lambda"), [Symbol("e"), Symbol("p"), Symbol("it")], Symbol("e")]],
        [Symbol("controller"), [Symbol("lambda"), [Symbol("f"), Symbol("p"), Symbol("e"), Symbol("it")], 
                                [Symbol("list"), [Symbol("quote"), Symbol("stop")], Symbol("e")]]]
    ]
    with pytest.raises(SexpEvaluationError, match="'director' expression must evaluate to a callable S-expression function, got <class 'int'>"):
        evaluator.evaluate_string(sexp_string)

def test_director_loop_single_iteration_stop(evaluator, mock_parser):
    sexp_string = """
    (director-evaluator-loop
      (max-iterations 5)
      (initial-director-input (quote "start_val"))
      (director   (lambda (current-input iter) (list 'plan-for current-input iter)))
      (executor   (lambda (plan iter) (list 'exec-of plan iter)))
      (evaluator  (lambda (exec-result plan iter) (list 'eval-of exec-result iter)))
      (controller (lambda (eval-feedback plan exec-result iter) (list 'stop (list 'final eval-feedback iter))))
    )
    """
    # Use a real parser to avoid recursion
    real_parser_for_side_effect = SexpParser()
    mock_parser.parse_string.side_effect = real_parser_for_side_effect.parse_string
    
    result = evaluator.evaluate_string(sexp_string)
    
    expected_final_val_structure = [
        Symbol('final'), 
        [Symbol('eval-of'), 
         [Symbol('exec-of'), 
          [Symbol('plan-for'), 'start_val', 1], 
          1], 
         1], 
        1
    ]
    assert result == expected_final_val_structure

def test_director_loop_max_iterations_termination(evaluator, mock_parser):
    sexp_string_corrected_controller = """
    (director-evaluator-loop
      (max-iterations 2)
      (initial-director-input "initial")
      (director   (lambda (current-input iter) (list 'd current-input iter)))
      (executor   (lambda (plan iter) (list 'e plan iter)))
      (evaluator  (lambda (exec-result plan iter) (list 'v exec-result iter)))
      (controller (lambda (eval-feedback plan exec-result iter) 
                    (list 'continue (list 'next_input_for iter))))
    )
    """
    real_parser_for_side_effect = SexpParser()
    mock_parser.parse_string.side_effect = real_parser_for_side_effect.parse_string

    result = evaluator.evaluate_string(sexp_string_corrected_controller)
    expected_result = [
        Symbol('e'), 
        [Symbol('d'), [Symbol('next_input_for'), 1], 2], 
        2
    ]
    assert result == expected_result

def test_director_loop_max_iterations_zero(evaluator, mock_parser):
    sexp_string = """
    (director-evaluator-loop
      (max-iterations 0)
      (initial-director-input "initial")
      (director   (lambda (ci iter) (log-message "director should not run")))
      (executor   (lambda (p iter)  (log-message "executor should not run")))
      (evaluator  (lambda (er p iter) (log-message "evaluator should not run")))
      (controller (lambda (ef p er iter) (log-message "controller should not run")))
    )
    """
    real_parser_for_side_effect = SexpParser()
    mock_parser.parse_string.side_effect = real_parser_for_side_effect.parse_string
    result = evaluator.evaluate_string(sexp_string)
    assert result == [] 

def test_director_loop_controller_malformed_decision_not_list(evaluator, mock_parser):
    sexp_string = """
    (director-evaluator-loop
      (max-iterations 1) (initial-director-input "start")
      (director (lambda (i it) i)) (executor (lambda (p it) p)) (evaluator (lambda (e p it) e))
      (controller (lambda (f p e it) "stop")) 
    )
    """
    real_parser_for_side_effect = SexpParser()
    mock_parser.parse_string.side_effect = real_parser_for_side_effect.parse_string
    with pytest.raises(SexpEvaluationError, match="Controller must return a list of \\(action_symbol value\\)"):
        evaluator.evaluate_string(sexp_string)

def test_director_loop_error_in_phase_function_propagates(evaluator, mock_parser):
    sexp_string = """
    (director-evaluator-loop
      (max-iterations 1) (initial-director-input "start")
      (director (lambda (i it) (undefined-function i))) 
      (executor (lambda (p it) p)) (evaluator (lambda (e p it) e)) (controller (lambda (f p e it) (list 'stop e)))
    )
    """
    real_parser_for_side_effect = SexpParser()
    mock_parser.parse_string.side_effect = real_parser_for_side_effect.parse_string
    with pytest.raises(SexpEvaluationError, match="Error in 'director' phase.*Unbound symbol or unrecognized operator: undefined-function"):
        evaluator.evaluate_string(sexp_string)

def test_director_loop_config_access_in_all_phases(evaluator, mock_parser, caplog):
    """Test that phase functions can access *loop-config*."""
    sexp_string = """
    (director-evaluator-loop
      (max-iterations 1)
      (initial-director-input "start_token")
      (director (lambda (current-input iter) 
                  (log-message "DIR_MAX_ITER:" (get-field *loop-config* "max-iterations"))
                  (log-message "DIR_INIT_IN:" (get-field *loop-config* "initial-director-input"))
                  (list 'plan current-input iter (get-field *loop-config* "max-iterations"))))
      (executor (lambda (plan iter) 
                  (log-message "EXEC_MAX_ITER:" (get-field *loop-config* "max-iterations"))
                  (list 'exec plan iter (get-field *loop-config* "initial-director-input"))))
      (evaluator (lambda (exec-result plan iter) 
                   (log-message "EVAL_INIT_IN:" (get-field *loop-config* "initial-director-input"))
                   (list 'eval exec-result iter (get-field *loop-config* "max-iterations"))))
      (controller (lambda (eval-feedback plan exec-result iter)
                    (log-message "CTRL_MAX_ITER:" (get-field *loop-config* "max-iterations"))
                    (log-message "CTRL_INIT_IN:" (get-field *loop-config* "initial-director-input"))
                    (list 'stop 
                          (list 'final_result 
                                (get-field *loop-config* "max-iterations")
                                (get-field *loop-config* "initial-director-input")
                                eval-feedback
                                iter))))
    )
    """
    real_parser_for_side_effect = SexpParser()
    mock_parser.parse_string.side_effect = real_parser_for_side_effect.parse_string
    
    # Enable capturing logs at INFO level for log-message primitive
    caplog.set_level(logging.INFO)

    result = evaluator.evaluate_string(sexp_string)

    # Expected result structure based on the lambdas
    # (list 'final_result max_iter init_input eval_feedback iter)
    # eval_feedback = (list 'eval exec_result iter max_iter)
    # exec_result = (list 'exec plan iter init_input)
    # plan = (list 'plan current_input iter max_iter)
    # current_input = "start_token", iter = 1, max_iter = 1, init_input = "start_token"

    expected_result = [
        Symbol('final_result'),
        1,  # max-iterations from *loop-config* in controller
        "start_token", # initial-director-input from *loop-config* in controller
        [   # eval_feedback
            Symbol('eval'),
            [   # exec_result
                Symbol('exec'),
                [   # plan
                    Symbol('plan'),
                    "start_token",  # current-input to director
                    1,  # iter in director
                    1   # max-iterations from *loop-config* in director
                ],
                1,  # iter in executor
                "start_token"  # initial-director-input from *loop-config* in executor
            ],
            1,  # iter in evaluator
            1   # max-iterations from *loop-config* in evaluator
        ],
        1  # iter in controller
    ]
    assert result == expected_result

    # Check logs for evidence of config access
    log_records = [record.message for record in caplog.records if record.name == 'src.sexp_evaluator.sexp_primitives']
    
    assert "SexpLog: DIR_MAX_ITER: 1" in log_records
    assert "SexpLog: DIR_INIT_IN: start_token" in log_records
    assert "SexpLog: EXEC_MAX_ITER: 1" in log_records
    assert "SexpLog: EVAL_INIT_IN: start_token" in log_records
    assert "SexpLog: CTRL_MAX_ITER: 1" in log_records
    assert "SexpLog: CTRL_INIT_IN: start_token" in log_records

def test_director_loop_integration_with_get_field_and_eq(evaluator, mock_parser):
    sexp_string = """
    (director-evaluator-loop
      (max-iterations 3)
      (initial-director-input (list (list 'status "initial") (list 'data 0)))
      (director (lambda (current-input iter)
                  (log-message "Director: current_input=" current-input "iter=" iter)
                  current-input)) 
      (executor (lambda (plan iter)
                  (log-message "Executor: plan=" plan "iter=" iter)
                  (if (< (get-field plan "data") 2)
                      (list (list 'status "pending") (list 'data (+ (get-field plan "data") 1)))
                      (list (list 'status "done") (list 'data (get-field plan "data"))))))
      (evaluator (lambda (exec-result plan iter)
                   (log-message "Evaluator: exec_result=" exec-result "iter=" iter)
                   exec-result)) 
      (controller (lambda (eval-feedback plan exec-result iter)
                    (log-message "Controller: eval_feedback=" eval-feedback "iter=" iter)
                    ;; Can still access *loop-config* if needed, via lexical scope
                    (log-message "Controller: Max Iter from loop-config:" (get-field *loop-config* "max-iterations"))
                    (if (string=? (get-field eval-feedback "status") "done")
                        (list 'stop exec-result) 
                        (list 'continue eval-feedback)))) 
    )
    """
    real_parser_for_side_effect = SexpParser()
    mock_parser.parse_string.side_effect = real_parser_for_side_effect.parse_string

    result = evaluator.evaluate_string(sexp_string)
    
    expected_result = [
        [Symbol('status'), "done"],
        [Symbol('data'), 2]
    ]
    assert result == expected_result
def test_string_append_with_numbers_and_none(evaluator, mock_parser):
    """Test string-append correctly handles numbers and None."""
    sexp_str = '(string-append "val:" 123 " " nil "end")'
    ast = [Symbol('string-append'), "val:", 123, " ", None, "end"] # Assume nil parses to None
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) == "val:123 end"

# Add this new test to ensure numbers are stringified
def test_string_append_with_numeric_args(evaluator, mock_parser):
    """Test (string-append "Value: " 123 " units") returns "Value: 123 units"."""
    sexp_str = '(string-append "Value: " 123 " units" 4.5)'
    ast = [Symbol('string-append'), "Value: ", 123, " units", 4.5]
    mock_parser.parse_string.return_value = ast
    assert evaluator.evaluate_string(sexp_str) == "Value: 123 units4.5"

from typing import Callable # Add this import

class TestSexpEvaluatorIterativeLoop:

    # Helper to create a basic valid loop AST for tests
    def _create_loop_ast(self, max_iter=1, initial_input_expr="'start'", test_cmd_expr="'echo test'", executor_body="'exec_result'", validator_body="(list (list 'stdout' \"ok\") (list 'stderr' \"\") (list 'exit_code 0))", controller_body="(list 'stop 'final_result')"):
        S = Symbol
        # Ensure initial_input_expr and test_cmd_expr are quoted if they are simple strings
        # The helper was already doing this with [S("quote"), initial_input_expr]
        # but the default values were strings like "'start'" which would become (quote 'start')
        # Let's assume the expressions passed to the helper are already valid S-expression nodes
        # or simple values that _eval can handle.
        # For simplicity in the helper, we'll assume they are expressions that need quoting if literal.
        # However, the tests often pass direct values for max_iter, so we need to be careful.

        # Let's refine the helper to construct AST nodes more directly for literals
        # or use a placeholder for complex expressions that tests will mock _eval for.

        def make_expr_node(val):
            if isinstance(val, str) and val.startswith("'") and val.endswith("'"): # Quoted symbol like 'start'
                return [S("quote"), S(val[1:-1])]
            if isinstance(val, str): # Simple string literal
                return val
            if isinstance(val, (int, float, bool)) or val is None: # Numeric/bool/nil literals
                return val
            return val # Assume it's already an AST node if complex

        return [
            S("iterative-loop"),
            [S("max-iterations"), make_expr_node(max_iter)],
            [S("initial-input"), make_expr_node(initial_input_expr)],
            [S("test-command"), make_expr_node(test_cmd_expr)],
            [S("executor"),   [S("lambda"), [S("ci"), S("it")], make_expr_node(executor_body)]],
            [S("validator"),  [S("lambda"), [S("tc"), S("it")], validator_body if isinstance(validator_body, list) else make_expr_node(validator_body)]],
            [S("controller"), [S("lambda"), [S("er"), S("vr"), S("ci"), S("it")], controller_body if isinstance(controller_body, list) else make_expr_node(controller_body)]]
        ]


    def test_iterative_loop_syntax_missing_clause(self, evaluator, mock_parser):
        ast = self._create_loop_ast()
        # Remove controller: it's the 7th element (index 6) in the list returned by _create_loop_ast
        # [iterative-loop, max-iter-clause, initial-input-clause, test-cmd-clause, executor-clause, validator-clause, controller-clause]
        # So, ast[0] is 'iterative-loop', ast[1] is max-iter clause, ..., ast[6] is controller clause.
        # To remove controller, we pop the last element if it's the default structure.
        # A more robust way is to filter by clause name if the helper returned a dict, but it returns a list.
        # Let's assume the structure from _create_loop_ast is fixed for this removal.
        # The list is [loop_sym, clause1, clause2, clause3, clause4, clause5, clause6]
        # So, to remove controller (last clause), we can do:
        filtered_ast = [item for item in ast if not (isinstance(item, list) and item[0] == Symbol("controller"))]

        mock_parser.parse_string.return_value = filtered_ast
        with pytest.raises(SexpEvaluationError, match="Missing required clauses:.*controller"):
            evaluator.evaluate_string("(iterative-loop ...)")

    def test_iterative_loop_syntax_duplicate_clause(self, evaluator, mock_parser):
        ast = self._create_loop_ast()
        ast.append([Symbol("max-iterations"), 5]) # Add duplicate
        mock_parser.parse_string.return_value = ast
        with pytest.raises(SexpEvaluationError, match="Duplicate clause 'max-iterations'"):
            evaluator.evaluate_string("(iterative-loop ...)")

    def test_iterative_loop_syntax_invalid_clause_format(self, evaluator, mock_parser):
        ast = self._create_loop_ast()
        ast[1] = Symbol("max-iterations") # Invalid format, should be [Symbol("max-iterations"), value_expr]
        mock_parser.parse_string.return_value = ast
        with pytest.raises(SexpEvaluationError, match="Each clause must be a list"):
            evaluator.evaluate_string("(iterative-loop ...)")

    def test_iterative_loop_config_max_iter_not_int(self, evaluator, mock_parser, mocker):
        ast = self._create_loop_ast(max_iter="'not-an-int'") # String literal
        mock_parser.parse_string.return_value = ast
        
        # Store the original _eval method
        original_eval = evaluator._eval
        
        # Define the side effect function
        def eval_side_effect(node, env):
            # Specifically handle the max-iterations expression
            if isinstance(node, list) and len(node) == 2 and node[0] == Symbol("quote") and node[1] == Symbol("not-an-int"):
                return "not-an-int"  # Return the problematic string value
            # For all other nodes, use the original _eval method
            return original_eval(node, env)
        
        # Apply the patch with the side effect
        mocker.patch.object(evaluator, '_eval', side_effect=eval_side_effect)
        
        with pytest.raises(SexpEvaluationError, match="'max-iterations' must evaluate to a non-negative integer, got 'not-an-int'"):
            evaluator.evaluate_string("(iterative-loop ...)")


    def test_iterative_loop_config_max_iter_negative(self, evaluator, mock_parser):
        ast = self._create_loop_ast(max_iter=-1) # Pass -1 directly
        mock_parser.parse_string.return_value = ast
        
        with pytest.raises(SexpEvaluationError, match="'max-iterations' must evaluate to a non-negative integer"):
            evaluator.evaluate_string("(iterative-loop ...)")

    def test_iterative_loop_config_test_cmd_not_string(self, evaluator, mock_parser):
        ast = self._create_loop_ast(test_cmd_expr=123) # Pass 123 directly
        mock_parser.parse_string.return_value = ast

        with pytest.raises(SexpEvaluationError, match="'test-command' must evaluate to a string"):
            evaluator.evaluate_string("(iterative-loop ...)")

    def test_iterative_loop_config_phase_fn_not_callable(self, evaluator, mock_parser):
        ast = self._create_loop_ast()
        # Modify the executor clause to be a number instead of a lambda expression
        # ast[0] = 'iterative-loop'
        # ast[1] = (max-iterations ...)
        # ast[2] = (initial-input ...)
        # ast[3] = (test-command ...)
        # ast[4] = (executor ...)
        ast[4] = [Symbol("executor"), 123] # Executor expression is now the number 123
        mock_parser.parse_string.return_value = ast

        with pytest.raises(SexpEvaluationError, match="'executor' expression must evaluate to a callable"):
            evaluator.evaluate_string("(iterative-loop ...)")

    def test_iterative_loop_config_eval_error(self, evaluator, mock_parser):
        # initial_input_expr is already an S-expression node in the helper
        ast = self._create_loop_ast(initial_input_expr=Symbol("unbound-symbol"))
        mock_parser.parse_string.return_value = ast
        
        with pytest.raises(SexpEvaluationError, match="Error evaluating 'initial-input'.*Unbound symbol.*unbound-symbol"):
            evaluator.evaluate_string("(iterative-loop ...)")

    def test_iterative_loop_stops_immediately(self, evaluator, mock_parser, mocker):
        """Test stops on first controller 'stop'."""
        final_val = {"result": "stopped early"}
        # Construct the AST for the controller body explicitly
        controller_body_ast = [
            Symbol("list"),
            [Symbol("quote"), Symbol("stop")],
            # Quote the dictionary itself to pass it as literal data
            [Symbol("quote"), final_val]
        ]
        ast = self._create_loop_ast(
            max_iter=5,
            controller_body=controller_body_ast # Pass the constructed AST
        )
        mock_parser.parse_string.return_value = ast

        # Mock _eval more carefully: only intercept specific expressions
        original_eval = evaluator._eval

        # Store the mock functions that _eval should return for the lambdas
        mock_executor_lambda_func = MagicMock(spec=Callable, name="mock_executor_lambda")
        mock_validator_lambda_func = MagicMock(spec=Callable, name="mock_validator_lambda")
        mock_controller_lambda_func = MagicMock(spec=Callable, name="mock_controller_lambda")

        def config_eval_side_effect(node, env):
            # Check for specific config expressions
            if node == 5: return 5
            if node == [Symbol("quote"), Symbol("start")]: return "start"
            if node == [Symbol("quote"), Symbol("echo test")]: return "echo test"

            # Return the stored mock functions for the lambda expressions
            if isinstance(node, list) and len(node) > 0 and node[0] == Symbol("lambda"):
                # Identify lambda by parameter list
                params = node[1]
                if params == [Symbol("ci"), Symbol("it")]: # Executor lambda
                    return mock_executor_lambda_func
                if params == [Symbol("tc"), Symbol("it")]: # Validator lambda
                    return mock_validator_lambda_func
                if params == [Symbol("er"), Symbol("vr"), Symbol("ci"), Symbol("it")]: # Controller lambda
                    return mock_controller_lambda_func

            # Fallback to original _eval for everything else
            # This includes the top-level (iterative-loop ...) call itself
            return original_eval(node, env)

        mocker.patch.object(evaluator, '_eval', side_effect=config_eval_side_effect)

        # Mock the _call_phase_function helper
        mock_executor_result = TaskResult(status="COMPLETE", content="Exec Iter 1")
        mock_validator_result = {"stdout": "Test OK", "stderr": "", "exit_code": 0}
        mock_controller_decision = [Symbol("stop"), final_val]

        mock_call_phase = mocker.patch.object(evaluator, '_call_phase_function')
        mock_call_phase.side_effect = [
            mock_executor_result,    # Return value for _call_phase_function(executor, ...)
            mock_validator_result,   # Return value for _call_phase_function(validator, ...)
            mock_controller_decision # Return value for _call_phase_function(controller, ...)
        ]

        # ACT: Call the evaluator
        result = evaluator.evaluate_string("(iterative-loop ...)")

        # ASSERT: The final result should be the value associated with 'stop'
        assert result == final_val
        assert mock_call_phase.call_count == 3 # Called once for each phase in the first iteration

        # Verify the arguments passed TO _call_phase_function
        # Check that the correct mock lambda function was passed as func_to_call
        mock_call_phase.assert_any_call("executor", mock_executor_lambda_func, ["start", 1], mocker.ANY, mocker.ANY, 1)
        mock_call_phase.assert_any_call("validator", mock_validator_lambda_func, ["echo test", 1], mocker.ANY, mocker.ANY, 1)
        mock_call_phase.assert_any_call("controller", mock_controller_lambda_func, [mock_executor_result, mock_validator_result, "start", 1], mocker.ANY, mocker.ANY, 1)


    def test_iterative_loop_continues_once_then_stops(self, evaluator, mock_parser, mocker):
        """Test continue -> stop flow."""
        final_val = {"result": "stopped iter 2"}
        # Controller body will be mocked via _call_phase_function side_effect
        ast = self._create_loop_ast(max_iter=5) 
        mock_parser.parse_string.return_value = ast

        # Mock _eval for config expressions
        def config_eval_side_effect(node, env):
            if node == 5: return 5
            if node == [Symbol("quote"), Symbol("start")]: return "start"
            if node == [Symbol("quote"), Symbol("echo test")]: return "echo test"
            if isinstance(node, list) and node[0] == Symbol("lambda"): return MagicMock(spec=Callable)
            return MagicMock()
        mocker.patch.object(evaluator, '_eval', side_effect=config_eval_side_effect)

        mock_exec_res_1 = TaskResult(status="COMPLETE", content="Exec Iter 1")
        mock_val_res_1 = {"stdout": "Test Failed", "stderr": "AssertionError", "exit_code": 1}
        next_input_iter_1 = {"prompt": "Revise 1", "files": ["f1"]}
        mock_ctrl_dec_1 = [Symbol("continue"), next_input_iter_1] 

        mock_exec_res_2 = TaskResult(status="COMPLETE", content="Exec Iter 2")
        mock_val_res_2 = {"stdout": "Test OK", "stderr": "", "exit_code": 0}
        mock_ctrl_dec_2 = [Symbol("stop"), final_val] 

        mock_call_phase = mocker.patch.object(evaluator, '_call_phase_function')
        mock_call_phase.side_effect = [
            mock_exec_res_1, mock_val_res_1, mock_ctrl_dec_1, # Iter 1
            mock_exec_res_2, mock_val_res_2, mock_ctrl_dec_2  # Iter 2
        ]

        result = evaluator.evaluate_string("(iterative-loop ...)")

        assert result == final_val
        assert mock_call_phase.call_count == 6 
        mock_call_phase.assert_any_call("executor", mocker.ANY, [next_input_iter_1, 2], mocker.ANY, mocker.ANY, 2)

    def test_iterative_loop_reaches_max_iterations(self, evaluator, mock_parser, mocker):
        """Test loop terminates by max_iterations."""
        ast = self._create_loop_ast(max_iter=2) 
        mock_parser.parse_string.return_value = ast

        def config_eval_side_effect(node, env):
            if node == 2: return 2 # max_iter
            if node == [Symbol("quote"), Symbol("start")]: return "start"
            if node == [Symbol("quote"), Symbol("echo test")]: return "echo test"
            if isinstance(node, list) and node[0] == Symbol("lambda"): return MagicMock(spec=Callable)
            return MagicMock()
        mocker.patch.object(evaluator, '_eval', side_effect=config_eval_side_effect)


        mock_exec_res_1 = TaskResult(status="COMPLETE", content="Exec Iter 1")
        mock_val_res_1 = {"stdout": "Test Failed", "stderr": "Error 1", "exit_code": 1}
        mock_ctrl_dec_1 = [Symbol("continue"), "next_input_1"]

        mock_exec_res_2 = TaskResult(status="COMPLETE", content="Exec Iter 2 - Last") 
        mock_val_res_2 = {"stdout": "Test Failed Again", "stderr": "Error 2", "exit_code": 1}
        mock_ctrl_dec_2 = [Symbol("continue"), "next_input_2"] 

        mock_call_phase = mocker.patch.object(evaluator, '_call_phase_function')
        mock_call_phase.side_effect = [
            mock_exec_res_1, mock_val_res_1, mock_ctrl_dec_1, 
            mock_exec_res_2, mock_val_res_2, mock_ctrl_dec_2  
        ]

        result = evaluator.evaluate_string("(iterative-loop ...)")

        assert result == mock_exec_res_2 
        assert mock_call_phase.call_count == 6

    def test_iterative_loop_zero_iterations(self, evaluator, mock_parser, mocker):
        """Test loop with max_iterations=0."""
        ast = self._create_loop_ast(max_iter=0)
        mock_parser.parse_string.return_value = ast

        def config_eval_side_effect(node, env):
            if node == 0: return 0 # max_iter
            if node == [Symbol("quote"), Symbol("start")]: return "start" # initial-input
            if node == [Symbol("quote"), Symbol("echo test")]: return "echo test" # test-command
            if isinstance(node, list) and node[0] == Symbol("lambda"): return MagicMock(spec=Callable)
            return MagicMock()
        mocker.patch.object(evaluator, '_eval', side_effect=config_eval_side_effect)
        
        mock_call_phase = mocker.patch.object(evaluator, '_call_phase_function')

        result = evaluator.evaluate_string("(iterative-loop ...)")

        assert result == [] 
        mock_call_phase.assert_not_called()

    def test_iterative_loop_controller_invalid_decision_format(self, evaluator, mock_parser, mocker):
        """Test controller returning invalid format."""
        # Controller body is a string literal, not (list 'action value)
        ast = self._create_loop_ast(controller_body="'stop_string_literal'") 
        mock_parser.parse_string.return_value = ast

        def config_eval_side_effect(node, env):
            if node == 1: return 1 # max_iter
            if node == [Symbol("quote"), Symbol("start")]: return "start"
            if node == [Symbol("quote"), Symbol("echo test")]: return "echo test"
            if isinstance(node, list) and node[0] == Symbol("lambda"): return MagicMock(spec=Callable)
            return MagicMock()
        mocker.patch.object(evaluator, '_eval', side_effect=config_eval_side_effect)

        mock_exec_res = TaskResult(status="COMPLETE", content="Exec")
        mock_val_res = {"stdout": "OK", "stderr": "", "exit_code": 0}
        # This is what the controller's lambda (mocked by _eval) will return to _call_phase_function
        # And _call_phase_function will return this to _eval_iterative_loop
        mock_invalid_decision = "stop_string_literal" 

        mock_call_phase = mocker.patch.object(evaluator, '_call_phase_function')
        mock_call_phase.side_effect = [mock_exec_res, mock_val_res, mock_invalid_decision]

        with pytest.raises(SexpEvaluationError, match="Controller must return a list of .*action_symbol value"):
            evaluator.evaluate_string("(iterative-loop ...)")

    def test_iterative_loop_controller_invalid_action_symbol(self, evaluator, mock_parser, mocker):
        """Test controller returning invalid action symbol."""
        ast = self._create_loop_ast(controller_body=[Symbol("list"), [Symbol("quote"), Symbol("stahp")], [Symbol("quote"), "val"]])
        mock_parser.parse_string.return_value = ast

        def config_eval_side_effect(node, env):
            if node == 1: return 1
            if node == [Symbol("quote"), Symbol("start")]: return "start"
            if node == [Symbol("quote"), Symbol("echo test")]: return "echo test"
            if isinstance(node, list) and node[0] == Symbol("lambda"): return MagicMock(spec=Callable)
            return MagicMock()
        mocker.patch.object(evaluator, '_eval', side_effect=config_eval_side_effect)


        mock_exec_res = TaskResult(status="COMPLETE", content="Exec")
        mock_val_res = {"stdout": "OK", "stderr": "", "exit_code": 0}
        mock_invalid_decision = [Symbol("stahp"), "val"]

        mock_call_phase = mocker.patch.object(evaluator, '_call_phase_function')
        mock_call_phase.side_effect = [mock_exec_res, mock_val_res, mock_invalid_decision]

        with pytest.raises(SexpEvaluationError, match="Controller decision action must be 'continue' or 'stop'"):
            evaluator.evaluate_string("(iterative-loop ...)")

    def test_iterative_loop_error_in_executor(self, evaluator, mock_parser, mocker):
        """Test error propagation from executor phase."""
        ast = self._create_loop_ast()
        mock_parser.parse_string.return_value = ast

        def config_eval_side_effect(node, env): # For _eval of config clauses
            if node == 1: return 1
            if node == [Symbol("quote"), Symbol("start")]: return "start"
            if node == [Symbol("quote"), Symbol("echo test")]: return "echo test"
            if isinstance(node, list) and node[0] == Symbol("lambda"): return MagicMock(spec=Callable)
            return MagicMock()
        mocker.patch.object(evaluator, '_eval', side_effect=config_eval_side_effect)
        
        mock_call_phase = mocker.patch.object(evaluator, '_call_phase_function')
        # _call_phase_function for executor raises error
        mock_call_phase.side_effect = SexpEvaluationError("Executor failed!") 

        with pytest.raises(SexpEvaluationError, match="Error in 'executor' phase.*Executor failed!"):
            evaluator.evaluate_string("(iterative-loop ...)")

    def test_iterative_loop_error_in_validator(self, evaluator, mock_parser, mocker):
        """Test error propagation from validator phase."""
        ast = self._create_loop_ast()
        mock_parser.parse_string.return_value = ast

        def config_eval_side_effect(node, env):
            if node == 1: return 1
            if node == [Symbol("quote"), Symbol("start")]: return "start"
            if node == [Symbol("quote"), Symbol("echo test")]: return "echo test"
            if isinstance(node, list) and node[0] == Symbol("lambda"): return MagicMock(spec=Callable)
            return MagicMock()
        mocker.patch.object(evaluator, '_eval', side_effect=config_eval_side_effect)

        mock_call_phase = mocker.patch.object(evaluator, '_call_phase_function')
        mock_call_phase.side_effect = [
            TaskResult(status="COMPLETE", content="Exec OK"), 
            SexpEvaluationError("Validator failed!") 
        ]

        with pytest.raises(SexpEvaluationError, match="Error in 'validator' phase.*Validator failed!"):
            evaluator.evaluate_string("(iterative-loop ...)")

    def test_iterative_loop_error_in_controller(self, evaluator, mock_parser, mocker):
        """Test error propagation from controller phase."""
        ast = self._create_loop_ast()
        mock_parser.parse_string.return_value = ast

        def config_eval_side_effect(node, env):
            if node == 1: return 1
            if node == [Symbol("quote"), Symbol("start")]: return "start"
            if node == [Symbol("quote"), Symbol("echo test")]: return "echo test"
            if isinstance(node, list) and node[0] == Symbol("lambda"): return MagicMock(spec=Callable)
            return MagicMock()
        mocker.patch.object(evaluator, '_eval', side_effect=config_eval_side_effect)

        mock_call_phase = mocker.patch.object(evaluator, '_call_phase_function')
        mock_call_phase.side_effect = [
            TaskResult(status="COMPLETE", content="Exec OK"), 
            {"stdout": "OK", "stderr": "", "exit_code": 0}, 
            SexpEvaluationError("Controller failed!") 
        ]

        with pytest.raises(SexpEvaluationError, match="Error in 'controller' phase.*Controller failed!"):
            evaluator.evaluate_string("(iterative-loop ...)")

    def test_iterative_loop_integration_simple_counter(self, evaluator, mock_parser):
        """Test a simple counter loop using actual lambdas and primitives."""
        sexp_string = """
        (iterative-loop
          (max-iterations 5)
          (initial-input 0) 
          (test-command "'true'") 
          (executor   (lambda (current-count iter) (+ current-count 1))) 
          (validator  (lambda (cmd iter) (list (list 'stdout "") (list 'stderr "") (list 'exit_code 0)))) 
          (controller (lambda (exec-res valid-res current-in iter)
                        (if (< exec-res 3) 
                            (list 'continue exec-res) 
                            (list 'stop exec-res)))) 
        )
        """
        # Use the real parser for this integration test
        real_parser = SexpParser()
        mock_parser.parse_string.side_effect = real_parser.parse_string
        
        result = evaluator.evaluate_string(sexp_string)
        assert result == 3
