"""Integration tests for sharded context retrieval."""
import pytest
import os
import tempfile
import shutil
from unittest.mock import MagicMock

from src.memory.memory_system import MemorySystem
from src.memory.indexers.git_repository_indexer import GitRepositoryIndexer

class TestShardedRetrieval:
    """Integration tests for sharded context retrieval."""
    
    @pytest.fixture
    def large_mock_repo(self):
        """Create a temporary repository with enough files to trigger sharding."""
        # Create a temporary directory
        repo_dir = tempfile.mkdtemp()
        
        # Create a .git directory to make it look like a git repo
        os.makedirs(os.path.join(repo_dir, ".git"))
        
        # Create multiple subdirectories
        subdirs = ["src", "src/components", "src/utils", "tests", "docs"]
        for subdir in subdirs:
            os.makedirs(os.path.join(repo_dir, subdir))
        
        # Create a variety of files with different sizes
        for i in range(50):  # Enough files to trigger sharding
            category = "user" if i % 5 == 0 else "auth" if i % 7 == 0 else "system"
            size = "small" if i % 3 == 0 else "medium" if i % 3 == 1 else "large"
            
            # Choose directory based on number
            if i % 4 == 0:
                directory = os.path.join(repo_dir, "src")
            elif i % 4 == 1:
                directory = os.path.join(repo_dir, "src/components")
            elif i % 4 == 2:
                directory = os.path.join(repo_dir, "src/utils")
            else:
                directory = os.path.join(repo_dir, "tests")
                
            # Create file with varying content to trigger different token counts
            file_path = os.path.join(directory, f"file_{i}.py")
            with open(file_path, "w") as f:
                # Write different amounts of content based on size
                if size == "small":
                    f.write(f"# {category} functionality\ndef function_{i}():\n    pass")
                elif size == "medium":
                    f.write(f"""# {category} functionality
def function_{i}(param1, param2):
    \"\"\"This is a {category} related function.
    
    It does some things related to {category}.
    \"\"\"
    # Implementation
    return param1 + param2
                    """)
                else:  # large
                    f.write(f"""# {category} functionality module
\"\"\"
This module contains functionality related to {category}.
It provides several functions and classes for working with {category} data.

Main components:
- function_{i}: Primary function
- Helper_{i}: Helper class
- utilities_{i}: Utility functions
\"\"\"

class Helper_{i}:
    \"\"\"A helper class for {category} operations.\"\"\"
    
    def __init__(self, config):
        self.config = config
        self.data = []
        
    def process(self, item):
        \"\"\"Process an item using {category} logic.\"\"\"
        return item

def function_{i}(param1, param2, param3=None):
    \"\"\"
    Primary function for {category} operations.
    
    Args:
        param1: First parameter
        param2: Second parameter
        param3: Optional third parameter
        
    Returns:
        Processed result
    \"\"\"
    helper = Helper_{i}(param1)
    return helper.process(param2)

def utilities_{i}():
    \"\"\"Additional utilities for {category}.\"\"\"
    return {{}}
                    """)
        
        # Create a README.md in docs
        readme_path = os.path.join(repo_dir, "docs", "README.md")
        with open(readme_path, "w") as f:
            f.write(f"""# Project Documentation
            
## Overview

This project contains functionality for:
- User management
- Authentication
- System operations

## Usage

See individual modules for detailed documentation.
            """)
            
        yield repo_dir
        
        # Clean up
        shutil.rmtree(repo_dir)
    
    def test_sharded_retrieval_with_large_repo(self, large_mock_repo):
        """Test sharded retrieval with a large mock repository."""
        # Create memory system with token-based sharding enabled
        memory_system = MemorySystem()
        
        # Create and configure mock TaskSystem
        mock_task_system = MagicMock(spec=TaskSystem)
        memory_system.task_system = mock_task_system
        
        # Configure mock to simulate finding relevant files based on keyword matching
        def mock_generate_context(context_input, file_metadata):
            from memory.context_generation import AssociativeMatchResult
            
            query = context_input.template_description.lower()
            matches = []
            
            for path, metadata in file_metadata.items():
                if query in metadata.lower():
                    matches.append((path, f"Relevant to '{query}'"))
            
            return AssociativeMatchResult(
                context=f"Found {len(matches)} relevant files",
                matches=matches
            )
        
        mock_task_system.generate_context_for_memory_system.side_effect = mock_generate_context
        
        memory_system.configure_sharding(
            token_size_per_shard=1000,  # Small enough to trigger multiple shards
            max_shards=5
        )
        memory_system.enable_sharding(True)
        
        # We don't need the handler when we have task_system
        memory_system.handler = None
        
        # Create a repository indexer
        indexer = GitRepositoryIndexer(large_mock_repo)
        indexer.include_patterns = ["**/*.py", "**/*.md"]  # Include Python and Markdown files
        
        # Index the repository
        file_metadata = indexer.index_repository(memory_system)
        
        # Verify indexing worked
        assert len(file_metadata) > 0, "Repository indexing should find files"
        assert len(memory_system.global_index) > 0, "Global index should be populated"
        
        # Verify multiple shards were created
        assert len(memory_system._sharded_index) > 1, "Multiple shards should be created"
        
        # Test queries for different categories
        categories = ["user", "auth", "system"]
        for category in categories:
            # Perform query
            result = memory_system.get_relevant_context_for({"taskText": category})
            
            # Count expected matches - same logic as used in mock_generate_context
            expected_count = sum(1 for metadata in file_metadata.values()
                                if category in metadata.lower())
            
            # Verify correct results
            assert len(result.matches) == expected_count, f"All {category} files should be returned"
        
        # Test query with multiple terms
        result = memory_system.get_relevant_context_for({"taskText": "user function"})
        
        # Verify results
        assert len(result.matches) > 0, "Should find files matching 'user function'"
        
        # Test query with no matches
        result = memory_system.get_relevant_context_for({"taskText": "nonexistent feature xyz"})
        assert len(result.matches) == 0, "Should find no matches for nonexistent terms"
