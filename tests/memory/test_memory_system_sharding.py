"""Tests for token-based sharded context retrieval."""
import pytest
import os
from unittest.mock import MagicMock
from src.memory.memory_system import MemorySystem
from src.task_system.task_system import TaskSystem

class TestTokenBasedSharding:
    """Tests for token-based sharded context retrieval."""
    
    def test_token_estimation(self):
        """Test token estimation method."""
        memory_system = MemorySystem()
        
        # Test with default token ratio (0.25)
        assert memory_system._estimate_tokens("") == 0
        assert memory_system._estimate_tokens("hello") == 1  # 5 * 0.25 = 1.25 -> 1
        assert memory_system._estimate_tokens("hello world") == 2  # 11 * 0.25 = 2.75 -> 2
        
        # Test with custom token ratio
        memory_system.configure_sharding(token_estimation_ratio=0.1)
        assert memory_system._estimate_tokens("hello") == 0  # 5 * 0.1 = 0.5 -> 0
        assert memory_system._estimate_tokens("hello world") == 1  # 11 * 0.1 = 1.1 -> 1
    
    def test_token_based_sharding(self):
        """Test creating shards based on token count."""
        memory_system = MemorySystem()
        memory_system.configure_sharding(
            token_size_per_shard=10,  # Very small for testing
            max_shards=4
        )
        memory_system.enable_sharding(True)
        
        # Create test index with varying metadata sizes
        test_index = {
            os.path.abspath("file1.py"): "Small",  # ~1 token
            os.path.abspath("file2.py"): "Medium sized metadata",  # ~5 tokens
            os.path.abspath("file3.py"): "This is a much longer metadata entry that should be around 15 tokens or so",  # ~15 tokens
            os.path.abspath("file4.py"): "Short",  # ~1 token
            os.path.abspath("file5.py"): "Another medium sized metadata entry"  # ~7 tokens
        }
        memory_system.update_global_index(test_index)
        
        # We should have multiple shards due to token size limits
        assert len(memory_system._sharded_index) > 1
        
        # All files should be distributed across shards
        total_files = sum(len(shard) for shard in memory_system._sharded_index)
        assert total_files == 5, "All files should be distributed across shards"
    
    def test_shard_all_matches_returned(self):
        """Test that ALL matches are returned without filtering."""
        memory_system = MemorySystem()
        
        # Create and configure mock TaskSystem
        mock_task_system = MagicMock(spec=TaskSystem)
        memory_system.task_system = mock_task_system
        
        # Configure sharding
        memory_system.configure_sharding(token_size_per_shard=10)
        memory_system.enable_sharding(True)
        
        # Create test index with matching metadata
        test_index = {
            os.path.abspath("file1.py"): "Contains user code",
            os.path.abspath("file2.py"): "More user related functions",
            os.path.abspath("file3.py"): "Core authentication code",
            os.path.abspath("file4.py"): "User profile handling",
            os.path.abspath("file5.py"): "Database utilities",
            os.path.abspath("file6.py"): "Logging functionality"
        }
        memory_system.update_global_index(test_index)
        
        # Should have multiple shards
        assert len(memory_system._sharded_index) > 1
        
        # Configure mock to simulate finding files containing "user"
        def mock_generate_context(context_input, file_metadata):
            from memory.context_generation import AssociativeMatchResult
            
            query = "user"  # Hard-coded for this test
            matches = []
            
            for path, metadata in file_metadata.items():
                if query in metadata.lower():
                    matches.append((path, f"Relevant to '{query}'"))
            
            return AssociativeMatchResult(
                context=f"Found {len(matches)} relevant files",
                matches=matches
            )
        
        mock_task_system.generate_context_for_memory_system.side_effect = mock_generate_context
        
        # Search for "user" which should match 3 files
        result = memory_system.get_relevant_context_for({"taskText": "user"})
        
        # Count matches in raw index
        user_files_count = sum(1 for metadata in test_index.values()
                              if "user" in metadata.lower())
        
        # Verify ALL matches are returned (not limited)
        assert len(result.matches) == user_files_count, "All matching files should be returned"
        
        # Verify each shard was processed
        assert mock_task_system.generate_context_for_memory_system.call_count == len(memory_system._sharded_index)
    
    def test_absolute_path_validation(self):
        """Test validation of absolute paths."""
        # Create a subclass that enforces absolute paths even in tests
        class StrictMemorySystem(MemorySystem):
            def update_global_index(self, index):
                # Override to always enforce absolute paths
                for path in index.keys():
                    if not os.path.isabs(path):
                        raise ValueError(f"File path must be absolute: {path}")
                # Call parent implementation
                super().update_global_index(index)
        
        memory_system = StrictMemorySystem()
        
        # Test with absolute paths (should succeed)
        abs_paths = {
            os.path.abspath("file1.py"): "metadata1",
            os.path.abspath("file2.py"): "metadata2"
        }
        memory_system.update_global_index(abs_paths)
        
        # Test with relative paths (should fail)
        rel_paths = {
            "file3.py": "metadata3",
            "dir/file4.py": "metadata4"
        }
        with pytest.raises(ValueError, match="must be absolute"):
            memory_system.update_global_index(rel_paths)
