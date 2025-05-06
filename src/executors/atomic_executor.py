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
from src.system.models import TaskResult, TaskFailureReason, TaskFailureError, resolve_model_class, ModelNotFoundError
from pydantic import ValidationError

# Regex to find {{parameter.name.access}} placeholders
PARAM_REGEX = re.compile(r"\{\{([\w.]+)\}\}")  # Allow dots in parameter names

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
        
        def resolve_dot_notation(param_dict, key_string):
            """Helper to access nested dict/object attributes."""
            keys = key_string.split('.')
            val = param_dict
            for key in keys:
                if isinstance(val, dict):
                    if key not in val: raise KeyError(key)
                    val = val[key]
                elif hasattr(val, key):
                    val = getattr(val, key)
                else:
                    raise KeyError(key)  # Or AttributeError
            return val
            
        def replace_match(match):
            full_param_name = match.group(1)  # e.g., "context_input.query"
            try:
                # Use helper to resolve dot notation
                value = resolve_dot_notation(params, full_param_name)
                # Inside replace_match function in _substitute_params, before return
                value_type = type(value)
                value_size = len(value) if hasattr(value, '__len__') else 'N/A'
                logging.debug(f"Substituting '{full_param_name}': Type={value_type}, Size/Len={value_size}")
                
                # Enhanced error handling for str() conversion
                try:
                    result = str(value)  # Try to convert to string
                    return result
                except TypeError as str_err:
                    # More detailed error for str() conversion failure
                    logging.error(f"Failed to convert parameter '{full_param_name}' to string: {str_err}")
                    logging.error(f"Value details: type={value_type}, repr={value!r}")
                    if hasattr(value, '__origin__'):
                        logging.error(f"  __origin__={value.__origin__}, __args__={getattr(value, '__args__', 'N/A')}")
                    # Re-raise with more context
                    raise TypeError(f"Cannot convert parameter '{full_param_name}' to string: {str_err}")
            except (KeyError, AttributeError, TypeError) as e:  # Catch potential errors during access
                logging.error(f"Parameter '{full_param_name}' not found or access error in provided params: {e}")
                missing_params.append(full_param_name)
                # Return the placeholder itself to find all missing ones first
                return match.group(0)

        try:
            substituted_text = PARAM_REGEX.sub(replace_match, text)
            if missing_params:
                raise ParameterMismatchError(f"Missing parameter(s) or access error for substitution: {', '.join(missing_params)}")
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

        # --- START ADDED LOGGING ---
        try:
            # Log types of values within params for detailed debugging
            param_types = {k: type(v).__name__ for k, v in params.items()}
            logging.debug(f"AtomicTaskExecutor received params: {params}")
            logging.debug(f"AtomicTaskExecutor received param types: {param_types}")
            
            # Additional detailed logging for complex objects
            for k, v in params.items():
                if not isinstance(v, (str, int, float, bool, type(None))):
                    logging.debug(f"Complex parameter '{k}' details: {v!r}")
                    if hasattr(v, '__dict__'):
                        logging.debug(f"  __dict__: {v.__dict__}")
                    if hasattr(v, '__origin__'):
                        logging.debug(f"  __origin__: {v.__origin__}")
                        logging.debug(f"  __args__: {getattr(v, '__args__', 'N/A')}")
        except Exception as log_e:
            logging.error(f"Error logging params in AtomicTaskExecutor: {log_e}")
        # --- END ADDED LOGGING ---

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
            # Build file_context string from params if available
            file_context_str = None
            fc = params.get("file_contents")
            if isinstance(fc, dict) and fc:
                pieces = []
                for path, content in fc.items():
                    if content:
                        pieces.append(f"--- File: {path} ---\n{content}\n--- End File: {path} ---")
                file_context_str = "\n\n".join(pieces)
            final_system_prompt = handler._build_system_prompt(
                template=substituted_system_prompt_template,
                file_context=file_context_str
            )

            # Main prompt is the substituted instructions
            main_prompt = substituted_instructions
            if not main_prompt:
                 logging.warning(f"Task '{task_name}' has empty instructions after substitution. Proceeding with empty prompt.")
                 # raise ValueError("Substituted instructions resulted in an empty prompt.") # REMOVE or COMMENT OUT this line
                 main_prompt = "" # Ensure it's an empty string if None/empty
            elif not isinstance(main_prompt, str):
                 logging.error(f"Substituted instructions are not a string (type: {type(main_prompt)}). Value: {main_prompt!r}")
                 raise TypeError("Substituted instructions must result in a string.")

            # Determine model override, if any (passed to handler's call)
            model_override = atomic_task_def.get("model") # TODO: Confirm handler._execute_llm_call supports this

            # Initialize task notes that we might add to
            task_notes = {}
            
            # Determine output type override based on output_format.schema if provided
            output_format = atomic_task_def.get("output_format", {})
            output_type_override: Optional[Type] = None
            
            # Check if output_format.schema is provided
            schema_name = output_format.get("schema")
            if schema_name:
                try:
                    # Try to resolve the model class from the schema name
                    logging.debug(f"Attempting to resolve model class for schema: {schema_name}")
                    output_type_override = resolve_model_class(schema_name)
                    logging.info(f"Using output_type_override {output_type_override.__name__} for task: {task_name}")
                except ModelNotFoundError as e:
                    # Log the error but don't fail the task yet - let handler try to execute without the type
                    logging.warning(f"Failed to resolve model class for schema {schema_name}: {e}")
                    # Add a warning note to the task result (will be created later)
                    task_notes["schema_warning"] = f"Failed to resolve model class for schema {schema_name}: {e}"
                except Exception as e:
                    # Log unexpected errors during model resolution
                    logging.error(f"Unexpected error resolving model class for schema {schema_name}: {e}")
                    # Add an error note to the task result (will be created later)
                    task_notes["schema_error"] = f"Unexpected error resolving model class: {e}"
            
            # --- 3. Invoke Handler ---
            logging.debug(f"Invoking handler._execute_llm_call for task: {task_name}")
            # Add debug logging for prompt
            logging.debug(f"Passing prompt to handler (type: {type(main_prompt)}, length: {len(main_prompt)}): '{main_prompt[:200]}...'")
            # Log if we're using an output_type_override
            if output_type_override:
                logging.debug(f"Using output_type_override: {output_type_override.__name__}")
            
            # Pass necessary overrides to the handler
            handler_result = handler._execute_llm_call(
                prompt=main_prompt,
                system_prompt_override=final_system_prompt,
                tools_override=None, # Atomic executor doesn't handle tool registration itself
                output_type_override=output_type_override,
                # model_override=model_override # Pass if handler supports it
            )

            # Ensure result is a dict or TaskResult object
            if isinstance(handler_result, dict):
                # For the handler result dict case, convert to TaskResult for validation
                handler_result_obj = TaskResult.model_validate(handler_result)
                task_result_dict = handler_result  # Use the original dict
            elif isinstance(handler_result, TaskResult):
                handler_result_obj = handler_result
                task_result_dict = handler_result.model_dump(exclude_none=True)
            else:
                logging.error(f"Handler._execute_llm_call returned unexpected type: {type(handler_result)}")
                # This indicates a bug in the handler or its manager
                raise TypeError("Handler call did not return a TaskResult object or dict.")

            # --- 4. Handle Parsed Content ---
            # Merge task_notes into the task result notes
            if task_notes:
                task_result_dict.setdefault("notes", {}).update(task_notes)
            
            # Check if parsed_content was returned by the handler (from pydantic-ai)
            if "parsed_content" in task_result_dict and task_result_dict["status"] == "COMPLETE":
                # Use the parsed_content from the handler if it exists
                logging.debug(f"Using parsed_content from handler for task: {task_name}")
                task_result_dict["parsedContent"] = task_result_dict.pop("parsed_content")
            # Otherwise, try the old JSON parsing approach if needed
            elif task_result_dict.get("status") == "COMPLETE" and output_format.get("type") == "json" and "parsedContent" not in task_result_dict:
                logging.debug(f"Attempting legacy JSON parsing for task: {task_name}")
                content_to_parse = task_result_dict.get("content")
                if isinstance(content_to_parse, str):
                    try:
                        parsed_content = json.loads(content_to_parse)
                        task_result_dict["parsedContent"] = parsed_content
                        logging.debug(f"Legacy JSON parsing successful for task: {task_name}")
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

        except (ParameterMismatchError, ValueError, TypeError) as e:
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
