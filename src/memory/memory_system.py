"""
Memory System manages file metadata and context retrieval.
Implements the contract defined in src/memory/memory_system_IDL.md.
"""

import os
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

# Import necessary models
from src.system.models import ContextGenerationInput, AssociativeMatchResult, MatchTuple

# Default sharding config (can be refined)
DEFAULT_SHARDING_CONFIG = {
    "sharding_enabled": False,
    "token_size_per_shard": 10000,
    "max_shards": 10,
    "token_estimation_ratio": 0.75,  # Placeholder ratio
    "max_parallel_shards": 3,
}

# Forward declarations for type hinting cycles
# from src.handler.base_handler import BaseHandler
# from src.task_system.task_system import TaskSystem
# from src.system.models import ContextGenerationInput, AssociativeMatchResult, MatchTuple


class MemorySystem:
    """
    Manages file metadata and context retrieval.
    """

    def __init__(
        self,
        handler: Optional[Any] = None,  # BaseHandler
        task_system: Optional[Any] = None,  # TaskSystem
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initializes the Memory System.

        Args:
            handler: Optional BaseHandler instance (required for context generation).
            task_system: Optional TaskSystem instance (required for context generation mediation).
            config: Optional dictionary for sharding parameters and other settings.
        """
        self.handler = handler
        self.task_system = task_system
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
            if not os.path.isabs(path):
                invalid_paths.append(path)

        if invalid_paths:
            raise ValueError(f"Non-absolute paths provided in index: {invalid_paths}")

        self.global_index.update(index)
        logging.debug(
            f"Global index updated with {len(index)} entries. Total size: {len(self.global_index)}"
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
        logging.warning(
            "get_relevant_context_with_description called, but implementation is deferred."
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
        self, input_data: Any  # Union[Dict[str, Any], ContextGenerationInput]
    ) -> Any:  # AssociativeMatchResult
        """
        Retrieves relevant context for a task, mediating through the TaskSystem.

        Args:
            input_data: Either a legacy dictionary or a ContextGenerationInput object.

        Returns:
            An AssociativeMatchResult object.
        """
        # Implementation deferred to Phase 2
        logging.warning(
            "get_relevant_context_for called, but implementation is deferred."
        )
        # --- Start Phase 2, Set A: Behavior Structure ---
        # 1. Parse/Validate input_data:
        #    - If it's a legacy dict, convert it to ContextGenerationInput.
        #    - If it's already ContextGenerationInput, validate it.
        # 2. Determine the effective query string for matching:
        #    - Prioritize input_data.query if present.
        #    - Else, use input_data.templateDescription and relevant input_data.inputs.
        # 3. Check if fresh context generation is effectively disabled:
        #    - This might depend on flags within input_data or other context settings (logic might be complex and partially determined by the caller).
        #    - If disabled, potentially return early with inherited context or an empty result (TBD based on exact requirements).
        # 4. Perform associative matching:
        #    - If sharding is enabled (self._config['sharding_enabled'] and len(self._sharded_index) > 0):
        #        - Determine which shards to process (potentially all or a subset).
        #        - Process shards in parallel (up to max_parallel_shards) using a helper like _process_single_shard.
        #        - Aggregate results from shards (e.g., combine matches, potentially re-rank).
        #    - If sharding is disabled or not applicable:
        #        - Call a helper method like _get_relevant_context_with_mediator, passing the full global_index and input_data.
        #        - This mediator method will likely:
        #            - Check if TaskSystem is available.
        #            - Call self.task_system.generate_context_for_memory_system(input_data, self.global_index).
        # 5. Format the results:
        #    - Construct an AssociativeMatchResult object from the matches and context summary obtained.
        # 6. Handle errors:
        #    - Catch exceptions during the process (e.g., TaskSystem unavailable, matching task failure).
        #    - Return an AssociativeMatchResult with an appropriate error message.
        # 7. Return the AssociativeMatchResult.
        # --- End Phase 2, Set A ---

        # --- Start Phase 2a Implementation ---
        # 1. Parse/Validate input_data (Assuming it's already ContextGenerationInput for now)
        if not isinstance(input_data, ContextGenerationInput):
            # Basic handling if legacy dict is passed, might need refinement
            logging.warning("Received non-ContextGenerationInput, attempting conversion.")
            try:
                input_data = ContextGenerationInput.model_validate(input_data)
            except Exception as e:
                logging.error(f"Failed to parse input_data: {e}")
                return AssociativeMatchResult(
                    context_summary="Error: Invalid input data format.",
                    matches=[],
                    error=f"Invalid input data format: {e}"
                )

        # 2. Determine the effective query string(s) for matching
        search_strings = []
        if input_data.query:
            search_strings.append(input_data.query)
        elif input_data.templateDescription:
            # Combine description and potentially key inputs for search
            # Simple approach: use description directly
            search_strings.append(input_data.templateDescription)
            # Future enhancement: could extract keywords from inputs dict
            # if input_data.inputs:
            #     search_strings.extend([str(v) for v in input_data.inputs.values()])
        else:
            # No query or description provided
            logging.warning("No query or templateDescription in input_data for context matching.")
            return AssociativeMatchResult(
                context_summary="No search criteria provided.",
                matches=[],
                error="No query or templateDescription provided."
            )

        # Normalize search strings (e.g., lower case for case-insensitive matching)
        search_strings_lower = [s.lower() for s in search_strings if s]
        if not search_strings_lower:
             return AssociativeMatchResult(context_summary="Empty search criteria.", matches=[])


        # 4. Perform associative matching (Simple Substring Search for Phase 2a)
        matches = []
        index_to_search = {}

        # Use global index regardless of sharding setting for Phase 2a
        # Structure is in place for future sharding logic.
        if self._config.get("sharding_enabled", False):
            logging.debug("Sharding enabled, but using global index for Phase 2a matching.")
            # In future: iterate through self._sharded_index
            index_to_search = self.global_index
        else:
            logging.debug("Sharding disabled, using global index for matching.")
            index_to_search = self.global_index

        for file_path, metadata in index_to_search.items():
            metadata_lower = metadata.lower()
            # Check if *any* of the search strings are found in the metadata
            if any(search_str in metadata_lower for search_str in search_strings_lower):
                # Create MatchTuple according to Pydantic model
                # Using placeholder relevance 1.0 for direct match, no excerpt
                matches.append(MatchTuple(path=file_path, relevance=1.0)) # Adhere to MatchTuple model

        # 5. Format the results
        context_summary = f"Found {len(matches)} potential matches based on keyword search."
        logging.debug(f"Context matching complete. Found {len(matches)} matches for query derived from: {search_strings}")

        # 7. Return the AssociativeMatchResult
        return AssociativeMatchResult(
            context_summary=context_summary,
            matches=matches,
            error=None
        )
        # --- End Phase 2a Implementation ---

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
            options: Optional dictionary for indexer configuration.
        """
        # Implementation deferred to Phase 2
        logging.warning("index_git_repository called, but implementation is deferred.")
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
        pass
