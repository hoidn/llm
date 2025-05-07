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
from .sexp_special_forms import SpecialFormProcessor # ADDED
from .sexp_primitives import PrimitiveProcessor     # ADDED

# System Models and Errors
from src.system.models import (
    TaskResult, SubtaskRequest, ContextGenerationInput, ContextManagement,
    TaskFailureError, AssociativeMatchResult, MatchTuple,
    TaskError # ContextGenerationInput was duplicated, removed one
)
from src.system.errors import SexpSyntaxError, SexpEvaluationError

# Type for Sexp AST nodes (adjust based on SexpParser output)
# Assuming sexpdata-like output: lists, tuples, strings, numbers, bools, None, Symbol objects
from sexpdata import Symbol # Or use str if parser converts symbols


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

        # Instantiate helper processors
        self.special_form_processor = SpecialFormProcessor(self)
        self.primitive_processor = PrimitiveProcessor(self)

        # Dispatch dictionaries for special forms and primitives
        # These now point to methods on the helper processor instances.
        self.SPECIAL_FORM_HANDLERS: Dict[str, Callable] = {
            "if": self.special_form_processor.handle_if_form,
            "let": self.special_form_processor.handle_let_form,
            "bind": self.special_form_processor.handle_bind_form,
            "progn": self.special_form_processor.handle_progn_form,
            "quote": self.special_form_processor.handle_quote_form,
            "defatom": self.special_form_processor.handle_defatom_form,
            "loop": self.special_form_processor.handle_loop_form,
            "director-evaluator-loop": self.special_form_processor.handle_director_evaluator_loop, # New
        }
        self.PRIMITIVE_APPLIERS: Dict[str, Callable] = {
            "list": self.primitive_processor.apply_list_primitive,
            "get_context": self.primitive_processor.apply_get_context_primitive,
            "get-field": self.primitive_processor.apply_get_field_primitive,
            "string=?": self.primitive_processor.apply_string_equal_primitive,
            "log-message": self.primitive_processor.apply_log_message_primitive,
        }
        logging.info("SexpEvaluator initialized with helper processors.")

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

        if not isinstance(node, list):
            logger.debug(f"Eval Literal/Atom: {node}")
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
            if op_name_str in self.SPECIAL_FORM_HANDLERS: 
                logger.debug(f"  _eval_list_form: Dispatching to Special Form Handler: {op_name_str}")
                handler_method = self.SPECIAL_FORM_HANDLERS[op_name_str]
                # Special form handlers are now methods on self.special_form_processor
                # They will receive (arg_expr_nodes, env, original_expr_str)
                return handler_method(arg_expr_nodes, env, original_expr_str) 
            
            is_primitive = op_name_str in self.PRIMITIVE_APPLIERS
            template_def = self.task_system.find_template(op_name_str)
            is_atomic_task = template_def and template_def.get("type") == "atomic"
            is_handler_tool = op_name_str in self.handler.tool_executors

            if is_primitive or is_atomic_task or is_handler_tool:
                resolved_operator = op_name_str 
                logger.debug(f"  _eval_list_form: Operator '{op_name_str}' identified as known primitive/task/tool name.")
            else:
                logger.debug(f"  _eval_list_form: Operator symbol '{op_name_str}' is not a fixed operator. Evaluating (looking up) '{op_name_str}'...")
                try:
                    resolved_operator = self._eval(op_expr_node, env) 
                except NameError as ne: 
                    logger.error(f"  _eval_list_form: Operator symbol '{op_name_str}' is unbound during lookup.")
                    raise SexpEvaluationError(f"Unbound symbol or unrecognized operator: {op_name_str}", original_expr_str) from ne
                except SexpEvaluationError as se: 
                    raise se
                except Exception as e: 
                    logger.exception(f"  _eval_list_form: Unexpected error evaluating operator symbol '{op_name_str}': {e}")
                    raise SexpEvaluationError(f"Error evaluating operator symbol '{op_name_str}': {e}", original_expr_str, error_details=str(e)) from e
        elif isinstance(op_expr_node, list): 
            logger.debug(f"  _eval_list_form: Operator is a complex expression, evaluating it: {op_expr_node}")
            try:
                resolved_operator = self._eval(op_expr_node, env)
            except Exception as e_op_eval: 
                logger.exception(f"  _eval_list_form: Error evaluating complex operator expression '{op_expr_node}': {e_op_eval}")
                if isinstance(e_op_eval, SexpEvaluationError): raise 
                raise SexpEvaluationError(f"Error evaluating operator expression: {op_expr_node}", original_expr_str, error_details=str(e_op_eval)) from e_op_eval
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
            
            logger.debug(f"    Creating new call frame. Parent (definition_env from closure) ID: {id(closure_to_apply.definition_env)}")
            call_frame_env = closure_to_apply.definition_env.extend({}) 

            for param_symbol, arg_value in zip(closure_to_apply.params_ast, evaluated_args):
                param_name = param_symbol.value() 
                call_frame_env.define(param_name, arg_value)
                logger.debug(f"      Bound '{param_name}' = {arg_value} in call frame (id={id(call_frame_env)})")
            
            final_body_result: Any = [] 
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

        elif isinstance(resolved_op, str):
            op_name_str = resolved_op
            logger.debug(f"  _apply_operator: Operator is a name string: '{op_name_str}'")

            if op_name_str in self.PRIMITIVE_APPLIERS:
                logger.debug(f"  _apply_operator: Dispatching to Primitive Applier: {op_name_str}")
                applier_method = self.PRIMITIVE_APPLIERS[op_name_str]
                # Primitive appliers are now methods on self.primitive_processor
                # They will receive (arg_expr_nodes, calling_env, original_call_expr_str)
                return applier_method(arg_expr_nodes, calling_env, original_call_expr_str)

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

    # --- Special Form Handlers (Original implementations - to be migrated) ---

    def _eval_if_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Any:
        logging.debug(f"SexpEvaluator._eval_if_form START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) != 3:
            raise SexpEvaluationError("'if' requires 3 arguments: (if condition then_branch else_branch)", original_expr_str)
        cond_expr, then_expr, else_expr = arg_exprs
        try:
            condition_result = self._eval(cond_expr, env)
        except Exception as e:
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error evaluating 'if' condition: {cond_expr}", original_expr_str, error_details=str(e)) from e
        chosen_branch_expr = then_expr if condition_result else else_expr
        try:
            return self._eval(chosen_branch_expr, env)
        except Exception as e:
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error evaluating chosen 'if' branch: {chosen_branch_expr}", original_expr_str, error_details=str(e)) from e

    def _eval_let_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Any:
        logging.debug(f"SexpEvaluator._eval_let_form START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) < 1 or not isinstance(arg_exprs[0], list):
            raise SexpEvaluationError("'let' requires a bindings list and at least one body expression", original_expr_str)
        bindings_list_expr = arg_exprs[0]
        body_exprs = arg_exprs[1:]
        if not body_exprs:
            raise SexpEvaluationError("'let' requires at least one body expression.", original_expr_str)
        let_env = env.extend({})
        for binding_expr in bindings_list_expr:
            if not (isinstance(binding_expr, list) and len(binding_expr) == 2 and isinstance(binding_expr[0], Symbol)):
                raise SexpEvaluationError(f"Invalid 'let' binding format: {binding_expr}", original_expr_str)
            var_name_symbol, value_expr = binding_expr
            var_name_str = var_name_symbol.value()
            try:
                evaluated_value = self._eval(value_expr, env)
                let_env.define(var_name_str, evaluated_value)
            except Exception as e:
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating value for 'let' binding '{var_name_str}'", original_expr_str, error_details=str(e)) from e
        final_result = []
        for body_item_expr in body_exprs:
            try:
                final_result = self._eval(body_item_expr, let_env)
            except Exception as e:
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating 'let' body expression: {body_item_expr}", original_expr_str, error_details=str(e)) from e
        return final_result

    def _eval_bind_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Any:
        logging.debug(f"SexpEvaluator._eval_bind_form START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) != 2 or not isinstance(arg_exprs[0], Symbol):
            raise SexpEvaluationError("'bind' requires a symbol and a value expression", original_expr_str)
        var_name_symbol, value_expr = arg_exprs
        var_name_str = var_name_symbol.value()
        try:
            evaluated_value = self._eval(value_expr, env)
            env.define(var_name_str, evaluated_value)
            return evaluated_value
        except Exception as e:
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error evaluating value for 'bind' variable '{var_name_str}'", original_expr_str, error_details=str(e)) from e

    def _eval_progn_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Any:
        logging.debug(f"SexpEvaluator._eval_progn_form START: original_expr_str='{original_expr_str}'")
        final_result = []
        for expr in arg_exprs:
            try:
                final_result = self._eval(expr, env)
            except Exception as e:
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating 'progn' expression: {expr}", original_expr_str, error_details=str(e)) from e
        return final_result

    def _eval_quote_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Any:
        logging.debug(f"SexpEvaluator._eval_quote_form START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) != 1:
            raise SexpEvaluationError("'quote' requires exactly one argument", original_expr_str)
        return arg_exprs[0]

    def _eval_defatom_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Symbol:
        logging.debug(f"SexpEvaluator._eval_defatom_form START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) < 3:
            raise SexpEvaluationError("'defatom' requires name, params, and instructions", original_expr_str)
        task_name_node, params_node, instructions_node = arg_exprs[0], arg_exprs[1], arg_exprs[2]
        if not isinstance(task_name_node, Symbol):
            raise SexpEvaluationError("'defatom' task name must be a Symbol", original_expr_str)
        task_name_str = task_name_node.value()
        if not (isinstance(params_node, list) and params_node and isinstance(params_node[0], Symbol) and params_node[0].value() == "params"):
            raise SexpEvaluationError("'defatom' requires (params ...) definition", original_expr_str)
        param_name_strings = []
        for p_item in params_node[1:]:
            if isinstance(p_item, Symbol): param_name_strings.append(p_item.value())
            elif isinstance(p_item, list) and p_item and isinstance(p_item[0], Symbol): param_name_strings.append(p_item[0].value())
            else: raise SexpEvaluationError("Invalid parameter definition in (params ...)", original_expr_str)
        template_params = {name: {"description": f"Parameter {name}"} for name in param_name_strings}
        if not (isinstance(instructions_node, list) and len(instructions_node) == 2 and isinstance(instructions_node[0], Symbol) and instructions_node[0].value() == "instructions" and isinstance(instructions_node[1], str)):
            raise SexpEvaluationError("'defatom' requires (instructions \"string\")", original_expr_str)
        instructions_str = instructions_node[1]
        optional_args_map = {}
        for opt_node in arg_exprs[3:]:
            if not (isinstance(opt_node, list) and len(opt_node) == 2 and isinstance(opt_node[0], Symbol) and isinstance(opt_node[1], str)): # Assuming values are strings for simplicity
                raise SexpEvaluationError("Invalid optional argument format for 'defatom'", original_expr_str)
            optional_args_map[opt_node[0].value()] = opt_node[1]
        template_dict = {
            "name": task_name_str, "type": "atomic",
            "subtype": optional_args_map.get("subtype", "standard"),
            "description": optional_args_map.get("description", f"Dynamically defined: {task_name_str}"),
            "params": template_params, "instructions": instructions_str,
        }
        if "model" in optional_args_map: template_dict["model"] = optional_args_map["model"]
        try:
            if self.task_system.register_template(template_dict) is False:
                raise SexpEvaluationError(f"TaskSystem failed to register template '{task_name_str}'", original_expr_str)
        except Exception as e:
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Failed to register template '{task_name_str}': {e}", original_expr_str, error_details=str(e)) from e
        def defatom_task_wrapper(*args):
            if len(args) != len(param_name_strings):
                raise SexpEvaluationError(f"Task '{task_name_str}' expects {len(param_name_strings)} args, got {len(args)}.")
            inputs_dict = {name: val for name, val in zip(param_name_strings, args)}
            request = SubtaskRequest(task_id=f"defatom_call_{task_name_str}", type="atomic", name=task_name_str, inputs=inputs_dict)
            try:
                return self.task_system.execute_atomic_template(request)
            except Exception as e_exec:
                raise SexpEvaluationError(f"Error executing defatom task '{task_name_str}': {e_exec}", error_details=str(e_exec)) from e_exec
        env.define(task_name_str, defatom_task_wrapper)
        return task_name_node

    def _eval_loop_form(self, arg_exprs: list, env: SexpEnvironment, original_expr_str: str) -> Any:
        logging.debug(f"SexpEvaluator._eval_loop_form START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) != 2:
            raise SexpEvaluationError(f"Loop requires 2 arguments: count_expression and body_expression.", original_expr_str)
        count_expr, body_expr = arg_exprs
        try:
            count_value = self._eval(count_expr, env)
        except Exception as e:
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error evaluating loop count expression: {count_expr}", original_expr_str, error_details=str(e)) from e
        if not isinstance(count_value, int) or count_value < 0:
            raise SexpEvaluationError(f"Loop count must be a non-negative integer.", original_expr_str, f"Got: {count_value}")
        last_result = []
        for i in range(count_value):
            try:
                last_result = self._eval(body_expr, env)
            except Exception as e:
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating loop body iteration {i+1}: {body_expr}", original_expr_str, error_details=str(e)) from e
        return last_result

    # --- Primitive Appliers (Original implementations - to be migrated) ---

    def _apply_list_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> List[Any]:
        logging.debug(f"SexpEvaluator._apply_list_primitive: arg_exprs={arg_exprs}")
        evaluated_args = []
        for arg_node in arg_exprs:
            try:
                evaluated_args.append(self._eval(arg_node, env))
            except Exception as e:
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating argument for 'list': {arg_node}", original_expr_str, error_details=str(e)) from e
        return evaluated_args

    def _apply_get_context_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> List[str]:
        logging.debug(f"SexpEvaluator._apply_get_context_primitive: arg_exprs={arg_exprs}")
        context_params = {}
        for arg_pair in arg_exprs:
            if not (isinstance(arg_pair, list) and len(arg_pair) == 2 and isinstance(arg_pair[0], Symbol)):
                raise SexpEvaluationError("Invalid arg format for 'get_context'", original_expr_str)
            key_str, value_expr = arg_pair[0].value(), arg_pair[1]
            try:
                evaluated_value = self._eval(value_expr, env)
                if key_str == "matching_strategy" and evaluated_value not in {'content', 'metadata'}:
                    raise SexpEvaluationError(f"Invalid 'matching_strategy': {evaluated_value}", original_expr_str)
                context_params[key_str] = evaluated_value
            except Exception as e:
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating value for '{key_str}' in 'get_context'", original_expr_str, error_details=str(e)) from e
        if not context_params: raise SexpEvaluationError("'get_context' requires parameters.", original_expr_str)
        try:
            if "inputs" in context_params and isinstance(context_params["inputs"], list): # Handle (quote ((k v)...))
                context_params["inputs"] = { (p[0].value() if isinstance(p[0], Symbol) else str(p[0])): p[1] for p in context_params["inputs"] }
            context_input_obj = ContextGenerationInput(**context_params)
            match_result = self.memory_system.get_relevant_context_for(context_input_obj)
            if match_result.error: raise SexpEvaluationError(f"MemorySystem error: {match_result.error}", original_expr_str)
            return [m.path for m in match_result.matches if isinstance(m, MatchTuple)]
        except Exception as e:
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Failed 'get_context' call: {e}", original_expr_str, error_details=str(e)) from e

    def _apply_get_field_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        logging.debug(f"SexpEvaluator._apply_get_field_primitive: {original_expr_str}")
        if len(arg_exprs) != 2: raise SexpEvaluationError("'get-field' needs 2 args", original_expr_str)
        obj_expr, field_expr = arg_exprs[0], arg_exprs[1]
        try:
            target_obj = self._eval(obj_expr, env)
            field_name = self._eval(field_expr, env)
            if isinstance(field_name, Symbol): field_name = field_name.value()
            if not isinstance(field_name, str): raise SexpEvaluationError("Field name must be string/symbol", original_expr_str)
            if isinstance(target_obj, dict): return target_obj.get(field_name)
            if hasattr(target_obj, field_name): return getattr(target_obj, field_name)
            return None
        except Exception as e:
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error in 'get-field': {e}", original_expr_str, error_details=str(e)) from e

    def _apply_string_equal_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> bool:
        logging.debug(f"SexpEvaluator._apply_string_equal_primitive: {original_expr_str}")
        if len(arg_exprs) != 2: raise SexpEvaluationError("'string=?' needs 2 args", original_expr_str)
        try:
            str1 = self._eval(arg_exprs[0], env)
            str2 = self._eval(arg_exprs[1], env)
            if not (isinstance(str1, str) and isinstance(str2, str)):
                raise SexpEvaluationError("Args to 'string=?' must be strings", original_expr_str)
            return str1 == str2
        except Exception as e:
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error in 'string=?': {e}", original_expr_str, error_details=str(e)) from e

    def _apply_log_message_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        logging.debug(f"SexpEvaluator._apply_log_message_primitive: {original_expr_str}")
        if not arg_exprs: logger.info("SexpLog: (log-message) called with no arguments."); return []
        evaluated_args = []
        for arg_expr in arg_exprs:
            try: evaluated_args.append(self._eval(arg_expr, env))
            except Exception as e: evaluated_args.append(f"<Error: {e}>")
        log_output = " ".join(map(str, evaluated_args))
        logger.info(f"SexpLog: {log_output}")
        return log_output

    # --- Invocation Helpers (Original implementations) ---

    def _invoke_task_system(self, task_name: str, template_def: Dict[str, Any], arg_exprs: List[SexpNode], calling_env: SexpEnvironment, original_expr_str: str) -> TaskResult:
        logging.debug(f"SexpEvaluator._invoke_task_system: task='{task_name}', arg_exprs={arg_exprs}")
        named_params, file_paths, context_settings_dict, history_config_dict = {}, None, None, None
        for arg_pair in arg_exprs:
            if not (isinstance(arg_pair, list) and len(arg_pair) == 2 and isinstance(arg_pair[0], Symbol)):
                raise SexpEvaluationError(f"Invalid arg format for task '{task_name}'", original_expr_str)
            key_str, value_expr = arg_pair[0].value(), arg_pair[1]
            try:
                evaluated_value = self._eval(value_expr, calling_env)
                if key_str == "files":
                    if not (isinstance(evaluated_value, list) and all(isinstance(i, str) for i in evaluated_value)):
                        raise SexpEvaluationError("'files' must be list of strings", original_expr_str)
                    file_paths = evaluated_value
                elif key_str == "context":
                    if isinstance(evaluated_value, list): context_settings_dict = { (p[0].value() if isinstance(p[0], Symbol) else str(p[0])): p[1] for p in evaluated_value }
                    elif isinstance(evaluated_value, dict): context_settings_dict = evaluated_value
                    else: raise SexpEvaluationError("'context' must be dict or list of pairs", original_expr_str)
                elif key_str == "history_config":
                    if isinstance(evaluated_value, list): history_config_dict = { (p[0].value() if isinstance(p[0], Symbol) else str(p[0])): p[1] for p in evaluated_value }
                    elif isinstance(evaluated_value, dict): history_config_dict = evaluated_value
                    else: raise SexpEvaluationError("'history_config' must be dict or list of pairs", original_expr_str)
                else: named_params[key_str] = evaluated_value
            except Exception as e:
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating value for '{key_str}' in task '{task_name}'", original_expr_str, error_details=str(e)) from e
        
        context_mgmt_obj = ContextManagement(**context_settings_dict) if context_settings_dict else None
        request = SubtaskRequest(
            task_id=f"sexp_task_{task_name}_{id(original_expr_str)}", type="atomic", name=task_name,
            inputs=named_params, file_paths=file_paths, context_management=context_mgmt_obj, history_config=history_config_dict
        )
        try:
            task_result = self.task_system.execute_atomic_template(request)
            if not isinstance(task_result, TaskResult):
                 return TaskResult(status="FAILED", content=f"Task '{task_name}' bad return type: {type(task_result)}",
                                   notes={"error": TaskFailureError(type="TASK_FAILURE", reason="output_format_failure", message="Invalid return type").model_dump()})
            return task_result
        except Exception as e:
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error executing task '{task_name}': {e}", original_expr_str, error_details=str(e)) from e

    def _invoke_handler_tool(self, tool_name: str, arg_exprs: List[SexpNode], calling_env: SexpEnvironment, original_expr_str: str) -> TaskResult:
        logging.debug(f"SexpEvaluator._invoke_handler_tool: tool='{tool_name}', arg_exprs={arg_exprs}")
        named_params = {}
        for arg_pair in arg_exprs:
            if not (isinstance(arg_pair, list) and len(arg_pair) == 2 and isinstance(arg_pair[0], Symbol)):
                raise SexpEvaluationError(f"Invalid arg format for tool '{tool_name}'", original_expr_str)
            key_str, value_expr = arg_pair[0].value(), arg_pair[1]
            try:
                named_params[key_str] = self._eval(value_expr, calling_env)
            except Exception as e:
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating value for '{key_str}' in tool '{tool_name}'", original_expr_str, error_details=str(e)) from e
        try:
            tool_result = self.handler._execute_tool(tool_name, named_params)
            if not isinstance(tool_result, TaskResult):
                return TaskResult(status="FAILED", content=f"Tool '{tool_name}' bad return type: {type(tool_result)}",
                                  notes={"error": TaskFailureError(type="TASK_FAILURE", reason="output_format_failure", message="Invalid return type").model_dump()})
            return tool_result
        except Exception as e:
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error executing tool '{tool_name}': {e}", original_expr_str, error_details=str(e)) from e
