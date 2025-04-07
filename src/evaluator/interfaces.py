"""Interface definitions for the Evaluator component.

This module defines the interfaces that the Evaluator component implements
and that other components use to interact with the Evaluator.
"""
from typing import Any, Dict, List, Optional, Protocol, Union, runtime_checkable

from task_system.ast_nodes import FunctionCallNode
from task_system.template_utils import Environment


@runtime_checkable
class EvaluatorInterface(Protocol):
    """
    Interface for Evaluator component.
    
    The Evaluator is responsible for evaluating AST nodes, particularly function calls,
    managing variable bindings, and handling execution context.
    
    [Interface:Evaluator:1.0]
    """
    
    def evaluateFunctionCall(self, call_node: FunctionCallNode, env: Environment, template: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Evaluate a function call AST node.
        
        This is the canonical execution path for all function calls.
        
        Args:
            call_node: FunctionCallNode to evaluate
            env: Environment for variable resolution
            
        Returns:
            Result of function execution as a TaskResult dictionary
        """
        ...
    
    def evaluate(self, node: Any, env: Environment) -> Any:
        """
        Evaluate an AST node in the given environment.
        
        Args:
            node: AST node to evaluate
            env: Environment for variable resolution
            
        Returns:
            Evaluation result
        """
        ...


class TemplateLookupInterface(Protocol):
    """
    Interface for template lookup operations.
    
    This interface is implemented by components that can look up templates
    by name or type/subtype.
    """
    
    def find_template(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Find a template by name or type:subtype combination.
        
        Args:
            identifier: Template name or 'type:subtype' string
            
        Returns:
            Template dictionary or None if not found
        """
        ...
    
    def execute_task(self, task_type: str, task_subtype: str, 
                   inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task with the given type, subtype, and inputs.
        
        Args:
            task_type: Type of task
            task_subtype: Subtype of task
            inputs: Task inputs
            
        Returns:
            Task execution result
        """
        ...
