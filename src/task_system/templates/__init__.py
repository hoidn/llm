"""Task templates for specialized operations."""

from src.task_system.templates.associative_matching import register_template as register_associative_matching
from src.task_system.templates.function_examples import register_function_templates

__all__ = [
    "register_associative_matching",
    "register_function_templates"
]
