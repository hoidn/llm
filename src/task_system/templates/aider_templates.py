from typing import Dict, Any

AIDER_AUTOMATIC_TEMPLATE: Dict[str, Any] = {
    "name": "aider:automatic", # Matches identifier
    "type": "aider",
    "subtype": "automatic",
    "description": "Execute an automatic Aider task with auto-confirmation for straightforward code changes.",
    "parameters": {
        "prompt": {"type": "string", "description": "The instruction for code changes.", "required": True},
        "file_context": {"type": "string", "description": "(Optional) JSON string array of explicit file paths to include.", "required": False}
    },
    # Note: No 'body' needed if primarily invoked as Direct Tool
}

AIDER_INTERACTIVE_TEMPLATE: Dict[str, Any] = {
    "name": "aider:interactive", # Matches identifier
    "type": "aider",
    "subtype": "interactive",
    "description": "Start an interactive Aider session for complex code editing tasks.",
    "parameters": {
        "query": {"type": "string", "description": "The initial query or instruction for the Aider session.", "required": True},
        "file_context": {"type": "string", "description": "(Optional) JSON string array of explicit file paths to start the session with.", "required": False}
    },
}

def register_aider_templates(task_system):
    """Registers the optional Aider templates with the TaskSystem."""
    task_system.register_template(AIDER_AUTOMATIC_TEMPLATE)
    task_system.register_template(AIDER_INTERACTIVE_TEMPLATE)
