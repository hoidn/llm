"""Task templates for specialized operations."""

from .associative_matching import register_template as register_associative_matching
from .function_examples import register_function_templates
from .aider_templates import register_aider_templates
from .debug_templates import register_debug_templates

__all__ = [
    "register_associative_matching",
    "register_function_templates",
    "register_aider_templates",
    "register_debug_templates",
]
