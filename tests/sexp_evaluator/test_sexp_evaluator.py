"""
Unit tests for the SexpEvaluator.
"""

import pytest
import re # Import re for regular expression matching in error messages
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
            "parameters": {"p1": {"description": "Parameter p1"}},
            "instructions": "inst {{p1}}",
            "model": None # Ensure not present if not specified
        }
        # Clear model if it exists from optional args test
        if "model" in expected_template_dict: del expected_template_dict["model"]


        mock_task_system.register_template.return_value = True # Simulate success

        result = evaluator.evaluate_string(f"(defatom {task_name} ...)") # String content doesn't matter due to mock

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
            "parameters": {
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
        # Mock find_template to return the definition *after* registration is called
        # Use side_effect to control return value based on call order if needed,
        # or simply mock it to return the template assuming registration worked.
        expected_template_dict = {
            "name": def_task_name, "type": "atomic", "subtype": "standard",
            "description": f"Dynamically defined task: {def_task_name}",
            "parameters": {"x": {"description": "Parameter x"}},
            "instructions": "Run {{x}}", "model": None
        }
        if "model" in expected_template_dict: del expected_template_dict["model"]

        # Mock find_template to return the dict when called with the task name
        # No need for side_effect list here, as defatom doesn't call find_template
        mock_task_system.find_template.side_effect = lambda name: expected_template_dict if name == def_task_name else None


        # Mock invocation result
        mock_invocation_result = TaskResult(status="COMPLETE", content="Task A Done")
        mock_task_system.execute_atomic_template.return_value = mock_invocation_result

        result = evaluator.evaluate_string(f"(progn (defatom {def_task_name} ...) ({def_task_name} ...))")

        # Assert registration happened
        mock_task_system.register_template.assert_called_once_with(expected_template_dict)

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
            [Symbol("params"), ["p1"], "bad-item"], # "bad-item" is not a list
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
        with pytest.raises(SexpEvaluationError, match=r"subtype.*must be a string"):
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
    mock_executor_func.assert_not_called()

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
        if isinstance(node, list) and len(node) > 0 and node[0] == S('+'):
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
        if node == [S('list'), 1]:
            return [1] # Simulate list primitive result
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
    mock_handler.tool_executors = {
        "mock_ok": mock_ok_executor,
        "fail_sometimes": mock_fail_executor
    }
    # Mock the _execute_tool wrapper as well
    mock_handler._execute_tool.side_effect = lambda name, params: mock_handler.tool_executors[name](params)


    # Mock 'fail_sometimes' executor to fail on the second call using side_effect
    body_expr_for_error_str = str([S('progn'), [S('mock_ok')], [S('fail_sometimes')]])
    fail_error = SexpEvaluationError(
        "Intentional body failure from test",
        expression=body_expr_for_error_str,
        error_details="Test-induced failure in body"
    )
    call_count = 0
    def fail_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise fail_error
        return TaskResult(status="COMPLETE", content="OK") # Simulate success on other calls

    mock_fail_executor.side_effect = fail_side_effect

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



    def test_eval_list_form_standard_path_evaluates_op_and_args_and_applies(self, evaluator, mocker):
        """Test _eval_list_form's standard path: evaluates operator, evaluates args, then applies."""
        env = SexpEnvironment()
        op_expr = Symbol("my_func_name") # Operator expression (a symbol)
        arg1_expr = 10 # Argument expression 1
        arg2_expr = Symbol("var_a") # Argument expression 2
        expr_list = [op_expr, arg1_expr, arg2_expr] # (my_func_name 10 var_a)
        original_expr_str = str(expr_list)

        env.define("var_a", 20) # For evaluating arg2_expr

        # Mock _eval to control evaluation of operator and arguments
        # op_expr ("my_func_name") -> "resolved_func_name" (string)
        # arg1_expr (10) -> 10 (literal)
        # arg2_expr ("var_a") -> 20 (lookup)
        def eval_side_effect(node, e):
            if node == op_expr: return "resolved_func_name"
            if node == arg1_expr: return 10
            if node == arg2_expr: return e.lookup("var_a") # 20
            raise ValueError(f"Unexpected node for _eval mock: {node}")

        mock_internal_eval = mocker.patch.object(evaluator, '_eval', side_effect=eval_side_effect)
        
        # Mock _apply_operator
        mock_apply_op = mocker.patch.object(evaluator, '_apply_operator', return_value="apply_result")

        result = evaluator._eval_list_form(expr_list, env)

        assert result == "apply_result"
        
        # Check calls to _eval for operator resolution and argument evaluation
        assert mock_internal_eval.call_count == 3  # Called for op_expr, arg1_expr, and arg2_expr
        mock_internal_eval.assert_any_call(op_expr, env)
        mock_internal_eval.assert_any_call(arg1_expr, env)
        mock_internal_eval.assert_any_call(arg2_expr, env)
        
        # Check call to _apply_operator with evaluated args
        mock_apply_op.assert_called_once_with(
            "resolved_func_name",  # resolved_operator
            [10, 20],  # evaluated_args
            [arg1_expr, arg2_expr],  # original_arg_exprs
            env,
            original_expr_str
        )

    def test_apply_operator_dispatches_primitive(self, evaluator, mocker):
        env = SexpEnvironment()
        original_expr_str = "(list 1 2)"
        evaluated_args = [1, 2]  # Pre-evaluated argument values
        original_arg_exprs = [1, 2]  # Original expressions (same as evaluated in this simple case)

        mock_list_applier = mocker.patch.object(evaluator, '_apply_list_primitive', return_value="list_applied")
        evaluator.PRIMITIVE_APPLIERS['list'] = mock_list_applier # Ensure dispatcher uses mock

        result = evaluator._apply_operator("list", evaluated_args, original_arg_exprs, env, original_expr_str)
        
        assert result == "list_applied"
        # Primitive applier receives evaluated_args and original_arg_exprs
        mock_list_applier.assert_called_once_with(evaluated_args, original_arg_exprs, env, original_expr_str)
        evaluator.PRIMITIVE_APPLIERS['list'] = evaluator._apply_list_primitive # Restore

    def test_apply_operator_dispatches_task(self, evaluator, mock_task_system, mocker):
        env = SexpEnvironment()
        task_name = "my_atomic_task"
        original_expr_str = f"({task_name} (p 1))"
        evaluated_args = [1]  # Pre-evaluated argument values
        original_arg_exprs = [[Symbol("p"), 1]]  # Original unevaluated expressions

        mock_task_system.find_template.return_value = {"name": task_name, "type": "atomic"}
        mock_invoke_task = mocker.patch.object(evaluator, '_invoke_task_system', return_value=TaskResult(status="COMPLETE", content="task_done"))

        result = evaluator._apply_operator(task_name, evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result.content == "task_done"
        mock_task_system.find_template.assert_called_once_with(task_name)
        # Invoker receives evaluated_args and original_arg_exprs
        mock_invoke_task.assert_called_once_with(
            task_name, 
            {"name": task_name, "type": "atomic"}, 
            evaluated_args,
            original_arg_exprs, 
            env, 
            original_expr_str
        )

    def test_apply_operator_dispatches_tool(self, evaluator, mock_handler, mocker):
        env = SexpEnvironment()
        tool_name = "my_direct_tool"
        original_expr_str = f"({tool_name} (arg 'foo'))"
        evaluated_args = ["foo_value"]  # Pre-evaluated argument values
        original_arg_exprs = [[Symbol("arg"), Symbol("'foo")]]  # Original unevaluated expressions

        mock_handler.tool_executors = {tool_name: MagicMock()} # Tool must exist
        mock_invoke_tool = mocker.patch.object(evaluator, '_invoke_handler_tool', return_value=TaskResult(status="COMPLETE", content="tool_done"))

        result = evaluator._apply_operator(tool_name, evaluated_args, original_arg_exprs, env, original_expr_str)
        
        assert result.content == "tool_done"
        # Invoker receives evaluated_args and original_arg_exprs
        mock_invoke_tool.assert_called_once_with(tool_name, evaluated_args, original_arg_exprs, env, original_expr_str)

    def test_apply_operator_calls_python_callable(self, evaluator, mocker):
        env = SexpEnvironment()
        original_expr_str = "(py_func 10 (add x 5))"
        # Pre-evaluated argument values
        evaluated_args = [10, 7]  # These are already evaluated
        # Original unevaluated expressions (not used for callable)
        original_arg_exprs = [10, [Symbol("add"), Symbol("x"), 5]]
        
        # No need to mock _eval since it's not called by _apply_operator for callables anymore
        
        mock_callable = MagicMock(return_value="callable_result")
        
        result = evaluator._apply_operator(mock_callable, evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result == "callable_result"
        # Assert callable was called with *evaluated* args
        mock_callable.assert_called_once_with(10, 7)

    def test_apply_operator_error_unrecognized_name(self, evaluator):
        with pytest.raises(SexpEvaluationError, match="Unrecognized operator name: unknown_op"):
            evaluator._apply_operator("unknown_op", [], SexpEnvironment(), "(unknown_op)")

    def test_apply_operator_error_non_callable(self, evaluator):
        with pytest.raises(SexpEvaluationError, match="Cannot apply non-callable operator: 123"):
            evaluator._apply_operator(123, [], SexpEnvironment(), "(123)") # 123 is not a string name or callable

    # --- Tests for Special Form Handlers (Example: _eval_if_form) ---
    def test_eval_if_form_true_condition(self, evaluator, mocker):
        env = SexpEnvironment()
        original_expr_str = "(if cond_expr then_expr else_expr)"
        cond_expr, then_expr, else_expr = Symbol("cond"), "then_val", "else_val"
        arg_exprs = [cond_expr, then_expr, else_expr]

        # Mock _eval: cond_expr -> True, then_expr -> "THEN", else_expr -> "ELSE"
        def eval_side_effect(node, e):
            if node == cond_expr: return True
            if node == then_expr: return "THEN"
            if node == else_expr: return "ELSE"
            return mocker.DEFAULT # Should not be called for others
        
        mock_internal_eval = mocker.patch.object(evaluator, '_eval', side_effect=eval_side_effect)
        
        result = evaluator._eval_if_form(arg_exprs, env, original_expr_str)
        
        assert result == "THEN"
        mock_internal_eval.assert_any_call(cond_expr, env)
        mock_internal_eval.assert_any_call(then_expr, env)
        # Assert that else_expr was NOT evaluated
        for call_args in mock_internal_eval.call_args_list:
            assert call_args[0][0] != else_expr 

    def test_eval_if_form_false_condition(self, evaluator, mocker):
        env = SexpEnvironment()
        original_expr_str = "(if cond_expr then_expr else_expr)"
        cond_expr, then_expr, else_expr = Symbol("cond"), "then_val", "else_val"
        arg_exprs = [cond_expr, then_expr, else_expr]

        def eval_side_effect(node, e):
            if node == cond_expr: return False
            if node == then_expr: return "THEN"
            if node == else_expr: return "ELSE"
            return mocker.DEFAULT
        
        mock_internal_eval = mocker.patch.object(evaluator, '_eval', side_effect=eval_side_effect)
        
        result = evaluator._eval_if_form(arg_exprs, env, original_expr_str)
        
        assert result == "ELSE"
        mock_internal_eval.assert_any_call(cond_expr, env)
        mock_internal_eval.assert_any_call(else_expr, env)
        for call_args in mock_internal_eval.call_args_list:
            assert call_args[0][0] != then_expr

    def test_eval_if_form_arity_error(self, evaluator):
        with pytest.raises(SexpEvaluationError, match="'if' requires 3 arguments"):
            evaluator._eval_if_form([Symbol("true"), 1], SexpEnvironment(), "(if true 1)")
    
    # (Similar focused tests should be added for _eval_let_form, _eval_bind_form, etc.)

    # --- Tests for Primitive Appliers (Example: _apply_list_primitive) ---
    def test_apply_list_primitive_evaluates_args_and_returns_list(self, evaluator, mocker):
        env = SexpEnvironment()
        original_expr_str = "(list 10 (add 5 5))"
        # Unevaluated args for the primitive
        unevaluated_arg_exprs = [10, [Symbol("add"), 5, 5]] 

        # Mock _eval for argument evaluation phase within _apply_list_primitive
        # This mock will be called by _apply_list_primitive when it evaluates its arguments.
        def eval_side_effect_for_list_args(node, e_env):
            if node == 10: return 10
            if node == [Symbol("add"), 5, 5]: return 10 # Simulate (add 5 5) -> 10
            raise ValueError(f"Unexpected node for _eval mock in list primitive: {node}")
        
        mocker.patch.object(evaluator, '_eval', side_effect=eval_side_effect_for_list_args)
        
        result = evaluator._apply_list_primitive(unevaluated_arg_exprs, env, original_expr_str)
        
        assert result == [10, 10] # Expect evaluated arguments

    def test_apply_get_context_primitive_parses_and_calls_memory(self, evaluator, mock_memory_system, mocker):
        """Test the (get_context ...) primitive."""
        env = SexpEnvironment()
        original_expr_str = "(get_context (query \"search\") (matching_strategy content_var))"
        # Pre-evaluated argument values
        evaluated_args = ["evaluated_search_query", "content"]
        # Original (key value_expr) pairs
        original_arg_exprs = [
            [Symbol("query"), "search_query_str"],  # Original unevaluated expressions
            [Symbol("matching_strategy"), Symbol("content_var_name")]
        ]

        # No need to mock _eval since it's not called by _apply_get_context_primitive anymore

        expected_cg_input = ContextGenerationInput(query="evaluated_search_query", matching_strategy="content")
        mock_memory_system.get_relevant_context_for.return_value = AssociativeMatchResult(
            context_summary="ctx", matches=[MatchTuple(path="/f.py", relevance=0.9)]
        )

        result = evaluator._apply_get_context_primitive(evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result == ["/f.py"]
        mock_memory_system.get_relevant_context_for.assert_called_once_with(expected_cg_input)


    # --- Tests for Invocation Helpers (Example: _invoke_task_system) ---
    def test_invoke_task_system_parses_args_and_calls_task_system(self, evaluator, mock_task_system, mocker):
        env = SexpEnvironment()
        task_name = "my_task"
        template_def = {"name": task_name, "type": "atomic"}
        original_expr_str = f"({task_name} (param1 val1_expr) (files (list_files_func)))"
        
        # Pre-evaluated argument values
        evaluated_args = ["actual_val1", ["/a.txt", "/b.txt"]]
        
        # Original unevaluated arg expressions for the task (for key extraction)
        original_arg_exprs = [
            [Symbol("param1"), Symbol("val1_expr_node")], 
            [Symbol("files"), [Symbol("list_files_func")]]
        ]
        
        # No need to mock _eval since it's not called by _invoke_task_system anymore
        
        mock_task_system.execute_atomic_template.return_value = TaskResult(status="COMPLETE", content="task_res")
        
        result = evaluator._invoke_task_system(task_name, template_def, evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result.content == "task_res"
        
        mock_task_system.execute_atomic_template.assert_called_once()
        actual_request_arg = mock_task_system.execute_atomic_template.call_args[0][0]
        
        assert isinstance(actual_request_arg, SubtaskRequest)
        assert isinstance(actual_request_arg.task_id, str) and actual_request_arg.task_id
        assert actual_request_arg.type == "atomic"
        assert actual_request_arg.name == task_name
        assert actual_request_arg.inputs == {"param1": "actual_val1"}
        assert actual_request_arg.file_paths == ["/a.txt", "/b.txt"]
        assert actual_request_arg.context_management is None

    def test_invoke_handler_tool_parses_args_and_calls_handler(self, evaluator, mock_handler, mocker):
        env = SexpEnvironment()
        tool_name = "my_tool"
        original_expr_str = f"({tool_name} (arg1 123) (arg2 some_var))"
        
        # Pre-evaluated argument values
        evaluated_args = [123, "var_value"]
        
        # Original unevaluated arg expressions (for key extraction)
        original_arg_exprs = [
            [Symbol("arg1"), 123],
            [Symbol("arg2"), Symbol("some_var")]
        ]
        
        # No need to mock _eval since it's not called by _invoke_handler_tool anymore
        
        mock_handler._execute_tool.return_value = TaskResult(status="COMPLETE", content="tool_res")
        
        result = evaluator._invoke_handler_tool(tool_name, evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result.content == "tool_res"
        mock_handler._execute_tool.assert_called_once_with(tool_name, {"arg1": 123, "arg2": "var_value"})

    # --- Tests for _invoke_task_system and _invoke_handler_tool (formerly _parse_invocation_arguments tests) ---
    # These tests verify that the invocation helpers correctly parse and evaluate arguments.

    @pytest.mark.parametrize("helper_method_name, underlying_system_mock_name, target_name, template_def_if_task", [
        ("_invoke_task_system", "mock_task_system", "my_task", {"name": "my_task", "type": "atomic"}),
        ("_invoke_handler_tool", "mock_handler", "my_tool", None)
    ])
    def test_invocation_helper_full_args_parsing(
        self, evaluator, mocker, helper_method_name, underlying_system_mock_name, target_name, template_def_if_task
    ):
        """Test invocation helpers parse all argument types: named, files, context."""
        env = SexpEnvironment()
        original_expr_str = f"({target_name} (p1 v1_expr) (files files_expr) (context context_expr))"
        
        # Unevaluated argument expressions
        unevaluated_arg_exprs = [
            [Symbol("p1"), Symbol("v1_expr_node")],
            [Symbol("files"), Symbol("files_expr_node")],
            [Symbol("context"), Symbol("context_expr_node")]
        ]

        # Mock self._eval to control how value expressions are evaluated
        def eval_side_effect(node, e_env):
            if node == Symbol("v1_expr_node"): return "evaluated_v1"
            if node == Symbol("files_expr_node"): return ["/f1.txt", "/f2.txt"]
            if node == Symbol("context_expr_node"): return [[Symbol("inherit"), "none"], [Symbol("fresh"), "enabled"]] # Quoted list of pairs
            raise ValueError(f"Unexpected node for _eval mock: {node}")
        mocker.patch.object(evaluator, '_eval', side_effect=eval_side_effect)

        # Get the actual system mock (mock_task_system or mock_handler)
        system_mock = getattr(evaluator, underlying_system_mock_name.replace("mock_", "")) # e.g. evaluator.task_system

        if helper_method_name == "_invoke_task_system":
            mock_system_call = mocker.patch.object(system_mock, 'execute_atomic_template', return_value=TaskResult(status="COMPLETE"))
        else: # _invoke_handler_tool
            mock_system_call = mocker.patch.object(system_mock, '_execute_tool', return_value=TaskResult(status="COMPLETE"))
            # Ensure tool exists if it's a handler tool
            evaluator.handler.tool_executors[target_name] = MagicMock()


        helper_method_to_call = getattr(evaluator, helper_method_name)
        
        if helper_method_name == "_invoke_task_system":
            helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs, env, original_expr_str)
        else: # _invoke_handler_tool
            helper_method_to_call(target_name, unevaluated_arg_exprs, env, original_expr_str)

        mock_system_call.assert_called_once()
        
        if helper_method_name == "_invoke_task_system":
            request = mock_system_call.call_args[0][0]
            assert request.inputs == {"p1": "evaluated_v1"}
            assert request.file_paths == ["/f1.txt", "/f2.txt"]
            assert request.context_management == ContextManagement(inheritContext="none", freshContext="enabled")
        else: # _invoke_handler_tool
            called_tool_name, called_params = mock_system_call.call_args[0]
            assert called_tool_name == target_name
            # Handler tools get all args (files, context, etc.) as flat named_params
            assert called_params == {
                "p1": "evaluated_v1",
                "files": ["/f1.txt", "/f2.txt"],
                "context": {"inherit": "none", "fresh": "enabled"} # Context becomes dict for handler
            }

    @pytest.mark.parametrize("helper_method_name, underlying_system_mock_name, target_name, template_def_if_task", [
        ("_invoke_task_system", "mock_task_system", "task_only_named", {"name": "task_only_named", "type": "atomic"}),
        ("_invoke_handler_tool", "mock_handler", "tool_only_named", None)
    ])
    def test_invocation_helper_only_named_params(
        self, evaluator, mocker, helper_method_name, underlying_system_mock_name, target_name, template_def_if_task
    ):
        env = SexpEnvironment()
        original_expr_str = f"({target_name} (p1 v1_expr))"
        unevaluated_arg_exprs = [[Symbol("p1"), Symbol("v1_expr_node")]]

        mocker.patch.object(evaluator, '_eval', return_value="evaluated_v1") # Simple mock for all evals
        
        system_mock = getattr(evaluator, underlying_system_mock_name.replace("mock_", ""))
        if helper_method_name == "_invoke_task_system":
            mock_system_call = mocker.patch.object(system_mock, 'execute_atomic_template', return_value=TaskResult(status="COMPLETE"))
        else:
            mock_system_call = mocker.patch.object(system_mock, '_execute_tool', return_value=TaskResult(status="COMPLETE"))
            evaluator.handler.tool_executors[target_name] = MagicMock()

        helper_method_to_call = getattr(evaluator, helper_method_name)
        if helper_method_name == "_invoke_task_system":
            helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs, env, original_expr_str)
        else:
            helper_method_to_call(target_name, unevaluated_arg_exprs, env, original_expr_str)

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
        ("_invoke_handler_tool", "tool_bad_files", None) # Handler tools also parse files arg if present
    ])
    def test_invocation_helper_invalid_files_type(
        self, evaluator, mocker, helper_method_name, target_name, template_def_if_task
    ):
        env = SexpEnvironment()
        original_expr_str = f"({target_name} (files \"not-a-list\"))"
        unevaluated_arg_exprs = [[Symbol("files"), Symbol("str_node")]]
        
        mocker.patch.object(evaluator, '_eval', return_value="not-a-list") # _eval("str_node") -> "not-a-list"
        
        helper_method_to_call = getattr(evaluator, helper_method_name)
        
        expected_error_match = r"'files' argument .* must evaluate to a list of strings"
        with pytest.raises(SexpEvaluationError, match=expected_error_match):
            if helper_method_name == "_invoke_task_system":
                helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs, env, original_expr_str)
            else:
                 helper_method_to_call(target_name, unevaluated_arg_exprs, env, original_expr_str)


    @pytest.mark.parametrize("helper_method_name, target_name, template_def_if_task", [
        ("_invoke_task_system", "task_bad_context", {"name": "task_bad_context", "type": "atomic"}),
        ("_invoke_handler_tool", "tool_bad_context", None) # Handler tools also parse context arg
    ])
    def test_invocation_helper_invalid_context_type(
        self, evaluator, mocker, helper_method_name, target_name, template_def_if_task
    ):
        env = SexpEnvironment()
        original_expr_str = f"({target_name} (context \"not-a-dict-or-list\"))"
        unevaluated_arg_exprs = [[Symbol("context"), Symbol("str_node")]]
        
        mocker.patch.object(evaluator, '_eval', return_value="not-a-dict-or-list")
        
        helper_method_to_call = getattr(evaluator, helper_method_name)
        
        expected_error_match = r"'context' argument .* must evaluate to a dictionary or a list of pairs"
        with pytest.raises(SexpEvaluationError, match=expected_error_match):
            if helper_method_name == "_invoke_task_system":
                helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs, env, original_expr_str)
            else:
                helper_method_to_call(target_name, unevaluated_arg_exprs, env, original_expr_str)

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
        original_expr_str = f"({target_name} {invalid_arg_expr})" # Simplified original_expr_str for test
        unevaluated_arg_exprs = [invalid_arg_expr]
        
        # Mock _eval, though it might not be called if parsing fails early
        mocker.patch.object(evaluator, '_eval', return_value="dummy_eval_result")
        
        helper_method_to_call = getattr(evaluator, helper_method_name)
        
        with pytest.raises(SexpEvaluationError, match=err_match_detail):
            if helper_method_name == "_invoke_task_system":
                helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs, env, original_expr_str)
            else:
                helper_method_to_call(target_name, unevaluated_arg_exprs, env, original_expr_str)


