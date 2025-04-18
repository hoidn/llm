"""
// === IDL-CREATION-GUIDLINES === // Object Oriented: Use OO Design. // Design Patterns: Use Factory, Builder and Strategy patterns where possible // ** Complex parameters JSON : Use JSON where primitive params are not possible and document them in IDL like "Expected JSON format: { "key1": "type1", "key2": "type2" }" // == !! BEGIN IDL TEMPLATE !! === // === CODE-CREATION-RULES === // Strict Typing: Always use strict typing. Avoid using ambiguous or variant types. // Primitive Types: Favor the use of primitive types wherever possible. // Portability Mandate: Python code must be written with the intent to be ported to Java, Go, and JavaScript. Consider language-agnostic logic and avoid platform-specific dependencies. // No Side Effects: Functions should be pure, meaning their output should only be determined by their input without any observable side effects. // Testability: Ensure that every function and method is easily testable. Avoid tight coupling and consider dependency injection where applicable. // Documentation: Every function, method, and module should be thoroughly documented, especially if there's a nuance that's not directly evident from its signature. // Contractual Obligation: The definitions provided in this IDL are a strict contract. All specified interfaces, methods, and constraints must be implemented precisely as defined without deviation. // =======================

@module MemorySystemModule
// Dependencies: BaseHandler, TaskSystem, ContextGenerationInput, AssociativeMatchResult, GitRepositoryIndexer, PromptRegistry
// Description: Manages a global index of file metadata and provides context retrieval
//              capabilities, primarily through associative matching mediated by the TaskSystem.
//              Supports optional sharding for large indexes.
module MemorySystemModule {

    // Interface for the Memory System.
    interface MemorySystem {
        // @depends_on(BaseHandler, TaskSystem)

        // Constructor
        // Preconditions:
        // - handler is an optional BaseHandler instance.
        // - task_system is an optional TaskSystem instance.
        // - config is an optional dictionary for sharding parameters.
        // Postconditions:
        // - MemorySystem is initialized with an empty global index and dependencies.
        // - Sharding configuration is set from config or defaults.
        void __init__(optional BaseHandler handler, optional TaskSystem task_system, optional dict<string, Any> config);

        // Retrieves the current global file metadata index.
        // Preconditions: None.
        // Postconditions:
        // - Returns the dictionary mapping absolute file paths to metadata strings.
        dict<string, string> get_global_index();

        // Updates the global file metadata index.
        // Preconditions:
        // - index is a dictionary mapping file paths to metadata strings.
        // - All file paths in the index must be absolute (unless in a test environment).
        // Postconditions:
        // - The provided index entries are merged into the `global_index`.
        // - Internal shards are updated if sharding is enabled.
        // Raises:
        // - ValueError if a non-absolute path is provided outside a test environment.
        void update_global_index(dict<string, string> index);

        // Enables or disables sharded context retrieval.
        // Preconditions:
        // - enabled is a boolean value.
        // Postconditions:
        // - Sharding flag `_config["sharding_enabled"]` is set.
        // - Shards are updated via `_update_shards` if sharding is enabled.
        void enable_sharding(boolean enabled);

        // Configures parameters for sharded context retrieval.
        // Preconditions:
        // - Parameters (token_size_per_shard, max_shards, etc.) are valid types (int, float).
        // Postconditions:
        // - Internal sharding configuration `_config` is updated.
        // - Shards are updated via `_update_shards` if sharding is enabled.
        void configure_sharding(optional int token_size_per_shard, optional int max_shards, optional float token_estimation_ratio, optional int max_parallel_shards);

        // Retrieves relevant context using a specific description for matching.
        // Preconditions:
        // - query is the main task query string.
        // - context_description is the string to use for associative matching.
        // Postconditions:
        // - Calls `get_relevant_context_for` using `context_description`.
        // - Returns an AssociativeMatchResult object.
        AssociativeMatchResult get_relevant_context_with_description(string query, string context_description);

        // Retrieves relevant context for a task, mediating through the TaskSystem.
        // Preconditions:
        // - input_data is either a legacy dictionary or a ContextGenerationInput object.
        // - TaskSystem dependency must be available.
        // Expected JSON format for legacy input_data: { "taskText": "string", "inheritedContext": "string", ... }
        // Postconditions:
        // - Converts input to ContextGenerationInput if necessary.
        // - Handles sharding if enabled, processing shards in parallel.
        // - Delegates context generation to `TaskSystem.generate_context_for_memory_system`.
        // - Returns an AssociativeMatchResult object containing context summary and file matches.
        AssociativeMatchResult get_relevant_context_for(union<dict<string, Any>, ContextGenerationInput> input_data);

        // Indexes a Git repository and updates the global index.
        // Preconditions:
        // - repo_path is a valid path to a Git repository.
        // - options is an optional dictionary for indexer configuration.
        // Expected JSON format for options: { "include_patterns": list<string>, "exclude_patterns": list<string>, "max_file_size": int }
        // Postconditions:
        // - Instantiates GitRepositoryIndexer.
        // - Indexes the repository based on configuration.
        // - Updates the global index via `update_global_index`.
        void index_git_repository(string repo_path, optional dict<string, Any> options);

        // Additional methods... (Private/protected methods like _estimate_tokens, _update_shards are not part of the public IDL)
    };
};
// == !! END IDL TEMPLATE !! ===

"""
from typing import Dict, List, Any, Optional, Tuple, Union
import os
import math
import sys
import logging
import concurrent.futures

