"""
S-expression DSL Evaluator implementation.
Parses and executes workflows defined in S-expression syntax.
Handles workflow composition logic (sequences, conditionals, loops, task/tool calls).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

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
    TaskFailureError, TaskFailureReason, AssociativeMatchResult, MatchTuple,
    TaskError as TaskErrorModel  # Import the model with an alias for type hints
)
from src.system.errors import SexpSyntaxError, SexpEvaluationError # Removed NameError import

# Type for Sexp AST nodes (adjust based on SexpParser output)
# Assuming sexpdata-like output: lists, tuples, strings, numbers, bools, None, Symbol objects
from sexpdata import Symbol # Or use str if parser converts symbols
SexpNode = Any # General type hint for AST nodes

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
            # Wrap underlying errors (including TaskFailureError) in SexpEvaluationError
            error_details_str = ""
            if hasattr(e, 'model_dump'):
                 # Use model_dump() instead of model_dump_json() for potentially non-JSON serializable content
                 try:
                     error_details_str = str(e.model_dump(exclude_none=True))
                 except Exception: # Fallback if model_dump fails
                     error_details_str = str(e)
            else:
                 error_details_str = str(e)
            raise SexpEvaluationError(f"Evaluation failed: {e}", expression=sexp_string, error_details=error_details_str) from e


    def _eval(self, node: SexpNode, env: SexpEnvironment) -> Any:
        """
        Internal recursive evaluation method for S-expression AST nodes.
        Handles base cases and dispatches list evaluation.
        """
        logging.debug(f"Eval START: Node={node} (Type={type(node)}) EnvID={id(env)}")

        # 1. Handle Symbols (Lookup)
        if isinstance(node, Symbol):
            symbol_name = node.value()
            logging.debug(f"Eval Symbol: '{symbol_name}'. Performing lookup.")
            try:
                value = env.lookup(symbol_name) # Let NameError propagate if needed
                logging.debug(f"Eval Symbol END: '{symbol_name}' -> {value} (Type={type(value)})")
                return value
            except NameError as e:
                 logging.error(f"Eval Symbol FAILED: Unbound symbol '{symbol_name}'")
                 raise # Re-raise NameError to be caught by evaluate_string

        # 2. Handle Atoms/Literals (Anything not a list/symbol)
        # Includes str, int, float, bool, None, and [] (parsed nil/())
        if not isinstance(node, list):
            logging.debug(f"Eval Literal/Atom: {node}")
            return node

        # 3. Handle Empty List
        if not node:
            logging.debug("Eval Empty List: -> []")
            return []

        # 4. Delegate ALL Non-Empty List Evaluation
        logging.debug(f"Dispatching list evaluation for: {node}")
        # Pass the original node list to the list evaluation handler
        return self._eval_list(node, env)
    def _eval_list(self, node_list: list, env: SexpEnvironment) -> Any:
        """Handles the evaluation of a non-empty list."""
        node_str = str(node_list) # For error reporting
        if not node_list: return [] # Should not happen

        operator_node = node_list[0]
        args = node_list[1:] # Unevaluated args

        # --- Refined Evaluation Flow ---

        # 1. Evaluate the Operator Node first to determine what it is
        logging.debug(f"Evaluating operator node: {operator_node}")
        operator_target_name = None # Keep track of original name if it was a symbol
        try:
            if isinstance(operator_node, Symbol):
                 operator_target_name = operator_node.value()
                 # Try lookup first
                 operator_target = env.lookup(operator_target_name)
                 logging.debug(f"Operator symbol '{operator_target_name}' evaluated via lookup to: {operator_target} (Type: {type(operator_target)})")
            else:
                 # Operator is a complex expression, evaluate it
                 operator_target = self._eval(operator_node, env)
                 logging.debug(f"Operator expression '{operator_node}' evaluated to: {operator_target} (Type: {type(operator_target)})")

        except NameError:
            # Operator was an unbound symbol, treat its name as the target ID
            if isinstance(operator_node, Symbol):
                operator_target = operator_target_name # Use the name string
                logging.debug(f"Operator symbol '{operator_target_name}' is unbound, treating name as target.")
            else:
                raise SexpEvaluationError(f"Failed to evaluate operator expression: {operator_node}", node_str)
        except Exception as e:
             raise SexpEvaluationError(f"Unexpected error evaluating operator: {operator_node}", node_str) from e

        # 2. Check if the operator name (if it was a symbol) is a Special Form
        special_forms = {"if", "let", "bind", "progn"}
        if operator_target_name in special_forms:
            logging.debug(f"Identified Special Form: {operator_target_name}")
            # Special forms operate on *unevaluated* args
            return self._eval_special_form(operator_target_name, args, env)

        # 3. Check if the operator name (if it was a symbol) is a Primitive
        primitives = {"list", "get_context"}
        if operator_target_name in primitives:
            logging.debug(f"Identified Primitive: {operator_target_name}")
            # Primitives operate on *evaluated* args
            try:
                evaluated_args = [self._eval(arg, env) for arg in args]
                logging.debug(f"Evaluated args for primitive '{operator_target_name}': {evaluated_args}")
            except Exception as e:
                logging.error(f"Error evaluating arguments for primitive {operator_target_name}: {e}", exc_info=True)
                raise SexpEvaluationError(f"Error evaluating arguments for primitive {operator_target_name}", node_str) from e
            return self._eval_primitive(operator_target_name, evaluated_args, env)

        # 4. Handle General Invocation (Task, Tool, Callable)
        logging.debug(f"Handling as General Invocation (Target: {operator_target})")
        # General invocations use specific argument syntax: `(key value_expr)`
        # We parse these *unevaluated* args here.
        parsed_args: Dict[str, Any] = {"named": {}, "files": None, "context": None}
        try:
            for arg_pair in args: # Iterate through unevaluated argument pairs
                if not (isinstance(arg_pair, list) and len(arg_pair) == 2 and isinstance(arg_pair[0], Symbol)):
                    raise SexpEvaluationError("Invalid argument format for invocation. Expected (key value_expr)", str(arg_pair))
                key_node, value_expr = arg_pair
                key_str = key_node.value()
                logging.debug(f"  Evaluating value for key '{key_str}'...")
                value = self._eval(value_expr, env) # Evaluate the value expression
                logging.debug(f"  Evaluated value for '{key_str}': {value}")

                if key_str == "files":
                    if not (isinstance(value, list) and all(isinstance(i, str) for i in value)):
                        raise SexpEvaluationError("'files' arg must evaluate to a list of strings", node_str)
                    parsed_args["files"] = value
                elif key_str == "context":
                    # Context value should already be evaluated dict or list of pairs
                    if isinstance(value, list) and all(isinstance(p, list) and len(p)==2 for p in value):
                         # Convert list of evaluated pairs to dict
                         try: value = {str(k):v for k,v in value}
                         except (ValueError, TypeError): raise SexpEvaluationError("Failed converting 'context' list of pairs", node_str)
                    elif not isinstance(value, dict):
                         raise SexpEvaluationError("'context' arg must evaluate to a dict or list of pairs", node_str)
                    parsed_args["context"] = value
                else:
                    parsed_args["named"][key_str] = value
            logging.debug(f"Parsed invocation args: {parsed_args}")
        except Exception as e:
             logging.error(f"Error parsing arguments for invocation {operator_node}: {e}", exc_info=True)
             # Ensure we wrap the error correctly
             if isinstance(e, SexpEvaluationError):
                 raise # Re-raise if already the correct type
             else:
                 raise SexpEvaluationError(f"Error parsing arguments for invocation {operator_node}", node_str) from e

        # Pass the evaluated operator target and the fully *parsed* arguments dictionary
        return self._handle_invocation(operator_target, parsed_args, env, node_str)

    def _eval_special_form(self, op_str: str, args: list, env: SexpEnvironment) -> Any:
        """Evaluates special forms like if, let, bind, progn."""
        logging.debug(f"Eval Special Form START: {op_str}")
        node_repr = f"({op_str} {' '.join(map(str, args))})" # For error messages

        if op_str == "if":
            if len(args) != 3: raise SexpEvaluationError("'if' requires 3 args: (if cond then else)", node_repr)
            cond_expr, then_expr, else_expr = args
            condition_result = self._eval(cond_expr, env) # Eval condition
            logging.debug(f"  'if' condition evaluated to: {condition_result}")
            result_expr = then_expr if condition_result else else_expr
            result = self._eval(result_expr, env) # Eval chosen branch
            logging.debug(f"Eval 'if' END: -> {result}")
            return result

        elif op_str == "let":
            if len(args) < 1 or not isinstance(args[0], list): raise SexpEvaluationError("'let' requires bindings list and body: (let ((var expr)...) body...)", node_repr)
            bindings_list, body_exprs = args[0], args[1:]
            if not body_exprs: raise SexpEvaluationError("'let' requires at least one body expression", node_repr)
            logging.debug(f"  'let' processing {len(bindings_list)} bindings.")
            let_env = env.extend({}) # Create child env immediately
            for binding in bindings_list:
                if not (isinstance(binding, list) and len(binding) == 2 and isinstance(binding[0], Symbol)):
                    raise SexpEvaluationError("Invalid 'let' binding format: expected (symbol expression)", str(binding))
                var_name = binding[0].value()
                # Evaluate value expression in the *outer* environment
                val = self._eval(binding[1], env)
                let_env.define(var_name, val) # Define in the *new* child environment
                logging.debug(f"    Defined '{var_name}' in let scope {id(let_env)}")
            result = [] # Default for empty body (though disallowed by check above)
            for expr in body_exprs: result = self._eval(expr, let_env) # Evaluate body in child env
            logging.debug(f"Eval 'let' END: -> {result}")
            return result

        elif op_str == "bind":
             if len(args) != 2 or not isinstance(args[0], Symbol): raise SexpEvaluationError("'bind' requires symbol and value expr: (bind var expr)", node_repr)
             var_name = args[0].value()
             logging.debug(f"  Eval 'bind' for '{var_name}'")
             value = self._eval(args[1], env) # Eval value expr
             env.define(var_name, value) # Define in *current* env
             logging.debug(f"  Eval 'bind' END: defined '{var_name}' -> {value} in env {id(env)}")
             return value # bind returns the assigned value

        elif op_str == "progn":
            logging.debug("  Eval 'progn'")
            result = [] # Default result for empty progn is nil/[]
            for expr in args:
                result = self._eval(expr, env) # Eval each expression sequentially
            logging.debug(f"Eval 'progn' END: -> {result}")
            return result # Return result of last expression

        else:
             # Should not be reached if called from _eval_list correctly
             raise SexpEvaluationError(f"Internal error: Unknown special form '{op_str}'", node_repr)

    def _eval_primitive(self, op_str: str, evaluated_args: list, env: SexpEnvironment) -> Any:
        """Evaluates built-in primitives like list, get_context."""
        logging.debug(f"Eval Primitive START: {op_str}")
        node_repr = f"({op_str} ...)" # Approximate representation for errors

        if op_str == "list":
            logging.debug(f"Eval 'list' END: -> {evaluated_args}")
            return evaluated_args # Primitive just returns the evaluated args

        elif op_str == "get_context":
            context_input_args: Dict[str, Any] = {}
            # Arguments are already evaluated. Expect list of ['key', value] pairs
            # from the arguments being evaluated `(list 'key' value_expr)` forms.
            for arg in evaluated_args:
                 if isinstance(arg, list) and len(arg) == 2 and isinstance(arg[0], str):
                     key = arg[0]
                     value = arg[1]
                     context_input_args[key] = value
                 else:
                     raise SexpEvaluationError(f"Invalid argument type for 'get_context': {type(arg)}. Expected evaluated ['key', value] pair.", node_repr)

            if not context_input_args: raise SexpEvaluationError("'get_context' requires options", node_repr)

            logging.debug(f"  get_context received evaluated args: {context_input_args}")

            # Map to ContextGenerationInput fields (keys should be strings now)
            # No mapping needed if keys match ContextGenerationInput fields
            try:
                # Convert inputs if needed (e.g., from list of pairs if passed that way)
                if "inputs" in context_input_args and isinstance(context_input_args["inputs"], list):
                    try: context_input_args["inputs"] = {str(k):v for k,v in context_input_args["inputs"]}
                    except (ValueError, TypeError): raise SexpEvaluationError("Failed converting 'inputs' list of pairs to dict", node_repr)

                context_input = ContextGenerationInput(**context_input_args)
            except Exception as e:
                raise SexpEvaluationError(f"Failed creating ContextGenerationInput from args {context_input_args}: {e}", node_repr) from e

            logging.debug(f"Calling memory_system.get_relevant_context_for with: {context_input}")
            try:
                match_result: AssociativeMatchResult = self.memory_system.get_relevant_context_for(context_input)
            except Exception as e:
                 logging.exception(f"MemorySystem.get_relevant_context_for failed: {e}")
                 # Wrap underlying error
                 raise SexpEvaluationError("Context retrieval failed internally", node_repr, error_details=str(e)) from e

            if match_result.error:
                 # Raise error if MemorySystem indicated failure
                 raise SexpEvaluationError("Context retrieval failed", node_repr, error_details=match_result.error)

            file_paths = [m.path for m in match_result.matches if isinstance(m, MatchTuple)]
            logging.debug(f"Eval 'get_context' END: -> {file_paths}")
            return file_paths
        else:
             # Should not be reached
             raise SexpEvaluationError(f"Internal error: Unknown primitive '{op_str}'", node_repr)

    def _handle_invocation(self, operator_target: Any, parsed_args: Dict[str, Any], env: SexpEnvironment, node_str: str) -> Any:
        """Handles the invocation of tasks, tools, or other callables using pre-parsed arguments."""
        logging.debug(f"Handle Invocation START: Target={operator_target}, ParsedArgs={parsed_args}")

        # Determine target ID if operator was originally a symbol name
        target_id = operator_target if isinstance(operator_target, str) else None

        try:
            if target_id: # Target is identified by name (tool or task)
                # Pass the parsed_args dict directly to the helper
                result = self._invoke_target_by_name(target_id, parsed_args, node_str)
            elif callable(operator_target):
                # Target is an evaluated callable (e.g., from environment)
                logging.info(f"Invoking evaluated callable: {operator_target}")
                try:
                    # Pass named args only from the parsed dict
                    result = operator_target(**parsed_args["named"])
                    # Note: Callables might return non-TaskResult types.
                except Exception as e:
                    raise SexpEvaluationError(f"Error invoking callable {operator_target}: {e}", node_str) from e
            else:
                # Operator evaluated to something non-callable and wasn't a symbol name
                raise SexpEvaluationError(f"Cannot apply non-callable operator: {operator_target} (type: {type(operator_target)})", node_str)

            logging.debug(f"Handle Invocation END: Result Type={type(result)}")
            # Ensure the result is a valid TaskResult if it came from a tool/task
            # Callables might return other types, which is allowed.
            if target_id: # Only validate if it was a named tool/task call
                 if isinstance(result, dict): # Allow dicts that can be validated
                    try: result = TaskResult.model_validate(result)
                    except Exception as e: raise SexpEvaluationError(f"Target '{target_id}' result validation failed: {e}", node_str) from e
                 elif not isinstance(result, TaskResult): # Must be TaskResult object otherwise
                     raise SexpEvaluationError(f"Target '{target_id}' returned unexpected type {type(result)}", node_str)

            return result

        except SexpEvaluationError: # Propagate evaluation errors cleanly
             raise
        except Exception as e:
            # Catch errors during execution (e.g., from _invoke_target_by_name)
            logging.exception(f"Error during invocation handling for target '{operator_target}': {e}")
            # Wrap underlying error
            raise SexpEvaluationError(f"Invocation of '{operator_target}' failed: {e}", node_str, error_details=str(e)) from e

    def _invoke_target_by_name(self, target_id: str, parsed_args: Dict[str, Any], node_str: str) -> TaskResult:
        """Invokes the target (tool or task) by name and ensures TaskResult return."""
        logging.debug(f"Invoking target by name: ID='{target_id}', ParsedArgs={parsed_args}")
        # Extract args from the pre-parsed dictionary
        named_args = parsed_args["named"]
        files = parsed_args["files"]
        context_settings = parsed_args["context"]

        # 1. Check Handler Tools
        if target_id in self.handler.tool_executors:
            logging.info(f"Invoking direct tool: '{target_id}'")
            # Note: Tools might not expect files/context directly. Adapt if needed.
            if files is not None or context_settings is not None:
                 logging.warning(f"Tool '{target_id}' invoked with 'files' or 'context' args, which might not be supported by the tool executor.")
            # _execute_tool should return a TaskResult object or raise
            tool_result_obj = self.handler._execute_tool(target_id, named_args)
            logging.debug(f"  Tool '{target_id}' returned: {tool_result_obj}")
            # Ensure it's a TaskResult object before returning
            if not isinstance(tool_result_obj, TaskResult):
                 # This indicates an issue in _execute_tool's contract fulfillment
                 logging.error(f"Tool executor '{target_id}' did not return a TaskResult object (got {type(tool_result_obj)}).")
                 raise SexpEvaluationError(f"Tool '{target_id}' execution returned invalid type.", node_str)
            return tool_result_obj

        # 2. Check Task System Atomic Templates
        template_def = self.task_system.find_template(target_id)
        if template_def and template_def.get("type") == "atomic":
            logging.info(f"Invoking atomic task: '{target_id}'")
            context_mgmt_obj: Optional[ContextManagement] = None
            if context_settings:
                try: context_mgmt_obj = ContextManagement.model_validate(context_settings)
                except Exception as e: raise SexpEvaluationError(f"Invalid 'context' settings for task '{target_id}': {e}", node_str) from e

            request = SubtaskRequest(
                task_id=f"sexp_task_{target_id}_{id(node_str)}", # Use node_str hash/id?
                type="atomic",
                name=target_id,
                inputs=named_args,
                file_paths=files,
                context_management=context_mgmt_obj
            )
            # execute_atomic_template should return a TaskResult object or raise
            task_result_obj = self.task_system.execute_atomic_template(request)
            logging.debug(f"  Task '{target_id}' returned: {task_result_obj}")
            # Ensure it's a TaskResult object before returning
            if not isinstance(task_result_obj, TaskResult):
                 # This indicates an issue in execute_atomic_template's contract fulfillment
                 logging.error(f"Task executor for '{target_id}' did not return a TaskResult object (got {type(task_result_obj)}).")
                 raise SexpEvaluationError(f"Task '{target_id}' execution returned invalid type.", node_str)
            return task_result_obj

        # 3. Not Found
        raise SexpEvaluationError(f"Cannot invoke '{target_id}': Not a recognized tool or atomic task.", node_str)
