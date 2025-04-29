import logging
from typing import Any, Dict, List, Optional, Tuple

class TemplateRegistry:
    """
    Manages the registration, storage, and lookup of atomic task templates.
    """

    def __init__(self):
        """Initializes the TemplateRegistry."""
        self.templates: Dict[str, Dict[str, Any]] = {}  # Key: template name
        self.template_index: Dict[str, str] = {}  # Key: type:subtype, Value: name
        logging.info("TemplateRegistry initialized.")

    def register(self, template: Dict[str, Any]) -> bool:
        """
        Validates and registers an atomic task template definition.

        Args:
            template: A dictionary representing the template.

        Returns:
            True if registration was successful, False otherwise.
        """
        name = template.get("name")
        template_type = template.get("type")
        params = template.get("params")
        subtype = template.get("subtype")

        # --- Validation Logic (Moved from TaskSystem) ---
        if template_type != "atomic":
            logging.error(
                f"Registration failed: Template '{name}' is not atomic (type: '{template_type}'). Only atomic templates can be registered."
            )
            return False # Reject non-atomic

        if params is None:
             logging.error(
                 f"Registration failed: Atomic template '{name}' must have a 'params' definition."
             )
             return False # Reject missing params

        if not isinstance(params, dict):
            logging.error(
                f"Registration failed: Atomic template '{name}' has invalid 'params' definition (must be a dictionary)."
            )
            return False # Reject invalid params type

        if not all([name, subtype]):
             logging.error(
                 f"Registration failed: Atomic template missing 'name' or 'subtype'."
             )
             return False # Reject missing name/subtype
        # --- End Validation ---

        # Description warning (optional, kept for consistency)
        if not template.get("description"):
            logging.warning(
                f"Atomic template '{name}' registered without a 'description'."
            )

        # Handle index/template overwrites (Moved from TaskSystem)
        if name in self.templates:
            logging.warning(f"Overwriting existing template registration for name: '{name}'")

        type_subtype_key = f"{template_type}:{subtype}"

        existing_key_for_name = None
        for key, mapped_name in self.template_index.items():
            if mapped_name == name:
                existing_key_for_name = key
                break

        if existing_key_for_name and existing_key_for_name != type_subtype_key:
            logging.warning(
                f"Template name '{name}' is being re-registered with a new type:subtype "
                f"('{type_subtype_key}', was '{existing_key_for_name}'). Removing old index entry."
            )
            if existing_key_for_name in self.template_index:
                 del self.template_index[existing_key_for_name]
        elif type_subtype_key in self.template_index:
             existing_name = self.template_index[type_subtype_key]
             if existing_name != name:
                 logging.warning(
                     f"Overwriting template index for '{type_subtype_key}'. "
                     f"Old name: '{existing_name}', New name: '{name}'"
                 )
             elif self.templates.get(name) != template:
                 logging.info(f"Updating template content for name '{name}' and type:subtype '{type_subtype_key}'")

        # Store the template
        self.templates[name] = template
        self.template_index[type_subtype_key] = name
        logging.info(f"Registered atomic template: '{name}' ({type_subtype_key})")
        return True # Indicate success

    def find(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Finds an atomic template definition by its identifier (name or type:subtype).

        Args:
            identifier: The template's unique 'name' or 'atomic:subtype'.

        Returns:
            The atomic template definition dictionary if found, otherwise None.
        """
        # Direct name lookup
        template = self.templates.get(identifier)
        if template:
            logging.debug(f"Registry found template by name: '{identifier}'")
            return template

        # Type:subtype lookup (only atomic:subtype keys are stored)
        if identifier in self.template_index:
            name = self.template_index[identifier]
            template = self.templates.get(name)
            if template:
                logging.debug(
                    f"Registry found template by type:subtype '{identifier}' (name: '{name}')"
                )
                return template
            else:
                # Should not happen if register logic is correct, but handle defensively
                logging.error(
                    f"Registry index inconsistency: Identifier '{identifier}' points to name '{name}', "
                    f"but template not found."
                )
                return None

        logging.debug(f"Registry did not find template for identifier: '{identifier}'")
        return None

    def get_all_atomic_templates(self) -> List[Dict[str, Any]]:
        """
        Returns a list of all registered atomic template definitions.
        Useful for operations like matching that need to iterate over templates.
        """
        # Assumes self.templates only contains atomic ones due to register() validation
        return list(self.templates.values())
