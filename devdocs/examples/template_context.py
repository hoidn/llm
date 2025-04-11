"""
Examples demonstrating template-aware context generation.

This module provides examples and explanations for developers on how to use
the context relevance features in templates.
"""

# Example 1: Basic template with context relevance
BASIC_EXAMPLE = {
    "type": "atomic",
    "subtype": "file_search",
    "name": "file_search",
    "description": "Find files related to a specific topic",
    "parameters": {
        "query": {
            "type": "string",
            "description": "Search query",
            "required": True
        },
        "file_type": {
            "type": "string",
            "description": "File type filter (.py, .js, etc.)",
            "default": ""
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results",
            "default": 10
        }
    },
    "context_relevance": {
        "query": True,      # Include in context matching
        "file_type": True,  # Include in context matching
        "max_results": False  # Exclude from context matching
    }
}

# Usage example for developers
"""
How Context Relevance Works:

1. Template Execution Flow
   When the task_system executes a template, it:
   a. Resolves parameter values
   b. Extracts context_relevance from the template
   c. Creates a ContextGenerationInput with template info, inputs, and context_relevance
   d. Passes the ContextGenerationInput to memory_system.get_relevant_context_for()

2. Context Retrieval Flow
   The memory_system then:
   a. Takes the ContextGenerationInput
   b. Passes it directly to the handler's determine_relevant_files method
   c. The handler extracts information from the ContextGenerationInput
   d. Only inputs marked as relevant in context_relevance are used for context matching

3. Using the LLM for Relevance
   The LLM receives:
   a. The template description
   b. Only the inputs marked as relevant
   c. The file metadata
   d. The LLM determines which files are most relevant based on this information
"""

# Example 2: Template with complex structured inputs
COMPLEX_EXAMPLE = {
    "type": "atomic",
    "subtype": "code_analysis",
    "name": "code_analysis",
    "description": "Analyze code patterns in a project",
    "parameters": {
        "project_settings": {
            "type": "object",
            "description": "Project configuration",
            "default": {
                "name": "default_project",
                "language": "python",
                "version": "1.0.0"
            }
        },
        "analysis_patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]}
                }
            },
            "description": "Patterns to analyze",
            "default": []
        },
        "output_settings": {
            "type": "object",
            "description": "Output configuration",
            "default": {
                "format": "json",
                "include_line_numbers": True,
                "max_results": 50
            }
        }
    },
    "context_relevance": {
        "project_settings": True,      # Include project info in context
        "analysis_patterns": True,     # Include patterns in context
        "output_settings": False       # Exclude output config from context
    }
}

"""
Best Practices for Complex Objects:

1. Granularity
   - Consider whether the entire object is relevant for context matching
   - For complex objects, typically includes business logic properties but not formatting
   
2. Input Structure Design
   - Group related properties into objects with clear purposes
   - Separate search/matching properties from display/output properties
   
3. Testing
   - Use integration tests to verify correct behavior with complex objects
   - Monitor the quality of context matches with different configurations
"""

# Example 3: Backward compatibility demonstration
LEGACY_TEMPLATE = {
    "type": "atomic",
    "subtype": "legacy_search",
    "name": "legacy_search",
    "description": "Legacy template without context_relevance",
    "parameters": {
        "query": {
            "type": "string",
            "description": "Search query",
            "required": True
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results",
            "default": 10
        }
    }
    # No context_relevance - defaults to including all parameters
}

"""
Backward Compatibility:

1. Default Behavior
   - Templates without context_relevance default to including all parameters
   - This maintains compatibility with existing templates
   
2. Migration Strategy
   - Start by testing your existing templates with the new system
   - Add context_relevance to templates that would benefit from selective inclusion
   - No need to update all templates at once
"""
