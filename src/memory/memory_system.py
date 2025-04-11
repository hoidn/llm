"""Memory System implementation."""
from typing import Dict, List, Any, Optional, Tuple
import os
import math

class MemorySystem:
    """Memory System for metadata management and associative matching.
    
    Maintains a global metadata index to support context retrieval
    while delegating actual file operations to Handler tools.
    """
    
    def __init__(self, handler=None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Memory System.
        
        Args:
            handler: Optional handler component for LLM operations
            config: Optional configuration dictionary
        """
        self.global_index = {}  # Global file metadata index
        self.handler = handler  # Reference to the handler for LLM operations
        
        # Initialize configuration with defaults
        self._config = {
            "sharding_enabled": False,
            "token_size_per_shard": 4000,   # Target tokens per shard (~1/4 of context window)
            "max_shards": 8,                # Maximum number of shards
            "token_estimation_ratio": 0.25  # Character to token ratio (4 chars per token)
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
            ValueError: If any file path is not absolute
        """
        # Validate all paths are absolute
        for path in index.keys():
            if not os.path.isabs(path):
                raise ValueError(f"File path must be absolute: {path}")
                
        # Update the global index
        self.global_index.update(index)  # Update instead of replace
        
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

    def configure_sharding(self, 
                          token_size_per_shard: Optional[int] = None,
                          max_shards: Optional[int] = None,
                          token_estimation_ratio: Optional[float] = None) -> None:
        """
        Configure sharded context retrieval parameters.
        
        Args:
            token_size_per_shard: Maximum estimated tokens per shard
            max_shards: Maximum number of shards
            token_estimation_ratio: Ratio for converting characters to tokens
        """
        # Update configuration
        if token_size_per_shard is not None:
            self._config["token_size_per_shard"] = token_size_per_shard
            
        if max_shards is not None:
            self._config["max_shards"] = max_shards
            
        if token_estimation_ratio is not None:
            self._config["token_estimation_ratio"] = token_estimation_ratio
        
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
    
    def get_relevant_context_for(self, input_data: Dict[str, Any]) -> Any:
        """
        Get relevant context for a task.
        
        Args:
            input_data: The input data containing task context
            
        Returns:
            Object containing context and file matches
        """
        task_text = input_data.get("taskText", "")
        
        # Create result class - keep this for API compatibility
        class Result:
            def __init__(self, context, matches):
                self.context = context
                self.matches = matches
        
        # If the handler is available, use it to determine relevant files
        if self.handler and hasattr(self.handler, 'determine_relevant_files'):
            try:
                # Get file metadata
                file_metadata = self.get_global_index()
                
                # Use the handler to determine relevant files
                relevant_matches = self.handler.determine_relevant_files(task_text, file_metadata)
                
                if relevant_matches:
                    context = f"Found {len(relevant_matches)} relevant files for '{task_text}'."
                    return Result(context=context, matches=relevant_matches)
            except Exception as e:
                print(f"Error using handler for file relevance: {e}")
                # Fall back to basic matching
        
        # If sharding is disabled or global index is small enough, use standard approach
        if not self._config["sharding_enabled"] or len(self._sharded_index) <= 1:
            return self._get_relevant_context_standard(input_data)
        
        # Otherwise, use sharded approach (internal implementation)
        return self._get_relevant_context_sharded(input_data)
    
    def _get_relevant_context_standard(self, input_data: Dict[str, Any]) -> Any:
        """
        Get relevant context using standard approach.
        This is an internal method.
        
        Args:
            input_data: The input data containing task context
            
        Returns:
            Object containing context and file matches
        """
        task_text = input_data.get("taskText", "")
        
        # Create result class
        class Result:
            def __init__(self, context, matches):
                self.context = context
                self.matches = matches
        
        # Perform basic keyword matching - return ALL matches
        matches = []
        for path, metadata in self.global_index.items():
            # Check if any keywords from the query appear in the metadata
            if any(keyword.lower() in metadata.lower() for keyword in task_text.lower().split()):
                matches.append((path, metadata))
        
        if matches:
            context = f"Found {len(matches)} relevant files for '{task_text}'."
        else:
            context = f"No relevant files found for '{task_text}'."
            
        return Result(context=context, matches=matches)

    def _get_relevant_context_sharded(self, input_data: Dict[str, Any]) -> Any:
        """
        Get relevant context using sharded approach.
        This is an internal method.
        
        Args:
            input_data: The input data containing task context
            
        Returns:
            Object containing context and file matches
        """
        task_text = input_data.get("taskText", "")
        
        # Create result class
        class Result:
            def __init__(self, context, matches):
                self.context = context
                self.matches = matches
        
        # Process each shard independently
        all_matches = []
        for shard in self._sharded_index:
            # Basic keyword matching for this shard
            for path, metadata in shard.items():
                if any(keyword.lower() in metadata.lower() for keyword in task_text.lower().split()):
                    all_matches.append((path, metadata))
        
        # Remove duplicates while preserving order (deduplication is acceptable)
        seen = set()
        unique_matches = []
        for match in all_matches:
            path = match[0]
            if path not in seen:
                seen.add(path)
                unique_matches.append(match)
        
        # Create context message
        if unique_matches:
            context = f"Found {len(unique_matches)} relevant files for '{task_text}'."
        else:
            context = f"No relevant files found for '{task_text}'."
        
        return Result(context=context, matches=unique_matches)
    
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
        
        print(f"Updated global index with {len(file_metadata)} files from repository")
