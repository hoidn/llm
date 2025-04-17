"""Context generation input structures for Memory System."""
from typing import Dict, List, Any, Optional, Union, Set, Tuple


class ContextGenerationInput:
    """Input structure for template-aware context generation.
    
    This class provides a standardized interface for passing template and input
    information to the Memory System for context retrieval.
    """
    
    def __init__(
        self,
        template_description: str = "",
        template_type: str = "",
        template_subtype: str = "",
        inputs: Optional[Dict[str, Any]] = None,
        context_relevance: Optional[Dict[str, bool]] = None,
        inherited_context: str = "",
        previous_outputs: Optional[List[str]] = None,
        fresh_context: str = "enabled",
        taskText: str = "",  # For backward compatibility
        history_context: Optional[str] = None # <-- New Parameter
    ):
        """Initialize a ContextGenerationInput instance.
        Args:
            template_description: Main template description
            template_type: Template type (e.g., 'atomic')
            template_subtype: Template subtype (e.g., 'associative_matching')
            inputs: Dictionary of input parameters
            context_relevance: Dictionary mapping input names to boolean include/exclude
            inherited_context: Context inherited from parent tasks
            previous_outputs: Previous task outputs for context accumulation
            fresh_context: Whether to generate fresh context or use inherited only
            taskText: Legacy parameter for backward compatibility
            history_context: Optional string containing recent conversation history.
        """
        self.template_description = template_description or taskText
        self.template_type = template_type
        self.template_subtype = template_subtype
        self.inputs = inputs or {}
        self.context_relevance = context_relevance or {}
        self.inherited_context = inherited_context
        self.previous_outputs = previous_outputs or []
        self.fresh_context = fresh_context
        self.taskText = taskText or template_description  # For backward compatibility
        self.history_context = history_context # <-- New Assignment

        # Default to including all inputs if not specified
        if not self.context_relevance and self.inputs:
            self.context_relevance = {k: True for k in self.inputs.keys()}
            
    def get(self, key, default=None):
        """Dictionary-like access for backward compatibility.
        
        Args:
            key: Key to look up
            default: Default value if key not found
            
        Returns:
            Value for key or default
        """
        if key == "taskText":
            return self.taskText or default
        elif key == "inheritedContext":
            return self.inherited_context or default
        elif key == "previousOutputs":
            return self.previous_outputs or default
        elif key == "history_context":
            return self.history_context or default
        elif hasattr(self, key):
            return getattr(self, key) or default
        return default
        
    def __getitem__(self, key):
        """Dictionary-like access for backward compatibility.
        
        Args:
            key: Key to look up
            
        Returns:
            Value for key
            
        Raises:
            KeyError: If key not found
        """
        result = self.get(key)
        if result is None:
            raise KeyError(key)
        return result
    
    @classmethod
    def from_legacy_format(cls, input_data: Dict[str, Any]) -> 'ContextGenerationInput':
        """Create an instance from legacy format with taskText.
        
        Args:
            input_data: Dictionary with taskText and other legacy fields
            
        Returns:
            New ContextGenerationInput instance
        """
        return cls(
            template_description=input_data.get("taskText", ""),
            inherited_context=input_data.get("inheritedContext", ""),
            previous_outputs=input_data.get("previousOutputs", []),
            history_context=input_data.get("history_context", None) # <-- Add history
        )


class AssociativeMatchResult:
    """Result structure for context retrieval operations.
    
    This class provides a standardized format for context retrieval results,
    including a context summary and list of file matches with relevance and score.
    """
    
    def __init__(self, context: str, matches: List[Tuple[str, str, Optional[float]]]):
        """Initialize an AssociativeMatchResult instance.
        
        Args:
            context: Context summary text
            matches: List of (file_path, relevance, score) tuples. Score is optional float.
        """
        self.context = context
        self.matches = matches
    
    def __repr__(self) -> str:
        """Get string representation of the result."""
        return f"AssociativeMatchResult(context='{self.context}', matches={len(self.matches)} files)"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssociativeMatchResult':
        """Create an instance from dictionary format.
        
        Args:
            data: Dictionary with 'context' and 'matches' keys.
                  'matches' should be a list of [path, relevance, score] lists/tuples.
            
        Returns:
            New AssociativeMatchResult instance
        """
        context = data.get("context", "No context available")
        matches_data = data.get("matches", [])
        # Convert list-based matches to the expected tuple format
        matches_tuples = []
        for match_item in matches_data:
            if isinstance(match_item, (list, tuple)) and len(match_item) >= 2:
                path = match_item[0]
                relevance = match_item[1]
                score = float(match_item[2]) if len(match_item) > 2 and match_item[2] is not None else None
                matches_tuples.append((path, relevance, score))
            elif isinstance(match_item, dict):
                # Handle dictionary format
                path = match_item.get("path", "")
                relevance = match_item.get("relevance", "")
                score = match_item.get("score")
                if score is not None:
                    try:
                        score = float(score)
                    except (ValueError, TypeError):
                        score = None
                matches_tuples.append((path, relevance, score))
            else:
                # Skip invalid items
                continue
                
        return cls(context=context, matches=matches_tuples)
