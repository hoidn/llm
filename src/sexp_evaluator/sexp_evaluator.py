"""
S-expression DSL Evaluator implementation.
Parses and executes workflows defined in S-expression syntax.
Handles workflow composition logic (sequences, conditionals, loops, task/tool calls).
"""

import logging
from typing import Any, Dict, List, Optional, Callable # Removed Tuple, Union, Added Callable

# Core System Dependencies (Injected)
from src.task_system.task_system import TaskSystem
from src.handler.base_handler import BaseHandler
from src.memory.memory_system import MemorySystem

# Sexp Parsing and Environment
from src.sexp_parser.sexp_parser import SexpParser
from src.sexp_evaluator.sexp_environment import SexpEnvironment

# System Models and Errors
from src.system.models import (
    TaskResult, SubtaskRequest, ContextGenerationInput, ContextManagement,
    TaskFailureError, AssociativeMatchResult, MatchTuple,
    TaskError, ContextGenerationInput # Ensure ContextGenerationInput is imported
)
from src.system.errors import SexpSyntaxError, SexpEvaluationError

# Type for Sexp AST nodes (adjust based on SexpParser output)
# Assuming sexpdata-like output: lists, tuples, strings, numbers, bools, None, Symbol objects
from sexpdata import Symbol # Or use str if parser converts symbols
from src.sexp_evaluator.sexp_environment import SexpEnvironment # Ensure this import works
from src.system.errors import SexpSyntaxError, SexpEvaluationError # Ensure this import works


SexpNode = Any # General type hint for AST nodes

logger = logging.getLogger(__name__) # Define logger at module level if not already

