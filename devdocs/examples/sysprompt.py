#!/usr/bin/env python3
"""
Interactive example demonstrating the Hierarchical System Prompt Pattern.

This script allows you to experiment with different combinations of base system prompts,
template-specific prompts, and file contexts to see how they're combined.

Run this script and follow the interactive prompts to explore the pattern.
"""

import os
import sys
import json
from textwrap import dedent
from typing import Dict, List, Optional, Any

# Add parent directory to path to allow imports from the project
# (Only needed for the example script)
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Mock classes to simulate the project structure
class MockMemorySystem:
    """Mock MemorySystem for demonstration."""
    def get_relevant_context_for(self, input_data):
        """Return mock context result."""
        class MockResult:
            def __init__(self):
                self.context = "Mock context"
                self.matches = [
                    ("main.py", "main file"),
                    ("utils.py", "utility functions")
                ]
        return MockResult()

class MockTaskSystem:
    """Mock TaskSystem for demonstration."""
    def __init__(self):
        self.templates = {
            "atomic:code_editing": {
                "type": "atomic",
                "subtype": "code_editing",
                "description": "Edit code based on user instructions",
                "system_prompt": dedent("""
                When editing code:
                - Maintain the existing style and conventions
                - Add clear comments explaining significant changes
                - Consider edge cases and error handling
                - Always test the code mentally before providing it
                """).strip()
            },
            "atomic:file_search": {
                "type": "atomic", 
                "subtype": "file_search",
                "description": "Find relevant files for a given query",
                "system_prompt": dedent("""
                When searching for relevant files:
                - Consider file names, extensions, and content
                - Look for semantic relevance beyond exact keyword matches
                - Prioritize files most directly relevant to the query
                - Include both implementation files and tests when appropriate
                """).strip()
            },
            "atomic:documentation": {
                "type": "atomic",
                "subtype": "documentation",
                "description": "Generate or update documentation",
                "system_prompt": dedent("""
                When working with documentation:
                - Use clear, concise language
                - Include examples for complex concepts
                - Follow standard documentation formats
                - Ensure backward compatibility with existing docs
                """).strip()
            }
        }
    
    def find_matching_tasks(self, input_text, memory_system):
        """Find matching templates based on a provided input string."""
        # Simple keyword matching for demonstration
        keywords = {
            "code": "atomic:code_editing",
            "edit": "atomic:code_editing",
            "function": "atomic:code_editing",
            "file": "atomic:file_search",
            "find": "atomic:file_search",
            "search": "atomic:file_search",
            "document": "atomic:documentation",
            "docs": "atomic:documentation",
            "readme": "atomic:documentation"
        }
        
        matches = []
        for word in input_text.lower().split():
            if word in keywords:
                template_key = keywords[word]
                template = self.templates.get(template_key)
                if template:
                    # Simple word count based scoring
                    score = sum(1 for w in input_text.lower().split() 
                               if w in template["description"].lower())
                    matches.append({
                        "task": template,
                        "score": score,
                        "taskType": "atomic",
                        "subtype": template_key.split(":")[1]
                    })
        
        # Remove duplicates and sort by score
        unique_matches = {}
        for match in matches:
            key = match["task"]["description"]
            if key not in unique_matches or match["score"] > unique_matches[key]["score"]:
                unique_matches[key] = match
        
        return sorted(unique_matches.values(), key=lambda x: x["score"], reverse=True)

class BaseHandler:
    """Mock BaseHandler for demonstration."""
    def __init__(self, task_system, memory_system, config=None):
        self.task_system = task_system
        self.memory_system = memory_system
        self.config = config or {}
        self.base_system_prompt = self.config.get("base_system_prompt", dedent("""
        You are a helpful assistant that responds to user queries.
        Follow these general guidelines:
        - Provide accurate and relevant information
        - Answer concisely when appropriate, detailed when necessary
        - Maintain a helpful and friendly tone
        - Acknowledge when you don't know something
        """).strip())
    
    def _build_system_prompt(self, template=None, file_context=None):
        """Build the complete system prompt by combining base, template, and file context."""
        # Start with base system prompt
        system_prompt = self.base_system_prompt
        
        # Add template-specific system prompt if available
        if template and "system_prompt" in template and template["system_prompt"]:
            system_prompt = f"{system_prompt}\n\n===\n\n{template['system_prompt']}"
        
        # Add file context if available
        if file_context:
            system_prompt = f"{system_prompt}\n\nRelevant files:\n{file_context}"
        
        return system_prompt
    
    def _get_relevant_files(self, query):
        """Get relevant files from memory system based on query."""
        context_input = {
            "taskText": query,
            "inheritedContext": ""
        }
        
        context_result = self.memory_system.get_relevant_context_for(context_input)
        
        # Extract file paths from matches
        relevant_files = [match[0] for match in context_result.matches]
        return relevant_files
    
    def _create_file_context(self, file_paths):
        """Create a context string from file paths."""
        if not file_paths:
            return ""
        
        file_contexts = []
        for path in file_paths:
            # In a real implementation, this would read actual file content
            content = f"Mock content for {path}"
            file_contexts.append(f"File: {path}\n```\n{content}\n```\n")
        
        return "\n".join(file_contexts)

