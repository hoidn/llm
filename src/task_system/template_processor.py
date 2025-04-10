"""Template processing module for Task System.

This module provides utilities for processing templates, including
variable substitution and function call resolution.
"""
from typing import Dict, Any, List, Optional, Union, Set

from task_system.template_utils import Environment, substitute_variables, resolve_function_calls

class TemplateProcessor:
    """
    Processes templates by handling variable substitution and function calls.
    
    This class centralizes the template processing logic to ensure consistent
    behavior across different template fields.
    """
    
    def __init__(self, task_system):
        """
        Initialize the template processor.
        
        Args:
            task_system: TaskSystem instance for function call execution
        """
        self.task_system = task_system
    
    def process_template(self, template: Dict[str, Any], env: Environment) -> Dict[str, Any]:
        """
        Process a template by resolving variables and function calls.
        
        Args:
            template: Template definition
            env: Environment for variable resolution
            
        Returns:
            Processed template with resolved variables and function calls
        """
        # Create a copy to avoid modifying the original
        processed = template.copy()
        
        # Fields that should be processed (in order)
        # First resolve variables, then function calls
        fields_to_process = self.get_fields_to_process(template)
        
        # Process each field
        for field in fields_to_process:
            if field in processed and isinstance(processed[field], str):
                # First substitute variables
                processed[field] = substitute_variables(processed[field], env)
                
                # Then resolve function calls
                processed[field] = resolve_function_calls(processed[field], self.task_system, env)
        
        return processed
    
    def get_fields_to_process(self, template: Dict[str, Any]) -> List[str]:
        """
        Get the list of fields that should be processed.
        
        Args:
            template: Template definition
            
        Returns:
            List of field names to process
        """
        # Standard fields that always need processing
        standard_fields = [
            "system_prompt", 
            "description", 
            "taskPrompt"
        ]
        
        # Add any custom fields from the template
        result = standard_fields.copy()
        
        # Look for additional text fields that might need processing
        for key, value in template.items():
            if key not in result and isinstance(value, str) and ('{{' in value):
                # This field contains potential variable references or function calls
                result.append(key)
        
        return result
