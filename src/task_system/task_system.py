import logging
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
        self.memory_system = memory_system
        self.templates: Dict[str, Dict[str, Any]] = {}  # Keyed by template 'name'
        self.template_index: Dict[str, str] = (
            {}
        )  # Keyed by 'type:subtype', value is 'name'
        self._test_mode: bool = False
        self._handler_cache: Dict[str, Any] = (
            {}
        )  # Cache for handler instances (if needed later)
        logging.info("TaskSystem initialized.")

    def set_test_mode(self, enabled: bool) -> None:
        """
        Enables or disables test mode.

        Args:
            enabled: Boolean value to enable/disable test mode.
        """
        self._test_mode = enabled
        logging.info(f"TaskSystem test mode set to: {enabled}")
        # Potentially clear handler cache if mode changes behavior
        self._handler_cache = {}

    def execute_atomic_template(self, request: Any) -> Dict[str, Any]:  # SubtaskRequest
        """
        Executes a single *atomic* Task System template workflow directly from a SubtaskRequest.

        Args:
            request: A valid SubtaskRequest object.

        Returns:
            The final TaskResult dictionary from the executed atomic template.
        """
        # Implementation deferred to Phase 2
        logging.warning(
            "execute_atomic_template called, but implementation is deferred."
        )
        raise NotImplementedError(
            "execute_atomic_template implementation deferred to Phase 2"
        )

    def find_matching_tasks(
        self, input_text: str, memory_system: Any  # MemorySystem
    ) -> List[Dict[str, Any]]:
        """
        Finds matching atomic task templates based on similarity to input text.

        Args:
            input_text: A string describing the desired task.
            memory_system: A valid MemorySystem instance.

        Returns:
            A list of dictionaries, each representing a matching template, sorted by score.
        """
        # Implementation deferred to Phase 2
        logging.warning("find_matching_tasks called, but implementation is deferred.")
        # Placeholder structure for return type hint satisfaction
        return []
        # raise NotImplementedError("find_matching_tasks implementation deferred to Phase 2")

    def register_template(self, template: Dict[str, Any]) -> None:
        """
        Registers an *atomic* task template definition.

        Args:
            template: A dictionary representing the template.
        """
        # Basic validation based on IDL preconditions
        name = template.get("name")
        template_type = template.get("type")
        subtype = template.get("subtype")
        params = template.get("params")  # Check if params definition exists

        if not all([name, template_type, subtype]):
            logging.error(
                f"Template registration failed: Missing 'name', 'type', or 'subtype' in {template}"
            )
            # IDL doesn't specify error raising, just logging for now
            return

        if template_type != "atomic":
            logging.warning(
                f"Registering non-atomic template type '{template_type}' via register_template. This method is intended for atomic tasks."
            )
            # Allow registration but warn, as composite tasks are handled differently.

        if params is None:
            logging.warning(
                f"Template '{name}' registered without a 'params' attribute. Validation might fail later."
            )
            # Allow registration but warn.

        # TODO: Implement ensure_template_compatibility if needed

        self.templates[name] = template
        type_subtype_key = f"{template_type}:{subtype}"
        self.template_index[type_subtype_key] = name
        logging.info(f"Registered template: '{name}' ({type_subtype_key})")

    def find_template(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Finds a template definition by its identifier (name or type:subtype).

        Args:
            identifier: The template's unique 'name' or 'type:subtype'.

        Returns:
            The template definition dictionary if found, otherwise None.
        """
        # Try direct name lookup first
        if identifier in self.templates:
            template = self.templates[identifier]
            # Ensure it's atomic type as per IDL behavior description
            if template.get("type") == "atomic":
                logging.debug(f"Found template by name: '{identifier}'")
                return template
            else:
                logging.debug(
                    f"Template found by name '{identifier}' but is not atomic type."
                )
                # If we have a non-atomic template with this name, we need to check
                # if there's an atomic template with the same name in the index
                for key, name in self.template_index.items():
                    if name == identifier and key.startswith("atomic:"):
                        template = self.templates[name]
                        if template.get("type") == "atomic":
                            logging.debug(f"Found atomic template '{name}' via index after name collision")
                            return template

        # Try type:subtype lookup
        if identifier in self.template_index:
            name = self.template_index[identifier]
            if name in self.templates:
                template = self.templates[name]
                # Double check type matches (should always if index is correct)
                if template.get("type") == "atomic":
                    logging.debug(
                        f"Found template by type:subtype '{identifier}' (name: '{name}')"
                    )
                    return template

        logging.debug(f"Template not found for identifier: '{identifier}'")
        return None

    def generate_context_for_memory_system(
        self, context_input: Any, global_index: Dict[str, str]  # ContextGenerationInput
    ) -> Any:  # AssociativeMatchResult
        """
        Generates context for the Memory System, acting as a mediator.

        Args:
            context_input: A valid ContextGenerationInput object.
            global_index: Dictionary mapping file paths to metadata strings.

        Returns:
            An AssociativeMatchResult object.
        """
        # Implementation deferred to Phase 2
        logging.warning(
            "generate_context_for_memory_system called, but implementation is deferred."
        )
        raise NotImplementedError(
            "generate_context_for_memory_system implementation deferred to Phase 2"
        )

    def resolve_file_paths(
        self,
        template: Dict[str, Any],
        memory_system: Any,
        handler: Any,  # MemorySystem, BaseHandler
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
        # Implementation deferred to Phase 2
        logging.warning("resolve_file_paths called, but implementation is deferred.")
        # Placeholder structure for return type hint satisfaction
        return ([], "Implementation deferred")
        # raise NotImplementedError("resolve_file_paths implementation deferred to Phase 2")
