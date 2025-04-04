"""Associative matching template for finding relevant files."""
from typing import Dict, List, Any, Tuple
import re
import os
import math

# Template definition as a Python dictionary to be converted to XML
ASSOCIATIVE_MATCHING_TEMPLATE = {
    "type": "atomic",
    "subtype": "associative_matching",
    "name": "find_relevant_files",  # Unique template name
    "description": "Find relevant files for the given query",
    "parameters": {  # Structured parameters
        "query": {
            "type": "string",
            "description": "The user query or task to find relevant files for",
            "required": True
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of files to return",
            "default": 20
        }
    },
    "model": {  # Model preferences
        "preferred": "claude-3-5-sonnet",
        "fallback": ["gpt-4", "claude-3-haiku"]
    },
    "returns": {  # Return type definition
        "type": "array",
        "items": {"type": "string"},
        "description": "List of relevant file paths"
    },
    "context_management": {
        "inherit_context": "none",
        "accumulate_data": False,
        "fresh_context": "disabled"
    },
    "output_format": {
        "type": "json",
        "schema": "string[]"
    },
    "system_prompt": """When finding relevant files, consider:
- Direct keyword matches in file names and content
- Semantically similar terms to the query
- Related programming concepts
- File types appropriate for the task

Return a comprehensive list of relevant files that would be helpful for addressing the user's query."""
}

def register_template(task_system) -> None:
    """Register the associative matching template with the Task System.
    
    Args:
        task_system: The Task System instance
    """
    task_system.register_template(ASSOCIATIVE_MATCHING_TEMPLATE)

def create_xml_template() -> str:
    """Create the XML representation of the template.
    
    Returns:
        XML string representing the template
    """
    # This is a helper to generate the actual XML when needed
    xml = """
    <task type="atomic" subtype="associative_matching" name="find_relevant_files">
      <description>Find relevant files for the given query</description>
      <parameters>
        <parameter name="query" type="string" required="true">The user query or task to find relevant files for</parameter>
        <parameter name="max_results" type="integer" default="20">Maximum number of files to return</parameter>
      </parameters>
      <returns type="array" items="string">List of relevant file paths</returns>
      <model preferred="claude-3-5-sonnet" fallback="gpt-4,claude-3-haiku" />
      <context_management>
        <inherit_context>none</inherit_context>
        <accumulate_data>false</accumulate_data>
        <fresh_context>disabled</fresh_context>
      </context_management>
      <output_format type="json" schema="string[]" />
    </task>
    """
    return xml

def execute_template(query: str, memory_system, max_results: int = 20) -> List[str]:
    """Execute the associative matching template logic.
    
    This function passes the file metadata to memory_system, which then determines
    which files are most relevant to the given query (delegated to the handler's LLM).
    
    Args:
        query: The user query or task
        memory_system: The Memory System instance
        max_results: Maximum number of files to return
        
    Returns:
        List of relevant file paths selected by the LLM via the handler
    """
    print(f"Executing associative matching for query: '{query}'")
    
    # Get global index from memory system
    file_metadata = get_global_index(memory_system)
    if not file_metadata:
        print("No indexed files found. Run index_git_repository first.")
        return []
    
    print(f"Found {len(file_metadata)} indexed files")
    
    # The actual file relevance determination is now handled by the memory_system,
    # which delegates to its handler (using LLM) when available.
    # Here we just need to call the right method and extract the paths.
    
    # Use memory_system's existing API to get relevant files
    context_input = {
        "taskText": query,
        "inheritedContext": ""
    }
    
    context_result = memory_system.get_relevant_context_for(context_input)
    
    # Extract file paths from matches
    relevant_files = [match[0] for match in context_result.matches]
    
    # Limit to max_results
    relevant_files = relevant_files[:max_results]
    
    print(f"Selected {len(relevant_files)} relevant files")
    for i, path in enumerate(relevant_files[:5], 1):
        print(f"  {i}. {path}")
    if len(relevant_files) > 5:
        print(f"  ... and {len(relevant_files) - 5} more")
    
    return relevant_files


def get_global_index(memory_system) -> Dict[str, str]:
    """Get the global index from the memory system.
    
    This function provides compatibility with different Memory System implementations.
    
    Args:
        memory_system: The Memory System instance
        
    Returns:
        Dictionary mapping file paths to metadata
    """
    # Try different methods to get the global index
    if hasattr(memory_system, 'get_global_index'):
        return memory_system.get_global_index()
    elif hasattr(memory_system, 'global_index'):
        return memory_system.global_index
    else:
        # Return empty dict if global index not found
        return {}