from memory.context_generation import ContextGenerationInput
from memory.context_generation import AssociativeMatchResult  # Import the standard result type
from system.prompt_registry import registry as prompt_registry

class MemorySystem:
    """Memory System for metadata management and associative matching.
    
    Maintains a global metadata index to support context retrieval
    while delegating actual file operations to Handler tools.
    """
    
    def __init__(self, handler=None, task_system=None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Memory System.
        
        Args:
            handler: Optional handler component for LLM operations
            task_system: Optional task system for mediating context generation
            config: Optional configuration dictionary
        """
        self.global_index = {}  # Global file metadata index
        self.handler = handler  # Reference to the handler for LLM operations
        self.task_system = task_system  # Reference to the task system for mediation
        
        # Initialize configuration with defaults
        self._config = {
            "sharding_enabled": False,
            "token_size_per_shard": 4000,   # Target tokens per shard (~1/4 of context window)
            "max_shards": 8,                # Maximum number of shards
            "token_estimation_ratio": 0.25, # Character to token ratio (4 chars per token)
            "max_parallel_shards": min(8, (os.cpu_count() or 1) * 2)  # Limit parallel processing
        }
        
        # Update configuration if provided
        if config:
            self._config.update(config)
            
        # Initialize internal state
        self._sharded_index = []  # List of index shards
    
    def get_global_index(self) -> Dict[str, str]:
        """Get the global file metadata index.
        
        Returns:
            Dict mapping file paths to their metadata
        """
        return self.global_index
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in text.
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count
        """
        # Simple estimation based on character count
        token_ratio = self._config["token_estimation_ratio"]
        return int(len(text) * token_ratio)

    def _update_shards(self) -> None:
        """
        Update internal shards based on the global index.
        This is an internal method used for sharded context retrieval.
        """
        # Get configuration values
        token_size_per_shard = self._config["token_size_per_shard"]
        max_shards = self._config["max_shards"]
        
        # Calculate token size for each file
        items = [(path, metadata, self._estimate_tokens(metadata)) 
                 for path, metadata in self.global_index.items()]
        
        # Calculate total tokens and estimate number of shards needed
        total_tokens = sum(tokens for _, _, tokens in items)
        estimated_shards = min(max_shards, math.ceil(total_tokens / token_size_per_shard))
        
        # Initialize shards
        self._sharded_index = [dict() for _ in range(estimated_shards)]
        shard_tokens = [0] * estimated_shards
        
        # Simple round-robin assignment for initial version
        for i, (path, metadata, tokens) in enumerate(items):
            # Assign to the shard with the lowest token count
            target_shard = min(range(estimated_shards), key=lambda i: shard_tokens[i])
            self._sharded_index[target_shard][path] = metadata
            shard_tokens[target_shard] += tokens
            
    def update_global_index(self, index: Dict[str, str]) -> None:
        """
        Update the global file metadata index.
        
        Args:
            index: New index to set
            
        Raises:
            ValueError: If any file path is not absolute in non-test environments
        """
        # Convert relative paths to absolute in test environments
        normalized_index = {}
        for path, metadata in index.items():
            # Check if we're in a test environment (simple heuristic)
            is_test = 'pytest' in sys.modules or 'unittest' in sys.modules
            
            if not os.path.isabs(path) and not is_test:
                raise ValueError(f"File path must be absolute: {path}")
            
            # Convert to absolute path if relative and in test environment
            if not os.path.isabs(path) and is_test:
                abs_path = os.path.abspath(path)
                normalized_index[abs_path] = metadata
            else:
                normalized_index[path] = metadata
                
        # Update the global index
        self.global_index.update(normalized_index)  # Update instead of replace
        
        # Update shards if sharding is enabled
        if self._config["sharding_enabled"]:
            self._update_shards()
    
    def enable_sharding(self, enabled: bool = True) -> None:
        """
        Enable or disable sharded context retrieval.
        
        Args:
            enabled: Whether to enable sharding
        """
        self._config["sharding_enabled"] = enabled
        
        # Update shards if enabling
        if enabled:
            self._update_shards()

    def _process_single_shard(self,
                             shard_index: int,
                             shard_data: Dict[str, str],
                             context_input_base: ContextGenerationInput,
                             total_shards: int) -> Tuple[int, Union[AssociativeMatchResult, Exception]]:
        """
        Processes a single shard to find relevant context.

        Args:
            shard_index: The index of the shard being processed.
            shard_data: The metadata dictionary for this shard.
            context_input_base: The base ContextGenerationInput to be adapted for the shard.
            total_shards: The total number of shards.

        Returns:
            A tuple containing the shard index and either the AssociativeMatchResult or an Exception.
        """
        try:
            # Defensive check, should not happen if called correctly
            if not self.task_system:
                raise RuntimeError("TaskSystem not available during shard processing.")

            logging.debug("Processing shard %d/%d with %d files (Thread)", shard_index + 1, total_shards, len(shard_data))

            # Create a copy of the context input for this shard
            # Ensure all relevant fields from the original context_input are copied
            shard_context_input = ContextGenerationInput(
                template_description=context_input_base.template_description,
                template_type=context_input_base.template_type,
                template_subtype=context_input_base.template_subtype,
                inputs=context_input_base.inputs,
                context_relevance=context_input_base.context_relevance,
                inherited_context=context_input_base.inherited_context,
                previous_outputs=context_input_base.previous_outputs,
                fresh_context=context_input_base.fresh_context
            )

            # Use TaskSystem mediator for this shard
            # This call is still synchronous within this thread, but multiple threads run this concurrently.
            shard_result = self.task_system.generate_context_for_memory_system(
                shard_context_input, shard_data
            )

            # Ensure the result is the expected type
            if not isinstance(shard_result, AssociativeMatchResult):
                logging.warning("Shard %d mediator returned unexpected type: %s", shard_index, type(shard_result))
                # Handle unexpected return type, maybe return an error or empty result
                return shard_index, AssociativeMatchResult(context=f"Unexpected result type from shard {shard_index}", matches=[])
            
            # Validate the matches format
            validated_matches = []
            for match in shard_result.matches:
                if isinstance(match, (list, tuple)):
                    if len(match) >= 2:
                        # Keep the first two elements as a tuple
                        validated_matches.append((match[0], match[1]))
                    elif len(match) == 1:
                        # Add a default relevance score
                        validated_matches.append((match[0], "1.0"))
                elif isinstance(match, dict) and "path" in match:
                    # Handle dictionary format (from some templates)
                    relevance = match.get("relevance", "1.0")
                    validated_matches.append((match["path"], relevance))
                else:
                    logging.warning("Shard %d contains invalid match format: %s", shard_index, match)
            
            # Replace the matches with validated ones
            shard_result.matches = validated_matches

            logging.debug("Shard %d finished processing, found %d matches.", shard_index + 1, len(shard_result.matches))
            return shard_index, shard_result # Return index and result

        except Exception as e:
            # Log the exception specific to this shard's processing
            logging.error("Error processing shard %d: %s", shard_index, e, exc_info=True)
            return shard_index, e # Return index and exception for handling in the main loop
            
    def configure_sharding(self, 
                          token_size_per_shard: Optional[int] = None,
                          max_shards: Optional[int] = None,
                          token_estimation_ratio: Optional[float] = None,
                          max_parallel_shards: Optional[int] = None) -> None:
        """
        Configure sharded context retrieval parameters.
        
        Args:
            token_size_per_shard: Maximum estimated tokens per shard
            max_shards: Maximum number of shards
            token_estimation_ratio: Ratio for converting characters to tokens
            max_parallel_shards: Maximum number of parallel threads for shard processing
        """
        # Update configuration
        if token_size_per_shard is not None:
            self._config["token_size_per_shard"] = token_size_per_shard
            
        if max_shards is not None:
            self._config["max_shards"] = max_shards
            
        if token_estimation_ratio is not None:
            self._config["token_estimation_ratio"] = token_estimation_ratio
            
        if max_parallel_shards is not None:
            self._config["max_parallel_shards"] = max_parallel_shards
        
        # Update shards if sharding is enabled
        if self._config["sharding_enabled"]:
            self._update_shards()
            
    def get_relevant_context_with_description(self, query: str, context_description: str) -> Any:
        """Get relevant context using a dedicated context description.
        
        Uses the context description for associative matching instead of the main query.
        
        Args:
            query: The main task query
            context_description: Description specifically for context matching
            
        Returns:
            Object containing context and file matches
        """
        # Use the context description for matching instead of the main query
        context_input = {
            "taskText": context_description, 
            "inheritedContext": ""
        }
        
        # Get relevant context using the description
        result = self.get_relevant_context_for(context_input)
        
        # If using the handler for determination, provide additional info
        if self.handler and hasattr(self.handler, 'determine_relevant_files'):
            try:
                # Inform the handler about both queries
                self.handler.log_debug(f"Using dedicated context description: '{context_description}'")
                self.handler.log_debug(f"Original query: '{query}'")
            except AttributeError:
                pass
                
        return result
    
    def get_relevant_context_for(self, input_data: Union[Dict[str, Any], ContextGenerationInput]) -> AssociativeMatchResult:  # Update return type hint
        """Get relevant context for a task using TaskSystem mediator exclusively.
        
        Args:
            input_data: The input data containing task context, either as a
                      legacy dict format or ContextGenerationInput instance
        
        Returns:
            Object containing context and file matches
        """
        logging.debug("MemorySystem.get_relevant_context_for called with input type: %s", type(input_data).__name__)
        
        # Convert input to ContextGenerationInput if needed
        if isinstance(input_data, dict):
            # Handle legacy format with taskText
            context_input = ContextGenerationInput.from_legacy_format(input_data)
            logging.debug("Converted dict to ContextGenerationInput: %s", context_input.template_description)
        else:
            context_input = input_data
            if hasattr(context_input, 'template_description'):
                logging.debug("Using existing ContextGenerationInput: %s", context_input.template_description)
        
        # Check if fresh context is disabled
        if hasattr(context_input, 'fresh_context') and context_input.fresh_context == "disabled":
            logging.info("Fresh context disabled, returning inherited context only")
            return AssociativeMatchResult(  # Return standard type
                context=context_input.inherited_context or "No context available",
                matches=[]
            )
        
        # Verify TaskSystem is available
        if not hasattr(self, 'task_system') or self.task_system is None:
            logging.warning("TaskSystem not available for context generation")
            return AssociativeMatchResult(  # Return standard type
                context="TaskSystem not available for context generation",
                matches=[]
            )
        
        try:
            # If sharding is disabled or global index is small enough, use standard approach
            if not self._config["sharding_enabled"] or len(self._sharded_index) <= 1:
                return self._get_relevant_context_with_mediator(context_input)
            
            # Otherwise, use sharded approach
            return self._get_relevant_context_sharded_with_mediator(context_input)
        except Exception as e:
            # Improved error handling - return empty result with error message
            error_msg = f"Error during context generation: {str(e)}"
            logging.error(error_msg)
            return AssociativeMatchResult(context=error_msg, matches=[])  # Return standard type
    
    def _get_relevant_context_with_mediator(self, context_input: ContextGenerationInput) -> AssociativeMatchResult:  # Update return type hint
        """
        Get relevant context using TaskSystem mediator.
        
        Args:
            context_input: The ContextGenerationInput instance
            
        Returns:
            Object containing context and file matches
        """
        try:
            # Check if task_system is available (should have been checked in get_relevant_context_for)
            if not hasattr(self, 'task_system') or self.task_system is None:
                return AssociativeMatchResult(context="TaskSystem not available for context generation", matches=[])  # Return standard type
            
            # Get file metadata
            file_metadata = self.get_global_index()
            
            # Add debug logging
            logging.debug("Global index contains %d files", len(file_metadata))
            
            if not file_metadata:
                # Make this a clear log message for debugging
                logging.info("No files in index for context generation")
                return AssociativeMatchResult(context="No files in index", matches=[])  # Return standard type
            
            # Use TaskSystem mediator pattern
            # TaskSystem returns AssociativeMatchResult
            associative_result = self.task_system.generate_context_for_memory_system(
                context_input, file_metadata
            )
            
            # Return the AssociativeMatchResult directly
            logging.debug("Returning AssociativeMatchResult directly (matches=%d)", len(associative_result.matches))
            return associative_result
        except Exception as e:
            # Improved error handling with detailed logging
            error_msg = f"Error during context generation with mediator: {str(e)}"
            logging.exception("Error during context generation with mediator:")
            return AssociativeMatchResult(context=error_msg, matches=[])  # Return standard type

    def _get_relevant_context_sharded_with_mediator(self, context_input: ContextGenerationInput) -> AssociativeMatchResult:
        """
        Get relevant context using sharded approach with TaskSystem mediator, processed in parallel.
        
        Args:
            context_input: The ContextGenerationInput instance
            
        Returns:
            Object containing context and file matches
        """
        # Check if task_system is available (should have been checked in get_relevant_context_for)
        if not hasattr(self, 'task_system') or self.task_system is None:
            # This path should ideally not be reached if get_relevant_context_for checks first
            logging.warning("TaskSystem not available for context generation (sharded).")
            return AssociativeMatchResult(context="TaskSystem not available for context generation", matches=[])
        
        all_matches = []
        successful_shards = 0
        total_shards = len(self._sharded_index)
        futures = []

        # Determine a reasonable number of workers
        # Limit threads to avoid overwhelming resources, especially the LLM API
        max_parallel_shards = self._config.get("max_parallel_shards")
        num_workers = min(total_shards, max_parallel_shards)
        logging.info("Processing %d shards with %d worker threads.", total_shards, num_workers)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            for shard_index, shard in enumerate(self._sharded_index):
                # Skip empty shards
                if not shard:
                    logging.debug("Skipping empty shard %d", shard_index)
                    continue

                # Submit the processing of this shard to the thread pool
                # Pass necessary arguments to the helper function
                future = executor.submit(
                    self._process_single_shard,
                    shard_index,
                    shard,
                    context_input, # Pass the original context_input
                    total_shards
                )
                futures.append(future)

            # Process results as they complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    # Retrieve the result (or exception) from the future
                    shard_idx, result_or_error = future.result()

                    # Check if an exception occurred during shard processing
                    if isinstance(result_or_error, Exception):
                        # Error was already logged within _process_single_shard
                        logging.warning("Shard %d processing failed.", shard_idx)
                    # Check if the result is the expected type
                    elif isinstance(result_or_error, AssociativeMatchResult):
                        # Add matches from this shard (already validated in _process_single_shard)
                        all_matches.extend(result_or_error.matches)
                        successful_shards += 1
                        logging.debug("Added %d matches from shard %d", len(result_or_error.matches), shard_idx)
                    else:
                        # Log unexpected return type
                        logging.warning("Received unexpected result type from shard %d: %s",
                                        shard_idx, type(result_or_error))

                except Exception as exc:
                    # Catch exceptions raised *during* future.result() itself (less common)
                    # This might happen if the future was cancelled, etc.
                    logging.error("Error retrieving result from future: %s", exc, exc_info=True)
        
        # Remove duplicates while preserving order (based on file path)
        seen = set()
        unique_matches = []
        for match in all_matches:
            # Ensure match is a tuple/list and has at least one element (the path)
            if isinstance(match, (list, tuple)) and len(match) > 0:
                path = match[0]
                if path not in seen:
                    seen.add(path)
                    # Ensure we always store a 2-element tuple for consistency
                    if len(match) >= 2:
                        unique_matches.append((path, match[1]))
                    else:
                        # If there's only one element, add a default second element
                        unique_matches.append((path, "1.0"))  # Default relevance score
                        logging.debug("Added default relevance score for match: %s", path)
            else:
                logging.warning("Skipping malformed match item during deduplication: %s", match)

        # Create context message
        if successful_shards < total_shards:
            context = (f"Found {len(unique_matches)} relevant files. "
                      f"Processed {successful_shards}/{total_shards} shards successfully (some failed).")
        elif unique_matches:
            context = f"Found {len(unique_matches)} relevant files across {successful_shards}/{total_shards} shards."
        else:
            context = f"No relevant files found across {successful_shards}/{total_shards} shards."

        logging.info("Sharded context retrieval complete. %s", context)
        return AssociativeMatchResult(context=context, matches=unique_matches)
    
    def index_git_repository(self, repo_path: str, options: Optional[Dict[str, Any]] = None) -> None:
        """Index a git repository and update the global index.
        
        Args:
            repo_path: Path to the git repository
            options: Optional indexing configuration
                - include_patterns: List of glob patterns to include
                - exclude_patterns: List of glob patterns to exclude
                - max_file_size: Maximum file size to process in bytes
        """
        from memory.indexers.git_repository_indexer import GitRepositoryIndexer
        
        # Create indexer
        indexer = GitRepositoryIndexer(repo_path)
        
        # Apply options if provided
        if options:
            if "include_patterns" in options:
                indexer.include_patterns = options["include_patterns"]
            if "exclude_patterns" in options:
                indexer.exclude_patterns = options["exclude_patterns"]
            if "max_file_size" in options:
                indexer.max_file_size = options["max_file_size"]
        
        # Index repository
        file_metadata = indexer.index_repository(self)
        
        # Update global index
        if hasattr(self, 'global_index'):
            # If the memory system already has a global index, update it
            self.global_index.update(file_metadata)
        else:
            # Otherwise, create a new global index
            self.global_index = file_metadata
        
        # Ensure the update_global_index method is called if it exists
        if hasattr(self, 'update_global_index'):
            self.update_global_index(file_metadata)
        
        logging.info("Updated global index with %d files from repository", len(file_metadata))
