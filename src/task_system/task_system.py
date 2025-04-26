"""
Task System manages and executes task templates.
Implements the contract defined in src/task_system/task_system_IDL.md.
"""

from typing import Any, Dict, List, Optional, Tuple

# Forward declarations for type hinting cycles
# from src.memory.memory_system import MemorySystem
# from src.handler.base_handler import BaseHandler
# from src.system.models import SubtaskRequest, ContextGenerationInput, AssociativeMatchResult


class TaskSystem:
    """
    Manages and executes task templates.
    """

    def __init__(self, memory_system: Optional[Any] = None):  # MemorySystem
        """
        Initializes the Task System.

        Args:
            memory_system: An optional instance of MemorySystem.
        """
        pass

    def set_test_mode(self, enabled: bool) -> None:
        """
        Enables or disables test mode.

        Args:
            enabled: Boolean value to enable/disable test mode.
        """
        pass

    def execute_atomic_template(self, request: Any) -> Dict[str, Any]:  # SubtaskRequest
        """
        Executes a single *atomic* Task System template workflow directly from a SubtaskRequest.

        Args:
            request: A valid SubtaskRequest object.

        Returns:
            The final TaskResult dictionary from the executed atomic template.
        """
        pass

    def find_matching_tasks(
        self, input_text: str, memory_system: Any # MemorySystem
    ) -> List[Dict[str, Any]]:
        """
        Finds matching atomic task templates based on similarity to input text.

        Args:
            input_text: A string describing the desired task.
            memory_system: A valid MemorySystem instance.

        Returns:
            A list of dictionaries, each representing a matching template, sorted by score.
        """
        pass

    def register_template(self, template: Dict[str, Any]) -> None:
        """
        Registers an *atomic* task template definition.

        Args:
            template: A dictionary representing the template.
        """
        pass

    def find_template(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Finds a template definition by its identifier (name or type:subtype).

        Args:
            identifier: The template's unique 'name' or 'type:subtype'.

        Returns:
            The template definition dictionary if found, otherwise None.
        """
        pass

    def generate_context_for_memory_system(
        self, context_input: Any, global_index: Dict[str, str] # ContextGenerationInput
    ) -> Any:  # AssociativeMatchResult
        """
        Generates context for the Memory System, acting as a mediator.

        Args:
            context_input: A valid ContextGenerationInput object.
            global_index: Dictionary mapping file paths to metadata strings.

        Returns:
            An AssociativeMatchResult object.
        """
        pass

    def resolve_file_paths(
        self, template: Dict[str, Any], memory_system: Any, handler: Any # MemorySystem, BaseHandler
    ) -> Tuple[List[str], Optional[str]]:
        """
        Resolves the final list of file paths to be used for context based on template settings.

        Args:
            template: A dictionary representing a fully resolved task template.
            memory_system: A valid MemorySystem instance.
            handler: A valid Handler instance.

        Returns:
            A tuple: (list_of_file_paths, optional_error_message).
        """
        pass
