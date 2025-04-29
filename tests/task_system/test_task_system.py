"""
TaskSystem manages the registration, lookup, and execution orchestration of tasks.
It interacts with MemorySystem for context and BaseHandler for execution resources.
"""

import logging
import json
from typing import Any, Dict, List, Optional, Tuple

# Assuming MemorySystem and BaseHandler types are available for hinting
# from src.memory.memory_system import MemorySystem # Import actual when available
# from src.handler.base_handler import BaseHandler # Import actual when available
from src.system.models import (
    SubtaskRequest, TaskResult, ContextManagement,
    ContextGenerationInput, AssociativeMatchResult, MatchTuple,
    SUBTASK_CONTEXT_DEFAULTS, TaskError, TaskFailureReason
)
# Placeholder for the actual executor - will be mocked in tests for Phase 2c
# from src.executors.atomic_executor import AtomicTaskExecutor
from pydantic import ValidationError


# Placeholder for the actual executor class until Phase 3
class AtomicTaskExecutor:
    def execute_body(self, template, params, handler, context, files):
        # This is a placeholder implementation for Phase 2c testing
        logging.warning("Using placeholder AtomicTaskExecutor.execute_body")
        if params.get("fail_execution"):
             raise ValueError("Executor forced fail")
        # Simulate basic success
        return TaskResult(
            content=f"Executed {template.get('name', 'unknown_template')}",
            status="COMPLETE",
            notes={"executor": "placeholder"}
        )

