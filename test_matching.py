#!/usr/bin/env python3
"""Test script for associative matching functionality."""
import sys
import os
import json

def test_associative_matching(query, repo_path="."):
    """Test associative matching with the given query.
    
    Args:
        query: Query to test
        repo_path: Repository path to index
    """
    # Import components
    from memory.memory_system import MemorySystem
    from memory.indexers.git_repository_indexer import GitRepositoryIndexer
    from task_system.templates.associative_matching import execute_template
    
    # Initialize memory system
    memory_system = MemorySystem()
    
    # Index git repository
    print(f"Indexing repository: {repo_path}")
    indexer = GitRepositoryIndexer(repo_path)
    # Configure indexer to exclude some common directories
    indexer.exclude_patterns = ["**/__pycache__/**", "**/node_modules/**", "**/.git/**"]
    file_metadata = indexer.index_repository(memory_system)
    
    # Execute template
    print(f"\nExecuting associative matching for query: '{query}'")
    matching_files = execute_template(query, memory_system)
    
    # Display results
    print(f"\nFound {len(matching_files)} relevant files:")
    for i, file_path in enumerate(matching_files):
        rel_path = os.path.relpath(file_path, os.path.abspath(repo_path))
        print(f"{i+1}. {rel_path}")
        
        # Show file metadata
        if i < 3:  # Only show metadata for top 3 results
            metadata = file_metadata.get(file_path, "No metadata available")
            print(f"   Metadata: {metadata.splitlines()[0]}")
            print(f"   {'-' * 40}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_matching.py <query> [repo_path]")
        sys.exit(1)
    
    query = sys.argv[1]
    repo_path = sys.argv[2] if len(sys.argv) > 2 else "."
    
    try:
        test_associative_matching(query, repo_path)
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
