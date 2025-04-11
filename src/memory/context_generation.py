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
        fresh_context: str = "enabled"
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
        """
        self.template_description = template_description
        self.template_type = template_type
        self.template_subtype = template_subtype
        self.inputs = inputs or {}
        self.context_relevance = context_relevance or {}
        self.inherited_context = inherited_context
        self.previous_outputs = previous_outputs or []
        self.fresh_context = fresh_context
        
        # Default to including all inputs if not specified
        if not self.context_relevance and self.inputs:
            self.context_relevance = {k: True for k in self.inputs.keys()}
    
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
            previous_outputs=input_data.get("previousOutputs", [])
        )


class AssociativeMatchResult:
    """Result structure for context retrieval operations.
    
    This class provides a standardized format for context retrieval results,
    including a context summary and list of file matches.
    """
    
    def __init__(self, context: str, matches: List[Tuple[str, str]]):
        """Initialize an AssociativeMatchResult instance.
        
        Args:
            context: Context summary text
            matches: List of (file_path, relevance) tuples
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
            data: Dictionary with 'context' and 'matches' keys
            
        Returns:
            New AssociativeMatchResult instance
        """
        context = data.get("context", "No context available")
        matches = data.get("matches", [])
        return cls(context=context, matches=matches)
