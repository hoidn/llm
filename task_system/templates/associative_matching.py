"""Associative matching template for finding relevant files."""
from typing import Dict, List, Any

# Template definition as a Python dictionary to be converted to XML
ASSOCIATIVE_MATCHING_TEMPLATE = {
    "type": "atomic",
    "subtype": "associative_matching",
    "description": "Find relevant files for the given query",
    "inputs": {
        "query": "The user query or task to find relevant files for"
    },
    "context_management": {
        "inherit_context": "none",
        "accumulate_data": False,
        "fresh_context": "disabled"
    },
    "output_format": {
        "type": "json",
        "schema": "string[]"
    }
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
    <task type="atomic" subtype="associative_matching">
      <description>Find relevant files for the given query</description>
      <inputs>
        <input name="query">The user query or task to find relevant files for</input>
      </inputs>
      <context_management>
        <inherit_context>none</inherit_context>
        <accumulate_data>false</accumulate_data>
        <fresh_context>disabled</fresh_context>
      </context_management>
      <output_format type="json" schema="string[]" />
    </task>
    """
    return xml
