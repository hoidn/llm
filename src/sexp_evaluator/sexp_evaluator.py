"""
S-expression DSL Evaluator implementation.
Parses and executes workflows defined in S-expression syntax.
Handles workflow composition logic (sequences, conditionals, loops, task/tool calls).
"""

import logging
from typing import Any, Dict, List, Optional, Callable 

# Core System Dependencies (Injected)
from src.task_system.task_system import TaskSystem
from src.handler.base_handler import BaseHandler
from src.memory.memory_system import MemorySystem

# Sexp Parsing and Environment
from src.sexp_parser.sexp_parser import SexpParser
from src.sexp_evaluator.sexp_environment import SexpEnvironment
from .sexp_closure import Closure 
from .sexp_special_forms import SpecialFormProcessor 
from .sexp_primitives import PrimitiveProcessor     

# System Models and Errors
from sexpdata import Symbol, Quoted as sexpdata_Quoted  # Renamed for clarity in debugging
from src.system.models import (
    TaskResult, SubtaskRequest, ContextGenerationInput, ContextManagement,
    TaskFailureError, AssociativeMatchResult, MatchTuple,
    TaskError 
)
from src.system.errors import SexpSyntaxError, SexpEvaluationError

# Debug logging for sexpdata.Quoted import
logging.debug(f"SexpEvaluator: Imported Quoted type: {type(sexpdata_Quoted)}, id: {id(sexpdata_Quoted)}, module: {getattr(sexpdata_Quoted, '__module__', 'N/A')}")

# Type for Sexp AST nodes (adjust based on SexpParser output)
from sexpdata import Symbol 


SexpNode = Any # General type hint for AST nodes

logger = logging.getLogger(__name__) 


