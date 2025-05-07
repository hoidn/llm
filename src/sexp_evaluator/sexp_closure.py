"""
Defines the Closure class for representing lexically-scoped anonymous functions
created by the 'lambda' special form in the S-expression evaluator.
"""
import logging
from typing import List, Any # SexpNode is Any, params_ast is List[Symbol], body_ast is List[SexpNode]

from sexpdata import Symbol
from .sexp_environment import SexpEnvironment

logger = logging.getLogger(__name__)

class Closure:
    def __init__(self, params_ast: List[Symbol], body_ast: List[Any], definition_env: SexpEnvironment):
        """
        Represents a lexically-scoped anonymous function created by 'lambda'.

        Args:
            params_ast: A list of Symbol objects representing the function's formal parameters.
            body_ast: A list of AST nodes representing the function's body expressions.
                        Each element in this list is a complete S-expression AST node.
            definition_env: The SexpEnvironment captured at the time of lambda definition.
                            This environment is the parent for the function's call frame.
        """
        # Validation that params_ast contains only Symbol objects is done
        # in SexpEvaluator._eval before Closure instantiation.
        
        self.params_ast: List[Symbol] = params_ast # List of Symbol objects
        self.body_ast: List[Any] = body_ast     # List of SexpNode (body expressions)
        self.definition_env: SexpEnvironment = definition_env # Captured environment
        
        # For debugging purposes
        param_names_str = ", ".join([p.value() for p in self.params_ast])
        logger.debug(f"Closure created: params=({param_names_str}), num_body_exprs={len(self.body_ast)}, def_env_id={id(self.definition_env)}")

    def __repr__(self):
        param_names = [p.value() for p in self.params_ast]
        return f"<Closure params=({', '.join(param_names)}) body_exprs#={len(self.body_ast)} def_env_id={id(self.definition_env)}>"
