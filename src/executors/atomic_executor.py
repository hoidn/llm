"""
Atomic Task Executor implementation.
Executes the body of a pre-parsed atomic task template.
"""

import logging
import re
import json
from typing import Any, Dict, Optional, Type, List, Callable, Tuple # Added Type, List, Callable, Tuple

# Assuming BaseHandler and TaskResult types are available for hinting
# from src.handler.base_handler import BaseHandler # Import actual when available
from src.handler.base_handler import BaseHandler # Ensure BaseHandler is imported for type hinting
from src.system.models import TaskResult, TaskFailureReason, TaskFailureError, resolve_model_class, ModelNotFoundError, HistoryConfigSettings
from pydantic import ValidationError

# Regex to find {{parameter.name.access}} placeholders
# MODIFIED: Added '-' to the character set to allow hyphens in names
PARAM_REGEX = re.compile(r"\{\{([\w.-]+)\}\}")  # Allow dots and hyphens in parameter names

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
            # Add logging before returning
            logging.debug(f"    _resolve_dot_notation: Resolved '{key_string}' to value type {type(val).__name__}")
            return val
            
        def replace_match(match):
            full_param_name = match.group(1)  # e.g., "context_input.query"
            logging.debug(f"  _substitute_params: Attempting to substitute placeholder '{{{{{full_param_name}}}}}'") # Log placeholder
            logging.debug(f"  _substitute_params: Available keys in params dict: {list(params.keys())}") # Log available keys
            try:
                # Use helper to resolve dot notation
                value = resolve_dot_notation(params, full_param_name)
                # --- Log value BEFORE str() ---
                logging.debug(f"  _substitute_params: Value for '{full_param_name}' is: {value!r} (Type: {type(value).__name__})")
                # --- End log ---
                value_type = type(value)
                value_size = len(value) if hasattr(value, '__len__') else 'N/A'
                logging.debug(f"  Substituting '{full_param_name}': Type={value_type}, Size/Len={value_size}")
                
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
                logging.error(f"  _substitute_params: Parameter '{full_param_name}' not found or access error in provided params: {params}. Error: {e}")
                missing_params.append(full_param_name)
                # Return the placeholder itself to find all missing ones first
                return match.group(0)

        # --- Add logging for input text ---
        logging.debug(f"--- _substitute_params processing text (first 500 chars): --- \n{text[:500] if text else 'None'}\n-------------------------------------")
        # --- End logging ---
        
        try:
            substituted_text = PARAM_REGEX.sub(replace_match, text)
            if missing_params:
                # This specific ParameterMismatchError for missing keys is fine
                raise ParameterMismatchError(f"Missing parameter(s) or access error for substitution: {', '.join(missing_params)}")
            return substituted_text
        except ParameterMismatchError:  # Explicitly catch the one we raise above
            raise  # Re-raise it if it was about missing params
        except Exception as e:
            # Catch potential errors during string conversion or regex
            logging.exception(f"Unexpected error during parameter substitution: {e}")
            # Re-raise the original exception to get the full traceback
            raise e  # Re-raise the original exception to get the full traceback


    def execute_body(
        self,
        atomic_task_def: Dict[str, Any], # Renamed from template to atomic_task_def for clarity
        params: Dict[str, Any],
        handler: BaseHandler, # Use specific type hint
        history_config: Optional[HistoryConfigSettings] = None
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

        # --- START REFINED EXCEPTION HANDLING ---
        substituted_instructions = None
        substituted_system_prompt_template = None
        output_type_override: Optional[Type] = None # Renamed from output_type_model
        task_notes = {}

        try:
            # --- 1. Parameter Substitution (Isolate this step) ---
            logging.debug(f"Substituting parameters for task: {task_name} using params: {list(params.keys())}")
            template_instructions = atomic_task_def.get("instructions") # Use atomic_task_def
            substituted_instructions = self._substitute_params(template_instructions, params)
            substituted_system_prompt_template = self._substitute_params(atomic_task_def.get("system"), params) # Use atomic_task_def
            logging.debug("Parameter substitution successful.")

            # --- 2. Determine Output Type Override (Isolate this step) ---
            output_format_config = atomic_task_def.get("output_format", {}) # Use atomic_task_def, rename var
            schema_name = output_format.get("schema")
            if schema_name:
                try:
                    logging.debug(f"Attempting to resolve model class for schema: {schema_name}")
                    output_type_override = resolve_model_class(schema_name)
                    logging.info(f"Using output_type_override {output_type_override.__name__} for task: {task_name}")
                except ModelNotFoundError as e:
                    logging.warning(f"Failed to resolve model class for schema {schema_name}: {e}")
                    task_notes["schema_warning"] = f"Failed to resolve model class for schema {schema_name}: {e}"
                except Exception as e:
                    logging.error(f"Unexpected error resolving model class for schema {schema_name}: {e}")
                    task_notes["schema_error"] = f"Unexpected error resolving model class: {e}"

        except (ParameterMismatchError, ValueError, TypeError) as sub_err:
            # Catch errors ONLY from substitution or output type resolution
            logging.error(f"Parameter substitution or type resolution failed for task '{task_name}': {sub_err}")
            error_details = TaskFailureError(type="TASK_FAILURE", reason="input_validation_failure", message=str(sub_err))
            return TaskResult(content=str(sub_err), status="FAILED", notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)
        except Exception as setup_err:
            # Catch other unexpected errors during setup
             logging.exception(f"Unexpected setup error for task '{task_name}': {setup_err}")
             error_details = TaskFailureError(type="TASK_FAILURE", reason="unexpected_error", message=f"Task setup failed: {setup_err}")
             return TaskResult(content=f"Task setup failed: {setup_err}", status="FAILED", notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)


        # --- 3. Construct Handler Payload & Invoke Handler ---
        try:
            # Build the final system prompt
            # The 'substituted_system_prompt_template' is the content from the template's 'system' field,
            # after its own {{placeholders}} have been filled. This becomes the 'template_specific_instructions'.
            final_system_prompt = handler._build_system_prompt(
                template_specific_instructions=substituted_system_prompt_template
            )

            # Main prompt for the LLM is the content from the template's 'instructions' field,
            # after its {{placeholders}} have been filled.
            main_prompt = substituted_instructions
            if not main_prompt:
                logging.warning(f"Task '{task_name}' has empty instructions after substitution.")
                main_prompt = ""
            elif not isinstance(main_prompt, str):
                 logging.error(f"Substituted instructions are not a string (type: {type(main_prompt)}).")
                 raise TypeError("Substituted instructions must result in a string.") # Raise specific error

            # Invoke Handler - THIS is where the TypeError might happen
            logging.debug(f"Invoking handler._execute_llm_call for task: {task_name}")
            logging.debug(f"Passing prompt to handler (type: {type(main_prompt)}, length: {len(main_prompt)}): '{main_prompt[:200]}...'")
            if output_type_override:
                logging.debug(f"Using output_type_override: {output_type_override.__name__}")
            
            # Pass the effective_history_config
            effective_history_config = history_config # Use the one passed in if available

            handler_result = handler._execute_llm_call(
                prompt=main_prompt,
                system_prompt_override=final_system_prompt,
                task_tools_config=task_tools_config_override, # MODIFIED: Pass the tuple
                output_type_override=output_type_override, # Use renamed variable
                model_override=atomic_task_def.get("model"), # Pass model if specified
                history_config=effective_history_config # Pass history_config
            )

            # --- 4. Process Handler Result ---
            if isinstance(handler_result, dict):
                handler_result_obj = TaskResult.model_validate(handler_result)
                task_result_dict = handler_result
            elif isinstance(handler_result, TaskResult):
                handler_result_obj = handler_result
                task_result_dict = handler_result.model_dump(exclude_none=True)
            else:
                raise TypeError("Handler call did not return a TaskResult object or dict.")

            # Merge task_notes into the task result notes
            if task_notes:
                task_result_dict.setdefault("notes", {}).update(task_notes)

            # Process parsed_content
            if "parsed_content" in task_result_dict and task_result_dict["status"] == "COMPLETE":
                logging.debug(f"Using parsed_content from handler for task: {task_name}")
                task_result_dict["parsedContent"] = task_result_dict.pop("parsed_content")
            elif task_result_dict.get("status") == "COMPLETE" and output_format_config.get("type") == "json" and "parsedContent" not in task_result_dict: # Use output_format_config
                logging.debug(f"Attempting legacy JSON parsing for task: {task_name}")
                content_to_parse = task_result_dict.get("content")
                if isinstance(content_to_parse, str):
                    try:
                        parsed_content = json.loads(content_to_parse)
                        task_result_dict["parsedContent"] = parsed_content
                        logging.debug(f"Legacy JSON parsing successful for task: {task_name}")
                    except json.JSONDecodeError as e:
                        logging.warning(f"Failed to parse JSON output for task '{task_name}': {e}")
                        task_result_dict.setdefault("notes", {})["parseError"] = f"JSONDecodeError: {e}"
                    except Exception as e:
                        logging.exception(f"Unexpected error during output parsing for task '{task_name}': {e}")
                        task_result_dict.setdefault("notes", {})["parseError"] = f"Unexpected parsing error: {e}"
                else:
                    logging.warning(f"Cannot parse non-string content of type {type(content_to_parse)} as JSON for task '{task_name}'.")
                    task_result_dict.setdefault("notes", {})["parseError"] = f"Cannot parse non-string content ({type(content_to_parse)}) as JSON."

            logging.info(f"Atomic task execution finished for '{task_name}' with status: {task_result_dict.get('status')}")
            return task_result_dict

        # --- Specific Handling for TypeError from Handler Call ---
        except TypeError as type_err:
             logging.exception(f"TypeError occurred during handler call for task '{task_name}': {type_err}")
             # Check if it's the specific Union error
             if "Cannot instantiate typing.Union" in str(type_err):
                 error_reason = "llm_error" # Or maybe 'dependency_error'?
                 error_msg = f"LLM interaction failed (TypeError: {type_err})"
             else:
                 error_reason = "unexpected_error"
                 error_msg = f"Unexpected TypeError during handler call: {type_err}"
             error_details = TaskFailureError(type="TASK_FAILURE", reason=error_reason, message=error_msg)
             return TaskResult(content=error_msg, status="FAILED", notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)

        # --- Catch other potential errors from the handler call ---
        except Exception as handler_err:
            logging.exception(f"Unexpected error during handler call for task '{task_name}': {handler_err}")
            # Determine if it's an error propagated from the handler (e.g., LLM error)
            error_reason: TaskFailureReason = "llm_error" # Assume LLM error if from handler
            error_type = "TASK_FAILURE"
            error_details = TaskFailureError(type=error_type, reason=error_reason, message=f"Handler execution failed: {handler_err}")
            return TaskResult(content=f"Handler execution failed: {handler_err}", status="FAILED", notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)
        # --- END REFINED EXCEPTION HANDLING ---