# --- New Unit Tests for Refactored Internal Methods ---
        env = SexpEnvironment()
        original_expr_str = "(if cond_expr then_expr else_expr)"
        cond_expr, then_expr, else_expr = Symbol("cond"), "then_val", "else_val"
        arg_exprs = [cond_expr, then_expr, else_expr]

        # Mock _eval: cond_expr -> True, then_expr -> "THEN", else_expr -> "ELSE"
        def eval_side_effect(node, e):
            if node == cond_expr: return True
            if node == then_expr: return "THEN"
            if node == else_expr: return "ELSE"
            return mocker.DEFAULT # Should not be called for others
        
        mock_internal_eval = mocker.patch.object(evaluator, '_eval', side_effect=eval_side_effect)
        
        result = evaluator._eval_if_form(arg_exprs, env, original_expr_str)
        
        assert result == "THEN"
        mock_internal_eval.assert_any_call(cond_expr, env)
        mock_internal_eval.assert_any_call(then_expr, env)
        # Assert that else_expr was NOT evaluated
        for call_args in mock_internal_eval.call_args_list:
            assert call_args[0][0] != else_expr 

    def test_eval_if_form_false_condition(self, evaluator, mocker):
        env = SexpEnvironment()
        original_expr_str = "(if cond_expr then_expr else_expr)"
        cond_expr, then_expr, else_expr = Symbol("cond"), "then_val", "else_val"
        arg_exprs = [cond_expr, then_expr, else_expr]

        def eval_side_effect(node, e):
            if node == cond_expr: return False
            if node == then_expr: return "THEN"
            if node == else_expr: return "ELSE"
            return mocker.DEFAULT
        
        mock_internal_eval = mocker.patch.object(evaluator, '_eval', side_effect=eval_side_effect)
        
        result = evaluator._eval_if_form(arg_exprs, env, original_expr_str)
        
        assert result == "ELSE"
        mock_internal_eval.assert_any_call(cond_expr, env)
        mock_internal_eval.assert_any_call(else_expr, env)
        for call_args in mock_internal_eval.call_args_list:
            assert call_args[0][0] != then_expr

    def test_eval_if_form_arity_error(self, evaluator):
        with pytest.raises(SexpEvaluationError, match="'if' requires 3 arguments"):
            evaluator._eval_if_form([Symbol("true"), 1], SexpEnvironment(), "(if true 1)")
    
    # (Similar focused tests should be added for _eval_let_form, _eval_bind_form, etc.)

    # --- Tests for Primitive Appliers (Example: _apply_list_primitive) ---
    def test_apply_list_primitive_returns_evaluated_args(self, evaluator, mocker):
        # This test checks that _apply_list_primitive correctly returns the pre-evaluated args
        env = SexpEnvironment()
        original_expr_str = "(list 1 (add 1 1))"
        evaluated_args = [1, 2]  # These are already evaluated
        original_arg_exprs = [1, [Symbol("add"), 1, 1]]  # Original expressions (not used in this primitive)

        # No need to mock _eval since it's not called by _apply_list_primitive anymore
        
        result = evaluator._apply_list_primitive(evaluated_args, original_arg_exprs, env, original_expr_str)
        assert result == [1, 2]


    # (Tests for _apply_get_context_primitive would be more involved, mocking memory_system)
    # Example structure for _apply_get_context_primitive test:
    # test_apply_get_context_primitive_parses_and_calls_memory is already updated above.


    # --- Tests for Invocation Helpers (Example: _invoke_task_system) ---
    # test_invoke_task_system_parses_and_evals_args_and_calls is already updated above.
    # test_invoke_handler_tool_parses_and_evals_args_and_calls is already updated above.

    # --- Tests for _invoke_task_system and _invoke_handler_tool (formerly _parse_invocation_arguments tests) ---
    # These tests verify that the invocation helpers correctly parse and evaluate arguments.

    @pytest.mark.parametrize("helper_method_name, underlying_system_mock_name, target_name, template_def_if_task", [
        ("_invoke_task_system", "mock_task_system", "my_task", {"name": "my_task", "type": "atomic"}),
        ("_invoke_handler_tool", "mock_handler", "my_tool", None)
    ])
    def test_invocation_helper_full_args_parsing(
        self, evaluator, mocker, helper_method_name, underlying_system_mock_name, target_name, template_def_if_task
    ):
        """Test invocation helpers parse all argument types: named, files, context."""
        env = SexpEnvironment()
        original_expr_str = f"({target_name} (p1 v1_expr) (files files_expr) (context context_expr))"
        
        # Unevaluated argument expressions
        unevaluated_arg_exprs = [
            [Symbol("p1"), Symbol("v1_expr_node")],
            [Symbol("files"), Symbol("files_expr_node")],
            [Symbol("context"), Symbol("context_expr_node")]
        ]

        # Mock self._eval to control how value expressions are evaluated
        def eval_side_effect(node, e_env):
            if node == Symbol("v1_expr_node"): return "evaluated_v1"
            if node == Symbol("files_expr_node"): return ["/f1.txt", "/f2.txt"]
            if node == Symbol("context_expr_node"): return [[Symbol("inherit"), "none"], [Symbol("fresh"), "enabled"]] # Quoted list of pairs
            raise ValueError(f"Unexpected node for _eval mock: {node}")
        mocker.patch.object(evaluator, '_eval', side_effect=eval_side_effect)

        # Get the actual system mock (mock_task_system or mock_handler)
        system_mock = getattr(evaluator, underlying_system_mock_name.replace("mock_", "")) # e.g. evaluator.task_system

        if helper_method_name == "_invoke_task_system":
            mock_system_call = mocker.patch.object(system_mock, 'execute_atomic_template', return_value=TaskResult(status="COMPLETE"))
        else: # _invoke_handler_tool
            mock_system_call = mocker.patch.object(system_mock, '_execute_tool', return_value=TaskResult(status="COMPLETE"))
            # Ensure tool exists if it's a handler tool
            evaluator.handler.tool_executors[target_name] = MagicMock()


        helper_method_to_call = getattr(evaluator, helper_method_name)
        
        if helper_method_name == "_invoke_task_system":
            helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs, env, original_expr_str)
        else: # _invoke_handler_tool
            helper_method_to_call(target_name, unevaluated_arg_exprs, env, original_expr_str)

        mock_system_call.assert_called_once()
        
        if helper_method_name == "_invoke_task_system":
            request = mock_system_call.call_args[0][0]
            assert request.inputs == {"p1": "evaluated_v1"}
            assert request.file_paths == ["/f1.txt", "/f2.txt"]
            assert request.context_management == ContextManagement(inheritContext="none", freshContext="enabled")
        else: # _invoke_handler_tool
            called_tool_name, called_params = mock_system_call.call_args[0]
            assert called_tool_name == target_name
            # Handler tools get all args (files, context, etc.) as flat named_params
            assert called_params == {
                "p1": "evaluated_v1",
                "files": ["/f1.txt", "/f2.txt"],
                "context": {"inherit": "none", "fresh": "enabled"} # Context becomes dict for handler
            }

    @pytest.mark.parametrize("helper_method_name, underlying_system_mock_name, target_name, template_def_if_task", [
        ("_invoke_task_system", "mock_task_system", "task_only_named", {"name": "task_only_named", "type": "atomic"}),
        ("_invoke_handler_tool", "mock_handler", "tool_only_named", None)
    ])
    def test_invocation_helper_only_named_params(
        self, evaluator, mocker, helper_method_name, underlying_system_mock_name, target_name, template_def_if_task
    ):
        env = SexpEnvironment()
        original_expr_str = f"({target_name} (p1 v1_expr))"
        unevaluated_arg_exprs = [[Symbol("p1"), Symbol("v1_expr_node")]]

        mocker.patch.object(evaluator, '_eval', return_value="evaluated_v1") # Simple mock for all evals
        
        system_mock = getattr(evaluator, underlying_system_mock_name.replace("mock_", ""))
        if helper_method_name == "_invoke_task_system":
            mock_system_call = mocker.patch.object(system_mock, 'execute_atomic_template', return_value=TaskResult(status="COMPLETE"))
        else:
            mock_system_call = mocker.patch.object(system_mock, '_execute_tool', return_value=TaskResult(status="COMPLETE"))
            evaluator.handler.tool_executors[target_name] = MagicMock()

        helper_method_to_call = getattr(evaluator, helper_method_name)
        if helper_method_name == "_invoke_task_system":
            helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs, env, original_expr_str)
        else:
            helper_method_to_call(target_name, unevaluated_arg_exprs, env, original_expr_str)

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
        ("_invoke_handler_tool", "tool_bad_files", None) # Handler tools also parse files arg if present
    ])
    def test_invocation_helper_invalid_files_type(
        self, evaluator, mocker, helper_method_name, target_name, template_def_if_task
    ):
        env = SexpEnvironment()
        original_expr_str = f"({target_name} (files \"not-a-list\"))"
        unevaluated_arg_exprs = [[Symbol("files"), Symbol("str_node")]]
        
        mocker.patch.object(evaluator, '_eval', return_value="not-a-list") # _eval("str_node") -> "not-a-list"
        
        helper_method_to_call = getattr(evaluator, helper_method_name)
        
        expected_error_match = r"'files' argument .* must evaluate to a list of strings"
        with pytest.raises(SexpEvaluationError, match=expected_error_match):
            if helper_method_name == "_invoke_task_system":
                helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs, env, original_expr_str)
            else:
                 helper_method_to_call(target_name, unevaluated_arg_exprs, env, original_expr_str)


    @pytest.mark.parametrize("helper_method_name, target_name, template_def_if_task", [
        ("_invoke_task_system", "task_bad_context", {"name": "task_bad_context", "type": "atomic"}),
        ("_invoke_handler_tool", "tool_bad_context", None) # Handler tools also parse context arg
    ])
    def test_invocation_helper_invalid_context_type(
        self, evaluator, mocker, helper_method_name, target_name, template_def_if_task
    ):
        env = SexpEnvironment()
        original_expr_str = f"({target_name} (context \"not-a-dict-or-list\"))"
        unevaluated_arg_exprs = [[Symbol("context"), Symbol("str_node")]]
        
        mocker.patch.object(evaluator, '_eval', return_value="not-a-dict-or-list")
        
        helper_method_to_call = getattr(evaluator, helper_method_name)
        
        expected_error_match = r"'context' argument .* must evaluate to a dictionary or a list of pairs"
        with pytest.raises(SexpEvaluationError, match=expected_error_match):
            if helper_method_name == "_invoke_task_system":
                helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs, env, original_expr_str)
            else:
                helper_method_to_call(target_name, unevaluated_arg_exprs, env, original_expr_str)

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
        original_expr_str = f"({target_name} {invalid_arg_expr})" # Simplified original_expr_str for test
        unevaluated_arg_exprs = [invalid_arg_expr]
        
        # Mock _eval, though it might not be called if parsing fails early
        mocker.patch.object(evaluator, '_eval', return_value="dummy_eval_result")
        
        helper_method_to_call = getattr(evaluator, helper_method_name)
        
        with pytest.raises(SexpEvaluationError, match=err_match_detail):
            if helper_method_name == "_invoke_task_system":
                helper_method_to_call(target_name, template_def_if_task, unevaluated_arg_exprs, env, original_expr_str)
            else:
                helper_method_to_call(target_name, unevaluated_arg_exprs, env, original_expr_str)


