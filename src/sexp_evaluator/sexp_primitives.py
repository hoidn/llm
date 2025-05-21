"""
Processor for S-expression primitives.
This module will contain the PrimitiveProcessor class, which centralizes
the application logic for all built-in primitives in the S-expression language.
"""
import logging
from typing import Any, List, TYPE_CHECKING, Dict
from pydantic import BaseModel as PydanticBaseModel # add once, aliased
from src.system.models import TaskResult   # NEW – needed for isinstance check

from sexpdata import Symbol

from src.sexp_evaluator.sexp_environment import SexpEnvironment
from src.system.errors import SexpEvaluationError
from src.system.models import ContextGenerationInput, AssociativeMatchResult, MatchItem # For get_context

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

    async def apply_list_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> List[Any]:
        """Applies the 'list' primitive: (list expr...)"""
        logger.debug(f"PrimitiveProcessor.apply_list_primitive START: arg_exprs={arg_exprs}, original_expr_str='{original_expr_str}'")
        evaluated_args = []
        for i, arg_node in enumerate(arg_exprs):
            try:
                evaluated_args.append(await self.evaluator._eval(arg_node, env))
                logging.debug(f"  apply_list_primitive: Evaluated arg {i+1} ('{arg_node}') to: {evaluated_args[-1]}")
            except Exception as e_arg_eval:
                logging.exception(f"  apply_list_primitive: Error evaluating argument {i+1} ('{arg_node}'): {e_arg_eval}")
                if isinstance(e_arg_eval, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating argument {i+1} for 'list': {arg_node}", original_expr_str, error_details=str(e_arg_eval)) from e_arg_eval
        
        logging.debug(f"PrimitiveProcessor.apply_list_primitive END: -> {evaluated_args}")
        return evaluated_args

    async def apply_get_context_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Dict[str, Any]:
        """
        Applies the 'get_context' primitive.
        Parses (key value_expr) pairs from arg_exprs, evaluates each value_expr,
        constructs ContextGenerationInput, calls memory_system, and returns structured context result.
        """
        logger.debug(f"PrimitiveProcessor.apply_get_context_primitive START: arg_exprs={arg_exprs}, original_expr_str='{original_expr_str}'")
        
        # Check if we have at least one arg - required for the query
        if not arg_exprs:
            raise SexpEvaluationError("'get-context' requires at least a query argument.", original_expr_str)
            
        # Special handling for the simple case: (get-context "query string")
        if len(arg_exprs) == 1 and not isinstance(arg_exprs[0], list):
            # It's a direct query string, not a (key value) pair
            try:
                query_value = await self.evaluator._eval(arg_exprs[0], env)
                if not isinstance(query_value, str):
                    raise SexpEvaluationError(f"'get-context' query must be a string, got: {type(query_value)}", original_expr_str)
                
                # Default to 'content' strategy
                context_strategy = "content"
                query = query_value
                
                # Simple case: directly call memory_system with these values
                match_result = await self.evaluator.memory_system.get_relevant_context_for(
                    ContextGenerationInput(query=query, matching_strategy=context_strategy)
                )
                
                # Convert to the expected dict format
                result_dict = {
                    "summary": match_result.context_summary or "",  # Ensure we have a string, not None
                    "matches": [
                        {
                            "id": item.id,
                            "content": item.content,
                            "relevance_score": item.relevance_score,
                            "content_type": item.content_type
                        }
                        for item in match_result.matches
                    ]
                }
                
                # Include any error message if present
                if match_result.error:
                    result_dict["error"] = match_result.error
                    
                # Return the structured result
                return result_dict
                
            except SexpEvaluationError:
                raise  # Re-raise SexpEvaluationError directly
            except Exception as e:
                logging.exception(f"Error in simple 'get-context' call: {e}")
                raise SexpEvaluationError(f"Error in 'get-context': {e}", original_expr_str, error_details=str(e)) from e
                
        # Handle the full case with (key value) pairs
        context_params: Dict[str, Any] = {}
        context_strategy = Symbol("content-only") if Symbol != str else "content-only"  # Default

        for i, arg_expr_pair in enumerate(arg_exprs): 
            # Handle special case: first arg might be a direct query string without a key
            if i == 0 and not isinstance(arg_expr_pair, list):
                try:
                    query_value = await self.evaluator._eval(arg_expr_pair, env)
                    if not isinstance(query_value, str):
                        raise SexpEvaluationError(f"'get-context' query must be a string, got: {type(query_value)}", original_expr_str)
                    context_params["query"] = query_value
                    continue
                except SexpEvaluationError:
                    raise
                except Exception as e:
                    logging.exception(f"Error evaluating direct query argument: {e}")
                    raise SexpEvaluationError(f"Error evaluating query: {arg_expr_pair}", original_expr_str, error_details=str(e)) from e
            
            # Handle (key value) pairs
            if not (isinstance(arg_expr_pair, list) and len(arg_expr_pair) == 2 and isinstance(arg_expr_pair[0], Symbol)):
                raise SexpEvaluationError(f"Invalid argument format for 'get-context'. Expected (key_symbol value_expression), got: {arg_expr_pair}", original_expr_str)
            
            key_symbol = arg_expr_pair[0]
            value_expr_node = arg_expr_pair[1] 
            key_str = key_symbol.value()

            try:
                evaluated_value = await self.evaluator._eval(value_expr_node, env) 
                logging.debug(f"  apply_get_context_primitive: Evaluated value for key '{key_str}' ('{value_expr_node}'): {evaluated_value}")
            except SexpEvaluationError as e_val_eval:
                raise SexpEvaluationError(
                    f"Error evaluating value for '{key_str}' in 'get-context': {e_val_eval.args[0] if e_val_eval.args else str(e_val_eval)}",
                    expression=original_expr_str, 
                    error_details=f"Failed on value_expr='{e_val_eval.expression if hasattr(e_val_eval, 'expression') else value_expr_node}'. Original detail: {e_val_eval.error_details if hasattr(e_val_eval, 'error_details') else str(e_val_eval)}"
                ) from e_val_eval
            except Exception as e_val_eval:
                logging.exception(f"  apply_get_context_primitive: Error evaluating value for key '{key_str}' ('{value_expr_node}'): {e_val_eval}")
                raise SexpEvaluationError(f"Error evaluating value for '{key_str}' in 'get-context': {value_expr_node}", original_expr_str, error_details=str(e_val_eval)) from e_val_eval
            
            # Handle special case for context-strategy
            if key_str == "context-strategy":
                if not isinstance(evaluated_value, Symbol) and not isinstance(evaluated_value, str):
                    raise SexpEvaluationError(f"Context strategy must be a symbol: content-only or metadata-only, got {type(evaluated_value)}", original_expr_str)
                
                context_strategy = evaluated_value
                # Don't add to context_params, we'll handle it separately
                continue
                
            # Handle normal key-value pairs
            if key_str == "matching_strategy":
                allowed_strategies = {'content', 'metadata'}
                if not isinstance(evaluated_value, str) or evaluated_value not in allowed_strategies: 
                    raise SexpEvaluationError(f"Invalid value for 'matching_strategy'. Expected 'content' or 'metadata', got: {evaluated_value!r}", original_expr_str)
            
            context_params[key_str] = evaluated_value

        # Ensure we have a query
        if "query" not in context_params: 
            raise SexpEvaluationError("'get-context' requires a query parameter.", original_expr_str)

        # Process inputs conversion if needed
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
            
            # Create ContextGenerationInput
            context_input_obj = ContextGenerationInput(**context_params)
        except Exception as e: 
            logging.exception(f"  Error creating ContextGenerationInput from params {context_params}: {e}")
            raise SexpEvaluationError(f"Failed creating ContextGenerationInput for 'get-context': {e}", original_expr_str, error_details=str(e)) from e

        # Map context_strategy symbols to context strategies
        context_strategy_str = context_strategy.value() if isinstance(context_strategy, Symbol) else context_strategy
        if context_strategy_str == "content-only":
            strategy = "content"
        elif context_strategy_str == "metadata-only":
            strategy = "metadata"
        else:
            raise SexpEvaluationError(f"Invalid context strategy: {context_strategy_str}. Must be content-only or metadata-only.", original_expr_str)
            
        # Override the matching_strategy in the input object
        context_input_obj.matching_strategy = strategy

        try:
            logging.debug(f"  Calling memory_system.get_relevant_context_for with: {context_input_obj}")
            match_result: AssociativeMatchResult = await self.evaluator.memory_system.get_relevant_context_for(context_input_obj)
        except Exception as e: 
            logging.exception(f"  MemorySystem.get_relevant_context_for failed: {e}")
            raise SexpEvaluationError("Context retrieval failed during MemorySystem call.", original_expr_str, error_details=str(e)) from e

        # Convert result to a dictionary format
        result_dict = {
            "summary": match_result.context_summary or "",  # Ensure we have a string, not None
            "matches": [
                {
                    "id": item.id,
                    "content": item.content,
                    "relevance_score": item.relevance_score,
                    "content_type": item.content_type
                }
                for item in match_result.matches
            ]
        }
        
        # Include any error message if present
        if match_result.error:
            result_dict["error"] = match_result.error
            
        logging.debug(f"PrimitiveProcessor.apply_get_context_primitive END: returning dictionary with {len(result_dict['matches'])} matches")
        return result_dict

    async def apply_get_field_primitive(self, args: List[Any], env: 'SexpEnvironment', original_expr_str: str) -> Any: # Match user's signature
        logger.debug(f"PrimitiveProcessor.apply_get_field_primitive: {original_expr_str}") # Use original_expr_str
        if len(args) != 2: # Use args
            raise SexpEvaluationError(f"get-field: Expected 2 arguments, got {len(args)}", original_expr_str)

        target_obj_expr = args[0]
        field_name_expr = args[1]

        target_obj = await self.evaluator._eval(target_obj_expr, env)
        field_name_val_intermediate = await self.evaluator._eval(field_name_expr, env)

        field_name_str: str
        if isinstance(field_name_val_intermediate, Symbol):
            field_name_str = field_name_val_intermediate.value()
        elif isinstance(field_name_val_intermediate, str):
            field_name_str = field_name_val_intermediate
        else:
            raise SexpEvaluationError(f"get-field: Field name must evaluate to a string or symbol, got {type(field_name_val_intermediate)}", original_expr_str)

        if isinstance(target_obj, dict):
            if field_name_str in target_obj:
                return target_obj[field_name_str]
            else:
                logger.warning(f"get-field: Key '{field_name_str}' not found in dictionary.")
                return None 
        elif isinstance(target_obj, PydanticBaseModel): # Use imported PydanticBaseModel
            if hasattr(target_obj, field_name_str):
                # Ensure it's in model_fields to avoid accessing private/computed attrs unexpectedly
                if field_name_str in target_obj.__class__.model_fields:
                     return getattr(target_obj, field_name_str)
                else:
                    logger.warning(f"get-field: Field '{field_name_str}' is not a declared model field for {type(target_obj).__name__}, though attribute exists.")
                    return None 
            else:
                logger.warning(f"get-field: Field '{field_name_str}' not found in Pydantic model {type(target_obj).__name__}.")
                return None
        # Special-case TaskResult (if it's not a PydanticBaseModel or needs specific handling)
        elif isinstance(target_obj, TaskResult):
            try:
                return getattr(target_obj, field_name_str)
            except AttributeError:
                if hasattr(target_obj, 'parsedContent') and target_obj.parsedContent and isinstance(target_obj.parsedContent, dict):
                    if field_name_str in target_obj.parsedContent:
                        return target_obj.parsedContent.get(field_name_str)
                logger.warning(f"get-field: '{field_name_str}' missing in TaskResult and its parsedContent")
                return None
        else:
            try: # General object attribute access
                return getattr(target_obj, field_name_str)
            except AttributeError:
                logger.warning(f"get-field: Attribute '{field_name_str}' not found on object of type {type(target_obj)}.")
                return None

    async def apply_string_equal_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> bool:
        logger.debug(f"PrimitiveProcessor.apply_string_equal_primitive: {original_expr_str}")
        if len(arg_exprs) != 2:
            raise SexpEvaluationError("'string=?' requires exactly two string arguments.", original_expr_str)

        try:
            str1 = await self.evaluator._eval(arg_exprs[0], env)
            str2 = await self.evaluator._eval(arg_exprs[1], env)
        except Exception as e_eval:
            raise SexpEvaluationError(f"Error evaluating arguments for 'string=?': {e_eval}", original_expr_str, error_details=str(e_eval)) from e_eval

        if not isinstance(str1, str) or not isinstance(str2, str):
            raise SexpEvaluationError(f"'string=?' arguments must be strings. Got: {type(str1)}, {type(str2)}", original_expr_str)
        
        result = (str1 == str2)
        logger.debug(f"  'string=?': '{str1}' == '{str2}' -> {result}")
        return result

    async def apply_log_message_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any: 
        logger.debug(f"PrimitiveProcessor.apply_log_message_primitive: {original_expr_str}")
        if not arg_exprs:
            logger.info("SexpLog: (log-message) called with no arguments.") 
            return [] 
        
        evaluated_args = []
        for arg_expr in arg_exprs:
            try:
                evaluated_args.append(await self.evaluator._eval(arg_expr, env))
            except Exception as e_eval:
                logger.error(f"SexpLog: Error evaluating arg for log-message: {arg_expr} -> {e_eval}")
                evaluated_args.append(f"<Error evaluating: {arg_expr}>")

        log_output = " ".join(map(str, evaluated_args))
        logger.info(f"SexpLog: {log_output}") 
        return log_output 

    async def apply_eq_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> bool:
        logger.debug(f"PrimitiveProcessor.apply_eq_primitive: {original_expr_str}")
        if len(arg_exprs) != 2:
            raise SexpEvaluationError("'eq?' requires exactly two arguments.", original_expr_str)

        try:
            val1 = await self.evaluator._eval(arg_exprs[0], env)
            val2 = await self.evaluator._eval(arg_exprs[1], env)
        except Exception as e_eval:
            raise SexpEvaluationError(f"Error evaluating arguments for 'eq?': {e_eval}", original_expr_str, error_details=str(e_eval)) from e_eval

        # Handle Symbol comparison by their string value
        if isinstance(val1, Symbol): val1 = val1.value()
        if isinstance(val2, Symbol): val2 = val2.value()
        
        # Python's `==` handles most cases appropriately.
        result = (val1 == val2)
        logger.debug(f"  'eq?': {val1} == {val2} -> {result}")
        return result

    async def apply_null_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> bool:
        logger.debug(f"PrimitiveProcessor.apply_null_primitive: {original_expr_str}")
        if len(arg_exprs) != 1:
            raise SexpEvaluationError("'null?' requires exactly one argument.", original_expr_str)
        
        try:
            val = await self.evaluator._eval(arg_exprs[0], env)
        except Exception as e_eval:
            raise SexpEvaluationError(f"Error evaluating argument for 'null?': {e_eval}", original_expr_str, error_details=str(e_eval)) from e_eval
            
        # Consider Python None or an empty list as "null"
        result = (val is None or val == [])
        logger.debug(f"  'null?': {val} is None or [] -> {result}")
        return result

    async def apply_set_bang_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        logger.debug(f"PrimitiveProcessor.apply_set_bang_primitive: {original_expr_str}")
        if len(arg_exprs) != 2:
            raise SexpEvaluationError("'set!' requires exactly two arguments: a symbol and a new value expression.", original_expr_str)

        symbol_node = arg_exprs[0]
        new_value_expr = arg_exprs[1]

        if not isinstance(symbol_node, Symbol):
            raise SexpEvaluationError(f"'set!' first argument must be a symbol, got {type(symbol_node)}.", original_expr_str)
        
        symbol_name = symbol_node.value()
        
        try:
            new_value = await self.evaluator._eval(new_value_expr, env)
        except Exception as e_eval:
            raise SexpEvaluationError(f"Error evaluating new value for 'set! {symbol_name}': {e_eval}", original_expr_str, error_details=str(e_eval)) from e_eval

        try:
            env.set_value_in_scope(symbol_name, new_value)
            logger.debug(f"  'set!': Updated '{symbol_name}' to {new_value}")
            return new_value
        except NameError as e: 
            raise SexpEvaluationError(f"Cannot 'set!' unbound symbol: {symbol_name}. {e}", original_expr_str) from e
        except Exception as e_set: # Catch other unexpected errors from set_value_in_scope
            raise SexpEvaluationError(f"Error during 'set! {symbol_name}': {e_set}", original_expr_str, error_details=str(e_set)) from e_set

    async def apply_add_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any: # Number (int or float)
        logger.debug(f"PrimitiveProcessor.apply_add_primitive: {original_expr_str}")
        if not arg_exprs: # N-ary, but 0 args is allowed
            return 0 
        
        total = 0
        is_float = False
        for i, arg_expr in enumerate(arg_exprs):
            try:
                val = await self.evaluator._eval(arg_expr, env)
            except Exception as e_eval:
                raise SexpEvaluationError(f"Error evaluating argument {i+1} for '+': {e_eval}", original_expr_str, error_details=str(e_eval)) from e_eval

            if not isinstance(val, (int, float)):
                raise SexpEvaluationError(f"'+' argument {i+1} must be a number, got {type(val)}.", original_expr_str)
            if isinstance(val, float):
                is_float = True
            total += val
        
        result = float(total) if is_float else int(total)
        logger.debug(f"  '+': Result -> {result}")
        return result

    async def apply_subtract_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any: # Number
        logger.debug(f"PrimitiveProcessor.apply_subtract_primitive: {original_expr_str}")
        if not (1 <= len(arg_exprs) <= 2): # Arity check
            raise SexpEvaluationError("'-' requires one or two numeric arguments.", original_expr_str)

        try:
            val1 = await self.evaluator._eval(arg_exprs[0], env)
        except Exception as e_eval:
            raise SexpEvaluationError(f"Error evaluating first argument for '-': {e_eval}", original_expr_str, error_details=str(e_eval)) from e_eval
        
        if not isinstance(val1, (int, float)):
            raise SexpEvaluationError(f"'-' first argument must be a number, got {type(val1)}.", original_expr_str)

        if len(arg_exprs) == 1: # Unary negation
            result = -val1
            logger.debug(f"  '-' (unary): -{val1} -> {result}")
            return result
        
        # Binary subtraction
        try:
            val2 = await self.evaluator._eval(arg_exprs[1], env)
        except Exception as e_eval:
            raise SexpEvaluationError(f"Error evaluating second argument for '-': {e_eval}", original_expr_str, error_details=str(e_eval)) from e_eval

        if not isinstance(val2, (int, float)):
            raise SexpEvaluationError(f"'-' second argument must be a number, got {type(val2)}.", original_expr_str)
        
        result = 0
        if isinstance(val1, float) or isinstance(val2, float):
            result = float(val1) - float(val2)
        else:
            result = int(val1) - int(val2)
        logger.debug(f"  '-' (binary): {val1} - {val2} -> {result}")
        return result
        
    async def apply_less_than_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> bool:
        logger.debug(f"PrimitiveProcessor.apply_less_than_primitive: {original_expr_str}")
        if len(arg_exprs) != 2:
            raise SexpEvaluationError("'<' requires exactly two numeric arguments.", original_expr_str)

        try:
            val1 = await self.evaluator._eval(arg_exprs[0], env)
            val2 = await self.evaluator._eval(arg_exprs[1], env)
        except Exception as e_eval:
            raise SexpEvaluationError(f"Error evaluating arguments for '<': {e_eval}", original_expr_str, error_details=str(e_eval)) from e_eval

        if not (isinstance(val1, (int, float)) and isinstance(val2, (int, float))):
            raise SexpEvaluationError(f"'<' arguments must be numbers. Got: {type(val1)}, {type(val2)}", original_expr_str)
        
        result = (val1 < val2)
        logger.debug(f"  '<': {val1} < {val2} -> {result}")
        return result
        
    async def apply_string_append_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> str:
        """
        Applies the 'string-append' primitive: (string-append str1 str2 ...)
        Concatenates multiple string arguments into a single string.
        Converts None arguments to empty strings.
        Converts numbers (int, float) to their string representation.
        Raises SexpEvaluationError for other non-string/non-symbol types.
        """
        logger.debug(f"PrimitiveProcessor.apply_string_append_primitive: {original_expr_str}")
        
        evaluated_parts = []
        for i, arg_expr in enumerate(arg_exprs):
            try:
                evaluated_value = await self.evaluator._eval(arg_expr, env)
                logger.debug(f"  apply_string_append_primitive: Evaluated arg {i+1} ('{arg_expr}') to: {evaluated_value!r} (Type: {type(evaluated_value)})")
            except Exception as e_eval:
                logging.exception(f"  apply_string_append_primitive: Error evaluating argument {i+1} ('{arg_expr}'): {e_eval}")
                if isinstance(e_eval, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating argument {i+1} for 'string-append': {arg_expr}", original_expr_str, error_details=str(e_eval)) from e_eval
            
            if evaluated_value is None:
                logger.debug(f"  apply_string_append_primitive: Arg {i+1} was None, converting to string 'None'.")
                evaluated_parts.append("None")
            elif isinstance(evaluated_value, str):
                evaluated_parts.append(evaluated_value)
            elif isinstance(evaluated_value, Symbol):
                evaluated_parts.append(evaluated_value.value())
            elif isinstance(evaluated_value, (int, float)): # Allow numbers, convert to string
                logger.debug(f"  apply_string_append_primitive: Arg {i+1} was a number, converting to string: {str(evaluated_value)}")
                evaluated_parts.append(str(evaluated_value))
            else:
                # Stricter check: if not string, symbol, None, or number, then error
                raise SexpEvaluationError(
                    f"'string-append' argument {i+1} must be a string, symbol, number, or nil. Got {type(evaluated_value)}: {evaluated_value!r}.",
                    original_expr_str
                )
            
        result = ''.join(evaluated_parts)
        logger.debug(f"  'string-append': Result -> '{result}'")
        return result

    async def apply_not_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> bool:
        """Applies the 'not' primitive: (not expr)"""
        logger.debug(f"PrimitiveProcessor.apply_not_primitive: {original_expr_str}")
        if len(arg_exprs) != 1:
            raise SexpEvaluationError("'not' requires exactly one argument.", original_expr_str)

        try:
            value = await self.evaluator._eval(arg_exprs[0], env)
        except Exception as e_eval:
            raise SexpEvaluationError(f"Error evaluating argument for 'not': {e_eval}", original_expr_str, error_details=str(e_eval)) from e_eval

        # Lisp/Scheme convention: False and empty list are falsey, everything else is truthy.
        # Python's bool() handles most cases similarly (0, "", [], {}, None are False).
        # We can directly use Python's `not` on the evaluated result.
        result = not bool(value) # Apply Python's boolean negation
        logger.debug(f"  'not': Input value {value!r} resulted in {result}")
        return result
