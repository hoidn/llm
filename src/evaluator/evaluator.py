"""Evaluator component implementation.

This module contains the Evaluator class, which is responsible for
evaluating AST nodes, particularly function calls.
"""
import logging
import re
import json # Added for target_files parsing
from typing import Any, Dict, List, Optional, Union, Tuple, TypeVar, cast

# Adjust import paths if needed based on your project structure
from task_system.ast_nodes import ArgumentNode, FunctionCallNode
from task_system.template_utils import Environment, resolve_parameters
from system.errors import (
    TaskError,
    create_input_validation_error,
    create_unexpected_error,
    create_task_failure,
    format_error_result,
    INPUT_VALIDATION_FAILURE,
    SUBTASK_FAILURE,
    UNEXPECTED_ERROR
)
from evaluator.interfaces import EvaluatorInterface, TemplateLookupInterface

# Type variable for the template lookup interface
T = TypeVar('T', bound=TemplateLookupInterface)

# Constants
DEFAULT_MAX_ITERATIONS = 5

# Define TaskResult type hint if not already globally available
TaskResult = Dict[str, Any]

logger = logging.getLogger(__name__) # Added logger


class Evaluator(EvaluatorInterface):
    """
    Evaluates AST nodes, particularly function calls.
    
    This is the canonical execution path for all function calls,
    whether they originate from XML-based or template-level syntax.
    """
    
    def __init__(self, template_provider: T):
        """
        Initialize the Evaluator.
        
        Args:
            template_provider: Component that provides template lookup and execution
        """
        self.template_provider = template_provider
        # Assuming template_provider has find_template or is the TaskSystem itself
        if not hasattr(template_provider, 'find_template'):
             logger.warning("Evaluator initialized with a template_provider that lacks 'find_template'. Step execution might fail.")

    def find_template(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Helper to access template finding capability."""
        if hasattr(self.template_provider, 'find_template'):
            # Assuming template_provider is the TaskSystem or similar
            return self.template_provider.find_template(identifier)
        else:
            logger.error(f"Template provider {type(self.template_provider)} lacks find_template method.")
            return None

    def _parse_step_to_call_node(self, step: Dict[str, Any]) -> Optional[FunctionCallNode]:
        """Parses a step dictionary into a FunctionCallNode if it's a call type."""
        if step.get("type") != "call" or "template" not in step:
            # Log warning or handle non-call steps if needed later
            logger.debug(f"Skipping non-call step: {step.get('type')}")
            return None

        template_name = step["template"]
        arguments = []
        for arg_def in step.get("arguments", []):
            if "name" in arg_def and "value" in arg_def:
                # Note: AST nodes might expect specific value types,
                # this assumes value is directly usable or evaluate_arguments handles types.
                # The value here is likely a string like "{{ variable }}" which evaluateFunctionCall will resolve.
                arguments.append(ArgumentNode(name=arg_def["name"], value=arg_def["value"]))
            elif "value" in arg_def: # Handle positional arguments if needed
                 arguments.append(ArgumentNode(value=arg_def["value"]))
            else:
                logger.warning(f"Skipping invalid argument definition in step: {arg_def}")
                # Consider if this should be an error

        return FunctionCallNode(template_name=template_name, arguments=arguments)

    def _execute_steps(self, steps: List[Dict[str, Any]], env: Environment) -> TaskResult:
        """Executes a list of steps sequentially, binding results."""
        last_result: TaskResult = {"status": "PENDING", "content": "No steps executed.", "notes": {}}
        # Use a copy for local bindings within the sequence
        current_env = env.copy() # Use copy to avoid modifying caller's env directly

        for i, step in enumerate(steps):
            step_name = step.get('description', step.get('template', f'Step {i+1}'))
            logger.debug(f"Executing step {i+1}/{len(steps)}: {step_name}")
            call_node = self._parse_step_to_call_node(step)

            if call_node:
                try:
                    # Resolve the template definition for the function being called in the step
                    step_template = self.find_template(call_node.template_name)

                    if not step_template:
                         logger.error(f"Template '{call_node.template_name}' not found for step {i+1}.")
                         # Decide error handling: return error TaskResult or raise?
                         return {"status": "FAILED", "content": f"Template '{call_node.template_name}' not found.", "notes": {"step": i+1, "failed_template": call_node.template_name}}

                    # evaluateFunctionCall handles evaluating arguments *within* its logic using the env
                    sub_call_result = self.evaluateFunctionCall(call_node, current_env, step_template)
                    last_result = sub_call_result # Store result of this step

                    # Check status and fail fast
                    if sub_call_result.get("status") != "COMPLETE":
                        logger.warning(f"Step {i+1} ({call_node.template_name}) failed. Stopping sequence.")
                        # Optionally add failure info to notes
                        last_result.setdefault("notes", {})["sequence_failure_step"] = i+1
                        return last_result

                    # Bind result to environment if requested
                    if "bind_result_to" in step:
                        var_name = step["bind_result_to"]
                        logger.debug(f"Binding result of step {i+1} to env var '{var_name}'")
                        # Bind the *entire* TaskResult dict
                        current_env = current_env.extend({var_name: sub_call_result})


                except TaskError as te:
                     logger.error(f"TaskError executing step {i+1} ({call_node.template_name}): {te.message}")
                     return format_error_result(te) # Return formatted TaskError
                except Exception as e:
                    logger.exception(f"Unexpected error executing step {i+1} ({call_node.template_name}): {e}")
                    return {"status": "FAILED", "content": f"Unexpected error in step {i+1}: {e}", "notes": {"step": i+1, "template": call_node.template_name}}
            else:
                logger.warning(f"Skipping non-call or invalid step {i+1}: {step}")
                # Decide how to handle non-call steps if they become relevant

        # Return the result of the last successfully executed step
        return last_result

    def evaluate(self, node: Any, env: Environment) -> Any:
        """
        Evaluate an AST node or template dictionary in the given environment.
        
        Args:
            node: AST node to evaluate
            env: Environment for variable resolution
            
        Returns:
            Evaluation result
            
        Raises:
            TaskError: If evaluation fails
        """
        logger.debug(f"Evaluator.evaluate called with node type: {type(node).__name__}, env: {env}")

        template_name_or_id = None
        template = None

        # Determine template name/ID and potentially fetch template
        if isinstance(node, FunctionCallNode):
            template_name_or_id = node.template_name
            # Don't fetch template yet, evaluateFunctionCall will handle it
        elif isinstance(node, dict) and 'name' in node: # If node is already template-like
             template_name_or_id = node.get('name')
             template = node # Assume the dict is the template itself
        elif isinstance(node, dict) and 'template' in node and 'type' in node and node['type'] == 'call': # Handle step-like dicts passed directly
             template_name_or_id = node['template']
             # Convert step dict to FunctionCallNode before proceeding
             call_node_from_dict = self._parse_step_to_call_node(node)
             if call_node_from_dict:
                 node = call_node_from_dict # Replace node with the parsed FunctionCallNode
                 template_name_or_id = node.template_name
             else:
                 logger.warning(f"Could not parse dictionary as a call step: {node}")
                 # Fall through to unsupported type error

        # Fetch template if we have a name but haven't fetched it yet
        if template_name_or_id and template is None and isinstance(node, FunctionCallNode):
             template = self.find_template(template_name_or_id)

        # --- START New Logic for Step Execution ---
        if template and isinstance(template.get('steps'), list):
            logger.debug(f"Detected template '{template_name_or_id}' with steps. Executing sequence.")
            # Context management check (optional for now)
            # if template.get("context_management", {}).get("fresh_context") == "disabled":
            #      pass
            return self._execute_steps(template['steps'], env)
        # --- END New Logic ---

        # --- Existing Logic ---
        # Handle D-E loop node (assuming it's passed as a dict matching the template structure)
        if isinstance(node, dict) and node.get("type") == "director_evaluator_loop":
            # Pass the template dict directly
            return self._evaluate_director_evaluator_loop(node, env)

        # Handle standard function call node
        if isinstance(node, FunctionCallNode):
             # evaluateFunctionCall will fetch template if not provided
             return self.evaluateFunctionCall(node, env, template)

        # Handle simple variable resolution or literals if node is a string
        if isinstance(node, str):
             if self._is_variable_reference(node):
                 var_name = self._extract_variable_name(node)
                 try:
                     return env.find(var_name)
                 except ValueError as e:
                      raise create_input_validation_error(f"Variable not found: {var_name}", details={"variable": var_name}) from e
             else:
                 # Try resolving as complex path or return literal
                 try:
                     return env.find(node)
                 except ValueError:
                      return node # Return as literal string

        # Default: return the node itself (for literals like numbers, bools, etc.)
        if not isinstance(node, (dict, list)): # Avoid returning complex structures unintentionally
            logger.debug(f"Evaluator.evaluate: Passing through literal node of type {type(node).__name__}")
            return node

        # If we reach here, the node type is unsupported
        logger.error(f"Unsupported node type for evaluation: {type(node)}")
        raise create_task_failure(f"Unsupported node type for evaluation: {type(node)}", UNEXPECTED_ERROR)


    def evaluateFunctionCall(self, call_node: FunctionCallNode, env: Environment, template: Optional[Dict[str, Any]] = None) -> TaskResult:
        """
        Evaluate a function call AST node.

        This is the canonical execution path for function calls.
        
        This is the canonical execution path for function calls.
        
        Args:
            call_node: FunctionCallNode to evaluate
            env: Environment for variable resolution
            template: Optional pre-looked-up template to avoid redundant lookups
            
        Returns:
            Result of function execution as a TaskResult dictionary
            
        Raises:
            TaskError: If evaluation fails
        """
        try:
            # Use provided template or lookup if not provided
            if template is None:
                template = self.template_provider.find_template(call_node.template_name)
            if not template:
                details = {
                    "template_name": call_node.template_name
                }
                if hasattr(self.template_provider, "templates"):
                    templates = getattr(self.template_provider, "templates", {})
                    details["available_templates"] = list(templates.keys())
                
                raise create_task_failure(
                    message=f"Template not found: '{call_node.template_name}'",
                    reason="input_validation_failure",
                    details=details,
                    source_node=call_node
                )
            
            # Evaluate arguments in caller's environment
            pos_args, named_args = self._evaluate_arguments(call_node.arguments, env)
            
            # Bind arguments to template parameters
            try:
                param_bindings = self._bind_arguments_to_parameters(template, pos_args, named_args)
            except ValueError as e:
                raise create_input_validation_error(
                    message=f"Error binding arguments for '{call_node.template_name}': {str(e)}",
                    details={
                        "template_name": call_node.template_name,
                        "positional_args": str(pos_args),
                        "named_args": str(named_args)
                    },
                    source_node=call_node
                )
            
            # Create function environment with parameter bindings
            func_env = env.extend(param_bindings)
            
            # Execute the template in the function environment
            return self._execute_template(template, func_env)
        except TaskError:
            # Re-raise task errors
            raise
        except Exception as e:
            # Wrap other exceptions in TaskError
            raise create_unexpected_error(
                message=f"Error evaluating function call '{call_node.template_name}': {str(e)}",
                exception=e,
                source_node=call_node
            )
    
    def _evaluate_arguments(self, arguments: List[ArgumentNode], env: Environment) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Evaluate function call arguments in the given environment.
        
        Args:
            arguments: List of ArgumentNode objects
            env: Environment for variable resolution
            
        Returns:
            Tuple of (positional_args, named_args)
            
        Raises:
            TaskError: If argument evaluation fails
        """
        pos_args = []
        named_args = {}
        
        for arg in arguments:
            # Evaluate the argument value
            evaluated_value = self._evaluate_argument(arg, env)
            
            # Store in appropriate collection based on argument type
            if arg.is_named() and arg.name is not None:
                named_args[arg.name] = evaluated_value
            else:
                pos_args.append(evaluated_value)
        
        return pos_args, named_args
    
    def _evaluate_argument(self, arg_node: ArgumentNode, env: Environment) -> Any:
        """
        Evaluate a single argument in the given environment.
        
        Args:
            arg_node: ArgumentNode to evaluate
            env: Environment for variable resolution
            
        Returns:
            Evaluated argument value
            
        Raises:
            TaskError: If argument evaluation fails
        """
        try:
            # Check if the value is a variable reference
            if isinstance(arg_node.value, str):
                # Case 1: Explicit variable reference with braces {{variable}}
                if self._is_variable_reference(arg_node.value):
                    var_name = self._extract_variable_name(arg_node.value)
                    try:
                        return env.find(var_name)
                    except ValueError as e:
                        raise create_input_validation_error(
                            message=f"Error resolving variable '{var_name}': {str(e)}",
                            details={"variable_name": var_name},
                            source_node=arg_node
                        )
                
                # Case 2: Try to resolve complex paths (with . or [])
                # This includes cases like "obj.prop", "array[0]", or "obj.array[0].prop"
                elif "." in arg_node.value or ("[" in arg_node.value and "]" in arg_node.value):
                    try:
                        return env.find(arg_node.value)
                    except ValueError:
                        # Return as literal string if path doesn't resolve
                        return arg_node.value
                
                # Case 3: Try as simple variable name
                elif arg_node.value.isidentifier():
                    try:
                        return env.find(arg_node.value)
                    except ValueError:
                        # Return as literal if not found
                        return arg_node.value
            
            # For literal values or non-variable strings, return as is
            return arg_node.value
        except TaskError:
            # Re-raise task errors
            raise
        except Exception as e:
            # Wrap other exceptions in TaskError
            raise create_unexpected_error(
                message=f"Error evaluating argument: {str(e)}",
                exception=e,
                source_node=arg_node
            )
    
    def _is_variable_reference(self, value: str) -> bool:
        """
        Check if a string is a variable reference.
        
        Args:
            value: String value to check
            
        Returns:
            True if the value is a variable reference, False otherwise
        """
        # Using a basic pattern for variable references: {{variable_name}}
        return isinstance(value, str) and value.startswith("{{") and value.endswith("}}")
    
    def _extract_variable_name(self, var_ref: str) -> str:
        """
        Extract variable name from a variable reference.
        
        Args:
            var_ref: Variable reference string (e.g., "{{variable_name}}")
            
        Returns:
            Variable name
        """
        # Strip the {{ and }} and trim whitespace
        return var_ref[2:-2].strip()
    
    def _bind_arguments_to_parameters(self, template: Dict[str, Any], pos_args: List[Any], 
                                     named_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bind arguments to template parameters.
        
        Args:
            template: Template definition
            pos_args: Positional arguments
            named_args: Named arguments
            
        Returns:
            Dictionary mapping parameter names to values
            
        Raises:
            ValueError: If required parameters are missing or too many positional arguments
        """
        # Convert positional arguments to named arguments based on parameter order
        parameters = template.get("parameters", {})
        param_names = list(parameters.keys())
        
        # Combine positional and named arguments
        combined_args = named_args.copy()
        
        # Map positional arguments to parameter names
        for i, arg in enumerate(pos_args):
            if i < len(param_names):
                combined_args[param_names[i]] = arg
            else:
                raise ValueError(f"Too many positional arguments for template '{template.get('name')}'")
        
        # Using existing parameter resolution logic from template_utils
        if callable(resolve_parameters):
            return resolve_parameters(template, combined_args)
        
        # Fallback logic if resolve_parameters is not available
        parameters = template.get("parameters", {})
        param_names = list(parameters.keys())
        result = {}
        
        # Assign positional arguments
        for i, arg in enumerate(pos_args):
            if i < len(param_names):
                result[param_names[i]] = arg
            else:
                raise ValueError(f"Too many positional arguments for template '{template.get('name')}'")
        
        # Assign named arguments (overwriting positional if specified)
        for name, value in named_args.items():
            if name in parameters:
                result[name] = value
            else:
                raise ValueError(f"Unknown parameter '{name}' for template '{template.get('name')}'")
        
        # Apply defaults for unspecified parameters
        for name, schema in parameters.items():
            if name not in result and "default" in schema:
                result[name] = schema["default"]
        
        # Check for missing required parameters
        for name, schema in parameters.items():
            if name not in result and schema.get("required", False):
                raise ValueError(f"Missing required parameter '{name}' for template '{template.get('name')}'")
        
        return result
    
    def _execute_template(self, template: Dict[str, Any], env: Environment) -> Dict[str, Any]:
        """
        Execute a template with the given environment.
        
        Args:
            template: Template definition
            env: Environment with parameter bindings
            
        Returns:
            Template execution result
            
        Raises:
            TaskError: If template execution fails
        """
        try:
            # Extract task type and subtype from template
            task_type = template.get("type", "atomic") # Default to atomic
            task_subtype = template.get("subtype", "generic") # Default to generic

            # Extract inputs from environment based on template parameters
            inputs = {}
            template_params = template.get("parameters", {})
            for param_name in template_params.keys():
                # Use env.find to respect scoping and handle potential errors
                try:
                    inputs[param_name] = env.find(param_name)
                except ValueError:
                    # Parameter not found in env, check if it has a default or is required later
                    if "default" not in template_params[param_name] and template_params[param_name].get("required", False):
                         # This should ideally be caught during binding, but double-check
                         raise create_input_validation_error(f"Missing required parameter '{param_name}' in environment for template '{template.get('name')}'")
                    # If not required and no default, it remains absent from inputs

            # Handle context management settings if present (less relevant here, more for TaskSystem)
            # context_mgmt = template.get("context_management", {})

            # Check for explicit file paths defined *in the template itself* (less common)
            # file_paths = template.get("file_paths", [])
            # if file_paths:
            #     inputs["file_paths"] = file_paths # Add/overwrite if defined in template

            # Execute template using template provider's execute_task method
            # This assumes template_provider (likely TaskSystem) has this method
            if not hasattr(self.template_provider, 'execute_task'):
                 raise create_task_failure(f"Template provider {type(self.template_provider)} does not support execute_task", UNEXPECTED_ERROR)

            # Pass necessary context if execute_task requires it (e.g., memory_system)
            # This depends on the signature of template_provider.execute_task
            # Example: result = self.template_provider.execute_task(task_type, task_subtype, inputs, memory_system=self.memory_system)
            # Assuming execute_task only needs type, subtype, inputs for now:
            result = self.template_provider.execute_task(task_type, task_subtype, inputs)

            # Add JSON parsing for the result content
            output_format = template.get("output_format", {})
            if isinstance(output_format, dict) and output_format.get("type") == "json":
                try:
                    import json
                    content = result.get("content", "")
                    if isinstance(content, str) and content.strip():
                        parsed_content = json.loads(content)
                        result["parsedContent"] = parsed_content
                except json.JSONDecodeError as e:
                    # Add parsing error to notes but don't fail the task
                    if "notes" not in result:
                        result["notes"] = {}
                    result["notes"]["parseError"] = f"Failed to parse output as JSON: {str(e)}"
            
            return result
        except Exception as e:
            # Wrap exceptions in TaskError
            raise create_unexpected_error(
                message=f"Error executing template: {str(e)}",
                exception=e
            )
    
    def _evaluate_director_evaluator_loop(self, node: Any, env: Environment) -> Dict[str, Any]:
        """ 
        Executes the logic for a director_evaluator_loop task.
        
        Args:
            node: The director_evaluator_loop AST node
            env: Environment for variable resolution
            
        Returns:
            TaskResult containing the loop execution results
        """
        # Node is expected to be a dictionary matching the template structure
        if not isinstance(node, dict):
             return format_error_result(create_task_failure(
                 f"Director-Evaluator loop node must be a dictionary, got {type(node)}", INPUT_VALIDATION_FAILURE
             ))

        logging.info(f"Starting Director-Evaluator Loop: {node.get('description', 'N/A')}")

        # --- Initialization ---
        # Evaluate parameters defined in the loop template itself using the initial env
        try:
             # Use resolve_parameters to handle defaults and required checks based on loop's own params
             # Pass env.bindings as the provided arguments
             evaluated_params = resolve_parameters(node, env.bindings)
        except ValueError as e:
             logging.error(f"Error resolving parameters for D-E loop '{node.get('name')}': {e}")
             return format_error_result(create_input_validation_error(f"Loop parameter error: {e}"))

        # Get max_iterations from evaluated params, falling back to template default, then constant
        max_iter_param = evaluated_params.get('max_cycles', node.get('parameters', {}).get('max_cycles', {}).get('default', DEFAULT_MAX_ITERATIONS))
        try:
            # Handle potential variable substitution in max_iterations value itself
            if isinstance(max_iter_param, str) and self._is_variable_reference(max_iter_param):
                 max_iterations_str = self._extract_variable_name(max_iter_param)
                 max_iterations = int(env.find(max_iterations_str))
            else:
                 max_iterations = int(max_iter_param) # Use evaluated param directly
        except (ValueError, TypeError) as e:
             logging.warning(f"Invalid max_iterations value '{max_iter_param}', using default {DEFAULT_MAX_ITERATIONS}. Error: {e}")
             max_iterations = DEFAULT_MAX_ITERATIONS

        # Get node definitions (director, evaluator, script, condition) from the template dict
        director_node_def = node.get('director')
        evaluator_node_def = node.get('evaluator')
        script_node_def = node.get('script_execution')
        termination_condition_def = node.get('termination_condition')

        # Validate required nodes
        if not director_node_def or not evaluator_node_def:
            logging.error("D-E Loop Error: Missing director or evaluator definition in the template.")
            return format_error_result(create_task_failure(
                "Director-Evaluator loop template is missing director or evaluator definition.",
                INPUT_VALIDATION_FAILURE
            ))

        iteration_history = []
        # Create initial loop environment containing evaluated parameters
        initial_bindings = evaluated_params.copy()

        # --- START New Logic for target_files ---
        target_files_str = evaluated_params.get("target_files", "[]") # Default to empty JSON array string
        try:
            # Ensure it's treated as a string before parsing
            if not isinstance(target_files_str, str):
                 # If it was already parsed to a list (e.g., by upstream logic), use it directly
                 if isinstance(target_files_str, list):
                      target_files_list = target_files_str
                 else:
                      raise ValueError(f"Expected string or list for target_files, got {type(target_files_str)}")
            else:
                 target_files_list = json.loads(target_files_str)

            if not isinstance(target_files_list, list) or not all(isinstance(f, str) for f in target_files_list):
                raise ValueError("target_files parameter must be a JSON list of strings.")
            initial_bindings["target_files"] = target_files_list # Store the list
            logging.debug(f"Parsed target_files: {target_files_list}")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid 'target_files' parameter value: '{target_files_str}'. Error: {e}")
            # Return an error TaskResult
            return format_error_result(create_input_validation_error(f"Invalid target_files parameter: {e}"))
        # --- END New Logic for target_files ---

        # Create the loop's environment, potentially inheriting from the caller's env
        # For now, create a fresh environment with only the loop's evaluated parameters
        loop_env = Environment(bindings=initial_bindings) # No parent=env for isolation initially

        last_director_result: Optional[TaskResult] = None
        last_script_output: Optional[Dict[str, Any]] = None # Stores {stdout, stderr, exit_code}
        last_evaluation_result: Optional[TaskResult] = None
        loop_error: Optional[TaskError] = None
        loop_status = "FAILED" # Default status

        logging.debug(f"Loop configured: max_iterations={max_iterations}, script_present={bool(script_node_def)}, condition_present={bool(termination_condition_def)}")

        # --- Iteration Loop ---
        for iteration in range(max_iterations):
            current_iteration = iteration + 1
            logging.debug(f"--- D-E Loop Iteration {current_iteration}/{max_iterations} ---")
            current_iteration_results = {"iteration": current_iteration} # Store results for this iteration
            
            # Extend environment with iteration number for potential use in steps
            loop_env_iter = loop_env.extend({"current_iteration": current_iteration})

            try:
                # --- 1. Execute Director ---
                logging.debug("Executing Director step...")
                director_env_bindings = {}
                if last_evaluation_result: # Pass feedback from *previous* iteration
                    feedback = last_evaluation_result.get("notes", {}).get("feedback")
                    success = last_evaluation_result.get("notes", {}).get("success")
                    if feedback is not None: director_env_bindings['evaluation_feedback'] = feedback
                    if success is not None: director_env_bindings['evaluation_success'] = success
                    # Pass the full evaluation result if needed by the template inputs
                    director_env_bindings['last_evaluation'] = last_evaluation_result

                director_env = loop_env_iter.extend(director_env_bindings)

                # Recursively evaluate the director node definition (which is likely a 'call' dict)
                last_director_result = self.evaluate(director_node_def, director_env)
                current_iteration_results["director"] = last_director_result
                logging.debug(f"Director result status: {last_director_result.get('status')}, content: {str(last_director_result.get('content'))[:100]}...")

                # Check for failure
                if last_director_result.get("status") == "FAILED":
                    logging.error("Director step failed.")
                    # Wrap the error to indicate it happened within the loop/subtask
                    raise create_task_failure("Director step failed within loop.", SUBTASK_FAILURE, details=last_director_result)

                # Update loop_env for subsequent steps *in this iteration*
                # Pass director's content (or potentially full result if needed)
                loop_env_iter = loop_env_iter.extend({"director_result": last_director_result.get("content", "")})

                # --- 2. Execute Script (Optional) ---
                last_script_output = None # Initialize for this iteration

                if script_node_def:
                    logging.debug("Executing Script step...")
                    # Environment already contains director_result from previous step
                    script_env = loop_env_iter

                    # Recursively evaluate the script node definition (e.g., a call to system:run_script)
                    script_task_result = self.evaluate(script_node_def, script_env)
                    current_iteration_results["script"] = script_task_result
                    logging.debug(f"Script result status: {script_task_result.get('status')}")

                    # Check for failure
                    if script_task_result.get("status") == "FAILED":
                        logging.error("Script execution step failed.")
                        raise create_task_failure("Script execution step failed within loop.", SUBTASK_FAILURE, details=script_task_result)

                    # Extract script output from notes (assuming system:run_script tool format)
                    script_output_notes = script_task_result.get("notes", {}).get("scriptOutput")
                    if script_output_notes and isinstance(script_output_notes, dict):
                        last_script_output = script_output_notes # Store the dict {stdout, stderr, exit_code}
                        # Update loop_env for the Evaluator step
                        loop_env_iter = loop_env_iter.extend({
                            "script_stdout": last_script_output.get("stdout", ""),
                            "script_stderr": last_script_output.get("stderr", ""),
                            "script_exit_code": last_script_output.get("exit_code", -1)
                        })
                        logging.debug(f"Script output captured: exit_code={last_script_output.get('exit_code')}")
                    else:
                        logging.warning("Script executed but did not produce expected 'scriptOutput' dict in notes.")
                        # Still update env, but with error indicators
                        loop_env_iter = loop_env_iter.extend({
                            "script_stdout": script_task_result.get("content", ""), # Maybe content has something?
                            "script_stderr": "Script output format error",
                            "script_exit_code": -1
                        })
                        last_script_output = {"stdout": "", "stderr": "Output format error", "exit_code": -1} # Store error state

                # --- 3. Execute Evaluator ---
                logging.debug("Executing Evaluator step...")
                # Environment already contains director_result and script outputs
                evaluator_env = loop_env_iter

                # Recursively evaluate the evaluator node definition
                last_evaluation_result = self.evaluate(evaluator_node_def, evaluator_env)
                current_iteration_results["evaluator"] = last_evaluation_result
                logging.debug(f"Evaluator result status: {last_evaluation_result.get('status')}, content: {str(last_evaluation_result.get('content'))[:100]}...")

                # Check for failure
                if last_evaluation_result.get("status") == "FAILED":
                    logging.error("Evaluator step failed.")
                    raise create_task_failure("Evaluator step failed within loop.", SUBTASK_FAILURE, details=last_evaluation_result)

                # Validate EvaluationResult structure (presence of notes.success)
                if not isinstance(last_evaluation_result.get("notes"), dict) or \
                   'success' not in last_evaluation_result['notes']:
                     logging.warning("Evaluator result missing 'notes.success'. Treating as failure.")
                     # Ensure notes structure exists and set success to False
                     if 'notes' not in last_evaluation_result: last_evaluation_result['notes'] = {}
                     last_evaluation_result['notes']['success'] = False
                     # Ensure feedback exists, even if generic
                     if 'feedback' not in last_evaluation_result['notes']:
                         last_evaluation_result['notes']['feedback'] = 'Evaluation failed or structure invalid.'

                # --- 4. Check Termination Conditions ---
                evaluation_success = last_evaluation_result.get("notes", {}).get("success", False)

                # Check 1: Success from Evaluator
                if evaluation_success:
                    logging.info(f"Loop terminating successfully after iteration {current_iteration} based on evaluation.")
                    loop_status = "COMPLETE"
                    iteration_history.append(current_iteration_results) # Add final iteration results
                    break # Exit loop

                # Check 2: Custom Termination Condition (if exists)
                if termination_condition_def:
                     condition_str = termination_condition_def.get('condition_string')
                     if condition_str:
                         # Create env for condition check, adding 'evaluation' binding
                         # Also add other relevant bindings like 'current_iteration'
                         condition_env = loop_env_iter.extend({
                             "evaluation": last_evaluation_result,
                             # Ensure current_iteration is available if needed by condition
                             "current_iteration": current_iteration
                         })
                         try:
                             if self._evaluate_termination_condition(condition_str, condition_env):
                                 logging.info(f"Loop terminating early after iteration {current_iteration} due to condition: {condition_str}")
                                 loop_status = "COMPLETE" # Or maybe a different status like "HALTED"? Using COMPLETE for now.
                                 iteration_history.append(current_iteration_results) # Add final iteration results
                                 break # Exit loop
                         except Exception as cond_err:
                              logging.error(f"Error evaluating termination condition '{condition_str}': {cond_err}. Loop will continue.")
                              # Do not break the loop on condition evaluation error

                # --- Prepare for next iteration ---
                # Add results to history *before* loop continues/breaks
                iteration_history.append(current_iteration_results)
                # Update loop_env with results needed for the *next* iteration's feedback
                loop_env = loop_env_iter.extend({"last_evaluation_result": last_evaluation_result})

            except TaskError as e:
                logging.error(f"TaskError in D-E Loop Iteration {current_iteration}: {e.message}")
                loop_error = e
                current_iteration_results["error"] = e.to_dict() # Add error to iteration results
                iteration_history.append(current_iteration_results) # Record partial iteration results
                break # Exit loop on error
            except Exception as e:
                 logging.exception(f"Unexpected error in D-E Loop Iteration {current_iteration}:")
                 loop_error = create_task_failure(f"Unexpected error in loop iteration {current_iteration}: {str(e)}", UNEXPECTED_ERROR)
                 current_iteration_results["error"] = loop_error.to_dict()
                 iteration_history.append(current_iteration_results)
                 break # Exit loop on unexpected error

        # --- Loop Finished: Format Final Result ---
        if loop_error:
            # Loop terminated due to an error within an iteration
            final_content = f"Director-Evaluator loop failed during iteration {len(iteration_history)}."
            final_notes = {
                "error": loop_error.to_dict(),
                "iteration_history": iteration_history,
                # Iterations completed is len(history) - 1 because error occurred *in* the last recorded one
                "iterations_completed": max(0, len(iteration_history) - 1)
            }
            logging.info(f"D-E Loop finished with error: {loop_error.message}")
            return {"status": "FAILED", "content": final_content, "notes": final_notes}

        elif loop_status == "COMPLETE":
            # Loop terminated successfully (evaluation success or condition met)
            final_content = last_director_result.get("content", "Loop completed successfully.") if last_director_result else "Loop completed successfully."
            final_notes = {
                "iteration_history": iteration_history,
                "final_evaluation": last_evaluation_result,
                "iterations_completed": len(iteration_history)
            }
            logging.info(f"D-E Loop finished successfully after {len(iteration_history)} iterations.")
            return {"status": "COMPLETE", "content": final_content, "notes": final_notes}

        else: # loop_status == "FAILED" implicitly (max iterations reached)
            # Loop finished due to max iterations without success
            final_content = f"Director-Evaluator loop reached max iterations ({max_iterations}) without meeting success criteria."
            final_notes = {
                "iteration_history": iteration_history,
                "final_evaluation": last_evaluation_result, # Include the last evaluation result
                "iterations_completed": max_iterations,
                "termination_reason": "max_iterations_reached"
            }
            logging.info(f"D-E Loop finished after reaching max iterations ({max_iterations}).")
            # Consider this COMPLETE, but indicate reason in notes.
            return {"status": "COMPLETE", "content": final_content, "notes": final_notes}
    
    def _evaluate_termination_condition(self, expression: str, env: Environment) -> bool:
        """
        Safely evaluates simple termination condition expressions.
        Avoids using eval(). Handles basic variable access and comparisons.

        Args:
            expression: The condition string (e.g., "evaluation.notes.success == true").
            env: The environment containing relevant variables (e.g., 'evaluation', 'current_iteration').

        Returns:
            True if the condition evaluates to true, False otherwise or if evaluation fails.
        """
        logging.debug(f"Evaluating termination condition: '{expression}'")
        expression = expression.strip()

        try:
            # --- Handle Specific Supported Patterns ---

            # Pattern 1: evaluation.notes.success == true
            if expression == "evaluation.notes.success == true":
                evaluation = env.find("evaluation") # Expects last_evaluation_result bound as 'evaluation'
                return evaluation.get("notes", {}).get("success", False) is True

            # Pattern 2: current_iteration >= X
            match_iter = re.match(r"current_iteration\s*(>=|>|<=|<|==)\s*(\d+)", expression)
            if match_iter:
                op = match_iter.group(1)
                val = int(match_iter.group(2))
                current_iter = env.find("current_iteration")
                logging.debug(f"Checking iteration condition: {current_iter} {op} {val}")
                if op == ">=": return current_iter >= val
                if op == ">": return current_iter > val
                if op == "<=": return current_iter <= val
                if op == "<": return current_iter < val
                if op == "==": return current_iter == val
                return False # Should not happen with regex

            # Pattern 3: evaluation.notes.metrics.some_metric >= X.Y (Example)
            match_metric = re.match(r"evaluation\.notes\.details\.metrics\.(\w+)\s*(>=|>|<=|<|==)\s*([\d.]+)", expression)
            if match_metric:
                 metric_name = match_metric.group(1)
                 op = match_metric.group(2)
                 val_str = match_metric.group(3)
                 try:
                     val = float(val_str)
                     evaluation = env.find("evaluation")
                     metric_value = evaluation.get("notes",{}).get("details",{}).get("metrics",{}).get(metric_name)
                     if metric_value is not None:
                         metric_value = float(metric_value) # Ensure numeric comparison
                         logging.debug(f"Checking metric condition: {metric_name}={metric_value} {op} {val}")
                         if op == ">=": return metric_value >= val
                         if op == ">": return metric_value > val
                         if op == "<=": return metric_value <= val
                         if op == "<": return metric_value < val
                         if op == "==": return metric_value == val
                     else:
                          logging.warning(f"Metric '{metric_name}' not found in evaluation notes for condition check.")
                          return False
                 except (ValueError, TypeError) as metric_err:
                     logging.warning(f"Error comparing metric in condition '{expression}': {metric_err}")
                     return False

            # --- Fallback for Unsupported Expressions ---
            logging.warning(f"Unsupported termination condition expression format: '{expression}'. Treating as False.")
            return False

        except Exception as e:
            # Catch potential errors during env.find or comparisons
            logging.error(f"Error evaluating termination condition '{expression}': {e}. Treating as False.")
            return False
    
    def execute_subtask(self, inputs: Dict[str, Any], template: Dict[str, Any], parent_env: Optional[Environment] = None, isolate: bool = True) -> Dict[str, Any]:
        """
        Execute a subtask with proper environment handling.
        
        Args:
            inputs: Subtask inputs
            template: Subtask template
            parent_env: Optional parent environment
            isolate: Whether to isolate the subtask environment from parent
            
        Returns:
            Subtask result
        """
        # Create environment based on isolation setting
        if isolate or parent_env is None:
            # Create isolated environment (not extending parent)
            subtask_env = Environment(inputs)
        else:
            # Create environment extending parent
            subtask_env = parent_env.extend(inputs)
        
        # Execute subtask with appropriate environment
        return self._execute_template(template, subtask_env)