class PassthroughHandler(BaseHandler):
    """Mock PassthroughHandler for demonstration."""
    def __init__(self, task_system, memory_system, config=None):
        super().__init__(task_system, memory_system, config)
        
        # Extend base system prompt with passthrough-specific instructions
        passthrough_extension = dedent("""
        When referring to code or files, cite the relevant file paths.
        Be precise and helpful, focusing on the user's specific question.
        """).strip()
        
        self.base_system_prompt = f"{self.base_system_prompt}\n\n{passthrough_extension}"
    
    def _find_matching_template(self, query):
        """Find a matching template for the query."""
        if self.task_system and hasattr(self.task_system, 'find_matching_tasks'):
            try:
                matching_tasks = self.task_system.find_matching_tasks(query, self.memory_system)
                if matching_tasks:
                    print(f"Found matching template: {matching_tasks[0]['task']['description']}")
                    return matching_tasks[0]["task"]
            except Exception as e:
                print(f"Error finding matching template: {str(e)}")
        
        return None
    
    def handle_query(self, query):
        """Handle a raw text query."""
        # Find matching template
        matching_template = self._find_matching_template(query)
        
        # Get relevant files
        relevant_files = self._get_relevant_files(query)
        
        # Create file context
        file_context = self._create_file_context(relevant_files)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(matching_template, file_context)
        
        return {
            "query": query,
            "template": matching_template["description"] if matching_template else None,
            "relevant_files": relevant_files,
            "system_prompt": system_prompt
        }

def print_fancy_header(text):
    """Print a fancy header for the interactive example."""
    width = 80
    print("\n" + "=" * width)
    print(text.center(width))
    print("=" * width + "\n")

def print_system_prompt(prompt):
    """Print a formatted system prompt."""
    print("\nSystem Prompt:")
    print("-" * 80)
    print(prompt)
    print("-" * 80 + "\n")

def interactive_example():
    """Run interactive example of hierarchical system prompts."""
    print_fancy_header("Hierarchical System Prompt Pattern Demo")
    
    print(dedent("""
    This interactive example demonstrates how the Hierarchical System Prompt Pattern works.
    You can experiment with different queries to see how templates are matched and
    how system prompts are combined.
    """))
    
    # Initialize components
    memory_system = MockMemorySystem()
    task_system = MockTaskSystem()
    
    # Create default handler
    config = {
        "base_system_prompt": dedent("""
        You are a helpful assistant that responds to user queries.
        Follow these general guidelines:
        - Provide accurate and relevant information
        - Answer concisely when appropriate, detailed when necessary
        - Maintain a helpful and friendly tone
        - Acknowledge when you don't know something
        """).strip()
    }
    handler = PassthroughHandler(task_system, memory_system, config)
    
    # Main interaction loop
    while True:
        print("\nAvailable Templates:")
        for key, template in task_system.templates.items():
            print(f"- {key}: {template['description']}")
            
        print("\nEnter a query to see how the system prompt would be built.")
        print("Example queries: 'edit the main function', 'find files for authentication', 'update docs'")
        print("Type 'exit', 'quit', or 'q' to exit.")
            
        query = input("\nQuery> ")
        if query.lower() in ['exit', 'quit', 'q']:
            break
        
        # Process query
        result = handler.handle_query(query)
        
        # Display results
        if result["template"]:
            print(f"\nMatched template: {result['template']}")
        else:
            print("\nNo matching template found. Using base system prompt only.")
            
        if result["relevant_files"]:
            print(f"\nRelevant files: {', '.join(result['relevant_files'])}")
        else:
            print("\nNo relevant files found.")
            
        print_system_prompt(result["system_prompt"])
        
        # Options for next steps
        while True:
            print("What would you like to do next?")
            print("1. Enter a new query")
            print("2. Modify base system prompt")
            print("3. Show template details")
            print("4. Exit")
            
            choice = input("Choice [1-4]> ")
            
            if choice == '1':
                break
            elif choice == '2':
                new_base = input("\nEnter new base system prompt (or 'default' to reset)> ")
                if new_base.lower() == 'default':
                    handler.base_system_prompt = config["base_system_prompt"]
                else:
                    handler.base_system_prompt = new_base
                print("\nBase system prompt updated.")
            elif choice == '3':
                if result["template"]:
                    for key, template in task_system.templates.items():
                        if template["description"] == result["template"]:
                            print("\nTemplate Details:")
                            print(json.dumps(template, indent=2))
                            break
                else:
                    print("\nNo template was matched for this query.")
            elif choice == '4':
                return
            else:
                print("Invalid choice. Please try again.")

if __name__ == "__main__":
    interactive_example()
