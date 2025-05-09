#!/usr/bin/env python3
"""
Test script for Anthropic Tool Use integration.

This script tests the integration of Anthropic Tool Use with Aider tools.
"""

import os
import sys
import json
from typing import Dict, Any, List, Optional

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

def test_tool_registration_anthropic_format():
    """Test registration of tools in Anthropic format."""
    from handler.passthrough_handler import PassthroughHandler
    from aider_bridge.bridge import AiderBridge
    from aider_bridge.tools import create_aider_tool_specs
    
    # Create mock components
    class MockMemorySystem:
        def get_relevant_context_for(self, input_data):
            class MockResult:
                def __init__(self):
                    self.context = "Mock context"
                    self.matches = [("test_file.py", 0.9)]
            return MockResult()
    
    class MockTaskSystem:
        pass
    
    # Create handler and bridge
    memory_system = MockMemorySystem()
    task_system = MockTaskSystem()
    handler = PassthroughHandler(task_system, memory_system)
    bridge = AiderBridge(memory_system)
    
    # Enable debug mode
    handler.set_debug_mode(True)
    
    # Get tool specifications
    tool_specs = create_aider_tool_specs()
    
    # Define mock executor functions
    def mock_interactive_executor(input_data):
        return {
            "status": "success",
            "content": f"Interactive session with: {input_data['query']}",
            "notes": {"session_id": "test-session"}
        }
    
    def mock_automatic_executor(input_data):
        return {
            "status": "success",
            "content": f"Automatic task executed: {input_data['prompt']}",
            "notes": {"files_modified": ["test_file.py"]}
        }
    
    # Register tools
    interactive_result = handler.register_tool(tool_specs["aiderInteractive"], mock_interactive_executor)
    automatic_result = handler.register_tool(tool_specs["aiderAutomatic"], mock_automatic_executor)
    
    print(f"Interactive tool registration: {'Success' if interactive_result else 'Failed'}")
    print(f"Automatic tool registration: {'Success' if automatic_result else 'Failed'}")
    
    # Verify tool registration
    assert "aiderInteractive" in handler.tool_executors
    assert "aiderAutomatic" in handler.tool_executors
    
    print("✅ Tool registration in Anthropic format successful")
    return handler

## The tests for tool invocation based on _check_for_tool_invocation have been removed
## because the handler API was refactored and that private method is no longer available.

if __name__ == "__main__":
    print("Deprecated tool invocation tests have been removed.")

def test_end_to_end_flow():
    """Test the end-to-end flow with model provider and handler."""
    from handler.passthrough_handler import PassthroughHandler
    from handler.model_provider import ClaudeProvider
    from aider_bridge.bridge import AiderBridge
    from aider_bridge.tools import register_aider_tools
    
    # Create mock components
    class MockMemorySystem:
        def get_relevant_context_for(self, input_data):
            class MockResult:
                def __init__(self):
                    self.context = "Mock context"
                    self.matches = [("test_file.py", 0.9)]
            return MockResult()
    
    class MockTaskSystem:
        pass
    
    # Create components
    memory_system = MockMemorySystem()
    task_system = MockTaskSystem()
    model_provider = ClaudeProvider()  # Will use mock mode without API key
    handler = PassthroughHandler(task_system, memory_system, model_provider)
    bridge = AiderBridge(memory_system)
    
    # Enable debug mode
    handler.set_debug_mode(True)
    
    # Register tools
    register_results = register_aider_tools(handler, bridge)
    print(f"Tool registration results: {register_results}")
    
    # Mock the tool executors for testing
    for tool_name in handler.tool_executors:
        original_executor = handler.tool_executors[tool_name]
        
        def mock_executor(input_data, tool_name=tool_name):
            print(f"Executing {tool_name} with input: {input_data}")
            return {
                "status": "success",
                "content": f"Mock execution of {tool_name}",
                "notes": {"tool": tool_name, "input": input_data}
            }
        
        handler.tool_executors[tool_name] = mock_executor
    
    # Test query that should trigger tool use
    query = "Add docstrings to all functions in test_file.py"
    
    # Process query
    result = handler.handle_query(query)
    
    print(f"\nQuery result: {result}")
    print(f"Content: {result.get('content', 'No content')}")
    
    print("✅ End-to-end flow test completed")
    return result

def main():
    """Run all tests."""
    print("Running Anthropic Tool Use integration tests...\n")
    
    # Run tests
    test_tool_registration_anthropic_format()
    test_end_to_end_flow()
    
    print("\nAll tests passed! ✅")

if __name__ == "__main__":
    main()
