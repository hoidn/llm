"""
Main application entry point and orchestration layer.

Initializes and wires together the core components (MemorySystem, TaskSystem, Handler)
and provides top-level methods for interacting with the system.
"""

import os
import sys
import logging
from typing import Dict, Any, Optional, List

# Add project root to path for src imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.memory.memory_system import MemorySystem
from src.task_system.task_system import TaskSystem
from src.handler.passthrough_handler import PassthroughHandler
from src.memory.indexers.git_repository_indexer import GitRepositoryIndexer
from src.system.models import TaskResult, TaskFailureError, TaskFailureReason
from src.executors.system_executors import SystemExecutorFunctions
from src import dispatcher # Import the dispatcher module

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Aider integration is deferred to Phase 8
AIDER_AVAILABLE = False
AiderBridge = None # Define as None for type hinting if needed elsewhere temporarily

# Helper function to create a standard FAILED TaskResult dictionary
def _create_failed_result_dict(reason: TaskFailureReason, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Creates a dictionary representing a FAILED TaskResult."""
    error_obj = TaskFailureError(type="TASK_FAILURE", reason=reason, message=message, details=details or {})
    task_result = TaskResult(status="FAILED", content=message, notes={"error": error_obj})
    # Use exclude_none=True to avoid sending null fields if not set
    return task_result.model_dump(exclude_none=True)


class Application:
    """
    Main application class orchestrating system components.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initializes the Application, setting up MemorySystem, TaskSystem, Handler,
        and other core components.

        Args:
            config: Optional configuration dictionary. Expected keys might include
                    'memory_config', 'task_system_config', 'handler_config', etc.
        """
        self.config = config or {}
        self.memory_system: Optional[MemorySystem] = None
        self.task_system: Optional[TaskSystem] = None
        self.passthrough_handler: Optional[PassthroughHandler] = None
        self.aider_bridge: Optional['AiderBridge'] = None # Forward reference if needed
        self.indexed_repositories: List[str] = []

        logger.info("Initializing Application components...")
        try:
            # Instantiate components in dependency order
            self.memory_system = MemorySystem(config=self.config.get('memory_config'))
            self.task_system = TaskSystem(memory_system=self.memory_system)
            # Pass handler-specific config if available
            handler_config = self.config.get('handler_config', {})
            # Ensure a default model identifier is provided if not in config
            default_model = handler_config.get('default_model_identifier', "anthropic:claude-3-5-sonnet-latest")
            
            self.passthrough_handler = PassthroughHandler(
                task_system=self.task_system,
                memory_system=self.memory_system,
                config=handler_config,
                # Pass the determined default model identifier
                default_model_identifier=default_model
            )

            # Wire cross-dependencies
            self.memory_system.handler = self.passthrough_handler
            self.memory_system.task_system = self.task_system
            # Inject the handler into TaskSystem
            self.task_system.set_handler(self.passthrough_handler)
            logging.info("Injected Handler into TaskSystem.")

            logger.info("Components instantiated.")

            # --- Core Template Registration ---
            logger.info("Registering core task templates...")
            try:
                assoc_matching_template = {
                    "name": "internal:associative_matching", # Use a distinct name
                    "type": "atomic",
                    "subtype": "associative_matching", # Use the specific subtype
                    "description": "Internal task to find relevant files based on query and index.",
                    "params": {
                        "context_input": {"description": "Input query/context details (as dict)"},
                        "global_index": {"description": "File index (as dict)"}
                    },
                    # This is where the LLM instructions go.
                    "instructions": """Analyze the user query and context provided in 'context_input'.
Review the file metadata provided in 'global_index'.
Identify the top 3-5 most relevant file paths from the index based on the query.
Provide a brief 'context_summary' explaining the relevance.
Output the result as a JSON object conforming to the AssociativeMatchResult structure:
{
"context_summary": "string",
"matches": [ { "path": "string", "relevance": float (0.0-1.0), "excerpt": "optional string" } ],
"error": null
}
Query Details: {{context_input.query}}
Inherited Context Hints: {{context_input.inheritedContext}}
Previous Output Hints: {{context_input.previousOutputs}}
File Index Snippet (Example Format - Actual input is a dict):
{% for path, meta in global_index.items() | slice(5) %}
--- File: {{ path }} ---
{{ meta | truncate(200) }}
{% endfor %}
Based only on the provided query and index metadata, determine the most relevant file paths and output the JSON.""",
                    # Optional: Specify a model optimized for this kind of task
                    # "model": "anthropic:claude-3-haiku-latest",
                    "output_format": {"type": "json"} # Expecting JSON output
                }
                try:
                    success = self.task_system.register_template(assoc_matching_template)
                    if success:
                        logger.info(f"Successfully registered template: {assoc_matching_template['name']}")
                    else:
                        # This path might be hit if registry validation fails silently
                        logger.error(f"Failed to register template (returned False): {assoc_matching_template['name']}")
                except Exception as reg_err:
                     # Catch errors raised by registry validation
                     logger.error(f"Error during template registration for {assoc_matching_template['name']}: {reg_err}")
                # Add other core templates if needed here...
            except Exception as e:
                logger.exception(f"Failed to register core templates: {e}")
                # Decide if this should be fatal for application startup
            
            logger.info("Core templates registration complete.")

            # Register system-level tools
            self._register_system_tools()
            logger.info("System tools registered.")

            # Initialize Aider integration (if available) - DEFERRED to Phase 8
            # self.initialize_aider()
            # logger.info(f"Aider integration initialized (Available: {AIDER_AVAILABLE}).")

            logger.info("Application initialization complete.")

        except Exception as e:
            logger.exception(f"FATAL: Application initialization failed: {e}")
            # Depending on context, might re-raise or handle differently
            raise

    def _register_system_tools(self):
        """Registers system-level tools with the handler."""
        if not self.passthrough_handler:
            logger.error("Cannot register system tools: Handler not initialized.")
            return

        tools_to_register = [
            {
                "spec": {
                    "name": "system:get_context",
                    "description": "Retrieves relevant context based on a query.",
                    "input_schema": { # Define expected input structure
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The query to find context for."},
                            # Add other params from ContextGenerationInput if needed
                        },
                        "required": ["query"]
                    }
                },
                # Use lambda to pass the correct dependency instance
                "executor": lambda params: SystemExecutorFunctions.execute_get_context(params, self.memory_system)
            },
            {
                "spec": {
                    "name": "system:read_files",
                    "description": "Reads the content of specified files.",
                     "input_schema": {
                        "type": "object",
                        "properties": {
                            "file_paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of file paths to read."
                            },
                            "max_size": {"type": "integer", "description": "Optional max size per file."}
                        },
                        "required": ["file_paths"]
                    }
                },
                # Use lambda to pass the handler's file manager
                "executor": lambda params: SystemExecutorFunctions.execute_read_files(params, self.passthrough_handler.file_manager)
            }
        ]

        registered_count = 0
        for tool in tools_to_register:
            try:
                success = self.passthrough_handler.register_tool(tool["spec"], tool["executor"])
                if success:
                    registered_count += 1
                else:
                    logger.warning(f"Failed to register system tool: {tool['spec']['name']}")
            except Exception as e:
                logger.exception(f"Error registering system tool {tool['spec']['name']}: {e}")
        logger.info(f"Registered {registered_count}/{len(tools_to_register)} system tools.")


    def initialize_aider(self) -> None:
        """
        Placeholder for AiderBridge initialization and tool registration.
        Currently deferred as per project plan (Phase 8).
        """
        # Ensure AiderBridge type hint works if needed, even if None
        # from typing import TYPE_CHECKING
        # if TYPE_CHECKING:
        #     try:
        #         from src.aider_bridge.bridge import AiderBridge
        #     except ImportError:
        #         AiderBridge = None # type: ignore

        logger.info("Aider initialization is deferred (Phase 8). Skipping.")
        self.aider_bridge = None # Ensure it remains None
        # Do not attempt to import Aider components or register Aider tools here in Phase 6


    def index_repository(self, repo_path: str, options: Optional[Dict[str, Any]] = None) -> bool:
        """
        Indexes a Git repository using the GitRepositoryIndexer.

        Args:
            repo_path: The path to the Git repository.
            options: Optional dictionary of configuration options for the indexer.

        Returns:
            True if indexing was successful or initiated, False otherwise.
        """
        if not self.memory_system:
            logger.error("Cannot index repository: MemorySystem not initialized.")
            return False

        logger.info(f"Attempting to index repository: {repo_path}")
        try:
            # Validate path
            norm_path = os.path.abspath(repo_path)
            if not os.path.isdir(norm_path):
                logger.error(f"Invalid repository path (not a directory): {norm_path}")
                return False
            # Basic check for .git directory
            git_dir = os.path.join(norm_path, ".git")
            if not os.path.isdir(git_dir):
                 logger.error(f"Invalid repository path (no .git directory found): {norm_path}")
                 return False

            # Instantiate indexer
            indexer = GitRepositoryIndexer(repo_path=norm_path)
            
            # Configure the indexer based on options passed to this method
            if options:
                logger.debug(f"Applying indexer options: {options}")
                if 'max_file_size' in options and isinstance(options['max_file_size'], int):
                    # Use setter method if available, otherwise direct attribute access
                    # Assuming direct attribute access for simplicity/matching indexer code
                    indexer.max_file_size = options['max_file_size']
                    logger.debug(f"  Set indexer max_file_size to: {indexer.max_file_size}")
                if 'include_patterns' in options and isinstance(options['include_patterns'], list):
                    indexer.include_patterns = options['include_patterns']
                    logger.debug(f"  Set indexer include_patterns to: {indexer.include_patterns}")
                if 'exclude_patterns' in options and isinstance(options['exclude_patterns'], list):
                    indexer.exclude_patterns = options['exclude_patterns']
                    logger.debug(f"  Set indexer exclude_patterns to: {indexer.exclude_patterns}")
            else:
                logger.debug("No specific indexer options provided, using indexer defaults.")
            
            logger.info(f"Starting indexing for {norm_path}...")
            index_results = indexer.index_repository(memory_system=self.memory_system)
            logger.info(f"Indexing complete for {norm_path}. Indexed {len(index_results)} files.")

            if norm_path not in self.indexed_repositories:
                self.indexed_repositories.append(norm_path)
            return True

        except ValueError as e: # Catch specific errors if indexer raises them
            logger.error(f"Indexing validation error for {repo_path}: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error during repository indexing for {repo_path}: {e}")
            return False

    def handle_query(self, query: str) -> Dict[str, Any]:
        """
        Handles a natural language query using the PassthroughHandler.

        Args:
            query: The user's query string.

        Returns:
            A dictionary representing the TaskResult.
        """
        if not self.passthrough_handler:
            logger.error("Cannot handle query: PassthroughHandler not initialized.")
            return _create_failed_result_dict("handler_not_ready", "Handler not initialized.")

        logger.debug(f"Handling query: '{query[:100]}...'") # Log truncated query
        try:
            task_result_obj = self.passthrough_handler.handle_query(query)
            result_dict = task_result_obj.model_dump(exclude_none=True)
            logger.debug(f"Query result status: {result_dict.get('status')}")
            return result_dict
        except Exception as e:
            logger.exception(f"Error handling query: {e}")
            return _create_failed_result_dict("unexpected_error", f"Unexpected error during query handling: {e}")

    def reset_conversation(self) -> None:
        """Resets the conversation history in the PassthroughHandler."""
        if not self.passthrough_handler:
            logger.error("Cannot reset conversation: PassthroughHandler not initialized.")
            return

        logger.info("Resetting conversation history.")
        try:
            self.passthrough_handler.reset_conversation()
        except Exception as e:
            logger.exception(f"Error resetting conversation: {e}")


    def handle_task_command(
        self,
        identifier: str,
        params: Optional[Dict[str, Any]] = None,
        flags: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handles a programmatic task command via the Dispatcher.

        Args:
            identifier: The task identifier (S-expression, atomic task ID, tool ID).
            params: Dictionary of parameters for the task/tool.
            flags: Dictionary of flags for the task/tool.

        Returns:
            A dictionary representing the TaskResult.
        """
        if not self.passthrough_handler or not self.task_system or not self.memory_system:
             logger.error("Cannot handle task command: Core components not initialized.")
             return _create_failed_result_dict("system_not_ready", "Core components not initialized.")

        logger.debug(f"Handling task command: Identifier='{identifier}', Params={params}, Flags={flags}")
        try:
            # Delegate to the dispatcher function
            result_dict = dispatcher.execute_programmatic_task(
                identifier=identifier,
                params=params or {},
                flags=flags or {},
                handler_instance=self.passthrough_handler,
                task_system_instance=self.task_system,
                memory_system=self.memory_system
                # optional_history_str=self.passthrough_handler.get_history_string() # If needed
            )
            logger.debug(f"Task command result status: {result_dict.get('status')}")
            return result_dict
        except Exception as e:
            logger.exception(f"Error handling task command '{identifier}': {e}")
            return _create_failed_result_dict("unexpected_error", f"Unexpected error during task command execution: {e}")


# Example Usage (Optional)
if __name__ == "__main__":
    # This block is for basic testing or demonstration if run directly
    # In a real application, Application instance would likely be managed elsewhere
    logger.info("Running basic Application example...")
    try:
        app = Application()

        # Example: Index a dummy repo (replace with actual path if needed)
        # dummy_repo_path = "./dummy_repo_for_testing"
        # if not os.path.exists(dummy_repo_path): os.makedirs(os.path.join(dummy_repo_path, ".git"))
        # app.index_repository(dummy_repo_path)

        # Example: Handle a query
        query_result = app.handle_query("What is the capital of France?")
        print("\nQuery Result:")
        import json
        print(json.dumps(query_result, indent=2))

        # Example: Handle a task command (assuming a core:echo template exists or Sexp works)
        # task_result = app.handle_task_command("core:echo", {"message": "Hello Task!"})
        task_result = app.handle_task_command('(list "hello" "world")')
        print("\nTask Command Result:")
        print(json.dumps(task_result, indent=2))

        # Example: Use a system tool via task command
        tool_result = app.handle_task_command("system:read_files", {"file_paths": ["src/main.py"]})
        print("\nSystem Tool Result:")
        print(json.dumps(tool_result, indent=2))


    except Exception as main_e:
        logger.exception(f"Error in main execution block: {main_e}")
