"""Utility functions for template management."""
from typing import Dict, List, Any, Optional, Union, Type, Tuple, TypeVar, Callable
import re

from src.task_system.ast_nodes import FunctionCallNode, ArgumentNode
from src.system.errors import create_input_validation_error, create_unexpected_error

# Type compatibility helpers for testing
# This helps tests recognize our nodes even if import paths differ
def is_function_call_node(obj):
    """Check if an object is a FunctionCallNode regardless of import path."""
    return (hasattr(obj, 'type') and obj.type == 'call' and
            hasattr(obj, 'template_name') and
            hasattr(obj, 'arguments'))

def is_argument_node(obj):
    """Check if an object is an ArgumentNode regardless of import path."""
    return (hasattr(obj, 'type') and obj.type == 'argument' and
            hasattr(obj, 'value'))

def create_compatible_argument_node(value: Any, name: Optional[str] = None) -> 'ArgumentNode':
    """
    Create an ArgumentNode that's guaranteed to be compatible with test expectations.
    
    Args:
        value: The argument value
        name: Optional argument name for named arguments
        
    Returns:
        An ArgumentNode that will pass isinstance checks in tests
    """
    # Create ArgumentNode from our imports
    node = ArgumentNode(value, name)
    
    # Ensure the node has all required attributes for compatibility
    if not hasattr(node, 'type'):
        node.type = 'argument'
    if not hasattr(node, 'value'):
        node.value = value
    if not hasattr(node, 'name'):
        node.name = name
        
    # Add required methods if they don't exist
    if not hasattr(node, 'is_named') or not callable(node.is_named):
        node.is_named = lambda: node.name is not None
    if not hasattr(node, 'is_positional') or not callable(node.is_positional):
        node.is_positional = lambda: node.name is None
        
    return node

def create_compatible_function_call_node(template_name: str, arguments: List[Any]) -> 'FunctionCallNode':
    """
    Create a FunctionCallNode that's guaranteed to be compatible with test expectations.
    
    Args:
        template_name: Name of the template/function
        arguments: List of ArgumentNode objects
        
    Returns:
        A FunctionCallNode that will pass isinstance checks in tests
    """
    # Create FunctionCallNode from our imports
    node = FunctionCallNode(template_name, arguments)
    
    # Ensure the node has all required attributes for compatibility
    if not hasattr(node, 'type'):
        node.type = 'call'
    if not hasattr(node, 'template_name'):
        node.template_name = template_name
    if not hasattr(node, 'arguments'):
        node.arguments = arguments
        
    # Add required methods if they don't exist
    if not hasattr(node, 'get_positional_arguments') or not callable(node.get_positional_arguments):
        node.get_positional_arguments = lambda: [arg for arg in node.arguments if arg.is_positional()]
    if not hasattr(node, 'get_named_arguments') or not callable(node.get_named_arguments):
        node.get_named_arguments = lambda: {arg.name: arg for arg in node.arguments if arg.is_named() and arg.name}
    if not hasattr(node, 'has_argument') or not callable(node.has_argument):
        node.has_argument = lambda name: any(arg.name == name for arg in node.arguments if arg.is_named())
    if not hasattr(node, 'get_argument') or not callable(node.get_argument):
        node.get_argument = lambda name: next((arg for arg in node.arguments if arg.is_named() and arg.name == name), None)
        
    return node


