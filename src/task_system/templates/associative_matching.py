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
            "type": "string",
            "description": "Formatted string of file metadata",
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
        "metadata": False,      # Metadata is now part of the prompt, not separate context
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
    "system_prompt": """You are a file relevance assistant. Your task is to select files that are relevant to a user's query and additional context.

The user message will contain:
1. The main query: {{query}}
2. Additional context parameters:
{% for key, value in additional_context.items() %}
   - {{key}}: {{value}}
{% endfor %}
3. Inherited context (if any): {{inherited_context}}
4. A list of available files with metadata below.

Examine the metadata of each file and determine which files would be most useful for addressing the query.

RETURN ONLY a JSON array of objects with the following format:
[{"path": "path/to/file1.py", "relevance": "Reason this file is relevant"}, ...]

Include only files that are truly relevant to the query and context.
The "relevance" field should briefly explain why the file is relevant.
Prioritize the most relevant files, up to a maximum of {{max_results}}.

Available Files Metadata:
{{metadata}}
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

def execute_template(inputs: Dict[str, Any], memory_system, handler) -> List[Dict[str, Any]]:
    """
    Execute the associative matching template logic using the LLM via the handler.

    Args:
        inputs: Dictionary of resolved input parameters for the template.
        memory_system: The Memory System instance (unused in this version, but kept for signature compatibility).
        handler: The Handler instance to execute the LLM call.

    Returns:
        List of relevant file objects [{'path': str, 'relevance': str}]
    """
    print(f"Executing associative matching template directly via handler")

    # --- 1. Extract resolved inputs ---
    query = inputs.get("query", "")
    metadata_str = inputs.get("metadata", "")  # Expecting formatted string now
    additional_context = inputs.get("additional_context", {})
    max_results = inputs.get("max_results", 20)
    inherited_context = inputs.get("inherited_context", "")

    if not query:
        print("Warning: No query provided for associative matching.")
        return []
    if not metadata_str:
        print("Warning: No file metadata provided for associative matching.")
        return []

    # --- 2. Prepare prompt for the handler ---
    # Create a minimal environment for substituting variables in the system prompt
    from task_system.template_utils import Environment
    prompt_env = Environment(inputs)
    try:
        # Substitute variables in the system prompt template string
        system_prompt_template = ASSOCIATIVE_MATCHING_TEMPLATE.get("system_prompt", "")
        # Handle the Jinja-like syntax in prompt
        import jinja2
        jinja_env = jinja2.Environment()
        template = jinja_env.from_string(system_prompt_template)
        processed_system_prompt = template.render(
            query=query,
            additional_context=additional_context,
            inherited_context=inherited_context,
            max_results=max_results,
            metadata=metadata_str
        )
    except Exception as e:
        print(f"Error processing system prompt template: {e}")
        processed_system_prompt = f"Error processing prompt template: {e}"  # Fallback

    # The main prompt for the LLM
    main_prompt = "Based on the system prompt, provide the JSON list of relevant files."

    # --- 3. Execute using the handler ---
    # Try to use _send_to_model if available
    if hasattr(handler, '_send_to_model'):
        llm_response = handler._send_to_model(
            query=main_prompt,
            file_context=None,  # File context is already in the system prompt
            template={"system_prompt": processed_system_prompt}
        )
        response_content = llm_response
    else:
        # Fallback: If _send_to_model isn't suitable, use handle_query
        print("Warning: Using fallback handler execution method for associative matching.")
        # Temporarily set a specific system prompt for this call
        original_base_prompt = getattr(handler, 'base_system_prompt', None)
        if hasattr(handler, 'base_system_prompt'):
            handler.base_system_prompt = processed_system_prompt
        # Execute
        result_dict = handler.handle_query(main_prompt)
        # Restore original prompt if needed
        if hasattr(handler, 'base_system_prompt') and original_base_prompt is not None:
            handler.base_system_prompt = original_base_prompt
        response_content = result_dict.get("content", "[]")

    # --- 4. Parse the LLM response ---
    try:
        # Clean the response: LLMs sometimes add markdown backticks
        import json
        cleaned_response = response_content.strip()
        if cleaned_response.startswith("```") and cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[3:-3].strip()
        if cleaned_response.startswith("json"):
            cleaned_response = cleaned_response[4:].strip()

        parsed_files = json.loads(cleaned_response)
        if not isinstance(parsed_files, list):
            print(f"Warning: LLM response for file matching was not a JSON list. Got: {type(parsed_files)}")
            return []

        # Validate format
        validated_files = []
        for item in parsed_files:
            if isinstance(item, dict) and "path" in item and "relevance" in item:
                validated_files.append(item)
            else:
                print(f"Warning: Skipping invalid item in LLM response: {item}")
        
        print(f"Selected {len(validated_files)} relevant files")
        for i, item in enumerate(validated_files[:5], 1):
            print(f"  {i}. {item['path']} - {item['relevance'][:50]}...")
        if len(validated_files) > 5:
            print(f"  ... and {len(validated_files) - 5} more")
            
        return validated_files

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response from LLM: {e}")
        print(f"LLM Raw Response was: {response_content}")
        return []
    except Exception as e:
        print(f"Unexpected error processing LLM response: {e}")
        return []


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
