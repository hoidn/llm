"""
Processor for S-expression primitives.
This module will contain the PrimitiveProcessor class, which centralizes
the application logic for all built-in primitives in the S-expression language.
"""
import logging
from typing import Any, List, TYPE_CHECKING

from src.sexp_evaluator.sexp_environment import SexpEnvironment
# SexpNode is an alias for Any, representing a parsed S-expression node.
SexpNode = Any 

if TYPE_CHECKING:
    from .sexp_evaluator import SexpEvaluator # Forward reference for type hinting

logger = logging.getLogger(__name__)

class PrimitiveProcessor:
    """
    Applies primitives for the SexpEvaluator.
    Each method implements a specific primitive and is responsible for
    evaluating its arguments (as needed by the primitive's semantics)
    and performing the primitive's action.
    """
    def __init__(self, evaluator_instance: 'SexpEvaluator'):
        """
        Initializes the PrimitiveProcessor.

        Args:
            evaluator_instance: An instance of the SexpEvaluator to be used for
                                evaluation of arguments if the primitive requires it.
        """
        self.evaluator = evaluator_instance
        logger.debug("PrimitiveProcessor initialized.")

    def apply_list_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Applies the 'list' primitive: (list expr...)"""
        logger.debug(f"PrimitiveProcessor.apply_list_primitive called for: {original_expr_str}")
        # Logic will be moved from SexpEvaluator._apply_list_primitive
        raise NotImplementedError("apply_list_primitive logic not yet migrated to PrimitiveProcessor.")

    def apply_get_context_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Applies the 'get_context' primitive: (get_context (key val_expr)...)"""
        logger.debug(f"PrimitiveProcessor.apply_get_context_primitive called for: {original_expr_str}")
        # Logic will be moved from SexpEvaluator._apply_get_context_primitive
        raise NotImplementedError("apply_get_context_primitive logic not yet migrated to PrimitiveProcessor.")

    def apply_get_field_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Applies the 'get-field' primitive: (get-field obj_expr field_expr)"""
        logger.debug(f"PrimitiveProcessor.apply_get_field_primitive called for: {original_expr_str}")
        # Logic will be moved from SexpEvaluator._apply_get_field_primitive
        raise NotImplementedError("apply_get_field_primitive logic not yet migrated to PrimitiveProcessor.")

    def apply_string_equal_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Applies the 'string=?' primitive: (string=? str1_expr str2_expr)"""
        logger.debug(f"PrimitiveProcessor.apply_string_equal_primitive called for: {original_expr_str}")
        # Logic will be moved from SexpEvaluator._apply_string_equal_primitive
        raise NotImplementedError("apply_string_equal_primitive logic not yet migrated to PrimitiveProcessor.")

    def apply_log_message_primitive(self, arg_exprs: List[SexpNode], env: SexpEnvironment, original_expr_str: str) -> Any:
        """Applies the 'log-message' primitive: (log-message expr...)"""
        logger.debug(f"PrimitiveProcessor.apply_log_message_primitive called for: {original_expr_str}")
        # Logic will be moved from SexpEvaluator._apply_log_message_primitive
        raise NotImplementedError("apply_log_message_primitive logic not yet migrated to PrimitiveProcessor.")
