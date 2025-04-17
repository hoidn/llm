"""AST node implementations for Task System.

This module contains concrete implementations of AST nodes used in task
template processing, particularly for function call evaluation.
"""
from typing import Any, Dict, List, Optional, Union

class ArgumentNode:
    """
    Represents an argument to a function call.
    
    Implements the ArgumentNode interface from types.md.
    
    Attributes:
        type: Node type identifier, always "argument"
        value: The argument value, can be a literal value or variable reference
        name: Optional name for named arguments, None for positional arguments
    """
    
    def __init__(self, value: Any, name: Optional[str] = None):
        """
        Initialize an ArgumentNode.
        
        Args:
            value: The argument value, can be a literal or variable reference
            name: Optional argument name for named arguments
        """
        self.type = "argument"
        self.value = value
        self.name = name
    
    def __repr__(self) -> str:
        """Return a string representation of the ArgumentNode."""
        if self.name:
            return f"ArgumentNode(name='{self.name}', value={repr(self.value)})"
        return f"ArgumentNode(value={repr(self.value)})"
    
    def __str__(self) -> str:
        """Return a human-readable string representation."""
        if self.name:
            return f"{self.name}={self.value}"
        return str(self.value)
    
    def is_named(self) -> bool:
        """Check if this is a named argument."""
        return self.name is not None
    
    def is_positional(self) -> bool:
        """Check if this is a positional argument."""
        return self.name is None


class FunctionCallNode:
    """
    Represents a function call expression.
    
    Implements the FunctionCallNode interface from types.md.
    
    Attributes:
        type: Node type identifier, always "call"
        template_name: Name of the template/function to call
        arguments: List of ArgumentNode objects representing call arguments
    """
    
    def __init__(self, template_name: str, arguments: List[ArgumentNode]):
        """
        Initialize a FunctionCallNode.
        
        Args:
            template_name: Name of the template/function to call
            arguments: List of ArgumentNode objects
        """
        self.type = "call"
        self.template_name = template_name
        self.arguments = arguments
    
    def __repr__(self) -> str:
        """Return a string representation of the FunctionCallNode."""
        args_repr = ", ".join(repr(arg) for arg in self.arguments)
        return f"FunctionCallNode(template_name='{self.template_name}', arguments=[{args_repr}])"
    
    def __str__(self) -> str:
        """Return a human-readable string representation."""
        args_str = ", ".join(str(arg) for arg in self.arguments)
        return f"{self.template_name}({args_str})"
    
    def get_positional_arguments(self) -> List[ArgumentNode]:
        """Get all positional arguments."""
        return [arg for arg in self.arguments if arg.is_positional()]
    
    def get_named_arguments(self) -> Dict[str, ArgumentNode]:
        """Get all named arguments as a dictionary."""
        result = {}
        for arg in self.arguments:
            if arg.is_named() and arg.name is not None:
                result[arg.name] = arg
        return result
    
    def has_argument(self, name: str) -> bool:
        """Check if a named argument exists."""
        return any(arg.name == name for arg in self.arguments if arg.is_named())
    
    def get_argument(self, name: str) -> Optional[ArgumentNode]:
        """Get a named argument by name, or None if not found."""
        for arg in self.arguments:
            if arg.is_named() and arg.name == name:
                return arg
        return None


class SubtaskRequest:
    """
    Represents a request to execute a subtask programmatically.

    Attributes:
        type: The primary type of the task (e.g., "atomic", "composite").
        subtype: The specific subtype of the task (e.g., "code_generation", "file_edit").
        inputs: A dictionary of input parameters for the task.
        file_paths: Optional list of explicit file paths to use as context.
    """
    def __init__(self,
                 type: str,
                 subtype: Optional[str],
                 inputs: Optional[Dict[str, Any]] = None,
                 file_paths: Optional[List[str]] = None,
                 history_context: Optional[str] = None):
        """
        Initialize a SubtaskRequest.

        Args:
            type: The task type.
            subtype: The task subtype.
            inputs: Input parameters dictionary.
            file_paths: Explicit file paths for context.
            history_context: Optional conversation history for context generation.
        """
        self.type = type
        self.subtype = subtype
        self.inputs = inputs or {}
        self.file_paths = file_paths or []
        self.history_context = history_context

    def __repr__(self) -> str:
        """Return a string representation of the SubtaskRequest."""
        return (f"SubtaskRequest(type='{self.type}', subtype='{self.subtype}', "
                f"inputs={repr(self.inputs)}, file_paths={repr(self.file_paths)})")
