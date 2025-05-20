import logging
from typing import Any, Dict, List, Optional, Tuple

# Need imports used by the original method's logic
# Import the actual models needed for runtime use
from src.system.models import ContextGenerationInput, MatchItem, AssociativeMatchResult # Changed MatchTuple to MatchItem

# Types needed only for type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.memory.memory_system import MemorySystem
    from src.handler.base_handler import BaseHandler


async def resolve_paths_from_template(
    template: Dict[str, Any],
    memory_system: Optional['MemorySystem'],
    handler: Optional['BaseHandler'],
) -> Tuple[List[str], Optional[str]]:
    """
    Resolves the final list of file paths based on template settings.

    This function encapsulates the logic previously in TaskSystem.resolve_file_paths.

    Args:
        template: A dictionary representing a fully resolved task template.
        memory_system: A valid MemorySystem instance (required for description/context types).
        handler: A valid Handler instance (required for command type).

    Returns:
        A tuple: (list_of_file_paths, optional_error_message).
    """
    logging.debug(f"Resolving file paths for template: {template.get('name', 'unnamed')}")

    # Check for top-level literal paths first (legacy?)
    if "file_paths" in template and isinstance(template["file_paths"], list):
        logging.debug("Using literal file_paths from template top-level.")
        return template["file_paths"], None

    source_info = template.get("file_paths_source")
    if not source_info or not isinstance(source_info, dict):
        logging.debug("No file_paths_source found or invalid format, returning empty list.")
        return [], None # No source specified

    source_type = source_info.get("type", "literal") # Default to literal if type missing

    if source_type == "literal":
        paths = source_info.get("path", []) # Use 'path' key inside source_info
        if isinstance(paths, list):
             logging.debug(f"Using literal paths from file_paths_source: {paths}")
             return paths, None
        else:
             msg = "Invalid format for literal file_paths_source: 'path' key must be a list."
             logging.error(msg)
             return [], msg

    elif source_type == "command":
        if not handler:
            return [], "Handler instance is required for file_paths_source type 'command'"
        command = source_info.get("command")
        if not command:
            return [], "Missing command in file_paths_source type 'command'"
        logging.debug(f"Executing command for file paths: {command}")
        try:
            # Assuming handler has a method like execute_file_path_command
            paths = handler.execute_file_path_command(command)
            logging.debug(f"Command returned paths: {paths}")
            return paths, None
        except Exception as e:
            msg = f"Error executing command for file paths: {e}"
            logging.exception(msg) # Use logging.exception to include traceback
            return [], msg

    elif source_type == "description":
        if not memory_system:
            return [], "MemorySystem instance is required for file_paths_source type 'description'"
        # Use specific description if provided, else fall back to template description
        description = source_info.get("description") or template.get("description")
        if not description:
            return [], "Missing description for file_paths_source type 'description'"
        logging.debug(f"Getting context by description: {description}")
        try:
            # Use the primary context retrieval method with description as query
            context_input = ContextGenerationInput(query=description)
            result: AssociativeMatchResult = await memory_system.get_relevant_context_for(context_input) # type: ignore
            if result.error:
                return [], f"Error getting context by description: {result.error}"
            # Ensure matches are MatchItem instances and extract path
            paths = []
            if result.matches:
                for item in result.matches:
                    if isinstance(item, MatchItem):
                        path_to_add = item.source_path if item.source_path else item.id
                        if path_to_add:
                            paths.append(path_to_add)
            logging.debug(f"Context by description returned paths: {paths}")
            return paths, None
        except Exception as e:
            msg = f"Error getting context by description: {e}"
            logging.exception(msg) # Use logging.exception
            return [], msg

    elif source_type == "context_description":
         if not memory_system:
             return [], "MemorySystem instance is required for file_paths_source type 'context_description'"
         context_query = source_info.get("context_query")
         if not context_query:
             return [], "Missing context_query for file_paths_source type 'context_description'"
         logging.debug(f"Getting context by context_query: {context_query}")
         try:
             # Use the primary context retrieval method
             context_input = ContextGenerationInput(query=context_query)
             result: AssociativeMatchResult = await memory_system.get_relevant_context_for(context_input) # type: ignore
             if result.error:
                 return [], f"Error getting context by context_query: {result.error}"
             # Ensure matches are MatchItem instances and extract path
             paths = []
             if result.matches:
                 for item in result.matches:
                     if isinstance(item, MatchItem):
                         path_to_add = item.source_path if item.source_path else item.id
                         if path_to_add:
                             paths.append(path_to_add)
             logging.debug(f"Context by context_query returned paths: {paths}")
             return paths, None
         except Exception as e:
             msg = f"Error getting context by context_query: {e}"
             logging.exception(msg) # Use logging.exception
             return [], msg

    else:
        msg = f"Unknown file_paths_source type: {source_type}"
        logging.error(msg)
        return [], msg
