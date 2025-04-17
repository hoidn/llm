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
from typing import Dict, Any

AIDER_AUTOMATIC_TEMPLATE: Dict[str, Any] = {
    "name": "aider:automatic", # Matches identifier used for Direct Tool
    "type": "aider", # Logical type
    "subtype": "automatic",
    "description": "Execute an automatic Aider task with auto-confirmation for straightforward code changes.",
    "parameters": {
        "prompt": {"type": "string", "description": "The instruction for code changes.", "required": True},
        # file_context is technically optional for the *tool*, but often needed.
        # Represent it as a string here as that's what the user passes via CLI.
        "file_context": {"type": "string", "description": "(Optional) JSON string array of explicit file paths to include. e.g., '[\"/path/to/file1.py\", \"/path/to/file2.py\"]'", "required": False}
    },
    # No 'body' or 'system_prompt' needed as execution is via Direct Tool
}

AIDER_INTERACTIVE_TEMPLATE: Dict[str, Any] = {
    "name": "aider:interactive", # Matches identifier used for Direct Tool
    "type": "aider", # Logical type
    "subtype": "interactive",
    "description": "Start an interactive Aider session for complex code editing tasks.",
    "parameters": {
        "query": {"type": "string", "description": "The initial query or instruction for the Aider session.", "required": True},
        # file_context is technically optional for the *tool*, but often needed.
        "file_context": {"type": "string", "description": "(Optional) JSON string array of explicit file paths to start the session with.", "required": False}
    },
}

def register_aider_templates(task_system):
    """Registers the optional Aider metadata templates with the TaskSystem."""
    if hasattr(task_system, 'register_template'):
        task_system.register_template(AIDER_AUTOMATIC_TEMPLATE)
        task_system.register_template(AIDER_INTERACTIVE_TEMPLATE)
        print("Registered Aider metadata templates.") # Add confirmation
    else:
        print("Warning: TaskSystem does not have register_template method. Skipping Aider template registration.")