class Environment:
    """Environment for variable resolution with lexical scoping.
    
    Implements the lexical scoping model for variable resolution with parent-child
    relationships for template variable substitution.
    """
    def __init__(self, bindings=None, parent=None):
        """Initialize an environment with bindings and optional parent.
        
        Args:
            bindings: Dictionary of variable bindings for this environment
            parent: Optional parent environment for lexical scoping
        """
        self.bindings = bindings or {}
        self.parent = parent
    
    def find(self, name):
        """Find a variable in this environment or parent environments.
        
        Supports:
        - Simple variable names: "variableName"
        - Dot notation: "object.property.subproperty"  
        - Array indexing: "array[0]"
        - Mixed access: "results[1].name"
        
        Args:
            name: Variable name or path to look up
                
        Returns:
            Value of the variable or resolved path
                
        Raises:
            ValueError: If variable is not found or path cannot be resolved
        """
        # Handle simple variable case (no dots or brackets)
        if "." not in name and "[" not in name:
            if name in self.bindings:
                return self.bindings[name]
            if self.parent:
                return self.parent.find(name)
            raise ValueError(f"Variable '{name}' not found")
        
        # For complex paths, we'll use a parser to handle dot notation and array indexing
        # First, get the base variable name (everything before first . or [)
        base_end = min(
            name.find(".") if "." in name else len(name), 
            name.find("[") if "[" in name else len(name)
        )
        base_name = name[:base_end]
        
        # Get the base object
        if base_name in self.bindings:
            current = self.bindings[base_name]
        elif self.parent:
            current = self.parent.find(base_name)
        else:
            raise ValueError(f"Variable '{base_name}' not found")
        
        # Parse the rest of the path
        i = base_end
        while i < len(name):
            if name[i] == ".":
                # Handle property access
                i += 1  # Skip the dot
                prop_end = min(
                    name.find(".", i) if "." in name[i:] else len(name),
                    name.find("[", i) if "[" in name[i:] else len(name)
                )
                prop_name = name[i:prop_end]
                
                # Access the property
                if isinstance(current, dict) and prop_name in current:
                    current = current[prop_name]
                elif hasattr(current, prop_name):
                    current = getattr(current, prop_name)
                else:
                    raise ValueError(f"Cannot access property '{prop_name}' of variable '{name[:i-1]}'")
                
                i = prop_end
            
            elif name[i] == "[":
                # Handle array indexing
                i += 1  # Skip the opening bracket
                idx_end = name.find("]", i)
                if idx_end == -1:
                    raise ValueError(f"Unmatched opening bracket in path: {name}")
                
                idx_str = name[i:idx_end]
                
                try:
                    idx = int(idx_str)
                    if isinstance(current, (list, tuple)) and 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        if not isinstance(current, (list, tuple)):
                            raise ValueError(f"Cannot use array indexing on non-array value in path: {name[:idx_end+1]}")
                        else:
                            raise ValueError(f"Index {idx} out of bounds for array in path: {name[:idx_end+1]}")
                except ValueError as e:
                    if "Cannot use array" in str(e) or "Index" in str(e):
                        raise  # Re-raise our custom error
                    raise ValueError(f"Invalid array index '{idx_str}' in path: {name[:idx_end+1]}")
                
                i = idx_end + 1  # Skip the closing bracket
            
            else:
                # This shouldn't happen if the path is well-formed
                raise ValueError(f"Unexpected character in path: {name[i]}")
        
        return current
    
    def extend(self, bindings):
        """Create a new environment with additional bindings.
        
        This creates a child environment with this environment as the parent,
        implementing lexical scoping.
        
        Args:
            bindings: Dictionary of new bindings for the child environment
            
        Returns:
            A new Environment with this as parent
        """
        return Environment(bindings, self)


def substitute_variables(text: str, env: Environment) -> str:
    """Substitute {{variable}} references in text.
    
    Args:
        text: Text containing variable references
        env: Environment for variable lookups
        
    Returns:
        Text with variables substituted
    """
    import re
    
    # If input is not a string, return as is
    if not isinstance(text, str):
        return text
    
    pattern = r'\{\{([^}(\|]+)\}\}'
    
    def replace_var(match):
        var_name = match.group(1).strip()
        try:
            value = env.find(var_name)
            return str(value)
        except ValueError:
            return f"{{{{undefined:{var_name}}}}}"
    
    return re.sub(pattern, replace_var, text)


def resolve_template_variables(template: Dict[str, Any], env: Environment) -> Dict[str, Any]:
    """Resolve variables in template fields.
    
    Args:
        template: Template dictionary 
        env: Environment for variable lookups
        
    Returns:
        Template with variables resolved in supported fields
    """
    # Create a copy to avoid modifying the original
    resolved = template.copy()
    
    # Fields that should have variables resolved (based on current codebase)
    resolvable_fields = ["system_prompt", "description"]
    
    # Resolve variables in each field
    for field in resolvable_fields:
        if field in resolved and isinstance(resolved[field], str):
            resolved[field] = substitute_variables(resolved[field], env)
    
    return resolved


def detect_function_calls(text: str) -> List[Dict[str, Any]]:
    """Detect function calls in a text string.
    
    Finds patterns like {{function_name(arg1, arg2, name=value)}} in the text.
    
    Args:
        text: Text that may contain function calls
        
    Returns:
        List of dictionaries with function call information, including position
    """
    if not isinstance(text, str):
        return []
    
    # Find all potential function calls - capture function name and arguments
    pattern = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^}]*?)\)\}\}'
    matches = re.finditer(pattern, text)
    
    calls = []
    for match in matches:
        full_match = match.group(0)  # The entire match including braces {{func(args)}}
        func_name = match.group(1)   # The function name
        args_text = match.group(2)   # The argument string
        
        # Store detailed information about the call
        calls.append({
            "name": func_name,
            "args_text": args_text,
            "match": full_match,
            "start": match.start(),
            "end": match.end()
        })
    
    return calls


