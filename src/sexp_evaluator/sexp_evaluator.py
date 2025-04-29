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
            # SexpParser might return a single expression or a list of top-level expressions
            parsed_nodes = self.parser.parse_string(sexp_string)
            logging.debug(f"Parsed S-expression AST: {parsed_nodes}")

            # 2. Setup Environment
            env = initial_env if initial_env is not None else SexpEnvironment()
            logging.debug(f"Using environment: {env}")

            # 3. Evaluate the AST
            # SexpParser should return a single AST node (which might be a list)
            # If the parser *could* return a Python list representing multiple top-level S-expressions,
            # the parser interface/implementation needs clarification.
            # Assuming parser returns ONE top-level node as per sexpdata.load standard behavior:
            # Remove the implicit progn check for now, assume single top-level expression.
            # If multiple expressions need to be supported, they should be wrapped in (progn ...)
            # or the parser needs to handle it explicitly.
            # Evaluate the single top-level expression returned by the parser
            result = self._eval(parsed_nodes, env)
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
        except TaskFailureError as e:
            # Catch errors propagated from underlying system calls
            logging.error(f"TaskFailureError during S-expression evaluation: {e.message}")
            raise SexpEvaluationError(f"Task execution failed: {e.message}", 
                                     expression=sexp_string, 
                                     error_details=str(e)) from e
        except Exception as e:
            # Catch any other unexpected errors during evaluation
            logging.exception(f"Unexpected error during S-expression evaluation: {e}")
            raise SexpEvaluationError(f"Unexpected evaluation error: {e}", expression=sexp_string) from e


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

        # 1. Literals (Non-Symbol, Non-List)
        if not isinstance(node, (Symbol, str, list)):
            # Catches int, float, bool, None, etc.
            logging.debug(f"Node is non-symbol/non-list literal: {node}")
            return node

        # 2. Symbol Lookup (if node is a Symbol or string *not* being treated as operator)
        # We defer actual lookup until needed, but handle the type check here if parser distinguishes
        if isinstance(node, Symbol):
             symbol_name = node.value()
             logging.debug(f"Node is Symbol: '{symbol_name}'. Deferring lookup until usage.")
             # Fall through to list processing if it's the operator,
             # otherwise lookup happens when used as value/variable.
             # If a Symbol is encountered standalone, lookup should happen in evaluate_string or caller.
             # This path primarily identifies the type.

        # 3. String Literals (If parser returns plain strings for them)
        # This check depends heavily on how SexpParser returns quoted strings vs symbols.
        # If SexpParser returns strings for both symbols and string literals, this needs adjustment.
        # Assuming SexpParser returns Symbol objects for symbols and strings for literals:
        if isinstance(node, str):
            logging.debug(f"Node is string literal: {node}")
            return node # String literals evaluate to themselves

        # 4. Lists (Function Calls / Special Forms / Literal Data)
        if isinstance(node, list):
            if not node:
                logging.debug("Node is empty list, returning empty list.")
                return [] # Empty list evaluates to itself

            operator_node = node[0]
            args = node[1:]

            # --- 3a. Special Forms ---
            # Special forms handle their argument evaluation specially.

            # (if cond then_expr else_expr)
            if operator_node == Symbol("if") or operator_node == "if":
                if len(args) != 3:
                    raise SexpEvaluationError(f"'if' requires 3 arguments (condition, then, else), got {len(args)}", expression=str(node))
                cond_expr, then_expr, else_expr = args
                logging.debug("Evaluating 'if' special form.")
                condition_result = self._eval(cond_expr, env)
                logging.debug(f"'if' condition evaluated to: {condition_result}")
                if condition_result: # Truthy check
                    return self._eval(then_expr, env)
                else:
                    return self._eval(else_expr, env)

            # (let ((var1 val1) (var2 val2) ...) body...)
            # (bind var val) - Simpler single binding variant
            if operator_node == Symbol("let") or operator_node == "let":
                 if len(args) < 1 or not isinstance(args[0], list):
                      raise SexpEvaluationError("'let' requires a binding list and at least one body expression.", expression=str(node))
                 bindings_list = args[0]
                 body_exprs = args[1:]
                 if not body_exprs:
                      raise SexpEvaluationError("'let' requires at least one body expression.", expression=str(node))

                 logging.debug(f"Evaluating 'let' special form with {len(bindings_list)} bindings.")
                 # Evaluate binding values *in the current environment*
                 new_bindings = {}
                 for binding in bindings_list:
                      if not isinstance(binding, list) or len(binding) != 2 or not isinstance(binding[0], (Symbol, str)):
                           raise SexpEvaluationError("Invalid 'let' binding format. Expected (symbol expression).", expression=str(binding))
                      var_name = str(binding[0])
                      val_expr = binding[1]
                      new_bindings[var_name] = self._eval(val_expr, env) # Eval value in *outer* env

                 # Create extended environment
                 let_env = env.extend(new_bindings)
                 logging.debug(f"'let' created extended env {id(let_env)} with bindings: {list(new_bindings.keys())}")

                 # Evaluate body expressions sequentially in the new environment
                 result = None
                 for expr in body_exprs:
                      result = self._eval(expr, let_env)
                 return result # Return result of last body expression

            if operator_node == Symbol("bind") or operator_node == "bind":
                 if len(args) != 2 or not isinstance(args[0], (Symbol, str)):
                      raise SexpEvaluationError("'bind' requires a symbol and a value expression.", expression=str(node))
                 var_name = str(args[0])
                 val_expr = args[1]
                 logging.debug(f"Evaluating 'bind' special form for '{var_name}'.")
                 value = self._eval(val_expr, env)
                 env.define(var_name, value) # Define in *current* env
                 logging.debug(f"'bind' defined '{var_name}' in env {id(env)}")
                 return value # Bind typically returns the bound value

            # --- 3b. Primitive Functions ---
            # Primitives evaluate their arguments first.

            # (list item1 item2 ...)
            if operator_node == Symbol("list") or operator_node == "list":
                logging.debug("Evaluating 'list' primitive.")
                evaluated_items = [self._eval(arg, env) for arg in args]
                return evaluated_items

            # (get_context (option1 val1) (option2 val2) ...)
            if operator_node == Symbol("get_context") or operator_node == "get_context":
                 logging.debug("Evaluating 'get_context' primitive.")
                 context_input_args: Dict[str, Any] = {}
                 for option_pair in args:
                      if not isinstance(option_pair, list) or len(option_pair) != 2 or not isinstance(option_pair[0], (Symbol, str)):
                           raise SexpEvaluationError("Invalid 'get_context' option format. Expected (option_name value_expression).", expression=str(option_pair))
                      option_name = str(option_pair[0])
                      value_expr = option_pair[1]
                      evaluated_value = self._eval(value_expr, env)
                      # Map Sexp option names to ContextGenerationInput fields
                      # (Ensure field names match Pydantic model)
                      if option_name == "query":
                           context_input_args["query"] = evaluated_value
                      elif option_name == "templateDescription":
                           context_input_args["templateDescription"] = evaluated_value
                      elif option_name == "templateType":
                           context_input_args["templateType"] = evaluated_value
                      elif option_name == "templateSubtype":
                           context_input_args["templateSubtype"] = evaluated_value
                      elif option_name == "inputs":
                           context_input_args["inputs"] = evaluated_value # Should be dict
                      elif option_name == "inheritedContext":
                           context_input_args["inheritedContext"] = evaluated_value
                      elif option_name == "previousOutputs":
                           context_input_args["previousOutputs"] = evaluated_value
                      else:
                           logging.warning(f"Unknown 'get_context' option: {option_name}")
                           # Store it anyway? Or raise error? Let's store for flexibility.
                           context_input_args[option_name] = evaluated_value

                 # Validate required fields? ContextGenerationInput allows many optionals.
                 if not context_input_args:
                      raise SexpEvaluationError("'get_context' requires at least one option (e.g., query, templateDescription).", expression=str(node))

                 try:
                      context_input = ContextGenerationInput(**context_input_args)
                 except Exception as e: # Catch Pydantic validation errors etc.
                      raise SexpEvaluationError(f"Failed to create ContextGenerationInput for 'get_context': {e}", expression=str(node)) from e

                 logging.debug(f"Calling memory_system.get_relevant_context_for with: {context_input}")
                 # Call MemorySystem (can raise TaskError)
                 match_result: AssociativeMatchResult = self.memory_system.get_relevant_context_for(context_input)

                 if match_result.error:
                      # Handle error reported by memory system within the result object
                      logging.error(f"Memory system reported error during get_context: {match_result.error}")
                      # Convert this to a TaskFailureError? Or let caller handle?
                      # Let's raise for now to signal failure clearly.
                      failure_details = TaskFailureError(type="TASK_FAILURE", reason="context_retrieval_failure", message=f"Context retrieval failed: {match_result.error}")
                      raise SexpEvaluationError(f"Context retrieval failed", expression=str(node), error_details=str(failure_details.model_dump())) from None # Don't chain original TaskError model

                 # Return the list of file paths as per IDL
                 file_paths = [match.path for match in match_result.matches]
                 logging.debug(f"'get_context' successful, returning paths: {file_paths}")
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


            # --- 3c. General Invocation (Task or Tool Call) ---
            # (<identifier> (arg_name1 val_expr1) (arg_name2 val_expr2) ... )
            # Positional arguments are discouraged/disallowed for task/tool calls.
            logging.debug(f"Attempting general invocation for operator: {operator_node}")
            target_id_obj = self._eval(operator_node, env)
            if not isinstance(target_id_obj, str):
                # If the operator doesn't evaluate to a string name, it's likely data or error
                # Check if the original operator_node was a list itself (invalid call)
                if isinstance(operator_node, list):
                    raise SexpEvaluationError(f"Cannot use a list as an operator: {operator_node}", expression=str(node))
                # Otherwise, maybe treat the whole list as literal data?
                # Let's assume for now that if the operator isn't a string, it's an error.
                raise SexpEvaluationError(f"Operator must evaluate to a string (task/tool name), got {type(target_id_obj)}", expression=str(operator_node))
            target_id = target_id_obj

            logging.debug(f"Invocation target ID: '{target_id}'")
            
            # --- Check if target_id is a known callable BEFORE processing args ---
            is_tool = target_id in self.handler.tool_executors
            is_atomic_task = False
            if not is_tool:
                template_def = self.task_system.find_template(target_id)
                if template_def and template_def.get("type") == "atomic":
                    is_atomic_task = True
            
            # --- If NOT a known callable, treat as literal data list ---
            if not is_tool and not is_atomic_task:
                logging.debug(f"'{target_id}' is not a known tool or atomic task. Treating list as literal data.")
                # Evaluate elements and return the list
                return [self._eval(item, env) for item in node]

            # Evaluate named arguments
            resolved_named_args: Dict[str, Any] = {}
            resolved_files: Optional[List[str]] = None
            resolved_context_settings: Optional[Dict[str, Any]] = None # For ContextManagement

            for arg_pair in args:
                 if not isinstance(arg_pair, list) or len(arg_pair) != 2 or not isinstance(arg_pair[0], (Symbol, str)):
                      # Disallow positional arguments for task/tool calls for clarity
                      raise SexpEvaluationError(f"Invalid argument format for task/tool '{target_id}'. Expected named arguments like (arg_name value_expression). Got: {arg_pair}", expression=str(node))

                 key_node = arg_pair[0]
                 value_expr = arg_pair[1]
                 arg_name = str(key_node) # Get the string name of the argument symbol

                 logging.debug(f"Evaluating argument '{arg_name}'...")
                 evaluated_value = self._eval(value_expr, env)
                 logging.debug(f"Argument '{arg_name}' evaluated to: {type(evaluated_value)}")

                 # Handle special argument names for TaskSystem call
                 if arg_name == "files":
                      if not isinstance(evaluated_value, list) or not all(isinstance(item, str) for item in evaluated_value):
                           raise SexpEvaluationError(f"Special argument 'files' for task '{target_id}' must evaluate to a list of strings.", expression=str(value_expr))
                      resolved_files = evaluated_value
                      logging.debug(f"Resolved 'files' argument: {resolved_files}")
                 elif arg_name == "context":
                      if not isinstance(evaluated_value, dict):
                           raise SexpEvaluationError(f"Special argument 'context' for task '{target_id}' must evaluate to a dictionary (ContextManagement settings).", expression=str(value_expr))
                      resolved_context_settings = evaluated_value
                      logging.debug(f"Resolved 'context' argument: {resolved_context_settings}")
                 else:
                      # Regular named argument
                      resolved_named_args[arg_name] = evaluated_value

            logging.debug(f"Resolved named args for '{target_id}': {list(resolved_named_args.keys())}")
            logging.debug(f"Resolved files for '{target_id}': {resolved_files}")
            logging.debug(f"Resolved context settings for '{target_id}': {resolved_context_settings}")

            # --- Look up and Execute Target ---
            # Priority: Direct Tool > Atomic Task

            # 1. Check Handler Tools
            if target_id in self.handler.tool_executors:
                 logging.info(f"Invoking direct tool: '{target_id}'")
                 try:
                      # Call _execute_tool which handles execution and returns TaskResult dict
                      tool_result_dict = self.handler._execute_tool(target_id, resolved_named_args)
                      # Convert dict back to TaskResult object for consistency? Or return dict?
                      # Let's return the object if possible.
                      return TaskResult.model_validate(tool_result_dict)
                 except Exception as e:
                      # Catch errors during tool execution
                      logging.exception(f"Error executing direct tool '{target_id}': {e}")
                      # Wrap in TaskFailureError for consistency
                      raise TaskFailureError(
                           type="TASK_FAILURE",
                           reason="tool_execution_error",
                           message=f"Tool '{target_id}' execution failed: {e}"
                      ) from e

            # 2. Check TaskSystem Atomic Templates
            logging.debug(f"Checking TaskSystem for atomic template: '{target_id}'")
            template_def = self.task_system.find_template(target_id)
            if template_def and template_def.get("type") == "atomic":
                 logging.info(f"Invoking atomic task: '{target_id}'")
                 try:
                      # Construct SubtaskRequest
                      # Need a unique ID for the request - generate one? Or expect from caller?
                      # For now, generate a simple one. Caller might override via env.
                      subtask_id = f"subtask_{target_id}_{id(node)}" # Simple unique ID

                      # Parse context settings if provided
                      context_management_obj: Optional[ContextManagement] = None
                      if resolved_context_settings:
                           try:
                                # Validate/parse the dict into the Pydantic model
                                context_management_obj = ContextManagement.model_validate(resolved_context_settings)
                           except Exception as val_err:
                                raise SexpEvaluationError(f"Invalid 'context' settings for task '{target_id}': {val_err}", expression=str(node)) from val_err

                      request = SubtaskRequest(
                           task_id=subtask_id,
                           type="atomic",
                           name=target_id,
                           inputs=resolved_named_args,
                           file_paths=resolved_files, # Pass resolved files
                           context_management=context_management_obj # Pass parsed context settings
                           # description, template_hints, max_depth could be added if needed/passed
                      )
                      logging.debug(f"Constructed SubtaskRequest: {request}")

                      # Call TaskSystem (can raise TaskError)
                      task_result_dict = self.task_system.execute_atomic_template(request)
                      # Return the TaskResult object
                      return TaskResult.model_validate(task_result_dict)

                 except TaskFailureError as e:
                      logging.error(f"TaskFailureError executing atomic task '{target_id}': {e}")
                      raise # Propagate TaskFailureError
                 except Exception as e:
                      logging.exception(f"Unexpected error executing atomic task '{target_id}': {e}")
                      # Wrap in TaskFailureError
                      raise TaskFailureError(
                           type="TASK_FAILURE",
                           reason="unexpected_error", # Or more specific if possible
                           message=f"Unexpected error executing task '{target_id}': {e}"
                      ) from e

            # 3. Not Found
            logging.error(f"Invocation target '{target_id}' not found as a direct tool or atomic task.")
            raise SexpEvaluationError(f"Unknown function or task: {target_id}", expression=str(node))

        # --- Fallback for unknown node type ---
        raise SexpEvaluationError(f"Cannot evaluate unsupported node type: {type(node)}", expression=str(node))
