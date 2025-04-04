"""Utility functions for template management."""
from typing import Dict, Any, Optional, List, Union, Type


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