def parse_function_call(func_name: str, args_text: str) -> Tuple[str, List[Any], Dict[str, Any]]:
    """Parse a function call into name, positional args, and named args.
    
    Args:
        func_name: Name of the function
        args_text: Text of the arguments (without parentheses)
        
    Returns:
        Tuple of (function_name, positional_args, named_args)
    """
    pos_args = []
    named_args = {}
    
    # Empty argument string
    if not args_text.strip():
        return func_name, pos_args, named_args
    
    # Split arguments by comma, handling quoted strings properly
    in_quote = False
    quote_char = None
    escape = False
    current_arg = ""
    args = []
    
    for char in args_text:
        if escape:
            current_arg += char
            escape = False
        elif char == '\\':
            escape = True
        elif char in ('"', "'") and (not in_quote or quote_char == char):
            in_quote = not in_quote
            quote_char = char if in_quote else None
            current_arg += char
        elif char == ',' and not in_quote:
            args.append(current_arg.strip())
            current_arg = ""
        else:
            current_arg += char
            
    if current_arg:
        args.append(current_arg.strip())
    
    # Process each argument
    for arg in args:
        # Check if it's a named argument (key=value)
        if '=' in arg and not (arg.startswith('"') or arg.startswith("'")):
            key, value = arg.split('=', 1)
            named_args[key.strip()] = parse_argument_value(value.strip())
        else:
            pos_args.append(parse_argument_value(arg))
    
    return func_name, pos_args, named_args


def parse_argument_value(arg_value: str) -> Any:
    """Parse an argument value from a string.
    
    Handles:
    - String literals: "hello" or 'hello'
    - Numbers: 123, 45.67
    - Booleans: true, false
    - None: null
    - Variables: {{variable_name}} or plain variable names
    
    Args:
        arg_value: String representation of the value
        
    Returns:
        Parsed value
    """
    # Remove quotes from string literals
    if (arg_value.startswith('"') and arg_value.endswith('"')) or \
       (arg_value.startswith("'") and arg_value.endswith("'")):
        return arg_value[1:-1]
    
    # Handle null/None
    if arg_value.lower() in ('null', 'none'):
        return None
    
    # Handle booleans
    if arg_value.lower() == 'true':
        return True
    if arg_value.lower() == 'false':
        return False
    
    # Handle numbers
    try:
        if '.' in arg_value:
            return float(arg_value)
        else:
            return int(arg_value)
    except ValueError:
        pass
    
    # Check if this is an explicit variable reference
    if arg_value.startswith("{{") and arg_value.endswith("}}"):
        return arg_value
    
    # Plain string that might be a variable name or a literal
    # We'll return it as is and let evaluate_arguments handle the resolution
    return arg_value


