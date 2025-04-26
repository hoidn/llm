import logging
from typing import Any, Dict, List, Optional, Tuple

# Forward declarations for type hinting cycles
# from src.memory.memory_system import MemorySystem
# from src.handler.base_handler import BaseHandler
# from src.system.models import SubtaskRequest, ContextGenerationInput, AssociativeMatchResult


class TaskSystem:
    """
    Manages and executes task templates.

    Complies with the contract defined in src/task_system/task_system_IDL.md.
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

        Non-atomic templates will be ignored as per IDL guidance (they are
        handled via S-expressions).

        Args:
            template: A dictionary representing the template.
        """
        name = template.get("name")
        template_type = template.get("type")
        subtype = template.get("subtype")
        params = template.get("params")  # Check if params definition exists

        # --- Start Change ---
        # Enforce that only atomic templates are registered via this method
        if template_type != "atomic":
            logging.warning(
                f"Ignoring registration attempt for non-atomic template '{name}' "
                f"(type: '{template_type}'). Non-atomic tasks are defined and executed via S-expressions."
            )
            return  # Do not register non-atomic templates here

        if not all([name, subtype]): # Type is already checked
             logging.error(
                 f"Atomic template registration failed: Missing 'name' or 'subtype' in {template}"
             )
             # IDL doesn't specify error raising, just logging for now
             return
        # --- End Change ---


        if params is None:
            logging.warning(
                f"Atomic template '{name}' registered without a 'params' attribute. Validation might fail later."
            )
            # Allow registration but warn.

        # TODO: Implement ensure_template_compatibility if needed

        # Check for potential overwrite, log if necessary
        if name in self.templates:
            logging.warning(f"Overwriting existing template registration for name: '{name}'")
        if f"{template_type}:{subtype}" in self.template_index:
             existing_name = self.template_index[f"{template_type}:{subtype}"]
             if existing_name != name:
                 logging.warning(
                     f"Overwriting template index for '{template_type}:{subtype}'. "
                     f"Old name: '{existing_name}', New name: '{name}'"
                 )
             elif self.templates.get(name) != template:
                 logging.info(f"Updating template content for name '{name}' and type:subtype '{template_type}:{subtype}'")


        self.templates[name] = template
        type_subtype_key = f"{template_type}:{subtype}" # type is guaranteed to be 'atomic' here
        self.template_index[type_subtype_key] = name
        logging.info(f"Registered atomic template: '{name}' ({type_subtype_key})")

    def find_template(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Finds an *atomic* template definition by its identifier (name or type:subtype).

        As per the IDL, this method only returns templates of type 'atomic'.

        Args:
            identifier: The template's unique 'name' or 'atomic:subtype'.

        Returns:
            The atomic template definition dictionary if found, otherwise None.
        """
        # --- Start Change: Simplified Logic ---

        # 1. Try direct name lookup (only atomic templates are stored)
        template = self.templates.get(identifier)
        if template:
            # Since only atomic templates are stored by register_template,
            # we can assume template.get("type") == "atomic" here.
            logging.debug(f"Found atomic template by name: '{identifier}'")
            return template

        # 2. Try type:subtype lookup (index only stores atomic type:subtype keys)
        if identifier in self.template_index:
            name = self.template_index[identifier]
            template = self.templates.get(name)
            if template:
                # Again, assume template is atomic if found via index/name
                logging.debug(
                    f"Found atomic template by type:subtype '{identifier}' (name: '{name}')"
                )
                return template
            else:
                # This case indicates an inconsistent state (index points to a non-existent name)
                logging.error(
                    f"Template index inconsistency: Identifier '{identifier}' points to name '{name}', "
                    f"but template not found in main storage."
                )
                return None # Treat as not found

        # --- End Change ---

        logging.debug(f"Atomic template not found for identifier: '{identifier}'")
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

