"""
Processor for S-expression primitives.
This module will contain the PrimitiveProcessor class, which centralizes
the application logic for all built-in primitives in the S-expression language.
"""
import logging
from typing import Any, List, TYPE_CHECKING, Dict

from sexpdata import Symbol

from src.sexp_evaluator.sexp_environment import SexpEnvironment
from src.system.errors import SexpEvaluationError
from src.system.models import ContextGenerationInput, AssociativeMatchResult, MatchTuple # For get_context

# SexpNode is an alias for Any, representing a parsed S-expression node.
SexpNode = Any 

if TYPE_CHECKING:
    from .sexp_evaluator import SexpEvaluator # Forward reference for type hinting

logger = logging.getLogger(__name__)

class PrimitiveProcessor:
    """
    Applies primitives for the SexpEvaluator.
    Each method implements a specific primitive and is responsible for
    evaluating its arguments (as needed by the primitive's semantics)
    and performing the primitive's action.
    """
    def __init__(self, evaluator_instance: 'SexpEvaluator'):
        """
        Initializes the PrimitiveProcessor.

        Args:
            evaluator_instance: An instance of the SexpEvaluator to be used for
                                evaluation of arguments if the primitive requires it.
        """
        self.evaluator = evaluator_instance
        logger.debug("PrimitiveProcessor initialized.")

    def apply_list_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> List[Any]:
        """Applies the 'list' primitive: (list expr...)"""
        logger.debug(f"PrimitiveProcessor.apply_list_primitive START: arg_exprs={arg_exprs}, original_expr_str='{original_expr_str}'")
        evaluated_args = []
        for i, arg_node in enumerate(arg_exprs):
            try:
                evaluated_args.append(self.evaluator._eval(arg_node, env))
                logging.debug(f"  apply_list_primitive: Evaluated arg {i+1} ('{arg_node}') to: {evaluated_args[-1]}")
            except Exception as e_arg_eval:
                logging.exception(f"  apply_list_primitive: Error evaluating argument {i+1} ('{arg_node}'): {e_arg_eval}")
                if isinstance(e_arg_eval, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating argument {i+1} for 'list': {arg_node}", original_expr_str, error_details=str(e_arg_eval)) from e_arg_eval
        
        logging.debug(f"PrimitiveProcessor.apply_list_primitive END: -> {evaluated_args}")
        return evaluated_args

    def apply_get_context_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> List[str]:
        """
        Applies the 'get_context' primitive.
        Parses (key value_expr) pairs from arg_exprs, evaluates each value_expr,
        constructs ContextGenerationInput, calls memory_system, and returns file paths.
        """
        logger.debug(f"PrimitiveProcessor.apply_get_context_primitive START: arg_exprs={arg_exprs}, original_expr_str='{original_expr_str}'")
        
        context_params: Dict[str, Any] = {}
        for i, arg_expr_pair in enumerate(arg_exprs): 
            if not (isinstance(arg_expr_pair, list) and len(arg_expr_pair) == 2 and isinstance(arg_expr_pair[0], Symbol)):
                raise SexpEvaluationError(f"Invalid argument format for 'get_context'. Expected (key_symbol value_expression), got: {arg_expr_pair}", original_expr_str)
            
            key_symbol = arg_expr_pair[0]
            value_expr_node = arg_expr_pair[1] 
            key_str = key_symbol.value()

            try:
                evaluated_value = self.evaluator._eval(value_expr_node, env) 
                logging.debug(f"  apply_get_context_primitive: Evaluated value for key '{key_str}' ('{value_expr_node}'): {evaluated_value}")
            except SexpEvaluationError as e_val_eval:
                raise SexpEvaluationError(
                    f"Error evaluating value for '{key_str}' in 'get_context': {e_val_eval.args[0] if e_val_eval.args else str(e_val_eval)}",
                    expression=original_expr_str, 
                    error_details=f"Failed on value_expr='{e_val_eval.expression if hasattr(e_val_eval, 'expression') else value_expr_node}'. Original detail: {e_val_eval.error_details if hasattr(e_val_eval, 'error_details') else str(e_val_eval)}"
                ) from e_val_eval
            except Exception as e_val_eval:
                logging.exception(f"  apply_get_context_primitive: Error evaluating value for key '{key_str}' ('{value_expr_node}'): {e_val_eval}")
                raise SexpEvaluationError(f"Error evaluating value for '{key_str}' in 'get_context': {value_expr_node}", original_expr_str, error_details=str(e_val_eval)) from e_val_eval
            
            if key_str == "matching_strategy":
                allowed_strategies = {'content', 'metadata'}
                if not isinstance(evaluated_value, str) or evaluated_value not in allowed_strategies: 
                    raise SexpEvaluationError(f"Invalid value for 'matching_strategy'. Expected 'content' or 'metadata', got: {evaluated_value!r}", original_expr_str)
            
            context_params[key_str] = evaluated_value 

        if not context_params: 
            raise SexpEvaluationError("'get_context' requires at least one parameter like (query ...).", original_expr_str)

        try:
            if "inputs" in context_params and isinstance(context_params["inputs"], list):
                inputs_list_of_pairs = context_params["inputs"] 
                inputs_dict = {}
                for pair in inputs_list_of_pairs: 
                    if isinstance(pair, list) and len(pair) == 2:
                        inner_key_node = pair[0]
                        inner_val = pair[1] 
                        inner_key_str = inner_key_node.value() if isinstance(inner_key_node, Symbol) else str(inner_key_node)
                        inputs_dict[inner_key_str] = inner_val
                    else: 
                        raise SexpEvaluationError(f"Invalid pair format in 'inputs' list after evaluation: {pair}. Expected [Symbol, value] or [str, value].", original_expr_str)
                context_params["inputs"] = inputs_dict
                logging.debug(f"  apply_get_context_primitive: Converted 'inputs' list (post-eval) to dict: {context_params['inputs']}")
            
            context_input_obj = ContextGenerationInput(**context_params)
        except Exception as e: 
            logging.exception(f"  Error creating ContextGenerationInput from params {context_params}: {e}")
            raise SexpEvaluationError(f"Failed creating ContextGenerationInput for 'get_context': {e}", original_expr_str, error_details=str(e)) from e

        try:
            logging.debug(f"  Calling memory_system.get_relevant_context_for with: {context_input_obj}")
            match_result: AssociativeMatchResult = self.evaluator.memory_system.get_relevant_context_for(context_input_obj)
        except Exception as e: 
            logging.exception(f"  MemorySystem.get_relevant_context_for failed: {e}")
            raise SexpEvaluationError("Context retrieval failed during MemorySystem call.", original_expr_str, error_details=str(e)) from e

        if match_result.error:
            logging.error(f"  MemorySystem returned error for get_context: {match_result.error}")
            raise SexpEvaluationError("Context retrieval failed (MemorySystem error).", original_expr_str, error_details=match_result.error)

        file_paths = [m.path for m in match_result.matches if isinstance(m, MatchTuple)]
        logging.debug(f"PrimitiveProcessor.apply_get_context_primitive END: -> {file_paths}")
        return file_paths

    def apply_get_field_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        logger.debug(f"PrimitiveProcessor.apply_get_field_primitive: {original_expr_str}")
        if len(arg_exprs) != 2:
            raise SexpEvaluationError("'get-field' requires exactly two arguments: (get-field <object/dict> <field-name>)", original_expr_str)

        obj_expr = arg_exprs[0]
        field_name_expr = arg_exprs[1]

        try:
            target_obj = self.evaluator._eval(obj_expr, env)
            field_name_val = self.evaluator._eval(field_name_expr, env)
        except Exception as e_eval:
            raise SexpEvaluationError(f"Error evaluating arguments for 'get-field': {e_eval}", original_expr_str, error_details=str(e_eval)) from e_eval

        if not isinstance(field_name_val, str):
            if isinstance(field_name_val, Symbol):
                field_name_val = field_name_val.value()
            else:
                raise SexpEvaluationError(f"'get-field' field name must be a string or symbol, got {type(field_name_val)}: {field_name_val!r}", original_expr_str)
        
        logger.debug(f"  'get-field': target_obj type={type(target_obj)}, field_name_val='{field_name_val}'")

        try:
            if isinstance(target_obj, dict):
                if field_name_val not in target_obj:
                    logger.warning(f"  'get-field': Key '{field_name_val}' not found in dict {list(target_obj.keys())}. Returning None.")
                    return None 
                return target_obj.get(field_name_val)
            elif hasattr(target_obj, '__class__') and hasattr(target_obj.__class__, 'model_fields') and hasattr(target_obj, field_name_val):
                logger.debug(f"  'get-field': Accessing attribute '{field_name_val}' from Pydantic-like object.")
                return getattr(target_obj, field_name_val)
            elif hasattr(target_obj, field_name_val):
                logger.debug(f"  'get-field': Accessing attribute '{field_name_val}' from object.")
                return getattr(target_obj, field_name_val)
            else:
                logger.warning(f"  'get-field': Field or attribute '{field_name_val}' not found in object of type {type(target_obj)}. Returning None.")
                return None
        except Exception as e_access:
            logger.exception(f"  Error accessing field '{field_name_val}' in 'get-field': {e_access}")
            raise SexpEvaluationError(f"Error accessing field '{field_name_val}': {e_access}", original_expr_str, error_details=str(e_access)) from e_access

    def apply_string_equal_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> bool:
        logger.debug(f"PrimitiveProcessor.apply_string_equal_primitive: {original_expr_str}")
        if len(arg_exprs) != 2:
            raise SexpEvaluationError("'string=?' requires exactly two string arguments.", original_expr_str)

        try:
            str1 = self.evaluator._eval(arg_exprs[0], env)
            str2 = self.evaluator._eval(arg_exprs[1], env)
        except Exception as e_eval:
            raise SexpEvaluationError(f"Error evaluating arguments for 'string=?': {e_eval}", original_expr_str, error_details=str(e_eval)) from e_eval

        if not isinstance(str1, str) or not isinstance(str2, str):
            raise SexpEvaluationError(f"'string=?' arguments must be strings. Got: {type(str1)}, {type(str2)}", original_expr_str)
        
        result = (str1 == str2)
        logger.debug(f"  'string=?': '{str1}' == '{str2}' -> {result}")
        return result

    def apply_log_message_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any: 
        logger.debug(f"PrimitiveProcessor.apply_log_message_primitive: {original_expr_str}")
        if not arg_exprs:
            logger.info("SexpLog: (log-message) called with no arguments.") 
            return [] 
        
        evaluated_args = []
        for arg_expr in arg_exprs:
            try:
                evaluated_args.append(self.evaluator._eval(arg_expr, env))
            except Exception as e_eval:
                logger.error(f"SexpLog: Error evaluating arg for log-message: {arg_expr} -> {e_eval}")
                evaluated_args.append(f"<Error evaluating: {arg_expr}>")

        log_output = " ".join(map(str, evaluated_args))
        logger.info(f"SexpLog: {log_output}") 
        return log_output 
