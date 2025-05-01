"""
Memory System manages file metadata and context retrieval.
Implements the contract defined in src/memory/memory_system_IDL.md.
"""

import os
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

# Configure logger
logger = logging.getLogger(__name__)

# Import necessary models
from src.system.models import (
    ContextGenerationInput, AssociativeMatchResult, MatchTuple, 
    SubtaskRequest, ContextManagement, TaskResult
)
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
        logger.info(
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
        logger.debug(
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
        logger.info(f"Sharding explicitly set to: {enabled}")
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

        logger.info(f"Sharding configuration updated: {self._config}")

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
        logger.debug(
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
        self, input_data: ContextGenerationInput # Expect v5.0 model
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
        # Check TaskSystem dependency EARLY
        if not self.task_system:
            error_msg = "TaskSystem dependency not available in MemorySystem."
            logger.error(error_msg)
            return AssociativeMatchResult(context_summary="", matches=[], error=error_msg)
        
        # Check FileAccessManager dependency EARLY
        if not self.file_access_manager:
            error_msg = "FileAccessManager dependency not available in MemorySystem."
            logger.error(error_msg)
            return AssociativeMatchResult(context_summary="", matches=[], error=error_msg)
            
        logger.debug(f"get_relevant_context_for called with strategy: {input_data.matching_strategy}")

        # 1. Determine Strategy (Default to 'content')
        strategy = input_data.matching_strategy or 'content'
        logger.debug(f"Using matching strategy: {strategy}")

        # 2. Determine Query
        query = input_data.query
        if not query and input_data.templateDescription:
            query = input_data.templateDescription # Fallback
        if not query:
             return AssociativeMatchResult(context_summary="Error: No query provided.", matches=[], error="No query provided.")

        # 3. Pre-filtering (Optional - Placeholder: Use all indexed paths for now)
        # TODO: Implement actual pre-filtering based on query vs paths/metadata later if needed.
        candidate_paths = list(self.global_index.keys())
        logger.debug(f"Pre-filtering selected {len(candidate_paths)} candidate paths (currently uses all).")
        if not candidate_paths:
            return AssociativeMatchResult(context_summary="No files indexed to search.", matches=[])

        inputs_for_llm: Dict[str, Any] = {"context_input": input_data.model_dump(exclude_none=True)}
        llm_task_name: str = ""

        # 4/5. Retrieve Data based on Strategy & Prepare Inputs
        if strategy == 'content':
            llm_task_name = "internal:associative_matching_content"
            file_contents: Dict[str, str] = {}
            skipped_reads = []
            # TODO: Implement sharding/chunking for content if candidate_paths is large
            logger.debug(f"Retrieving content for {len(candidate_paths)} candidate paths...")
            for path in candidate_paths:
                try:
                    # Use file_access_manager - assuming it handles limits/errors internally
                    content = self.file_access_manager.read_file(path, max_size=None)
                    if content is not None:
                        file_contents[path] = content
                    else:
                        skipped_reads.append(path)
                        logger.warning(f"Could not read content for candidate path: {path}")
                except Exception as e:
                    logger.error(f"Error reading content for {path}: {e}")
                    skipped_reads.append(path)
            inputs_for_llm["file_contents"] = file_contents
            logger.debug(f"Prepared file_contents input: {len(file_contents)} files included, {len(skipped_reads)} skipped.")

        elif strategy == 'metadata':
            llm_task_name = "internal:associative_matching_metadata"
            metadata_snippet: Dict[str, str] = {}
            # TODO: Implement sharding/chunking for metadata if candidate_paths is large
            logger.debug(f"Retrieving metadata for {len(candidate_paths)} candidate paths...")
            for path in candidate_paths:
                 meta = self.global_index.get(path)
                 if meta is not None:
                     metadata_snippet[path] = meta # Pass full metadata string for now
                 else:
                      logger.warning(f"Metadata not found in index for candidate path: {path}")
            inputs_for_llm["metadata_snippet"] = metadata_snippet
            logger.debug(f"Prepared metadata_snippet input: {len(metadata_snippet)} entries included.")
        else:
             # Should not happen if ContextGenerationInput validation works
             return AssociativeMatchResult(context_summary="Error: Invalid matching strategy.", matches=[], error=f"Invalid matching strategy: {strategy}")

        # 6. TaskSystem dependency already checked at the beginning of the method

        # 7. Create SubtaskRequest
        try:
            # Prevent recursive context fetching within the matching task
            context_override = ContextManagement(freshContext='disabled', inheritContext='none')
            request = SubtaskRequest(
                task_id=f"context-gen-{strategy}-{input_data.query[:20]}", # Unique-ish ID
                type="atomic",
                name=llm_task_name,
                inputs=inputs_for_llm,
                context_management=context_override
            )
        except Exception as e:
             error_msg = f"Failed to create SubtaskRequest: {e}"
             logger.exception(error_msg)
             return AssociativeMatchResult(context_summary="", matches=[], error=error_msg)

        # 8. Call TaskSystem
        try:
            logger.debug(f"Calling TaskSystem to execute: {llm_task_name}")
            task_result: TaskResult = self.task_system.execute_atomic_template(request)

            # 9. Parse Result
            if task_result.status == "FAILED":
                # Extract error details from the FAILED TaskResult
                error_msg = f"Associative matching task '{llm_task_name}' failed." # Use specific message prefix
                error_details = task_result.notes.get("error")
                reason_suffix = ""
                if error_details:
                    # Handle both dict and TaskFailureError object cases for the message
                    detail_msg = error_details.get("message") if isinstance(error_details, dict) else getattr(error_details, 'message', None)
                    if detail_msg:
                        reason_suffix = f" Reason: {detail_msg}"
                if not reason_suffix:
                    reason_suffix = f" Reason: {task_result.content}" # Fallback to content

                full_error_message = error_msg + reason_suffix
                logger.error(full_error_message)
                # Return AssociativeMatchResult indicating failure WITH the extracted message
                return AssociativeMatchResult(context_summary="", matches=[], error=full_error_message)

            # --- Successful Task Result - Attempt Parsing ---
            parsed_assoc_result = None

            # Try parsedContent first (Pydantic object)
            if hasattr(task_result, 'parsedContent') and isinstance(task_result.parsedContent, AssociativeMatchResult):
                parsed_assoc_result = task_result.parsedContent
                logger.debug("Using AssociativeMatchResult directly from TaskResult.parsedContent")
            elif task_result.parsedContent and isinstance(task_result.parsedContent, dict):
                try:
                    parsed_assoc_result = AssociativeMatchResult.model_validate(task_result.parsedContent)
                    logger.debug("Validated dict from TaskResult.parsedContent as AssociativeMatchResult")
                except Exception as e:
                    logger.warning(f"Failed to validate parsedContent dict as AssociativeMatchResult: {e}. Will try parsing content string.")

            # Fall back to content string (JSON) if parsedContent didn't work or wasn't present/correct type
            if parsed_assoc_result is None and isinstance(task_result.content, str):
                try:
                    parsed_assoc_result = AssociativeMatchResult.model_validate_json(task_result.content)
                    logger.debug("Parsed AssociativeMatchResult from TaskResult.content JSON string")
                except Exception as e:
                    # Specific error message for parsing failure - RETURN IMMEDIATELY
                    parsing_error_message = f"Failed to parse AssociativeMatchResult JSON from task output: {e}"
                    logger.error(f"{parsing_error_message}\nContent was: {task_result.content}")
                    return AssociativeMatchResult(context_summary="", matches=[], error=parsing_error_message)

            # Final check: Did we successfully parse the result?
            if parsed_assoc_result is None:
                 # This means status was COMPLETE, but parsing failed from both sources, or parsedContent was wrong type
                 final_error_msg = "Failed to obtain valid AssociativeMatchResult from successful task."
                 logger.error(f"{final_error_msg} (Content Type: {type(task_result.content)}, ParsedContent Type: {type(task_result.parsedContent)})")
                 return AssociativeMatchResult(context_summary="", matches=[], error=final_error_msg)

            logger.info(f"Successfully generated context via '{llm_task_name}'. Matches: {len(parsed_assoc_result.matches)}")
            return parsed_assoc_result

        except Exception as e:
            error_msg = f"Unexpected error executing matching task via TaskSystem: {e}"
            logger.exception(error_msg)
            return AssociativeMatchResult(context_summary="", matches=[], error=error_msg)

    def _recalculate_shards(self) -> None:
        """
        Internal method to recalculate shards based on the global index and config.
        (Implementation TBD in Phase 2)
        """
        if not self._config.get("sharding_enabled", False):
            self._sharded_index = []
            return

        logger.debug("Recalculating shards (logic TBD)...")
        # Placeholder: In Phase 2, this will split self.global_index into
        # self._sharded_index based on token estimates and config limits.
        # For now, just log and potentially clear/reset.
        self._sharded_index = []  # Resetting for now
        # Example placeholder logic:
        # self._sharded_index = [self.global_index] # Put everything in one shard for now if enabled
        logger.debug(f"Shards recalculated. Count: {len(self._sharded_index)}")

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
            logger.error("GitRepositoryIndexer is not available. Cannot index repository.")
            return

        logger.info(f"Received request to index Git repository: {repo_path}")
        if not os.path.isdir(repo_path):
             logger.error(f"Repository path is not a valid directory: {repo_path}")
             # Consider raising an error or returning a status
             return

        try:
            # 3. Instantiate the indexer
            indexer = GitRepositoryIndexer(repo_path=repo_path)

            # 4. Configure the indexer based on options
            if options:
                logger.debug(f"Configuring indexer with options: {options}")
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
            logger.info(f"Successfully initiated indexing for {repo_path}. {len(indexed_data)} files processed by indexer.")

        except ValueError as ve: # Catch init errors
            logger.error(f"Error initializing GitRepositoryIndexer for {repo_path}: {ve}")
        except Exception as e:
            logger.error(f"Error indexing repository {repo_path}: {e}", exc_info=True)
            # Potentially re-raise or handle more gracefully depending on desired system behavior
        # --- End Phase 4 Implementation ---
