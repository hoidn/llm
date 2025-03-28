"""Task System implementation."""
from typing import Dict, List, Any

class TaskSystem:
    """Task System for task execution and management.
    
    Manages task templates, execution, and context management.
    """
    
    def __init__(self):
        """Initialize the Task System."""
        self.templates = {}  # Task templates
    
    def register_template(self, template: Dict[str, Any]) -> None:
        """Register a task template.
        
        Args:
            template: Template definition
        """
        template_type = template.get("type")
        template_subtype = template.get("subtype")
        
        if template_type and template_subtype:
            key = f"{template_type}:{template_subtype}"
            self.templates[key] = template
    
    def execute_task(self, task_type: str, task_subtype: str, inputs: Dict[str, Any], memory_system=None) -> Dict[str, Any]:
        """Execute a task.
        
        Args:
            task_type: Type of task
            task_subtype: Subtype of task
            inputs: Task inputs
            memory_system: Optional Memory System instance
            
        Returns:
            Task result
        """
        # Check if task type and subtype are registered
        task_key = f"{task_type}:{task_subtype}"
        if task_key not in self.templates:
            return {
                "status": "FAILED",
                "content": f"Unknown task type: {task_key}",
                "notes": {
                    "error": "Task type not registered"
                }
            }
        
        # Handle specific task types
        if task_type == "atomic" and task_subtype == "associative_matching":
            return self._execute_associative_matching(self.templates[task_key], inputs, memory_system)
        
        # Default fallback for unimplemented task types
        return {
            "status": "FAILED",
            "content": "Task execution not implemented for this task type",
            "notes": {
                "task_type": task_type,
                "task_subtype": task_subtype
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
        from task_system.templates.associative_matching import execute_template
        
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
            relevant_files = execute_template(query, memory_system)
            
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
