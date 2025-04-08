"""Evaluator component implementation.

This module contains the Evaluator class, which is responsible for
evaluating AST nodes, particularly function calls.
"""
from typing import Any, Dict, List, Optional, Union, Tuple, TypeVar, cast

from task_system.ast_nodes import ArgumentNode, FunctionCallNode
from task_system.template_utils import Environment, resolve_parameters
from system.errors import (
    TaskError, 
    create_input_validation_error,
    create_unexpected_error,
    create_task_failure,
    INPUT_VALIDATION_FAILURE
)
from evaluator.interfaces import EvaluatorInterface, TemplateLookupInterface

# Type variable for the template lookup interface
T = TypeVar('T', bound=TemplateLookupInterface)


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
        if hasattr(node, "type"):
            if node.type == "call":
                return self.evaluateFunctionCall(node, env)
            # Add additional node types as needed
        
        # Default: return the node itself (for literals, etc.)
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
                # Check for explicit variable reference pattern "{{var}}"
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
                
                # Check if this could be a direct variable reference (plain identifier)
                elif arg_node.value.isidentifier():
                    try:
                        return env.find(arg_node.value)
                    except ValueError:
                        # Return as literal string if not found as variable
                        return arg_node.value
                
                # Check for array indexing or dot notation patterns without explicit {{ }}
                elif ("[" in arg_node.value and arg_node.value.endswith("]")) or "." in arg_node.value:
                    try:
                        return env.find(arg_node.value)
                    except ValueError:
                        # Return as literal string if pattern doesn't resolve
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
