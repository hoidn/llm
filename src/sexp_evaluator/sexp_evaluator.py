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
from src.system.errors import SexpSyntaxError, SexpEvaluationError

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
             logging.error(f"S-expression evaluation error: Unbound symbol - {e}")
             raise SexpEvaluationError(f"Unbound symbol: {e}", expression=sexp_string) from e
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

        Args:
            node: The S-expression AST node to evaluate (list, symbol, literal).
            env: The current SexpEnvironment for evaluation.

        Returns:
            The evaluated value of the node.

        Raises:
            SexpEvaluationError: For runtime errors during evaluation.
            NameError: For unbound symbols (caught by evaluate_string).
            TaskError: Propagated from underlying calls.
        """
        logging.debug(f"Evaluating node: {node} (type: {type(node)}) in env {id(env)}")

        # --- Handle Node Types ---

        # Fix: Handle Standalone Symbol Lookup FIRST
        if isinstance(node, Symbol):
            symbol_name = node.value()
            logging.debug(f"Node is Symbol: '{symbol_name}'. Performing lookup.")
            return env.lookup(symbol_name) # Raises NameError if unbound

        # Fix: Handle Literals (anything not a list)
        if not isinstance(node, list):
            logging.debug(f"Node is literal: {node}")
            return node

        # Handle Lists
        if isinstance(node, list):
            if not node:
                logging.debug("Node is empty list, returning empty list.")
                return []

            operator_node = node[0]
            args = node[1:]
            op_str = str(operator_node) # Use string representation for checks

            # --- Special Forms (Check FIRST) ---

            if op_str == "if":
                # ... (if implementation - ensure condition check is correct) ...
                if len(args) != 3: raise SexpEvaluationError("'if' requires 3 args", str(node))
                cond_expr, then_expr, else_expr = args
                condition_result = self._eval(cond_expr, env)
                return self._eval(then_expr, env) if condition_result else self._eval(else_expr, env)

            if op_str == "let":
                # ... (let implementation - relies on correct recursive _eval) ...
                if len(args) < 1 or not isinstance(args[0], list): raise SexpEvaluationError("'let' requires bindings list and body", str(node))
                bindings_list, body_exprs = args[0], args[1:]
                if not body_exprs: raise SexpEvaluationError("'let' requires body", str(node))
                new_bindings = {}
                for binding in bindings_list:
                    if not (isinstance(binding, list) and len(binding) == 2 and isinstance(binding[0], (Symbol, str))):
                        raise SexpEvaluationError("Invalid 'let' binding format", str(binding))
                    var_name, val_expr = str(binding[0]), binding[1]
                    new_bindings[var_name] = self._eval(val_expr, env) # Eval value in outer env
                let_env = env.extend(new_bindings)
                result = None
                for expr in body_exprs: result = self._eval(expr, let_env)
                return result

            if op_str == "bind":
                 # ... (bind implementation) ...
                 if len(args) != 2 or not isinstance(args[0], (Symbol, str)): raise SexpEvaluationError("'bind' requires symbol and value expr", str(node))
                 var_name, val_expr = str(args[0]), args[1]
                 value = self._eval(val_expr, env)
                 env.define(var_name, value)
                 return value

            if op_str == "progn": # Handle progn if implemented/needed
                logging.debug("Evaluating 'progn' special form.")
                result = None
                for expr in args:
                    result = self._eval(expr, env)
                return result

            # --- Primitives (Check SECOND) ---

            if op_str == "list":
                logging.debug("Evaluating 'list' primitive.")
                evaluated_items = [self._eval(arg, env) for arg in args]
                return evaluated_items

            if op_str == "get_context":
                 # ... (get_context implementation - ensure values are _eval'd) ...
                 logging.debug("Evaluating 'get_context' primitive.")
                 context_input_args: Dict[str, Any] = {}
                 for option_pair in args:
                      if not (isinstance(option_pair, list) and len(option_pair) == 2 and isinstance(option_pair[0], (Symbol, str))):
                           raise SexpEvaluationError("Invalid 'get_context' option format", str(option_pair))
                      option_name, value_expr = str(option_pair[0]), option_pair[1]
                      evaluated_value = self._eval(value_expr, env) # Evaluate the value expression
                      # ... (mapping logic remains the same) ...
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
                 return file_paths

            # (map task_expr list_expr) - Simplified map
            # TODO: Implement 'map' primitive if needed. Requires careful handling of
            #       evaluation scope for each item. Example:
            # if operator_node == Symbol("map") or operator_node == "map":
            #     if len(args) != 2:
            #         raise SexpEvaluationError("'map' requires a task/function expression and a list expression.", expression=str(node))
            #     task_expr = args[0]
            #     list_expr = args[1]
            #     evaluated_list = self._eval(list_expr, env)
            #     if not isinstance(evaluated_list, list):
            #         raise SexpEvaluationError("'map' requires the second argument to evaluate to a list.", expression=str(list_expr))
            #
            #     results = []
            #     # Need a way to bind the current item, e.g., using a convention like 'item' variable
            #     item_var_name = "item" # Or make this configurable?
            #     for item in evaluated_list:
            #         map_env = env.extend({item_var_name: item})
            #         # Evaluate the task_expr which should reference item_var_name
            #         item_result = self._eval(task_expr, map_env)
            #         results.append(item_result)
            #     return results


            # --- General Invocation OR Data List (Check THIRD) ---
            # Evaluate the operator node to see if it's a callable name (string)
            logging.debug(f"Evaluating potential operator node: {operator_node}")
            evaluated_operator = self._eval(operator_node, env)

            # If operator doesn't evaluate to a string, treat the whole list as data
            if not isinstance(evaluated_operator, str):
                logging.debug(f"Operator evaluated to non-string ({type(evaluated_operator)}). Treating list as literal data.")
                evaluated_args = [self._eval(arg, env) for arg in args]
                return [evaluated_operator] + evaluated_args # Prepend evaluated operator

            # We have a string operator - check if it's a known callable
            target_id = evaluated_operator
            logging.debug(f"Invocation target ID resolved to string: '{target_id}'")
            is_tool = target_id in self.handler.tool_executors
            is_atomic_task = False
            template_def = None
            if not is_tool:
                template_def = self.task_system.find_template(target_id)
                if template_def and template_def.get("type") == "atomic":
                    is_atomic_task = True

            # If NOT a known callable, treat original list as data
            if not is_tool and not is_atomic_task:
                logging.debug(f"'{target_id}' is not a known tool/task. Treating list as literal data.")
                evaluated_args = [self._eval(arg, env) for arg in args]
                # Return the original operator unevaluated + evaluated args
                return [operator_node] + evaluated_args # Return list starting with original operator symbol/literal

            # --- It IS a known callable ---
            # Evaluate named arguments
            resolved_named_args: Dict[str, Any] = {}
            resolved_files: Optional[List[str]] = None
            resolved_context_settings: Optional[Dict[str, Any]] = None
            for arg_pair in args:
                 # ... (argument parsing logic - relies on correct recursive _eval for values) ...
                 if not (isinstance(arg_pair, list) and len(arg_pair) == 2 and isinstance(arg_pair[0], (Symbol, str))):
                      raise SexpEvaluationError(f"Invalid arg format for '{target_id}'. Expected (name value). Got: {arg_pair}", str(node))
                 arg_name, value_expr = str(arg_pair[0]), arg_pair[1]
                 evaluated_value = self._eval(value_expr, env) # Evaluate value
                 if arg_name == "files":
                      if not (isinstance(evaluated_value, list) and all(isinstance(i, str) for i in evaluated_value)): raise SexpEvaluationError(f"'files' arg must be list of strings", str(value_expr))
                      resolved_files = evaluated_value
                 elif arg_name == "context":
                      if not isinstance(evaluated_value, dict): raise SexpEvaluationError(f"'context' arg must be dict", str(value_expr))
                      resolved_context_settings = evaluated_value
                 else: resolved_named_args[arg_name] = evaluated_value

            # --- Execute Callable ---
            if is_tool:
                 logging.info(f"Invoking direct tool: '{target_id}'")
                 try:
                      tool_result = self.handler._execute_tool(target_id, resolved_named_args)
                      # ... (result handling) ...
                      if isinstance(tool_result, dict): return TaskResult.model_validate(tool_result)
                      if isinstance(tool_result, TaskResult): return tool_result
                      raise SexpEvaluationError(f"Tool '{target_id}' returned invalid type: {type(tool_result)}")
                 except Exception as e:
                      raise SexpEvaluationError(f"Tool '{target_id}' failed: {e}", str(node), error_details=str(e)) from e

            elif is_atomic_task and template_def:
                 logging.info(f"Invoking atomic task: '{target_id}'")
                 try:
                      context_management_obj: Optional[ContextManagement] = None
                      if resolved_context_settings:
                           try: context_management_obj = ContextManagement.model_validate(resolved_context_settings)
                           except Exception as val_err: raise SexpEvaluationError(f"Invalid 'context' settings: {val_err}", str(node)) from val_err
                      request = SubtaskRequest( task_id=f"sexp_task_{target_id}_{id(node)}", type="atomic", name=target_id, inputs=resolved_named_args, file_paths=resolved_files, context_management=context_management_obj )
                      task_result = self.task_system.execute_atomic_template(request)
                      return task_result
                 except Exception as e:
                      raise SexpEvaluationError(f"Task '{target_id}' failed: {e}", str(node), error_details=str(e)) from e
            else:
                 # This path should not be reached if logic is correct
                 raise SexpEvaluationError(f"Internal error: Cannot execute '{target_id}'", str(node))

        # Fallback for unhandled node type (shouldn't happen)
        raise SexpEvaluationError(f"Cannot evaluate unsupported node type: {type(node)}", expression=str(node))