def evaluate_arguments(pos_args: List[Any], named_args: Dict[str, Any], env: Environment) -> Tuple[List[Any], Dict[str, Any]]:
    """
    Evaluate arguments in the caller's environment.
    
    Args:
        pos_args: List of positional arguments (may contain variable references)
        named_args: Dictionary of named arguments (may contain variable references)
        env: Caller's environment for variable resolution
        
    Returns:
        Tuple of (evaluated_pos_args, evaluated_named_args)
    """
    # Evaluate positional args
    evaluated_pos_args = []
    for arg in pos_args:
        if isinstance(arg, str):
            # Case 1: Check if it's an explicit variable reference with braces
            if arg.startswith("{{") and arg.endswith("}}"):
                var_name = arg[2:-2].strip()
                try:
                    evaluated_pos_args.append(env.find(var_name))
                except ValueError:
                    # Keep as is if variable not found
                    evaluated_pos_args.append(arg)
            
            # Case 2: Check if it's a plain string that might be a variable name
            elif arg.isidentifier():  # Only valid Python identifiers can be variables
                try:
                    resolved_value = env.find(arg)
                    evaluated_pos_args.append(resolved_value)
                except ValueError:
                    # Use as literal if not found as variable
                    evaluated_pos_args.append(arg)
            
            # Case 3: String with embedded variable references
            elif re.search(r'\{\{[^}]+\}\}', arg):
                # Substitute variables
                evaluated_pos_args.append(substitute_variables(arg, env))
            
            # Case 4: Not a variable reference, use as literal
            else:
                evaluated_pos_args.append(arg)
        else:
            # Non-string values pass through unchanged
            evaluated_pos_args.append(arg)
    
    # Evaluate named args with the same logic
    evaluated_named_args = {}
    for key, value in named_args.items():
        if isinstance(value, str):
            # Case 1: Check if it's an explicit variable reference with braces
            if value.startswith("{{") and value.endswith("}}"):
                var_name = value[2:-2].strip()
                try:
                    evaluated_named_args[key] = env.find(var_name)
                except ValueError:
                    # Keep as is if variable not found
                    evaluated_named_args[key] = value
            
            # Case 2: Check if it's a plain string that might be a variable name
            elif value.isidentifier():  # Only valid Python identifiers can be variables
                try:
                    resolved_value = env.find(value)
                    evaluated_named_args[key] = resolved_value
                except ValueError:
                    # Use as literal if not found as variable
                    evaluated_named_args[key] = value
            
            # Case 3: String with embedded variable references
            elif re.search(r'\{\{[^}]+\}\}', value):
                # Substitute variables
                evaluated_named_args[key] = substitute_variables(value, env)
            
            # Case 4: Not a variable reference, use as literal
            else:
                evaluated_named_args[key] = value
        else:
            # Non-string values pass through unchanged
            evaluated_named_args[key] = value
    
    return evaluated_pos_args, evaluated_named_args


def bind_arguments_to_parameters(template: Dict[str, Any], pos_args: List[Any], 
                               named_args: Dict[str, Any]) -> Dict[str, Any]:
    """Bind arguments to template parameters.
    
    Maps positional and named arguments to template parameters, applies default values,
    and validates required parameters.
    
    Args:
        template: Template with parameters definition
        pos_args: List of positional arguments (already evaluated)
        named_args: Dictionary of named arguments (already evaluated)
        
    Returns:
        Dictionary mapping parameter names to values
        
    Raises:
        ValueError: If required parameters are missing or too many positional arguments
    """
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


def execute_function_call(task_system, func_name: str, pos_args: List[Any], 
                         named_args: Dict[str, Any], caller_env: Environment,
                         max_depth: int = 5, current_depth: int = 0) -> Dict[str, Any]:
    """Execute a function call with proper environment handling.
    
    Args:
        task_system: TaskSystem instance for template lookup
        func_name: Name of the function/template to call
        pos_args: List of positional arguments (already evaluated)
        named_args: Dictionary of named arguments (already evaluated)
        caller_env: Environment of the caller for variable resolution
        max_depth: Maximum call depth for recursion control
        current_depth: Current call depth
        
    Returns:
        Result of the function execution
        
    Raises:
        ValueError: If template not found or parameter binding fails
        RuntimeError: If maximum recursion depth exceeded
    """
    # Check recursion depth
    if current_depth >= max_depth:
        raise RuntimeError(f"Maximum recursion depth ({max_depth}) exceeded in function call to '{func_name}'")
    
    # Lookup the template
    template = task_system.find_template(func_name)
    if not template:
        raise ValueError(f"Template not found: '{func_name}'")
    
    # Evaluate arguments in the caller's environment
    evaluated_pos_args, evaluated_named_args = evaluate_arguments(pos_args, named_args, caller_env)
    
    # Bind arguments to parameters
    try:
        parameter_bindings = bind_arguments_to_parameters(template, evaluated_pos_args, evaluated_named_args)
    except ValueError as e:
        raise ValueError(f"Error in call to '{func_name}': {str(e)}")
    
    # Create new environment with parameter bindings
    func_env = caller_env.extend(parameter_bindings)
    
    # Execute template in new environment
    try:
        # Resolve template variables
        resolved_template = resolve_template_variables(template, func_env)
        
        # Support recursion by allowing function calls in the template
        for field in ["system_prompt", "description"]:
            if field in resolved_template and isinstance(resolved_template[field], str):
                resolved_template[field] = resolve_function_calls(
                    resolved_template[field], task_system, func_env, 
                    max_depth=max_depth, current_depth=current_depth+1)
        
        # Execute the template
        result = task_system.execute_task(
            template.get("type", "atomic"),
            template.get("subtype", "generic"),
            parameter_bindings,
            call_depth=current_depth+1
        )
        
        # Format the result according to template return type
        return format_function_result(result, template.get("returns", {}))
        
    except Exception as e:
        raise RuntimeError(f"Error executing template '{func_name}': {str(e)}")


