"""Task System implementation."""
from typing import Dict, List, Any, Optional
import json

from .template_utils import resolve_parameters, ensure_template_compatibility, get_preferred_model

class TaskSystem:
    """Task System for task execution and management.
    
    Manages task templates, execution, and context management.
    """
    
    def __init__(self):
        """Initialize the Task System."""
        self.templates = {}  # Templates by name
        self.template_index = {}  # Maps type:subtype to template name
        
    def find_matching_tasks(self, input_text: str, memory_system) -> List[Dict[str, Any]]:
        """Find matching templates based on a provided input string.
        
        Args:
            input_text: Natural language task description
            memory_system: MemorySystem instance providing context
            
        Returns:
            List of matching templates with scores
        """
        matches = []
        
        # Filter for atomic templates only
        for name, template in self.templates.items():
            if template.get("type") == "atomic":
                # Calculate similarity score
                description = template.get("description", "")
                score = self._calculate_similarity_score(input_text, description)
                
                # Add to matches if score is above threshold
                if score > 0.1:  # Low threshold to ensure we get some matches
                    task_type = template.get("type", "")
                    subtype = template.get("subtype", "")
                    matches.append({
                        "task": template,
                        "score": score,
                        "taskType": task_type,
                        "subtype": subtype
                    })
        
        # Sort by score (descending)
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches
    
    def _calculate_similarity_score(self, input_text: str, template_description: str) -> float:
        """Calculate similarity score between input text and template description.
        
        This is a simple heuristic approach using word overlap.
        
        Args:
            input_text: User's input text
            template_description: Template description
            
        Returns:
            Similarity score (0-1)
        """
        # Normalize texts
        input_text = input_text.lower()
        template_description = template_description.lower()
        
        # Remove punctuation
        for char in ".,;:!?()[]{}\"'":
            input_text = input_text.replace(char, " ")
            template_description = template_description.replace(char, " ")
        
        # Split into words
        input_words = set(input_text.split())
        template_words = set(template_description.split())
        
        # Calculate overlap
        if not template_words:
            return 0.0
            
        # Jaccard similarity
        intersection = len(input_words.intersection(template_words))
        union = len(input_words.union(template_words))
        
        if union == 0:
            return 0.0
            
        return intersection / union
    
    def register_template(self, template: Dict[str, Any]) -> None:
        """Register a task template with enhanced structure.
        
        Args:
            template: Template definition
        """
        # Ensure template is compatible with enhanced structure
        enhanced_template = ensure_template_compatibility(template)
        
        # Get template name, type and subtype
        template_name = enhanced_template.get("name")
        template_type = enhanced_template.get("type")
        template_subtype = enhanced_template.get("subtype")
        
        # Register by name (primary key)
        self.templates[template_name] = enhanced_template
        
        # Also index by type and subtype
        if template_type and template_subtype:
            key = f"{template_type}:{template_subtype}"
            self.template_index[key] = template_name
    
    def find_template(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Find template by name or type:subtype combination.
        
        Args:
            identifier: Template name or 'type:subtype' string
            
        Returns:
            Template dictionary or None if not found
        """
        # Try direct name lookup first
        if identifier in self.templates:
            return self.templates[identifier]
        
        # Try type:subtype lookup via index
        if identifier in self.template_index:
            name = self.template_index[identifier]
            return self.templates.get(name)
        
        return None
    
    def execute_task(self, task_type: str, task_subtype: str, inputs: Dict[str, Any], 
                     memory_system=None, available_models: Optional[List[str]] = None) -> Dict[str, Any]:
        """Execute a task with parameter validation and model selection.
        
        Args:
            task_type: Type of task
            task_subtype: Subtype of task
            inputs: Task inputs
            memory_system: Optional Memory System instance
            available_models: Optional list of available model names
            
        Returns:
            Task result
        """
        # Check if task type and subtype are registered
        task_key = f"{task_type}:{task_subtype}"
        template_name = self.template_index.get(task_key)
        
        if not template_name or template_name not in self.templates:
            return {
                "status": "FAILED",
                "content": f"Unknown task type: {task_key}",
                "notes": {
                    "error": "Task type not registered"
                }
            }
        
        # Get the template
        template = self.templates[template_name]
        
        # Resolve parameters
        try:
            resolved_inputs = resolve_parameters(template, inputs)
        except ValueError as e:
            return {
                "status": "FAILED",
                "content": str(e),
                "notes": {
                    "error": "PARAMETER_ERROR"
                }
            }
        
        # Create environment from resolved parameters
        from .template_utils import Environment, resolve_template_variables
        env = Environment(resolved_inputs)
        
        # Resolve variables in template fields
        resolved_template = resolve_template_variables(template, env)
        
        # Select model if available_models provided
        selected_model = None
        if available_models:
            selected_model = get_preferred_model(resolved_template, available_models)
        
        # Handle specific task types
        if task_type == "atomic":
            if task_subtype == "associative_matching" or task_subtype == "test_matching" or task_subtype == "var_test":
                result = self._execute_associative_matching(resolved_template, resolved_inputs, memory_system)
                
                # Add model info if selected
                if selected_model:
                    if "notes" not in result:
                        result["notes"] = {}
                    result["notes"]["selected_model"] = selected_model
                    
                return result
        
        # Default fallback for unimplemented task types
        return {
            "status": "FAILED",
            "content": "Task execution not implemented for this task type",
            "notes": {
                "task_type": task_type,
                "task_subtype": task_subtype,
                "selected_model": selected_model
            }
        }
    
    def _execute_associative_matching(self, task, inputs, memory_system):
        """Execute an associative matching task.
        
        Args:
            task: The task definition
            inputs: Task inputs
            memory_system: The Memory System instance
            
        Returns:
            Task result with relevant files
        """
        from .templates.associative_matching import execute_template
        
        # Get query from inputs
        query = inputs.get("query", "")
        if not query:
            return {
                "content": "[]",
                "status": "COMPLETE",
                "notes": {
                    "error": "No query provided"
                }
            }
        
        # Execute the template
        try:
            max_results = inputs.get("max_results", 20)
            relevant_files = execute_template(query, memory_system, max_results)
            
            # Convert to JSON string
            import json
            file_list_json = json.dumps(relevant_files)
            
            return {
                "content": file_list_json,
                "status": "COMPLETE",
                "notes": {
                    "file_count": len(relevant_files)
                }
            }
        except Exception as e:
            return {
                "content": "[]",
                "status": "FAILED",
                "notes": {
                    "error": f"Error during associative matching: {str(e)}"
                }
            }
