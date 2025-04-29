"""
Atomic Task Executor implementation.
Executes the body of a pre-parsed atomic XML task template.
"""

import logging
import re
import json
from typing import Any, Dict, Optional

# Assuming BaseHandler and TaskResult types are available for hinting
# from src.handler.base_handler import BaseHandler # Import actual when available
from src.system.models import TaskResult, TaskError, TaskFailureReason
from pydantic import ValidationError

# Regex to find {{parameter_name}} placeholders
PARAM_REGEX = re.compile(r"\{\{(\w+)\}\}")

class ParameterMismatchError(Exception):
    """Custom exception for missing parameters during substitution."""
    pass

class AtomicTaskExecutor:
    """
    Executes the body of a pre-parsed atomic task template using provided parameters.
    Handles parameter substitution and invokes the necessary Handler method.

    Complies with the contract defined in src/executors/atomic_executor_IDL.md.
    """

    def __init__(self):
        """Initializes the AtomicTaskExecutor."""
        logging.debug("AtomicTaskExecutor initialized.")

    def _substitute_params(self, text: Optional[str], params: Dict[str, Any]) -> Optional[str]:
        """Performs {{parameter_name}} substitution in a string."""
        if text is None:
            return None

        def replace_match(match):
            param_name = match.group(1)
            if param_name not in params:
                logging.error(f"Parameter '{param_name}' not found in provided params: {list(params.keys())}")
                raise ParameterMismatchError(f"Missing parameter for substitution: {param_name}")
            # Convert param value to string for substitution
            return str(params[param_name])

        try:
            return PARAM_REGEX.sub(replace_match, text)
        except ParameterMismatchError:
            # Re-raise to be caught by the caller
            raise
        except Exception as e:
            logging.exception(f"Unexpected error during parameter substitution: {e}")
            # Wrap unexpected errors
            raise ParameterMismatchError(f"Unexpected substitution error: {e}")


    def execute_body(
        self,
        atomic_task_def: Dict[str, Any],
        params: Dict[str, Any],
        handler: Any # Represents BaseHandler instance
    ) -> Dict[str, Any]: # Returns TaskResult structure as dict
        """
        Executes the body of a pre-parsed atomic task template.

        Args:
            atomic_task_def: A dictionary representing the parsed atomic task definition.
            params: A dictionary mapping declared input parameter names to their evaluated values.
            handler: A valid BaseHandler instance to use for LLM execution.

        Returns:
            A dictionary representing the TaskResult outcome.
        """
        task_name = atomic_task_def.get("name", "unnamed_atomic_task")
        logging.info(f"Executing atomic task body for: {task_name}")

        try:
            # --- 1. Parameter Substitution ---
            logging.debug(f"Substituting parameters for task: {task_name}")
            substituted_instructions = self._substitute_params(atomic_task_def.get("instructions"), params)
            substituted_system_prompt_template = self._substitute_params(atomic_task_def.get("system"), params)
            # Substitute other fields if necessary (e.g., description, criteria - though less common)

            # --- 2. Construct Handler Payload ---
            # Build the final system prompt using the handler's method
            # Note: The IDL for execute_body doesn't include file_context.
            # If file context is needed, it must be prepared beforehand and potentially
            # included in the handler's base system prompt or passed differently.
            final_system_prompt = handler._build_system_prompt(
                template=substituted_system_prompt_template,
                file_context=None # Explicitly None as per IDL signature
            )

            # Main prompt is the substituted instructions
            main_prompt = substituted_instructions
            if not main_prompt:
                 logging.warning(f"Task '{task_name}' has no instructions after substitution.")
                 # Decide handling: error or proceed with empty prompt? Proceed for now.
                 main_prompt = ""

            # Determine model override, if any
            model_override = atomic_task_def.get("model")

            # Determine output type override, if any
            output_format = atomic_task_def.get("output_format", {})
            output_type_override = None
            # TODO: Map output_format schema (e.g., "object", "string[]") to actual Pydantic types
            # This requires a more robust mapping mechanism. For now, we pass None.
            # Example placeholder:
            # if output_format.get("type") == "json" and output_format.get("schema") == "object":
            #     output_type_override = Dict[str, Any] # Or a specific Pydantic model if schema is richer

            # --- 3. Invoke Handler ---
            logging.debug(f"Invoking handler for task: {task_name}")
            # Assuming _execute_llm_call returns a TaskResult object or similar structure
            handler_result_obj = handler._execute_llm_call(
                prompt=main_prompt,
                system_prompt_override=final_system_prompt,
                # tools_override=None, # TODO: Handle tool registration/passing if needed
                output_type_override=output_type_override,
                # model_override=model_override # TODO: Check if _execute_llm_call supports model override
            )

            # Ensure result is a dictionary matching TaskResult structure
            if isinstance(handler_result_obj, TaskResult):
                 task_result_dict = handler_result_obj.model_dump(exclude_none=True)
            elif isinstance(handler_result_obj, dict):
                 task_result_dict = handler_result_obj # Assume it's already correct structure
            else:
                 # Handle unexpected return type from handler
                 logging.error(f"Handler returned unexpected type: {type(handler_result_obj)}")
                 raise TypeError("Handler call did not return a TaskResult or dict.")

            # --- 4. Output Parsing/Validation (Basic) ---
            if task_result_dict.get("status") == "COMPLETE" and output_format.get("type") == "json":
                logging.debug(f"Attempting JSON parsing for task: {task_name}")
                try:
                    # Ensure content is a string before parsing
                    content_to_parse = task_result_dict.get("content")
                    if not isinstance(content_to_parse, str):
                        raise TypeError(f"Expected string content for JSON parsing, got {type(content_to_parse)}")
                    parsed_content = json.loads(content_to_parse)
                    task_result_dict["parsedContent"] = parsed_content
                    # TODO: Add schema validation if output_format.schema is provided
                except (json.JSONDecodeError, TypeError) as e:
                    logging.warning(f"Failed to parse JSON output for task '{task_name}': {e}")
                    task_result_dict["notes"] = task_result_dict.get("notes", {})
                    task_result_dict["notes"]["parseError"] = f"JSONDecodeError/TypeError: {e}"
                    # Optionally change status to FAILED? Or keep COMPLETE with error note? Keep COMPLETE for now.
                except Exception as e:
                     logging.exception(f"Unexpected error during output parsing for task '{task_name}': {e}")
                     task_result_dict["notes"] = task_result_dict.get("notes", {})
                     task_result_dict["notes"]["parseError"] = f"Unexpected parsing error: {e}"


            logging.info(f"Atomic task execution finished for '{task_name}' with status: {task_result_dict.get('status')}")
            return task_result_dict

        except ParameterMismatchError as e:
            logging.error(f"Parameter mismatch during execution of task '{task_name}': {e}")
            error_details = TaskError(type="TASK_FAILURE", reason="input_validation_failure", message=str(e))
            return TaskResult(content=str(e), status="FAILED", notes={"error": error_details}).model_dump(exclude_none=True)
        except Exception as e:
            # Catch potential errors from handler call or other unexpected issues
            logging.exception(f"Unexpected error during atomic task execution for '{task_name}': {e}")
            # Map general exceptions to TASK_FAILURE/unexpected_error
            error_reason: TaskFailureReason = "unexpected_error"
            error_type = "TASK_FAILURE"
            # Check if it's a known error type from the handler (if handler raises specific exceptions)
            # Example: if isinstance(e, HandlerLLMError): error_reason = "llm_error"

            error_details = TaskError(type=error_type, reason=error_reason, message=f"Execution failed: {e}")
            return TaskResult(content=f"Execution failed: {e}", status="FAILED", notes={"error": error_details}).model_dump(exclude_none=True)
```