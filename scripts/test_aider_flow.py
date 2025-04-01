#!/usr/bin/env python3
"""
Test script for Aider integration workflows.

This script tests the complete flow of Aider integration with sample code.
"""

import os
import sys
import tempfile
import shutil
import subprocess
from typing import Dict, Any, List, Optional

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Sample code for testing
SAMPLE_CODE = {
    "calculator.py": """
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
""",
    "utils.py": """
def is_even(num):
    return num % 2 == 0

def is_prime(num):
    if num < 2:
        return False
    for i in range(2, int(num ** 0.5) + 1):
        if num % i == 0:
            return False
    return True

def factorial(n):
    if n == 0 or n == 1:
        return 1
    else:
        return n * factorial(n - 1)
""",
    "main.py": """
from calculator import add, subtract, multiply, divide
from utils import is_even, is_prime, factorial

def main():
    print("Calculator and Utils Demo")
    print("------------------------")
    
    a, b = 10, 5
    print(f"{a} + {b} = {add(a, b)}")
    print(f"{a} - {b} = {subtract(a, b)}")
    print(f"{a} * {b} = {multiply(a, b)}")
    print(f"{a} / {b} = {divide(a, b)}")
    
    print(f"Is {a} even? {is_even(a)}")
    print(f"Is {b} prime? {is_prime(b)}")
    print(f"Factorial of 5: {factorial(5)}")

if __name__ == "__main__":
    main()
"""
}

def setup_test_environment():
    """Set up a test environment with sample code files."""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp(prefix="aider_test_")
    print(f"Created test directory: {temp_dir}")
    
    # Create sample files
    for filename, content in SAMPLE_CODE.items():
        file_path = os.path.join(temp_dir, filename)
        with open(file_path, "w") as f:
            f.write(content)
        print(f"Created sample file: {file_path}")
    
    # Initialize git repository
    subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True, capture_output=True)
    
    print(f"Initialized git repository in {temp_dir}")
    return temp_dir

def test_automatic_mode(app, test_dir):
    """Test Aider in automatic mode with a simple code edit."""
    print("\n=== Testing Automatic Mode ===")
    
    # Create a simple edit task
    task = "Add docstrings to all functions in calculator.py"
    print(f"Task: {task}")
    
    # Get file context
    file_path = os.path.join(test_dir, "calculator.py")
    
    # Execute automatic task
    try:
        result = app.aider_bridge.execute_automatic_task(task, [file_path])
        
        print("\nResult:")
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"Content: {result.get('content', 'No content')}")
        
        if 'notes' in result and 'files_modified' in result['notes']:
            print(f"Files modified: {result['notes']['files_modified']}")
            
            # Show file content after modification
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    print("\nUpdated file content:")
                    print(f.read())
        
        return result
    except Exception as e:
        print(f"Error in automatic mode test: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return {"status": "error", "error": str(e)}

def test_interactive_mode(app, test_dir):
    """Test Aider in interactive mode with a complex refactoring task."""
    print("\n=== Testing Interactive Mode ===")
    
    # Create a complex refactoring task
    task = "Refactor the factorial function in utils.py to use iteration instead of recursion"
    print(f"Task: {task}")
    
    # Get file context
    file_path = os.path.join(test_dir, "utils.py")
    
    # Start interactive session
    try:
        print(f"Adding file to context: {file_path}")
        result = app.aider_bridge.start_interactive_session(task, [file_path])
        
        print("\nResult:")
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"Content: {result.get('content', 'No content')}")
        
        # Show file content after modification
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                print("\nFile content after session:")
                print(f.read())
        
        return result
    except Exception as e:
        print(f"Error in interactive mode test: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return {"status": "error", "error": str(e)}

def test_direct_aider_command(app, test_dir):
    """Test direct Aider command handling."""
    print("\n=== Testing Direct Aider Command ===")
    
    # Create a direct Aider command
    command = "/aider interactive Add type hints to all functions in main.py"
    print(f"Command: {command}")
    
    # Get file context
    file_path = os.path.join(test_dir, "main.py")
    app.aider_bridge.set_file_context([file_path])
    
    # Handle the command through the passthrough handler
    try:
        result = app.handle_query(command)
        
        print("\nResult:")
        print(f"Content: {result.get('content', 'No content')}")
        
        # Show file content after modification
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                print("\nFile content after command:")
                print(f.read())
        
        return result
    except Exception as e:
        print(f"Error in direct command test: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return {"status": "error", "error": str(e)}

def cleanup_test_environment(test_dir):
    """Clean up the test environment."""
    try:
        shutil.rmtree(test_dir)
        print(f"\nCleaned up test directory: {test_dir}")
    except Exception as e:
        print(f"Error cleaning up test directory: {str(e)}")

def main():
    """Run the test script."""
    print("=== Aider Integration Test Script ===\n")
    
    # Set up test environment
    test_dir = setup_test_environment()
    
    try:
        # Import application
        from main import Application
        
        # Initialize application
        app = Application()
        
        # Index the test repository
        app.index_repository(test_dir)
        
        # Run tests
        automatic_result = test_automatic_mode(app, test_dir)
        interactive_result = test_interactive_mode(app, test_dir)
        command_result = test_direct_aider_command(app, test_dir)
        
        # Print summary
        print("\n=== Test Summary ===")
        print(f"Automatic mode: {automatic_result.get('status', 'unknown')}")
        print(f"Interactive mode: {interactive_result.get('status', 'unknown')}")
        print(f"Direct command: {command_result.get('status', 'unknown') if isinstance(command_result, dict) else 'completed'}")
        
    finally:
        # Clean up
        cleanup_test_environment(test_dir)

if __name__ == "__main__":
    main()
