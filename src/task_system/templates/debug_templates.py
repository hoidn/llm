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


# Task 3: Define DEBUG_LOOP_DIRECTOR_STEP_TEMPLATE
DEBUG_LOOP_DIRECTOR_STEP_TEMPLATE: Dict[str, Any] = {
    "name": "debug_loop_director_step",
    "type": "atomic", # Type isn't driving execution; 'steps' list is. Let Evaluator handle steps.
    "description": "Internal step for the debug loop: Gets context, generates fix, applies fix.",
    "parameters": {
        # Implicitly receives from D-E loop environment:
        # - evaluation_result: TaskResult from the previous evaluator step.
        # - target_files: List[str] of target file paths (parsed by D-E loop).
        # - test_cmd: Original test command string.
    },
    "context_management": {"fresh_context": "disabled"}, # Critical: Prevent recursive context lookup
    "steps": [ # Execution managed by updated Evaluator based on this list
        # Step 1: Call system:get_context
        {
            "type": "call",
            "template": "system:get_context",
            "description": "Get relevant files based on test failure.",
            "arguments": [
                # Pass the error message as the query
                {"name": "query", "value": "{{ evaluation_result.notes.error_details.error_message }}"},
                # Pass the target_files list directly (parsed by D-E loop)
                # Use default filter in case it's somehow missing, though D-E loop should ensure it exists
                {"name": "target_files", "value": "{{ target_files | default([]) }}"}
            ],
            "bind_result_to": "context_files_result"
        },
        # Step 2: Call system:read_files
        {
            "type": "call",
            "template": "system:read_files",
            "description": "Read content of relevant files.",
            "arguments": [
                # Access the file paths list from the notes of the previous step's result
                {"name": "file_paths", "value": "{{ context_files_result.notes.file_paths }}"}
            ],
            "bind_result_to": "read_files_result" # Bind TaskResult to this var
        },
        # Step 3: Call debug:generate_fix
        {
            "type": "call",
            "template": "debug:generate_fix",
            "description": "Generate code fix based on error and context.",
            "arguments": [
                # Pass the error details object
                {"name": "error_details", "value": "{{ evaluation_result.notes.error_details }}"},
                # Pass the concatenated file content
                {"name": "code_context", "value": "{{ read_files_result.content }}"}
            ],
            "bind_result_to": "generate_fix_result" # Bind TaskResult to this var
        },
        # Step 4: Call aider:automatic (Apply the fix)
        # TODO: Add conditional logic here if possible to skip if fix is "// NO FIX FOUND"
        {
            "type": "call",
            "template": "aider:automatic", # This is a Direct Tool
            "description": "Apply the generated fix using Aider.",
            "arguments": [
                # Pass the fix proposal as the prompt
                {"name": "prompt", "value": "{{ generate_fix_result.content }}"},
                # Pass the file path list directly (Task 2 ensures aider accepts list)
                # Access the list from the notes of the context result
                {"name": "file_context", "value": "{{ context_files_result.notes.file_paths }}"}
            ],
            "bind_result_to": "apply_fix_result" # Bind TaskResult to this var (final result of this step)
        }
    ]
}

DEBUG_LOOP_TEMPLATE: Dict[str, Any] = {
    "name": "debug:loop",
    "type": "director_evaluator_loop",
    "description": "Automated Debug-Fix Loop: Runs tests, analyzes failures, attempts fixes.",
    "parameters": {
        "test_cmd": {"type": "string", "description": "The shell command to execute tests.", "required": True},
        # User provides JSON string, parsing handled in Evaluator (Task 1)
        "target_files": {"type": "string", "description": "(Optional) JSON string array of target file paths, e.g., '[\"file1.py\"]'.", "required": False, "default": "[]"},
        "max_cycles": {"type": "integer", "description": "Maximum fix attempts.", "required": False, "default": 3}
    },
    "context_management": {"fresh_context": "disabled"}, # Prevent top-level context lookup
    "max_iterations": "{{ max_cycles }}", # Evaluator substitutes this during loop init
    # Define the Director step - points to the template defined in Task 3
    "director": {
        "type": "call", # This structure tells the D-E loop logic *what* to call
        "template": "debug_loop_director_step", # References the template with steps
        "description": "Attempt to fix the failed tests.",
        "arguments": [] # Arguments passed implicitly by D-E loop environment
    },
    # Define the Script Execution step
    "script_execution": {
        "type": "call",
        "template": "system:run_script", # ASSUMES this direct tool exists and is registered
        "description": "Run the test command.",
        "arguments": [{"name": "command", "value": "{{ test_cmd }}"}]
        # Result (stdout, stderr, exit_code) bound automatically to env by D-E loop logic
    },
    # Define the Evaluator step
    "evaluator": {
        "type": "call",
        "template": "debug:analyze_test_results", # Existing template from Phase 4
        "description": "Analyze the test command output.",
        "arguments": [
            # Inputs bound automatically by the D-E loop logic from script execution result
            {"name": "test_stdout", "value": "{{ script_stdout }}"},
            {"name": "test_stderr", "value": "{{ script_stderr }}"},
            {"name": "test_exit_code", "value": "{{ script_exit_code }}"}
        ]
        # Result automatically bound to 'evaluation_result' in env by D-E loop logic
    },
    # Define the Termination Condition
    "termination_condition": {
        # Evaluated by D-E loop logic against the 'evaluation_result'
        "condition_string": "evaluation.notes.success == true"
    }
}

def register_debug_templates(task_system):
    """
    Registers the debug loop templates with the TaskSystem.
    
    Args:
        task_system: The TaskSystem instance to register templates with
    """
    """
    logger.info("Registering Debug Loop templates...")
    if hasattr(task_system, 'register_template'):
        task_system.register_template(DEBUG_ANALYZE_RESULTS_TEMPLATE) # Existing
        task_system.register_template(DEBUG_GENERATE_FIX_TEMPLATE)    # Existing
        # --- Add New Templates ---
        task_system.register_template(DEBUG_LOOP_DIRECTOR_STEP_TEMPLATE) # From Task 3
        task_system.register_template(DEBUG_LOOP_TEMPLATE)               # From Task 4
        # --------------------------
        logger.info("All Debug Loop templates registered.")
    else:
        logger.error("TaskSystem object does not have 'register_template' method.")
