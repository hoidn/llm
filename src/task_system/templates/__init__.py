"""Task templates for specialized operations."""

"""Task templates for specialized operations."""

from task_system.templates.associative_matching import register_template as register_associative_matching
from task_system.templates.function_examples import register_function_templates
from .aider_templates import register_aider_templates # Add this

__all__ = [
    "register_associative_matching",
    "register_function_templates",
    "register_aider_templates", # Add this
]
