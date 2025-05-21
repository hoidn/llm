import logging
import os # Added import
import warnings # Added import
from typing import Any, List

# real imports
from src.handler.file_access import FileAccessManager
from src.system.models import ContextGenerationInput, MatchItem # Added MatchItem


class FileContextManager:
    """
    Manages the retrieval of relevant files and creation of context strings.

    Separates file context logic from the main BaseHandler.
    """

    def __init__(
        self,
        memory_system: Any,  # MemorySystem
        file_manager: FileAccessManager,
    ):
        """
        Initializes the FileContextManager.

        Args:
            memory_system: An instance of MemorySystem for context retrieval.
            file_manager: An instance of FileAccessManager for reading files.
        """
        self.memory_system = memory_system
        self.file_manager = file_manager
        logging.info("FileContextManager initialized.")

    def get_match_items_for_paths(self, file_paths: List[str]) -> List[MatchItem]:
        """
        Creates MatchItem objects for a list of file paths, reading their content.
        """
        match_items: List[MatchItem] = []
        for path_str in file_paths:
            content = self.file_manager.read_file(path_str)
            if content and "File too large" not in content: # Check for actual content
                # Ensure the path is absolute, resolved from the FileAccessManager's base_path
                # FileAccessManager._resolve_path already gives a canonical absolute path
                try:
                    abs_path = self.file_manager._resolve_path(path_str)
                except ValueError: # Path outside base path
                    logging.warning(f"[FileContextManager] Path '{path_str}' is outside the FileAccessManager's base path. Skipping for MatchItem creation.")
                    continue
                except Exception as e:
                    logging.warning(f"[FileContextManager] Error resolving path '{path_str}': {e}. Skipping for MatchItem creation.")
                    continue

                item = MatchItem(id=abs_path, content=content, relevance_score=1.0, content_type="file_content", source_path=abs_path)
                match_items.append(item)
            else:
                logging.warning(f"[FileContextManager] Failed to read or file too large: {path_str}. Skipping for MatchItem creation.")
        logging.debug(f"[FileContextManager] Created {len(match_items)} MatchItems from {len(file_paths)} initial paths.")
        return match_items

    def ensure_match_item_content(self, item: MatchItem) -> None:
        """
        Ensures a MatchItem has its content populated, fetching it if necessary.
        Modifies the item in-place.
        """
        if item.content is not None:
            return # Content already exists

        path_to_read = item.id # Default to id as the path
        if item.source_path:
            path_to_read = item.source_path # Prefer source_path if available

        if not path_to_read:
            logging.warning(f"[FileContextManager] Cannot fetch content for MatchItem {item.id}: no path available.")
            return

        logging.debug(f"[FileContextManager] Attempting to fetch content for MatchItem {item.id} from path {path_to_read}.")
        content = self.file_manager.read_file(path_to_read)
        if content and "File too large" not in content: # Check for actual content
            item.content = content
            logging.debug(f"[FileContextManager] Successfully fetched content for MatchItem {item.id}.")
        else:
            logging.warning(f"[FileContextManager] Failed to fetch content for MatchItem {item.id} from {path_to_read}. Error/Status: {content}")
            item.content = None # Ensure it's None if fetch failed

    async def get_relevant_files(self, query: str) -> List[str]:
        """
        Gets relevant file paths based on a query using the MemorySystem.
        DEPRECATED: BaseHandler now calls MemorySystem directly.

        Args:
            query: The query string to find relevant files for.

        Returns:
            A list of relevant file paths.
        """
        warnings.warn(
            "FileContextManager.get_relevant_files is deprecated. BaseHandler now calls MemorySystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        logging.debug(f"[FileContextManager] DEPRECATED get_relevant_files for query: {query!r}")
        if not self.memory_system:
            logging.error("[FileContextManager] No memory_system available – returning empty file list.")
            return []

        try:
            # build proper ContextGenerationInput
            input_model = ContextGenerationInput(query=query)
            result = await self.memory_system.get_relevant_context_for(input_model)

            if not result or not hasattr(result, "matches"):
                logging.warning(f"[FileContextManager] No matches found for DEPRECATED call with query '{query}'.")
                return []

            paths: List[str] = []
            for match in result.matches:
                # handle Pydantic MatchTuple or simple tuple/list
                if hasattr(match, "path"):
                    paths.append(match.path)
                elif isinstance(match, (tuple, list)) and match:
                    paths.append(match[0])

            logging.debug(f"[FileContextManager] Relevant files: {paths}")
            return paths
        except Exception:
            logging.exception(f"[FileContextManager] Error retrieving context for '{query}'")
            return []
        # raise NotImplementedError(
        #     "_get_relevant_files implementation deferred to Phase 2"
        # ) # Original placeholder removed

    def create_file_context(self, file_paths: List[str]) -> str:
        """
        Creates a formatted context string by reading the content of given file paths.

        Args:
            file_paths: A list of file paths to include in the context.

        Returns:
            A single string containing the formatted content of the files.
        DEPRECATED: BaseHandler._create_data_context_string now handles this with MatchItems.
        """
        warnings.warn(
            "FileContextManager.create_file_context is deprecated. BaseHandler._create_data_context_string now handles this.",
            DeprecationWarning,
            stacklevel=2
        )
        logging.debug(f"[FileContextManager] DEPRECATED create_file_context for paths: {file_paths}")

        context_parts: List[str] = []
        for p in file_paths:
            try:
                content = self.file_manager.read_file(p)
                if content:
                    logging.debug(f"[FileContextManager] Read {len(content)} chars from '{p}'")
                    context_parts.append(f"--- File: {p} ---\n{content}\n--- End File: {p} ---")
                else:
                    logging.warning(f"[FileContextManager] No content for '{p}' (skipped).")
            except Exception:
                logging.exception(f"[FileContextManager] Failed to read '{p}'")

        final = "\n\n".join(context_parts)
        logging.debug(f"[FileContextManager] Built file_context (length={len(final)})")
        return final
        # raise NotImplementedError(
        #     "_create_file_context implementation deferred to Phase 2"
        # ) # Original placeholder removed
