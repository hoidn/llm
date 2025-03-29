"""Memory System implementation."""
from typing import Dict, List, Any, Optional, Tuple

class MemorySystem:
    """Memory System for metadata management and associative matching.
    
    Maintains a global metadata index to support context retrieval
    while delegating actual file operations to Handler tools.
    """
    
    def __init__(self):
        """Initialize the Memory System."""
        self.global_index = {}  # Global file metadata index
    
    def get_global_index(self) -> Dict[str, str]:
        """Get the global file metadata index.
        
        Returns:
            Dict mapping file paths to their metadata
        """
        return self.global_index
    
    def update_global_index(self, index: Dict[str, str]) -> None:
        """Update the global file metadata index.
        
        Args:
            index: New index to set
        """
        self.global_index.update(index)  # Update instead of replace
    
    def get_relevant_context_for(self, input_data: Dict[str, Any]) -> Any:
        """Get relevant context for a task.
        
        Args:
            input_data: The input data containing task context
            
        Returns:
            Object containing context and file matches
        """
        task_text = input_data.get("taskText", "")
        
        # Simple keyword matching for now
        matches = []
        for path, metadata in self.global_index.items():
            # Check if any keywords from the query appear in the metadata
            if any(keyword.lower() in metadata.lower() for keyword in task_text.lower().split()):
                matches.append((path, metadata))
        
        # No limit on number of matches
        # matches = matches[:5]  # Previous limit of 5 files
        
        # Create result object with matches
        class Result:
            def __init__(self, context, matches):
                self.context = context
                self.matches = matches
        
        if matches:
            context = f"Found {len(matches)} relevant files for '{task_text}'."
        else:
            context = f"No relevant files found for '{task_text}'."
            
        return Result(context=context, matches=matches)
    
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