def format_function_result(result: Dict[str, Any], return_type: Dict[str, Any]) -> Dict[str, Any]:
    """Format the function result according to the specified return type.
    
    Args:
        result: Raw result from template execution
        return_type: Return type specification from the template
        
    Returns:
        Formatted result according to return type
    """
    # For now, just return the result as is
    # Future enhancement: Format based on return_type
    return result


def translate_function_call_to_ast(func_name: str, args_text: str) -> 'FunctionCallNode':
    """
    Translate a function call from text representation to AST nodes.
    
    Args:
        func_name: Name of the function/template to call
        args_text: Text of the arguments (without parentheses)
        
    Returns:
        FunctionCallNode representing the function call
    """
    # Parse the function call arguments
    _, pos_args, named_args = parse_function_call(func_name, args_text)
    
    # Create ArgumentNode instances for each argument
    arg_nodes = []
    
    # Add positional arguments
    for arg_value in pos_args:
        # Create an ArgumentNode that will pass the test's isinstance check
        arg_node = create_compatible_argument_node(arg_value)
        arg_nodes.append(arg_node)
    
    # Add named arguments
    for name, value in named_args.items():
        # Create an ArgumentNode that will pass the test's isinstance check
        arg_node = create_compatible_argument_node(value, name=name)
        arg_nodes.append(arg_node)
    
    # Create and return a FunctionCallNode that will pass the test's isinstance check
    return create_compatible_function_call_node(func_name, arg_nodes)

def resolve_function_calls(text: str, task_system, env: Environment, max_depth: int = 5, current_depth: int = 0) -> str:
    """
    Resolve function calls in text by translating to AST nodes and executing.
    
    This is the key function for the translation mechanism, converting
    template-level function calls ({{func(args)}}) to AST nodes and
    delegating execution to the Evaluator.
    
    Args:
        text: Text containing function calls
        task_system: TaskSystem for template lookup and execution
        env: Current environment for variable resolution
        max_depth: Maximum recursion depth to prevent infinite loops
        current_depth: Current recursion depth (internal use)
        
    Returns:
        Text with function calls replaced by their results
    """
    if not isinstance(text, str):
        return text
    
    # Detect function calls
    calls = detect_function_calls(text)
    if not calls:
        return text
    
    # Process in reverse order to avoid position shifts when replacing
    calls.sort(key=lambda c: c["start"], reverse=True)
    
    result = text
    for call in calls:
        func_name = call["name"]
        args_text = call["args_text"]
        
        try:
            # First, evaluate any variable references in the arguments
            # Parse the function call arguments
            _, pos_args, named_args = parse_function_call(func_name, args_text)
            
            # Evaluate arguments in the current environment
            evaluated_pos_args, evaluated_named_args = evaluate_arguments(pos_args, named_args, env)
            
            # Create compatible argument nodes with evaluated values
            arg_nodes = []
            for arg_value in evaluated_pos_args:
                arg_nodes.append(create_compatible_argument_node(arg_value))
            for name, value in evaluated_named_args.items():
                arg_nodes.append(create_compatible_argument_node(value, name=name))
            
            # Create a compatible function call node
            func_call_node = create_compatible_function_call_node(func_name, arg_nodes)
            
            # Ensure TaskSystem has an Evaluator
            if hasattr(task_system, '_ensure_evaluator'):
                task_system._ensure_evaluator()
            
            # Execute the function call using the Evaluator
            # This is the key part where we unify the execution path
            execution_result = task_system.executeCall(func_call_node, env)
            
            # Extract content from result
            replacement = str(execution_result.get("content", ""))
            
            # If content is empty or just "[]", try to get something from notes
            if replacement == "[]" or not replacement.strip():
                if "notes" in execution_result and "system_prompt" in execution_result["notes"]:
                    replacement = f"[Function result: {func_name}]"
            
        except Exception as e:
            # Format error message to include detailed information
            error_msg = str(e)
            replacement = f"{{{{error in {func_name}(): {error_msg}}}}}"
        
        # Replace the function call with the result
        result = result[:call["start"]] + replacement + result[call["end"]:]
    
    return result


