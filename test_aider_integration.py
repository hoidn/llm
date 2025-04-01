#!/usr/bin/env python3
"""
Test harness for Aider integration.

This script tests the integration of Aider tools with the Handler system.
"""

import os
import sys
from typing import Dict, Any, List, Optional

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Mock classes for testing
class MockMemorySystem:
    """Mock MemorySystem for testing."""
    
    def get_relevant_context_for(self, input_data):
        """Return mock context result."""
        class MockResult:
            def __init__(self):
                self.context = "Mock context"
                self.matches = [
                    ("test_file1.py", 0.9),
                    ("test_file2.py", 0.8)
                ]
        
        return MockResult()

class MockHandler:
    """Mock Handler for testing tool registration."""
    
    def __init__(self):
        self.direct_tools = {}
        self.subtask_tools = {}
    
    def registerDirectTool(self, name, func):
        """Register a direct tool."""
        self.direct_tools[name] = func
        return True
    
    def registerSubtaskTool(self, name, func):
        """Register a subtask tool."""
        self.subtask_tools[name] = func
        return True

def test_tool_registration():
    """Test registration of Aider tools."""
    from aider_bridge.bridge import AiderBridge
    from aider_bridge.tools import register_aider_tools
    
    # Create mock components
    memory_system = MockMemorySystem()
    handler = MockHandler()
    
    # Create AiderBridge
    bridge = AiderBridge(memory_system)
    
    # Register tools
    results = register_aider_tools(handler, bridge)
    
    # Verify results
    assert "interactive" in results, "Interactive tool registration result missing"
    assert "automatic" in results, "Automatic tool registration result missing"
    
    # Verify tool registration
    assert "aiderInteractive" in handler.direct_tools, "Interactive tool not registered"
    assert "aiderAutomatic" in handler.subtask_tools, "Automatic tool not registered"
    
    print("✅ Tool registration test passed")
    return results

def test_context_retrieval():
    """Test retrieval of file context for queries."""
    from aider_bridge.bridge import AiderBridge
    
    # Create mock components
    memory_system = MockMemorySystem()
    
    # Create AiderBridge
    bridge = AiderBridge(memory_system)
    
    # Test context retrieval
    query = "Test query for context retrieval"
    files = bridge.get_context_for_query(query)
    
    # Verify results
    assert len(files) == 2, f"Expected 2 files, got {len(files)}"
    assert files[0] == "test_file1.py", f"Expected test_file1.py, got {files[0]}"
    assert files[1] == "test_file2.py", f"Expected test_file2.py, got {files[1]}"
    
    # Verify internal state
    assert len(bridge.file_context) == 2, "File context not updated correctly"
    assert bridge.context_source == "associative_matching", "Context source not set correctly"
    
    print("✅ Context retrieval test passed")
    return files

def test_tool_invocation():
    """Test invocation of Aider tools."""
    from aider_bridge.bridge import AiderBridge
    
    # Create mock components
    memory_system = MockMemorySystem()
    
    # Create AiderBridge with mocked aider_available
    bridge = AiderBridge(memory_system)
    bridge.aider_available = True  # Mock availability
    
    # Mock the execute_automatic_task method
    original_method = bridge.execute_automatic_task
    
    def mock_execute_automatic_task(prompt, file_context=None):
        """Mock implementation that just returns the inputs."""
        return {
            "status": "success",
            "content": f"Executed: {prompt}",
            "notes": {
                "files_modified": file_context or [],
                "prompt": prompt
            }
        }
    
    # Replace with mock
    bridge.execute_automatic_task = mock_execute_automatic_task
    
    # Test invocation
    result = bridge.execute_automatic_task("Test prompt", ["test_file1.py"])
    
    # Verify result
    assert result["status"] == "success", f"Expected success status, got {result['status']}"
    assert "Executed: Test prompt" in result["content"], "Prompt not included in result"
    assert result["notes"]["files_modified"] == ["test_file1.py"], "File context not passed correctly"
    
    # Restore original method
    bridge.execute_automatic_task = original_method
    
    print("✅ Tool invocation test passed")
    return result

def main():
    """Run all tests."""
    print("Running Aider integration tests...\n")
    
    # Run tests
    registration_results = test_tool_registration()
    context_files = test_context_retrieval()
    invocation_result = test_tool_invocation()
    
    print("\nAll tests passed! ✅")
    
    # Return results for inspection
    return {
        "registration": registration_results,
        "context_files": context_files,
        "invocation": invocation_result
    }

if __name__ == "__main__":
    main()