class Closure:
    def __init__(self, params_ast: list, body_ast: list, definition_env: 'SexpEnvironment'): # Use forward ref for SexpEnvironment if needed
        """
        Represents a lexically-scoped anonymous function created by 'lambda'.

        Args:
            params_ast: A list of Symbol objects representing the function's formal parameters.
            body_ast: A list of AST nodes representing the function's body expressions.
                        Each element in this list is a complete S-expression AST node.
            definition_env: The SexpEnvironment captured at the time of lambda definition.
                            This environment is the parent for the function's call frame.
        """
        # Validation that params_ast contains only Symbol objects is now done
        # in SexpEvaluator._eval before Closure instantiation.
        
        self.params_ast: list = params_ast # List of Symbol objects
        self.body_ast: list = body_ast     # List of SexpNode (body expressions)
        self.definition_env: SexpEnvironment = definition_env # Captured environment
        
        # For debugging purposes
        param_names_str = ", ".join([p.value() for p in self.params_ast])
        logger.debug(f"Closure created: params=({param_names_str}), num_body_exprs={len(self.body_ast)}, def_env_id={id(self.definition_env)}")

    def __repr__(self):
        param_names = [p.value() for p in self.params_ast]
        return f"<Closure params=({', '.join(param_names)}) body_exprs#={len(self.body_ast)} def_env_id={id(self.definition_env)}>"

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
        self.parser = SexpParser() # Instantiate the Sexp parser

        # Dispatch dictionaries for special forms and primitives
        self.SPECIAL_FORM_HANDLERS: Dict[str, Callable] = {
            "if": self._eval_if_form,
            "let": self._eval_let_form,
            "bind": self._eval_bind_form,
            "progn": self._eval_progn_form,
            "quote": self._eval_quote_form,
            "defatom": self._eval_defatom_form,
            "loop": self._eval_loop_form,
        }
        self.PRIMITIVE_APPLIERS: Dict[str, Callable] = {
            "list": self._apply_list_primitive,
            "get_context": self._apply_get_context_primitive,
            "get-field": self._apply_get_field_primitive,
            "string=?": self._apply_string_equal_primitive,
            "log-message": self._apply_log_message_primitive,
        }
        logging.info("SexpEvaluator initialized.")

    def evaluate_string(
        self,
        sexp_string: str,
        initial_env: Optional[SexpEnvironment] = None
    ) -> Any:
        """
        Parses and evaluates an S-expression string within a given environment.
        Main entry point for executing S-expression workflows.

        Args:
            sexp_string: The string containing the S-expression workflow.
            initial_env: An optional existing SexpEnvironment. If None, a new
                         root environment is created.

        Returns:
            The final result of evaluating the S-expression. This is often the
            result of the last top-level expression. The caller (e.g., Dispatcher)
            might wrap this in a TaskResult if needed.

        Raises:
            SexpSyntaxError: If the input string has invalid S-expression syntax.
            SexpEvaluationError: If runtime errors occur during evaluation (e.g.,
                                 unbound symbol, invalid arguments, type mismatch).
            TaskError: Propagated if an underlying TaskSystem/Handler/MemorySystem
                       call invoked by the S-expression fails.
        """
        logging.info(f"Evaluating S-expression string: {sexp_string[:100]}...")
        try:
            # 1. Parse the string into an AST
            # Parser should return a single top-level AST node.
            parsed_node = self.parser.parse_string(sexp_string)
            logging.debug(f"Parsed S-expression AST: {parsed_node}")

            # 2. Setup Environment
            env = initial_env if initial_env is not None else SexpEnvironment()
            logging.debug(f"Using environment: {env}")

            # 3. Evaluate the single node.
            result = self._eval(parsed_node, env)
            logging.info(f"Finished evaluating S-expression. Result type: {type(result)}")
            return result

        except SexpSyntaxError as e:
            logging.error(f"S-expression syntax error: {e}")
            raise # Re-raise specific syntax error
        except NameError as e:
             # Catch unbound symbols from env.lookup
             logging.error(f"Sexp evaluation error: Unbound symbol - {e}")
             # Fix: Ensure the message format matches the test expectation
             # The NameError 'e' already contains the detailed message from env.lookup
             raise SexpEvaluationError(f"{e}", expression=sexp_string) from e # Use the direct NameError message
        except SexpEvaluationError as e:
            logging.error(f"S-expression evaluation error: {e}")
            # Add expression context if not already present
            if not hasattr(e, 'expression') or not e.expression: # Check if expression attribute exists and is set
                 e.expression = sexp_string
            raise # Re-raise evaluation error
        except Exception as e:
            # Catch any other unexpected errors during evaluation
            logging.exception(f"Unexpected error during S-expression evaluation: {e}")
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

        # 1. Handle Symbols (Lookup)
        if isinstance(node, Symbol):
            symbol_name = node.value()
            # logging.debug(f"Eval Symbol: '{symbol_name}'. Performing lookup.") # Keep existing debug
            try:
                value = env.lookup(symbol_name) # Let NameError propagate if needed
                logger.debug(f"Eval Symbol END: '{symbol_name}' -> {value} (Type={type(value)})")
                return value
            except NameError as e:
                 logger.error(f"Eval Symbol FAILED: Unbound symbol '{symbol_name}'")
                 raise # Re-raise NameError to be caught by evaluate_string

        # 2. Handle Atoms/Literals (Anything not a list/symbol)
        # Includes str, int, float, bool, None, and [] (parsed nil/())
        if not isinstance(node, list):
            logger.debug(f"Eval Literal/Atom: {node}")
            return node

        # 3. Handle Empty List
        if not node: # Empty list '()'
            logger.debug("Eval Empty List: -> []")
            return []

        # --- START LAMBDA DEFINITION HANDLING ---
        op_expr_node = node[0]
        if isinstance(op_expr_node, Symbol) and op_expr_node.value() == "lambda":
            logger.debug(f"Eval: Encountered 'lambda' special form: {node}")
            
            if len(node) < 3: # (lambda (params) body1 ...)
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

            lambda_params_ast = []
            for p_node in params_list_node:
                if not isinstance(p_node, Symbol):
                    raise SexpEvaluationError(
                        f"Lambda parameters must be symbols, got {type(p_node)}: {p_node}", 
                        expression=str(params_list_node)
                    )
                lambda_params_ast.append(p_node)
            
            lambda_body_ast = node[2:] # List of body expressions
            if not lambda_body_ast: # Should be caught by len(node) < 3, but good to be explicit
                 raise SexpEvaluationError("Lambda requires at least one body expression.", expression=str(node))

            logger.debug(f"Creating Closure: params={lambda_params_ast}, num_body_exprs={len(lambda_body_ast)}, def_env_id={id(env)}")
            return Closure(lambda_params_ast, lambda_body_ast, env) # Capture current 'env'
        # --- END LAMBDA DEFINITION HANDLING ---

        # 4. Handle Non-Empty List (Delegate to _eval_list_form)
        logger.debug(f"Eval Non-Empty List (not lambda): Delegating to _eval_list_form for: {node}")
        return self._eval_list_form(node, env)

    def _eval_list_form(self, expr_list: list, env: SexpEnvironment) -> Any:
        """
        Evaluates a non-empty list expression.
        Dispatches to special form handlers or standard operator application.
        """
        original_expr_str = str(expr_list) # For error reporting
        logging.debug(f"--- _eval_list_form START: expr_list={expr_list}, original_expr_str='{original_expr_str}'")

        op_expr_node = expr_list[0]
        arg_expr_nodes = expr_list[1:] # These are UNEVALUATED argument expressions

        resolved_operator: Any

        if isinstance(op_expr_node, Symbol):
            op_name_str = op_expr_node.value()
            # Priority 1: Special Forms (lambda is handled by _eval now, so it won't be caught here)
            # Ensure 'lambda' is NOT in SPECIAL_FORM_HANDLERS if _eval handles it directly.
            if op_name_str in self.SPECIAL_FORM_HANDLERS: # e.g. if, let, defatom, loop
                logger.debug(f"  _eval_list_form: Dispatching to Special Form Handler: {op_name_str}")
                handler_method = self.SPECIAL_FORM_HANDLERS[op_name_str]
                return handler_method(arg_expr_nodes, env, original_expr_str)
            
            # Priority 2: Primitives, Tasks, Tools (use name directly)
            is_primitive = op_name_str in self.PRIMITIVE_APPLIERS
            template_def = self.task_system.find_template(op_name_str)
            is_atomic_task = template_def and template_def.get("type") == "atomic"
            is_handler_tool = op_name_str in self.handler.tool_executors

            if is_primitive or is_atomic_task or is_handler_tool:
                resolved_operator = op_name_str 
                logger.debug(f"  _eval_list_form: Operator '{op_name_str}' identified as known primitive/task/tool name.")
            else:
                # Priority 3: Symbol needs to be evaluated (looked up in env)
                logger.debug(f"  _eval_list_form: Operator symbol '{op_name_str}' is not a fixed operator. Evaluating (looking up) '{op_name_str}'...")
                try:
                    resolved_operator = self._eval(op_expr_node, env) # This will perform env.lookup
                except NameError as ne: 
                    logger.error(f"  _eval_list_form: Operator symbol '{op_name_str}' is unbound during lookup.")
                    raise SexpEvaluationError(f"Unbound symbol or unrecognized operator: {op_name_str}", original_expr_str) from ne
                except SexpEvaluationError as se: 
                    raise se
                except Exception as e: 
                    logger.exception(f"  _eval_list_form: Unexpected error evaluating operator symbol '{op_name_str}': {e}")
                    raise SexpEvaluationError(f"Error evaluating operator symbol '{op_name_str}': {e}", original_expr_str, error_details=str(e)) from e
        elif isinstance(op_expr_node, list): # Operator is a sub-expression, e.g., ((lambda (x) x) 5)
            logger.debug(f"  _eval_list_form: Operator is a complex expression, evaluating it: {op_expr_node}")
            try:
                resolved_operator = self._eval(op_expr_node, env)
            except Exception as e_op_eval: 
                logger.exception(f"  _eval_list_form: Error evaluating complex operator expression '{op_expr_node}': {e_op_eval}")
                if isinstance(e_op_eval, SexpEvaluationError): raise 
                raise SexpEvaluationError(f"Error evaluating operator expression: {op_expr_node}", original_expr_str, error_details=str(e_op_eval)) from e_op_eval
        else: # Operator is a literal, e.g. (1 2 3) - this is an error
            raise SexpEvaluationError(f"Operator in list form must be a symbol or another list, got {type(op_expr_node)}: {op_expr_node}", original_expr_str)

        logger.debug(f"  _eval_list_form: Resolved operator to: {resolved_operator} (Type: {type(resolved_operator)})")
        
        # --- DISPATCH TO _apply_operator ---
        return self._apply_operator(resolved_operator, arg_expr_nodes, env, original_expr_str)

    def _apply_operator(
        self,
        resolved_op: Any, 
        arg_expr_nodes: List[SexpNode],  # UNEVALUATED argument expressions from the call site
        calling_env: SexpEnvironment, # Renamed from 'env' to 'calling_env' for clarity
        original_call_expr_str: str  # String representation of the full call expression (op arg1_expr ...)
    ) -> Any:
        """
        Applies a resolved operator to a list of argument expressions.
        Dispatches to closure application, primitive appliers, task/tool invokers, or Python callables.
        Handles argument evaluation based on the operator type.
        """
        logger.debug(f"--- _apply_operator START: resolved_op_type={type(resolved_op)}, num_arg_exprs={len(arg_expr_nodes)}, original_call_expr_str='{original_call_expr_str}'")

        # --- Case 0: Closure Application (NEW) ---
        if isinstance(resolved_op, Closure):
            closure_to_apply = resolved_op
            logger.debug(f"  _apply_operator: Applying Closure: {closure_to_apply}")

            # 0a. Arity Check
            num_expected_params = len(closure_to_apply.params_ast)
            num_provided_args = len(arg_expr_nodes)
            if num_expected_params != num_provided_args:
                raise SexpEvaluationError(
                    f"Arity mismatch: Closure expects {num_expected_params} arguments, got {num_provided_args} for {original_call_expr_str}",
                    expression=original_call_expr_str
                )

            # 0b. Evaluate arguments in the CALLING environment
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
            
            # 0c. Create new environment frame, linked to Closure's DEFINITION environment
            logger.debug(f"    Creating new call frame. Parent (definition_env from closure) ID: {id(closure_to_apply.definition_env)}")
            call_frame_env = closure_to_apply.definition_env.extend({}) # Extend the *definition* environment

            # 0d. Bind parameters to evaluated arguments in the new frame
            for param_symbol, arg_value in zip(closure_to_apply.params_ast, evaluated_args):
                param_name = param_symbol.value() # Assuming params_ast contains Symbol objects
                call_frame_env.define(param_name, arg_value)
                logger.debug(f"      Bound '{param_name}' = {arg_value} in call frame (id={id(call_frame_env)})")
            
            # 0e. Evaluate body expressions sequentially in the new frame
            final_body_result: Any = [] # Default for empty body (lambda spec requires at least one)
            logger.debug(f"    Evaluating closure body with {len(closure_to_apply.body_ast)} expressions in call frame (id={id(call_frame_env)})")
            for i, body_node in enumerate(closure_to_apply.body_ast):
                try:
                    final_body_result = self._eval(body_node, call_frame_env)
                    logger.debug(f"      Body expression {i+1} evaluated to: {final_body_result}")
                except Exception as e_body_eval:
                    logger.exception(f"      Error evaluating closure body expression {i+1} '{body_node}': {e_body_eval}")
                    if isinstance(e_body_eval, SexpEvaluationError): raise
                    raise SexpEvaluationError(f"Error evaluating closure body expression {i+1}: {body_node}", original_call_expr_str, error_details=str(e_body_eval)) from e_body_eval
            
            logger.debug(f"--- _apply_operator (Closure) END: returning {final_body_result}")
            return final_body_result

        # --- Case 1: Operator is a Name (String) - Could be Primitive, Task, or Tool ---
        elif isinstance(resolved_op, str):
            op_name_str = resolved_op
            logger.debug(f"  _apply_operator: Operator is a name string: '{op_name_str}'")

            # 1a. Check Primitives
            if op_name_str in self.PRIMITIVE_APPLIERS:
                logger.debug(f"  _apply_operator: Dispatching to Primitive Applier: {op_name_str}")
                applier_method = self.PRIMITIVE_APPLIERS[op_name_str]
                # Primitives are responsible for evaluating their arguments from arg_expr_nodes as needed.
                return applier_method(arg_expr_nodes, calling_env, original_call_expr_str)

            # 1b. Check Task System Atomic Templates
            template_def = self.task_system.find_template(op_name_str)
            if template_def and template_def.get("type") == "atomic":
                logger.debug(f"  _apply_operator: Dispatching to Task System Invoker for: {op_name_str}")
                # Task invoker receives unevaluated arg_expr_nodes.
                return self._invoke_task_system(op_name_str, template_def, arg_expr_nodes, calling_env, original_call_expr_str)

            # 1c. Check Handler Tools
            if op_name_str in self.handler.tool_executors:
                logger.debug(f"  _apply_operator: Dispatching to Handler Tool Invoker for: {op_name_str}")
                # Tool invoker receives unevaluated arg_expr_nodes.
                return self._invoke_handler_tool(op_name_str, arg_expr_nodes, calling_env, original_call_expr_str)
            
            # 1d. If op_name_str was resolved from a symbol lookup but isn't a known type of operator
            logger.error(f"  _apply_operator: Operator name '{op_name_str}' was resolved but is not a recognized primitive, task, or tool.")
            raise SexpEvaluationError(f"Operator '{op_name_str}' is not a callable primitive, task, or tool.", original_call_expr_str)

        # --- Case 2: Operator is a (non-Closure) Python Callable ---
        elif callable(resolved_op): # Should be after Closure check
            logger.debug(f"  _apply_operator: Operator is a general Python callable: {resolved_op}. Evaluating arguments...")
            # For general callables, evaluate all arguments first.
            evaluated_args_list = []
            for i, arg_node in enumerate(arg_expr_nodes): # Iterate over original arg expressions
                try:
                    # Evaluate each in the calling_env
                    evaluated_args_list.append(self._eval(arg_node, calling_env)) 
                    logger.debug(f"    Evaluated arg {i+1} ('{arg_node}') to: {evaluated_args_list[-1]}")
                except Exception as e_arg_eval:
                    # Handle errors during argument evaluation for the callable
                    logger.exception(f"  _apply_operator: Error evaluating argument {i+1} ('{arg_node}') for callable '{resolved_op}': {e_arg_eval}")
                    if isinstance(e_arg_eval, SexpEvaluationError): raise # Re-raise if already our type
                    # Wrap other exceptions
                    raise SexpEvaluationError(f"Error evaluating argument {i+1} for callable '{resolved_op}': {arg_node}", original_call_expr_str, error_details=str(e_arg_eval)) from e_arg_eval
            
            try:
                # Call directly with already evaluated args
                result = resolved_op(*evaluated_args_list) 
                logger.debug(f"  _apply_operator: Callable {resolved_op} returned: {result}")
                return result
            except Exception as e:
                logger.exception(f"  _apply_operator: Error calling Python callable {resolved_op} with args {evaluated_args_list}: {e}")
                raise SexpEvaluationError(f"Error invoking callable {resolved_op}: {e}", original_call_expr_str, error_details=str(e)) from e

        # --- Case 3: Operator is Not a Name and Not Callable/Closure ---
        else:
            logger.error(f"  _apply_operator: Operator is not a name and not callable/closure: {resolved_op}")
            raise SexpEvaluationError(f"Cannot apply non-callable/non-closure operator: {resolved_op} (type: {type(resolved_op)})", original_call_expr_str)

    # --- Special Form Handlers (Signatures unchanged, logic relies on _eval) ---

    def _eval_if_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Any:
        """Evaluates the 'if' special form. Args are unevaluated."""
        logging.debug(f"Eval 'if' START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) != 3:
            raise SexpEvaluationError("'if' requires 3 arguments: (if condition then_branch else_branch)", original_expr_str)
        
        cond_expr, then_expr, else_expr = arg_exprs
        
        try:
            condition_result = self._eval(cond_expr, env)
            logging.debug(f"  'if' condition '{cond_expr}' evaluated to: {condition_result}")
        except Exception as e:
            logging.exception(f"  Error evaluating 'if' condition '{cond_expr}': {e}")
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error evaluating 'if' condition: {cond_expr}", original_expr_str, error_details=str(e)) from e

        chosen_branch_expr = then_expr if condition_result else else_expr
        logging.debug(f"  'if' chose branch: {chosen_branch_expr}")
        
        try:
            result = self._eval(chosen_branch_expr, env)
            logging.debug(f"Eval 'if' END: -> {result}")
            return result
        except Exception as e:
            logging.exception(f"  Error evaluating chosen 'if' branch '{chosen_branch_expr}': {e}")
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error evaluating chosen 'if' branch: {chosen_branch_expr}", original_expr_str, error_details=str(e)) from e

    def _eval_let_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Any:
        """Evaluates the 'let' special form. Args are unevaluated."""
        logging.debug(f"Eval 'let' START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) < 1 or not isinstance(arg_exprs[0], list):
            raise SexpEvaluationError("'let' requires a bindings list and at least one body expression: (let ((var expr)...) body...)", original_expr_str)
        
        bindings_list_expr = arg_exprs[0]
        body_exprs = arg_exprs[1:]

        if not body_exprs:
            raise SexpEvaluationError("'let' requires at least one body expression.", original_expr_str)

        logging.debug(f"  'let' processing {len(bindings_list_expr)} binding expressions.")
        let_env = env.extend({}) # Create child environment for the 'let' scope

        for binding_expr in bindings_list_expr:
            binding_expr_repr = str(binding_expr)
            if not (isinstance(binding_expr, list) and len(binding_expr) == 2 and isinstance(binding_expr[0], Symbol)):
                raise SexpEvaluationError(f"Invalid 'let' binding format: expected (symbol expression), got {binding_expr_repr}", original_expr_str)
            
            var_name_symbol = binding_expr[0]
            value_expr = binding_expr[1]
            var_name_str = var_name_symbol.value()

            try:
                # Evaluate value expression in the *outer* environment (env, not let_env yet)
                evaluated_value = self._eval(value_expr, env)
                let_env.define(var_name_str, evaluated_value) # Define in the *new* child environment
                logging.debug(f"    Defined '{var_name_str}' = {evaluated_value} in 'let' scope {id(let_env)}")
            except Exception as e:
                logging.exception(f"  Error evaluating value for 'let' binding '{var_name_str}': {e}")
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating value for 'let' binding '{var_name_str}': {value_expr}", original_expr_str, error_details=str(e)) from e
        
        # Evaluate body expressions in the new 'let' environment
        final_result = [] # Default for empty body (though disallowed by check above)
        for i, body_item_expr in enumerate(body_exprs):
            try:
                final_result = self._eval(body_item_expr, let_env)
                logging.debug(f"  'let' body expression {i+1} evaluated to: {final_result}")
            except Exception as e:
                logging.exception(f"  Error evaluating 'let' body expression {i+1} '{body_item_expr}': {e}")
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating 'let' body expression {i+1}: {body_item_expr}", original_expr_str, error_details=str(e)) from e
                
        logging.debug(f"Eval 'let' END: -> {final_result}")
        return final_result

    def _eval_bind_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Any:
        """Evaluates the 'bind' special form. Args are unevaluated."""
        logging.debug(f"Eval 'bind' START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) != 2 or not isinstance(arg_exprs[0], Symbol):
            raise SexpEvaluationError("'bind' requires a symbol and a value expression: (bind variable_symbol expression)", original_expr_str)

        var_name_symbol = arg_exprs[0]
        value_expr = arg_exprs[1]
        var_name_str = var_name_symbol.value()
        
        logging.debug(f"  Eval 'bind' for variable '{var_name_str}'")
        try:
            evaluated_value = self._eval(value_expr, env) # Evaluate value expression in current env
            env.define(var_name_str, evaluated_value) # Define in *current* environment
            logging.debug(f"  Eval 'bind' END: defined '{var_name_str}' = {evaluated_value} in env {id(env)}")
            return evaluated_value # 'bind' returns the assigned value
        except Exception as e:
            logging.exception(f"  Error evaluating value for 'bind' variable '{var_name_str}': {e}")
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error evaluating value for 'bind' variable '{var_name_str}': {value_expr}", original_expr_str, error_details=str(e)) from e

    def _eval_progn_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Any:
        """Evaluates the 'progn' special form. Args are unevaluated."""
        logging.debug(f"Eval 'progn' START: original_expr_str='{original_expr_str}'")
        final_result = [] # Default result for empty 'progn' is nil/[]
        
        for i, expr in enumerate(arg_exprs):
            try:
                final_result = self._eval(expr, env) # Evaluate each expression sequentially
                logging.debug(f"  'progn' expression {i+1} evaluated to: {final_result}")
            except Exception as e:
                logging.exception(f"  Error evaluating 'progn' expression {i+1} '{expr}': {e}")
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating 'progn' expression {i+1}: {expr}", original_expr_str, error_details=str(e)) from e
                
        logging.debug(f"Eval 'progn' END: -> {final_result}")
        return final_result # Return result of the last expression

    def _eval_quote_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Any:
        """Evaluates the 'quote' special form. Args are unevaluated."""
        logging.debug(f"Eval 'quote' START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) != 1:
            raise SexpEvaluationError("'quote' requires exactly one argument: (quote expression)", original_expr_str)
        
        # Return the argument node *without* evaluating it
        quoted_expression = arg_exprs[0]
        logging.debug(f"Eval 'quote' END: -> {quoted_expression} (unevaluated)")
        return quoted_expression

    def _eval_defatom_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Symbol:
        """Evaluates the 'defatom' special form. Args are unevaluated."""
        logging.debug(f"Eval 'defatom' START: original_expr_str='{original_expr_str}'")

        if len(arg_exprs) < 3: # Task name, params, instructions
            raise SexpEvaluationError(
                f"'defatom' requires at least name, params, and instructions arguments. Got {len(arg_exprs)}.",
                original_expr_str
            )

        task_name_node = arg_exprs[0]
        if not isinstance(task_name_node, Symbol):
            raise SexpEvaluationError(
                f"'defatom' task name must be a Symbol, got {type(task_name_node)}: {task_name_node}",
                original_expr_str
            )
        task_name_str = task_name_node.value()

        params_node = arg_exprs[1]
        if not (isinstance(params_node, list) and len(params_node) > 0 and isinstance(params_node[0], Symbol) and params_node[0].value() == "params"):
            raise SexpEvaluationError(
                f"'defatom' requires a (params ...) definition as the second argument, got: {params_node}",
                original_expr_str
            )
        
        # Extract parameter names for the template's 'params' field and for the callable wrapper
        param_name_strings_for_template = [] # List of param name strings for template_params
        for param_def_item in params_node[1:]:
            if isinstance(param_def_item, Symbol): # Simple form: (params p1 p2)
                param_name_strings_for_template.append(param_def_item.value())
            elif isinstance(param_def_item, list) and len(param_def_item) >= 1 and isinstance(param_def_item[0], Symbol): # Richer form: (params (p1 type?) ...)
                param_name_strings_for_template.append(param_def_item[0].value())
            else:
                 raise SexpEvaluationError(
                    f"Invalid parameter definition format in (params ...). Expected symbol or (symbol type?), got: {param_def_item}",
                    original_expr_str
                )

        template_params = {name: {"description": f"Parameter {name}"} for name in param_name_strings_for_template}


        instructions_node = arg_exprs[2]
        if not (isinstance(instructions_node, list) and len(instructions_node) == 2 and isinstance(instructions_node[0], Symbol) and instructions_node[0].value() == "instructions" and isinstance(instructions_node[1], str)):
            raise SexpEvaluationError(
                f"'defatom' requires an (instructions \"string\") definition as the third argument, got: {instructions_node}",
                original_expr_str
            )
        instructions_str = instructions_node[1]

        optional_args_map = {}
        allowed_optionals = {"subtype", "description", "model"} # Allowed optional keys
        for opt_node in arg_exprs[3:]: # Iterate through remaining arguments
            if not (isinstance(opt_node, list) and len(opt_node) == 2 and isinstance(opt_node[0], Symbol)):
                raise SexpEvaluationError(
                    f"Invalid optional argument format for 'defatom'. Expected (key value_string), got: {opt_node}",
                    original_expr_str
                )
            key_node, value_node = opt_node
            key_str = key_node.value()

            if key_str not in allowed_optionals:
                raise SexpEvaluationError(f"Unknown optional argument '{key_str}' for 'defatom'. Allowed: {allowed_optionals}", original_expr_str)
            
            # Ensure value is a string for these optional args
            if not isinstance(value_node, str):
                 raise SexpEvaluationError(f"Value for optional argument '{key_str}' must be a string, got {type(value_node)}: {value_node}", original_expr_str)
            optional_args_map[key_str] = value_node
        
        template_dict = {
            "name": task_name_str,
            "type": "atomic", # Hardcoded as per ADR
            "subtype": optional_args_map.get("subtype", "standard"),
            "description": optional_args_map.get("description", f"Dynamically defined task: {task_name_str}"),
            "params": template_params,
            "instructions": instructions_str,
        }
        if "model" in optional_args_map: # Only add model if explicitly provided
            template_dict["model"] = optional_args_map["model"]

        logging.debug(f"Constructed template dictionary for '{task_name_str}': {template_dict}")

        try:
            logging.info(f"Registering dynamic atomic task template: '{task_name_str}'")
            # Assuming register_template returns bool or raises error
            self.task_system.register_template(template_dict) 
            # ADR suggests TaskSystem.register_template might warn on overwrite.
            # If it returns False on failure (e.g. validation), that should be handled.
        except Exception as e: # Catch specific errors from TaskSystem if possible
            logging.exception(f"Error registering template '{task_name_str}' with TaskSystem: {e}")
            raise SexpEvaluationError(f"Failed to register template '{task_name_str}' with TaskSystem: {e}", original_expr_str, error_details=str(e)) from e

        # --- (Recommended) Lexical Binding ---
        # Create a callable wrapper that invokes this newly defined task.
        # The wrapper will take positional arguments corresponding to the defined params.
        
        # Define the actual Python function that will be the wrapper
        def defatom_task_wrapper(*args):
            logger.debug(f"defatom_task_wrapper for '{task_name_str}' called with {len(args)} args: {args}")
            
            # Check arity
            if len(args) != len(param_name_strings_for_template):
                raise SexpEvaluationError(
                    f"Task '{task_name_str}' (defined by defatom) expects {len(param_name_strings_for_template)} arguments, got {len(args)}.",
                    expression=f"call to {task_name_str}" # Approximate expression
                )
            
            # Construct inputs dictionary for SubtaskRequest
            # The order of param_name_strings_for_template matches the order of *args
            inputs_dict = {name: val for name, val in zip(param_name_strings_for_template, args)}
            
            request = SubtaskRequest(
                task_id=f"defatom_call_{task_name_str}_{id(args)}",
                type="atomic",
                name=task_name_str,
                inputs=inputs_dict
            )
            logging.debug(f"  defatom_task_wrapper: Invoking TaskSystem for '{task_name_str}' with request: {request.model_dump_json(indent=2)}")
            
            # Call the TaskSystem directly
            # This is a direct Python call, not going through SexpEvaluator's _invoke_task_system
            try:
                task_result: TaskResult = self.task_system.execute_atomic_template(request)
                return task_result # Return the TaskResult object
            except Exception as e_exec:
                logging.exception(f"  Error executing defatom task '{task_name_str}' via wrapper: {e_exec}")
                # Propagate as SexpEvaluationError to be caught by the evaluator's error handling
                raise SexpEvaluationError(f"Error executing defatom task '{task_name_str}': {e_exec}", expression=f"call to {task_name_str}", error_details=str(e_exec)) from e_exec

        # Bind the wrapper function to the task name in the *current* lexical environment
        env.define(task_name_str, defatom_task_wrapper)
        logging.info(f"Successfully registered and lexically bound dynamic task '{task_name_str}'.")
        # --- End Lexical Binding ---

        return task_name_node # Return the Symbol

    def _eval_loop_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Any:
        """Evaluates the 'loop' special form. Args are unevaluated."""
        logging.debug(f"Eval 'loop' START: original_expr_str='{original_expr_str}'")

        if len(arg_exprs) != 2:
            raise SexpEvaluationError(f"Loop requires exactly 2 arguments: count_expression and body_expression. Got {len(arg_exprs)}.", original_expr_str)
        
        count_expr, body_expr = arg_exprs

        try:
            logging.debug(f"  Evaluating loop count expression: {count_expr}")
            count_value = self._eval(count_expr, env)
            logging.debug(f"  Loop count expression evaluated to: {count_value} (Type: {type(count_value)})")
        except SexpEvaluationError as e_count: # Catch specific SexpEvaluationError
            logging.exception(f"Error evaluating loop count expression '{count_expr}': {e_count}")
            # Re-raise, but ensure the outer expression (original_expr_str) is part of the new error if not already
            # The original error e_count.expression should be the count_expr itself.
            raise SexpEvaluationError(
                f"Error evaluating loop count expression: {e_count.args[0] if e_count.args else str(e_count)}",
                expression=original_expr_str, # The full (loop ...)
                error_details=f"Failed on count_expr='{e_count.expression if hasattr(e_count, 'expression') else count_expr}'. Original detail: {e_count.error_details if hasattr(e_count, 'error_details') else str(e_count)}"
            ) from e_count
        except Exception as e: # Catch other errors
            logging.exception(f"Error evaluating loop count expression '{count_expr}': {e}")
            raise SexpEvaluationError(f"Error evaluating loop count expression: {count_expr}", original_expr_str, error_details=str(e)) from e

        if not isinstance(count_value, int):
            raise SexpEvaluationError(f"Loop count must evaluate to an integer.", original_expr_str, f"Got type: {type(count_value)} for count '{count_value}'")
        if count_value < 0:
            raise SexpEvaluationError(f"Loop count must be non-negative.", original_expr_str, f"Got value: {count_value}")

        n = count_value
        if n == 0:
            logging.debug("Loop count is 0, skipping body execution and returning [].")
            return [] 

        last_result: Any = [] # Initialize to nil/empty list
        logging.debug(f"Starting loop execution for {n} iterations.")
        for i in range(n):
            iteration = i + 1
            logging.debug(f"  Loop iteration {iteration}/{n}. Evaluating body: {body_expr}")
            try:
                last_result = self._eval(body_expr, env)
                logging.debug(f"  Iteration {iteration}/{n} result: {last_result}")
            except SexpEvaluationError as e_body:
                logging.exception(f"Error evaluating loop body during iteration {iteration}/{n} for '{body_expr}': {e_body}")
                # Construct a new error that includes the loop context and the body error
                raise SexpEvaluationError(
                    f"Error during loop iteration {iteration}/{n}: {e_body.args[0] if e_body.args else str(e_body)}",
                    expression=original_expr_str, # The full (loop ...) expression
                    error_details=f"Failed on body_expr='{e_body.expression if hasattr(e_body, 'expression') else body_expr}'. Original detail: {e_body.error_details if hasattr(e_body, 'error_details') else str(e_body)}"
                ) from e_body
            except Exception as e: # Catch other unexpected errors
                logging.exception(f"Unexpected error evaluating loop body during iteration {iteration}/{n} for '{body_expr}': {e}")
                raise SexpEvaluationError(
                    f"Unexpected error during loop iteration {iteration}/{n} processing body '{body_expr}': {str(e)}",
                    expression=original_expr_str,
                    error_details=str(e)
                ) from e
                
        logging.debug(f"Loop finished after {n} iterations. Returning last result: {last_result}")
        return last_result

    # --- Primitive Appliers (Updated Signatures & Logic) ---

    def _apply_list_primitive(
        self,
        arg_exprs: List[SexpNode], # UNEVALUATED argument expressions
        env: SexpEnvironment,
        original_expr_str: str
    ) -> List[Any]:
        """Applies the 'list' primitive. Evaluates each argument expression."""
        logging.debug(f"Apply 'list' primitive START: arg_exprs={arg_exprs}, original_expr_str='{original_expr_str}'")
        evaluated_args = []
        for i, arg_node in enumerate(arg_exprs):
            try:
                evaluated_args.append(self._eval(arg_node, env))
                logging.debug(f"  _apply_list_primitive: Evaluated arg {i+1} ('{arg_node}') to: {evaluated_args[-1]}")
            except Exception as e_arg_eval:
                logging.exception(f"  _apply_list_primitive: Error evaluating argument {i+1} ('{arg_node}'): {e_arg_eval}")
                if isinstance(e_arg_eval, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating argument {i+1} for 'list': {arg_node}", original_expr_str, error_details=str(e_arg_eval)) from e_arg_eval
        
        logging.debug(f"Apply 'list' primitive END: -> {evaluated_args}")
        return evaluated_args

    def _apply_get_context_primitive(
        self,
        arg_exprs: List[SexpNode], # UNEVALUATED argument expressions [(key value_expr), ...]
        env: SexpEnvironment,
        original_expr_str: str
    ) -> List[str]:
        """
        Applies the 'get_context' primitive.
        Parses (key value_expr) pairs from arg_exprs, evaluates each value_expr,
        constructs ContextGenerationInput, calls memory_system, and returns file paths.
        """
        logging.debug(f"Apply 'get_context' primitive START: arg_exprs={arg_exprs}, original_expr_str='{original_expr_str}'")
        
        context_params: Dict[str, Any] = {}
        for i, arg_expr_pair in enumerate(arg_exprs): # Iterate over the unevaluated arg expressions
            if not (isinstance(arg_expr_pair, list) and len(arg_expr_pair) == 2 and isinstance(arg_expr_pair[0], Symbol)):
                raise SexpEvaluationError(f"Invalid argument format for 'get_context'. Expected (key_symbol value_expression), got: {arg_expr_pair}", original_expr_str)
            
            key_symbol = arg_expr_pair[0]
            value_expr_node = arg_expr_pair[1] # This is the UNEVALUATED value expression
            key_str = key_symbol.value()

            # Evaluate the value_expr_node here
            try:
                evaluated_value = self._eval(value_expr_node, env) 
                logging.debug(f"  _apply_get_context: Evaluated value for key '{key_str}' ('{value_expr_node}'): {evaluated_value}")
            except SexpEvaluationError as e_val_eval:
                # If _eval raises SexpEvaluationError, it should already have the specific failing sub-expression.
                # We want to add the context of the 'get_context' call.
                raise SexpEvaluationError(
                    f"Error evaluating value for '{key_str}' in 'get_context': {e_val_eval.args[0] if e_val_eval.args else str(e_val_eval)}",
                    expression=original_expr_str, # The full (get_context ...)
                    error_details=f"Failed on value_expr='{e_val_eval.expression if hasattr(e_val_eval, 'expression') else value_expr_node}'. Original detail: {e_val_eval.error_details if hasattr(e_val_eval, 'error_details') else str(e_val_eval)}"
                ) from e_val_eval
            except Exception as e_val_eval:
                logging.exception(f"  _apply_get_context: Error evaluating value for key '{key_str}' ('{value_expr_node}'): {e_val_eval}")
                raise SexpEvaluationError(f"Error evaluating value for '{key_str}' in 'get_context': {value_expr_node}", original_expr_str, error_details=str(e_val_eval)) from e_val_eval
            
            # Special validation for matching_strategy
            if key_str == "matching_strategy":
                allowed_strategies = {'content', 'metadata'}
                if not isinstance(evaluated_value, str) or evaluated_value not in allowed_strategies: # Check the evaluated value
                    raise SexpEvaluationError(f"Invalid value for 'matching_strategy'. Expected 'content' or 'metadata', got: {evaluated_value!r}", original_expr_str)
            
            context_params[key_str] = evaluated_value # Store the evaluated value

        if not context_params: # Should have at least one param like 'query'
            raise SexpEvaluationError("'get_context' requires at least one parameter like (query ...).", original_expr_str)

        try:
            # Convert 'inputs' if it's a list of pairs (already evaluated from quote) to a dictionary
            if "inputs" in context_params and isinstance(context_params["inputs"], list):
                inputs_list_of_pairs = context_params["inputs"] # This list contains already evaluated items if from (quote ((key val)...))
                inputs_dict = {}
                for pair in inputs_list_of_pairs: 
                    # If (quote ((key val)...)), then pair is [Symbol('key'), 'val']
                    if isinstance(pair, list) and len(pair) == 2:
                        inner_key_node = pair[0]
                        inner_val = pair[1] # This is already evaluated if from (quote ((key val)))
                        inner_key_str = inner_key_node.value() if isinstance(inner_key_node, Symbol) else str(inner_key_node)
                        inputs_dict[inner_key_str] = inner_val
                    else: 
                        # This path indicates the (quote ((key val)...)) structure was not correctly formed or evaluated
                        raise SexpEvaluationError(f"Invalid pair format in 'inputs' list after evaluation: {pair}. Expected [Symbol, value] or [str, value].", original_expr_str)
                context_params["inputs"] = inputs_dict
                logging.debug(f"  _apply_get_context: Converted 'inputs' list (post-eval) to dict: {context_params['inputs']}")
            
            context_input_obj = ContextGenerationInput(**context_params)
        except Exception as e: # Catches Pydantic validation errors
            logging.exception(f"  Error creating ContextGenerationInput from params {context_params}: {e}")
            raise SexpEvaluationError(f"Failed creating ContextGenerationInput for 'get_context': {e}", original_expr_str, error_details=str(e)) from e

        try:
            logging.debug(f"  Calling memory_system.get_relevant_context_for with: {context_input_obj}")
            match_result: AssociativeMatchResult = self.memory_system.get_relevant_context_for(context_input_obj)
        except Exception as e: # Catch errors from MemorySystem call itself
            logging.exception(f"  MemorySystem.get_relevant_context_for failed: {e}")
            raise SexpEvaluationError("Context retrieval failed during MemorySystem call.", original_expr_str, error_details=str(e)) from e

        if match_result.error:
            logging.error(f"  MemorySystem returned error for get_context: {match_result.error}")
            raise SexpEvaluationError("Context retrieval failed (MemorySystem error).", original_expr_str, error_details=match_result.error)

        file_paths = [m.path for m in match_result.matches if isinstance(m, MatchTuple)]
        logging.debug(f"Apply 'get_context' primitive END: -> {file_paths}")
        return file_paths

    def _apply_get_field_primitive(
        self,
        arg_exprs: List[SexpNode], # Expecting (object-or-dict-expr field-name-expr)
        calling_env: SexpEnvironment,
        original_call_expr_str: str
    ) -> Any:
        logger.debug(f"Apply 'get-field' primitive: {original_call_expr_str}")
        if len(arg_exprs) != 2:
            raise SexpEvaluationError("'get-field' requires exactly two arguments: (get-field <object/dict> <field-name>)", original_call_expr_str)

        obj_expr = arg_exprs[0]
        field_name_expr = arg_exprs[1]

        # Evaluate arguments
        try:
            target_obj = self._eval(obj_expr, calling_env)
            field_name_val = self._eval(field_name_expr, calling_env)
        except Exception as e_eval:
            raise SexpEvaluationError(f"Error evaluating arguments for 'get-field': {e_eval}", original_call_expr_str, error_details=str(e_eval)) from e_eval

        if not isinstance(field_name_val, str):
            # Allow Symbol for field name too, convert to string
            if isinstance(field_name_val, Symbol):
                field_name_val = field_name_val.value()
            else:
                raise SexpEvaluationError(f"'get-field' field name must be a string or symbol, got {type(field_name_val)}: {field_name_val!r}", original_call_expr_str)
        
        logger.debug(f"  'get-field': target_obj type={type(target_obj)}, field_name_val='{field_name_val}'")

        try:
            if isinstance(target_obj, dict):
                if field_name_val not in target_obj:
                    logger.warning(f"  'get-field': Key '{field_name_val}' not found in dict {list(target_obj.keys())}. Returning None.")
                    return None 
                return target_obj.get(field_name_val)
            # Check for Pydantic BaseModel or similar attribute access
            elif hasattr(target_obj, '__class__') and hasattr(target_obj.__class__, 'model_fields') and hasattr(target_obj, field_name_val):
                logger.debug(f"  'get-field': Accessing attribute '{field_name_val}' from Pydantic-like object.")
                return getattr(target_obj, field_name_val)
            elif hasattr(target_obj, field_name_val):
                logger.debug(f"  'get-field': Accessing attribute '{field_name_val}' from object.")
                return getattr(target_obj, field_name_val)
            else:
                # Check if target_obj is a TaskResult and field_name_val is 'content' or 'status' etc.
                # This case might be covered by Pydantic check if TaskResult is a Pydantic model.
                # If TaskResult is returned as a dict from some layers, the dict check above handles it.
                logger.warning(f"  'get-field': Field or attribute '{field_name_val}' not found in object of type {type(target_obj)}. Returning None.")
                return None
        except Exception as e_access:
            logger.exception(f"  Error accessing field '{field_name_val}' in 'get-field': {e_access}")
            raise SexpEvaluationError(f"Error accessing field '{field_name_val}': {e_access}", original_call_expr_str, error_details=str(e_access)) from e_access

    def _apply_string_equal_primitive(
        self,
        arg_exprs: List[SexpNode], # Expecting (str1-expr str2-expr)
        calling_env: SexpEnvironment,
        original_call_expr_str: str
    ) -> bool:
        logger.debug(f"Apply 'string=?' primitive: {original_call_expr_str}")
        if len(arg_exprs) != 2:
            raise SexpEvaluationError("'string=?' requires exactly two string arguments.", original_call_expr_str)

        # Evaluate arguments
        try:
            str1 = self._eval(arg_exprs[0], calling_env)
            str2 = self._eval(arg_exprs[1], calling_env)
        except Exception as e_eval:
            raise SexpEvaluationError(f"Error evaluating arguments for 'string=?': {e_eval}", original_call_expr_str, error_details=str(e_eval)) from e_eval

        if not isinstance(str1, str) or not isinstance(str2, str):
            raise SexpEvaluationError(f"'string=?' arguments must be strings. Got: {type(str1)}, {type(str2)}", original_call_expr_str)
        
        result = (str1 == str2)
        logger.debug(f"  'string=?': '{str1}' == '{str2}' -> {result}")
        return result

    def _apply_log_message_primitive(
        self,
        arg_exprs: List[SexpNode],
        calling_env: SexpEnvironment,
        original_call_expr_str: str
    ) -> Any: # Returns the message or nil
        logger.debug(f"Apply 'log-message' primitive: {original_call_expr_str}")
        if not arg_exprs:
            logger.info("SexpLog: (log-message) called with no arguments.") # Use info for user-facing logs
            return [] # nil
        
        evaluated_args = []
        for arg_expr in arg_exprs:
            try:
                evaluated_args.append(self._eval(arg_expr, calling_env))
            except Exception as e_eval:
                logger.error(f"SexpLog: Error evaluating arg for log-message: {arg_expr} -> {e_eval}")
                evaluated_args.append(f"<Error evaluating: {arg_expr}>")

        log_output = " ".join(map(str, evaluated_args))
        logger.info(f"SexpLog: {log_output}") # Use standard logger.info for SexpLog output
        return log_output # Return the logged string, or [] for nil if preferred

    # --- Invocation Helpers (Updated Signatures & Logic) ---

    def _invoke_task_system(
        self,
        task_name: str,
        template_def: Dict[str, Any],
        arg_exprs: List[SexpNode], # UNEVALUATED arg expressions [(key value_expr), ...]
        calling_env: SexpEnvironment, # Renamed from env for clarity
        original_expr_str: str
    ) -> TaskResult:
        logging.debug(f"--- _invoke_task_system START: task_name='{task_name}', arg_exprs={arg_exprs}")
        
        named_params: Dict[str, Any] = {}
        file_paths: Optional[List[str]] = None
        context_settings_dict: Optional[Dict[str, Any]] = None # Store as dict first

        for i, arg_expr_pair in enumerate(arg_exprs): # Iterate over the unevaluated arg expressions
            if not (isinstance(arg_expr_pair, list) and len(arg_expr_pair) == 2 and isinstance(arg_expr_pair[0], Symbol)):
                raise SexpEvaluationError(f"Invalid argument format for task '{task_name}'. Expected (key_symbol value_expression), got: {arg_expr_pair}", original_expr_str)
            
            key_symbol = arg_expr_pair[0]
            value_expr_node = arg_expr_pair[1] # This is the UNEVALUATED value expression
            key_str = key_symbol.value()

            # Evaluate the value_expr_node here, in the calling_env
            try:
                evaluated_value = self._eval(value_expr_node, calling_env) 
                logging.debug(f"  _invoke_task_system: Evaluated value for key '{key_str}' ('{value_expr_node}'): {evaluated_value}")
            except SexpEvaluationError as e_val_eval:
                # If _eval raises SexpEvaluationError, it should already have the specific failing sub-expression.
                # We want to add the context of the task call.
                raise SexpEvaluationError(
                    f"Error evaluating value for '{key_str}' in task '{task_name}': {e_val_eval.args[0] if e_val_eval.args else str(e_val_eval)}",
                    expression=original_expr_str, # The full task call expression
                    error_details=f"Failed on value_expr='{e_val_eval.expression if hasattr(e_val_eval, 'expression') else value_expr_node}'. Original detail: {e_val_eval.error_details if hasattr(e_val_eval, 'error_details') else str(e_val_eval)}"
                ) from e_val_eval
            except Exception as e_val_eval: # Catch other unexpected errors during value evaluation
                logging.exception(f"  _invoke_task_system: Unexpected error evaluating value for key '{key_str}' ('{value_expr_node}'): {e_val_eval}")
                raise SexpEvaluationError(f"Unexpected error evaluating value for '{key_str}' in task '{task_name}': {value_expr_node}", original_expr_str, error_details=str(e_val_eval)) from e_val_eval

            # Process special keys or add to named_params
            if key_str == "files":
                if not (isinstance(evaluated_value, list) and all(isinstance(item, str) for item in evaluated_value)):
                    raise SexpEvaluationError(f"'files' argument for task '{task_name}' must evaluate to a list of strings, got {type(evaluated_value)}: {evaluated_value!r}", original_expr_str)
                file_paths = evaluated_value
            elif key_str == "context":
                # Value for 'context' should be a list of pairs (from quote) or a dict (from var)
                if isinstance(evaluated_value, list) and all(isinstance(p, list) and len(p)==2 for p in evaluated_value):
                    try:
                        # Convert list of pairs (key_node, value_already_eval_from_quote) to dict
                        context_settings_dict = { (pair[0].value() if isinstance(pair[0], Symbol) else str(pair[0])): pair[1] for pair in evaluated_value }
                    except Exception as e_conv:
                         raise SexpEvaluationError(f"Failed converting 'context' list {evaluated_value!r} to dict for task '{task_name}': {e_conv}", original_expr_str) from e_conv
                elif isinstance(evaluated_value, dict):
                    context_settings_dict = evaluated_value
                else:
                    raise SexpEvaluationError(f"'context' argument for task '{task_name}' must evaluate to a dictionary or a list of pairs, got {type(evaluated_value)}: {evaluated_value!r}", original_expr_str)
            else: # Regular named parameter
                named_params[key_str] = evaluated_value
        
        context_mgmt_obj: Optional[ContextManagement] = None
        if context_settings_dict:
            try:
                context_mgmt_obj = ContextManagement(**context_settings_dict) # Pydantic model validation
            except Exception as e_cm_val: # Catches Pydantic validation errors
                raise SexpEvaluationError(f"Invalid 'context' settings for task '{task_name}': {e_cm_val}", original_expr_str) from e_cm_val

        request = SubtaskRequest(
            task_id=f"sexp_task_{task_name}_{id(original_expr_str)}", # Use a more unique task_id
            type="atomic", 
            name=task_name,
            inputs=named_params,
            file_paths=file_paths,
            context_management=context_mgmt_obj
        )
        logging.debug(f"  Constructed SubtaskRequest for '{task_name}': {request.model_dump_json(indent=2)}")

        try:
            task_result_obj = self.task_system.execute_atomic_template(request)
            # Ensure TaskResult is returned
            if not isinstance(task_result_obj, TaskResult):
                 logging.error(f"  Task executor for '{task_name}' did not return a TaskResult object (got {type(task_result_obj)}).")
                 # Fallback to create a FAILED TaskResult
                 return TaskResult(
                    status="FAILED", 
                    content=f"Task '{task_name}' execution returned invalid type: {type(task_result_obj)}",
                    notes={"error": TaskFailureError(
                        type="TASK_FAILURE", # Corrected type
                        reason="output_format_failure", # More fitting reason
                        message=f"Task '{task_name}' executor returned invalid type: {type(task_result_obj)}", # More specific message
                        details={"task_name": task_name, "returned_type": str(type(task_result_obj))} # Add details
                    ).model_dump(exclude_none=True)}
                 )
            # Robust logging for TaskResult
            try:
                debug_dump = task_result_obj.model_dump_json(indent=2)
            except Exception: 
                debug_dump = str(task_result_obj) # Fallback for serialization issues
            logging.debug(f"  Task '{task_name}' execution returned: {debug_dump}")
            return task_result_obj
        except Exception as e_exec:
            logging.exception(f"  Error executing atomic task '{task_name}': {e_exec}")
            if isinstance(e_exec, SexpEvaluationError): raise # Re-raise if already our specific error
            # Wrap other exceptions
            raise SexpEvaluationError(f"Error executing task '{task_name}': {e_exec}", original_expr_str, error_details=str(e_exec)) from e_exec

    def _invoke_handler_tool(
        self,
        tool_name: str,
        arg_exprs: List[SexpNode], # UNEVALUATED arg expressions [(key value_expr), ...]
        calling_env: SexpEnvironment, # Renamed from env for clarity
        original_expr_str: str
    ) -> TaskResult:
        logging.debug(f"--- _invoke_handler_tool START: tool_name='{tool_name}', arg_exprs={arg_exprs}")

        named_params: Dict[str, Any] = {}
        # Handler tools receive all arguments as named_params.

        for i, arg_expr_pair in enumerate(arg_exprs): # Iterate over the unevaluated arg expressions
            if not (isinstance(arg_expr_pair, list) and len(arg_expr_pair) == 2 and isinstance(arg_expr_pair[0], Symbol)):
                raise SexpEvaluationError(f"Invalid argument format for tool '{tool_name}'. Expected (key_symbol value_expression), got: {arg_expr_pair}", original_expr_str)
            
            key_symbol = arg_expr_pair[0]
            value_expr_node = arg_expr_pair[1] # This is the UNEVALUATED value expression
            key_str = key_symbol.value()

            # Evaluate the value_expr_node here, in the calling_env
            try:
                evaluated_value = self._eval(value_expr_node, calling_env) 
                logging.debug(f"  _invoke_handler_tool: Evaluated value for key '{key_str}' ('{value_expr_node}'): {evaluated_value}")
            except SexpEvaluationError as e_val_eval:
                # If _eval raises SexpEvaluationError, it should already have the specific failing sub-expression.
                # We want to add the context of the tool call.
                raise SexpEvaluationError(
                    f"Error evaluating value for '{key_str}' in tool '{tool_name}': {e_val_eval.args[0] if e_val_eval.args else str(e_val_eval)}",
                    expression=original_expr_str, # The full tool call expression
                    error_details=f"Failed on value_expr='{e_val_eval.expression if hasattr(e_val_eval, 'expression') else value_expr_node}'. Original detail: {e_val_eval.error_details if hasattr(e_val_eval, 'error_details') else str(e_val_eval)}"
                ) from e_val_eval
            except Exception as e_val_eval: # Catch other unexpected errors during value evaluation
                logging.exception(f"  _invoke_handler_tool: Unexpected error evaluating value for key '{key_str}' ('{value_expr_node}'): {e_val_eval}")
                raise SexpEvaluationError(f"Unexpected error evaluating value for '{key_str}' in tool '{tool_name}': {value_expr_node}", original_expr_str, error_details=str(e_val_eval)) from e_val_eval
            
            named_params[key_str] = evaluated_value
        
        logging.debug(f"  Invoking direct tool '{tool_name}' with named_params: {named_params}")
        try:
            # Assuming handler._execute_tool expects a dictionary of evaluated named parameters
            tool_result_obj = self.handler._execute_tool(tool_name, named_params)
            # Ensure TaskResult is returned
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
