# Template-Aware Context Generation

This guide explains how to use the new context relevance features in templates to provide more precise control over which inputs are used for context retrieval.

## Overview

When a template is executed, the system needs to determine which files are relevant to the task. With template-aware context generation, you can specify exactly which inputs should be considered when matching files. This allows for more precise control over context retrieval, making your templates more effective.

## Using Context Relevance

### Basic Usage

Add a `context_relevance` object to your template to specify which parameters should be included in context matching:

```json
{
  "type": "atomic",
  "subtype": "my_template",
  "name": "my_template",
  "description": "A template with context relevance",
  "parameters": {
    "query": {
      "type": "string",
      "description": "Search query",
      "required": true
    },
    "max_results": {
      "type": "integer",
      "description": "Maximum results",
      "default": 10
    }
  },
  "context_relevance": {
    "query": true,       // Include in context matching
    "max_results": false // Exclude from context matching
  }
}
```

### Default Behavior

If you don't specify `context_relevance`, the system defaults to including all parameters in context matching. This maintains backward compatibility with existing templates.

### Benefits of Selective Inclusion

By controlling which inputs are used for context matching, you can:

1. **Improve relevance**: Only include parameters that are meaningful for file selection
2. **Reduce noise**: Exclude parameters that don't impact file selection (like formatting options)
3. **Clarify intent**: Make it explicit which parameters should affect context retrieval

## Examples

### Including All Inputs

This template includes all inputs in context matching:

```python
TEMPLATE = {
    "type": "atomic",
    "subtype": "inclusive_context",
    "name": "inclusive_context",
    "description": "Example template that includes all inputs in context",
    "parameters": {
        "query": {"type": "string", "required": True},
        "filter_type": {"type": "string", "default": "all"},
        "max_results": {"type": "integer", "default": 10}
    },
    "context_relevance": {
        "query": True,
        "filter_type": True,
        "max_results": True
    }
}
```

### Selective Inclusion

This template only includes some inputs in context matching:

```python
TEMPLATE = {
    "type": "atomic",
    "subtype": "selective_context",
    "name": "selective_context",
    "description": "Example with selective context",
    "parameters": {
        "main_query": {"type": "string", "required": True},
        "secondary_topics": {"type": "array", "items": {"type": "string"}, "default": []},
        "excluded_topics": {"type": "array", "items": {"type": "string"}, "default": []},
        "max_results": {"type": "integer", "default": 20}
    },
    "context_relevance": {
        "main_query": True,       // Include
        "secondary_topics": True, // Include
        "excluded_topics": True,  // Include
        "max_results": False      // Exclude
    }
}
```

## Best Practices

1. **Include search-related parameters**: Always include parameters that directly influence what files are relevant (queries, filters, topics)
2. **Exclude formatting parameters**: Parameters like `max_results`, `sort_order`, or `output_format` typically don't affect which files are relevant
3. **Be explicit**: Even though the default is to include all parameters, explicitly defining context relevance makes your intentions clear
4. **Consider complex objects**: For complex object parameters, consider whether the entire object is relevant for context or just specific properties

## Advanced Usage

### Complex Structured Inputs

For complex structured inputs, you can still control their inclusion at the top level:

```python
TEMPLATE = {
    "parameters": {
        "project_info": {
            "type": "object",
            "default": {
                "name": "default_project",
                "language": "python"
            }
        }
    },
    "context_relevance": {
        "project_info": True  // The entire object is included
    }
}
```

The system will handle converting complex objects appropriately when determining relevance.