# --- New Unit Tests for Refactored Internal Methods ---

class TestSexpEvaluatorInternals:

    def test_eval_list_form_dispatches_special_form(self, evaluator, mocker):
        """Test _eval_list_form correctly dispatches to a special form handler."""
        env = SexpEnvironment()
        # original_expr_str = "(if true 1 0)" # Original string form
        original_expr_str_expected = "[Symbol('if'), Symbol('true'), 1, 0]" # str() of AST list
        arg_exprs = [Symbol("true"), 1, 0] # Unevaluated args for 'if'

        # Mock the specific special form handler (e.g., _eval_if_form)
        # The handler itself is an instance method, so it's already part of 'evaluator'
        # We need to patch it on the 'evaluator' instance or its class.
        mock_if_handler = mocker.patch.object(evaluator, '_eval_if_form', return_value="if_result")
        
        # Make SPECIAL_FORM_HANDLERS point to this mock for 'if'
        evaluator.SPECIAL_FORM_HANDLERS['if'] = mock_if_handler

        # AST for (if true 1 0)
        expr_list = [Symbol("if"), Symbol("true"), 1, 0]
        
        result = evaluator._eval_list_form(expr_list, env)

        assert result == "if_result"
        mock_if_handler.assert_called_once_with(arg_exprs, env, original_expr_str_expected)
        # Restore original handler if necessary for other tests, or use fresh evaluator
        evaluator.SPECIAL_FORM_HANDLERS['if'] = evaluator._eval_if_form

