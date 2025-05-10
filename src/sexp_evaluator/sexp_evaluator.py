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
    TaskFailureError, AssociativeMatchResult,
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
        # <<< ADD LOGGING >>>
        logger.debug(f"*** SexpEvaluator.__init__: Received TaskSystem instance ID = {id(task_system)}")
        # <<< END LOGGING >>>
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
            "iterative-loop": self.special_form_processor.handle_iterative_loop,
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
            "not": self.primitive_processor.apply_not_primitive,
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
            # --- REMOVED DEBUG LOGGING ---

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
        # --- REMOVED DEBUG LOGGING ---

        if isinstance(node, Symbol):
            symbol_name = node.value()
            # --- REMOVED DEBUG LOGGING ---
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
                # First try the standard attribute 'x' which is the primary field in sexpdata.Quoted
                if hasattr(node, 'x'):
                    actual_val = node.x
                    logging.debug(f"Eval Quoted: Extracted value from 'x' attribute: {actual_val!r}")
                    return actual_val
                
                # Try alternative attribute names that might be used in different versions
                for attr in ['val', 'value', '_value']:
                    if hasattr(node, attr):
                        actual_val = getattr(node, attr)
                        logging.debug(f"Eval Quoted: Found alternative attribute '{attr}': {actual_val!r}")
                        return actual_val
                
                # If we still don't have a value, try to get the first item if it's a sequence
                if hasattr(node, '__getitem__'):
                    try:
                        actual_val = node[0]
                        logging.debug(f"Eval Quoted: Extracted first item: {actual_val!r}")
                        return actual_val
                    except (IndexError, TypeError):
                        pass
                
                # If we get here, we couldn't extract a value
                # Try one more approach - maybe it's a tuple with a specific structure
                if hasattr(node, '__iter__'):
                    try:
                        for item in node:
                            logging.debug(f"Eval Quoted: Trying item from iteration: {item!r}")
                            return item  # Return the first item from iteration
                    except Exception:
                        pass
                
                # If we get here, we couldn't extract a value
                logging.error(f"Eval Quoted: Could not extract value from {node!r}")
                raise SexpEvaluationError(f"Could not extract value from Quoted object: {node!r}", expression=str(node))
            except Exception as e:
                # This might happen if our understanding of sexpdata.Quoted is off
                # or if a different type of Quoted object is encountered.
                logging.exception(f"Eval Quoted: Error accessing quoted value for {node!r}: {e}")
                raise SexpEvaluationError(f"Error accessing quoted value: {node!r} - {str(e)}", expression=str(node))

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
            
            # --- START FIX for Lexical Scope (Attempt 2) ---
            # Create new call frame: Its parent MUST be the closure's definition environment
            definition_env_for_closure = closure_to_apply.definition_env
            logger.debug(f"    Creating new call frame. Parent (definition_env) ID: {id(definition_env_for_closure)}")
            # Use the definition_env's extend method to link correctly
            # The new bindings (parameters) are added to this new frame.
            call_frame_bindings = {} # Start with empty bindings for the call frame itself
            for param_symbol, arg_value in zip(closure_to_apply.params_ast, evaluated_args):
                param_name = param_symbol.value()
                call_frame_bindings[param_name] = arg_value
                logger.debug(f"      Prepared binding '{param_name}' = {arg_value} for call frame")

            # Create the call frame environment, extending the *definition* environment
            call_frame_env = definition_env_for_closure.extend(call_frame_bindings)
            logger.debug(f"    Created call_frame_env id={id(call_frame_env)} extending definition_env id={id(definition_env_for_closure)} with bindings: {list(call_frame_bindings.keys())}")
            # --- END FIX for Lexical Scope (Attempt 2) ---
            
            # --- START FIX for *loop-config* ---
            # Check if the *calling* environment (passed into _apply_operator) has *loop-config*
            # If so, define it in the newly created call frame so the body can see it.
            try:
                loop_config_val = calling_env.lookup('*loop-config*')
                if loop_config_val is not None: # Be explicit, maybe lookup returns None legitimately
                    logger.debug(f"    Injecting '*loop-config*' from calling_env into call_frame_env id={id(call_frame_env)}")
                    call_frame_env.define('*loop-config*', loop_config_val)
            except NameError:
                # *loop-config* was not in the calling environment, that's fine.
                logger.debug("    '*loop-config*' not found in calling_env, not injecting.")
                # Try to look for it in parent environments
                parent_env = calling_env
                while hasattr(parent_env, '_parent') and parent_env._parent is not None:
                    parent_env = parent_env._parent
                    try:
                        loop_config_val = parent_env.lookup('*loop-config*')
                        if loop_config_val is not None:
                            logger.debug(f"    Found '*loop-config*' in parent environment id={id(parent_env)}, injecting into call_frame_env")
                            call_frame_env.define('*loop-config*', loop_config_val)
                            break
                    except NameError:
                        continue
            # --- END FIX for *loop-config* ---

            # Remove the old loop that defined bindings directly in call_frame_env
            # for param_symbol, arg_value in zip(closure_to_apply.params_ast, evaluated_args):
            #    param_name = param_symbol.value()
            #    call_frame_env.define(param_name, arg_value) # Define params in the new call_frame_env
            #    logger.debug(f"      Bound '{param_name}' = {arg_value} in call frame (id={id(call_frame_env)})")

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
        logger.debug(f"    Invoking {phase_name} (Iter {iteration}) with {len(args_list)} args in env_for_call={id(env_for_eval)}")
        logger.debug(f"    Args types: {[type(arg) for arg in args_list]}")
        logger.debug(f"    Args values: {[str(arg)[:100] + '...' if len(str(arg)) > 100 else str(arg) for arg in args_list]}")
        try:
            # Pass arguments directly without quoting - phase functions expect evaluated values
            conceptual_call_str = f"({phase_name} iter={iteration})" # For potential error messages
            
            if isinstance(func_to_call, Closure):
                # For Closures, we need to create a call frame and evaluate the body
                # This is similar to what _apply_operator does for Closures
                if len(func_to_call.params_ast) != len(args_list):
                    raise SexpEvaluationError(
                        f"Arity mismatch: {phase_name} function expects {len(func_to_call.params_ast)} arguments, got {len(args_list)}",
                        original_loop_expr
                    )
                
                # Create call frame extending the closure's definition environment
                call_frame_bindings = {}
                for param_symbol, arg_value in zip(func_to_call.params_ast, args_list):
                    param_name = param_symbol.value()
                    call_frame_bindings[param_name] = arg_value
                
                call_frame_env = func_to_call.definition_env.extend(call_frame_bindings)
                
                # Inject *loop-config* if available in the calling environment
                try:
                    loop_config_val = env_for_eval.lookup('*loop-config*')
                    if loop_config_val is not None:
                        call_frame_env.define('*loop-config*', loop_config_val)
                except NameError:
                    pass
                
                # Evaluate the body expressions in the call frame
                result = None
                for body_expr in func_to_call.body_ast:
                    result = self._eval(body_expr, call_frame_env)
                return result
            else:
                # For regular callables (Python functions), call directly
                result = func_to_call(*args_list)
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
        (Corrected implementation with validation and return logic).
        """
        # This method is a stub - the actual implementation is in SpecialFormProcessor.handle_iterative_loop
        # Delegate to the special form processor
        return self.special_form_processor.handle_iterative_loop(arg_exprs, env, original_expr_str)

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
                # <<< ADD/MODIFY LOGGING >>>
                logger.debug(f"  _invoke_task_system: Evaluating value for key '{key_str}' using EnvID={id(calling_env)}")
                bindings_info = "Unavailable"
                parent_bindings_info = "No Parent"
                if hasattr(calling_env, 'get_local_bindings'):
                     local_bindings = calling_env.get_local_bindings()
                     bindings_info = f"Local Bindings: {list(local_bindings.keys())}"
                     # Check for specific expected lambda params if inside controller context
                     if task_name == 'user:evaluate-and-retry-analysis':
                         expected_lambda_params = ['aider_result', 'validation_result', 'current_plan', 'iter_num']
                         missing_params = [p for p in expected_lambda_params if p not in local_bindings]
                         if missing_params:
                             logger.warning(f"    !!! EnvID={id(calling_env)} MISSING expected lambda params: {missing_params} !!!")
                         else:
                             logger.debug(f"    EnvID={id(calling_env)} contains expected lambda params.")

                if hasattr(calling_env, '_parent') and calling_env._parent:
                     parent_env = calling_env._parent
                     parent_bindings_info = f"Parent EnvID={id(parent_env)} Bindings: {list(parent_env.get_local_bindings().keys())}"

                logger.debug(f"  _invoke_task_system: Env Details: {bindings_info} | {parent_bindings_info}")
                # <<< END LOGGING >>>

                evaluated_value = self._eval(value_expr_node, calling_env) # Ensure calling_env is used
                logger.debug(f"  _invoke_task_system: Successfully evaluated value for key '{key_str}' to type: {type(evaluated_value)}")
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
            # <<< ADD LOGGING >>>
            logger.debug(f"*** _invoke_task_system: Using TaskSystem instance ID = {id(self.task_system)}")
            # <<< END LOGGING >>>
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
                # <<< ADD/MODIFY LOGGING >>>
                logger.debug(f"  _invoke_handler_tool: Evaluating value for key '{key_str}' using EnvID={id(calling_env)}")
                bindings_info = "Unavailable"
                parent_bindings_info = "No Parent"
                if hasattr(calling_env, 'get_local_bindings'):
                     local_bindings = calling_env.get_local_bindings()
                     bindings_info = f"Local Bindings: {list(local_bindings.keys())}"
                     # Note: The task_name specific check from _invoke_task_system is omitted here
                     # as it's not directly applicable to a generic handler tool invocation.

                if hasattr(calling_env, '_parent') and calling_env._parent:
                     parent_env = calling_env._parent
                     parent_bindings_info = f"Parent EnvID={id(parent_env)} Bindings: {list(parent_env.get_local_bindings().keys())}"

                logger.debug(f"  _invoke_handler_tool: Env Details: {bindings_info} | {parent_bindings_info}")
                # <<< END LOGGING >>>

                evaluated_value = self._eval(value_expr_node, calling_env) # Ensure calling_env is used
                logger.debug(f"  _invoke_handler_tool: Successfully evaluated value for key '{key_str}' to type: {type(evaluated_value)}")
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