class TaskSystem:
    """
    Manages and executes task templates.

    Complies with the contract defined in src/task_system/task_system_IDL.md.
    """

    def __init__(self, memory_system: Optional[Any] = None):  # MemorySystem
        """
        Initializes the TaskSystem.

        Args:
            memory_system: An instance of MemorySystem for context retrieval.
        """
        self.memory_system = memory_system
        self.templates: Dict[str, Dict[str, Any]] = {}  # name -> template_dict
        self.template_index: Dict[str, str] = {}  # type:subtype -> name
        self._test_mode: bool = False
        # Handler cache might be used to store/retrieve handler instances if needed
        self._handler_cache: Dict[str, Any] = {} # Key could be config hash or session ID
        logging.info("TaskSystem initialized.")
        if not self.memory_system:
            logging.warning("TaskSystem initialized without a MemorySystem.")

    def set_test_mode(self, enabled: bool) -> None:
        """
        Enables or disables test mode.

        In test mode, certain optimizations or caching might be disabled.
        Currently, it clears the handler cache when the mode changes.

        Args:
            enabled: True to enable test mode, False to disable.
        """
        if self._test_mode != enabled:
            logging.info(f"Setting TaskSystem test mode to: {enabled}")
            self._test_mode = enabled
            # Clear handler cache when mode changes, as handlers might be stateful
            self._handler_cache = {}
            logging.debug("Handler cache cleared due to test mode change.")
        else:
            logging.debug(f"TaskSystem test mode already set to: {enabled}")

    def register_template(self, template: Dict[str, Any]) -> None:
        """
        Registers an atomic task template.

        Non-atomic templates are ignored with a warning.
        Atomic templates require 'name' and 'subtype'.

        Args:
            template: The template dictionary to register.
        """
        template_type = template.get("type")
        template_name = template.get("name")
        template_subtype = template.get("subtype")

        if template_type != "atomic":
            logging.warning(
                f"Ignoring registration attempt for non-atomic template '{template_name or 'Unnamed'}'. "
                f"Type: {template_type}. TaskSystem only handles 'atomic' registration."
            )
            return

        if not template_name or not template_subtype:
            logging.error(
                f"Atomic template registration failed: Missing 'name' or 'subtype'. "
                f"Name: {template_name}, Subtype: {template_subtype}. Template not registered."
            )
            return

        if "params" not in template:
             logging.warning(
                 f"Atomic template '{template_name}' registered without a 'params' attribute. "
                 f"Validation might fail later during execution."
             )

        # Overwrite existing template with the same name
        if template_name in self.templates:
            logging.warning(
                f"Overwriting existing template registration for name: {template_name}"
            )
            # Clean up old index entry if subtype changed
            old_template = self.templates[template_name]
            old_subtype = old_template.get("subtype")
            if old_subtype and old_subtype != template_subtype:
                old_key = f"atomic:{old_subtype}"
                if self.template_index.get(old_key) == template_name:
                    del self.template_index[old_key]
                    logging.debug(f"Removed old index entry: {old_key}")

        self.templates[template_name] = template
        index_key = f"atomic:{template_subtype}"
        self.template_index[index_key] = template_name
        logging.info(f"Registered atomic template: '{template_name}' (Type: {template_type}, Subtype: {template_subtype})")

    def find_template(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Finds a registered atomic template by name or type:subtype identifier.

        Args:
            identifier: The name or type:subtype string.

        Returns:
            The template dictionary if found, otherwise None.
        """
        logging.debug(f"Attempting to find template with identifier: {identifier}")
        # Check if identifier is a direct name match
        if identifier in self.templates:
            template = self.templates[identifier]
            if template.get("type") == "atomic":
                logging.debug(f"Found template by name: {identifier}")
                return template
            else:
                # Should not happen if register_template filters correctly, but defensive check
                logging.warning(f"Template found by name '{identifier}' but is not atomic. Ignoring.")
                return None

        # Check if identifier is a type:subtype index key
        if identifier in self.template_index:
            template_name = self.template_index[identifier]
            if template_name in self.templates:
                 template = self.templates[template_name]
                 # Ensure it's still atomic (should be guaranteed by registration)
                 if template.get("type") == "atomic":
                     logging.debug(f"Found template by type:subtype '{identifier}' -> name '{template_name}'")
                     return template
                 else:
                     logging.error(f"Index inconsistency: Identifier '{identifier}' points to non-atomic template '{template_name}'.")
                     return None
            else:
                logging.error(f"Index inconsistency: Identifier '{identifier}' points to non-existent template name '{template_name}'.")
                return None

        logging.debug(f"Template not found for identifier: {identifier}")
        return None

    def _get_handler(self, config: Optional[Dict] = None) -> Any: # -> BaseHandler
        """
        Placeholder method to get a BaseHandler instance.
        In a real system, this might involve a factory, cache, or dependency injection.
        For Phase 2c, it might return a cached instance or raise if not available.
        """
        # Simple cache example (key could be more sophisticated)
        cache_key = "default_handler" # Or derive from config if provided
        if cache_key in self._handler_cache:
            logging.debug(f"Returning cached handler for key: {cache_key}")
            return self._handler_cache[cache_key]
        else:
            # In a real scenario, instantiate or retrieve handler here
            # For testing, this might need to be mocked or pre-populated
            logging.error("Handler instance requested but not found in cache or factory logic not implemented.")
            # You might need to import BaseHandler and instantiate it here if it's simple enough
            # from src.handler.base_handler import BaseHandler
            # handler = BaseHandler(task_system=self, memory_system=self.memory_system, config=config)
            # self._handler_cache[cache_key] = handler
            # return handler
            raise NotImplementedError("Handler acquisition logic is not fully implemented in TaskSystem._get_handler")


    def execute_atomic_template(self, request: SubtaskRequest) -> TaskResult:
        """
        Orchestrates the execution of a single atomic task template.

        Args:
            request: The SubtaskRequest detailing the task to execute.

        Returns:
            A TaskResult object containing the execution outcome.
        """
        logging.info(f"Executing atomic template request: {request.name}")

        if request.type != "atomic":
            logging.error(f"Attempted to execute non-atomic task type '{request.type}' via execute_atomic_template.")
            return TaskResult(
                content=f"Error: execute_atomic_template only handles 'atomic' type, got '{request.type}'",
                status="FAILED",
                notes={"error": TaskError(type="TASK_FAILURE", reason="input_validation_failure", message="Invalid task type for atomic execution")}
            )

        template = self.find_template(request.name)
        if not template:
            logging.error(f"Template not found for name: {request.name}")
            return TaskResult(
                content=f"Error: Template '{request.name}' not found.",
                status="FAILED",
                notes={"error": TaskError(type="TASK_FAILURE", reason="template_not_found", message=f"Template '{request.name}' not found.")}
            )

        # --- Determine Effective Context Settings ---
        try:
            base_settings = SUBTASK_CONTEXT_DEFAULTS.model_copy() # Start with defaults for subtasks
            template_settings = template.get("context_management", {})
            request_settings = request.context_management or {}

            # Merge settings: request overrides template overrides defaults
            effective_settings_dict = base_settings.model_dump()
            effective_settings_dict.update({k: v for k, v in template_settings.items() if v is not None})
            effective_settings_dict.update({k: v for k, v in request_settings.items() if v is not None})

            effective_context = ContextManagement(**effective_settings_dict)

            # Validate constraints
            if effective_context.freshContext == "enabled" and effective_context.inheritContext != "none":
                raise ValueError("Context validation failed: fresh_context='enabled' requires inherit_context='none'.")
            logging.debug(f"Effective context settings for '{request.name}': {effective_context.model_dump()}")

        except (ValidationError, ValueError) as e:
            logging.error(f"Context management configuration error for template '{request.name}': {e}")
            return TaskResult(
                content=f"Error: Invalid context management configuration for template '{request.name}'.",
                status="FAILED",
                notes={"error": TaskError(type="TASK_FAILURE", reason="input_validation_failure", message=f"Context configuration error: {e}")}
            )

        # --- Resolve File Paths ---
        final_file_paths: List[str] = []
        resolve_error: Optional[str] = None
        handler_instance = None # Initialize handler instance variable

        try:
            # Get handler instance needed for some resolution types
            # TODO: Refine handler acquisition - assuming _get_handler works for now
            handler_instance = self._get_handler() # Pass config if needed

            if request.file_paths: # Explicit paths in request take precedence
                final_file_paths = request.file_paths
                logging.debug(f"Using explicit file paths from request: {final_file_paths}")
            elif template.get('file_paths') or template.get('file_paths_source'):
                logging.debug("Resolving file paths based on template definition...")
                final_file_paths, resolve_error = self.resolve_file_paths(template, self.memory_system, handler_instance)
                if resolve_error:
                    logging.warning(f"Error resolving file paths for template '{request.name}': {resolve_error}")
                    # Decide if this is fatal - perhaps continue with empty list? For now, log warning.
            else:
                logging.debug(f"No explicit file paths in request or template for '{request.name}'.")

            if not isinstance(final_file_paths, list):
                 logging.warning(f"Resolved file paths are not a list: {final_file_paths}. Using empty list.")
                 final_file_paths = []

        except Exception as e:
            logging.exception(f"Unexpected error during file path resolution or handler acquisition for '{request.name}': {e}")
            return TaskResult(
                content=f"Error: Failed to resolve file paths or get handler for '{request.name}'.",
                status="FAILED",
                notes={"error": TaskError(type="TASK_FAILURE", reason="unexpected_error", message=f"File path/handler error: {e}")}
            )

        # --- Prepare Context ---
        final_context_string = ""
        context_notes = {}
        if not self.memory_system:
             logging.warning("Cannot prepare context: MemorySystem is not available.")
             context_notes["warning"] = "MemorySystem unavailable, context not generated."
        elif effective_context.freshContext == "enabled":
            logging.debug(f"Fetching fresh context for template '{request.name}'...")
            try:
                # Construct input for memory system
                context_input = ContextGenerationInput(
                    templateDescription=template.get('description'),
                    templateType=template.get('type'),
                    templateSubtype=template.get('subtype'),
                    inputs=request.inputs,
                    # Pass inherited context/outputs if needed based on effective_context
                    inheritedContext=None, # TODO: Determine how to pass inherited context if inheritContext != 'none'
                    previousOutputs=None   # TODO: Determine how to pass previous outputs if accumulateData=True
                )
                context_result = self.memory_system.get_relevant_context_for(context_input)

                if context_result.error:
                    logging.warning(f"Failed to get fresh context for '{request.name}': {context_result.error}")
                    context_notes["context_error"] = context_result.error
                    # Decide if this is fatal. Maybe continue without fresh context?
                else:
                    final_context_string = context_result.context_summary # Use summary for now
                    context_notes["context_source"] = "fresh_associative_match"
                    context_notes["context_matches"] = len(context_result.matches)
                    # TODO: Potentially combine with inherited context based on settings
                    # TODO: Potentially add content from final_file_paths if needed by executor/handler
                    logging.debug(f"Successfully fetched fresh context summary for '{request.name}'.")

            except Exception as e:
                logging.exception(f"Error fetching context from MemorySystem for '{request.name}': {e}")
                context_notes["context_error"] = f"Exception during context fetch: {e}"
                # Decide if fatal.

        # --- Prepare Parameters ---
        params = request.inputs or {}
        logging.debug(f"Parameters for executor: {params}")

        # --- Instantiate and Call Executor ---
        executor = AtomicTaskExecutor() # Using placeholder
        task_result: Optional[TaskResult] = None

        try:
            logging.info(f"Calling AtomicTaskExecutor for template: {request.name}")
            # Ensure handler_instance is available if needed by execute_body
            if not handler_instance:
                 handler_instance = self._get_handler() # Try getting handler again if not acquired during path resolution

            task_result = executor.execute_body(
                template=template,
                params=params,
                handler=handler_instance, # Pass the acquired handler
                context=final_context_string, # Pass the prepared context string
                files=final_file_paths # Pass the resolved file paths
            )
            logging.info(f"Executor finished for template: {request.name} with status: {task_result.status}")

        except Exception as e:
            logging.exception(f"AtomicTaskExecutor failed for template '{request.name}': {e}")
            # Create a FAILED TaskResult from the exception
            task_result = TaskResult(
                content=f"Executor failed: {e}",
                status="FAILED",
                notes={
                    "error": TaskError(type="TASK_FAILURE", reason="unexpected_error", message=f"Executor exception: {e}"),
                    "template_used": request.name,
                    "context_source": context_notes.get("context_source", "N/A"),
                    "file_count": len(final_file_paths),
                    **context_notes # Include context notes
                }
            )

        # --- Process Result ---
        if not isinstance(task_result, TaskResult):
             logging.error(f"Executor for '{request.name}' did not return a valid TaskResult object. Got: {type(task_result)}")
             task_result = TaskResult(
                 content=f"Error: Invalid result type from executor for '{request.name}'.",
                 status="FAILED",
                 notes={"error": TaskError(type="TASK_FAILURE", reason="unexpected_error", message="Invalid result type from executor.")}
             )

        # Add standard metadata to notes
        task_result.notes = task_result.notes or {}
        task_result.notes.update({
            "template_used": request.name,
            "context_source": context_notes.get("context_source", "N/A"),
            "file_count": len(final_file_paths),
            **context_notes # Ensure context notes are included
        })
        if resolve_error:
            task_result.notes["file_resolve_error"] = resolve_error

        return task_result


    def generate_context_for_memory_system(
        self, context_input: ContextGenerationInput, global_index: Dict[str, str]
    ) -> AssociativeMatchResult:
        """
        Generates context by executing a dedicated associative matching task.

        This method acts as a mediator, calling back into execute_atomic_template
        with a specific request for the 'atomic:associative_matching' task.

        Args:
            context_input: The input parameters for context generation.
            global_index: The current global file index (passed as input to the matching task).

        Returns:
            An AssociativeMatchResult object.
        """
        matching_template_id = "atomic:associative_matching" # Standard ID for the matching task
        logging.info(f"Generating context via template: {matching_template_id}")

        # Find the dedicated matching template
        template = self.find_template(matching_template_id)
        if not template:
            error_msg = f"Associative matching template '{matching_template_id}' not found."
            logging.error(error_msg)
            return AssociativeMatchResult(context_summary="", matches=[], error=error_msg)

        # Construct the request for the matching task
        # The inputs need to match what the 'atomic:associative_matching' template expects
        # Assuming it expects 'context_input' and 'global_index' as inputs
        matching_request = SubtaskRequest(
            type="atomic",
            name=template['name'], # Use the actual name found
            description=f"Internal context generation for: {context_input.query or context_input.templateDescription}",
            inputs={
                "context_input": context_input.model_dump(), # Pass the structured input
                "global_index": global_index
            },
            # Ensure this internal call doesn't trigger another fresh context lookup
            context_management={"freshContext": "disabled", "inheritContext": "none"}
        )

        # Execute the matching task
        logging.debug(f"Executing internal matching task request: {matching_request.name}")
        task_result = self.execute_atomic_template(matching_request)

        # Process the result
        if task_result.status == "FAILED":
            error_msg = f"Associative matching task failed: {task_result.notes.get('error', {}).get('message', task_result.content)}"
            logging.error(error_msg)
            return AssociativeMatchResult(context_summary="", matches=[], error=error_msg)

        if task_result.status == "COMPLETE":
            try:
                # Expecting the content to be JSON representing AssociativeMatchResult
                parsed_result = AssociativeMatchResult.model_validate_json(task_result.content)
                logging.info(f"Successfully generated and parsed context. Matches found: {len(parsed_result.matches)}")
                return parsed_result
            except (ValidationError, json.JSONDecodeError) as e:
                error_msg = f"Failed to parse AssociativeMatchResult from matching task output: {e}. Content: {task_result.content[:100]}..."
                logging.error(error_msg)
                return AssociativeMatchResult(context_summary="", matches=[], error=error_msg)
        else:
            # Should not happen if FAILED is handled, but defensive check
             error_msg = f"Associative matching task returned unexpected status: {task_result.status}"
             logging.error(error_msg)
             return AssociativeMatchResult(context_summary="", matches=[], error=error_msg)


    def resolve_file_paths(
        self,
        template: Dict[str, Any],
        memory_system: Any, # MemorySystem
        handler: Any, # BaseHandler
    ) -> Tuple[List[str], Optional[str]]:
        """
        Resolves file paths based on the source specified in the template.

        Args:
            template: The task template dictionary.
            memory_system: An instance of MemorySystem.
            handler: An instance of BaseHandler.

        Returns:
            A tuple containing a list of resolved file paths and an optional error message.
        """
        file_paths_source = template.get('file_paths_source', {})
        source_type = file_paths_source.get('type', 'literal') # Default to literal if type is missing
        logging.debug(f"Resolving file paths with source type: {source_type}")

        try:
            if source_type == 'literal':
                literal_paths = template.get('file_paths', []) # Check top-level 'file_paths' first
                if not literal_paths and isinstance(file_paths_source.get('path'), list):
                     literal_paths = file_paths_source.get('path', []) # Check within source element
                logging.debug(f"Resolved literal paths: {literal_paths}")
                return (literal_paths, None)

            elif source_type == 'command':
                command = file_paths_source.get('command')
                if not command:
                    return ([], "Missing command in file_paths_source type 'command'")
                if not handler:
                     return ([], "Handler instance is required for command execution")
                logging.debug(f"Executing command for file paths: {command}")
                # Assuming execute_file_path_command handles errors internally and returns a list
                paths = handler.execute_file_path_command(command)
                logging.debug(f"Command returned paths: {paths}")
                return (paths, None)

            elif source_type == 'description':
                 if not memory_system:
                     return ([], "MemorySystem instance is required for description matching")
                 # Use specific description from source first, fallback to template description
                 desc = file_paths_source.get('description') or template.get('description')
                 if not desc:
                     return ([], "Missing description for file_paths_source type 'description'")
                 logging.debug(f"Getting context by description: {desc}")
                 result = memory_system.get_relevant_context_with_description(desc, desc)
                 if result.error:
                     return ([], f"Error getting context by description: {result.error}")
                 paths = [match.path for match in result.matches]
                 logging.debug(f"Description match returned paths: {paths}")
                 return (paths, None)

            elif source_type == 'context_description':
                 if not memory_system:
                     return ([], "MemorySystem instance is required for context_description matching")
                 query = file_paths_source.get('context_query')
                 if not query:
                     return ([], "Missing context_query for file_paths_source type 'context_description'")
                 logging.debug(f"Getting context by context_query: {query}")
                 input_data = ContextGenerationInput(query=query)
                 result = memory_system.get_relevant_context_for(input_data)
                 if result.error:
                     return ([], f"Error getting context by context_query: {result.error}")
                 paths = [match.path for match in result.matches]
                 logging.debug(f"Context query match returned paths: {paths}")
                 return (paths, None)

            else:
                return ([], f"Unknown file_paths_source type: {source_type}")

        except Exception as e:
            logging.exception(f"Error during file path resolution (type: {source_type}): {e}")
            return ([], f"Unexpected error during file path resolution: {e}")


    def find_matching_tasks(
        self, input_text: str, memory_system: Any # MemorySystem (kept for potential future use)
    ) -> List[Dict[str, Any]]:
        """
        Finds atomic task templates that heuristically match the input text based on description.

        Args:
            input_text: The text to match against template descriptions.
            memory_system: The MemorySystem instance (currently unused, for future context).

        Returns:
            A list of matching task dictionaries, sorted by relevance score.
            Each dictionary contains 'task', 'score', 'taskType', 'subtype'.
        """
        logging.debug(f"Finding matching tasks for input: '{input_text[:50]}...'")
        matches = []
        input_words = set(input_text.lower().split())
        if not input_words:
            return [] # No words to match

        MIN_SCORE = 0.1 # Simple threshold

        for template in self.templates.values():
            if template.get("type") != "atomic":
                continue

            template_desc = template.get('description', '')
            if not template_desc:
                continue

            desc_words = set(template_desc.lower().split())
            if not desc_words:
                continue

            # Simple Jaccard index calculation
            intersection = len(input_words.intersection(desc_words))
            union = len(input_words.union(desc_words))
            score = intersection / union if union > 0 else 0

            if score >= MIN_SCORE:
                matches.append({
                    'task': template,
                    'score': score,
                    'taskType': 'atomic',
                    'subtype': template.get('subtype')
                })
                logging.debug(f"Found potential match: '{template.get('name')}' with score {score:.2f}")

        # Sort matches by score descending
        matches.sort(key=lambda x: x['score'], reverse=True)

        logging.info(f"Found {len(matches)} matching tasks for input.")
        return matches

```
```python
tests/task_system/test_task_system.py
```
