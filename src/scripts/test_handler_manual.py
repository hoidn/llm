#!/usr/bin/env python
"""
Manual test script for the provider-agnostic handler implementation.

This script demonstrates the functionality of the BaseHandler and
PassthroughHandler classes with real components.
"""
import os
import sys
import argparse
from typing import Dict, Any, List

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from handler.base_handler import BaseHandler
from handler.passthrough_handler import PassthroughHandler
from handler.model_provider import ClaudeProvider

# Import actual components if available
try:
    from memory.memory_system import MemorySystem
    from task_system.task_system import TaskSystem
    memory_imports_success = True
except ImportError:
    print("Warning: Could not import MemorySystem or TaskSystem. Using simplified test.")
    memory_imports_success = False

def create_simple_tool():
    """Create a simple tool for testing."""
    def echo_tool(input_data):
        """Echo tool implementation."""
        if isinstance(input_data, dict):
            query = input_data.get("query") or input_data.get("prompt") or "No input"
            print(f"[Tool] Echo tool received: {query}")
            return {
                "status": "success",
                "content": f"Echo: {query}",
                "metadata": {"tool_execution": "success"}
            }
        return {
            "status": "error",
            "content": "Invalid input format",
            "metadata": {"error": "Invalid input format"}
        }
    
    return echo_tool

def main():
    """Run the manual test."""
    parser = argparse.ArgumentParser(description="Test the provider-agnostic handler implementation")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--api-key", help="Anthropic API key (optional, will use env var if not provided)")
    args = parser.parse_args()
    
    # Set up API key if provided
    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key
    
    # Create provider
    provider = ClaudeProvider()
    
    # Create handler with real or simplified components
    if memory_imports_success:
        # Use real components
        memory_system = MemorySystem()
        task_system = TaskSystem()
        handler = PassthroughHandler(task_system, memory_system, provider)
    else:
        # Use simplified approach
        handler = PassthroughHandler(None, None, provider)
    
    # Enable debug mode if requested
    if args.debug:
        handler.set_debug_mode(True)
        print("Debug mode enabled")
    
    # Register a simple tool
    tool_spec = {
        "name": "echo",
        "description": "Echo the input back to the user",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The text to echo"
                }
            },
            "required": ["query"]
        }
    }
    
    echo_tool = create_simple_tool()
    handler.register_tool(tool_spec, echo_tool)
    print("Registered 'echo' tool")
    
    # Interactive loop
    print("\nEnter queries (type 'exit' to quit):")
    while True:
        try:
            query = input("\n> ")
            if query.lower() in ("exit", "quit"):
                break
                
            if query.lower() == "reset":
                handler.reset_conversation()
                print("Conversation reset")
                continue
                
            # Process the query
            result = handler.handle_query(query)
            
            # Display the result
            print("\nResponse:")
            print(result["content"])
            
            if "metadata" in result and result["metadata"]:
                print("\nMetadata:")
                for key, value in result["metadata"].items():
                    print(f"  {key}: {value}")
                    
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