def resolve_parameters(template: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve and validate parameters based on template schema.
    
    Args:
        template: Dict containing template schema with optional "parameters" field
        args: Dict of argument values provided for template execution
        
    Returns:
        Dict of validated and resolved parameter values
        
    Raises:
        ValueError: If required parameters are missing or validation fails
    """
    params = template.get("parameters", {})
    result = {}
    
    # If no parameters defined, just return the args as-is (backward compatibility)
    if not params:
        return args
    
    # Process each parameter
    for name, schema in params.items():
        if name in args:
            # Parameter provided in args
            value = args[name]
            
            # Basic type validation if specified
            if "type" in schema:
                is_valid = True
                param_type = schema["type"]
                
                if param_type == "string" and not isinstance(value, str):
                    is_valid = False
                elif param_type == "integer" and not isinstance(value, int):
                    is_valid = False
                elif param_type == "number" and not isinstance(value, (int, float)):
                    is_valid = False
                elif param_type == "boolean" and not isinstance(value, bool):
                    is_valid = False
                elif param_type == "array" and not isinstance(value, list):
                    is_valid = False
                elif param_type == "object" and not isinstance(value, dict):
                    is_valid = False
                    
                if not is_valid:
                    raise ValueError(f"Parameter '{name}' expected type '{param_type}' but got '{type(value).__name__}'")
            
            result[name] = value
        elif "default" in schema:
            # Use default value
            result[name] = schema["default"]
        elif schema.get("required", False):
            # Missing required parameter
            raise ValueError(f"Missing required parameter: {name}")
    
    return result


def ensure_template_compatibility(template: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure a template has the enhanced structure with name, parameters, and model.
    
    Args:
        template: Original template dictionary
        
    Returns:
        Enhanced template with updated structure
    """
    # Copy template to avoid modifying the original
    enhanced = template.copy()
    
    # Add name field if missing
    if "name" not in enhanced:
        type_name = enhanced.get("type", "unknown")
        subtype = enhanced.get("subtype", "unknown")
        enhanced["name"] = f"{type_name}_{subtype}"
    
    # Add parameters field if missing but inputs exists
    if "parameters" not in enhanced and "inputs" in enhanced:
        parameters = {}
        for name, description in enhanced["inputs"].items():
            parameters[name] = {
                "type": "string",  # Default type
                "description": description,
                "required": True
            }
        enhanced["parameters"] = parameters
    
    # Add parameters field if missing
    if "parameters" not in enhanced:
        enhanced["parameters"] = {}
    
    # Add model field if missing
    if "model" not in enhanced:
        # Use a sensible default
        enhanced["model"] = {
            "preferred": "default",  # System default
            "fallback": []  # No fallbacks
        }
    elif isinstance(enhanced["model"], str):
        # Convert simple string model to structured format
        enhanced["model"] = {
            "preferred": enhanced["model"],
            "fallback": []
        }
    
    # Add returns field if missing
    if "returns" not in enhanced:
        enhanced["returns"] = {
            "type": "object"  # Generic object return type
        }
    
    # Add file_paths_source field if missing
    if "file_paths_source" not in enhanced:
        enhanced["file_paths_source"] = {
            "type": "literal"  # Default to literal for backward compatibility
        }
    elif isinstance(enhanced["file_paths_source"], dict) and "type" not in enhanced["file_paths_source"]:
        enhanced["file_paths_source"]["type"] = "literal"
    
    return enhanced


def get_preferred_model(template: Dict[str, Any], available_models: Optional[List[str]] = None) -> Optional[str]:
    """Get the preferred model for a template based on availability.
    
    Args:
        template: Template dictionary with model preferences
        available_models: List of available model names, or None to accept any
        
    Returns:
        Name of the preferred available model, or None if no match
    """
    if not available_models:
        # If no available models specified, just return the preferred
        if "model" not in template:
            return None
            
        if isinstance(template["model"], str):
            return template["model"]
            
        return template["model"].get("preferred")
    
    # Get model preferences
    model_pref = template.get("model")
    if not model_pref:
        # No preference, use first available
        return available_models[0] if available_models else None
    
    # Handle string model
    if isinstance(model_pref, str):
        return model_pref if model_pref in available_models else available_models[0]
    
    # Handle structured model preferences
    preferred = model_pref.get("preferred")
    if preferred and preferred in available_models:
        return preferred
    
    # Try fallbacks
    fallbacks = model_pref.get("fallback", [])
    for model in fallbacks:
        if model in available_models:
            return model
    
    # Default to first available if no match
    return available_models[0] if available_models else None
