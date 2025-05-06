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

    with pytest.raises(SexpEvaluationError, match="Context retrieval failed (MemorySystem error).") as excinfo:
        evaluator.evaluate_string(sexp_str)
    assert "Database connection failed" in excinfo.value.error_details


def test_eval_primitive_get_context_with_content_strategy(evaluator, mock_parser, mock_memory_system):
    """Test get_context with explicit content strategy."""
    get_context_sym = Symbol("get_context")
    query_sym = Symbol("query")
    strategy_sym = Symbol("matching_strategy")
    content_sym = Symbol("content") 

    sexp_str = "(get_context (query \"q\") (matching_strategy content))" # Use symbol 'content'
    # AST: [get_context, [query, "q"], [matching_strategy, content_symbol]]
    ast = [
        get_context_sym,
        [query_sym, "q"],
        [strategy_sym, content_sym] 
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
    metadata_sym = Symbol("metadata")

    sexp_str = "(get_context (query \"q\") (matching_strategy metadata))" # Use symbol 'metadata'
    ast = [
        get_context_sym,
        [query_sym, "q"],
        [strategy_sym, metadata_sym]
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
    with pytest.raises(SexpEvaluationError, match="Error evaluating loop count expression: Unbound symbol: 'undefined'"):
        evaluator.evaluate_string(sexp_str)

def test_eval_special_form_loop_error_count_not_integer(evaluator, mock_parser):
    """Test loop fails if count evaluates to non-integer."""
    sexp_str_str = "(loop \"two\" (body))"
    ast_str = [S('loop'), "two", [S('body')]]
    mock_parser.parse_string.return_value = ast_str
    with pytest.raises(SexpEvaluationError, match="Loop count must evaluate to an integer"):
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

    with patch.object(evaluator, '_eval', side_effect=eval_side_effect):
        with pytest.raises(SexpEvaluationError, match="Loop count must evaluate to an integer"):
            evaluator.evaluate_string(sexp_str_list)

def test_eval_special_form_loop_error_count_negative(evaluator, mock_parser):
    """Test loop fails if count evaluates to negative integer."""
    sexp_str = "(loop -2 (body))"
    ast = [S('loop'), -2, [S('body')]]
    mock_parser.parse_string.return_value = ast

    with pytest.raises(SexpEvaluationError, match="Loop count must be non-negative"):
        evaluator.evaluate_string(sexp_str)

def test_eval_special_form_loop_error_body_eval_fails(evaluator, mock_parser, mock_handler):
    """Test loop fails if body evaluation errors during iteration."""
    sexp_str = "(loop 3 (progn (mock_ok) (fail_sometimes)))"
    # AST: ['loop', 3, ['progn', ['mock_ok'], ['fail_sometimes']]]
    ast = [S('loop'), 3, [S('progn'), [S('mock_ok')], [S('fail_sometimes')]]]
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
    fail_error = SexpEvaluationError("Intentional body failure")
    call_count = 0
    def fail_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise fail_error
        return TaskResult(status="COMPLETE", content="OK") # Simulate success on other calls

    mock_fail_executor.side_effect = fail_side_effect

    # No need to patch _eval directly if the tool executor raises the error
    with pytest.raises(SexpEvaluationError, match="Error during loop iteration 2/3: Intentional body failure"):
        evaluator.evaluate_string(sexp_str)

    # Verify mock_ok was called twice (once in iteration 1 and once in iteration 2 before failure)
    assert mock_ok_executor.call_count == 2
    # Verify fail_sometimes was called twice (failed on the second)
    assert mock_fail_executor.call_count == 2


# --- New Unit Tests for Refactored Internal Methods ---

class TestSexpEvaluatorInternals:

    def test_eval_list_form_dispatches_special_form(self, evaluator, mock_parser, mocker):
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
        
        # Check calls to _eval
        # Call 1: op_expr
        # Call 2: arg1_expr
        # Call 3: arg2_expr
        assert mock_internal_eval.call_count == 3 
        mock_internal_eval.assert_any_call(op_expr, env)
        mock_internal_eval.assert_any_call(arg1_expr, env)
        mock_internal_eval.assert_any_call(arg2_expr, env)
        
        # Check call to _apply_operator
        resolved_operator_expected = "resolved_func_name"
        evaluated_args_expected = [10, 20]
        original_arg_exprs_expected = [arg1_expr, arg2_expr]
        mock_apply_op.assert_called_once_with(
            resolved_operator_expected,
            evaluated_args_expected,
            original_arg_exprs_expected,
            env,
            original_expr_str
        )

    def test_apply_operator_dispatches_primitive(self, evaluator, mocker):
        env = SexpEnvironment()
        original_expr_str = "(list 1 2)"
        evaluated_args = [1, 2]
        original_arg_exprs = [1, 2] # For 'list', these happen to be the same as evaluated

        mock_list_applier = mocker.patch.object(evaluator, '_apply_list_primitive', return_value="list_applied")
        evaluator.PRIMITIVE_APPLIERS['list'] = mock_list_applier # Ensure dispatcher uses mock

        result = evaluator._apply_operator("list", evaluated_args, original_arg_exprs, env, original_expr_str)
        
        assert result == "list_applied"
        mock_list_applier.assert_called_once_with(evaluated_args, original_arg_exprs, env, original_expr_str)
        evaluator.PRIMITIVE_APPLIERS['list'] = evaluator._apply_list_primitive # Restore

    def test_apply_operator_dispatches_task(self, evaluator, mock_task_system, mocker):
        env = SexpEnvironment()
        task_name = "my_atomic_task"
        original_expr_str = f"({task_name} (p 1))"
        evaluated_args = [1] # e.g., (p 1) -> p's value is 1
        original_arg_exprs = [[Symbol("p"), 1]] # e.g. (p 1)

        mock_task_system.find_template.return_value = {"name": task_name, "type": "atomic"}
        mock_invoke_task = mocker.patch.object(evaluator, '_invoke_task_system', return_value=TaskResult(status="COMPLETE", content="task_done"))

        result = evaluator._apply_operator(task_name, evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result.content == "task_done"
        mock_task_system.find_template.assert_called_once_with(task_name)
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
        evaluated_args = ["foo"]
        original_arg_exprs = [[Symbol("arg"), Symbol("'foo")]] # Example original structure

        mock_handler.tool_executors = {tool_name: MagicMock()} # Tool must exist
        mock_invoke_tool = mocker.patch.object(evaluator, '_invoke_handler_tool', return_value=TaskResult(status="COMPLETE", content="tool_done"))

        result = evaluator._apply_operator(tool_name, evaluated_args, original_arg_exprs, env, original_expr_str)
        
        assert result.content == "tool_done"
        mock_invoke_tool.assert_called_once_with(tool_name, evaluated_args, original_arg_exprs, env, original_expr_str)

    def test_apply_operator_calls_python_callable(self, evaluator, mocker):
        env = SexpEnvironment()
        original_expr_str = "(py_func 10)"
        evaluated_args = [10]
        original_arg_exprs = [10]

        mock_callable = MagicMock(return_value="callable_result")
        
        result = evaluator._apply_operator(mock_callable, evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result == "callable_result"
        mock_callable.assert_called_once_with(*evaluated_args)

    def test_apply_operator_error_unrecognized_name(self, evaluator):
        with pytest.raises(SexpEvaluationError, match="Unrecognized operator name: unknown_op"):
            evaluator._apply_operator("unknown_op", [], [], SexpEnvironment(), "(unknown_op)")

    def test_apply_operator_error_non_callable(self, evaluator):
        with pytest.raises(SexpEvaluationError, match="Cannot apply non-callable operator: 123"):
            evaluator._apply_operator(123, [], [], SexpEnvironment(), "(123)") # 123 is not a string name or callable

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
    def test_apply_list_primitive_returns_evaluated_args(self, evaluator):
        evaluated_args = [1, "two", True]
        result = evaluator._apply_list_primitive(evaluated_args, [], SexpEnvironment(), "(list ...)")
        assert result == evaluated_args
        assert result is evaluated_args # Should be the same list object

    # (Tests for _apply_get_context_primitive would be more involved, mocking memory_system)
    # Example structure for _apply_get_context_primitive test:
    def test_apply_get_context_primitive_parses_and_calls_memory(self, evaluator, mock_memory_system, mocker):
        env = SexpEnvironment()
        original_expr_str = "(get_context (query \"search\") (matching_strategy content))"
        # original_arg_exprs are the unevaluated (key value_expr) pairs
        original_arg_exprs = [
            [Symbol("query"), "search"], 
            [Symbol("matching_strategy"), Symbol("content")]
        ]
        # evaluated_args are the results of _eval on each value_expr
        evaluated_args = ["search", "content"] # "content" symbol evaluates to "content" string

        expected_cg_input = ContextGenerationInput(query="search", matching_strategy="content")
        mock_memory_system.get_relevant_context_for.return_value = AssociativeMatchResult(
            context_summary="ctx", matches=[MatchTuple(path="/f.py", relevance=0.9)]
        )

        result = evaluator._apply_get_context_primitive(evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result == ["/f.py"]
        mock_memory_system.get_relevant_context_for.assert_called_once_with(expected_cg_input)


    # --- Tests for Invocation Helpers (Example: _invoke_task_system) ---
    def test_invoke_task_system_parses_args_and_calls(self, evaluator, mock_task_system, mocker):
        env = SexpEnvironment()
        task_name = "my_task"
        template_def = {"name": task_name, "type": "atomic"}
        original_expr_str = f"({task_name} (param1 val1_eval) (files (list \"/a.txt\")))"
        
        # original_arg_exprs: [(param1 val1_expr_node), (files (list "/a.txt"))]
        original_arg_exprs = [
            [Symbol("param1"), Symbol("val1_expr_node")], # val1_expr_node would be some AST
            [Symbol("files"), [Symbol("list"), "/a.txt"]]
        ]
        # evaluated_args: [result_of_eval_val1_expr_node, result_of_eval_(list "/a.txt")]
        evaluated_args = ["actual_val1", ["/a.txt"]]


        mock_task_system.execute_atomic_template.return_value = TaskResult(status="COMPLETE", content="task_res")

        # Mock the internal argument parser if it's complex enough, or test its effects directly
        # For this test, we'll assume _parse_invocation_arguments works and test its integration.
        # If _parse_invocation_arguments is complex, it needs its own unit tests.
        
        result = evaluator._invoke_task_system(task_name, template_def, evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result.content == "task_res"
        
        mock_task_system.execute_atomic_template.assert_called_once()
        actual_request_arg = mock_task_system.execute_atomic_template.call_args[0][0]
        
        assert isinstance(actual_request_arg, SubtaskRequest)
        assert isinstance(actual_request_arg.task_id, str) and actual_request_arg.task_id, "task_id should be a non-empty string"
        assert actual_request_arg.type == "atomic"
        assert actual_request_arg.name == task_name
        assert actual_request_arg.inputs == {"param1": "actual_val1"}
        assert actual_request_arg.file_paths == ["/a.txt"]
        assert actual_request_arg.context_management is None

    def test_invoke_handler_tool_parses_args_and_calls(self, evaluator, mock_handler, mocker):
        env = SexpEnvironment()
        tool_name = "my_tool"
        original_expr_str = f"({tool_name} (arg1 123))"
        original_arg_exprs = [[Symbol("arg1"), 123]]
        evaluated_args = [123] # Result of _eval(123, env)

        # Tool executor itself is usually a function, _execute_tool is the method on handler
        mock_handler._execute_tool.return_value = TaskResult(status="COMPLETE", content="tool_res")
        
        result = evaluator._invoke_handler_tool(tool_name, evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result.content == "tool_res"
        mock_handler._execute_tool.assert_called_once_with(tool_name, {"arg1": 123})

    # Test _parse_invocation_arguments separately if complex
    def test_parse_invocation_arguments_full(self, evaluator):
        original_expr_str = "(cmd (p1 v1) (files (list \"/f\")) (context (quote ((c1 v1)))))"
        original_arg_exprs = [
            [Symbol("p1"), Symbol("v1_node")],
            [Symbol("files"), [Symbol("list"), "/f"]],
            [Symbol("context"), [Symbol("quote"), [[Symbol("c1"), Symbol("v1_val_node")]]]]
        ]
        evaluated_args = [ # Results of _eval on value expressions
            "evaluated_v1", # for v1_node
            ["/f"],         # for (list "/f")
            [[Symbol("c1"), Symbol("v1_val_node")]] # for (quote ((c1 v1_val_node)))
        ]

        parsed = evaluator._parse_invocation_arguments(evaluated_args, original_arg_exprs, original_expr_str)

        assert parsed["named_params"] == {"p1": "evaluated_v1"}
        assert parsed["file_paths"] == ["/f"]
        assert parsed["context_settings"] == {"c1": Symbol("v1_val_node")} # Note: symbol keys from quote

    def test_parse_invocation_arguments_only_named(self, evaluator):
        original_expr_str = "(cmd (p1 v1))"
        original_arg_exprs = [[Symbol("p1"), Symbol("v1_node")]]
        evaluated_args = ["evaluated_v1"]
        
        parsed = evaluator._parse_invocation_arguments(evaluated_args, original_arg_exprs, original_expr_str)
        
        assert parsed["named_params"] == {"p1": "evaluated_v1"}
        assert parsed["file_paths"] is None
        assert parsed["context_settings"] is None

    def test_parse_invocation_arguments_invalid_files_type(self, evaluator):
        original_expr_str = "(cmd (files \"not-a-list\"))"
        original_arg_exprs = [[Symbol("files"), "not-a-list-node"]]
        evaluated_args = ["not-a-list"] # _eval("not-a-list-node") -> "not-a-list" string
        
        with pytest.raises(SexpEvaluationError, match="'files' argument must evaluate to a list of strings"):
            evaluator._parse_invocation_arguments(evaluated_args, original_arg_exprs, original_expr_str)

    def test_parse_invocation_arguments_invalid_context_type(self, evaluator):
        original_expr_str = "(cmd (context \"not-a-dict-or-list\"))"
        original_arg_exprs = [[Symbol("context"), "str_node"]]
        evaluated_args = ["not-a-dict-or-list"]
        
        with pytest.raises(SexpEvaluationError, match="'context' argument must evaluate to a dictionary or a list of pairs"):
            evaluator._parse_invocation_arguments(evaluated_args, original_arg_exprs, original_expr_str)

    def test_parse_invocation_arguments_invalid_arg_pair_format(self, evaluator):
        original_expr_str = "(cmd not-a-list)" # Arg is not a list
        original_arg_exprs = [Symbol("not-a-list")]
        evaluated_args = ["some_value"] # Dummy, parsing fails before using this
        
        with pytest.raises(SexpEvaluationError, match="Invalid argument format for invocation. Expected \\(key_symbol value_expression\\)"):
            evaluator._parse_invocation_arguments(evaluated_args, original_arg_exprs, original_expr_str)

        original_expr_str_2 = "(cmd (key-only))" # Arg list has only one element
        original_arg_exprs_2 = [[Symbol("key-only")]]
        evaluated_args_2 = ["some_value_2"]
        with pytest.raises(SexpEvaluationError, match="Invalid argument format for invocation. Expected \\(key_symbol value_expression\\)"):
            evaluator._parse_invocation_arguments(evaluated_args_2, original_arg_exprs_2, original_expr_str_2)

        original_expr_str_3 = "(cmd (123 value))" # Key is not a symbol
        original_arg_exprs_3 = [[123, Symbol("value_node")]]
        evaluated_args_3 = ["some_value_3"]
        with pytest.raises(SexpEvaluationError, match="Invalid argument format for invocation. Expected \\(key_symbol value_expression\\)"):
            evaluator._parse_invocation_arguments(evaluated_args_3, original_arg_exprs_3, original_expr_str_3)


# --- New Unit Tests for Refactored Internal Methods ---

class TestSexpEvaluatorInternals:

    def test_eval_list_form_dispatches_special_form(self, evaluator, mock_parser, mocker):
        """Test _eval_list_form correctly dispatches to a special form handler."""
        env = SexpEnvironment()
        original_expr_str = "(if true 1 0)"
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
        mock_if_handler.assert_called_once_with(arg_exprs, env, original_expr_str)
        # Restore original handler if necessary for other tests, or use fresh evaluator
        evaluator.SPECIAL_FORM_HANDLERS['if'] = evaluator._eval_if_form


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
        
        # Check calls to _eval
        # Call 1: op_expr
        # Call 2: arg1_expr
        # Call 3: arg2_expr
        assert mock_internal_eval.call_count == 3 
        mock_internal_eval.assert_any_call(op_expr, env)
        mock_internal_eval.assert_any_call(arg1_expr, env)
        mock_internal_eval.assert_any_call(arg2_expr, env)
        
        # Check call to _apply_operator
        resolved_operator_expected = "resolved_func_name"
        evaluated_args_expected = [10, 20]
        original_arg_exprs_expected = [arg1_expr, arg2_expr]
        mock_apply_op.assert_called_once_with(
            resolved_operator_expected,
            evaluated_args_expected,
            original_arg_exprs_expected,
            env,
            original_expr_str
        )

    def test_apply_operator_dispatches_primitive(self, evaluator, mocker):
        env = SexpEnvironment()
        original_expr_str = "(list 1 2)"
        evaluated_args = [1, 2]
        original_arg_exprs = [1, 2] # For 'list', these happen to be the same as evaluated

        mock_list_applier = mocker.patch.object(evaluator, '_apply_list_primitive', return_value="list_applied")
        evaluator.PRIMITIVE_APPLIERS['list'] = mock_list_applier # Ensure dispatcher uses mock

        result = evaluator._apply_operator("list", evaluated_args, original_arg_exprs, env, original_expr_str)
        
        assert result == "list_applied"
        mock_list_applier.assert_called_once_with(evaluated_args, original_arg_exprs, env, original_expr_str)
        evaluator.PRIMITIVE_APPLIERS['list'] = evaluator._apply_list_primitive # Restore

    def test_apply_operator_dispatches_task(self, evaluator, mock_task_system, mocker):
        env = SexpEnvironment()
        task_name = "my_atomic_task"
        original_expr_str = f"({task_name} (p 1))"
        evaluated_args = [1] # e.g., (p 1) -> p's value is 1
        original_arg_exprs = [[Symbol("p"), 1]] # e.g. (p 1)

        mock_task_system.find_template.return_value = {"name": task_name, "type": "atomic"}
        mock_invoke_task = mocker.patch.object(evaluator, '_invoke_task_system', return_value=TaskResult(status="COMPLETE", content="task_done"))

        result = evaluator._apply_operator(task_name, evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result.content == "task_done"
        mock_task_system.find_template.assert_called_once_with(task_name)
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
        evaluated_args = ["foo"]
        original_arg_exprs = [[Symbol("arg"), Symbol("'foo")]] # Example original structure

        mock_handler.tool_executors = {tool_name: MagicMock()} # Tool must exist
        mock_invoke_tool = mocker.patch.object(evaluator, '_invoke_handler_tool', return_value=TaskResult(status="COMPLETE", content="tool_done"))

        result = evaluator._apply_operator(tool_name, evaluated_args, original_arg_exprs, env, original_expr_str)
        
        assert result.content == "tool_done"
        mock_invoke_tool.assert_called_once_with(tool_name, evaluated_args, original_arg_exprs, env, original_expr_str)

    def test_apply_operator_calls_python_callable(self, evaluator, mocker):
        env = SexpEnvironment()
        original_expr_str = "(py_func 10)"
        evaluated_args = [10]
        original_arg_exprs = [10]

        mock_callable = MagicMock(return_value="callable_result")
        
        result = evaluator._apply_operator(mock_callable, evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result == "callable_result"
        mock_callable.assert_called_once_with(*evaluated_args)

    def test_apply_operator_error_unrecognized_name(self, evaluator):
        with pytest.raises(SexpEvaluationError, match="Unrecognized operator name: unknown_op"):
            evaluator._apply_operator("unknown_op", [], [], SexpEnvironment(), "(unknown_op)")

    def test_apply_operator_error_non_callable(self, evaluator):
        with pytest.raises(SexpEvaluationError, match="Cannot apply non-callable operator: 123"):
            evaluator._apply_operator(123, [], [], SexpEnvironment(), "(123)") # 123 is not a string name or callable

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
    def test_apply_list_primitive_returns_evaluated_args(self, evaluator):
        evaluated_args = [1, "two", True]
        result = evaluator._apply_list_primitive(evaluated_args, [], SexpEnvironment(), "(list ...)")
        assert result == evaluated_args
        assert result is evaluated_args # Should be the same list object

    # (Tests for _apply_get_context_primitive would be more involved, mocking memory_system)
    # Example structure for _apply_get_context_primitive test:
    def test_apply_get_context_primitive_parses_and_calls_memory(self, evaluator, mock_memory_system, mocker):
        env = SexpEnvironment()
        original_expr_str = "(get_context (query \"search\") (matching_strategy content))"
        # original_arg_exprs are the unevaluated (key value_expr) pairs
        original_arg_exprs = [
            [Symbol("query"), "search"], 
            [Symbol("matching_strategy"), Symbol("content")]
        ]
        # evaluated_args are the results of _eval on each value_expr
        evaluated_args = ["search", "content"] # "content" symbol evaluates to "content" string

        expected_cg_input = ContextGenerationInput(query="search", matching_strategy="content")
        mock_memory_system.get_relevant_context_for.return_value = AssociativeMatchResult(
            context_summary="ctx", matches=[MatchTuple(path="/f.py", relevance=0.9)]
        )

        result = evaluator._apply_get_context_primitive(evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result == ["/f.py"]
        mock_memory_system.get_relevant_context_for.assert_called_once_with(expected_cg_input)


    # --- Tests for Invocation Helpers (Example: _invoke_task_system) ---
    def test_invoke_task_system_parses_args_and_calls(self, evaluator, mock_task_system, mocker):
        env = SexpEnvironment()
        task_name = "my_task"
        template_def = {"name": task_name, "type": "atomic"}
        original_expr_str = f"({task_name} (param1 val1_eval) (files (list \"/a.txt\")))"
        
        # original_arg_exprs: [(param1 val1_expr_node), (files (list "/a.txt"))]
        original_arg_exprs = [
            [Symbol("param1"), Symbol("val1_expr_node")], # val1_expr_node would be some AST
            [Symbol("files"), [Symbol("list"), "/a.txt"]]
        ]
        # evaluated_args: [result_of_eval_val1_expr_node, result_of_eval_(list "/a.txt")]
        evaluated_args = ["actual_val1", ["/a.txt"]]


        mock_task_system.execute_atomic_template.return_value = TaskResult(status="COMPLETE", content="task_res")

        # Mock the internal argument parser if it's complex enough, or test its effects directly
        # For this test, we'll assume _parse_invocation_arguments works and test its integration.
        # If _parse_invocation_arguments is complex, it needs its own unit tests.
        
        result = evaluator._invoke_task_system(task_name, template_def, evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result.content == "task_res"
        
        expected_subtask_request = SubtaskRequest(
            task_id=ANY, # task_id is dynamically generated
            type="atomic",
            name=task_name,
            inputs={"param1": "actual_val1"},
            file_paths=["/a.txt"],
            context_management=None 
        )
        mock_task_system.execute_atomic_template.assert_called_once_with(expected_subtask_request)

    def test_invoke_handler_tool_parses_args_and_calls(self, evaluator, mock_handler, mocker):
        env = SexpEnvironment()
        tool_name = "my_tool"
        original_expr_str = f"({tool_name} (arg1 123))"
        original_arg_exprs = [[Symbol("arg1"), 123]]
        evaluated_args = [123] # Result of _eval(123, env)

        # Tool executor itself is usually a function, _execute_tool is the method on handler
        mock_handler._execute_tool.return_value = TaskResult(status="COMPLETE", content="tool_res")
        
        result = evaluator._invoke_handler_tool(tool_name, evaluated_args, original_arg_exprs, env, original_expr_str)

        assert result.content == "tool_res"
        mock_handler._execute_tool.assert_called_once_with(tool_name, {"arg1": 123})

    # Test _parse_invocation_arguments separately if complex
    def test_parse_invocation_arguments_full(self, evaluator):
        original_expr_str = "(cmd (p1 v1) (files (list \"/f\")) (context (quote ((c1 v1)))))"
        original_arg_exprs = [
            [Symbol("p1"), Symbol("v1_node")],
            [Symbol("files"), [Symbol("list"), "/f"]],
            [Symbol("context"), [Symbol("quote"), [[Symbol("c1"), Symbol("v1_val_node")]]]]
        ]
        evaluated_args = [ # Results of _eval on value expressions
            "evaluated_v1", # for v1_node
            ["/f"],         # for (list "/f")
            [[Symbol("c1"), Symbol("v1_val_node")]] # for (quote ((c1 v1_val_node)))
        ]

        parsed = evaluator._parse_invocation_arguments(evaluated_args, original_arg_exprs, original_expr_str)

        assert parsed["named_params"] == {"p1": "evaluated_v1"}
        assert parsed["file_paths"] == ["/f"]
        assert parsed["context_settings"] == {"c1": Symbol("v1_val_node")} # Note: symbol keys from quote

    def test_parse_invocation_arguments_only_named(self, evaluator):
        original_expr_str = "(cmd (p1 v1))"
        original_arg_exprs = [[Symbol("p1"), Symbol("v1_node")]]
        evaluated_args = ["evaluated_v1"]
        
        parsed = evaluator._parse_invocation_arguments(evaluated_args, original_arg_exprs, original_expr_str)
        
        assert parsed["named_params"] == {"p1": "evaluated_v1"}
        assert parsed["file_paths"] is None
        assert parsed["context_settings"] is None

    def test_parse_invocation_arguments_invalid_files_type(self, evaluator):
        original_expr_str = "(cmd (files \"not-a-list\"))"
        original_arg_exprs = [[Symbol("files"), "not-a-list-node"]]
        evaluated_args = ["not-a-list"] # _eval("not-a-list-node") -> "not-a-list" string
        
        with pytest.raises(SexpEvaluationError, match="'files' argument must evaluate to a list of strings"):
            evaluator._parse_invocation_arguments(evaluated_args, original_arg_exprs, original_expr_str)

    def test_parse_invocation_arguments_invalid_context_type(self, evaluator):
        original_expr_str = "(cmd (context \"not-a-dict-or-list\"))"
        original_arg_exprs = [[Symbol("context"), "str_node"]]
        evaluated_args = ["not-a-dict-or-list"]
        
        with pytest.raises(SexpEvaluationError, match="'context' argument must evaluate to a dictionary or a list of pairs"):
            evaluator._parse_invocation_arguments(evaluated_args, original_arg_exprs, original_expr_str)

    def test_parse_invocation_arguments_invalid_arg_pair_format(self, evaluator):
        original_expr_str = "(cmd not-a-list)" # Arg is not a list
        original_arg_exprs = [Symbol("not-a-list")]
        evaluated_args = ["some_value"] # Dummy, parsing fails before using this
        
        with pytest.raises(SexpEvaluationError, match="Invalid argument format for invocation. Expected \\(key_symbol value_expression\\)"):
            evaluator._parse_invocation_arguments(evaluated_args, original_arg_exprs, original_expr_str)

        original_expr_str_2 = "(cmd (key-only))" # Arg list has only one element
        original_arg_exprs_2 = [[Symbol("key-only")]]
        evaluated_args_2 = ["some_value_2"]
        with pytest.raises(SexpEvaluationError, match="Invalid argument format for invocation. Expected \\(key_symbol value_expression\\)"):
            evaluator._parse_invocation_arguments(evaluated_args_2, original_arg_exprs_2, original_expr_str_2)

        original_expr_str_3 = "(cmd (123 value))" # Key is not a symbol
        original_arg_exprs_3 = [[123, Symbol("value_node")]]
        evaluated_args_3 = ["some_value_3"]
        with pytest.raises(SexpEvaluationError, match="Invalid argument format for invocation. Expected \\(key_symbol value_expression\\)"):
            evaluator._parse_invocation_arguments(evaluated_args_3, original_arg_exprs_3, original_expr_str_3)
