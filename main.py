"""Main entry point for the application."""
import sys
import os

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
    indexer = GitRepositoryIndexer(repo_path)
    # Note: index_repository will update the memory_system directly
    indexer.index_repository(memory_system)
    
    # Start REPL
    repl = Repl(task_system, memory_system)
    repl.start()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
