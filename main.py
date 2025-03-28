"""Main entry point for the application."""
import sys
import os
import json

def main():
    """Main entry point."""
    # Import components
    from memory.memory_system import MemorySystem
    from task_system.task_system import TaskSystem
    from repl.repl import Repl
    from memory.indexers.git_repository_indexer import GitRepositoryIndexer
    from task_system.templates.associative_matching import register_template
    
    # Initialize components
    memory_system = MemorySystem()
    task_system = TaskSystem()
    
    # Register templates
    register_template(task_system)
    
    # Index git repository
    repo_path = os.path.abspath(".")  # Current directory
    
    print("Indexing repository...")
    indexer = GitRepositoryIndexer(repo_path)
    # Configure indexer to exclude some common directories
    indexer.exclude_patterns = ["**/__pycache__/**", "**/node_modules/**", "**/.git/**"]
    file_metadata = indexer.index_repository(memory_system)
    
    # Test associative matching
    if len(sys.argv) > 1 and sys.argv[1] == "--test-matching":
        test_query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "passthrough handler"
        print(f"\nTesting associative matching with query: '{test_query}'")
        
        # Import and execute the template directly
        from task_system.templates.associative_matching import execute_template
        matching_files = execute_template(test_query, memory_system)
        
        print(f"Found {len(matching_files)} relevant files:")
        for i, file_path in enumerate(matching_files):
            print(f"{i+1}. {file_path}")
        
        return
    
    # Start REPL
    print("\nStarting REPL...")
    repl = Repl(task_system, memory_system)
    repl.start()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
