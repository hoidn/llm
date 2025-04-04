"""Example templates demonstrating function call capabilities."""
from typing import Dict, List, Any
import json

# Format a value as JSON
FORMAT_JSON_TEMPLATE = {
    "type": "atomic",
    "subtype": "format_json",
    "name": "format_json",
    "description": "Format a value as pretty-printed JSON",
    "parameters": {
        "value": {
            "type": "object",
            "description": "Value to format as JSON",
            "required": True
        },
        "indent": {
            "type": "integer",
            "description": "Indentation level",
            "default": 2
        }
    },
    "returns": {
        "type": "string",
        "description": "JSON-formatted string"
    },
    "system_prompt": "Format the value as JSON with indent {{indent}}:\n{{value}}"
}

# Get current date/time
GET_DATE_TEMPLATE = {
    "type": "atomic",
    "subtype": "get_date",
    "name": "get_date",
    "description": "Get the current date in the specified format",
    "parameters": {
        "format": {
            "type": "string",
            "description": "Date format string",
            "default": "%Y-%m-%d"
        }
    },
    "returns": {
        "type": "string",
        "description": "Formatted date string"
    },
    "system_prompt": "Get current date with format {{format}}"
}

# Greeting template that uses function calls
GREETING_TEMPLATE = {
    "type": "atomic",
    "subtype": "greeting",
    "name": "greeting",
    "description": "Generate a personalized greeting",
    "parameters": {
        "name": {
            "type": "string",
            "description": "Name to greet",
            "required": True
        },
        "formal": {
            "type": "boolean",
            "description": "Whether to use formal greeting",
            "default": False
        }
    },
    "returns": {
        "type": "string",
        "description": "Greeting message"
    },
    "system_prompt": "Today's date: {{get_date()}}\n\n{{formal ? 'Dear' : 'Hello'}}, {{name}}!\n\nWelcome to our service."
}

# Nested function call example
NESTED_TEMPLATE = {
    "type": "atomic",
    "subtype": "nested_example",
    "name": "nested_example",
    "description": "Demonstrate nested function calls",
    "parameters": {
        "user_info": {
            "type": "object",
            "description": "User information",
            "default": {"name": "Guest", "role": "User"}
        }
    },
    "returns": {
        "type": "string",
        "description": "Message with nested function calls"
    },
    "system_prompt": "User data: {{format_json(value=user_info, indent=4)}}\n\n{{greeting(name=user_info.name, formal=true)}}"
}

def register_function_templates(task_system) -> None:
    """Register the function example templates with the Task System.
    
    Args:
        task_system: The Task System instance
    """
    task_system.register_template(FORMAT_JSON_TEMPLATE)
    task_system.register_template(GET_DATE_TEMPLATE)
    task_system.register_template(GREETING_TEMPLATE)
    task_system.register_template(NESTED_TEMPLATE)

def execute_format_json(value: Any, indent: int = 2) -> str:
    """Format a value as pretty-printed JSON.
    
    Args:
        value: Value to format
        indent: Indentation level
        
    Returns:
        JSON-formatted string
    """
    return json.dumps(value, indent=indent)

def execute_get_date(format: str = "%Y-%m-%d") -> str:
    """Get the current date in the specified format.
    
    Args:
        format: Date format string
        
    Returns:
        Formatted date string
    """
    import datetime
    return datetime.datetime.now().strftime(format)
