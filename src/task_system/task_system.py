import logging
import json
from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING
from pydantic import ValidationError as PydanticValidationError

# Use TYPE_CHECKING block for circular imports
if TYPE_CHECKING:
    from src.memory.memory_system import MemorySystem
    from src.handler.base_handler import BaseHandler

from .file_path_resolver import resolve_paths_from_template
from .template_registry import TemplateRegistry
from src.system.models import (
    SubtaskRequest, TaskResult, ContextManagement,
    ContextGenerationInput, AssociativeMatchResult, MatchTuple,
    SUBTASK_CONTEXT_DEFAULTS, TaskError, TaskFailureError, TaskFailureReason # Added TaskFailureError, TaskFailureReason
)
# Import the executor and its specific error
from src.executors.atomic_executor import AtomicTaskExecutor, ParameterMismatchError

# Import for find_matching_tasks
from difflib import SequenceMatcher

# Constants for find_matching_tasks
MATCH_THRESHOLD = 0.6 # Increased threshold to fix tests

class TaskSystem:
    """
    Manages and executes task templates.

    Complies with the contract defined in src/task_system/task_system_IDL.md.
    """

    def __init__(self, memory_system: Optional['MemorySystem'] = None, handler: Optional['BaseHandler'] = None):
        """
        Initializes the Task System.

        Args:
            memory_system: An optional instance of MemorySystem.
            handler: An optional instance of BaseHandler.
        """
        self.memory_system = memory_system
        self._registry = TemplateRegistry()
        self._test_mode: bool = False
        self._handler: Optional[BaseHandler] = handler # Store injected handler
        self._atomic_executor = AtomicTaskExecutor() # Instantiate the executor
        logging.info("TaskSystem initialized.")

    def set_test_mode(self, enabled: bool) -> None:
        """
        Enables or disables test mode.

        Args:
            enabled: Boolean value to enable/disable test mode.
        """
        self._test_mode = enabled
        logging.info(f"TaskSystem test mode set to: {enabled}")

    def set_handler(self, handler: 'BaseHandler'):
        """Allows injecting the handler after TaskSystem initialization."""
        logging.debug(f"TaskSystem: Handler instance set: {handler}")
        self._handler = handler
        
    def _get_handler(self) -> 'BaseHandler':
        """Returns the configured handler instance."""
        # Return the stored handler instance
        if self._handler is None:
            logging.error("Handler requested from TaskSystem but not set.")
            # Raise error as handler is crucial for execution
            raise RuntimeError("Handler not available in TaskSystem. Ensure it's injected via constructor or set_handler.")
        return self._handler

    def _validate_and_merge_context_settings(
        self,
        template_settings: Optional[Dict[str, Any]],
        request_settings: Optional[Dict[str, Any]],
        subtype: str
    ) -> Tuple[Optional[ContextManagement], Optional[TaskError]]:
        """Validates and merges context settings from template and request."""
        # Start with subtype defaults
        merged_settings = SUBTASK_CONTEXT_DEFAULTS.model_copy(deep=True) # Use defaults for 'subtask' as base

        # Apply template settings
        if template_settings:
            try:
                # Validate template settings structure first
                ContextManagement.model_validate(template_settings)
                merged_settings = merged_settings.model_copy(update=template_settings)
            except PydanticValidationError as e:
                msg = f"Invalid context_management in template: {e}"
                logging.error(msg)
                # Use the TaskError model for structured errors
                error_obj = TaskFailureError(type="TASK_FAILURE", reason="input_validation_failure", message=msg)
                return None, error_obj

        # Apply request overrides
        if request_settings:
            try:
                # Validate request settings structure
                ContextManagement.model_validate(request_settings) # Validate partial is tricky, validate full structure
                # Filter out None values from request_settings before updating
                valid_request_settings = {k: v for k, v in request_settings.items() if v is not None}
                merged_settings = merged_settings.model_copy(update=valid_request_settings)
            except PydanticValidationError as e:
                msg = f"Invalid context_management override in request: {e}"
                logging.error(msg)
                error_obj = TaskFailureError(type="TASK_FAILURE", reason="input_validation_failure", message=msg)
                return None, error_obj

        # Final validation of merged settings (e.g., mutual exclusivity)
        try:
            if merged_settings.freshContext == "enabled" and merged_settings.inheritContext in ["full", "subset"]:
                raise ValueError("freshContext='enabled' cannot be combined with inheritContext='full' or 'subset'")
            # Validate the final merged object
            final_context = ContextManagement.model_validate(merged_settings.model_dump())
            return final_context, None
        except (PydanticValidationError, ValueError) as e:
            msg = f"Context validation failed after merging: {e}"
            logging.error(msg)
            error_obj = TaskFailureError(type="TASK_FAILURE", reason="input_validation_failure", message=msg)
            return None, error_obj


    def execute_atomic_template(self, request: SubtaskRequest) -> TaskResult:
        """
        Executes a single *atomic* Task System template workflow directly from a SubtaskRequest.

        Args:
            request: A valid SubtaskRequest object.

        Returns:
            The final TaskResult from the executed atomic template.
        """
        logging.info(f"Executing atomic template request: {request.name} (Task ID: {request.task_id})")

        # 1. Find Template
        template_def = self.find_template(request.name)
        if not template_def:
            logging.error(f"Template not found for name: {request.name}")
            error = TaskFailureError(type="TASK_FAILURE", reason="template_not_found", message=f"Template not found: {request.name}")
            return TaskResult(content=f"Template not found: {request.name}", status="FAILED", notes={"error": error})

        # Ensure it's actually atomic (should be guaranteed by find_template, but double-check)
        if template_def.get("type") != "atomic":
             logging.error(f"Attempted to execute non-atomic template '{request.name}' via execute_atomic_template.")
             error = TaskFailureError(type="TASK_FAILURE", reason="input_validation_failure", message="Cannot execute non-atomic template directly")
             return TaskResult(content="Cannot execute non-atomic template directly", status="FAILED", notes={"error": error})

        subtype = template_def.get("subtype", "standard") # Default subtype if missing

        # 2. Get Handler (placeholder for actual handler retrieval)
        try:
            handler = self._get_handler()
        except RuntimeError as e:
             logging.exception("Failed to get handler instance.")
             error = TaskFailureError(type="TASK_FAILURE", reason="dependency_error", message=f"Failed to get handler: {e}")
             return TaskResult(content=f"Failed to get handler: {e}", status="FAILED", notes={"error": error})


        # 3. Resolve Context Management Settings
        template_context_settings = template_def.get("context_management")
        request_context_settings = request.context_management.model_dump(exclude_none=True) if request.context_management else None

        final_context_settings, context_error = self._validate_and_merge_context_settings(
            template_context_settings, request_context_settings, subtype
        )
        if context_error:
            # context_error is already a TaskError object
            return TaskResult(content=context_error.message, status="FAILED", notes={"error": context_error})

        # 4. Resolve File Paths
        file_paths = []
        context_source_note = "none"
        if request.file_paths:
            # Explicit paths provided in the request take precedence
            file_paths = request.file_paths
            context_source_note = "explicit_request"
            logging.debug(f"Using explicit file paths from request: {file_paths}")
        elif final_context_settings and final_context_settings.freshContext == "enabled":
            # Resolve paths based on template definition if fresh context is enabled
            resolved_paths, resolve_error = self.resolve_file_paths(template_def, self.memory_system, handler)
            if resolve_error:
                logging.warning(f"File path resolution failed for template '{request.name}': {resolve_error}")
                # Decide if this is fatal. For now, continue without files.
                # Could return error: TaskFailureError(type="TASK_FAILURE", reason="context_retrieval_failure", message=resolve_error)
                context_source_note = "resolution_failed"
            else:
                file_paths = resolved_paths
                # Use get() with default for safer access
                file_paths_source_dict = template_def.get("file_paths_source", {})
                context_source_note = file_paths_source_dict.get("type", "template_literal") # More specific note
                logging.debug(f"Resolved file paths from template: {file_paths}")
        else:
             logging.debug(f"No explicit file paths and fresh context disabled for template '{request.name}'.")


        # 5. Fetch Context (if needed - currently handled by AtomicTaskExecutor/Handler)
        # The current AtomicTaskExecutor IDL doesn't take file_context directly.
        # Context fetching logic might need refinement here or within the handler/executor.
        # For now, we assume the handler's _execute_llm_call uses the file_paths if needed.
        # We will pass file_paths to the executor for potential future use or logging.
        context_summary = "Context handling delegated to Handler/Executor" # Placeholder note

        # 6. Execute Atomic Task Body
        try:
            # Execute using the instantiated executor
            # This call now returns a dictionary directly
            result_dict = self._atomic_executor.execute_body(
                atomic_task_def=template_def,
                params=request.inputs,
                handler=handler
                # file_paths=file_paths, # Pass files if executor signature changes
                # context_summary=context_summary # Pass context if executor signature changes
            )
            # Validate the dictionary against TaskResult model before returning
            final_result = TaskResult.model_validate(result_dict)

        # Note: ParameterMismatchError is now handled inside execute_body and returns a dict
        # So, we only need to catch other potential exceptions from execute_body here.
        except Exception as e:
            logging.exception(f"Unexpected error executing template body for '{request.name}': {e}")
            # Create error dictionary directly instead of using TaskFailureError object
            error_dict = {
                "type": "TASK_FAILURE",
                "reason": "unexpected_error",
                "message": f"Execution failed: {e}"
            }
            final_result = TaskResult(content=f"Execution failed: {e}", status="FAILED", notes={"error": error_dict})

        # 7. Augment Result Notes
        if final_result.notes is None:
             final_result.notes = {}
        final_result.notes["template_used"] = request.name
        final_result.notes["task_id"] = request.task_id
        final_result.notes["context_source"] = context_source_note
        final_result.notes["file_count"] = len(file_paths)
        # Add merged context settings for debugging?
        # final_result.notes["context_settings"] = final_context_settings.model_dump() if final_context_settings else None

        logging.info(f"Finished atomic template execution for '{request.name}' with status: {final_result.status}")
        return final_result


    def find_matching_tasks(
        self, input_text: str, memory_system: Optional['MemorySystem'] # Keep optional for now
    ) -> List[Dict[str, Any]]:
        """
        Finds matching atomic task templates based on similarity to input text.

        Args:
            input_text: A string describing the desired task.
            memory_system: A valid MemorySystem instance (currently unused, placeholder).

        Returns:
            A list of dictionaries, each representing a matching template, sorted by score.
            Format: [{"score": float, "task": Dict[str, Any], "taskType": "atomic", "subtype": str}]
        """
        if not input_text:
            return []

        matches = []
        # Iterate through all atomic templates from the registry
        for template in self._registry.get_all_atomic_templates():
            name = template.get("name")
            if not name:
                continue # Should not happen if registered correctly

            description = template.get("description")
            if not description:
                continue # Cannot match without description

            # Simple similarity check using SequenceMatcher
            similarity = SequenceMatcher(None, input_text.lower(), description.lower()).ratio()
            logging.debug(f"Template '{name}' similarity score: {similarity} (Threshold: {MATCH_THRESHOLD})") # Debug score

            if similarity >= MATCH_THRESHOLD:
                matches.append({
                    "score": similarity,
                    "task": template, # Include the full template definition
                    "taskType": "atomic",
                    "subtype": template.get("subtype", "standard") # Include subtype
                })

        # Sort matches by score in descending order
        matches.sort(key=lambda x: x["score"], reverse=True)

        logging.info(f"Found {len(matches)} matching atomic tasks for input: '{input_text[:50]}...'")
        return matches


    def register_template(self, template: Dict[str, Any]) -> None:
        """
        Delegates template registration to the internal registry.
        
        Args:
            template: A dictionary representing the template.
        """
        # Validation and storage is now handled by the registry
        self._registry.register(template)
        # Return value from registry indicates success/failure, but TaskSystem method is void

    def find_template(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Delegates template finding to the internal registry.
        
        Args:
            identifier: The template's unique 'name' or 'atomic:subtype'.
            
        Returns:
            The atomic template definition dictionary if found, otherwise None.
        """
        return self._registry.find(identifier)

    def resolve_file_paths(
        self,
        template: Dict[str, Any],
        memory_system: Optional['MemorySystem'],
        handler: Optional['BaseHandler'],
    ) -> Tuple[List[str], Optional[str]]:
        """
        Resolves the final list of file paths by delegating to the utility function.
        (Original detailed docstring is now in file_path_resolver.py)
        """
        # Delegate directly to the extracted utility function
        return resolve_paths_from_template(template, memory_system, handler)
