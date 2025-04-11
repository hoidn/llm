"""Associative matching template for finding relevant files."""
from typing import Dict, List, Any, Tuple
import re
import os
import math
import json
from task_system.template_utils import Environment

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
    Execute the associative matching template logic using the LLM via the handler's provider.

    Args:
        inputs: Dictionary of resolved input parameters for the template.
        memory_system: The Memory System instance (unused in this version).
        handler: The Handler instance (expected to have model_provider and _build_system_prompt).

    Returns:
        List of relevant file objects [{'path': str, 'relevance': str}]
    """
    print(f"DEBUG: Executing associative matching template via handler.model_provider (Handler type: {type(handler).__name__})")

    # --- 1. Extract resolved inputs ---
    query = inputs.get("query", "")
    metadata_str = inputs.get("metadata", "")
    additional_context = inputs.get("additional_context", {})
    max_results = inputs.get("max_results", 20)
    inherited_context = inputs.get("inherited_context", "")

    if not query:
        print("Warning: No query provided for associative matching.")
        return []
    if not metadata_str:
        print("Warning: No file metadata provided for associative matching.")
        return []

    # --- 2. Prepare System Prompt using BaseHandler's method ---
    # Need the template definition itself to get the system_prompt template string
    template_definition = ASSOCIATIVE_MATCHING_TEMPLATE

    # Create environment for prompt processing
    prompt_env = Environment(inputs)
    try:
        system_prompt_template = template_definition.get("system_prompt", "")
        import jinja2
        jinja_env = jinja2.Environment()
        template = jinja_env.from_string(system_prompt_template)
        # Render the system prompt using the inputs
        processed_system_prompt = template.render(
            query=query,
            additional_context=additional_context,
            inherited_context=inherited_context,
            max_results=max_results,
            metadata=metadata_str
        )
        # Use BaseHandler's _build_system_prompt to combine with base prompt if desired,
        # although for this specific task, the template prompt *is* the full instruction.
        # We'll pass the processed prompt directly to the provider.
        # If hierarchical prompts were desired here, you'd call:
        # final_system_prompt = handler._build_system_prompt(template={"system_prompt": processed_system_prompt})
        # But for clarity, let's use the processed prompt directly:
        final_system_prompt = processed_system_prompt

    except Exception as e:
        print(f"Error processing system prompt template: {e}")
        final_system_prompt = f"Error processing prompt template: {e}" # Fallback

    # --- 3. Prepare Messages for the LLM Call ---
    # Minimal message list required by the API
    messages_for_api = [
        {"role": "user", "content": "Based on the system prompt, provide the JSON list of relevant files."}
    ]

    # --- 4. Execute using the handler's model_provider ---
    response_content = "[]" # Default empty JSON array string
    try:
        # Access the provider from the handler
        provider = handler.model_provider
        if not provider:
            print("Error: Handler does not have a model_provider.")
            return []

        print(f"DEBUG: Calling provider.send_message() directly.")
        # Call the provider's send_message directly
        raw_response = provider.send_message(
            messages=messages_for_api,
            system_prompt=final_system_prompt,
            tools=None # No tools needed for this specific task
        )

        # Check for API error strings returned by send_message
        if isinstance(raw_response, str) and raw_response.startswith("Error"):
             print(f"API Error received from provider: {raw_response}")
             return [] # Return empty list on error

        # Extract the content from the response using the provider's own method
        # This standardizes handling across different provider response structures
        extracted_data = provider.extract_tool_calls(raw_response) # Also extracts content
        response_content = extracted_data.get("content", "[]")
        print(f"DEBUG: Raw LLM Response Content: {response_content}")

    except Exception as e:
        import traceback
        print(f"Error during direct provider call: {e}\n{traceback.format_exc()}")
        return []


    # --- 5. Parse the LLM response ---
    try:
        # Clean the response
        cleaned_response = response_content.strip()
        if cleaned_response.startswith("```json") and cleaned_response.endswith("```"):
             cleaned_response = cleaned_response[7:-3].strip()
        elif cleaned_response.startswith("```") and cleaned_response.endswith("```"):
             cleaned_response = cleaned_response[3:-3].strip()
        if cleaned_response.lower().startswith("json"):
             cleaned_response = cleaned_response[4:].strip()

        print(f"DEBUG: Cleaned Response for JSON parsing:\n{cleaned_response}\n---")

        # Handle empty or non-JSON responses gracefully
        if not cleaned_response:
            print("Warning: LLM returned empty response content.")
            return []

        parsed_files = json.loads(cleaned_response)

        if not isinstance(parsed_files, list):
             print(f"Warning: LLM response for file matching was not a JSON list. Got: {type(parsed_files)}")
             return []

        # Validate format
        validated_files = []
        # TODO: Consider passing global_index keyset for validation against hallucinated paths
        # Example: global_paths = set(get_global_index(memory_system).keys())
        for item in parsed_files:
             if isinstance(item, dict) and "path" in item and "relevance" in item:
                 # if item["path"] in global_paths: # Optional validation
                 validated_files.append(item)
                 # else: print(f"Warning: Skipping hallucinated path from LLM: {item['path']}")
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
        print(f"LLM Raw Response Content was: >>>\n{response_content}\n<<<")
        return []
    except Exception as e:
        import traceback
        print(f"Unexpected error processing LLM response: {e}\n{traceback.format_exc()}")
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