class SexpEvaluator:
    """
    Parses and evaluates S-expression strings representing workflows.
    Handles special forms, primitives, and invocation of atomic tasks/tools.

    Implements the contract defined in src/sexp_evaluator/sexp_evaluator_IDL.md.
    Adheres to Unified ADR XX mandates regarding composition and invocation.
    """

    def __init__(
        self,
        task_system: TaskSystem,
        handler: BaseHandler,
        memory_system: MemorySystem
    ):
        """
        Initializes the S-expression evaluator with dependencies.

        Args:
            task_system: A valid TaskSystem instance.
            handler: A valid BaseHandler instance.
            memory_system: A valid MemorySystem instance.
        """
        self.task_system = task_system
        self.handler = handler
        self.memory_system = memory_system
        self.parser = SexpParser() 

        # Make Closure class accessible to helper processors
        self.Closure = Closure
        
        # Instantiate helper processors
        self.special_form_processor = SpecialFormProcessor(self)
        self.primitive_processor = PrimitiveProcessor(self)

        # Dispatch dictionaries for special forms and primitives
        self.SPECIAL_FORM_HANDLERS: Dict[str, Callable] = {
            "if": self.special_form_processor.handle_if_form,
            "let": self.special_form_processor.handle_let_form,
            "bind": self.special_form_processor.handle_bind_form,
            "progn": self.special_form_processor.handle_progn_form,
            "quote": self.special_form_processor.handle_quote_form,
            "defatom": self.special_form_processor.handle_defatom_form,
            "loop": self.special_form_processor.handle_loop_form,
            "iterative-loop": self._eval_iterative_loop, # Add this line
            "director-evaluator-loop": self.special_form_processor.handle_director_evaluator_loop,
            "and": self.special_form_processor.handle_and_form,
            "or": self.special_form_processor.handle_or_form,
        }
        self.PRIMITIVE_APPLIERS: Dict[str, Callable] = {
            "list": self.primitive_processor.apply_list_primitive,
            "get_context": self.primitive_processor.apply_get_context_primitive,
            "get-field": self.primitive_processor.apply_get_field_primitive,
            "string=?": self.primitive_processor.apply_string_equal_primitive,
            "log-message": self.primitive_processor.apply_log_message_primitive,
            # --- Phase 10b Additions ---
            "eq?": self.primitive_processor.apply_eq_primitive,
            "equal?": self.primitive_processor.apply_eq_primitive, # Alias for eq?
            "null?": self.primitive_processor.apply_null_primitive,
            "nil?": self.primitive_processor.apply_null_primitive,   # Alias for null?
            "set!": self.primitive_processor.apply_set_bang_primitive,
            "+": self.primitive_processor.apply_add_primitive,
            "-": self.primitive_processor.apply_subtract_primitive,
            "<": self.primitive_processor.apply_less_than_primitive,
            "string-append": self.primitive_processor.apply_string_append_primitive,
            # --- ADD THIS LINE ---
            "not": self.primitive_processor.apply_not_primitive,
            # --- END ADD ---
        }
        logging.debug(f"SexpEvaluator INITIALIZED. SPECIAL_FORM_HANDLERS keys: {list(self.SPECIAL_FORM_HANDLERS.keys())}")
        logging.debug(f"SexpEvaluator INITIALIZED. PRIMITIVE_APPLIERS keys: {list(self.PRIMITIVE_APPLIERS.keys())}")
        logging.info("SexpEvaluator initialized with helper processors.")

    def evaluate_string(
        self,
        sexp_string: str,
        initial_env: Optional[SexpEnvironment] = None
    ) -> Any:
        """
        Parses and evaluates an S-expression string within a given environment.
        Main entry point for executing S-expression workflows.
        """
        logging.info(f"Evaluating S-expression string: {sexp_string[:100]}...")
        try:
            parsed_node = self.parser.parse_string(sexp_string)
            logging.debug(f"Parsed S-expression AST: {parsed_node}")

            env = initial_env if initial_env is not None else SexpEnvironment()
            logging.debug(f"Using environment: {env}")

            result = self._eval(parsed_node, env)
            logging.info(f"Finished evaluating S-expression. Result type: {type(result)}")
            return result

        except SexpSyntaxError as e:
            logging.error(f"S-expression syntax error: {e}")
            raise 
        except NameError as e:
             logging.error(f"Sexp evaluation error: Unbound symbol - {e}")
             raise SexpEvaluationError(f"{e}", expression=sexp_string) from e 
        except SexpEvaluationError as e:
            logging.error(f"S-expression evaluation error: {e}")
            if not hasattr(e, 'expression') or not e.expression: 
                 e.expression = sexp_string
            raise 
        except Exception as e:
            logging.exception(f"Unexpected error during S-expression evaluation: {e}")
            error_details_str = ""
            if hasattr(e, 'model_dump'):
                 try:
                     error_details_str = str(e.model_dump(exclude_none=True))
                 except Exception: 
                     error_details_str = str(e)
            else:
                 error_details_str = str(e)

            original_message = e.args[0] if isinstance(e, (SexpEvaluationError, SexpSyntaxError)) and e.args else str(e)
            expression_context = e.expression if isinstance(e, (SexpEvaluationError, SexpSyntaxError)) and hasattr(e, 'expression') and e.expression else sexp_string
            
            raise SexpEvaluationError(
                f"Evaluation failed: {original_message}", 
                expression=expression_context, 
                error_details=error_details_str
            ) from e


    def _eval(self, node: SexpNode, env: SexpEnvironment) -> Any:
        """
        Internal recursive evaluation method for S-expression AST nodes.
        Handles base cases and dispatches list evaluation.
        """
        logging.debug(f"Eval START: Node={node} (Type={type(node)}) EnvID={id(env)}")

        if isinstance(node, Symbol):
            symbol_name = node.value()
            try:
                value = env.lookup(symbol_name) 
                logger.debug(f"Eval Symbol END: '{symbol_name}' -> {value} (Type={type(value)})")
                return value
            except NameError as e:
                 logger.error(f"Eval Symbol FAILED: Unbound symbol '{symbol_name}'")
                 raise 

        # Handle Quoted objects directly
        # A Quoted object, e.g., from 'foo, is like Quoted(Symbol('foo')).
        # The sexpdata.Quoted class is a namedtuple('Quoted', 'x').
        # So, node.x should give the inner value.
        if isinstance(node, sexpdata_Quoted):
            logging.debug(f"Eval Quoted: Encountered node: {node!r}")
            logging.debug(f"Eval Quoted: Type of node: {type(node)}")
            try:
                # The 'sexpdata.Quoted' object is a namedtuple with a single field 'x'.
                # This 'x' field holds the actual quoted data.
                actual_val = node.x
                logging.debug(f"Eval Quoted: Extracted value from node.x: {actual_val!r}")
                return actual_val
            except AttributeError:
                # This might happen if our understanding of sexpdata.Quoted is off
                # or if a different type of Quoted object is encountered.
                # Let's log and re-raise for now, as the direct attribute access
                # is the documented way for sexpdata.Quoted.
                logging.exception(f"Eval Quoted: AttributeError accessing node.x for {node!r}. This is unexpected for sexpdata.Quoted.")
                raise SexpEvaluationError(f"Invalid Quoted object structure: {node!r} does not have .x", expression=str(node))

        if not isinstance(node, list):
            # This branch now handles non-Symbol, non-Quoted, non-list atoms (numbers, strings, bools, None)
            logger.debug(f"Eval Literal/Atom (non-Symbol, non-Quoted, non-list): {node}")
            return node

        if not node: 
            logger.debug("Eval Empty List: -> []")
            return []

        op_expr_node = node[0]
        if isinstance(op_expr_node, Symbol) and op_expr_node.value() == "lambda":
            logger.debug(f"Eval: Encountered 'lambda' special form: {node}")
            
            if len(node) < 3: 
                raise SexpEvaluationError(
                    "'lambda' requires a parameter list and at least one body expression.", 
                    expression=str(node)
                )
            
            params_list_node = node[1]
            if not isinstance(params_list_node, list):
                raise SexpEvaluationError(
                    "Lambda parameter definition must be a list of symbols.", 
                    expression=str(params_list_node)
                )

            lambda_params_ast: List[Symbol] = [] 
            for p_node in params_list_node:
                if not isinstance(p_node, Symbol):
                    raise SexpEvaluationError(
                        f"Lambda parameters must be symbols, got {type(p_node)}: {p_node}", 
                        expression=str(params_list_node)
                    )
                lambda_params_ast.append(p_node)
            
            lambda_body_ast: List[SexpNode] = node[2:] 
            if not lambda_body_ast: 
                 raise SexpEvaluationError("Lambda requires at least one body expression.", expression=str(node))

            logger.debug(f"Creating Closure: params={lambda_params_ast}, num_body_exprs={len(lambda_body_ast)}, def_env_id={id(env)}")
            return Closure(lambda_params_ast, lambda_body_ast, env) 

        logger.debug(f"Eval Non-Empty List (not lambda): Delegating to _eval_list_form for: {node}")
        return self._eval_list_form(node, env)

    def _eval_list_form(self, expr_list: list, env: SexpEnvironment) -> Any:
        """
        Evaluates a non-empty list expression.
        Dispatches to special form handlers or standard operator application.
        """
        original_expr_str = str(expr_list) 
        logging.debug(f"--- _eval_list_form START: expr_list={expr_list}, original_expr_str='{original_expr_str}'")

        op_expr_node = expr_list[0]
        arg_expr_nodes = expr_list[1:] 

        resolved_operator: Any

        if isinstance(op_expr_node, Symbol):
            op_name_str = op_expr_node.value()
            # 1. Check for Special Forms first
            if op_name_str in self.SPECIAL_FORM_HANDLERS: 
                logger.debug(f"  _eval_list_form: Dispatching to Special Form Handler: {op_name_str}")
                handler_method = self.SPECIAL_FORM_HANDLERS[op_name_str]
                return handler_method(arg_expr_nodes, env, original_expr_str) 
            
            # 2. Check if it's a known primitive, atomic task, or handler tool name
            # These should be treated as direct call targets, not looked up as variables.
            is_primitive = op_name_str in self.PRIMITIVE_APPLIERS
            template_def = self.task_system.find_template(op_name_str)
            is_atomic_task = template_def is not None # find_template returns None if not found or not atomic
            is_handler_tool = op_name_str in self.handler.tool_executors

            if is_primitive or is_atomic_task or is_handler_tool:
                resolved_operator = op_name_str 
                logger.debug(f"  _eval_list_form: Operator '{op_name_str}' identified as known primitive/task/tool name. Will be passed to _apply_operator.")
            else:
                # 3. If not a special form or known invokable name, THEN try to evaluate it as a variable (e.g., a lambda)
                logger.debug(f"  _eval_list_form: Operator symbol '{op_name_str}' is not a special form or known invokable name. Evaluating (looking up) '{op_name_str}' as a variable...")
                try:
                    resolved_operator = self._eval(op_expr_node, env) # This does env.lookup()
                except NameError as ne: 
                    logger.error(f"  _eval_list_form: Operator symbol '{op_name_str}' is unbound during variable lookup.")
                    raise SexpEvaluationError(f"Unbound symbol or unrecognized operator: {op_name_str}", original_expr_str) from ne
                except SexpEvaluationError as se: 
                    raise se # Propagate if _eval itself raised SexpEvaluationError
                except Exception as e: 
                    logger.exception(f"  _eval_list_form: Unexpected error evaluating operator symbol '{op_name_str}' as variable: {e}")
                    raise SexpEvaluationError(f"Error evaluating operator symbol '{op_name_str}' as variable: {e}", original_expr_str, error_details=str(e)) from e
        elif isinstance(op_expr_node, list): 
            logger.debug(f"  _eval_list_form: Operator is a complex expression, evaluating it: {op_expr_node}")
            try:
                resolved_operator = self._eval(op_expr_node, env)
            except Exception as e_op_eval: 
                logger.exception(f"  _eval_list_form: Error evaluating complex operator expression '{op_expr_node}': {e_op_eval}")
                if isinstance(e_op_eval, SexpEvaluationError): raise 
                raise SexpEvaluationError(f"Error evaluating operator expression: {op_expr_node}", original_expr_str, error_details=str(e_op_eval)) from e_op_eval
        elif isinstance(op_expr_node, self.Closure) or callable(op_expr_node):
            # If op_expr_node is already a Closure or another Python callable (e.g., passed via environment)
            logger.debug(f"  _eval_list_form: Operator is already a resolved callable (type: {type(op_expr_node)}).")
            resolved_operator = op_expr_node
        else: 
            raise SexpEvaluationError(f"Operator in list form must be a symbol or another list, got {type(op_expr_node)}: {op_expr_node}", original_expr_str)

        logger.debug(f"  _eval_list_form: Resolved operator to: {resolved_operator} (Type: {type(resolved_operator)})")
        
        return self._apply_operator(resolved_operator, arg_expr_nodes, env, original_expr_str)

    def _apply_operator(
        self,
        resolved_op: Any, 
        arg_expr_nodes: List[SexpNode],  
        calling_env: SexpEnvironment, 
        original_call_expr_str: str  
    ) -> Any:
        """
        Applies a resolved operator to a list of argument expressions.
        Dispatches to closure application, primitive appliers, task/tool invokers, or Python callables.
        Handles argument evaluation based on the operator type.
        """
        logger.debug(f"--- _apply_operator START: resolved_op_type={type(resolved_op)}, num_arg_exprs={len(arg_expr_nodes)}, original_call_expr_str='{original_call_expr_str}'")

        if isinstance(resolved_op, Closure):
            closure_to_apply = resolved_op
            logger.debug(f"  _apply_operator: Applying Closure: {closure_to_apply}")

            num_expected_params = len(closure_to_apply.params_ast)
            num_provided_args = len(arg_expr_nodes)
            if num_expected_params != num_provided_args:
                raise SexpEvaluationError(
                    f"Arity mismatch: Closure expects {num_expected_params} arguments, got {num_provided_args} for {original_call_expr_str}",
                    expression=original_call_expr_str
                )

            evaluated_args = []
            logger.debug(f"    Evaluating {num_provided_args} arguments in calling_env (id={id(calling_env)})...")
            for i, arg_node in enumerate(arg_expr_nodes):
                try:
                    eval_arg = self._eval(arg_node, calling_env)
                    evaluated_args.append(eval_arg)
                    logger.debug(f"      Evaluated arg {i+1} ('{arg_node}') to: {eval_arg}")
                except Exception as e_arg_eval:
                    logger.exception(f"      Error evaluating argument {i+1} ('{arg_node}') for closure: {e_arg_eval}")
                    if isinstance(e_arg_eval, SexpEvaluationError): raise
                    raise SexpEvaluationError(f"Error evaluating argument {i+1} for closure: {arg_node}", original_call_expr_str, error_details=str(e_arg_eval)) from e_arg_eval
            
            # --- START FIX for Lexical Scope ---
            # Create new call frame: Its parent MUST be the closure's definition environment
            definition_env_for_closure = closure_to_apply.definition_env
            logger.debug(f"    Creating new call frame. Parent (definition_env) ID: {id(definition_env_for_closure)}")
            # Use the definition_env's extend method to link correctly
            call_frame_env = definition_env_for_closure.extend({})
            # --- END FIX for Lexical Scope ---


            for param_symbol, arg_value in zip(closure_to_apply.params_ast, evaluated_args):
                param_name = param_symbol.value()
                call_frame_env.define(param_name, arg_value) # Define params in the new call_frame_env
                logger.debug(f"      Bound '{param_name}' = {arg_value} in call frame (id={id(call_frame_env)})")
            
            final_body_result: Any = []
            # --- Use the new call_frame_env for body evaluation ---
            logger.debug(f"    Evaluating closure body with {len(closure_to_apply.body_ast)} expressions in call frame (id={id(call_frame_env)}) which has parent (definition_env) id={id(definition_env_for_closure)}")
            for i, body_node in enumerate(closure_to_apply.body_ast):
                try:
                    final_body_result = self._eval(body_node, call_frame_env) # Evaluate in call_frame_env
                    logger.debug(f"      Body expression {i+1} evaluated to: {final_body_result}")
                except Exception as e_body_eval:
                    logger.exception(f"      Error evaluating closure body expression {i+1} '{body_node}': {e_body_eval}")
                    if isinstance(e_body_eval, SexpEvaluationError): raise
                    raise SexpEvaluationError(f"Error evaluating closure body expression {i+1}: {body_node}", original_call_expr_str, error_details=str(e_body_eval)) from e_body_eval
            
            logger.debug(f"--- _apply_operator (Closure) END: returning {final_body_result}")
            return final_body_result

        elif isinstance(resolved_op, str):
            op_name_str = resolved_op
            logger.debug(f"_apply_operator: Checking for op_name_str '{op_name_str}'. Available primitives: {list(self.PRIMITIVE_APPLIERS.keys())}")
            logger.debug(f"  _apply_operator: Operator is a name string: '{op_name_str}'")

            if op_name_str in self.PRIMITIVE_APPLIERS:
                logger.info(f"  _apply_operator: Dispatching to Primitive Applier: {op_name_str}")
                applier_method = self.PRIMITIVE_APPLIERS[op_name_str]
                
                # Add specific try-except and logging for primitive calls
                try:
                    result = applier_method(arg_expr_nodes, calling_env, original_call_expr_str)
                    logger.info(f"  _apply_operator: Primitive '{op_name_str}' applier returned: {result!r} (Type: {type(result).__name__})")
                    return result
                except SexpEvaluationError as e_prim:
                    logger.warning(f"  _apply_operator: Primitive '{op_name_str}' applier RAISED SexpEvaluationError: {e_prim}")
                    raise  # Re-raise SexpEvaluationError directly
                except Exception as e_prim_unknown:
                    logger.exception(f"  _apply_operator: Primitive '{op_name_str}' applier RAISED UNEXPECTED Exception: {e_prim_unknown}")
                    # Wrap unexpected exceptions in SexpEvaluationError
                    raise SexpEvaluationError(
                        f"Unexpected error in primitive '{op_name_str}': {e_prim_unknown}",
                        original_call_expr_str,
                        error_details=str(e_prim_unknown)
                    ) from e_prim_unknown

            template_def = self.task_system.find_template(op_name_str)
            if template_def and template_def.get("type") == "atomic":
                logger.debug(f"  _apply_operator: Dispatching to Task System Invoker for: {op_name_str}")
                return self._invoke_task_system(op_name_str, template_def, arg_expr_nodes, calling_env, original_call_expr_str)

            if op_name_str in self.handler.tool_executors:
                logger.debug(f"  _apply_operator: Dispatching to Handler Tool Invoker for: {op_name_str}")
                return self._invoke_handler_tool(op_name_str, arg_expr_nodes, calling_env, original_call_expr_str)
            
            logger.error(f"  _apply_operator: Operator name '{op_name_str}' was resolved but is not a recognized primitive, task, or tool.")
            raise SexpEvaluationError(f"Operator '{op_name_str}' is not a callable primitive, task, or tool.", original_call_expr_str)

        elif callable(resolved_op): 
            logger.debug(f"  _apply_operator: Operator is a general Python callable: {resolved_op}. Evaluating arguments...")
            evaluated_args_list = []
            for i, arg_node in enumerate(arg_expr_nodes): 
                try:
                    evaluated_args_list.append(self._eval(arg_node, calling_env)) 
                    logger.debug(f"    Evaluated arg {i+1} ('{arg_node}') to: {evaluated_args_list[-1]}")
                except Exception as e_arg_eval:
                    logger.exception(f"  _apply_operator: Error evaluating argument {i+1} ('{arg_node}') for callable '{resolved_op}': {e_arg_eval}")
                    if isinstance(e_arg_eval, SexpEvaluationError): raise 
                    raise SexpEvaluationError(f"Error evaluating argument {i+1} for callable '{resolved_op}': {arg_node}", original_call_expr_str, error_details=str(e_arg_eval)) from e_arg_eval
            
            try:
                result = resolved_op(*evaluated_args_list) 
                logger.debug(f"  _apply_operator: Callable {resolved_op} returned: {result}")
                return result
            except Exception as e:
                logger.exception(f"  _apply_operator: Error calling Python callable {resolved_op} with args {evaluated_args_list}: {e}")
                raise SexpEvaluationError(f"Error invoking callable {resolved_op}: {e}", original_call_expr_str, error_details=str(e)) from e

        else:
            logger.error(f"  _apply_operator: Operator is not a name and not callable/closure: {resolved_op}")
            raise SexpEvaluationError(f"Cannot apply non-callable/non-closure operator: {resolved_op} (type: {type(resolved_op)})", original_call_expr_str)

    def _call_phase_function(self, phase_name: str, func_to_call: Any, args_list: List[Any], env_for_eval: SexpEnvironment, original_loop_expr: str, iteration: int) -> Any:
        """Helper to invoke a phase function (lambda/Closure) with error handling."""
        logger.debug(f"    Invoking {phase_name} (Iter {iteration}) with {len(args_list)} args in env_id={id(env_for_eval)}")
        try:
            # Re-quote evaluated arguments to pass them as if they were AST nodes
            # This allows _apply_operator to handle them correctly, especially for closures.
            dummy_arg_nodes = [[Symbol("quote"), arg] for arg in args_list]
            conceptual_call_str = f"({phase_name} iter={iteration})" # For potential error messages

            # Use _apply_operator to handle calling the resolved function (Closure or other callable)
            # _apply_operator will evaluate the quoted dummy nodes, effectively passing our args_list
            result = self._apply_operator(func_to_call, dummy_arg_nodes, env_for_eval, conceptual_call_str)
            logger.debug(f"    {phase_name} (Iter {iteration}) returned: {str(result)[:200]}{'...' if len(str(result)) > 200 else ''}")
            return result

        except SexpEvaluationError as e_phase:
            # Add context and re-raise
            error_msg = f"Error in '{phase_name}' phase (iteration {iteration}): {e_phase.args[0] if e_phase.args else str(e_phase)}"
            # Make sure error_details are preserved if they exist
            error_details = e_phase.error_details if hasattr(e_phase, 'error_details') else str(e_phase)
            logger.error(f"{error_msg} - Details: {error_details}")
            # Raise a NEW error instance with the combined info
            raise SexpEvaluationError(error_msg, original_loop_expr, error_details=error_details) from e_phase # Chain the exception
        except Exception as e_phase_unknown:
            # Wrap unexpected errors
            error_msg = f"Unexpected error in '{phase_name}' phase (iteration {iteration}): {e_phase_unknown}"
            logger.exception(error_msg) # Log with traceback
            raise SexpEvaluationError(error_msg, original_loop_expr, error_details=str(e_phase_unknown)) from e_phase_unknown

    def _eval_iterative_loop(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """
        Handles the 'iterative-loop' special form.
        (Implementation based on Step 4 plan).
        """
        logger.debug(f"SexpEvaluator._eval_iterative_loop START: {original_expr_str}")

        # 1. Parse and Validate Loop Structure
        clauses: Dict[str, SexpNode] = {}
        required_clauses = {"max-iterations", "initial-input", "test-command", "executor", "validator", "controller"}

        for arg_expr in arg_exprs:
            if not (isinstance(arg_expr, list) and len(arg_expr) == 2 and isinstance(arg_expr[0], Symbol)):
                raise SexpEvaluationError(
                    f"iterative-loop: Each clause must be a list of (ClauseName Expression), got: {arg_expr}",
                    original_expr_str
                )
            clause_name_symbol: Symbol = arg_expr[0]
            clause_name_str = clause_name_symbol.value()
            clause_expr_node: SexpNode = arg_expr[1]

            if clause_name_str in clauses:
                raise SexpEvaluationError(
                    f"iterative-loop: Duplicate clause '{clause_name_str}' found.",
                    original_expr_str
                )
            clauses[clause_name_str] = clause_expr_node

        missing = required_clauses - set(clauses.keys())
        if missing:
            raise SexpEvaluationError(
                f"iterative-loop: Missing required clauses: {', '.join(sorted(list(missing)))}",
                original_expr_str
            )

        # 2. Evaluate Configuration Expressions (with validation)
        try:
            max_iter_val = self._eval(clauses["max-iterations"], env)
            # --- ADDED VALIDATION ---
            if not isinstance(max_iter_val, int) or max_iter_val < 0:
                raise SexpEvaluationError(
                    f"iterative-loop: 'max-iterations' must evaluate to a non-negative integer, got {max_iter_val!r} (type: {type(max_iter_val)}).",
                    original_expr_str # Pass original expression string for context
                )
        except SexpEvaluationError as e:
            # Ensure the original expression string is included in the re-raised error
            raise SexpEvaluationError(f"iterative-loop: Error evaluating 'max-iterations': {e.args[0] if e.args else str(e)}", original_expr_str, error_details=e.error_details if hasattr(e, 'error_details') else str(e)) from e
        except Exception as e: # Catch unexpected errors during eval
            raise SexpEvaluationError(f"iterative-loop: Error evaluating 'max-iterations': {e}", original_expr_str, error_details=str(e)) from e

        try:
            current_loop_input = self._eval(clauses["initial-input"], env)
        except SexpEvaluationError as e:
            raise SexpEvaluationError(f"iterative-loop: Error evaluating 'initial-input': {e.args[0] if e.args else str(e)}", original_expr_str, error_details=e.error_details if hasattr(e, 'error_details') else str(e)) from e
        except Exception as e:
            raise SexpEvaluationError(f"iterative-loop: Error evaluating 'initial-input': {e}", original_expr_str, error_details=str(e)) from e

        try:
            test_cmd_string = self._eval(clauses["test-command"], env)
            # --- ADDED VALIDATION ---
            if not isinstance(test_cmd_string, str):
                raise SexpEvaluationError(
                    f"iterative-loop: 'test-command' must evaluate to a string, got {test_cmd_string!r} (type: {type(test_cmd_string)}).",
                    original_expr_str
                )
        except SexpEvaluationError as e:
            raise SexpEvaluationError(f"iterative-loop: Error evaluating 'test-command': {e.args[0] if e.args else str(e)}", original_expr_str, error_details=e.error_details if hasattr(e, 'error_details') else str(e)) from e
        except Exception as e: # Catch unexpected errors during eval
            raise SexpEvaluationError(f"iterative-loop: Error evaluating 'test-command': {e}", original_expr_str, error_details=str(e)) from e

        # 3. Evaluate and Validate Phase Function Expressions
        phase_functions: Dict[str, Any] = {}
        for phase_name in ["executor", "validator", "controller"]:
            try:
                resolved_fn = self._eval(clauses[phase_name], env)
                # --- ADDED VALIDATION ---
                # Check if it's our Closure or a general Python callable
                if not isinstance(resolved_fn, Closure) and not callable(resolved_fn):
                    raise SexpEvaluationError(
                        f"iterative-loop: '{phase_name}' expression must evaluate to a callable S-expression function or Python callable, got {type(resolved_fn)}: {resolved_fn!r}",
                        original_expr_str
                    )
                phase_functions[phase_name] = resolved_fn
            except SexpEvaluationError as e:
                 raise SexpEvaluationError(f"iterative-loop: Error evaluating '{phase_name}' function expression: {e.args[0] if e.args else str(e)}", original_expr_str, error_details=e.error_details if hasattr(e, 'error_details') else str(e)) from e
            except Exception as e: # Catch unexpected errors during eval
                raise SexpEvaluationError(f"iterative-loop: Error evaluating '{phase_name}' function expression: {e}", original_expr_str, error_details=str(e)) from e

        executor_fn   = phase_functions["executor"]
        validator_fn  = phase_functions["validator"]
        controller_fn = phase_functions["controller"]

        # 4. Initialize Loop State
        current_iteration = 1
        loop_result: Any = []  # S-expression 'nil' / Python empty list
        last_exec_result_val: Any = loop_result # Store last successful exec result

        # 5. Main Loop
        while current_iteration <= max_iter_val:
            logger.info(f"--- Iterative Loop: Iteration {current_iteration}/{max_iter_val} ---")

            try: # Wrap entire iteration body for error propagation
                # --- Executor Phase ---
                executor_result = self._call_phase_function(
                    "executor", executor_fn, [current_loop_input, current_iteration],
                env, original_expr_str, current_iteration
                )
                # Basic validation of executor result (optional but recommended)
                if not isinstance(executor_result, (dict, TaskResult)): # Allow TaskResult object too
                    logger.warning(f"Executor phase returned non-dict/TaskResult type: {type(executor_result)}")
                    # Decide how to handle - maybe wrap it or raise error? For now, log and continue.
                last_exec_result_val = executor_result # Store last exec result

                # --- Validator Phase ---
                validation_result = self._call_phase_function(
                    "validator", validator_fn, [test_cmd_string, current_iteration],
                    env, original_expr_str, current_iteration
                )
                # Basic validation of validator result (optional)
                if not isinstance(validation_result, dict) or not all(k in validation_result for k in ['stdout', 'stderr', 'exit_code']):
                     logger.warning(f"Validator phase returned unexpected structure: {validation_result!r}")
                     # Continue, controller might handle it or fail

                # --- Controller Phase ---
                decision_val = self._call_phase_function(
                    "controller", controller_fn, [executor_result, validation_result, current_loop_input, current_iteration],
                    env, original_expr_str, current_iteration
                )
            # --- FIXED Error Handling ---
            except Exception as phase_error:
                # Catch errors from _call_phase_function (which already wraps SexpEvaluationError)
                logging.exception(f"  Error during loop iteration {current_iteration}: {phase_error}")
                # Re-raise, ensuring it's SexpEvaluationError with loop context
                if isinstance(phase_error, SexpEvaluationError):
                    # Add iteration info if not already present
                    if "iteration" not in (phase_error.error_details or {}):
                        details = phase_error.error_details or {}
                        details["iteration"] = current_iteration
                        raise SexpEvaluationError(phase_error.args[0], original_expr_str, error_details=details) from phase_error
                    else:
                        raise phase_error # Re-raise if it already has context
                else: # Wrap unexpected errors
                    raise SexpEvaluationError(f"Unexpected error during loop iteration {current_iteration}: {phase_error}", original_expr_str, error_details={"iteration": current_iteration, "original_error": str(phase_error)}) from phase_error


            # --- Process Decision (with validation) ---
            if not (isinstance(decision_val, list) and len(decision_val) == 2 and isinstance(decision_val[0], Symbol)):
                raise SexpEvaluationError(
                    f"iterative-loop: Controller must return a list of (action_symbol value), got: {decision_val!r}",
                    original_expr_str
                )

            action_symbol: Symbol = decision_val[0]
            action_value: Any = decision_val[1]
            action_str = action_symbol.value()

            if action_str == "stop":
                logger.info(f"Loop stopping at iteration {current_iteration} due to controller 'stop'. Final result: {str(action_value)[:100]}...")
                loop_result = action_value # CORRECT ASSIGNMENT
                break # Exit the while loop
            elif action_str == "continue":
                logger.info(f"Loop continuing to next iteration. Next input: {str(action_value)[:100]}...")
                current_loop_input = action_value
                # loop_result = executor_result # Don't update loop_result here, only on stop or max_iter
                current_iteration += 1
            else: # Handle invalid action symbols
                raise SexpEvaluationError(
                    f"iterative-loop: Controller decision action must be 'continue' or 'stop' symbol, got: '{action_str}'",
                    original_expr_str
                )
        # --- End While Loop ---
        else: # Loop finished because current_iteration > max_iter_val
            logger.info(f"Loop finished after reaching max_iterations ({max_iter_val}). Returning last executor result.")
            # --- CORRECTED ASSIGNMENT ---
            # If the loop finished naturally, the result is the last executor result
            loop_result = last_exec_result_val

        logger.info(f"SexpEvaluator._eval_iterative_loop END. Iterations: {current_iteration-1 if current_iteration > 0 else 0}. Final loop_result type: {type(loop_result)}")
        logger.debug(f"SexpEvaluator._eval_iterative_loop END -> {str(loop_result)[:200]}...")
        return loop_result

    # --- Invocation Helpers (Remain in SexpEvaluator) ---

    def _invoke_task_system(
        self,
        task_name: str,
        template_def: Dict[str, Any],
        arg_exprs: List[SexpNode], 
        calling_env: SexpEnvironment, 
        original_expr_str: str
    ) -> TaskResult:
        logging.debug(f"--- _invoke_task_system START: task_name='{task_name}', arg_exprs={arg_exprs}")
        
        named_params: Dict[str, Any] = {}
        file_paths: Optional[List[str]] = None
        context_settings_dict: Optional[Dict[str, Any]] = None 
        history_config_dict: Optional[Dict[str, Any]] = None 

        for i, arg_expr_pair in enumerate(arg_exprs): 
            if not (isinstance(arg_expr_pair, list) and len(arg_expr_pair) == 2 and isinstance(arg_expr_pair[0], Symbol)):
                raise SexpEvaluationError(f"Invalid argument format for task '{task_name}'. Expected (key_symbol value_expression), got: {arg_expr_pair}", original_expr_str)
            
            key_symbol = arg_expr_pair[0]
            value_expr_node = arg_expr_pair[1] 
            key_str = key_symbol.value()

            try:
                evaluated_value = self._eval(value_expr_node, calling_env) 
                logging.debug(f"  _invoke_task_system: Evaluated value for key '{key_str}' ('{value_expr_node}'): {evaluated_value}")
            except SexpEvaluationError as e_val_eval:
                raise SexpEvaluationError(
                    f"Error evaluating value for '{key_str}' in task '{task_name}': {e_val_eval.args[0] if e_val_eval.args else str(e_val_eval)}",
                    expression=original_expr_str, 
                    error_details=f"Failed on value_expr='{e_val_eval.expression if hasattr(e_val_eval, 'expression') else value_expr_node}'. Original detail: {e_val_eval.error_details if hasattr(e_val_eval, 'error_details') else str(e_val_eval)}"
                ) from e_val_eval
            except Exception as e_val_eval: 
                logging.exception(f"  _invoke_task_system: Unexpected error evaluating value for key '{key_str}' ('{value_expr_node}'): {e_val_eval}")
                raise SexpEvaluationError(f"Unexpected error evaluating value for '{key_str}' in task '{task_name}': {value_expr_node}", original_expr_str, error_details=str(e_val_eval)) from e_val_eval

            if key_str == "files":
                if not (isinstance(evaluated_value, list) and all(isinstance(item, str) for item in evaluated_value)):
                    raise SexpEvaluationError(f"'files' argument for task '{task_name}' must evaluate to a list of strings, got {type(evaluated_value)}: {evaluated_value!r}", original_expr_str)
                file_paths = evaluated_value
            elif key_str == "context":
                if isinstance(evaluated_value, list) and all(isinstance(p, list) and len(p)==2 for p in evaluated_value):
                    try:
                        context_settings_dict = { (pair[0].value() if isinstance(pair[0], Symbol) else str(pair[0])): pair[1] for pair in evaluated_value }
                    except Exception as e_conv:
                         raise SexpEvaluationError(f"Failed converting 'context' list {evaluated_value!r} to dict for task '{task_name}': {e_conv}", original_expr_str) from e_conv
                elif isinstance(evaluated_value, dict):
                    context_settings_dict = evaluated_value
                else:
                    error_msg = f"'context' argument for task '{task_name}' must evaluate to a dictionary or a list of pairs, got {type(evaluated_value)}."
                    raise SexpEvaluationError(error_msg, original_expr_str)
            elif key_str == "history_config":
                if isinstance(evaluated_value, list) and all(isinstance(p, list) and len(p)==2 for p in evaluated_value):
                    try:
                        history_config_dict = { (pair[0].value() if isinstance(pair[0], Symbol) else str(pair[0])): pair[1] for pair in evaluated_value }
                    except Exception as e_conv:
                         raise SexpEvaluationError(f"Failed converting 'history_config' list {evaluated_value!r} to dict for task '{task_name}': {e_conv}", original_expr_str) from e_conv
                elif isinstance(evaluated_value, dict):
                    history_config_dict = evaluated_value
                else:
                    raise SexpEvaluationError(f"'history_config' argument for task '{task_name}' must evaluate to a dictionary or a list of pairs, got {type(evaluated_value)}: {evaluated_value!r}", original_expr_str)
            else: 
                named_params[key_str] = evaluated_value
        
        context_mgmt_obj: Optional[ContextManagement] = None
        if context_settings_dict:
            try:
                context_mgmt_obj = ContextManagement(**context_settings_dict) 
            except Exception as e_cm_val: 
                raise SexpEvaluationError(f"Invalid 'context' settings for task '{task_name}': {e_cm_val}", original_expr_str) from e_cm_val

        request = SubtaskRequest(
            task_id=f"sexp_task_{task_name}_{id(original_expr_str)}", 
            type="atomic", 
            name=task_name,
            inputs=named_params,
            file_paths=file_paths,
            context_management=context_mgmt_obj,
            history_config=history_config_dict  
        )
        logging.debug(f"  Constructed SubtaskRequest for '{task_name}': {request.model_dump_json(indent=2)}")

        try:
            task_result_obj = self.task_system.execute_atomic_template(request)
            if not isinstance(task_result_obj, TaskResult):
                 logging.error(f"  Task executor for '{task_name}' did not return a TaskResult object (got {type(task_result_obj)}).")
                 return TaskResult(
                    status="FAILED", 
                    content=f"Task '{task_name}' execution returned invalid type: {type(task_result_obj)}",
                    notes={"error": TaskFailureError(
                        type="TASK_FAILURE", 
                        reason="output_format_failure", 
                        message=f"Task '{task_name}' executor returned invalid type: {type(task_result_obj)}", 
                        details={"task_name": task_name, "returned_type": str(type(task_result_obj))} 
                    ).model_dump(exclude_none=True)}
                 )
            try:
                debug_dump = task_result_obj.model_dump_json(indent=2)
            except Exception: 
                debug_dump = str(task_result_obj) 
            logging.debug(f"  Task '{task_name}' execution returned: {debug_dump}")
            return task_result_obj
        except Exception as e_exec:
            logging.exception(f"  Error executing atomic task '{task_name}': {e_exec}")
            if isinstance(e_exec, SexpEvaluationError): raise 
            raise SexpEvaluationError(f"Error executing task '{task_name}': {e_exec}", original_expr_str, error_details=str(e_exec)) from e_exec

    def _invoke_handler_tool(
        self,
        tool_name: str,
        arg_exprs: List[SexpNode], 
        calling_env: SexpEnvironment, 
        original_expr_str: str
    ) -> TaskResult:
        logging.debug(f"--- _invoke_handler_tool START: tool_name='{tool_name}', arg_exprs={arg_exprs}")

        named_params: Dict[str, Any] = {}

        for i, arg_expr_pair in enumerate(arg_exprs): 
            if not (isinstance(arg_expr_pair, list) and len(arg_expr_pair) == 2 and isinstance(arg_expr_pair[0], Symbol)):
                raise SexpEvaluationError(f"Invalid argument format for tool '{tool_name}'. Expected (key_symbol value_expression), got: {arg_expr_pair}", original_expr_str)
            
            key_symbol = arg_expr_pair[0]
            value_expr_node = arg_expr_pair[1] 
            key_str = key_symbol.value()

            try:
                evaluated_value = self._eval(value_expr_node, calling_env) 
                logging.debug(f"  _invoke_handler_tool: Evaluated value for key '{key_str}' ('{value_expr_node}'): {evaluated_value}")
            except SexpEvaluationError as e_val_eval:
                raise SexpEvaluationError(
                    f"Error evaluating value for '{key_str}' in tool '{tool_name}': {e_val_eval.args[0] if e_val_eval.args else str(e_val_eval)}",
                    expression=original_expr_str, 
                    error_details=f"Failed on value_expr='{e_val_eval.expression if hasattr(e_val_eval, 'expression') else value_expr_node}'. Original detail: {e_val_eval.error_details if hasattr(e_val_eval, 'error_details') else str(e_val_eval)}"
                ) from e_val_eval
            except Exception as e_val_eval: 
                logging.exception(f"  _invoke_handler_tool: Unexpected error evaluating value for key '{key_str}' ('{value_expr_node}'): {e_val_eval}")
                raise SexpEvaluationError(f"Unexpected error evaluating value for '{key_str}' in tool '{tool_name}': {value_expr_node}", original_expr_str, error_details=str(e_val_eval)) from e_val_eval
            
            if key_str == "files":
                if not (isinstance(evaluated_value, list) and all(isinstance(item, str) for item in evaluated_value)):
                    raise SexpEvaluationError(f"'files' argument for tool '{tool_name}' must evaluate to a list of strings, got {type(evaluated_value)}: {evaluated_value!r}", original_expr_str)
                # For tools, 'files' is just another named parameter.
            elif key_str == "context":
                context_dict_for_tool: Optional[Dict[str, Any]] = None
                if isinstance(evaluated_value, list) and all(isinstance(p, list) and len(p)==2 for p in evaluated_value):
                    try:
                        context_dict_for_tool = { (pair[0].value() if isinstance(pair[0], Symbol) else str(pair[0])): pair[1] for pair in evaluated_value }
                    except Exception as e_conv:
                         raise SexpEvaluationError(f"Failed converting 'context' list {evaluated_value!r} to dict for tool '{tool_name}': {e_conv}", original_expr_str) from e_conv
                elif isinstance(evaluated_value, dict):
                    context_dict_for_tool = evaluated_value
                else:
                    raise SexpEvaluationError(f"'context' argument for tool '{tool_name}' must evaluate to a dictionary or a list of pairs, got {type(evaluated_value)}: {evaluated_value!r}", original_expr_str)
                evaluated_value = context_dict_for_tool # Store the processed dictionary

            named_params[key_str] = evaluated_value
        
        logging.debug(f"  Invoking direct tool '{tool_name}' with named_params: {named_params}")
        try:
            tool_result_obj = self.handler._execute_tool(tool_name, named_params)
            if not isinstance(tool_result_obj, TaskResult):
                 logging.error(f"  Tool executor '{tool_name}' did not return a TaskResult object (got {type(tool_result_obj)}).")
                 return TaskResult(
                    status="FAILED", 
                    content=f"Tool '{tool_name}' execution returned invalid type: {type(tool_result_obj)}",
                    notes={"error": TaskFailureError(
                        type="TASK_FAILURE", 
                        reason="output_format_failure", 
                        message=f"Tool '{tool_name}' executor returned invalid type: {type(tool_result_obj)}",
                        details={"tool_name": tool_name, "returned_type": str(type(tool_result_obj))}
                    ).model_dump(exclude_none=True)}
                 )
            logging.debug(f"  Tool '{tool_name}' execution returned: {tool_result_obj.model_dump_json(indent=2)}")
            return tool_result_obj
        except Exception as e_exec:
            logging.exception(f"  Error executing handler tool '{tool_name}': {e_exec}")
            if isinstance(e_exec, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error executing tool '{tool_name}': {e_exec}", original_expr_str, error_details=str(e_exec)) from e_exec
