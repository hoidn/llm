"""
Memory System manages file metadata and context retrieval.
Implements the contract defined in src/memory/memory_system_IDL.md.
"""

import os
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

# Import necessary models
from src.system.models import ContextGenerationInput, AssociativeMatchResult, MatchTuple, SubtaskRequest, ContextManagement
from src.handler.file_access import FileAccessManager

# Import the indexer
try:
    from src.memory.indexers.git_repository_indexer import GitRepositoryIndexer
except ImportError:
    logging.error("GitRepositoryIndexer could not be imported. Indexing features will be unavailable.")
    GitRepositoryIndexer = None # type: ignore


# Default sharding config (can be refined)
DEFAULT_SHARDING_CONFIG = {
    "sharding_enabled": False,
    "token_size_per_shard": 10000,
    "max_shards": 10,
    "token_estimation_ratio": 0.75,  # Placeholder ratio
    "max_parallel_shards": 3,
}

# Forward declarations for type hinting cycles - Use actual imports now
from src.handler.base_handler import BaseHandler
from src.task_system.task_system import TaskSystem


class MemorySystem:
    """
    Manages file metadata and context retrieval.
    """

    def __init__(
        self,
        handler: BaseHandler, # Remove Optional
        task_system: TaskSystem, # Remove Optional
        file_access_manager: FileAccessManager, # Add required arg
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initializes the Memory System.

        Args:
            handler: BaseHandler instance.
            task_system: TaskSystem instance.
            file_access_manager: FileAccessManager instance.
            config: Optional dictionary for sharding parameters and other settings.
        """
        # Add basic type checks for required dependencies
        if not isinstance(handler, BaseHandler): # Replace BaseHandler with actual class if possible
             raise TypeError("MemorySystem requires a valid BaseHandler instance.")
        if not isinstance(task_system, TaskSystem): # Replace TaskSystem with actual class if possible
             raise TypeError("MemorySystem requires a valid TaskSystem instance.")
        if not isinstance(file_access_manager, FileAccessManager):
             raise TypeError("MemorySystem requires a valid FileAccessManager instance.")

        self.handler = handler
        self.task_system = task_system
        self.file_access_manager = file_access_manager
        self.global_index: Dict[str, str] = {}
        self._sharded_index: List[Dict[str, str]] = []
        self._config: Dict[str, Any] = DEFAULT_SHARDING_CONFIG.copy()
        if config:
            self._config.update(config)
        logging.info(
            f"MemorySystem initialized. Sharding enabled: {self._config.get('sharding_enabled', False)}"
        )

    def get_global_index(self) -> Dict[str, str]:
        """
        Retrieves the current global file metadata index.

        Returns:
            The dictionary mapping absolute file paths to metadata strings.
        """
        return (
            self.global_index.copy()
        )  # Return a copy to prevent external modification

    def update_global_index(self, index: Dict[str, str]) -> None:
        """
        Updates the global file metadata index with new entries.

        Args:
            index: A dictionary mapping file paths to metadata strings. Paths MUST be absolute.

        Raises:
            ValueError: If a non-absolute path is provided.
        """
        invalid_paths = []
        for path in index.keys():
             # Normalize path for consistent checks
            norm_path = os.path.normpath(path)
            if not os.path.isabs(norm_path):
                invalid_paths.append(path)

        if invalid_paths:
            raise ValueError(f"Non-absolute paths provided in index: {invalid_paths}")

        # Store with normalized absolute paths
        normalized_index = {os.path.abspath(p): meta for p, meta in index.items()}

        # --- START ADDITION ---
        logging.debug(f"MemorySystem: Adding/updating keys in global index: {list(normalized_index.keys())}")
        # --- END ADDITION ---

        self.global_index.update(normalized_index)
        logging.debug(
            f"Global index updated with {len(normalized_index)} entries. Total size: {len(self.global_index)}"
        )

        if self._config.get("sharding_enabled", False):
            self._recalculate_shards()

    def enable_sharding(self, enabled: bool) -> None:
        """
        Enables or disables the use of sharded context retrieval.

        Args:
            enabled: Boolean value to enable/disable sharding.
        """
        self._config["sharding_enabled"] = enabled
        logging.info(f"Sharding explicitly set to: {enabled}")
        if enabled:
            self._recalculate_shards()
        else:
            self._sharded_index = []  # Clear shards if disabled

    def configure_sharding(
        self,
        token_size_per_shard: Optional[int] = None,
        max_shards: Optional[int] = None,
        token_estimation_ratio: Optional[float] = None,
        max_parallel_shards: Optional[int] = None,
    ) -> None:
        """
        Configures parameters for sharded context retrieval.

        Args:
            token_size_per_shard: Optional target token size per shard.
            max_shards: Optional maximum number of shards to generate.
            token_estimation_ratio: Optional ratio for estimating token count from text length.
            max_parallel_shards: Optional maximum number of shards to process in parallel.
        """
        if token_size_per_shard is not None:
            self._config["token_size_per_shard"] = token_size_per_shard
        if max_shards is not None:
            self._config["max_shards"] = max_shards
        if token_estimation_ratio is not None:
            self._config["token_estimation_ratio"] = token_estimation_ratio
        if max_parallel_shards is not None:
            self._config["max_parallel_shards"] = max_parallel_shards

        logging.info(f"Sharding configuration updated: {self._config}")

        if self._config.get("sharding_enabled", False):
            self._recalculate_shards()

    def get_relevant_context_with_description(
        self, query: str, context_description: str
    ) -> Any:  # AssociativeMatchResult
        """
        Retrieves relevant context using a specific description string for matching.

        Args:
            query: The main task query string.
            context_description: The string to be used for associative matching.

        Returns:
            An AssociativeMatchResult object.
        """
        # Implementation deferred to Phase 2
        logging.debug(
            "get_relevant_context_with_description called. Constructing input for get_relevant_context_for."
        )
        # --- Start Phase 2, Set A: Behavior Structure ---
        # 1. Construct a simple ContextGenerationInput-like dictionary using context_description.
        #    - e.g., {'taskText': context_description} or a minimal ContextGenerationInput object.
        # 2. Call self.get_relevant_context_for with the constructed input.
        # 3. Return the result from get_relevant_context_for.
        # --- End Phase 2, Set A ---
        # Create ContextGenerationInput using context_description as the query
        input_data = ContextGenerationInput(query=context_description)
        # Call the main method
        return self.get_relevant_context_for(input_data)

    def get_relevant_context_for(
        self, input_data: Any # Union[Dict[str, Any], ContextGenerationInput]
    ) -> AssociativeMatchResult:
        """
        Retrieves relevant context for a task, orchestrating content/metadata retrieval and LLM analysis.
        This is the primary method for context retrieval.

        Args:
            input_data: A valid ContextGenerationInput object (v5.0 or later).

        Returns:
            An AssociativeMatchResult object containing the context summary and a list of MatchTuple objects.
            Returns an error result if dependencies are unavailable, pre-filtering/reading fails, or the LLM task fails.
        """
        logging.debug(f"get_relevant_context_for called with input: {input_data}")

        # 1. Validate input_data and dependencies
        if not isinstance(input_data, ContextGenerationInput):
            logging.warning("Received non-ContextGenerationInput, attempting conversion.")
            try:
                input_data = ContextGenerationInput.model_validate(input_data)
            except Exception as e:
                msg = f"Invalid input data format: {e}"
                logging.error(msg)
                return AssociativeMatchResult(context_summary="Error", matches=[], error=msg)

        if not self.task_system:
            msg = "TaskSystem dependency not available."
            logging.error(msg)
            return AssociativeMatchResult(context_summary="Error", matches=[], error=msg)
        if not self.file_access_manager:
            msg = "FileAccessManager dependency not available."
            logging.error(msg)
            return AssociativeMatchResult(context_summary="Error", matches=[], error=msg)

        # 2. Determine matching strategy and query
        strategy = input_data.matching_strategy or 'content' # Default to 'content'
        query = input_data.query or input_data.templateDescription or "" # Determine query source
        if not query:
            msg = "No query or templateDescription provided for context matching."
            logging.warning(msg)
            return AssociativeMatchResult(context_summary="No query", matches=[], error=msg)

        logging.info(f"Using matching strategy: '{strategy}' for query: '{query[:50]}...'")

        # 3. Pre-filter candidate paths (Placeholder - using all for now)
        # TODO: Implement pre-filtering based on query/index structure
        candidate_paths = list(self.global_index.keys())
        logging.debug(f"Candidate paths for matching: {len(candidate_paths)}")
        if not candidate_paths:
            return AssociativeMatchResult(context_summary="No files indexed", matches=[])

        # 4/5. Prepare inputs for the appropriate internal LLM task
        inputs_for_llm: Dict[str, Any] = {"context_input": input_data.model_dump(exclude_none=True)}
        task_name: str

        if strategy == 'content':
            task_name = "internal:associative_matching_content"
            file_contents: Dict[str, str] = {}
            for path in candidate_paths:
                try:
                    content = self.file_access_manager.read_file(path)
                    if content is not None:
                        file_contents[path] = content
                    else:
                        logging.warning(f"Could not read content for candidate file: {path}")
                except Exception as e:
                    logging.warning(f"Error reading file {path}: {e}")
            if not file_contents:
                 msg = "No content could be read for any candidate files."
                 logging.warning(msg)
                 return AssociativeMatchResult(context_summary="No content read", matches=[], error=msg)
            inputs_for_llm["file_contents"] = file_contents
            logging.debug(f"Prepared {len(file_contents)} file contents for LLM.")

        elif strategy == 'metadata':
            task_name = "internal:associative_matching_metadata"
            metadata_snippet: Dict[str, str] = {path: self.global_index[path] for path in candidate_paths}
            inputs_for_llm["metadata_snippet"] = metadata_snippet
            logging.debug(f"Prepared {len(metadata_snippet)} metadata snippets for LLM.")

        else:
            # Should not happen if validation is correct, but handle defensively
            msg = f"Invalid matching strategy: {strategy}"
            logging.error(msg)
            return AssociativeMatchResult(context_summary="Error", matches=[], error=msg)

        # 6. Handle sharding (Placeholder - TBD)
        # TODO: Implement sharding logic if needed

        # 7. Create SubtaskRequest for the internal LLM task
        # Ensure this task does not try to fetch more context itself
        context_override = ContextManagement(freshContext="disabled", inheritContext="none")
        subtask_request = SubtaskRequest(
            task_id=f"context-gen-{strategy}-{hash(query)}", # Unique-ish ID
            type="atomic",
            name=task_name,
            description=f"Internal context generation using {strategy}",
            inputs=inputs_for_llm,
            context_management=context_override
        )

        # 8. Call TaskSystem to execute the internal task
        logging.debug(f"Executing internal task: {task_name}")
        try:
            task_result = self.task_system.execute_atomic_template(subtask_request)
        except Exception as e:
            msg = f"Unexpected error calling TaskSystem for internal task {task_name}: {e}"
            logging.exception(msg)
            return AssociativeMatchResult(context_summary="Error", matches=[], error=msg)

        # 9. Parse the AssociativeMatchResult from the TaskResult
        if task_result.status == "FAILED":
            error_msg = task_result.notes.get("error", {}).get("message", task_result.content)
            msg = f"Associative matching task '{task_name}' failed: {error_msg}"
            logging.error(msg)
            return AssociativeMatchResult(context_summary="Error", matches=[], error=msg)

        if not isinstance(task_result.content, str):
             msg = f"Internal task '{task_name}' returned non-string content: {type(task_result.content)}"
             logging.error(msg)
             return AssociativeMatchResult(context_summary="Error", matches=[], error=msg)

        try:
            # Use Pydantic validation for parsing
            assoc_match_result = AssociativeMatchResult.model_validate_json(task_result.content)
            logging.info(f"Successfully generated context via '{task_name}': {len(assoc_match_result.matches)} matches.")
            return assoc_match_result
        except Exception as e:
            msg = f"Failed to parse AssociativeMatchResult JSON from task '{task_name}': {e}"
            logging.error(f"{msg}\nContent was: {task_result.content[:500]}...") # Log truncated content
            return AssociativeMatchResult(context_summary="Error", matches=[], error=msg)

    def _recalculate_shards(self) -> None:
        """
        Internal method to recalculate shards based on the global index and config.
        (Implementation TBD in Phase 2)
        """
        if not self._config.get("sharding_enabled", False):
            self._sharded_index = []
            return

        logging.debug("Recalculating shards (logic TBD)...")
        # Placeholder: In Phase 2, this will split self.global_index into
        # self._sharded_index based on token estimates and config limits.
        # For now, just log and potentially clear/reset.
        self._sharded_index = []  # Resetting for now
        # Example placeholder logic:
        # self._sharded_index = [self.global_index] # Put everything in one shard for now if enabled
        logging.debug(f"Shards recalculated. Count: {len(self._sharded_index)}")
        pass  # Actual sharding logic deferred

    def index_git_repository(
        self, repo_path: str, options: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Indexes a Git repository and updates the global index.

        Args:
            repo_path: Path to the local Git repository.
            options: Optional dictionary for indexer configuration (e.g., max_file_size, include_patterns).
                     Expected keys: 'max_file_size' (int), 'include_patterns' (List[str]), 'exclude_patterns' (List[str]).
        """
        # Implementation deferred to Phase 2
        # logging.warning("index_git_repository called, but implementation is deferred.") # Removed warning
        # --- Start Phase 2, Set A: Behavior Structure ---
        # 1. Import GitRepositoryIndexer (likely needs to be done at module level or carefully handled).
        # 2. Validate/Normalize repo_path (e.g., check if it exists and is a directory).
        # 3. Instantiate the GitRepositoryIndexer:
        #    - indexer = GitRepositoryIndexer(repo_path=repo_path)
        # 4. Configure the indexer based on options:
        #    - If options are provided, call indexer configuration methods (e.g., set_include_patterns, set_max_file_size).
        # 5. Call the indexer's main method, passing self:
        #    - indexed_files_count = indexer.index_repository(memory_system=self)
        # 6. Log the results:
        #    - Log the number of files indexed or any errors encountered.
        # --- End Phase 2, Set A ---

        # --- Start Phase 4 Implementation ---
        if GitRepositoryIndexer is None:
            logging.error("GitRepositoryIndexer is not available. Cannot index repository.")
            return

        logging.info(f"Received request to index Git repository: {repo_path}")
        if not os.path.isdir(repo_path):
             logging.error(f"Repository path is not a valid directory: {repo_path}")
             # Consider raising an error or returning a status
             return

        try:
            # 3. Instantiate the indexer
            indexer = GitRepositoryIndexer(repo_path=repo_path)

            # 4. Configure the indexer based on options
            if options:
                logging.debug(f"Configuring indexer with options: {options}")
                if 'max_file_size' in options and isinstance(options['max_file_size'], int):
                    # Use setter method if available, otherwise direct attribute access (matching test assumption)
                    # indexer.set_max_file_size(options['max_file_size'])
                    indexer.max_file_size = options['max_file_size']
                if 'include_patterns' in options and isinstance(options['include_patterns'], list):
                    # indexer.set_include_patterns(options['include_patterns'])
                    indexer.include_patterns = options['include_patterns']
                if 'exclude_patterns' in options and isinstance(options['exclude_patterns'], list):
                    # indexer.set_exclude_patterns(options['exclude_patterns'])
                    indexer.exclude_patterns = options['exclude_patterns']

            # 5. Call the indexer's main method, passing self
            # The indexer's method will call self.update_global_index internally
            indexed_data = indexer.index_repository(memory_system=self)

            # 6. Log results (already done within indexer.index_repository)
            logging.info(f"Successfully initiated indexing for {repo_path}. {len(indexed_data)} files processed by indexer.")

        except ValueError as ve: # Catch init errors
            logging.error(f"Error initializing GitRepositoryIndexer for {repo_path}: {ve}")
        except Exception as e:
            logging.error(f"Error indexing repository {repo_path}: {e}", exc_info=True)
            # Potentially re-raise or handle more gracefully depending on desired system behavior
        # --- End Phase 4 Implementation ---
