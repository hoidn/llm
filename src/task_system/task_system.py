"""Task System implementation."""
from typing import Dict, List, Any

class TaskSystem:
    """Task System for task execution and management.
    
    Manages task templates, execution, and context management.
    """
    
    def __init__(self):
        """Initialize the Task System."""
        self.templates = {}  # Task templates
        
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
        for key, template in self.templates.items():
            if template.get("type") == "atomic":
                # Calculate similarity score
                description = template.get("description", "")
                score = self._calculate_similarity_score(input_text, description)
                
                # Add to matches if score is above threshold
                if score > 0.1:  # Low threshold to ensure we get some matches
                    task_type, subtype = key.split(":", 1)
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
