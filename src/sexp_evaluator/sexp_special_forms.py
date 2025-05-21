"""
Processor for S-expression special forms.
This module will contain the SpecialFormProcessor class, which centralizes
the handling logic for all special forms in the S-expression language.
"""
import logging
from typing import Any, List, TYPE_CHECKING, Dict

from sexpdata import Symbol, Quoted as sexpdata_Quoted, Quoted # Ensure Quoted is imported if used directly

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

    async def handle_if_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Handles the 'if' special form: (if condition then_branch else_branch)"""
        logger.debug(f"SpecialFormProcessor.handle_if_form START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) != 3:
            raise SexpEvaluationError("'if' requires 3 arguments: (if condition then_branch else_branch)", original_expr_str)
        
        cond_expr, then_expr, else_expr = arg_exprs
        
        try:
            condition_result = await self.evaluator._eval(cond_expr, env)
            logger.debug(f"  'if' condition '{cond_expr}' evaluated to: {condition_result}")
        except Exception as e:
            logging.exception(f"  Error evaluating 'if' condition '{cond_expr}': {e}")
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error evaluating 'if' condition: {cond_expr}", original_expr_str, error_details=str(e)) from e

        chosen_branch_expr = then_expr if condition_result else else_expr
        logging.debug(f"  'if' chose branch: {chosen_branch_expr}")
        
        try:
            result = await self.evaluator._eval(chosen_branch_expr, env)
            logging.debug(f"SpecialFormProcessor.handle_if_form END: -> {result}")
            return result
        except Exception as e:
            logging.exception(f"  Error evaluating chosen 'if' branch '{chosen_branch_expr}': {e}")
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error evaluating chosen 'if' branch: {chosen_branch_expr}", original_expr_str, error_details=str(e)) from e

    async def handle_let_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Handles the 'let' special form: (let ((var expr)...) body...)"""
        logger.debug(f"SpecialFormProcessor.handle_let_form START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) < 1 or not isinstance(arg_exprs[0], list):
            raise SexpEvaluationError("'let' requires a bindings list and at least one body expression: (let ((var expr)...) body...)", original_expr_str)
        
        bindings_list_expr = arg_exprs[0]
        body_exprs = arg_exprs[1:]

        if not body_exprs:
            raise SexpEvaluationError("'let' requires at least one body expression.", original_expr_str)

        logging.debug(f"  'let' processing {len(bindings_list_expr)} binding expressions.")
        # Create the child environment *before* evaluating values, but evaluate values in the *outer* env.
        let_env = env.extend({}) # Create child environment for the 'let' scope

        # --- FIX: Evaluate values in the OUTER environment (env) ---
        evaluated_bindings = {} # Temporarily store evaluated values
        for binding_expr in bindings_list_expr:
            binding_expr_repr = str(binding_expr)
            if not (isinstance(binding_expr, list) and len(binding_expr) == 2 and isinstance(binding_expr[0], Symbol)):
                raise SexpEvaluationError(f"Invalid 'let' binding format: expected (symbol expression), got {binding_expr_repr}", original_expr_str)

            var_name_symbol = binding_expr[0]
            value_expr = binding_expr[1]
            var_name_str = var_name_symbol.value()

            try:
                # *** CRITICAL FIX: Evaluate value expression in the OUTER environment (env) ***
                logger.debug(f"    Evaluating value for '{var_name_str}' using OUTER env (id={id(env)})")
                evaluated_value = await self.evaluator._eval(value_expr, env)
                evaluated_bindings[var_name_str] = evaluated_value # Store evaluated value
                logger.debug(f"    Evaluated value for '{var_name_str}': {evaluated_value}")
            except Exception as e:
                logging.exception(f"  Error evaluating value for 'let' binding '{var_name_str}': {e}")
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating value for 'let' binding '{var_name_str}': {value_expr}", original_expr_str, error_details=str(e)) from e

        # --- FIX: Define all evaluated bindings in the INNER environment (let_env) ---
        for var_name_str, evaluated_value in evaluated_bindings.items():
            let_env.define(var_name_str, evaluated_value)
            logger.debug(f"    Defined '{var_name_str}' = {evaluated_value} in 'let' scope {id(let_env)}")

        # Evaluate body expressions in the new 'let' environment (let_env) - This part was correct
        final_result = [] # Default for empty body (though disallowed by check above)
        for i, body_item_expr in enumerate(body_exprs):
            try:
                final_result = await self.evaluator._eval(body_item_expr, let_env) # Use INNER env
                logging.debug(f"  'let' body expression {i+1} evaluated to: {final_result}")
            except Exception as e:
                logging.exception(f"  Error evaluating 'let' body expression {i+1} '{body_item_expr}': {e}")
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating 'let' body expression {i+1}: {body_item_expr}", original_expr_str, error_details=str(e)) from e
                
        logging.debug(f"SpecialFormProcessor.handle_let_form END: -> {final_result}")
        return final_result

    async def handle_bind_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Handles the 'bind' special form: (bind variable_symbol expression)"""
        logger.debug(f"SpecialFormProcessor.handle_bind_form START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) != 2 or not isinstance(arg_exprs[0], Symbol):
            raise SexpEvaluationError("'bind' requires a symbol and a value expression: (bind variable_symbol expression)", original_expr_str)

        var_name_symbol = arg_exprs[0]
        value_expr = arg_exprs[1]
        var_name_str = var_name_symbol.value()
        
        logging.debug(f"  Eval 'bind' for variable '{var_name_str}'")
        try:
            evaluated_value = await self.evaluator._eval(value_expr, env) # Evaluate value expression in current env
            env.define(var_name_str, evaluated_value) # Define in *current* environment
            logging.debug(f"  SpecialFormProcessor.handle_bind_form END: defined '{var_name_str}' = {evaluated_value} in env {id(env)}")
            return evaluated_value # 'bind' returns the assigned value
        except Exception as e:
            logging.exception(f"  Error evaluating value for 'bind' variable '{var_name_str}': {e}")
            if isinstance(e, SexpEvaluationError): raise
            raise SexpEvaluationError(f"Error evaluating value for 'bind' variable '{var_name_str}': {value_expr}", original_expr_str, error_details=str(e)) from e

    async def handle_progn_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Handles the 'progn' special form: (progn expr...)"""
        logger.debug(f"SpecialFormProcessor.handle_progn_form START: original_expr_str='{original_expr_str}'")
        final_result = [] # Default result for empty 'progn' is nil/[]
        
        for i, expr in enumerate(arg_exprs):
            try:
                final_result = await self.evaluator._eval(expr, env) # Evaluate each expression sequentially
                logging.debug(f"  'progn' expression {i+1} evaluated to: {final_result}")
            except Exception as e:
                logging.exception(f"  Error evaluating 'progn' expression {i+1} '{expr}': {e}")
                if isinstance(e, SexpEvaluationError): raise
                raise SexpEvaluationError(f"Error evaluating 'progn' expression {i+1}: {expr}", original_expr_str, error_details=str(e)) from e
                
        logging.debug(f"SpecialFormProcessor.handle_progn_form END: -> {final_result}")
        return final_result # Return result of the last expression

    async def handle_quote_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Handles the 'quote' special form: (quote expression)"""
        logger.debug(f"SpecialFormProcessor.handle_quote_form START: original_expr_str='{original_expr_str}'")
        if len(arg_exprs) != 1:
            raise SexpEvaluationError("'quote' requires exactly 1 argument", original_expr_str)
        
        # Return the argument node *without* evaluating it
        quoted_expression = arg_exprs[0]
        logging.debug(f"SpecialFormProcessor.handle_quote_form END: -> {quoted_expression} (unevaluated)")
        return quoted_expression

    async def handle_defatom_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Symbol:
        """Handles the 'defatom' special form: (defatom name params instructions ...)"""
        logger.debug(f"SpecialFormProcessor.handle_defatom_form START: original_expr_str='{original_expr_str}'")

        if len(arg_exprs) < 2: # Task name, instructions (minimum)
            raise SexpEvaluationError(
                "'defatom' requires at least name and instructions arguments.",
                original_expr_str
            )

        task_name_node = arg_exprs[0]
        if not isinstance(task_name_node, Symbol):
            raise SexpEvaluationError(
                f"Task name must be a symbol, got {type(task_name_node)}: {task_name_node}",
                original_expr_str
            )
        task_name_str = task_name_node.value()
        
        # Validate task name format (typical conventions allow alphanumeric, dash, underscore)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', task_name_str):
            raise SexpEvaluationError(
                f"Invalid task name '{task_name_str}'. Task name must only contain letters, numbers, underscores, and dashes.",
                original_expr_str
            )

        instructions_node: Any = None
        params_node: Any = None
        optional_arg_nodes: List[SexpNode] = []

        # Scan for instructions, params, and collect other optional arguments
        for arg_item_expr in arg_exprs[1:]:
            if isinstance(arg_item_expr, list) and len(arg_item_expr) > 0:
                # Check if the first element is a Symbol
                if not isinstance(arg_item_expr[0], Symbol):
                    raise SexpEvaluationError(
                        f"Attribute name must be a symbol: {arg_item_expr}",
                        original_expr_str
                    )
                    
                clause_type_symbol = arg_item_expr[0].value()
                if clause_type_symbol == "instructions":
                    if instructions_node is not None:
                        raise SexpEvaluationError(f"Duplicate attribute: instructions", original_expr_str)
                    instructions_node = arg_item_expr
                elif clause_type_symbol == "params":
                    if params_node is not None:
                        raise SexpEvaluationError(f"Duplicate attribute: params", original_expr_str)
                    params_node = arg_item_expr
                else:
                    # Assume it's an optional argument like (subtype ...), (description ...), (model ...), (output_format ...), (history_config ...)
                    optional_arg_nodes.append(arg_item_expr)
            else:
                # This argument is not a list, so it cannot be instructions, params, or a standard optional argument.
                # This could be an error, or a different kind of optional argument not yet defined.
                # For now, we'll treat it as an unexpected/invalid argument structure outside of name, instructions, params.
                raise SexpEvaluationError(
                    f"Attribute must be a list starting with a keyword: {arg_item_expr}",
                    original_expr_str
                )

        # Validate that 'instructions' clause was found and is correctly structured
        if instructions_node is None:
            raise SexpEvaluationError(f"Missing required 'instructions' attribute for task '{task_name_str}'", original_expr_str)
        if not (isinstance(instructions_node, list) and len(instructions_node) == 2 and isinstance(instructions_node[0], Symbol) and instructions_node[0].value() == "instructions" and isinstance(instructions_node[1], str)):
            raise SexpEvaluationError(f"'defatom' requires an (instructions \"string\") definition, got: {instructions_node} for task '{task_name_str}'", original_expr_str)
        instructions_str = instructions_node[1]

        # Params is optional - create empty params if not provided
        param_name_strings_for_template = []
        if params_node is not None:
            if not (isinstance(params_node, list) and len(params_node) > 0 and isinstance(params_node[0], Symbol) and params_node[0].value() == "params"):
                raise SexpEvaluationError(f"'defatom' requires a (params ...) definition, got: {params_node} for task '{task_name_str}'", original_expr_str)
        
            # Process params if provided
            for param_def_item in params_node[1:]: # Iterate over items within (params item1 item2 ...)
                if isinstance(param_def_item, Symbol):
                    param_name_strings_for_template.append(param_def_item.value())
                elif isinstance(param_def_item, list) and len(param_def_item) >= 1 and isinstance(param_def_item[0], Symbol): # Support (param_name type?)
                    param_name_strings_for_template.append(param_def_item[0].value())
                else:
                     raise SexpEvaluationError(
                        f"Invalid parameter definition format in (params ...) for task '{task_name_str}'. Expected symbol or (symbol type?), got: {param_def_item}",
                        original_expr_str
                    )

        # Create template_params with proper types
        template_params = {}
        if params_node is not None:
            for param_def_item in params_node[1:]: # Iterate over items within (params item1 item2 ...)
                if isinstance(param_def_item, Symbol):
                    # When param is just Symbol('param_name'), add default type
                    param_name = param_def_item.value()
                    template_params[param_name] = {
                        "type": "any"
                    }
                    
                elif isinstance(param_def_item, list) and len(param_def_item) >= 1 and isinstance(param_def_item[0], Symbol):
                    # When param is (param_name "type_string"), extract both
                    param_name = param_def_item[0].value()
                    if len(param_def_item) >= 2 and isinstance(param_def_item[1], str):
                        # If we have a type string specified
                        template_params[param_name] = {
                            "type": param_def_item[1]
                        }
                    elif len(param_def_item) >= 2 and isinstance(param_def_item[1], Symbol):
                        # If type is a Symbol (like 'string or 'object), convert it to a string
                        type_symbol = param_def_item[1]
                        type_str = type_symbol.value()
                        template_params[param_name] = {
                            "type": type_str
                        }
                    elif len(param_def_item) >= 2 and isinstance(param_def_item[1], list):
                        # Handle complex type definitions like (param_name (object (field1 type1) ...))
                        try:
                            complex_type = param_def_item[1]
                            logger.debug(f"Processing complex type: {complex_type}")
                            # Check if it's a list with 'object' as first element (either as Symbol or string)
                            if len(complex_type) >= 1:
                                is_object_type = False
                                if isinstance(complex_type[0], Symbol) and complex_type[0].value() == "object":
                                    is_object_type = True
                                elif complex_type[0] == "object":
                                    is_object_type = True
                                
                                if is_object_type:
                                    type_dict = {"type": "object", "properties": {}}
                                    # Process the fields
                                    for field_def in complex_type[1:]:
                                        if isinstance(field_def, list) and len(field_def) >= 2:
                                            # Handle both Symbol and string field names
                                            if isinstance(field_def[0], Symbol):
                                                field_name = field_def[0].value()
                                            elif isinstance(field_def[0], str):
                                                field_name = field_def[0]
                                            else:
                                                field_name = str(field_def[0])
                                                
                                            field_type = field_def[1]
                                            if isinstance(field_type, Symbol):
                                                type_dict["properties"][field_name] = {"type": field_type.value()}
                                            elif isinstance(field_type, str):
                                                type_dict["properties"][field_name] = {"type": field_type}
                                            else:
                                                logger.warning(f"Complex field type not understood: {field_type}. Using 'any'.")
                                                type_dict["properties"][field_name] = {"type": "any"}
                                        
                                    template_params[param_name] = type_dict
                                    logger.debug(f"Created object type for {param_name}: {type_dict}")
                                else:
                                    # If complex type isn't following expected structure, fallback
                                    template_params[param_name] = {
                                        "type": "any"
                                    }
                        except Exception as e:
                            logger.error(f"Failed to parse complex type for param '{param_name}': {e}")
                            template_params[param_name] = {
                                "type": "any"
                            }
                    else:
                        # If no type string or invalid type (should not happen given validation above)
                        template_params[param_name] = {
                            "type": "any"
                        }

        optional_args_map: Dict[str, Any] = {} # Allow Any for structured values
        # Keys that expect a simple string value
        simple_string_optionals = {"subtype", "description", "model", "type"}
        # Keys that expect a structured value (list of lists/pairs)
        structured_optionals = {"output_format", "history_config"}

        # Process collected optional arguments
        for opt_node in optional_arg_nodes:
            # Validation for opt_node structure (already implicitly checked by the collection loop, but good for clarity)
            # if not (isinstance(opt_node, list) and len(opt_node) >= 2 and isinstance(opt_node[0], Symbol)): # This check is effectively done above
            #     raise SexpEvaluationError( # This specific error path should ideally not be hit if collection logic is correct
            #         f"Invalid optional argument format for 'defatom' task '{task_name_str}'. Expected (key value_expression), got: {opt_node}",
            #         original_expr_str
            #     )
            # The collection loop ensures opt_node is a list and opt_node[0] is a Symbol.
            # We still need to check len(opt_node) >= 2 for (key value) structure.
            
            key_node: Symbol = opt_node[0]
            # Ensure there's a value part. opt_node[1] is the start of the value.
            # For simple string optionals, opt_node[1] is the string.
            # For structured, opt_node[1] is the list of pairs OR (quote list-of-pairs).
            if len(opt_node) < 2:
                raise SexpEvaluationError(
                    f"Attribute must have at least two elements: {opt_node}",
                    original_expr_str
                )
            
            value_part_from_opt_node: Any = opt_node[1] # This is the S-expression value part
            key_str = key_node.value()

            if key_str == "depends":
                # Handle dependencies - handle both single dependency and multiple dependencies as arguments
                dependencies = []
                
                # Process dependencies from all remaining arguments in the "depends" form
                for i in range(1, len(opt_node)):
                    dep_node = opt_node[i]
                    if isinstance(dep_node, Symbol):
                        # Single dependency as a Symbol
                        dependencies.append(dep_node.value())
                    elif isinstance(dep_node, str):
                        # Single dependency as a string
                        dependencies.append(dep_node)
                    elif isinstance(dep_node, list):
                        # Process a list of dependencies
                        for dep_item in dep_node:
                            if isinstance(dep_item, Symbol):
                                dependencies.append(dep_item.value())
                            elif isinstance(dep_item, str):
                                dependencies.append(dep_item)
                            else:
                                raise SexpEvaluationError(
                                    f"Invalid dependency in 'depends' clause. Expected symbol or string, got {type(dep_item)}: {dep_item!r}",
                                    original_expr_str
                                )
                    else:
                        raise SexpEvaluationError(
                            f"Invalid dependency in 'depends' clause. Expected symbol, string, or list, got {type(dep_node)}: {dep_node!r}",
                            original_expr_str
                        )
                
                # Only add if we found dependencies
                if dependencies:
                    optional_args_map["dependencies"] = dependencies
                    logger.debug(f"Parsed dependencies for task '{task_name_str}': {dependencies}")
                
            elif key_str in simple_string_optionals:
                if not isinstance(value_part_from_opt_node, str): # Check the S-expression value directly
                    raise SexpEvaluationError(f"Value for optional argument '{key_str}' must be a string, got {type(value_part_from_opt_node)}: {value_part_from_opt_node!r}", original_expr_str)
                optional_args_map[key_str] = value_part_from_opt_node
            elif key_str in structured_optionals:
                actual_list_of_pairs = value_part_from_opt_node

                # Check if the value_part_from_opt_node is a (quote <list_of_pairs>) S-expression
                # The AST for (quote X) is [Symbol('quote'), X]
                if isinstance(value_part_from_opt_node, list) and \
                   len(value_part_from_opt_node) == 2 and \
                   isinstance(value_part_from_opt_node[0], Symbol) and \
                   value_part_from_opt_node[0].value() == 'quote':
                    
                    # It's quoted, get the actual list of pairs
                    actual_list_of_pairs = value_part_from_opt_node[1]
                    logger.debug(f"Unwrapped quoted value for '{key_str}': {actual_list_of_pairs!r}")
                
                # Now, actual_list_of_pairs should be the list like ((type "json") ...)
                if not isinstance(actual_list_of_pairs, list):
                    raise SexpEvaluationError(
                        f"Value for structured optional argument '{key_str}' must resolve to a list of pairs. Got {type(actual_list_of_pairs)}: {actual_list_of_pairs!r}",
                        original_expr_str
                    )

                structured_dict: Dict[str, Any] = {}
                for pair_idx, pair in enumerate(actual_list_of_pairs): # Iterate over the (now correctly unwrapped) list of pairs
                    if not (isinstance(pair, list) and len(pair) == 2 and isinstance(pair[0], Symbol)):
                        raise SexpEvaluationError(
                            f"Invalid pair format in '{key_str}' at index {pair_idx}. Expected (key_symbol value), got: {pair!r}",
                            original_expr_str
                        )
                    
                    inner_key_symbol: Symbol = pair[0]
                    inner_sexp_value: Any = pair[1] # This is an S-expression value from the pair

                    python_value: Any
                    if isinstance(inner_sexp_value, str):
                        python_value = inner_sexp_value
                    elif isinstance(inner_sexp_value, Symbol):
                        val_str = inner_sexp_value.value()
                        if val_str == 'true':
                            python_value = True
                        elif val_str == 'false':
                            python_value = False
                        elif val_str == 'nil': # Symbol 'nil' should map to Python None
                            python_value = None
                        else: # Any other symbol in a value context is an error unless it's a string
                            raise SexpEvaluationError(
                                f"Invalid symbol value '{val_str}' for key '{inner_key_symbol.value()}' in '{key_str}'. Expected 'true', 'false', or 'nil'. If a string is intended, it must be quoted in the S-expression (e.g., \"some-symbol-as-string\").",
                                original_expr_str
                            )
                    elif isinstance(inner_sexp_value, int):
                        python_value = inner_sexp_value
                    elif isinstance(inner_sexp_value, list) and not inner_sexp_value and \
                         key_str == "history_config" and inner_key_symbol.value() == "history_turns_to_include":
                        # If SexpParser turned 'nil' into [], treat [] as None for history_turns_to_include
                        logger.debug(f"Interpreting empty list [] as None for 'history_turns_to_include' in 'defatom {key_str}'.")
                        python_value = None
                    elif inner_sexp_value is None and key_str == "history_config" and inner_key_symbol.value() == "history_turns_to_include":
                        # This case specifically allows Python None for history_turns_to_include if the S-expression value was (quote nil)
                        # which sexpdata parses to Python None if not wrapped in a Symbol object.
                        # However, if (quote nil) is parsed as Symbol('nil'), the Symbol case above handles it.
                        # This explicit check is for robustness if the parser yields Python None directly for (quote nil).
                        python_value = None
                    else:
                        raise SexpEvaluationError(
                            f"Invalid value type for key '{inner_key_symbol.value()}' in '{key_str}'. "
                            f"Expected S-expression string (e.g., \"json\"), S-expression symbol (true/false/nil), "
                            f"S-expression integer, or an empty list [] for 'history_turns_to_include'. "
                            f"Got {type(inner_sexp_value)}: {inner_sexp_value!r}",
                            original_expr_str
                        )
                    
                    structured_dict[inner_key_symbol.value()] = python_value
                optional_args_map[key_str] = structured_dict
                logger.debug(f"Parsed structured optional arg '{key_str}': {structured_dict}")
            else:
                raise SexpEvaluationError(f"Unknown attribute name: {key_str}. Allowed attributes: {list(simple_string_optionals | structured_optionals)}", original_expr_str)
        
        template_dict: Dict[str, Any] = {
            "name": task_name_str,
            "type": optional_args_map.get("type", "atomic"),
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
        if "dependencies" in optional_args_map:
            template_dict["dependencies"] = optional_args_map["dependencies"]


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

        # We will use the async wrapper function from defatom_wrapper.py instead

        # Import the async wrapper creator function
        from src.sexp_evaluator.defatom_wrapper import create_async_defatom_task_wrapper
        
        # Create and bind the async wrapper function
        async_wrapper = await create_async_defatom_task_wrapper(
            task_name_str=task_name_str,
            param_name_strings=param_name_strings_for_template,
            evaluator_ref=self.evaluator
        )
        
        env.define(task_name_str, async_wrapper) # Bind the async wrapper
        logging.info(f"Successfully registered and lexically bound dynamic task '{task_name_str}'.")
        # Return the task name as a string, not a Symbol
        return task_name_str

    async def handle_loop_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Handles the 'loop' special form: (loop count_expr body_expr)"""
        logger.debug(f"SpecialFormProcessor.handle_loop_form START: original_expr_str='{original_expr_str}'")

        if len(arg_exprs) != 2:
            raise SexpEvaluationError(f"Loop requires exactly 2 arguments: count_expression and body_expression. Got {len(arg_exprs)}.", original_expr_str)
        
        count_expr, body_expr = arg_exprs

        try:
            logger.debug(f"  Evaluating loop count expression: {count_expr}")
            count_value = await self.evaluator._eval(count_expr, env)
            logger.debug(f"  Loop count expression evaluated to: {count_value} (Type: {type(count_value)})")
        except SexpEvaluationError as e_count: 
            logger.exception(f"Error evaluating loop count expression '{count_expr}': {e_count}")
            raise SexpEvaluationError(
                f"Error evaluating loop count expression: {e_count.args[0] if e_count.args else str(e_count)}",
                expression=original_expr_str, 
                error_details=f"Failed on count_expr='{e_count.expression if hasattr(e_count, 'expression') else count_expr}'. Original detail: {e_count.error_details if hasattr(e_count, 'error_details') else str(e_count)}"
            ) from e_count
        except Exception as e: 
            logger.exception(f"Error evaluating loop count expression '{count_expr}': {e}")
            raise SexpEvaluationError(f"Error evaluating loop count expression: {count_expr}", original_expr_str, error_details=str(e)) from e

        if not isinstance(count_value, int):
            raise SexpEvaluationError(f"Loop count must evaluate to an integer.", original_expr_str, f"Got type: {type(count_value)} for count '{count_value}'")
        if count_value < 0:
            raise SexpEvaluationError(f"Loop count must be non-negative.", original_expr_str, f"Got value: {count_value}")

        n = count_value
        if n == 0:
            logger.debug("Loop count is 0, skipping body execution and returning [].")
            return [] 

        last_result: Any = [] 
        logger.debug(f"Starting loop execution for {n} iterations.")
        for i in range(n):
            iteration = i + 1
            logger.debug(f"  Loop iteration {iteration}/{n}. Evaluating body: {body_expr}")
            try:
                last_result = await self.evaluator._eval(body_expr, env)
                logger.debug(f"  Iteration {iteration}/{n} result: {last_result}")
            except SexpEvaluationError as e_body:
                logger.exception(f"Error evaluating loop body during iteration {iteration}/{n} for '{body_expr}': {e_body}")
                raise SexpEvaluationError(
                    f"Error during loop iteration {iteration}/{n}: {e_body.args[0] if e_body.args else str(e_body)}",
                    expression=original_expr_str, 
                    error_details=f"Failed on body_expr='{e_body.expression if hasattr(e_body, 'expression') else body_expr}'. Original detail: {e_body.error_details if hasattr(e_body, 'error_details') else str(e_body)}"
                ) from e_body
            except Exception as e: 
                logger.exception(f"Unexpected error evaluating loop body during iteration {iteration}/{n} for '{body_expr}': {e}")
                raise SexpEvaluationError(
                    f"Unexpected error during loop iteration {iteration}/{n} processing body '{body_expr}': {str(e)}",
                    expression=original_expr_str,
                    error_details=str(e)
                ) from e
                
        logger.debug(f"SpecialFormProcessor.handle_loop_form finished after {n} iterations. Returning last result: {last_result}")
        return last_result

    async def handle_director_loop(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """
        Handles the 'director-loop' special form.
        
        Syntax:
        (director-loop 
          :max-iterations n
          :init-phase (lambda (...) ...)
          :controller (lambda (state) ...)
          :body-phase (lambda (state) ...)
          :config {...})
        
        Args:
            arg_exprs: A list of SexpNode objects representing the arguments 
                       to the director-loop form.
            env: The current SexpEnvironment for evaluation.
            original_expr_str: The string representation of the original S-expression call.
            
        Returns:
            The final state after loop completion.
            
        Raises:
            SexpEvaluationError: For syntax errors, type errors, or runtime errors during loop execution.
        """
        logger.debug(f"SpecialFormProcessor.handle_director_loop START: {original_expr_str}")
        
        if not arg_exprs:
            raise SexpEvaluationError("director-loop requires at least 1 argument", original_expr_str)
        
        # Parse the director-loop arguments
        max_iterations = None
        init_phase_fn = None
        controller_fn = None
        body_phase_fn = None
        config = None
        
        # Parse director-loop clauses
        i = 0
        while i < len(arg_exprs):
            if not isinstance(arg_exprs[i], Symbol):
                raise SexpEvaluationError(f"director-loop expects keyword arguments (e.g., :max-iterations), got: {arg_exprs[i]}", original_expr_str)
            
            key_symbol = arg_exprs[i]
            key_str = key_symbol.value()
            
            # Ensure there's a value after each key
            if i + 1 >= len(arg_exprs):
                raise SexpEvaluationError(f"Missing value for '{key_str}' in director-loop", original_expr_str)
            
            value_expr = arg_exprs[i + 1]
            
            # Process each key-value pair
            if key_str == "max-iterations":
                try:
                    max_iterations = await self.evaluator._eval(value_expr, env)
                    if not isinstance(max_iterations, int):
                        raise SexpEvaluationError(f"max-iterations must be a number", original_expr_str)
                except Exception as e:
                    if isinstance(e, SexpEvaluationError):
                        raise
                    raise SexpEvaluationError(f"Error evaluating max-iterations: {e}", original_expr_str) from e
            elif key_str == "init-phase":
                try:
                    init_phase_fn = await self.evaluator._eval(value_expr, env)
                    if not callable(init_phase_fn):
                        raise SexpEvaluationError(f"init-phase must be a callable", original_expr_str)
                except Exception as e:
                    if isinstance(e, SexpEvaluationError):
                        raise
                    raise SexpEvaluationError(f"Error evaluating init-phase: {e}", original_expr_str) from e
            elif key_str == "controller":
                try:
                    controller_fn = await self.evaluator._eval(value_expr, env)
                    if not callable(controller_fn):
                        raise SexpEvaluationError(f"controller must be a callable", original_expr_str)
                except Exception as e:
                    if isinstance(e, SexpEvaluationError):
                        raise
                    raise SexpEvaluationError(f"Error evaluating controller: {e}", original_expr_str) from e
            elif key_str == "body-phase":
                try:
                    body_phase_fn = await self.evaluator._eval(value_expr, env)
                    if not callable(body_phase_fn):
                        raise SexpEvaluationError(f"body-phase must be a callable", original_expr_str)
                except Exception as e:
                    if isinstance(e, SexpEvaluationError):
                        raise
                    raise SexpEvaluationError(f"Error evaluating body-phase: {e}", original_expr_str) from e
            elif key_str == "config":
                try:
                    config = await self.evaluator._eval(value_expr, env)
                except Exception as e:
                    if isinstance(e, SexpEvaluationError):
                        raise
                    raise SexpEvaluationError(f"Error evaluating config: {e}", original_expr_str) from e
            else:
                raise SexpEvaluationError(f"Unknown director-loop argument: {key_str}", original_expr_str)
            
            i += 2  # Move to the next key-value pair
        
        # Ensure required clauses are provided
        if init_phase_fn is None:
            raise SexpEvaluationError("director-loop requires an init-phase function", original_expr_str)
        if controller_fn is None:
            raise SexpEvaluationError("director-loop requires a controller function", original_expr_str)
        if body_phase_fn is None:
            raise SexpEvaluationError("director-loop requires a body-phase function", original_expr_str)
        
        # Default max_iterations if not specified
        if max_iterations is None:
            max_iterations = 10  # Default value
            logger.debug(f"  Using default max-iterations: {max_iterations}")
        
        # Run the init-phase to get the initial state
        try:
            if config is not None:
                current_state = await init_phase_fn(config)
            else:
                current_state = await init_phase_fn()
            logger.debug(f"  Init phase returned state: {current_state}")
        except SexpEvaluationError as e:
            # Re-raise SexpEvaluationError directly to preserve its details
            raise
        except Exception as e:
            # For other exceptions, we need to re-raise them directly without wrapping
            # to match the expected test behavior
            logger.exception(f"  Error in init-phase: {e}")
            raise e
        
        # Main loop
        for iteration in range(max_iterations):
            logger.debug(f"  Director-loop iteration {iteration + 1}/{max_iterations}")
            
            # Run the controller to determine next action
            try:
                if config is not None:
                    controller_result = await controller_fn(current_state, config)
                else:
                    controller_result = await controller_fn(current_state)
                
                logger.debug(f"  Controller returned: {controller_result}")
                
                # Validate controller result
                if not isinstance(controller_result, list):
                    raise SexpEvaluationError("Controller must return a list", original_expr_str)
                
                # Check if controller says to stop
                if controller_result[0] == "stop":
                    logger.debug(f"  Controller requested stop at iteration {iteration + 1}")
                    break
                
            except SexpEvaluationError as e:
                # Re-raise SexpEvaluationError directly to preserve its details
                raise
            except Exception as e:
                # For other exceptions, we need to re-raise them directly without wrapping
                # to match the expected test behavior
                logger.exception(f"  Error in controller: {e}")
                raise e
            
            # Run the body-phase to update the state
            try:
                if config is not None:
                    current_state = await body_phase_fn(current_state, config)
                else:
                    current_state = await body_phase_fn(current_state)
                logger.debug(f"  Body phase updated state: {current_state}")
            except SexpEvaluationError as e:
                # Re-raise SexpEvaluationError directly to preserve its details
                raise
            except Exception as e:
                # For other exceptions, we need to re-raise them directly without wrapping
                # to match the expected test behavior
                logger.exception(f"  Error in body-phase: {e}")
                raise e
        
        logger.debug(f"SpecialFormProcessor.handle_director_loop END: -> {current_state}")
        return current_state

    async def handle_director_evaluator_loop(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
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
            max_iter_val = await self.evaluator._eval(clauses["max-iterations"], env)
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
            current_director_input_val = await self.evaluator._eval(clauses["initial-director-input"], env)
        except SexpEvaluationError as e:
            raise SexpEvaluationError(f"director-evaluator-loop: Error evaluating 'initial-director-input': {e.args[0] if e.args else str(e)}", original_expr_str, error_details=e.error_details if hasattr(e, 'error_details') else str(e)) from e
        except Exception as e:
            raise SexpEvaluationError(f"director-evaluator-loop: Error evaluating 'initial-director-input': {e}", original_expr_str, error_details=str(e)) from e

        # 3. Evaluate and Validate Phase Function Expressions (with validation)
        phase_functions: Dict[str, Any] = {}
        for phase_name in ["director", "executor", "evaluator", "controller"]:
            try:
                resolved_fn = await self.evaluator._eval(clauses[phase_name], env)
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
            
            # Ensure *loop-config* is properly defined in the environment
            if '*loop-config*' not in phase_call_env.get_local_bindings():
                logger.warning(f"  *loop-config* not found in local bindings after extend, explicitly defining it")
                phase_call_env.define('*loop-config*', loop_config_data)

            try:
                # b. Director Phase - Pass ONLY required args per ADR
                plan_val = await self.evaluator._call_phase_function(
                    "director", director_fn, [current_director_input_val, current_iteration],
                    phase_call_env, original_expr_str, current_iteration
                )
                logger.debug(f"    Director result: {str(plan_val)[:200]}...")

                # c. Executor Phase - Pass ONLY required args per ADR
                exec_result_val = await self.evaluator._call_phase_function(
                    "executor", executor_fn, [plan_val, current_iteration],
                    phase_call_env, original_expr_str, current_iteration
                )
                logger.debug(f"    Executor result: {str(exec_result_val)[:200]}...")
                last_exec_result_val = exec_result_val

                # d. Evaluator Phase - Pass ONLY required args per ADR
                eval_feedback_val = await self.evaluator._call_phase_function(
                    "evaluator", evaluator_fn, [exec_result_val, plan_val, current_iteration],
                    phase_call_env, original_expr_str, current_iteration
                )
                logger.debug(f"    Evaluator result: {str(eval_feedback_val)[:200]}...")

                # e. Controller Phase - Pass ONLY required args per ADR
                decision_val = await self.evaluator._call_phase_function(
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
                    f"Controller must return a list of (action_symbol value), got: {decision_val!r}",
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
                    f"Controller decision action must be 'continue' or 'stop' symbol, got: '{action_str}'",
                    original_expr_str
                )
        else: # Loop finished due to max_iterations
            logger.info(f"  Loop finished after reaching max_iterations ({max_iter_val}).")
            # --- CORRECTED ASSIGNMENT ---
            # Return the result of the last EXECUTOR phase if max iterations hit
            loop_result = last_exec_result_val

        logger.debug(f"SpecialFormProcessor.handle_director_evaluator_loop END -> {str(loop_result)[:200]}...")
        return loop_result # Return the final determined result

    async def handle_and_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
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
                last_value = await self.evaluator._eval(expr, env)
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

    async def handle_or_form(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
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
                last_value = await self.evaluator._eval(expr, env)
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

    async def handle_iterative_loop(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
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
        required_clauses = {"max-iterations", "initial-input", "command-generator", "executor", "validator", "controller"}
        # Map command-generator to test-command for backward compatibility
        key_aliases = {"command-generator": "test-command", "test-command": "command-generator"}

        # Support both formats: list of clauses or flat key-value pairs
        # Check if the arguments are in pairs (key1, value1, key2, value2, ...)
        if len(arg_exprs) >= 2 and all(isinstance(arg_exprs[i], Symbol) for i in range(0, len(arg_exprs), 2) if i < len(arg_exprs)):
            # Process arguments as flat list of key-value pairs
            if len(arg_exprs) % 2 != 0:
                raise SexpEvaluationError(
                    f"iterative-loop: Uneven number of arguments. Expected key-value pairs.",
                    original_expr_str
                )
            
            for i in range(0, len(arg_exprs), 2):
                if i + 1 >= len(arg_exprs):
                    break  # Safety check
                    
                key_symbol = arg_exprs[i]
                value_expr = arg_exprs[i + 1]
                
                if not isinstance(key_symbol, Symbol):
                    raise SexpEvaluationError(
                        f"iterative-loop: Key must be a symbol, got: {key_symbol}",
                        original_expr_str
                    )
                
                key_str = key_symbol.value()
                # Remove leading colon if present (for :key-name style)
                if key_str.startswith(':'):
                    key_str = key_str[1:]
                    
                if key_str in clauses:
                    raise SexpEvaluationError(
                        f"iterative-loop: Duplicate key '{key_str}' found.",
                        original_expr_str
                    )
                
                clauses[key_str] = value_expr
        else:
            # Process arguments as list of (key value) pairs
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

        # Check for missing required keys, considering aliases
        effective_keys = set(clauses.keys())
        for key in list(clauses.keys()):
            if key in key_aliases:
                # If alias is provided, consider the required key as effectively present
                effective_keys.add(key_aliases[key])
        
        missing = required_clauses - effective_keys
        if missing:
            raise SexpEvaluationError(
                f"iterative-loop: Missing required parameters: {', '.join(sorted(list(missing)))}",
                original_expr_str
            )

        # 2. Evaluate Configuration Expressions (with validation)
        try:
            max_iter_val = await self.evaluator._eval(clauses["max-iterations"], env)
            if not isinstance(max_iter_val, int) or max_iter_val < 0:
                raise SexpEvaluationError(
                    f"'max-iterations' must evaluate to a non-negative integer, got {max_iter_val!r} (type: {type(max_iter_val)}).",
                    original_expr_str
                )
        except SexpEvaluationError:
            # Re-raise SexpEvaluationError directly to preserve its details
            raise
        except Exception as e:
            raise SexpEvaluationError(f"iterative-loop: Error evaluating 'max-iterations': {e}", original_expr_str, error_details=str(e)) from e

        try:
            current_loop_input = await self.evaluator._eval(clauses["initial-input"], env)
            logger.debug(f"iterative-loop: Evaluated 'initial-input' to: {current_loop_input!r} (Type: {type(current_loop_input)})")
            
            # Handle Quoted objects by extracting their inner value
            if isinstance(current_loop_input, sexpdata_Quoted):
                try:
                    # Try multiple attribute names that might contain the inner value
                    inner_val = None
                    for attr_name in ['x', 'val', 'value', '_value']:
                        if hasattr(current_loop_input, attr_name):
                            inner_val = getattr(current_loop_input, attr_name)
                            logger.debug(f"iterative-loop: Extracted value from Quoted 'initial-input' using '{attr_name}': {inner_val!r}")
                            break
                    
                    # If we still don't have a value, try indexing if possible
                    if inner_val is None and hasattr(current_loop_input, '__getitem__'):
                        try:
                            inner_val = current_loop_input[0]
                            logger.debug(f"iterative-loop: Extracted value from Quoted 'initial-input' using indexing: {inner_val!r}")
                        except (IndexError, TypeError):
                            pass
                    
                    if inner_val is not None:
                        current_loop_input = inner_val
                        logger.debug(f"iterative-loop: Updated current_loop_input with extracted value: {current_loop_input!r}")
                    else:
                        logger.warning(f"iterative-loop: Could not extract inner value from Quoted object: {current_loop_input!r}")
                except Exception as e_quoted:
                    logger.exception(f"iterative-loop: Error extracting value from Quoted object: {e_quoted}")
            
            # Handle Symbol objects by converting to their string value
            if isinstance(current_loop_input, Symbol):
                logger.debug(f"iterative-loop: Converting Symbol to string: {current_loop_input!r}")
                current_loop_input = current_loop_input.value()
                logger.debug(f"iterative-loop: Converted Symbol 'initial-input' to string: {current_loop_input}")
            
        except Exception as e:
            raise SexpEvaluationError(f"iterative-loop: Error evaluating 'initial-input': {e}", original_expr_str, error_details=str(e)) from e

        try:
            # Use command-generator if available, otherwise test-command
            cmd_generator_key = "command-generator" if "command-generator" in clauses else "test-command"
            
            cmd_generator_fn = await self.evaluator._eval(clauses[cmd_generator_key], env)
            if not isinstance(cmd_generator_fn, self.evaluator.Closure) and not callable(cmd_generator_fn):
                raise SexpEvaluationError(
                    f"iterative-loop: '{cmd_generator_key}' must evaluate to a callable function, got {cmd_generator_fn!r} (type: {type(cmd_generator_fn)}).",
                    original_expr_str
                )
        except KeyError:
            # This should not happen due to our earlier check for missing keys
            raise SexpEvaluationError(f"iterative-loop: Missing required command generator", original_expr_str)
        except Exception as e:
            raise SexpEvaluationError(f"iterative-loop: Error evaluating '{cmd_generator_key}': {e}", original_expr_str, error_details=str(e)) from e

        # 3. Evaluate and Validate Phase Function Expressions (with validation)
        phase_functions: Dict[str, Any] = {}
        for phase_name in ["executor", "validator", "controller"]:
            try:
                resolved_fn = await self.evaluator._eval(clauses[phase_name], env)
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
        last_exec_result_val: Any = None # Store last successful exec result

        if max_iter_val == 0:
            logger.info("iterative-loop: max-iterations is 0, returning [].")
            return [] # Return S-expression nil

        # 5. Main Loop
        while current_iteration <= max_iter_val:
            logger.debug(f"--- Iterative Loop: Iteration {current_iteration}/{max_iter_val} ---")

            try:
                # --- Command Generator Phase ---
                command = await self.evaluator._call_phase_function(
                    "command-generator", cmd_generator_fn, [current_loop_input],
                    env, original_expr_str, current_iteration
                )
                logger.debug(f"  Generated command: {command}")
                
                # --- Executor Phase ---
                executor_result = await self.evaluator._call_phase_function(
                    "executor", executor_fn, [command],
                    env, original_expr_str, current_iteration
                )
                logger.debug(f"  executor_result type: {type(executor_result)}")
                
                last_exec_result_val = executor_result # Store potentially final result

                # --- Validator Phase ---
                validation_result = await self.evaluator._call_phase_function(
                    "validator", validator_fn, [command, executor_result],
                    env, original_expr_str, current_iteration
                )

                # --- Controller Phase ---
                decision_val = await self.evaluator._call_phase_function(
                    "controller", controller_fn, [current_loop_input, command, executor_result, validation_result],
                    env, original_expr_str, current_iteration
                )

            except Exception as phase_error:
                logger.exception(f"  Error during iterative-loop iteration {current_iteration}: {phase_error}")
                
                # Always include iteration in both message and details
                error_details = {"iteration": current_iteration}
                
                # Extract original error information
                if isinstance(phase_error, SexpEvaluationError):
                    original_message = phase_error.args[0] if phase_error.args else str(phase_error)
                    # Include original details if available
                    if hasattr(phase_error, 'error_details'):
                        if isinstance(phase_error.error_details, dict):
                            # Merge dictionaries, giving precedence to iteration
                            error_details.update(phase_error.error_details)
                        else:
                            error_details["original_error_details"] = str(phase_error.error_details)
                else:
                    original_message = str(phase_error)
                    error_details["original_error"] = original_message
                
                # Create a clear, consistent error message format
                error_msg = f"Error during iterative-loop iteration {current_iteration}: {original_message}"
                
                new_error = SexpEvaluationError(
                    error_msg,
                    original_expr_str,
                    error_details=error_details
                )
                logger.error(f"Re-raising error from iterative-loop: {error_msg}")
                raise new_error from phase_error

            # --- Process Decision (with validation) ---
            if not (isinstance(decision_val, list) and len(decision_val) == 2 and isinstance(decision_val[0], Symbol)):
                raise SexpEvaluationError(
                    f"Controller must return a list of (action_symbol value), got: {decision_val!r}",
                    original_expr_str
                )

            action_symbol: Symbol = decision_val[0]
            action_value: Any = decision_val[1]
            action_str = action_symbol.value()

            if action_str == "stop":
                logger.debug(f"iterative-loop: Stopping at iteration {current_iteration} due to controller 'stop'.")
                loop_result = action_value
                break 
            elif action_str == "continue":
                logger.debug(f"iterative-loop: Continuing to next iteration.")
                current_loop_input = action_value
                current_iteration += 1
            else: 
                raise SexpEvaluationError(
                    f"Controller decision action must be 'continue' or 'stop' symbol, got: '{action_str}'",
                    original_expr_str
                )
        else: # Loop finished because current_iteration > max_iter_val (and not stopped early)
            logger.debug(f"iterative-loop: Finished after reaching max_iterations ({max_iter_val}).")
            # If we never executed anything (max_iter was 0), return empty list
            if last_exec_result_val is None:
                loop_result = []
            else:
                loop_result = last_exec_result_val

        logger.debug(f"SpecialFormProcessor.handle_iterative_loop END -> {loop_result}")
        return loop_result