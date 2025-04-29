"""
Unit tests for the SexpEvaluator.
"""

import pytest
from unittest.mock import MagicMock, call, ANY, patch
from src.sexp_evaluator.sexp_evaluator import SexpEvaluator
from src.sexp_evaluator.sexp_environment import SexpEnvironment
from src.system.errors import SexpSyntaxError, SexpEvaluationError # Remove TaskError import from here
from src.system.models import (
    TaskResult, SubtaskRequest, ContextGenerationInput, AssociativeMatchResult,
    MatchTuple, TaskFailureError, ContextManagement, TaskError # Import TaskError model here
)

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
    # Patch the SexpParser instantiation within the evaluator's init
    with patch('src.sexp_evaluator.sexp_evaluator.SexpParser', return_value=mock_parser):
         evaluator_instance = SexpEvaluator(
             task_system=mock_task_system,
             handler=mock_handler,
             memory_system=mock_memory_system
         )
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
    get_context_sym = Symbol("get_context") if Symbol != str else "get_context"
    query_sym = Symbol("query") if Symbol != str else "query"
    inputs_sym = Symbol("inputs") if Symbol != str else "inputs"
    file_sym = Symbol("file") if Symbol != str else "file"
    # Add quote symbol
    quote_sym = Symbol("quote") if Symbol != str else "quote"

    # Sexp: (get_context (query "find stuff") (inputs (quote ((file "/a.py")))))
    mock_parser.parse_string.return_value = [
        get_context_sym,
        [query_sym, "find stuff"],
        # Use quote around the literal list structure
        [inputs_sym, [quote_sym, [[file_sym, "/a.py"]]]]
    ]
    # Expected input to memory system after evaluation and conversion
    expected_context_input = ContextGenerationInput(
        query="find stuff",
        inputs={"file": "/a.py"} # Expect inputs as a dict
    )
    mock_memory_system.get_relevant_context_for.return_value = AssociativeMatchResult(
        context_summary="Mocked context", matches=[MatchTuple(path="/mock/file.py", relevance=1.0)]
    )

    # Test string can reflect quote, though mock overrides parsing
    result = evaluator.evaluate_string('(get_context (query "find stuff") (inputs (quote ((file "/a.py")))))')

    # Assert MemorySystem was called correctly
    mock_memory_system.get_relevant_context_for.assert_called_once_with(expected_context_input)

    # Assert result is the list of paths from the mock
    assert result == ["/mock/file.py"]

def test_eval_primitive_get_context_failure(evaluator, mock_parser, mock_memory_system):
    """Test get_context when memory system returns an error."""
    get_context_sym = Symbol("get_context") if Symbol != str else "get_context"
    query_sym = Symbol("query") if Symbol != str else "query"
    mock_parser.parse_string.return_value = [get_context_sym, [query_sym, "find stuff"]]
    # Configure mock to return an error in the result object
    mock_memory_system.get_relevant_context_for.return_value = AssociativeMatchResult(
        context_summary="", matches=[], error="Database connection failed"
    )

    # Expect the SexpEvaluationError that wraps the underlying failure
    with pytest.raises(SexpEvaluationError) as excinfo:
        evaluator.evaluate_string('(get_context (query "find stuff"))')

    # Check the wrapper exception message
    assert "Context retrieval failed" in str(excinfo.value)
    assert "Database connection failed" in str(excinfo.value) # Check detail propagation

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
    with pytest.raises(SexpEvaluationError, match=f"Cannot invoke '{unknown_id}': Not a recognized tool or atomic task."):
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
