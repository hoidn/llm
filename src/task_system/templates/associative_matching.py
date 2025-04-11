"""Associative matching template for finding relevant files."""
from typing import Dict, List, Any, Tuple
import re
import os
import math

# Template definition as a Python dictionary
ASSOCIATIVE_MATCHING_TEMPLATE = {
    "type": "atomic",
    "subtype": "associative_matching",
    "name": "find_relevant_files",  # Unique template name
    "description": "Find relevant files for '{{query}}' (max: {{max_results}})",  # Now using variables
    "parameters": {  # Structured parameters
        "query": {
            "type": "string",
            "description": "The user query or task to find relevant files for",
            "required": True
        },
        "metadata": {
            "type": "object",
            "description": "File metadata dictionary mapping paths to metadata",
            "required": True
        },
        "additional_context": {
            "type": "object",
            "description": "Additional context parameters to consider",
            "default": {}
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of files to return",
            "default": 20
        },
        "inherited_context": {
            "type": "string",
            "description": "Context inherited from parent tasks",
            "default": ""
        },
        "previous_outputs": {
            "type": "array",
            "description": "Outputs from previous steps",
            "default": []
        }
    },
    "context_relevance": {
        "query": True,          # Include query in context matching
        "metadata": True,       # Include metadata in context matching
        "additional_context": True,  # Include additional context in matching
        "max_results": False,   # Exclude max_results from context matching
        "inherited_context": True,   # Include inherited context in matching
        "previous_outputs": True     # Include previous outputs in matching
    },
    "model": {  # Model preferences
        "preferred": "claude-3-5-sonnet",
        "fallback": ["gpt-4", "claude-3-haiku"]
    },
    "returns": {  # Return type definition
        "type": "array",
        "items": {"type": "object"},
        "description": "List of relevant file objects with path and relevance"
    },
    "context_management": {
        "inherit_context": "optional",  # Use inherited context if available
        "accumulate_data": True,       # Accumulate data across steps
        "fresh_context": "disabled"    # Don't generate fresh context (would cause recursion)
    },
    "output_format": {
        "type": "json",
        "schema": "array"
    },
    "system_prompt": """You are a context retrieval assistant. Your task is to find the most relevant files for a given query.

Examine the provided metadata and determine which files would be most useful for addressing the query.

Consider the following in your analysis:
1. The main query: {{query}}
2. Additional context parameters:
{% for key, value in additional_context.items() %}
   - {{key}}: {{value}}
{% endfor %}
3. Inherited context (if any): {{inherited_context}}
4. File metadata content

Focus on files that contain:
- Direct keyword matches
- Semantically similar content
- Relevant functionality
- Associated concepts

RETURN ONLY a JSON array of objects with this format:
[{"path": "path/to/file1.py", "relevance": "Reason this file is relevant"}, ...]

Include up to {{max_results}} files, prioritizing the most relevant ones.
The "relevance" field should briefly explain why the file is relevant.
"""
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
      <description>Find relevant files for '{{query}}' (max: {{max_results}})</description>
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
    
    # Create context input
    from memory.context_generation import ContextGenerationInput
    context_input = ContextGenerationInput(
        template_description=query,
        template_type="atomic",
        template_subtype="associative_matching",
        inputs={"query": query}
    )
    
    # The actual file relevance determination is now handled by the memory_system
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
