"""Example templates demonstrating context relevance capabilities."""
from typing import Dict, List, Any

# Template that includes all inputs in context
INCLUDE_ALL_TEMPLATE = {
    "type": "atomic",
    "subtype": "inclusive_context",
    "name": "inclusive_context",
    "description": "Example template that includes all inputs in context",
    "parameters": {
        "query": {
            "type": "string",
            "description": "Main search query",
            "required": True
        },
        "filter_type": {
            "type": "string",
            "description": "Type of files to filter for",
            "default": "all"
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results",
            "default": 10
        }
    },
    "context_relevance": {
        "query": True,
        "filter_type": True,
        "max_results": True
    },
    "system_prompt": """Find information related to {{query}} with the following parameters:
- File type filter: {{filter_type}}
- Maximum results: {{max_results}}"""
}

# Template with selective input inclusion
SELECTIVE_CONTEXT_TEMPLATE = {
    "type": "atomic",
    "subtype": "selective_context",
    "name": "selective_context",
    "description": "Example template that selectively includes inputs in context",
    "parameters": {
        "main_query": {
            "type": "string",
            "description": "Primary search query",
            "required": True
        },
        "secondary_topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Additional topics to include",
            "default": []
        },
        "excluded_topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Topics to exclude",
            "default": []
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return",
            "default": 20
        }
    },
    "context_relevance": {
        "main_query": True,       # Include in context
        "secondary_topics": True, # Include in context
        "excluded_topics": True,  # Include in context
        "max_results": False      # Exclude from context
    },
    "system_prompt": """Search for information about {{main_query}}.
Include these additional topics: {{secondary_topics}}.
Exclude information about: {{excluded_topics}}.
Return at most {{max_results}} results."""
}

# Complex template with structured inputs
COMPLEX_CONTEXT_TEMPLATE = {
    "type": "atomic",
    "subtype": "complex_context",
    "name": "complex_context",
    "description": "Example template with complex structured inputs",
    "parameters": {
        "project_info": {
            "type": "object",
            "description": "Information about the project",
            "default": {
                "name": "default_project",
                "language": "python",
                "version": "1.0.0"
            }
        },
        "search_patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "importance": {"type": "string", "enum": ["high", "medium", "low"]}
                }
            },
            "description": "Patterns to search for",
            "default": []
        },
        "output_format": {
            "type": "string",
            "description": "Format for output",
            "default": "json"
        }
    },
    "context_relevance": {
        "project_info": True,      # Include in context
        "search_patterns": True,   # Include in context
        "output_format": False     # Exclude from context
    },
    "system_prompt": """Find code related to project {{project_info.name}} written in {{project_info.language}}.
Look for these patterns:
{{#each search_patterns}}
- {{this.pattern}} ({{this.importance}} importance)
{{/each}}

Format results as {{output_format}}."""
}

def register_context_examples(task_system) -> None:
    """Register the example templates with the Task System.
    
    Args:
        task_system: The Task System instance
    """
    task_system.register_template(INCLUDE_ALL_TEMPLATE)
    task_system.register_template(SELECTIVE_CONTEXT_TEMPLATE)
    task_system.register_template(COMPLEX_CONTEXT_TEMPLATE)