# --- Tests for Lambda and Closures ---

# Import Closure class for isinstance checks if it's accessible
# If not, tests will rely on attribute checking (duck typing)
try:
    from src.sexp_evaluator.sexp_evaluator import Closure
    CLOSURE_CLASS_AVAILABLE = True
except ImportError:
    CLOSURE_CLASS_AVAILABLE = False
    Closure = None # Placeholder if not importable

class TestSexpEvaluatorLambdaClosures:

    def test_lambda_definition_creates_closure(self, evaluator, mock_parser):
        """Test that (lambda (params) body) evaluates to a Closure object."""
        sexp_str = "(lambda (x) (+ x 1))"
        # AST for (lambda (x) (+ x 1))
        params_ast = [S('x')]
        body_expr_ast = [S('+'), S('x'), 1] # The single body expression
        
        # The SexpEvaluator's _eval for lambda expects node[2:] to be a list of body expressions.
        # So, if the body is just one expression like (+ x 1), lambda_body_ast will be [[S('+'), S('x'), 1]]
        # However, the Closure object itself stores node[2:] as self.body_ast.
        # If the parser returns (lambda (x) (+ x 1)) as [S('lambda'), [S('x')], [S('+'), S('x'), 1]],
        # then lambda_body_ast in _eval becomes [[S('+'), S('x'), 1]].
        # Let's assume the parser returns the body expression directly if it's singular,
        # and the _eval logic wraps it in a list if needed.
        # The provided plan for _eval for lambda: lambda_body_ast = node[2:]
        # If node = [S('lambda'), params_list_node, body_expr_1, body_expr_2, ...]
        # then lambda_body_ast = [body_expr_1, body_expr_2, ...]
        # So, for (lambda (x) (+ x 1)), AST is [S('lambda'), [S('x')], [S('+'), S('x'), 1]]
        # params_list_node = [S('x')]
        # lambda_body_ast = [[S('+'), S('x'), 1]]
        
        lambda_ast = [S('lambda'), params_ast, body_expr_ast] # Parser returns this
        
        mock_parser.parse_string.return_value = lambda_ast
        
        def_env = SexpEnvironment(parent=None)
        result = evaluator.evaluate_string(sexp_str, initial_env=def_env)

        assert hasattr(result, 'params_ast'), "Result missing 'params_ast'"
        assert hasattr(result, 'body_ast'), "Result missing 'body_ast'"
        assert hasattr(result, 'definition_env'), "Result missing 'definition_env'"
        
        if CLOSURE_CLASS_AVAILABLE:
            assert isinstance(result, Closure), f"Result is not a Closure object, got {type(result)}"

        assert result.params_ast == params_ast, "Closure params mismatch"
        # body_ast in Closure should be a list of body expressions.
        # Since lambda_body_ast = node[2:], and node[2] was body_expr_ast,
        # result.body_ast should be [body_expr_ast]
        assert result.body_ast == [body_expr_ast], "Closure body mismatch"
        assert result.definition_env is def_env, "Closure definition environment mismatch"
        mock_parser.parse_string.assert_called_once_with(sexp_str)

    def test_lambda_application_basic(self, evaluator, mock_parser):
        """Test basic application of a lambda-defined closure."""
        # Sexp: ((lambda (x) (+ x 10)) 5)
        sexp_str = "((lambda (x) (+ x 10)) 5)"

        # AST for the whole expression:
        # [[S('lambda'), [S('x')], [S('+'), S('x'), 10]], 5]
        lambda_params_ast = [S('x')]
        lambda_body_expr_ast = [S('+'), S('x'), 10]
        lambda_expr_ast = [S('lambda'), lambda_params_ast, lambda_body_expr_ast]
        
        application_ast = [lambda_expr_ast, 5]
        mock_parser.parse_string.return_value = application_ast

        # Mock the evaluation of '+' primitive if not fully implemented/tested elsewhere
        # For this test, assume '+' works or mock its behavior within _eval if needed.
        # We'll rely on the _apply_operator logic for Python callables if '+' is a Python func.
        # Or, if '+' is a primitive, its applier will be called.
        # Let's assume '+' is a primitive that evaluates its args and sums them.
        
        # To make '+' work, we can define it in the environment or mock _eval for it.
        # Simpler: Assume '+' is a known primitive that SexpEvaluator handles.
        # We need to ensure the SexpEvaluator's _eval can handle the `+` operation.
        # For simplicity in this test, let's mock the behavior of `_eval` for the `+` call.
        
        original_eval = evaluator._eval
        def eval_side_effect(node, env):
            if node == lambda_body_expr_ast and env.lookup('x') == 5: # Inside closure body
                 # Simulate evaluation of (+ x 10) where x is 5
                 # This part assumes '+' itself is handled correctly by a deeper _eval or primitive
                 # For this specific test, we can directly return the expected result of the body
                 return 15 
            return original_eval(node, env)

        with patch.object(evaluator, '_eval', side_effect=eval_side_effect) as mock_internal_eval:
            result = evaluator.evaluate_string(sexp_str)
            assert result == 15

            # Check that the lambda expression itself was evaluated to create a Closure
            # This call happens when `_eval(lambda_expr_ast, env)` is invoked by `_eval_list_form`
            # for the operator part of `application_ast`.
            assert any(call_args[0] == lambda_expr_ast for call_args, _ in mock_internal_eval.call_args_list), \
                "Lambda expression was not evaluated."

            # Check that the argument '5' was evaluated.
            assert any(call_args[0] == 5 for call_args, _ in mock_internal_eval.call_args_list), \
                "Argument '5' was not evaluated."

            # Check that the body of the closure was evaluated with x=5 in its environment
            # This is implicitly checked by `eval_side_effect` returning 15.
            # We can be more explicit by checking the call to _eval for the body:
            body_eval_call_found = False
            for call_args_tuple in mock_internal_eval.call_args_list:
                node_arg, env_arg = call_args_tuple[0] # call_args is a tuple: ((node, env), kwargs)
                if node_arg == lambda_body_expr_ast:
                    try:
                        if env_arg.lookup('x') == 5: # Check if 'x' is 5 in the call_frame_env
                            body_eval_call_found = True
                            break
                    except NameError:
                        pass # 'x' not in this env
            assert body_eval_call_found, "Closure body was not evaluated with correct parameter binding."


    def test_lambda_lexical_scope_capture(self, evaluator, mock_parser):
        """Test that closures capture their definition environment (lexical scope)."""
        # Sexp: (let ((y 10)) ((lambda (x) (+ x y)) 5))
        # The 'y' inside the lambda should refer to the 'y' from the 'let' scope.
        sexp_str = "(let ((y 10)) ((lambda (x) (+ x y)) 5))"

        y_sym = S('y')
        x_sym = S('x')
        plus_sym = S('+')
        lambda_sym = S('lambda')
        let_sym = S('let')

        # AST for ((lambda (x) (+ x y)) 5)
        lambda_expr_ast = [lambda_sym, [x_sym], [plus_sym, x_sym, y_sym]]
        application_inner_ast = [lambda_expr_ast, 5]
        
        # AST for (let ((y 10)) ...)
        let_ast = [let_sym, [[y_sym, 10]], application_inner_ast]
        mock_parser.parse_string.return_value = let_ast

        # Mock the evaluation of '+' primitive/callable
        original_eval = evaluator._eval
        def eval_side_effect(node, env):
            # This will be called for various parts. We're interested in the body of the lambda.
            # Body: [S('+'), S('x'), S('y')]
            # When body is evaluated, x should be 5 (from arg), y should be 10 (from captured def_env)
            if node == [plus_sym, x_sym, y_sym]:
                val_x = env.lookup(x_sym.value())
                val_y = env.lookup(y_sym.value())
                if val_x == 5 and val_y == 10:
                    return 15 # 5 + 10
            return original_eval(node, env)

        with patch.object(evaluator, '_eval', side_effect=eval_side_effect):
            result = evaluator.evaluate_string(sexp_str)
            assert result == 15

    def test_lambda_higher_order_function_create(self, evaluator, mock_parser):
        """Test creating a function that returns another function (closure)."""
        # Sexp: (let ((adder (lambda (n) (lambda (x) (+ n x))))) ((adder 10) 5))
        # (adder 10) should return a closure equivalent to (lambda (x) (+ 10 x))
        # Then ((lambda (x) (+ 10 x)) 5) should be 15.
        sexp_str = "(let ((adder (lambda (n) (lambda (x) (+ n x))))) ((adder 10) 5))"
        
        adder_sym, n_sym, x_sym, plus_sym, lambda_sym, let_sym = \
            S('adder'), S('n'), S('x'), S('+'), S('lambda'), S('let')

        # Inner lambda: (lambda (x) (+ n x))
        inner_lambda_ast = [lambda_sym, [x_sym], [plus_sym, n_sym, x_sym]]
        # Outer lambda: (lambda (n) <inner_lambda_ast>)
        outer_lambda_ast = [lambda_sym, [n_sym], inner_lambda_ast]
        
        # Application: ((adder 10) 5)
        # AST for (adder 10)
        adder_call_ast = [adder_sym, 10]
        # AST for (<result of (adder 10)> 5)
        full_application_ast = [adder_call_ast, 5]
        
        # Let expression
        let_ast = [let_sym, [[adder_sym, outer_lambda_ast]], full_application_ast]
        mock_parser.parse_string.return_value = let_ast

        # Mock '+' evaluation
        original_eval = evaluator._eval
        def eval_side_effect(node, env):
            # For the body of the inner lambda: (+ n x)
            if node == [plus_sym, n_sym, x_sym]:
                val_n = env.lookup(n_sym.value()) # Should be 10 (captured by outer, passed to inner)
                val_x = env.lookup(x_sym.value()) # Should be 5 (arg to inner lambda)
                if val_n == 10 and val_x == 5:
                    return 15
            return original_eval(node, env)

        with patch.object(evaluator, '_eval', side_effect=eval_side_effect):
            result = evaluator.evaluate_string(sexp_str)
            assert result == 15

    def test_lambda_arity_mismatch_too_few_args(self, evaluator, mock_parser):
        """Test error when a closure is called with too few arguments."""
        sexp_str = "((lambda (a b) (+ a b)) 1)" # Expects 2, gets 1
        
        lambda_expr_ast = [S('lambda'), [S('a'), S('b')], [S('+'), S('a'), S('b')]]
        application_ast = [lambda_expr_ast, 1]
        mock_parser.parse_string.return_value = application_ast
        
        with pytest.raises(SexpEvaluationError, match="Arity mismatch: Closure expects 2 arguments, got 1"):
            evaluator.evaluate_string(sexp_str)

    def test_lambda_arity_mismatch_too_many_args(self, evaluator, mock_parser):
        """Test error when a closure is called with too many arguments."""
        sexp_str = "((lambda (a) a) 1 2)" # Expects 1, gets 2
        
        lambda_expr_ast = [S('lambda'), [S('a')], S('a')]
        application_ast = [lambda_expr_ast, 1, 2]
        mock_parser.parse_string.return_value = application_ast
        
        with pytest.raises(SexpEvaluationError, match="Arity mismatch: Closure expects 1 arguments, got 2"):
            evaluator.evaluate_string(sexp_str)

    def test_lambda_definition_invalid_param_list_not_list(self, evaluator, mock_parser):
        """Test error if lambda parameter definition is not a list."""
        sexp_str = "(lambda x x)" # Params 'x' is not a list (x)
        mock_parser.parse_string.return_value = [S('lambda'), S('x'), S('x')]
        with pytest.raises(SexpEvaluationError, match="Lambda parameter definition must be a list of symbols."):
            evaluator.evaluate_string(sexp_str)

    def test_lambda_definition_invalid_param_not_symbol(self, evaluator, mock_parser):
        """Test error if a lambda parameter is not a symbol."""
        sexp_str = "(lambda (1) 1)" # Param '1' is not a symbol
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
        # New S-expression:
        # (let ((fact-body (lambda (self n)
        #                    (if (= n 0)
        #                        1
        #                        (* n (self self (- n 1)))))))
        #   (fact-body fact-body 3))
        sexp_str = "(let ((fact-body (lambda (self n) (if (= n 0) 1 (* n (self self (- n 1))))))) (fact-body fact-body 3))"
        
        fact_body_s, self_s, n_s, if_s, eq_s, mul_s, sub_s = \
            S('fact-body'), S('self'), S('n'), S('if'), S('='), S('*'), S('-')
        lambda_s, let_s = S('lambda'), S('let')

        # Body of lambda: (if (= n 0) 1 (* n (self self (- n 1))))
        recursive_call_ast = [self_s, self_s, [sub_s, n_s, 1]] # (self self (- n 1))
        if_body_ast = [if_s, [eq_s, n_s, 0], 1, [mul_s, n_s, recursive_call_ast]]

        # Lambda for fact-body: (lambda (self n) <if_body_ast>)
        fact_lambda_ast = [lambda_s, [self_s, n_s], if_body_ast] # Parameters are (self n)

        # Let expr: (let ((fact-body <fact_lambda_ast>)) (fact-body fact-body 3))
        let_binding_ast = [[fact_body_s, fact_lambda_ast]]
        final_call_ast = [fact_body_s, fact_body_s, 3] # Call is (fact-body fact-body 3)
        full_ast = [let_s, let_binding_ast, final_call_ast]
        
        mock_parser.parse_string.return_value = full_ast

        original_eval = evaluator._eval
        memo_eval_calls = [] # Keep for debugging if needed

        def eval_side_effect(node, env):
            memo_eval_calls.append((node, id(env))) # Keep for debugging

            # Simulate primitive operations within the lambda's body
            if isinstance(node, list) and len(node) > 0:
                op_sym_node = node[0]
                # Ensure op_sym_node is a Symbol before calling .value()
                if isinstance(op_sym_node, Symbol):
                    op_name = op_sym_node.value()

                    if op_name == '=': # (= n 0)
                        # Args are node[1] (n_s) and node[2] (0)
                        # These args themselves need to be evaluated by the mock if they are symbols
                        val_n = eval_side_effect(node[1], env) # Evaluate n
                        val_0 = eval_side_effect(node[2], env) # Evaluate 0
                        return val_n == val_0
                    
                    if op_name == '-': # (- n 1)
                        val_n = eval_side_effect(node[1], env) # Evaluate n
                        val_1 = eval_side_effect(node[2], env) # Evaluate 1
                        return val_n - val_1
                    
                    if op_name == '*': # (* n <recursive_call_result>)
                        val_n = eval_side_effect(node[1], env) # Evaluate n
                        # node[2] will be the recursive call `(self self (- n 1))`
                        # The SexpEvaluator's main _eval and _apply_operator should handle this call.
                        # eval_side_effect will be called again for the parts of this recursive call.
                        # So, we just need to evaluate node[2] using the mock to continue the chain.
                        val_rec_result = eval_side_effect(node[2], env)
                        return val_n * val_rec_result
            
            # For any other node (including symbols like 'n', 'self', or the recursive call list itself),
            # fall back to the original _eval. The original _eval will handle:
            # - Symbol lookup (e.g., looking up 'n', 'self')
            # - Closure creation for the lambda
            # - Closure application for (self self ...) and (fact-body fact-body ...)
            return original_eval(node, env)

        with patch.object(evaluator, '_eval', side_effect=eval_side_effect):
            result = evaluator.evaluate_string(sexp_str)
            assert result == 6 # 3 * 2 * 1

    def test_closure_retains_definition_env_even_if_outer_var_is_rebound(self, evaluator, mock_parser):
        """Test that a closure uses its definition-time environment, not the call-time one
           if an outer variable it captured is later rebound in the scope from which the
           closure was *returned* but before the closure is *called*.
        """
        # Sexp:
        # (let ((outer-val 10))
        #   (let ((my-closure (lambda () outer-val))) ; Closure captures outer-val=10
        #     (bind outer-val 20)                     ; Rebind outer-val in the middle scope
        #     (my-closure)))                          ; Call closure. Should still see outer-val=10
        
        sexp_str = "(let ((outer-val 10)) (let ((my-closure (lambda () outer-val))) (bind outer-val 20) (my-closure)))"

        let_s, lambda_s, bind_s = S('let'), S('lambda'), S('bind')
        outer_val_s, my_closure_s = S('outer-val'), S('my-closure')

        # (lambda () outer-val)
        closure_def_ast = [lambda_s, [], outer_val_s]
        # (my-closure)
        closure_call_ast = [my_closure_s]
        # (bind outer-val 20)
        rebind_ast = [bind_s, outer_val_s, 20]

        # Inner let: (let ((my-closure ...)) (bind ...) (my-closure))
        inner_let_bindings = [[my_closure_s, closure_def_ast]]
        inner_let_body = [rebind_ast, closure_call_ast] # progn is implicit for multiple body exprs in let
        inner_let_ast = [let_s, inner_let_bindings] + inner_let_body # Corrected: body exprs are separate args

        # Outer let: (let ((outer-val 10)) <inner_let_ast>)
        outer_let_bindings = [[outer_val_s, 10]]
        full_ast = [let_s, outer_let_bindings, inner_let_ast]
        
        mock_parser.parse_string.return_value = full_ast
        
        # No special eval mocking needed, rely on correct env behavior
        result = evaluator.evaluate_string(sexp_str)
        assert result == 10

    def test_closure_returned_from_function_retains_lexical_scope(self, evaluator, mock_parser):
        """
        Test that closures created by a 'maker' function at different times
        with different captured values maintain their distinct lexical environments.
        """
        sexp_str = """
        (let ((maker (lambda (captured_val) 
                       (lambda () captured_val)))) ; maker returns a closure that captures 'captured_val'
          (let ((closure_A (maker 100))
                (closure_B (maker 200)))
            (list (closure_A) (closure_B))))
        """
        
        let_s, lambda_s, list_s = S('let'), S('lambda'), S('list')
        maker_s, captured_val_s = S('maker'), S('captured_val')
        closure_A_s, closure_B_s = S('closure_A'), S('closure_B')

        # Inner lambda for returned closure: (lambda () captured_val)
        returned_closure_body_ast = captured_val_s
        returned_closure_ast = [lambda_s, [], returned_closure_body_ast]

        # Maker lambda: (lambda (captured_val) <returned_closure_ast>)
        maker_lambda_ast = [lambda_s, [captured_val_s], returned_closure_ast]

        # (maker 100)
        maker_call_A_ast = [maker_s, 100]
        # (maker 200)
        maker_call_B_ast = [maker_s, 200]

        # (closure_A)
        closure_A_call_ast = [closure_A_s]
        # (closure_B)
        closure_B_call_ast = [closure_B_s]
        
        # (list (closure_A) (closure_B))
        list_call_ast = [list_s, closure_A_call_ast, closure_B_call_ast]

        # Inner let: (let ((closure_A (maker 100)) (closure_B (maker 200))) <list_call_ast>)
        inner_let_bindings = [[closure_A_s, maker_call_A_ast], [closure_B_s, maker_call_B_ast]]
        inner_let_ast = [let_s, inner_let_bindings, list_call_ast]
        
        # Outer let: (let ((maker <maker_lambda_ast>)) <inner_let_ast>)
        outer_let_bindings = [[maker_s, maker_lambda_ast]]
        full_ast = [let_s, outer_let_bindings, inner_let_ast]

        mock_parser.parse_string.return_value = full_ast
        
        # No special eval mocking needed, rely on correct env, lambda, and list primitive behavior
        result = evaluator.evaluate_string(sexp_str)
        assert result == [100, 200]
