# src/scripts/demo_sharded_retrieval.py
#!/usr/bin/env python
"""
Demonstration script for token-based sharded context retrieval.

This script shows how the sharded context retrieval works with a real repository.
Usage: python src/scripts/demo_sharded_retrieval.py [repository_path] [query]

Example:
    python src/scripts/demo_sharded_retrieval.py /path/to/repo "user authentication"
"""

import os
import sys
import time
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory.memory_system import MemorySystem
from memory.indexers.git_repository_indexer import GitRepositoryIndexer
from task_system.task_system import TaskSystem
from task_system.templates.associative_matching import register_template as register_associative_matching_template
from handler.passthrough_handler import PassthroughHandler
from config.logging_config import get_logger

def main():
    # Setup logging
    logger = get_logger(__name__)
    logger.setLevel(logging.INFO)
    
    # Get repository path and query from arguments
    if len(sys.argv) < 3:
        print("Usage: python -m src.scripts.demo_sharded_retrieval [repository_path] [query]")
        return
        
    repo_path = os.path.abspath(sys.argv[1])
    query = sys.argv[2]
    
    if not os.path.isdir(repo_path):
        print(f"Error: Repository path {repo_path} not found")
        return
    
    print(f"Demonstrating sharded context retrieval")
    print(f"Repository: {repo_path}")
    print(f"Query: {query}")
    print("-" * 50)
    
    # Instantiate TaskSystem and register necessary templates
    task_system = TaskSystem()
    register_associative_matching_template(task_system)
    
    # Create memory system with TaskSystem
    memory_system = MemorySystem(task_system=task_system)
    
    # Create a handler and link components
    handler = PassthroughHandler(task_system=task_system, memory_system=memory_system)
    memory_system.handler = handler
    task_system.memory_system = memory_system
    
    # Configure for demonstration
    memory_system.configure_sharding(
        token_size_per_shard=4000,
        max_shards=8,
        token_estimation_ratio=0.25,
        max_parallel_shards=4  # Limit to 4 parallel threads for the demo
    )
    
    # Index the repository
    indexer = GitRepositoryIndexer(repo_path)
    indexer.include_patterns = ["**/*.py", "**/*.md", "**/*.js", "**/*.java", "**/*.c", "**/*.cpp"]  
    
    print("Indexing repository...")
    start_time = time.time()
    file_metadata = indexer.index_repository(memory_system)
    index_time = time.time() - start_time
    print(f"Indexed {len(file_metadata)} files in {index_time:.2f} seconds")
    
    # Run with sharding disabled first
    memory_system.enable_sharding(False)
    print("\nRunning query with sharding DISABLED...")
    start_time = time.time()
    result_standard = memory_system.get_relevant_context_for({"taskText": query})
    standard_time = time.time() - start_time
    print(f"Found {len(result_standard.matches)} matches in {standard_time:.2f} seconds")
    
    # Now run with sharding enabled
    memory_system.enable_sharding(True)
    print("\nRunning query with sharding ENABLED (parallel processing)...")
    print(f"Created {len(memory_system._sharded_index)} shards with {memory_system._config['max_parallel_shards']} parallel workers")
    start_time = time.time()
    result_sharded = memory_system.get_relevant_context_for({"taskText": query})
    sharded_time = time.time() - start_time
    print(f"Found {len(result_sharded.matches)} matches in {sharded_time:.2f} seconds")
    
    # Compare results
    print("\nResults comparison:")
    print(f"Standard approach: {len(result_standard.matches)} matches in {standard_time:.2f} seconds")
    print(f"Sharded approach: {len(result_sharded.matches)} matches in {sharded_time:.2f} seconds")
    print(f"Speed difference: {standard_time/sharded_time:.2f}x")
    
    # Basic verification
    standard_paths = {match[0] for match in result_standard.matches}
    sharded_paths = {match[0] for match in result_sharded.matches}
    
    if standard_paths == sharded_paths:
        print("\n✅ Results match exactly")
    else:
        print("\n⚠️ Results differ:")
        only_in_standard = standard_paths - sharded_paths
        only_in_sharded = sharded_paths - standard_paths
        
        if only_in_standard:
            print(f"  Missing in sharded approach: {len(only_in_standard)} files")
            for path in list(only_in_standard)[:5]:  # Show first 5
                print(f"    - {path}")
                
        if only_in_sharded:
            print(f"  Extra in sharded approach: {len(only_in_sharded)} files")
            for path in list(only_in_sharded)[:5]:  # Show first 5
                print(f"    + {path}")
    
    # Show top matches
    if result_sharded.matches:
        print("\nTop 5 relevant files:")
        for i, match_item in enumerate(result_sharded.matches[:5], 1):
            # Check if the item is a sequence and has at least one element (the path)
            if isinstance(match_item, (list, tuple)) and len(match_item) > 0:
                path = match_item[0]  # Safely get the first element
                print(f"{i}. {path}")
            else:
                # Log if the item has an unexpected format
                print(f"{i}. [Malformed Match Item: {match_item}]")

if __name__ == "__main__":
    main()
