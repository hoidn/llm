"""
// === IDL-CREATION-GUIDLINES === // Object Oriented: Use OO Design. // Design Patterns: Use Factory, Builder and Strategy patterns where possible // ** Complex parameters JSON : Use JSON where primitive params are not possible and document them in IDL like "Expected JSON format: { "key1": "type1", "key2": "type2" }" // == !! BEGIN IDL TEMPLATE !! === // === CODE-CREATION-RULES === // Strict Typing: Always use strict typing. Avoid using ambiguous or variant types. // Primitive Types: Favor the use of primitive types wherever possible. // Portability Mandate: Python code must be written with the intent to be ported to Java, Go, and JavaScript. Consider language-agnostic logic and avoid platform-specific dependencies. // No Side Effects: Functions should be pure, meaning their output should only be determined by their input without any observable side effects. // Testability: Ensure that every function and method is easily testable. Avoid tight coupling and consider dependency injection where applicable. // Documentation: Every function, method, and module should be thoroughly documented, especially if there's a nuance that's not directly evident from its signature. // Contractual Obligation: The definitions provided in this IDL are a strict contract. All specified interfaces, methods, and constraints must be implemented precisely as defined without deviation. // =======================

@module EvaluatorModule
// Dependencies: TemplateLookupInterface (TaskSystem), BaseHandler, ArgumentNode, FunctionCallNode, Environment, TaskError
// Description: Evaluates Abstract Syntax Tree (AST) nodes, focusing on function calls.
//              It resolves arguments, binds them to parameters, and orchestrates template
//              execution via the TemplateLookupInterface (TaskSystem). Handles the
//              Director-Evaluator loop execution logic.
module EvaluatorModule {

    // Interface for the Evaluator component.
    interface Evaluator extends EvaluatorInterface {
        // @depends_on(TemplateLookupInterface) // Requires TaskSystem to provide templates

        // Constructor
        // Preconditions:
        // - template_provider is an instance implementing TemplateLookupInterface (e.g., TaskSystem).
        // Postconditions:
        // - Evaluator is initialized with the template provider dependency.
        void __init__(TemplateLookupInterface template_provider);

        // Evaluates an AST node within a given environment.
        // Preconditions:
        // - node is an AST node (e.g., FunctionCallNode, DirectorEvaluatorLoopNode).
        // - env is a valid Environment instance.
        // Postconditions:
        // - If the node is a recognized type (call, director_evaluator_loop), delegates to the specific evaluation method.
        // - Otherwise, returns the node itself (e.g., for literals).
        // - Returns the evaluation result (can be Any type, often a TaskResult dict).
        // Raises:
        // - TaskError if evaluation fails.
        Any evaluate(Any node, Environment env);

        // Evaluates a function call AST node. Canonical path for all function calls.
        // Preconditions:
        // - call_node is a valid FunctionCallNode.
        // - env is a valid Environment instance.
        // - template is an optional pre-fetched template dictionary.
        // Postconditions:
        // - Looks up the template if not provided.
        // - Evaluates arguments in the caller's environment.
        // - Binds arguments to template parameters.
        // - Executes the template via the template_provider's execute_task method.
        // - Returns the TaskResult dictionary from the template execution.
        // Raises:
        // - TaskError if template not found, argument binding fails, or execution fails.
        // Expected JSON format for return value: { "status": "string", "content": "Any", "notes": { ... } }
        dict<string, Any> evaluateFunctionCall(FunctionCallNode call_node, Environment env, optional dict<string, Any> template);

        // Executes a subtask template with appropriate environment isolation.
        // Preconditions:
        // - inputs is a dictionary of subtask parameters.
        // - template is the subtask template dictionary.
        // - parent_env is an optional Environment instance from the caller.
        // - isolate is a boolean indicating whether the subtask environment should inherit from the parent.
        // Expected JSON format for inputs: { "param1": "value1", ... }
        // Expected JSON format for template: { "name": "string", ... }
        // Postconditions:
        // - Creates a new environment for the subtask (isolated or extended).
        // - Executes the subtask template via `_execute_template`.
        // - Returns the TaskResult dictionary from the subtask execution.
        // Expected JSON format for return value: { "status": "string", "content": "Any", "notes": { ... } }
        dict<string, Any> execute_subtask(dict<string, Any> inputs, dict<string, Any> template, optional Environment parent_env, boolean isolate);

        // Additional methods... (Private/protected methods like _evaluate_arguments, _execute_template are not part of the public IDL)
    };

    // Interface defining the contract for AST evaluation.
    interface EvaluatorInterface {
        // Evaluates a function call AST node.
        // Preconditions: See Evaluator.evaluateFunctionCall
        // Postconditions: See Evaluator.evaluateFunctionCall
        // Raises: TaskError
        dict<string, Any> evaluateFunctionCall(FunctionCallNode call_node, Environment env, optional dict<string, Any> template);
    };
};
// == !! END IDL TEMPLATE !! ===
"""

