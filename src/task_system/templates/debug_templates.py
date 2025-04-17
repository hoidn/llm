"""Debug templates for test analysis and fix generation."""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

DEBUG_ANALYZE_RESULTS_TEMPLATE: Dict[str, Any] = {
    "name": "debug:analyze_test_results",
    "type": "atomic",
    "subtype": "debug_analysis",
    "description": "Analyzes test command output to determine success/failure and extract error details.",
    "parameters": {
        "test_stdout": {"type": "string", "description": "Standard output from the test command.", "required": False, "default": ""},
        "test_stderr": {"type": "string", "description": "Standard error output from the test command.", "required": False, "default": ""},
        "test_exit_code": {"type": "integer", "description": "Exit code of the test command.", "required": True}
    },
    "output_format": {
        "type": "json",
        "schema": """{
            "success": "boolean",
            "feedback": "string",
            "error_details": {
                "failing_test": "string | null",
                "error_message": "string",
                "full_stderr": "string"
            } | null
        }"""  # Provide schema description for validation/guidance
    },
    "system_prompt": """Analyze the provided test execution results (stdout, stderr, exit code). Determine if the tests passed (exit code 0 indicates success).
If tests failed, provide a concise feedback message summarizing the failure and extract key information into 'error_details'.
Focus on identifying the primary error message and potentially the name of the failing test from the stderr.
Respond ONLY with the following JSON structure:
{
  "success": boolean, // true if exit_code is 0, false otherwise
  "feedback": "string", // e.g., "Tests passed.", "Tests failed: [Reason]", "Error running tests."
  "error_details": { // Include ONLY if success is false
    "failing_test": "string | null", // Name of first failing test if identifiable, otherwise null
    "error_message": "string", // Short, key error message snippet
    "full_stderr": "string" // Full standard error output
  } | null // Set to null if success is true
}

Test Exit Code: {{ test_exit_code }}
Standard Output:
```
{{ test_stdout }}
```
Standard Error:
```
{{ test_stderr }}
```"""
    # Add model preference if desired, e.g.:
    # "model": {"preferred": "claude-3-5-sonnet"}
}

DEBUG_GENERATE_FIX_TEMPLATE: Dict[str, Any] = {
    "name": "debug:generate_fix",
    "type": "atomic",
    "subtype": "debug_fix_generation",
    "description": "Generates a code fix proposal based on error details and code context.",
    "parameters": {
        "error_details": {"type": "object", "description": "Structured error details from the analysis step (JSON object).", "required": True},
        "code_context": {"type": "string", "description": "Concatenated content of relevant code files.", "required": True}
    },
    "output_format": {"type": "text"},  # Expecting raw code fix
    "system_prompt": """Analyze the following test error details and the relevant code context.
Generate ONLY the code snippet required to fix the error described.
Do NOT include explanations, apologies, markdown formatting (like ```python), or any text other than the code fix itself.
If you cannot determine a fix, output only the text "// NO FIX FOUND".

Error Details:
```json
{{ error_details | tojson }}
```

Relevant Code Context:
```
{{ code_context }}
```

Proposed Code Fix:"""
    # Add model preference if desired, e.g.:
    # "model": {"preferred": "claude-3-opus"} # Might need a stronger model for fix generation
}

def register_debug_templates(task_system):
    """
    Registers the debug loop templates with the TaskSystem.
    
    Args:
        task_system: The TaskSystem instance to register templates with
    """
    logger.info("Registering Debug Loop templates...")
    if hasattr(task_system, 'register_template'):
        task_system.register_template(DEBUG_ANALYZE_RESULTS_TEMPLATE)
        task_system.register_template(DEBUG_GENERATE_FIX_TEMPLATE)
        # Note: DEBUG_LOOP_DIRECTOR_STEP_TEMPLATE is NOT registered here yet (Phase 4.2/5)
        logger.info("Debug Loop analysis/fix templates registered.")
    else:
        logger.error("TaskSystem object does not have 'register_template' method.")
