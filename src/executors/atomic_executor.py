"""
Atomic Task Executor implementation.
Executes the body of a pre-parsed atomic task template.
"""

import logging
import re
import json
from typing import Any, Dict, Optional, Type # Added Type for output_type_override hint

# Assuming BaseHandler and TaskResult types are available for hinting
# from src.handler.base_handler import BaseHandler # Import actual when available
from src.system.models import TaskResult, TaskFailureReason, TaskFailureError
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
    Adheres to Unified ADR XX mandates regarding parameter substitution scope.
    """

    def __init__(self):
        """Initializes the AtomicTaskExecutor."""
        logging.debug("AtomicTaskExecutor initialized.")

    def _substitute_params(self, text: Optional[str], params: Dict[str, Any]) -> Optional[str]:
        """
        Performs {{parameter_name}} substitution in a string.
        Crucially, ONLY uses the provided `params` dictionary for substitution.
        """
        if text is None:
            return None

        missing_params = []
        def replace_match(match):
            param_name = match.group(1)
            if param_name not in params:
                logging.error(f"Parameter '{param_name}' not found in provided params: {list(params.keys())}")
                missing_params.append(param_name)
                # Return the placeholder itself to find all missing ones first
                return match.group(0)
            # Convert param value to string for substitution
            return str(params[param_name])

        try:
            substituted_text = PARAM_REGEX.sub(replace_match, text)
            if missing_params:
                raise ParameterMismatchError(f"Missing parameter(s) for substitution: {', '.join(missing_params)}")
            return substituted_text
        except Exception as e:
            # Catch potential errors during string conversion or regex
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
                               Expected keys: 'name', 'instructions', 'system' (optional),
                               'model' (optional), 'output_format' (optional).
            params: A dictionary mapping declared input parameter names to their evaluated values.
                    Substitution ONLY uses these values.
            handler: A valid BaseHandler instance to use for LLM execution.

        Returns:
            A dictionary representing the TaskResult outcome.
            Returns FAILED TaskResult on parameter mismatch or handler errors.
        """
        task_name = atomic_task_def.get("name", "unnamed_atomic_task")
        logging.info(f"Executing atomic task body for: {task_name}")

        try:
            # --- 1. Parameter Substitution (Strictly from params) ---
            logging.debug(f"Substituting parameters for task: {task_name} using params: {list(params.keys())}")
            substituted_instructions = self._substitute_params(atomic_task_def.get("instructions"), params)
            substituted_system_prompt_template = self._substitute_params(atomic_task_def.get("system"), params)
            # Note: Substitution does not access any wider environment.

            # --- 2. Construct Handler Payload ---
            # Build the final system prompt using the handler's method
            # File context is explicitly None as per IDL/ADR for atomic execution body.
            # Context must be prepared by the caller (e.g., TaskSystem) if needed.
            final_system_prompt = handler._build_system_prompt(
                template=substituted_system_prompt_template,
                file_context=None
            )

            # Main prompt is the substituted instructions
            main_prompt = substituted_instructions
            if not main_prompt:
                 logging.warning(f"Task '{task_name}' has empty instructions after substitution.")
                 main_prompt = "" # Proceed with empty prompt

            # Determine model override, if any (passed to handler's call)
            model_override = atomic_task_def.get("model") # TODO: Confirm handler._execute_llm_call supports this

            # Determine output type override, if any
            output_format = atomic_task_def.get("output_format", {})
            output_type_override: Optional[Type] = None
            # TODO: Implement robust mapping from output_format schema (e.g., {"type": "json", "schema": {...}})
            # to actual Pydantic models or standard types (Dict, List, etc.) for pydantic-ai.
            # Placeholder:
            # if output_format.get("type") == "json":
            #     # Basic check, needs schema mapping for real use
            #     output_type_override = Dict[str, Any]

            # --- 3. Invoke Handler ---
            logging.debug(f"Invoking handler._execute_llm_call for task: {task_name}")
            # Assuming _execute_llm_call returns a TaskResult object or raises errors
            # Pass necessary overrides.
            handler_result_obj: TaskResult = handler._execute_llm_call(
                prompt=main_prompt,
                system_prompt_override=final_system_prompt,
                tools_override=None, # Atomic executor doesn't handle tool registration itself
                output_type_override=output_type_override,
                # model_override=model_override # Pass if handler supports it
            )

            # Ensure result is a TaskResult object (handler should guarantee this or raise)
            if not isinstance(handler_result_obj, TaskResult):
                 logging.error(f"Handler._execute_llm_call returned unexpected type: {type(handler_result_obj)}")
                 # This indicates a bug in the handler or its manager
                 raise TypeError("Handler call did not return a TaskResult object.")

            task_result_dict = handler_result_obj.model_dump(exclude_none=True)

            # --- 4. Output Parsing/Validation (If specified and COMPLETE) ---
            if task_result_dict.get("status") == "COMPLETE" and output_format.get("type") == "json":
                logging.debug(f"Attempting JSON parsing for task: {task_name}")
                content_to_parse = task_result_dict.get("content")
                if isinstance(content_to_parse, str):
                    try:
                        parsed_content = json.loads(content_to_parse)
                        task_result_dict["parsedContent"] = parsed_content
                        # TODO: Add schema validation if output_format.schema is provided
                        logging.debug(f"JSON parsing successful for task: {task_name}")
                    except json.JSONDecodeError as e:
                        logging.warning(f"Failed to parse JSON output for task '{task_name}': {e}")
                        # Add parse error note, keep status COMPLETE as LLM finished
                        task_result_dict.setdefault("notes", {})["parseError"] = f"JSONDecodeError: {e}"
                    except Exception as e:
                         logging.exception(f"Unexpected error during output parsing for task '{task_name}': {e}")
                         task_result_dict.setdefault("notes", {})["parseError"] = f"Unexpected parsing error: {e}"
                else:
                    logging.warning(f"Cannot parse non-string content of type {type(content_to_parse)} as JSON for task '{task_name}'.")
                    task_result_dict.setdefault("notes", {})["parseError"] = f"Cannot parse non-string content ({type(content_to_parse)}) as JSON."


            logging.info(f"Atomic task execution finished for '{task_name}' with status: {task_result_dict.get('status')}")
            return task_result_dict

        except ParameterMismatchError as e:
            logging.error(f"Parameter mismatch during execution of task '{task_name}': {e}")
            # Create FAILED TaskResult as per IDL/ADR
            error_details = TaskFailureError(type="TASK_FAILURE", reason="input_validation_failure", message=str(e))
            return TaskResult(content=str(e), status="FAILED", notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)

        except Exception as e:
            # Catch potential errors from handler call (if not caught internally) or other unexpected issues
            logging.exception(f"Unexpected error during atomic task execution for '{task_name}': {e}")
            # Determine if it's an error propagated from the handler (e.g., LLM error)
            # For now, map general exceptions to TASK_FAILURE/unexpected_error
            error_reason: TaskFailureReason = "unexpected_error"
            error_type = "TASK_FAILURE"
            # Example: Check if handler raised a specific exception type if applicable

            error_details = TaskFailureError(type=error_type, reason=error_reason, message=f"Execution failed unexpectedly: {e}")
            return TaskResult(content=f"Execution failed: {e}", status="FAILED", notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)