"""
This module contains the Evaluator class, which is responsible for
evaluating AST nodes, particularly function calls.
"""
"""
import logging
import re
from typing import Any, Dict, List, Optional, Union, Tuple, TypeVar, cast

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
    
    def evaluate(self, node: Any, env: Environment) -> Any:
        """
        Evaluate an AST node in the given environment.
        
        Args:
            node: AST node to evaluate
            env: Environment for variable resolution
            
        Returns:
            Evaluation result
            
        Raises:
            TaskError: If evaluation fails
        """
        # Handle different node types
        node_type = getattr(node, "type", None)
        
        if node_type == "director_evaluator_loop":
            return self._evaluate_director_evaluator_loop(node, env)
        elif node_type == "call":
            return self.evaluateFunctionCall(node, env)
        # Add additional node types as needed
        
        # Default: return the node itself (for literals, etc.)
        logging.debug(f"Evaluator.evaluate: Passing through node of type {node_type or type(node).__name__}")
        return node
    
    def evaluateFunctionCall(self, call_node: FunctionCallNode, env: Environment, template: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Evaluate a function call AST node.
        
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
            task_type = template.get("type", "atomic")
            task_subtype = template.get("subtype", "generic")
            
            # Extract inputs from environment
            inputs = {}
            for key in env.bindings:
                inputs[key] = env.bindings[key]
            
            # Handle context management settings if present
            context_mgmt = template.get("context_management", {})
            
            # Check for explicit file paths to include
            file_paths = template.get("file_paths", [])
            if file_paths:
                inputs["file_paths"] = file_paths
            
            # Execute template using template provider
            result = self.template_provider.execute_task(task_type, task_subtype, inputs)
            
            # Add JSON parsing
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
        logging.info(f"Starting Director-Evaluator Loop: {getattr(node, 'description', 'N/A')}")
        
        # --- Initialization ---
        max_iterations = getattr(node, 'max_iterations', DEFAULT_MAX_ITERATIONS)
        # Safely get node references - assumes these attributes exist on the parsed node
        director_node = getattr(node, 'director_node', None)
        evaluator_node = getattr(node, 'evaluator_node', None)
        script_node = getattr(node, 'script_execution_node', None)
        termination_condition_node = getattr(node, 'termination_condition_node', None)

        # Validate required nodes
        if not director_node or not evaluator_node:
            logging.error("D-E Loop Error: Missing director or evaluator definition in the node.")
            return format_error_result(create_task_failure(
                "Director-Evaluator loop node is missing director or evaluator definition.",
                INPUT_VALIDATION_FAILURE
            ))

        iteration_history = []
        loop_env = env  # Start with the environment passed to the loop node
        last_director_result: Optional[Dict[str, Any]] = None
        last_script_output: Optional[Dict[str, Any]] = None # Stores {stdout, stderr, exit_code}
        last_evaluation_result: Optional[Dict[str, Any]] = None
        loop_error: Optional[TaskError] = None
        loop_status = "FAILED" # Default status, updated on success or max iterations reached

        logging.debug(f"Loop configured: max_iterations={max_iterations}, script_present={bool(script_node)}, condition_present={bool(termination_condition_node)}")
        
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

                # Recursively evaluate the director node using self.eval
                last_director_result = self.evaluate(director_node, director_env)
                current_iteration_results["director"] = last_director_result
                logging.debug(f"Director result status: {last_director_result.get('status')}")

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
                
                if script_node:
                    logging.debug("Executing Script step...")
                    # Environment already contains director_result from previous step
                    script_env = loop_env_iter

                    # Recursively evaluate the script node (e.g., a <call task="system:run_script">)
                    # self.eval handles resolving the call and invoking the Handler tool
                    script_task_result = self.evaluate(script_node, script_env)
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

                # Recursively evaluate the evaluator node
                last_evaluation_result = self.evaluate(evaluator_node, evaluator_env)
                current_iteration_results["evaluator"] = last_evaluation_result
                logging.debug(f"Evaluator result status: {last_evaluation_result.get('status')}")

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
                if termination_condition_node:
                     condition_str = getattr(termination_condition_node, 'condition_string', None)
                     if condition_str:
                         # Create env for condition check, adding 'evaluation' binding
                         condition_env = loop_env_iter.extend({"evaluation": last_evaluation_result})
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
