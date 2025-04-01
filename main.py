"""Main entry point for the application."""
import sys
import os
import json
from typing import Dict, List, Optional, Any

class Application:
    """
    Main application class that coordinates all components.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize application with optional configuration.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        
        # Import components
        from memory.memory_system import MemorySystem
        from task_system.task_system import TaskSystem
        from handler.passthrough_handler import PassthroughHandler
        from task_system.templates.associative_matching import register_template
        
        # Initialize components
        self.memory_system = MemorySystem()
        self.task_system = TaskSystem()
        
        # Register templates
        register_template(self.task_system)
        
        # Initialize handler
        self.passthrough_handler = PassthroughHandler(
            task_system=self.task_system,
            memory_system=self.memory_system
        )
        
        # Initialize Aider bridge
        self.aider_bridge = None
        
        # Initialize Aider if available
        self.initialize_aider()
        
        # Track indexed repositories
        self.indexed_repositories = []
    
    def index_repository(self, repo_path: str) -> bool:
        """
        Index a git repository.
        
        Args:
            repo_path: Path to git repository
            
        Returns:
            True if indexing successful, False otherwise
        """
        try:
            # Normalize path
            repo_path = os.path.abspath(repo_path)
            
            # Check if repository exists
            if not os.path.isdir(repo_path):
                print(f"Repository path does not exist: {repo_path}")
                return False
            
            # Check if .git directory exists
            if not os.path.isdir(os.path.join(repo_path, ".git")):
                print(f"Not a git repository: {repo_path}")
                return False
            
            # Initialize indexer
            from memory.indexers.git_repository_indexer import GitRepositoryIndexer
            indexer = GitRepositoryIndexer(repo_path)
            
            # Configure indexer to exclude some common directories
            # Note: include_patterns is already set to ["**/*.py"] in the GitRepositoryIndexer constructor
            indexer.exclude_patterns = ["**/__pycache__/**", "**/node_modules/**", "**/.git/**"]
            
            # Index repository
            print(f"Indexing repository: {repo_path}")
            file_metadata = indexer.index_repository(self.memory_system)
            
            # Track indexed repository
            self.indexed_repositories.append(repo_path)
            
            print(f"Repository indexed: {repo_path} ({len(file_metadata)} files)")
            return True
        except Exception as e:
            print(f"Error indexing repository: {str(e)}")
            return False
    
    def handle_query(self, query: str) -> Dict[str, Any]:
        """
        Handle a user query.
        
        Args:
            query: User query
            
        Returns:
            Response dictionary
        """
        try:
            return self.passthrough_handler.handle_query(query)
        except Exception as e:
            print(f"Error handling query: {str(e)}")
            return {
                "content": f"Error handling query: {str(e)}",
                "metadata": {"error": str(e)}
            }
    
    def reset_conversation(self):
        """
        Reset the conversation state.
        """
        self.passthrough_handler.reset_conversation()
        
    def initialize_aider(self) -> None:
        """
        Initialize AiderBridge and register tools with handler.
        
        Creates an AiderBridge instance and registers Aider tools with
        the passthrough handler if Aider is available.
        """
        try:
            from aider_bridge.bridge import AiderBridge
            from aider_bridge.tools import register_aider_tools
            
            if not self.aider_bridge:
                self.aider_bridge = AiderBridge(self.memory_system)
                # Register tools with handler
                registration_results = register_aider_tools(self.passthrough_handler, self.aider_bridge)
                
                # Log registration results
                if all(result.get("status") == "success" for result in registration_results.values()):
                    print("Aider tools registered successfully")
                else:
                    print("Some Aider tools failed to register")
        except ImportError:
            print("Aider bridge not available - skipping tool registration")

def main():
    """Main entry point."""
    # Create application
    app = Application()
    
    # Test associative matching
    if len(sys.argv) > 1 and sys.argv[1] == "--test-matching":
        test_query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "passthrough handler"
        print(f"\nTesting associative matching with query: '{test_query}'")
        
        # Import and execute the template directly
        from task_system.templates.associative_matching import execute_template
        matching_files = execute_template(test_query, app.memory_system)
        
        print(f"Found {len(matching_files)} relevant files:")
        for i, file_path in enumerate(matching_files):
            print(f"{i+1}. {file_path}")
        
        return
    
    # Start REPL
    print("\nStarting REPL...")
    from repl.repl import Repl
    repl = Repl(app)
    repl.start()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
