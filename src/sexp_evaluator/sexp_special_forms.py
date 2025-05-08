"""
Processor for S-expression special forms.
This module will contain the SpecialFormProcessor class, which centralizes
the handling logic for all special forms in the S-expression language.
"""
import logging
from typing import Any, List, TYPE_CHECKING, Dict

from sexpdata import Symbol

from src.sexp_evaluator.sexp_environment import SexpEnvironment
from src.sexp_evaluator.sexp_closure import Closure # Added import
from src.system.errors import SexpEvaluationError
from src.system.models import TaskResult, SubtaskRequest # For defatom

# SexpNode is an alias for Any, representing a parsed S-expression node.
SexpNode = Any

if TYPE_CHECKING:
    from .sexp_evaluator import SexpEvaluator # Forward reference for type hinting

logger = logging.getLogger(__name__)

class SpecialFormProcessor:
    """
    Processes special forms for the SexpEvaluator.
    Each method handles a specific special form and is responsible for
    its evaluation semantics, including managing argument evaluation
    and environment manipulation as required by the form.
    """
    def __init__(self, evaluator_instance: 'SexpEvaluator'):
        """
        Initializes the SpecialFormProcessor.

        Args:
            evaluator_instance: An instance of the SexpEvaluator to be used for
                                recursive evaluation of sub-expressions.
        """
        self.evaluator = evaluator_instance
        logger.debug("SpecialFormProcessor initialized.")

    def handle_if_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Handles the 'if' special form: (if condition then_branch else_branch)"""
        logger.debug(f"SpecialFormProcessor.handle_if_form START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) != 3:
            raise SexpEvaluationError("'if' requires 3 arguments: (if condition then_branch else_branch)", original_expr_str)
        
        cond_expr, then_expr, else_expr = arg_exprs
        
        try:
            condition_result = self.evaluator._eval(cond_expr, env)
            logger.debug(f"  'if' condition '{cond_expr}' evaluated to: {condition_result}")
        except Exception as e:
            logging.exception(f"  Error evaluating 'if' condition '{cond_expr}': {e}")
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error evaluating 'if' condition: {cond_expr}", original_expr_str, error_details=str(e)) from e

        chosen_branch_expr = then_expr if condition_result else else_expr
        logging.debug(f"  'if' chose branch: {chosen_branch_expr}")
        
        try:
            result = self.evaluator._eval(chosen_branch_expr, env)
            logging.debug(f"SpecialFormProcessor.handle_if_form END: -> {result}")
            return result
        except Exception as e:
            logging.exception(f"  Error evaluating chosen 'if' branch '{chosen_branch_expr}': {e}")
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error evaluating chosen 'if' branch: {chosen_branch_expr}", original_expr_str, error_details=str(e)) from e

    def handle_let_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Handles the 'let' special form: (let ((var expr)...) body...)"""
        logger.debug(f"SpecialFormProcessor.handle_let_form START: original_expr_str='{original_expr_str}'")
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
                evaluated_value = self.evaluator._eval(value_expr, env)
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
                final_result = self.evaluator._eval(body_item_expr, let_env)
                logging.debug(f"  'let' body expression {i+1} evaluated to: {final_result}")
            except Exception as e:
                logging.exception(f"  Error evaluating 'let' body expression {i+1} '{body_item_expr}': {e}")
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating 'let' body expression {i+1}: {body_item_expr}", original_expr_str, error_details=str(e)) from e
                
        logging.debug(f"SpecialFormProcessor.handle_let_form END: -> {final_result}")
        return final_result

    def handle_bind_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Handles the 'bind' special form: (bind variable_symbol expression)"""
        logger.debug(f"SpecialFormProcessor.handle_bind_form START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) != 2 or not isinstance(arg_exprs[0], Symbol):
            raise SexpEvaluationError("'bind' requires a symbol and a value expression: (bind variable_symbol expression)", original_expr_str)

        var_name_symbol = arg_exprs[0]
        value_expr = arg_exprs[1]
        var_name_str = var_name_symbol.value()
        
        logging.debug(f"  Eval 'bind' for variable '{var_name_str}'")
        try:
            evaluated_value = self.evaluator._eval(value_expr, env) # Evaluate value expression in current env
            env.define(var_name_str, evaluated_value) # Define in *current* environment
            logging.debug(f"  SpecialFormProcessor.handle_bind_form END: defined '{var_name_str}' = {evaluated_value} in env {id(env)}")
            return evaluated_value # 'bind' returns the assigned value
        except Exception as e:
            logging.exception(f"  Error evaluating value for 'bind' variable '{var_name_str}': {e}")
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error evaluating value for 'bind' variable '{var_name_str}': {value_expr}", original_expr_str, error_details=str(e)) from e

    def handle_progn_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Handles the 'progn' special form: (progn expr...)"""
        logger.debug(f"SpecialFormProcessor.handle_progn_form START: original_expr_str='{original_expr_str}'")
        final_result = [] # Default result for empty 'progn' is nil/[]
        
        for i, expr in enumerate(arg_exprs):
            try:
                final_result = self.evaluator._eval(expr, env) # Evaluate each expression sequentially
                logging.debug(f"  'progn' expression {i+1} evaluated to: {final_result}")
            except Exception as e:
                logging.exception(f"  Error evaluating 'progn' expression {i+1} '{expr}': {e}")
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating 'progn' expression {i+1}: {expr}", original_expr_str, error_details=str(e)) from e
                
        logging.debug(f"SpecialFormProcessor.handle_progn_form END: -> {final_result}")
        return final_result # Return result of the last expression

    def handle_quote_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Handles the 'quote' special form: (quote expression)"""
        logger.debug(f"SpecialFormProcessor.handle_quote_form START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) != 1:
            raise SexpEvaluationError("'quote' requires exactly one argument: (quote expression)", original_expr_str)
        
        # Return the argument node *without* evaluating it
        quoted_expression = arg_exprs[0]
        logging.debug(f"SpecialFormProcessor.handle_quote_form END: -> {quoted_expression} (unevaluated)")
        return quoted_expression

    def handle_defatom_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Symbol:
        """Handles the 'defatom' special form: (defatom name params instructions ...)"""
        logger.debug(f"SpecialFormProcessor.handle_defatom_form START: original_expr_str='{original_expr_str}'")

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
        
        param_name_strings_for_template = []
        for param_def_item in params_node[1:]:
            if isinstance(param_def_item, Symbol):
                param_name_strings_for_template.append(param_def_item.value())
            elif isinstance(param_def_item, list) and len(param_def_item) >= 1 and isinstance(param_def_item[0], Symbol): # Support (param_name type?)
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

        optional_args_map: Dict[str, Any] = {} # Allow Any for structured values
        # Keys that expect a simple string value
        simple_string_optionals = {"subtype", "description", "model"}
        # Keys that expect a structured value (list of lists/pairs)
        structured_optionals = {"output_format", "history_config"}

        for opt_node in arg_exprs[3:]:
            if not (isinstance(opt_node, list) and len(opt_node) >= 2 and isinstance(opt_node[0], Symbol)): # value can be complex
                raise SexpEvaluationError(
                    f"Invalid optional argument format for 'defatom'. Expected (key value_expression), got: {opt_node}",
                    original_expr_str
                )
            key_node: Symbol = opt_node[0]
            value_node: Any = opt_node[1] # The value part can be a string or a list for structured options
            key_str = key_node.value()

            if key_str in simple_string_optionals:
                if not isinstance(value_node, str):
                    raise SexpEvaluationError(f"Value for optional argument '{key_str}' must be a string, got {type(value_node)}: {value_node}", original_expr_str)
                optional_args_map[key_str] = value_node
            elif key_str in structured_optionals:
                # For output_format or history_config, the value_node is the list of pairs itself, e.g., ((type "json") (schema "..."))
                # We need to convert this list of pairs into a dictionary.
                # The value_node itself (opt_node[1]) is the list of (key value) pairs.
                if not isinstance(value_node, list):
                    raise SexpEvaluationError(
                        f"Value for structured optional argument '{key_str}' must be a list of pairs, got {type(value_node)}: {value_node}",
                        original_expr_str
                    )
                
                structured_dict: Dict[str, Any] = {}
                for pair in value_node:
                    if not (isinstance(pair, list) and len(pair) == 2 and isinstance(pair[0], Symbol)):
                        raise SexpEvaluationError(
                            f"Invalid pair format in '{key_str}'. Expected (key_symbol value), got: {pair}",
                            original_expr_str
                        )
                    inner_key_symbol: Symbol = pair[0]
                    inner_value: Any = pair[1] # Value can be string or another nested structure
                    structured_dict[inner_key_symbol.value()] = inner_value
                optional_args_map[key_str] = structured_dict
                logger.debug(f"Parsed structured optional arg '{key_str}': {structured_dict}")
            else:
                raise SexpEvaluationError(f"Unknown optional argument '{key_str}' for 'defatom'. Allowed: {list(simple_string_optionals | structured_optionals)}", original_expr_str)
        
        template_dict: Dict[str, Any] = {
            "name": task_name_str,
            "type": "atomic",
            "subtype": optional_args_map.get("subtype", "standard"),
            "description": optional_args_map.get("description", f"Dynamically defined task: {task_name_str}"),
            "params": template_params,
            "instructions": instructions_str,
        }
        if "model" in optional_args_map:
            template_dict["model"] = optional_args_map["model"]
        if "output_format" in optional_args_map:
            template_dict["output_format"] = optional_args_map["output_format"]
        if "history_config" in optional_args_map:
            template_dict["history_config"] = optional_args_map["history_config"]


        logging.debug(f"Constructed template dictionary for '{task_name_str}': {template_dict}")

        try:
            logging.info(f"Registering dynamic atomic task template: '{task_name_str}'")
            # TaskSystem.register_template now returns bool
            success = self.evaluator.task_system.register_template(template_dict)
            if not success:
                logging.error(f"TaskSystem.register_template for '{task_name_str}' returned False (registration failed).")
                raise SexpEvaluationError(f"TaskSystem failed to register template '{task_name_str}' (register_template returned False).", original_expr_str)
        except SexpEvaluationError:
            raise
        except Exception as e:
            logging.exception(f"Error registering template '{task_name_str}' with TaskSystem: {e}")
            raise SexpEvaluationError(f"Failed to register template '{task_name_str}' with TaskSystem: {e}", original_expr_str, error_details=str(e)) from e

        # Lexical binding of the task name to a callable wrapper
        evaluator_ref = self.evaluator # Capture self.evaluator for the closure
        
        def defatom_task_wrapper(*args):
            logger.debug(f"defatom_task_wrapper for '{task_name_str}' called with {len(args)} args: {args}")
            
            if len(args) != len(param_name_strings_for_template):
                raise SexpEvaluationError(
                    f"Task '{task_name_str}' (defined by defatom) expects {len(param_name_strings_for_template)} arguments, got {len(args)}.",
                    expression=f"call to {task_name_str}"
                )
            
            inputs_dict = {name: val for name, val in zip(param_name_strings_for_template, args)}
            
            request = SubtaskRequest(
                task_id=f"defatom_call_{task_name_str}_{id(args)}",
                type="atomic",
                name=task_name_str,
                inputs=inputs_dict
                # history_config can be added here if defatom supports it and it's passed
            )
            logging.debug(f"  defatom_task_wrapper: Invoking TaskSystem for '{task_name_str}' with request: {request.model_dump_json(indent=2)}")
            
            try:
                # Ensure task_system is accessed via evaluator_ref
                task_result: TaskResult = evaluator_ref.task_system.execute_atomic_template(request)
                # The result from execute_atomic_template should already be a TaskResult Pydantic model instance.
                # If it needs to be returned as a dictionary for S-expression processing, model_dump() it.
                # For now, let's assume the S-expression layer can handle TaskResult objects or they are converted later.
                return task_result 
            except Exception as e_exec:
                logging.exception(f"  Error executing defatom task '{task_name_str}' via wrapper: {e_exec}")
                raise SexpEvaluationError(f"Error executing defatom task '{task_name_str}': {e_exec}", expression=f"call to {task_name_str}", error_details=str(e_exec)) from e_exec

        env.define(task_name_str, defatom_task_wrapper) # Bind the wrapper
        logging.info(f"Successfully registered and lexically bound dynamic task '{task_name_str}'.")
        return task_name_node

    def handle_loop_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Handles the 'loop' special form: (loop count_expr body_expr)"""
        logger.debug(f"SpecialFormProcessor.handle_loop_form START: original_expr_str='{original_expr_str}'")

        if len(arg_exprs) != 2:
            raise SexpEvaluationError(f"Loop requires exactly 2 arguments: count_expression and body_expression. Got {len(arg_exprs)}.", original_expr_str)
        
        count_expr, body_expr = arg_exprs

        try:
            logging.debug(f"  Evaluating loop count expression: {count_expr}")
            count_value = self.evaluator._eval(count_expr, env)
            logging.debug(f"  Loop count expression evaluated to: {count_value} (Type: {type(count_value)})")
        except SexpEvaluationError as e_count: 
            logging.exception(f"Error evaluating loop count expression '{count_expr}': {e_count}")
            raise SexpEvaluationError(
                f"Error evaluating loop count expression: {e_count.args[0] if e_count.args else str(e_count)}",
                expression=original_expr_str, 
                error_details=f"Failed on count_expr='{e_count.expression if hasattr(e_count, 'expression') else count_expr}'. Original detail: {e_count.error_details if hasattr(e_count, 'error_details') else str(e_count)}"
            ) from e_count
        except Exception as e: 
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

        last_result: Any = [] 
        logging.debug(f"Starting loop execution for {n} iterations.")
        for i in range(n):
            iteration = i + 1
            logging.debug(f"  Loop iteration {iteration}/{n}. Evaluating body: {body_expr}")
            try:
                last_result = self.evaluator._eval(body_expr, env)
                logging.debug(f"  Iteration {iteration}/{n} result: {last_result}")
            except SexpEvaluationError as e_body:
                logging.exception(f"Error evaluating loop body during iteration {iteration}/{n} for '{body_expr}': {e_body}")
                raise SexpEvaluationError(
                    f"Error during loop iteration {iteration}/{n}: {e_body.args[0] if e_body.args else str(e_body)}",
                    expression=original_expr_str, 
                    error_details=f"Failed on body_expr='{e_body.expression if hasattr(e_body, 'expression') else body_expr}'. Original detail: {e_body.error_details if hasattr(e_body, 'error_details') else str(e_body)}"
                ) from e_body
            except Exception as e: 
                logging.exception(f"Unexpected error evaluating loop body during iteration {iteration}/{n} for '{body_expr}': {e}")
                raise SexpEvaluationError(
                    f"Unexpected error during loop iteration {iteration}/{n} processing body '{body_expr}': {str(e)}",
                    expression=original_expr_str,
                    error_details=str(e)
                ) from e
                
        logging.debug(f"SpecialFormProcessor.handle_loop_form finished after {n} iterations. Returning last result: {last_result}")
        return last_result

    def handle_director_evaluator_loop(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """
        Handles the 'director-evaluator-loop' special form.

        Syntax:
        (director-evaluator-loop
          (max-iterations <number-expr>)
          (initial-director-input <expr>)
          (director   <director-function-expr>)
          (executor   <executor-function-expr>)
          (evaluator  <evaluator-function-expr>)
          (controller <controller-function-expr>)
        )

        Args:
            arg_exprs: A list of SexpNode objects representing the arguments
                       to the (director-evaluator-loop ...) form.
            env: The current SexpEnvironment for evaluation.
            original_expr_str: The string representation of the original S-expression call.

        Returns:
            The final result of the loop.

        Raises:
            SexpEvaluationError: For syntax errors, type errors, or runtime errors during loop execution.
        """
        logger.debug(f"SpecialFormProcessor.handle_director_evaluator_loop START: {original_expr_str}")

        # 1. Parse and Validate Loop Structure
        clauses: Dict[str, SexpNode] = {}
        required_clauses = {"max-iterations", "initial-director-input", "director", "executor", "evaluator", "controller"}
        
        for arg_expr in arg_exprs:
            if not (isinstance(arg_expr, list) and len(arg_expr) == 2 and isinstance(arg_expr[0], Symbol)):
                raise SexpEvaluationError(
                    f"director-evaluator-loop: Each clause must be a list of (ClauseName Expression), got: {arg_expr}",
                    original_expr_str
                )
            clause_name_symbol: Symbol = arg_expr[0]
            clause_name_str = clause_name_symbol.value()
            clause_expr_node: SexpNode = arg_expr[1]

            if clause_name_str in clauses:
                raise SexpEvaluationError(
                    f"director-evaluator-loop: Duplicate clause '{clause_name_str}' found.",
                    original_expr_str
                )
            clauses[clause_name_str] = clause_expr_node
        
        missing = required_clauses - set(clauses.keys())
        if missing:
            raise SexpEvaluationError(
                f"director-evaluator-loop: Missing required clauses: {', '.join(sorted(list(missing)))}",
                original_expr_str
            )

        # 2. Evaluate Configuration Expressions (with validation)
        try:
            max_iter_val = self.evaluator._eval(clauses["max-iterations"], env)
            # --- ADDED VALIDATION ---
            if not isinstance(max_iter_val, int) or max_iter_val < 0:
                raise SexpEvaluationError(
                    f"'max-iterations' must evaluate to a non-negative integer, got {max_iter_val!r} (type: {type(max_iter_val)}).",
                    original_expr_str
                )
        except SexpEvaluationError as e:
            raise SexpEvaluationError(f"director-evaluator-loop: Error evaluating 'max-iterations': {e.args[0] if e.args else str(e)}", original_expr_str, error_details=e.error_details if hasattr(e, 'error_details') else str(e)) from e
        except Exception as e:
            raise SexpEvaluationError(f"director-evaluator-loop: Error evaluating 'max-iterations': {e}", original_expr_str, error_details=str(e)) from e

        try:
            current_director_input_val = self.evaluator._eval(clauses["initial-director-input"], env)
        except SexpEvaluationError as e:
            raise SexpEvaluationError(f"director-evaluator-loop: Error evaluating 'initial-director-input': {e.args[0] if e.args else str(e)}", original_expr_str, error_details=e.error_details if hasattr(e, 'error_details') else str(e)) from e
        except Exception as e:
            raise SexpEvaluationError(f"director-evaluator-loop: Error evaluating 'initial-director-input': {e}", original_expr_str, error_details=str(e)) from e

        # 3. Evaluate and Validate Phase Function Expressions (with validation)
        phase_functions: Dict[str, Any] = {}
        for phase_name in ["director", "executor", "evaluator", "controller"]:
            try:
                resolved_fn = self.evaluator._eval(clauses[phase_name], env)
                # --- ADDED VALIDATION ---
                if not isinstance(resolved_fn, Closure) and not callable(resolved_fn):
                    raise SexpEvaluationError(
                        f"director-evaluator-loop: '{phase_name}' expression must evaluate to a callable S-expression function, got {type(resolved_fn)}: {resolved_fn!r}",
                        original_expr_str
                    )
                phase_functions[phase_name] = resolved_fn
            except SexpEvaluationError as e:
                 raise SexpEvaluationError(f"director-evaluator-loop: Error evaluating '{phase_name}' function expression: {e.args[0] if e.args else str(e)}", original_expr_str, error_details=e.error_details if hasattr(e, 'error_details') else str(e)) from e
            except Exception as e:
                raise SexpEvaluationError(f"director-evaluator-loop: Error evaluating '{phase_name}' function expression: {e}", original_expr_str, error_details=str(e)) from e
        
        director_fn   = phase_functions["director"]
        executor_fn   = phase_functions["executor"]
        evaluator_fn  = phase_functions["evaluator"]
        controller_fn = phase_functions["controller"]

        # 4. Initialize Loop State
        current_iteration = 1
        # --- CORRECTED INITIALIZATION ---
        # Default result if loop doesn't run (max_iter=0) or finishes without 'stop'
        loop_result: Any = [] # S-expression 'nil'
        last_exec_result_val: Any = loop_result # Store last successful exec result

        # Create the *loop-config* data structure (association list)
        # This will be passed as an argument, not bound to the environment.
        loop_config_data = [
            [Symbol("max-iterations"), max_iter_val],
            [Symbol("initial-director-input"), current_director_input_val]
        ]
        logger.debug(f"  Loop Init: loop_config_data={loop_config_data!r}")

        # ... (Initialize loop state: current_iteration, loop_result, last_exec_result_val) ...
        # current_iteration, loop_result, last_exec_result_val are initialized before this block

        # 5. Main Loop
        while current_iteration <= max_iter_val:
            logger.debug(f"  Loop Iteration {current_iteration}/{max_iter_val}")

            # Create the environment with *loop-config* binding for this iteration
            phase_call_env = env.extend({'*loop-config*': loop_config_data})
            logger.debug(f"  Loop Iteration {current_iteration}: Created phase_call_env id={id(phase_call_env)} extending env id={id(env)} with *loop-config*")

            try:
                # b. Director Phase - Pass ONLY required args per ADR
                plan_val = self.evaluator._call_phase_function(
                    "director", director_fn, [current_director_input_val, current_iteration],
                    phase_call_env, original_expr_str, current_iteration
                )
                logger.debug(f"    Director result: {str(plan_val)[:200]}...")

                # c. Executor Phase - Pass ONLY required args per ADR
                exec_result_val = self.evaluator._call_phase_function(
                    "executor", executor_fn, [plan_val, current_iteration],
                    phase_call_env, original_expr_str, current_iteration
                )
                logger.debug(f"    Executor result: {str(exec_result_val)[:200]}...")
                last_exec_result_val = exec_result_val

                # d. Evaluator Phase - Pass ONLY required args per ADR
                eval_feedback_val = self.evaluator._call_phase_function(
                    "evaluator", evaluator_fn, [exec_result_val, plan_val, current_iteration],
                    phase_call_env, original_expr_str, current_iteration
                )
                logger.debug(f"    Evaluator result: {str(eval_feedback_val)[:200]}...")

                # e. Controller Phase - Pass ONLY required args per ADR
                decision_val = self.evaluator._call_phase_function(
                    "controller", controller_fn, [eval_feedback_val, plan_val, exec_result_val, current_iteration],
                    phase_call_env, original_expr_str, current_iteration
                )
                logger.debug(f"    Controller result: {str(decision_val)[:200]}...")

            # ... (Error handling for phase_error remains the same) ...
            except Exception as phase_error:
                 logging.exception(f"  Error during loop iteration {current_iteration}: {phase_error}")
                 if isinstance(phase_error, SexpEvaluationError):
                     # --- START FIX for TypeError ---
                     # Check if details is already a dict, if not, create one
                     current_details = phase_error.error_details
                     if isinstance(current_details, dict):
                         details = current_details.copy() # Avoid modifying original
                         if "iteration" not in details:
                              details["iteration"] = current_iteration
                     else: # Handle case where details might be a string or None
                         details = {
                             "iteration": current_iteration,
                             "original_error_details": str(current_details) if current_details else "N/A"
                         }
                     # --- END FIX for TypeError ---
                     new_error = SexpEvaluationError(
                         phase_error.args[0] if phase_error.args else str(phase_error),
                         original_expr_str,
                         error_details=details # Pass the potentially modified dict
                     )
                     logger.error(f"About to re-raise SexpEvaluationError from iterative-loop: {new_error}")
                     raise new_error from phase_error
                 else:
                     raise SexpEvaluationError(
                         f"Unexpected error during loop iteration {current_iteration}: {phase_error}",
                         original_expr_str,
                         error_details={"iteration": current_iteration, "original_error": str(phase_error)}
                     ) from phase_error

            # ... (Decision validation and processing remains the same) ...
            if not (isinstance(decision_val, list) and len(decision_val) == 2 and isinstance(decision_val[0], Symbol)):
                raise SexpEvaluationError(
                    f"director-evaluator-loop: Controller must return a list of (action_symbol value), got: {decision_val!r}",
                    original_expr_str
                )
            
            action_symbol: Symbol = decision_val[0]
            action_value: Any = decision_val[1]
            action_str = action_symbol.value()

            # g. If 'stop'
            if action_str == "stop":
                logger.info(f"  Loop stopping at iteration {current_iteration} due to controller 'stop'.")
                loop_result = action_value # --- CORRECTED ASSIGNMENT ---
                break # Exit the while loop
            # h. If 'continue'
            elif action_str == "continue":
                logger.debug(f"  Loop continuing. Next director input: {str(action_value)[:100]}...")
                current_director_input_val = action_value
                # loop_result = exec_result_val # Removed - loop_result only set on stop or end
                current_iteration += 1
            else: # --- ADDED VALIDATION ---
                raise SexpEvaluationError(
                    f"director-evaluator-loop: Controller decision action must be 'continue' or 'stop' symbol, got: '{action_str}'",
                    original_expr_str
                )
        else: # Loop finished due to max_iterations
            logger.info(f"  Loop finished after reaching max_iterations ({max_iter_val}).")
            # --- CORRECTED ASSIGNMENT ---
            # Return the result of the last EXECUTOR phase if max iterations hit
            loop_result = last_exec_result_val

        logger.debug(f"SpecialFormProcessor.handle_director_evaluator_loop END -> {str(loop_result)[:200]}...")
        return loop_result # Return the final determined result

    def handle_and_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """
        Handles the 'and' special form: (and expr...)
        Evaluates expressions from left to right. If any expression evaluates to a falsey value
        (Python False, None, 0, empty sequence/mapping), evaluation stops and that falsey value is returned.
        If all expressions evaluate to truthy values, the value of the last expression is returned.
        If no expressions are provided, (and) evaluates to True.
        """
        logger.debug(f"SpecialFormProcessor.handle_and_form START: {original_expr_str}")
        if not arg_exprs:
            logger.debug("  'and' with no arguments returns True.")
            return True

        last_value: Any = True  # Default if loop completes (e.g. if no args, though handled above)
                                # More accurately, this will be overwritten by the first eval.
        for i, expr in enumerate(arg_exprs):
            try:
                last_value = self.evaluator._eval(expr, env)
                logger.debug(f"  'and' evaluated argument {i+1} ('{expr}') to: {last_value!r}")
                if not bool(last_value):  # Python's truthiness check
                    logger.debug(f"  'and' short-circuiting on falsey value: {last_value!r}")
                    return last_value  # Return the actual falsey value
            except Exception as e:
                logging.exception(f"  Error evaluating 'and' argument {i+1} '{expr}': {e}")
                if isinstance(e, SexpEvaluationError):
                    raise
                raise SexpEvaluationError(f"Error evaluating argument {i+1} for 'and': {expr}", original_expr_str, error_details=str(e)) from e

        logger.debug(f"SpecialFormProcessor.handle_and_form END: All args truthy, returning last value -> {last_value!r}")
        return last_value # All arguments were truthy, return the value of the last one.

    def handle_or_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """
        Handles the 'or' special form: (or expr...)
        Evaluates expressions from left to right. If any expression evaluates to a truthy value,
        evaluation stops and that truthy value is returned.
        If all expressions evaluate to falsey values, the value of the last expression is returned.
        If no expressions are provided, (or) evaluates to False.
        """
        logger.debug(f"SpecialFormProcessor.handle_or_form START: {original_expr_str}")
        if not arg_exprs:
            logger.debug("  'or' with no arguments returns False.")
            return False

        last_value: Any = False # Default if loop completes (e.g. if no args, though handled above)
                                # More accurately, this will be overwritten by the first eval.
        for i, expr in enumerate(arg_exprs):
            try:
                last_value = self.evaluator._eval(expr, env)
                logger.debug(f"  'or' evaluated argument {i+1} ('{expr}') to: {last_value!r}")
                if bool(last_value):  # Python's truthiness check
                    logger.debug(f"  'or' short-circuiting on truthy value: {last_value!r}")
                    return last_value  # Return the actual truthy value
            except Exception as e:
                logging.exception(f"  Error evaluating 'or' argument {i+1} '{expr}': {e}")
                if isinstance(e, SexpEvaluationError):
                    raise
                raise SexpEvaluationError(f"Error evaluating argument {i+1} for 'or': {expr}", original_expr_str, error_details=str(e)) from e

        logger.debug(f"SpecialFormProcessor.handle_or_form END: All args falsey, returning last value -> {last_value!r}")
        return last_value # All arguments were falsey, return the value of the last one.

    def handle_iterative_loop(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """
        Handles the 'iterative-loop' special form.
        (iterative-loop
          (max-iterations <number-expr>)
          (initial-input <structured-expr>)
          (test-command <cmd-string-expr>)
          (executor   <executor-function-expr>)
          (validator  <validator-function-expr>)
          (controller <controller-function-expr>)
        )
        """
        logger.debug(f"SpecialFormProcessor.handle_iterative_loop START: {original_expr_str}")

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
            max_iter_val = self.evaluator._eval(clauses["max-iterations"], env)
            if not isinstance(max_iter_val, int) or max_iter_val < 0:
                raise SexpEvaluationError(
                    f"'max-iterations' must evaluate to a non-negative integer, got {max_iter_val!r} (type: {type(max_iter_val)}).",
                    original_expr_str
                )
        except SexpEvaluationError as e:
            # Re-raise SexpEvaluationError directly to preserve its details
            raise
        except Exception as e:
            raise SexpEvaluationError(f"iterative-loop: Error evaluating 'max-iterations': {e}", original_expr_str, error_details=str(e)) from e

        try:
            current_loop_input = self.evaluator._eval(clauses["initial-input"], env)
        except Exception as e:
            raise SexpEvaluationError(f"iterative-loop: Error evaluating 'initial-input': {e}", original_expr_str, error_details=str(e)) from e

        try:
            test_cmd_string = self.evaluator._eval(clauses["test-command"], env)
            if not isinstance(test_cmd_string, str):
                raise SexpEvaluationError(
                    f"iterative-loop: 'test-command' must evaluate to a string, got {test_cmd_string!r} (type: {type(test_cmd_string)}).",
                    original_expr_str
                )
        except Exception as e:
            raise SexpEvaluationError(f"iterative-loop: Error evaluating 'test-command': {e}", original_expr_str, error_details=str(e)) from e

        # 3. Evaluate and Validate Phase Function Expressions (with validation)
        phase_functions: Dict[str, Any] = {}
        for phase_name in ["executor", "validator", "controller"]:
            try:
                resolved_fn = self.evaluator._eval(clauses[phase_name], env)
                # Using self.evaluator.Closure to access Closure type from SexpEvaluator instance
                if not isinstance(resolved_fn, self.evaluator.Closure) and not callable(resolved_fn):
                    raise SexpEvaluationError(
                        f"iterative-loop: '{phase_name}' expression must evaluate to a callable S-expression function or Python callable, got {type(resolved_fn)}: {resolved_fn!r}",
                        original_expr_str
                    )
                phase_functions[phase_name] = resolved_fn
            except Exception as e:
                raise SexpEvaluationError(f"iterative-loop: Error evaluating '{phase_name}' function expression: {e}", original_expr_str, error_details=str(e)) from e

        executor_fn   = phase_functions["executor"]
        validator_fn  = phase_functions["validator"]
        controller_fn = phase_functions["controller"]

        # 4. Initialize Loop State
        current_iteration = 1
        loop_result: Any = []  # Default result is nil/[] if max_iter is 0 or loop doesn't run
        last_exec_result_val: Any = loop_result # Store last successful exec result

        if max_iter_val == 0:
            logger.info("iterative-loop: max-iterations is 0, returning [].")
            return [] # Return S-expression nil

        # 5. Main Loop
        while current_iteration <= max_iter_val:
            logger.info(f"--- Iterative Loop: Iteration {current_iteration}/{max_iter_val} ---")

            try:
                # --- Executor Phase ---
                executor_result = self.evaluator._call_phase_function(
                    "executor", executor_fn, [current_loop_input, current_iteration],
                    env, original_expr_str, current_iteration
                )
                last_exec_result_val = executor_result # Store potentially final result

                # --- Validator Phase ---
                validation_result = self.evaluator._call_phase_function(
                    "validator", validator_fn, [test_cmd_string, current_iteration],
                    env, original_expr_str, current_iteration
                )

                # --- Controller Phase ---
                decision_val = self.evaluator._call_phase_function(
                    "controller", controller_fn, [executor_result, validation_result, current_loop_input, current_iteration],
                    env, original_expr_str, current_iteration
                )

            except Exception as phase_error:
                logger.exception(f"  Error during iterative-loop iteration {current_iteration}: {phase_error}")
                # Wrap unexpected errors or re-raise SexpEvaluationError with context
                if isinstance(phase_error, SexpEvaluationError):
                    details = phase_error.error_details if hasattr(phase_error, 'error_details') else {}
                    if isinstance(details, dict) and "iteration" not in details:
                        details["iteration"] = current_iteration
                    raise SexpEvaluationError(
                        f"Error in {phase_error.args[0] if phase_error.args else str(phase_error)}",
                        original_expr_str, 
                        error_details=details
                    ) from phase_error
                else: # Wrap unexpected errors
                    new_error = SexpEvaluationError(
                        f"Unexpected error during iterative-loop iteration {current_iteration}: {phase_error}",
                        original_expr_str,
                        error_details={"iteration": current_iteration, "original_error": str(phase_error)}
                    )
                    logger.error(f"About to re-raise wrapped SexpEvaluationError from iterative-loop: {new_error}")
                    raise new_error from phase_error

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
                logger.info(f"iterative-loop: Stopping at iteration {current_iteration} due to controller 'stop'. Final result: {str(action_value)[:100]}...")
                loop_result = action_value
                break 
            elif action_str == "continue":
                logger.info(f"iterative-loop: Continuing to next iteration. Next input: {str(action_value)[:100]}...")
                current_loop_input = action_value
                current_iteration += 1
            else: 
                raise SexpEvaluationError(
                    f"iterative-loop: Controller decision action must be 'continue' or 'stop' symbol, got: '{action_str}'",
                    original_expr_str
                )
        else: # Loop finished because current_iteration > max_iter_val (and not stopped early)
            logger.info(f"iterative-loop: Finished after reaching max_iterations ({max_iter_val}). Returning last executor result.")
            loop_result = last_exec_result_val

        logger.info(f"SpecialFormProcessor.handle_iterative_loop END. Iterations run: {current_iteration-1 if max_iter_val > 0 else 0}. Final loop_result type: {type(loop_result)}")
        logger.debug(f"SpecialFormProcessor.handle_iterative_loop END -> {str(loop_result)[:200]}...")
        return loop_result

    def handle_and_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """
        Handles the 'and' special form: (and expr...)
        Evaluates expressions from left to right. If any expression evaluates to a falsey value
        (Python False, None, 0, empty sequence/mapping), evaluation stops and that falsey value is returned.
        If all expressions evaluate to truthy values, the value of the last expression is returned.
        If no expressions are provided, (and) evaluates to True.
        """
        logger.debug(f"SpecialFormProcessor.handle_and_form START: {original_expr_str}")
        if not arg_exprs:
            logger.debug("  'and' with no arguments returns True.")
            return True

        last_value: Any = True  # Default if loop completes (e.g. if no args, though handled above)
                                # More accurately, this will be overwritten by the first eval.
        for i, expr in enumerate(arg_exprs):
            try:
                last_value = self.evaluator._eval(expr, env)
                logger.debug(f"  'and' evaluated argument {i+1} ('{expr}') to: {last_value!r}")
                if not bool(last_value):  # Python's truthiness check
                    logger.debug(f"  'and' short-circuiting on falsey value: {last_value!r}")
                    return last_value  # Return the actual falsey value
            except Exception as e:
                logging.exception(f"  Error evaluating 'and' argument {i+1} '{expr}': {e}")
                if isinstance(e, SexpEvaluationError):
                    raise
                raise SexpEvaluationError(f"Error evaluating argument {i+1} for 'and': {expr}", original_expr_str, error_details=str(e)) from e

        logger.debug(f"SpecialFormProcessor.handle_and_form END: All args truthy, returning last value -> {last_value!r}")
        return last_value # All arguments were truthy, return the value of the last one.

    def handle_or_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """
        Handles the 'or' special form: (or expr...)
        Evaluates expressions from left to right. If any expression evaluates to a truthy value,
        evaluation stops and that truthy value is returned.
        If all expressions evaluate to falsey values, the value of the last expression is returned.
        If no expressions are provided, (or) evaluates to False.
        """
        logger.debug(f"SpecialFormProcessor.handle_or_form START: {original_expr_str}")
        if not arg_exprs:
            logger.debug("  'or' with no arguments returns False.")
            return False

        last_value: Any = False # Default if loop completes (e.g. if no args, though handled above)
                                # More accurately, this will be overwritten by the first eval.
        for i, expr in enumerate(arg_exprs):
            try:
                last_value = self.evaluator._eval(expr, env)
                logger.debug(f"  'or' evaluated argument {i+1} ('{expr}') to: {last_value!r}")
                if bool(last_value):  # Python's truthiness check
                    logger.debug(f"  'or' short-circuiting on truthy value: {last_value!r}")
                    return last_value  # Return the actual truthy value
            except Exception as e:
                logging.exception(f"  Error evaluating 'or' argument {i+1} '{expr}': {e}")
                if isinstance(e, SexpEvaluationError):
                    raise
                raise SexpEvaluationError(f"Error evaluating argument {i+1} for 'or': {expr}", original_expr_str, error_details=str(e)) from e

        logger.debug(f"SpecialFormProcessor.handle_or_form END: All args falsey, returning last value -> {last_value!r}")
        return last_value # All arguments were falsey, return the value of the last one.
