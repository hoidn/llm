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
            if not e.expression:
                 e.expression = sexp_string
            raise # Re-raise evaluation error
        except Exception as e:
            # Catch any other unexpected errors during evaluation
            logging.exception(f"Unexpected error during S-expression evaluation: {e}")
            # Wrap underlying errors (including TaskFailureError) in SexpEvaluationError
            error_details_str = ""
            if hasattr(e, 'model_dump'):
                 error_details_str = str(e.model_dump(exclude_none=True))
            else:
                 error_details_str = str(e)
            raise SexpEvaluationError(f"Evaluation failed: {e}", expression=sexp_string, error_details=error_details_str) from e


    def _eval(self, node: SexpNode, env: SexpEnvironment) -> Any:
        """
        Internal recursive evaluation method for S-expression AST nodes.
        Corrected Logic (Round 2): Handles atoms, special forms, primitives, callables, and data lists accurately.
        """
        logging.debug(f"Eval START: Node={node} (Type={type(node)}) EnvID={id(env)}")

        # 1. Handle Standalone Symbols (Lookup in environment)
        if isinstance(node, Symbol):
            symbol_name = node.value()
            logging.debug(f"Eval Symbol: '{symbol_name}'. Performing lookup.")
            # Let NameError propagate up to evaluate_string if lookup fails
            value = env.lookup(symbol_name)
            logging.debug(f"Eval Symbol END: '{symbol_name}' -> {value} (Type={type(value)})")
            return value

        # 2. Handle Literals (Anything not a list and not already handled as a Symbol)
        if not isinstance(node, list):
            logging.debug(f"Eval Literal: {node}")
            return node # Includes str, int, float, bool, None

        # 3. Handle Lists
        if isinstance(node, list):
            # Empty list evaluates to itself
            if not node:
                logging.debug("Eval Empty List: -> []")
                return []

            operator_node = node[0]
            args = node[1:]
            op_str = str(operator_node) # Use string representation for initial checks

            # --- Check for Special Forms (operate on unevaluated args) ---
            if op_str == "if":
                # ... (if implementation - unchanged from previous fix) ...
                if len(args) != 3: raise SexpEvaluationError("'if' requires 3 args", str(node))
                cond_expr, then_expr, else_expr = args
                logging.debug("Eval Special Form: 'if'")
                condition_result = self._eval(cond_expr, env)
                result = self._eval(then_expr, env) if condition_result else self._eval(else_expr, env)
                logging.debug(f"Eval 'if' END: -> {result}")
                return result

            if op_str == "let":
                # ... (let implementation - unchanged from previous fix) ...
                if len(args) < 1 or not isinstance(args[0], list): raise SexpEvaluationError("'let' requires bindings list and body", str(node))
                bindings_list, body_exprs = args[0], args[1:]
                if not body_exprs: raise SexpEvaluationError("'let' requires body", str(node))
                logging.debug(f"Eval Special Form: 'let' with {len(bindings_list)} bindings")
                new_bindings = {}
                for binding in bindings_list:
                    if not (isinstance(binding, list) and len(binding) == 2 and isinstance(binding[0], (Symbol, str))):
                        raise SexpEvaluationError("Invalid 'let' binding format", str(binding))
                    var_name, val_expr = str(binding[0]), binding[1]
                    new_bindings[var_name] = self._eval(val_expr, env) # Eval value in outer env
                let_env = env.extend(new_bindings)
                result = None
                for expr in body_exprs: result = self._eval(expr, let_env)
                logging.debug(f"Eval 'let' END: -> {result}")
                return result

            if op_str == "bind":
                 # ... (bind implementation - unchanged) ...
                 if len(args) != 2 or not isinstance(args[0], (Symbol, str)): raise SexpEvaluationError("'bind' requires symbol and value expr", str(node))
                 var_name, val_expr = str(args[0]), args[1]
                 logging.debug(f"Eval Special Form: 'bind' for '{var_name}'")
                 value = self._eval(val_expr, env)
                 env.define(var_name, value)
                 logging.debug(f"Eval 'bind' END: defined '{var_name}' -> {value}")
                 return value

            if op_str == "progn": # Handle progn if implemented/needed
                logging.debug("Eval Special Form: 'progn'")
                result = None
                for expr in args:
                    result = self._eval(expr, env)
                logging.debug(f"Eval 'progn' END: -> {result}")
                return result

            # --- Check for Primitives (evaluate args first) ---
            if op_str == "list":
                logging.debug("Eval Primitive: 'list'")
                evaluated_items = [self._eval(arg, env) for arg in args]
                logging.debug(f"Eval 'list' END: -> {evaluated_items}")
                return evaluated_items

            if op_str == "get_context":
                 logging.debug("Eval Primitive: 'get_context'")
                 context_input_args: Dict[str, Any] = {}
                 for option_pair_expr in args: # Process each option pair expression
                      # Validate the structure: must be [key_symbol, value_expression]
                      if not (isinstance(option_pair_expr, list) and len(option_pair_expr) == 2 and isinstance(option_pair_expr[0], (Symbol, str))):
                           raise SexpEvaluationError("Invalid 'get_context' option format. Expected (key_symbol value_expression) pair.", str(option_pair_expr))

                      option_name_sym, value_expr = option_pair_expr[0], option_pair_expr[1]
                      option_name = str(option_name_sym) # Convert symbol/str to string key

                      # Evaluate *only* the value expression
                      evaluated_value = self._eval(value_expr, env)

                      # Special handling for 'inputs': convert list of pairs to dict if necessary
                      if option_name == "inputs":
                          if isinstance(evaluated_value, list) and all(isinstance(p, list) and len(p) == 2 for p in evaluated_value):
                              try:
                                  # Convert keys to strings during dict creation
                                  evaluated_value = {str(k): v for k, v in evaluated_value}
                              except (TypeError, ValueError) as conv_err:
                                   raise SexpEvaluationError(f"'inputs' arg evaluated to list of pairs, but failed dict conversion: {conv_err}", str(option_pair_expr)) from conv_err
                          elif not isinstance(evaluated_value, dict):
                               raise SexpEvaluationError(f"'inputs' arg must evaluate to a dictionary or a list of pairs. Got: {type(evaluated_value)}", str(option_pair_expr))

                      # Map Sexp option names to ContextGenerationInput fields
                      field_map = { "query": "query", "templateDescription": "templateDescription", "templateType": "templateType", "templateSubtype": "templateSubtype", "inputs": "inputs", "inheritedContext": "inheritedContext", "previousOutputs": "previousOutputs" }
                      if option_name in field_map: context_input_args[field_map[option_name]] = evaluated_value
                      else: context_input_args[option_name] = evaluated_value # Store unknown
                 if not context_input_args: raise SexpEvaluationError("'get_context' requires options", str(node))
                 try: context_input = ContextGenerationInput(**context_input_args)
                 except Exception as e: raise SexpEvaluationError(f"Failed creating ContextGenerationInput: {e}", str(node)) from e
                 logging.debug(f"Calling memory_system.get_relevant_context_for with: {context_input}")
                 match_result: AssociativeMatchResult = self.memory_system.get_relevant_context_for(context_input)
                 if match_result.error:
                      raise SexpEvaluationError("Context retrieval failed", expression=str(node), error_details=match_result.error) from None
                 file_paths = [m.path for m in match_result.matches if isinstance(m, MatchTuple)]
                 logging.debug(f"Eval 'get_context' END: -> {file_paths}")
                 return file_paths


            # --- General Call or Data List ---
            # If the operator is NOT a symbol/string, it cannot be a callable name -> treat as data
            if not isinstance(operator_node, (Symbol, str)):
                logging.debug(f"Operator node type ({type(operator_node)}) not Symbol/String. Treating list as data.")
                evaluated_list = [self._eval(item, env) for item in node]
                logging.debug(f"Eval Data List (non-symbol op) END: -> {evaluated_list}")
                return evaluated_list

            # --- General Call or Data List ---
            # Evaluate the operator node itself to see what it resolves to
            try:
                # Use a temporary variable to avoid modifying operator_node in case it's needed later
                evaluated_op = self._eval(operator_node, env)
                is_op_callable_ref = callable(evaluated_op) # Check if the *evaluated* operator is callable
                logging.debug(f"Operator node '{operator_node}' evaluated to type {type(evaluated_op)}. Callable: {is_op_callable_ref}")
            except NameError:
                 # If the operator symbol is unbound, it cannot be a callable defined in the env
                 is_op_callable_ref = False
                 logging.debug(f"Operator node '{operator_node}' is an unbound symbol.")
                 # Fall through to check if it's a known tool/task name

            # Check if the *original* operator string names a known tool or task
            target_id = str(operator_node) # Use the original string name for lookup
            is_tool = target_id in self.handler.tool_executors
            template_def = self.task_system.find_template(target_id)
            is_atomic_task = bool(template_def and template_def.get("type") == "atomic")
            is_known_callable_name = is_tool or is_atomic_task

            # Decide if it's a function call or a data list
            # It's a function call if the operator *name* refers to a tool/task
            # OR if the operator node *evaluates* to a callable function (less common for this DSL)
            is_function_call = is_known_callable_name or is_op_callable_ref

            if is_function_call:
                logging.debug(f"List interpreted as CALL. Operator='{target_id}'")
                resolved_named_args: Dict[str, Any] = {}
                resolved_files: Optional[List[str]] = None
                resolved_context_settings: Optional[Dict[str, Any]] = None
                for arg_pair_expr in args:
                    # Validate the structure: must be [key_symbol, value_expression]
                    if not (isinstance(arg_pair_expr, list) and len(arg_pair_expr) == 2 and isinstance(arg_pair_expr[0], (Symbol, str))):
                        raise SexpEvaluationError(f"Invalid arg format for callable '{target_id}'. Expected (key_symbol value_expression). Got: {arg_pair_expr}", str(arg_pair_expr))

                    arg_name_sym, value_expr = arg_pair_expr[0], arg_pair_expr[1]
                    arg_name = str(arg_name_sym) # Convert symbol/str to string key

                    # Evaluate *only* the value expression
                    evaluated_value = self._eval(value_expr, env)

                    # Handle special args or regular args based on the key name
                    if arg_name == "files":
                        if not (isinstance(evaluated_value, list) and all(isinstance(i, str) for i in evaluated_value)): raise SexpEvaluationError(f"'files' arg must evaluate to a list of strings. Got: {type(evaluated_value)}", str(arg_pair_expr))
                        resolved_files = evaluated_value
                    elif arg_name == "context":
                        if not isinstance(evaluated_value, dict):
                             # Allow context to be provided as an evaluated list of pairs
                             if isinstance(evaluated_value, list) and all(isinstance(p, list) and len(p) == 2 for p in evaluated_value):
                                 try:
                                     # Convert the list of pairs into a dictionary, ensuring keys are strings
                                     evaluated_value = {str(k): v for k, v in evaluated_value}
                                 except (TypeError, ValueError) as conv_err:
                                     raise SexpEvaluationError(f"'context' arg evaluated to list of pairs, but failed dict conversion: {conv_err}", str(arg_pair_expr)) from conv_err
                             else:
                                 raise SexpEvaluationError(f"'context' arg must evaluate to a dictionary or a list of pairs. Got: {type(evaluated_value)}", str(arg_pair_expr))
                        resolved_context_settings = evaluated_value
                    else:
                        # Store regular named arguments
                        resolved_named_args[arg_name] = evaluated_value

                # Execute Tool or Task
                try:
                    if is_tool:
                        logging.info(f"Invoking direct tool: '{target_id}'")
                        # Handler._execute_tool might return dict or TaskResult based on IDL/impl
                        tool_result_obj = self.handler._execute_tool(target_id, resolved_named_args)

                        # Ensure we have a TaskResult object
                        if isinstance(tool_result_obj, dict):
                             logging.warning("Handler._execute_tool returned dict, attempting TaskResult validation.")
                             try:
                                 tool_result_obj = TaskResult.model_validate(tool_result_obj)
                             except Exception as model_val_err:
                                 raise SexpEvaluationError(f"Failed to validate Handler._execute_tool result as TaskResult: {model_val_err}", str(node), error_details=str(tool_result_obj)) from model_val_err
                        elif not isinstance(tool_result_obj, TaskResult):
                             raise SexpEvaluationError("Handler._execute_tool returned unexpected type", str(node), error_details=f"Type: {type(tool_result_obj)}")

                        logging.debug(f"Eval Tool Call END: '{target_id}' -> {tool_result_obj.status}")
                        return tool_result_obj # Return TaskResult object
                    elif is_atomic_task: # Must be atomic task if not tool
                        logging.info(f"Invoking atomic task: '{target_id}'")
                        context_management_obj: Optional[ContextManagement] = None
                        if resolved_context_settings:
                            try: context_management_obj = ContextManagement.model_validate(resolved_context_settings)
                            except Exception as val_err: raise SexpEvaluationError(f"Invalid 'context' settings: {val_err}", str(node)) from val_err
                        request = SubtaskRequest(
                            task_id=f"sexp_task_{target_id}_{id(node)}", type="atomic", name=target_id,
                            inputs=resolved_named_args, file_paths=resolved_files,
                            context_management=context_management_obj
                        )
                        # TaskSystem returns TaskResult object
                        task_result_obj = self.task_system.execute_atomic_template(request)

                        # Fix 2 START: Ensure we have a TaskResult object
                        if isinstance(task_result_obj, dict):
                             # Attempt conversion if TaskSystem returned dict (e.g., from mock)
                             logging.warning("TaskSystem returned dict, attempting TaskResult validation.")
                             try:
                                 task_result_obj = TaskResult.model_validate(task_result_obj)
                             except Exception as model_val_err:
                                 raise SexpEvaluationError(f"Failed to validate TaskSystem result as TaskResult: {model_val_err}", str(node), error_details=str(task_result_obj)) from model_val_err
                        elif not isinstance(task_result_obj, TaskResult):
                             # Raise error if it's neither dict nor TaskResult
                             raise SexpEvaluationError("TaskSystem returned unexpected type", str(node), error_details=f"Type: {type(task_result_obj)}")
                        # Fix 2 END

                        logging.debug(f"Eval Atomic Task Call END: '{target_id}' -> {task_result_obj.status}")
                        return task_result_obj # Return TaskResult object
                    else:
                         # This case should theoretically not be reached if is_function_call is true
                         raise SexpEvaluationError(f"Internal Error: Operator '{target_id}' determined as callable but neither tool nor atomic task.", str(node))

                except Exception as e:
                    # Catch errors from _execute_tool or execute_atomic_template
                    logging.exception(f"Error during execution of callable '{target_id}': {e}")
                    # Wrap underlying error
                    raise SexpEvaluationError(f"Execution of '{target_id}' failed: {e}", str(node), error_details=str(e)) from e

            else: # List is not a function call -> Treat as Data List
                 logging.debug(f"List interpreted as DATA. Operator='{operator_node}'")
                 # Evaluate ALL elements recursively, including the operator node itself
                 evaluated_list = [self._eval(item, env) for item in node]
                 logging.debug(f"Eval Data List END: -> {evaluated_list}")
                 return evaluated_list

        # Fallback for unhandled node type (should not happen with current checks)
        raise SexpEvaluationError(f"Cannot evaluate unsupported node type: {type(node)}", expression=str(node))
