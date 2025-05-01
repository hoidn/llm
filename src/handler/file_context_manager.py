import logging
from typing import Any, List

# real imports
from src.handler.file_access import FileAccessManager
from src.system.models import ContextGenerationInput


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

    def get_relevant_files(self, query: str) -> List[str]:
        """
        Gets relevant file paths based on a query using the MemorySystem.

        Args:
            query: The query string to find relevant files for.

        Returns:
            A list of relevant file paths.
        """
        logging.debug(f"[FileContextManager] get_relevant_files for query: {query!r}")
        if not self.memory_system:
            logging.error("[FileContextManager] No memory_system available – returning empty file list.")
            return []

        try:
            # build proper ContextGenerationInput
            input_model = ContextGenerationInput(query=query)
            result = self.memory_system.get_relevant_context_for(input_model)

            if not result or not hasattr(result, "matches"):
                logging.warning(f"[FileContextManager] No matches found for '{query}'.")
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
        """
        logging.debug(f"[FileContextManager] create_file_context for paths: {file_paths}")

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
