"""Context generation input structures for Memory System."""
from typing import Dict, List, Any, Optional, Union, Set, Tuple
from pydantic import BaseModel, Field


class ContextGenerationInput(BaseModel):
    """Input structure for template-aware context generation.
    
    This class provides a standardized interface for passing template and input
    information to the Memory System for context retrieval.
    """
    template_description: str = ""
    template_type: str = ""
    template_subtype: str = ""
    inputs: Dict[str, Any] = Field(default_factory=dict)
    context_relevance: Dict[str, bool] = Field(default_factory=dict)
    inherited_context: str = ""
    previous_outputs: List[str] = Field(default_factory=list)
    fresh_context: str = "enabled"
    taskText: str = ""  # For backward compatibility
    history_context: Optional[str] = None
    
    def __init__(self, **data):
        """Initialize with additional logic for backward compatibility."""
        super().__init__(**data)
        # Set template_description from taskText if not provided
        if not self.template_description and self.taskText:
            self.template_description = self.taskText
        # Set taskText from template_description if not provided
        if not self.taskText and self.template_description:
            self.taskText = self.template_description
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
            history_context=input_data.get("history_context", None)
        )


class MatchTuple(BaseModel):
    """Represents a file match with relevance and optional score."""
    path: str
    relevance: str
    score: Optional[float] = None


class AssociativeMatchResult(BaseModel):
    """Result structure for context retrieval operations.
    
    This class provides a standardized format for context retrieval results,
    including a context summary and list of file matches with relevance and score.
    """
    context: str
    matches: List[Union[MatchTuple, Tuple[str, str], Tuple[str, str, Optional[float]]]] = Field(default_factory=list)
    
    def __init__(self, **data):
        """Initialize with conversion of tuple matches to MatchTuple if needed."""
        # Handle the case where matches are provided as tuples
        if "matches" in data and isinstance(data["matches"], list):
            normalized_matches = []
            for match in data["matches"]:
                if isinstance(match, tuple) or isinstance(match, list):
                    if len(match) >= 2:
                        match_dict = {
                            "path": match[0],
                            "relevance": match[1]
                        }
                        if len(match) > 2 and match[2] is not None:
                            match_dict["score"] = match[2]
                        normalized_matches.append(match_dict)
                else:
                    normalized_matches.append(match)
            data["matches"] = normalized_matches
        super().__init__(**data)
    
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
        # Convert list-based matches to the expected format
        matches_list = []
        for match_item in matches_data:
            if isinstance(match_item, (list, tuple)) and len(match_item) >= 2:
                path = match_item[0]
                relevance = match_item[1]
                score = float(match_item[2]) if len(match_item) > 2 and match_item[2] is not None else None
                matches_list.append(MatchTuple(path=path, relevance=relevance, score=score))
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
                matches_list.append(MatchTuple(path=path, relevance=relevance, score=score))
            else:
                # Skip invalid items
                continue
                
        return cls(context=context, matches=matches_list)
