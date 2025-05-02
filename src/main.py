"""
Main application entry point and orchestration layer.

Initializes and wires together the core components (MemorySystem, TaskSystem, Handler)
and provides top-level methods for interacting with the system.
"""

import os
import sys
import logging
import functools # Add functools import
import asyncio # Add asyncio import
from typing import Dict, Any, Optional, List

# Add project root to path for src imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging early
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Define logger before first use

from src.memory.memory_system import MemorySystem
from src.task_system.task_system import TaskSystem
from src.handler.passthrough_handler import PassthroughHandler
from src.handler.file_access import FileAccessManager # Add import
from src.memory.indexers.git_repository_indexer import GitRepositoryIndexer
from src.system.models import TaskResult, TaskFailureError, TaskFailureReason
from src.executors.system_executors import SystemExecutorFunctions
from src import dispatcher # Import the dispatcher module
# Import the new tools module
from src.tools import anthropic_tools
# Import Aider components conditionally
try:
    from src.aider_bridge.bridge import AiderBridge
    from src.executors.aider_executors import AiderExecutorFunctions as AiderExecutors
    # Check environment variable for enabling Aider
    AIDER_ENABLED_ENV = os.environ.get('AIDER_ENABLED', 'false').lower() == 'true'
    AIDER_AVAILABLE = AIDER_ENABLED_ENV # Set availability based on env var
    if not AIDER_AVAILABLE:
        logger.info("Aider integration is disabled (AIDER_ENABLED env var not 'true' or not set).")
except ImportError:
    logger.warning("AiderBridge or AiderExecutorFunctions not found. Aider integration disabled.")
    AiderBridge = None # type: ignore
    AiderExecutors = None # type: ignore
    AIDER_AVAILABLE = False


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
        self.aider_bridge: Optional['AiderBridge'] = None # Initialize as None
        self.indexed_repositories: List[str] = []
        self.file_access_manager: Optional[FileAccessManager] = None # Add attribute

        logger.info("Initializing Application components...")
        try:
            # --- START MODIFICATION ---
            # 1. Instantiate components with fewer dependencies first
            # Define PROJECT_ROOT if not already defined globally in the file
            # This assumes PROJECT_ROOT is needed for the default path
            PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            fm_base_path = self.config.get('file_manager_base_path', PROJECT_ROOT) # Use PROJECT_ROOT as default
            self.file_access_manager = FileAccessManager(base_path=fm_base_path)
            logger.info(f"FileAccessManager initialized with base_path: {self.file_access_manager.base_path}") # Log actual base path

            # TaskSystem only needs MemorySystem later (or not at all in init)
            # We can instantiate it now, but MemorySystem needs TaskSystem.
            # Let's create placeholders and fully init later, OR change TaskSystem init.
            # Option A: Change TaskSystem init (Simpler if TaskSystem doesn't NEED memory_system during its own init)
            # Assume TaskSystem init doesn't strictly need memory_system immediately
            self.task_system = TaskSystem() # Instantiate with no args initially
            logger.info("TaskSystem initialized (placeholder).")

            # 2. Instantiate Handler (needs TaskSystem)
            handler_config = self.config.get('handler_config', {})
            handler_config['file_manager_base_path'] = fm_base_path
            default_model = handler_config.get('default_model_identifier', "anthropic:claude-3-5-sonnet-latest")
            self.passthrough_handler = PassthroughHandler(
                task_system=self.task_system, # Pass TaskSystem instance
                memory_system=None, # Pass None initially, set below
                config=handler_config,
                default_model_identifier=default_model
            )
            logger.info("PassthroughHandler initialized.")

            # Get provider identifier for tool determination
            provider_id = self.passthrough_handler.get_provider_identifier()
            logger.info(f"Provider identifier: {provider_id}")

            # Determine active tools based on provider (DEFERRED - done after registration)
            # active_tools = self._determine_active_tools(provider_id)

            # Set active tools on the handler (DEFERRED - done after registration)
            # if active_tools:
            #     self.passthrough_handler.set_active_tool_definitions(active_tools)
            #     logger.info(f"Set {len(active_tools)} active tool definitions on handler")

            # 3. Instantiate MemorySystem (needs Handler, TaskSystem, FileManager)
            self.memory_system = MemorySystem(
                handler=self.passthrough_handler, # Pass Handler instance
                task_system=self.task_system, # Pass TaskSystem instance
                file_access_manager=self.file_access_manager, # Pass FileManager instance
                config=self.config.get('memory_config')
            )
            logger.info("MemorySystem initialized.")

            # 4. Complete wiring dependencies
            # Ensure TaskSystem has memory_system attribute or setter
            if hasattr(self.task_system, 'memory_system'):
                self.task_system.memory_system = self.memory_system # Set memory_system on TaskSystem
            else:
                logger.warning("TaskSystem instance does not have a 'memory_system' attribute to set.")
            # Ensure TaskSystem has set_handler method
            if hasattr(self.task_system, 'set_handler'):
                 self.task_system.set_handler(self.passthrough_handler) # Set handler on TaskSystem
            else:
                 logger.error("TaskSystem does not have set_handler method! Cannot inject handler.")
                 raise AttributeError("TaskSystem missing set_handler method")
            # Ensure PassthroughHandler has memory_system attribute or setter
            if hasattr(self.passthrough_handler, 'memory_system'):
                self.passthrough_handler.memory_system = self.memory_system # Set memory_system on Handler
            else:
                logger.warning("PassthroughHandler instance does not have a 'memory_system' attribute to set.")
            logger.info("Cross-dependencies wired.")
            # --- END MODIFICATION ---

            logger.info("Components instantiated and wired.")

            # --- Core Template Registration ---
            logger.info("Registering core task templates...")
            try:
                # Define CONTENT-based template
                assoc_matching_content_template = {
                    "name": "internal:associative_matching_content", # New name
                    "type": "atomic",
                    "subtype": "associative_matching", # Keep subtype consistent
                    "description": "Internal task to find relevant files based on query and FULL FILE CONTENT.",
                    "params": {
                        "context_input": { "description": "Input query/context details (as dict)" },
                        "file_contents": { "description": "A single string containing file contents wrapped in `<file path=...>...</file>` tags" }
                    },
                    "instructions": """Analyze the user query details in 'context_input'.
Review the **full file contents** provided in the 'file_contents' parameter (a dictionary mapping paths to content).
Based on the query and the **provided file contents**, select up to 10 relevant file paths *from the keys of the file_contents dictionary*. Assign a relevance score (0.0-1.0) to each selected path.
Provide a brief 'context_summary' explaining the relevance based on the selected files' content.
Output the result as a JSON object conforming to the AssociativeMatchResult structure:
{
  "context_summary": "string",
  "matches": [ { "path": "string", "relevance": float (0.0-1.0) } ],
  "error": null
}

Query Details: {{context_input.query}}

File Contents Snippet (Example Format - Actual input is the full dict):
{{file_contents}}

Select the best matching paths *from the provided file contents*.
**IMPORTANT:** Your response MUST contain ONLY the valid JSON object conforming to the AssociativeMatchResult structure specified above. Do NOT include any introductory text, explanations, apologies, or concluding remarks. Your entire output must be the JSON object itself, starting with `{` and ending with `}`.""",
                    "output_format": {"type": "json"}
                }
                self.task_system.register_template(assoc_matching_content_template)
                logger.info(f"Registered template: {assoc_matching_content_template['name']}")

                # Define METADATA-based template
                assoc_matching_metadata_template = {
                    "name": "internal:associative_matching_metadata", # New name
                    "type": "atomic",
                    "subtype": "associative_matching",
                    "description": "Internal task to find relevant files based on query and pre-generated METADATA.",
                     "params": {
                        "context_input": { "description": "Input query/context details (as dict)" },
                        "metadata_snippet": { "description": "Dictionary mapping candidate file paths to their metadata strings" }
                    },
                   "instructions": """Analyze the user query details in 'context_input'.
Review the **file metadata** provided in the 'metadata_snippet' parameter (a dictionary mapping paths to metadata strings).
Based on the query and the **provided metadata**, select the top 3-5 most relevant file paths *from the keys of the metadata_snippet dictionary*. Assign a relevance score (0.0-1.0) to each selected path.
Provide a brief 'context_summary' explaining the relevance based on the selected files' metadata.
Output the result as a JSON object conforming to the AssociativeMatchResult structure:
{
  "context_summary": "string",
  "matches": [ { "path": "string", "relevance": float (0.0-1.0) } ],
  "error": null
}

Query Details: {{context_input.query}}

Metadata Snippet (Example Format - Actual input is the full dict):
{{ metadata_snippet | dict_slice(10) | format_dict_snippet(250) }}

Select the best matching paths *from the provided metadata* and output the JSON.""", # Simplified template example
                    "output_format": {"type": "json"}
                }
                self.task_system.register_template(assoc_matching_metadata_template)
                logger.info(f"Registered template: {assoc_matching_metadata_template['name']}")

            except AttributeError as ae:
                 logger.exception(f"Failed to register core templates - likely missing register_template method: {ae}")
                 raise # Re-raise as this is critical
            except Exception as e:
                logger.exception(f"Failed to register core templates: {e}")
                raise # Re-raise as this is critical

            # Register system-level tools
            self._register_system_tools()
            logger.info("System tools registered.")

            # --- Conditional Provider Tool Registration ---
            provider_id = self.passthrough_handler.get_provider_identifier()
            logger.info(f"Checking provider for specific tools: {provider_id}")

            if provider_id and provider_id.startswith("anthropic:"):
                logger.info("Anthropic provider detected. Registering Anthropic Editor tools...")
                registered_anthropic_count = 0
                try:
                    # --- START Anthropic Wrapper Refactor ---
                    # Define the wrapper function factory OUTSIDE the loop
                    def create_anthropic_wrapper(tool_func, fm_instance):
                        # This inner function is what gets registered
                        def _anthropic_tool_wrapper(params: Dict[str, Any]) -> str: # Assuming Anthropic tools return str
                            if not fm_instance: return "Error: File manager not available"
                            try:
                                # Call the original tool func, passing fm and unpacking params
                                return tool_func(fm_instance, **params)
                            except Exception as e:
                                logger.exception(f"Error executing Anthropic tool {tool_func.__name__}: {e}")
                                return f"Error executing tool: {e}" # Return error string
                        # Copy metadata for better introspection if needed (optional)
                        functools.update_wrapper(_anthropic_tool_wrapper, tool_func)
                        return _anthropic_tool_wrapper
                    # --- END Anthropic Wrapper Refactor ---

                    anthropic_tool_pairs = [
                        (anthropic_tools.ANTHROPIC_VIEW_SPEC, anthropic_tools.view),
                        (anthropic_tools.ANTHROPIC_CREATE_SPEC, anthropic_tools.create),
                        (anthropic_tools.ANTHROPIC_STR_REPLACE_SPEC, anthropic_tools.str_replace),
                        (anthropic_tools.ANTHROPIC_INSERT_SPEC, anthropic_tools.insert),
                    ]

                    for tool_spec, tool_func in anthropic_tool_pairs:
                        # --- START Anthropic Wrapper Refactor ---
                        # Create the specific wrapper for this tool_func and the current file_manager
                        executor_wrapper = create_anthropic_wrapper(tool_func, self.passthrough_handler.file_manager)
                        # --- END Anthropic Wrapper Refactor ---

                        success = self.passthrough_handler.register_tool(tool_spec, executor_wrapper)
                        if success:
                            registered_anthropic_count += 1
                            logger.debug(f"Registered Anthropic tool: {tool_spec['name']}")
                        else:
                            logger.warning(f"Failed to register Anthropic tool: {tool_spec['name']}")
                    logger.info(f"Registered {registered_anthropic_count}/{len(anthropic_tool_pairs)} Anthropic tools.")

                except ImportError:
                    logger.error("Failed to import anthropic_tools module. Cannot register Anthropic tools.")
                except AttributeError as e:
                     logger.error(f"Error accessing expected attributes/methods during Anthropic tool registration: {e}")
                except Exception as e:
                    logger.exception(f"Unexpected error during Anthropic tool registration: {e}")
            else:
                logger.info("Provider is not Anthropic. Skipping Anthropic tool registration.")
            # --- End Conditional Provider Tool Registration ---

            # Initialize Aider integration (if available) - Phase 8
            self.initialize_aider() # Call the helper method
            logger.info(f"Aider integration initialization check complete (Available: {AIDER_AVAILABLE}).")


            # Determine active tools based on provider AFTER registration
            active_tools_specs = self._determine_active_tools(provider_id)

            # Set active tools on the handler AFTER registration
            if active_tools_specs:
                self.passthrough_handler.set_active_tool_definitions(active_tools_specs)
                logger.info(f"Set {len(active_tools_specs)} active tool definitions on handler")


            # Retrieve tools for agent initialization AFTER registration
            agent_tools_executors = self.passthrough_handler.get_tools_for_agent()
            logger.info(f"Retrieved {len(agent_tools_executors)} tool executors for agent initialization.")

            # Trigger agent initialization in the manager AFTER registration
            if self.passthrough_handler.llm_manager:
                self.passthrough_handler.llm_manager.initialize_agent(tools=agent_tools_executors)
                logger.info("Triggered LLMInteractionManager agent initialization.")
            else:
                logger.error("LLMInteractionManager not available for agent initialization.")
                raise RuntimeError("LLMInteractionManager not available for agent initialization.")


            logger.info("Application initialization complete.")

        except Exception as e:
            logger.exception(f"FATAL: Application initialization failed: {e}")
            # Depending on context, might re-raise or handle differently
            raise

    def _determine_active_tools(self, provider_identifier: Optional[str]) -> List[Dict[str, Any]]:
        """
        Determines which tools should be active based on the provider identifier.
        This should return the list of TOOL SPECIFICATIONS.

        Args:
            provider_identifier: String identifying the LLM provider (e.g., "openai:gpt-4o", "anthropic:claude-3-5-sonnet-latest")

        Returns:
            List of tool specification dictionaries to be set as active.
        """
        logger.info(f"Determining active tool specifications for provider: {provider_identifier}")

        active_tool_specs = []

        # Add system tools from registered_tools if they exist
        if self.passthrough_handler and hasattr(self.passthrough_handler, 'registered_tools'):
            for tool_name, tool_data in self.passthrough_handler.registered_tools.items():
                # tool_data is expected to be {'spec': {...}, 'executor': callable}
                if tool_name.startswith('system:'):
                    if 'spec' in tool_data:
                        active_tool_specs.append(tool_data['spec'])
                        logger.debug(f"Including system tool spec: {tool_name}")
                    else:
                        logger.warning(f"System tool '{tool_name}' missing 'spec' in registered_tools.")

        # Add provider-specific tools based on the provider_identifier
        if provider_identifier:
            if provider_identifier.startswith('anthropic:'):
                logger.debug("Including Anthropic tool specs.")
                # Add Anthropic tool specs from registered_tools
                if self.passthrough_handler and hasattr(self.passthrough_handler, 'registered_tools'):
                     for tool_name, tool_data in self.passthrough_handler.registered_tools.items():
                         if tool_name.startswith('anthropic:'):
                             if 'spec' in tool_data:
                                 active_tool_specs.append(tool_data['spec'])
                                 logger.debug(f"Including Anthropic tool spec: {tool_name}")
                             else:
                                 logger.warning(f"Anthropic tool '{tool_name}' missing 'spec' in registered_tools.")
            # Add other provider-specific logic here if needed
            # elif provider_identifier.startswith('openai:'):
            #     pass

        # Add Aider tools if available
        if AIDER_AVAILABLE:
            logger.debug("Including Aider tool specs.")
            if self.passthrough_handler and hasattr(self.passthrough_handler, 'registered_tools'):
                 for tool_name, tool_data in self.passthrough_handler.registered_tools.items():
                     if tool_name.startswith('aider:'):
                         if 'spec' in tool_data:
                             active_tool_specs.append(tool_data['spec'])
                             logger.debug(f"Including Aider tool spec: {tool_name}")
                         else:
                             logger.warning(f"Aider tool '{tool_name}' missing 'spec' in registered_tools.")


        logger.info(f"Determined {len(active_tool_specs)} active tool specifications: {[t.get('name', 'unnamed') for t in active_tool_specs]}")
        return active_tool_specs

    def _register_system_tools(self):
        """Registers system-level tools with the handler."""
        if not self.passthrough_handler:
            logger.error("Cannot register system tools: Handler not initialized.")
            return
        if not self.memory_system:
             logger.error("Cannot register system:get_context tool: MemorySystem not initialized.")
             # Decide whether to continue or raise
             # return # Or raise an error
        if not self.passthrough_handler.file_manager: # Check file manager dependency
            logger.error("Cannot register system:read_files tool: FileAccessManager not initialized.")
            # return # Or raise an error

        # --- START System Wrapper Refactor ---
        # --- Wrapper for get_context ---
        def _get_context_wrapper(params: Dict[str, Any], mem_sys=self.memory_system) -> Dict[str, Any]:
            """Wrapper for SystemExecutorFunctions.execute_get_context."""
            if not mem_sys: return {"status": "FAILED", "content": "Memory system not available"}
            # Assuming execute_get_context is synchronous
            return SystemExecutorFunctions.execute_get_context(params, mem_sys)

        # --- Wrapper for read_files ---
        def _read_files_wrapper(params: Dict[str, Any], fm=self.passthrough_handler.file_manager) -> Dict[str, Any]:
            """Wrapper for SystemExecutorFunctions.execute_read_files."""
            if not fm: return {"status": "FAILED", "content": "File manager not available"}
            # Assuming execute_read_files is synchronous
            return SystemExecutorFunctions.execute_read_files(params, fm)
        # --- END System Wrapper Refactor ---

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
                # --- START System Wrapper Refactor ---
                "executor": _get_context_wrapper # Pass the defined function
                # --- END System Wrapper Refactor ---
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
                # --- START System Wrapper Refactor ---
                "executor": _read_files_wrapper # Pass the defined function
                # --- END System Wrapper Refactor ---
            }
        ]

        registered_count = 0
        for tool in tools_to_register:
            try:
                # Check if dependencies for the executor are met before registering
                if tool['spec']['name'] == 'system:get_context' and not self.memory_system:
                    logger.error("Skipping registration of system:get_context: MemorySystem not initialized.")
                    continue
                if tool['spec']['name'] == 'system:read_files' and not self.passthrough_handler.file_manager:
                    logger.error("Skipping registration of system:read_files: FileAccessManager not initialized.")
                    continue

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
        Initializes the AiderBridge and registers Aider tools if available.
        """
        if not AIDER_AVAILABLE:
            logger.info("Aider integration is unavailable (missing dependencies or disabled). Skipping initialization.")
            self.aider_bridge = None # Ensure it's None
            return

        # Proceed only if AIDER_AVAILABLE is True
        if not self.passthrough_handler:
            logger.error("Cannot initialize Aider: PassthroughHandler not available.")
            return
        if not self.memory_system:
             logger.error("Cannot initialize Aider: MemorySystem not available.")
             return
        if not self.file_access_manager:
             logger.error("Cannot initialize Aider: FileAccessManager not available.")
             return

        logger.info("Aider is available. Initializing AiderBridge and registering tools...")
        try:
            # Instantiate AiderBridge ONLY if available
            aider_config = self.config.get('aider_config', {})
            # Ensure dependencies are passed correctly
            self.aider_bridge = AiderBridge(
                memory_system=self.memory_system,
                file_access_manager=self.file_access_manager,
                config=aider_config
            )
            logger.info("AiderBridge (MCP Client) instantiated.")

            # --- START Aider Wrapper Refactor ---
            # --- Wrapper for Aider automatic ---
            def _aider_auto_wrapper(params: Dict[str, Any], bridge=self.aider_bridge) -> Dict[str, Any]:
                 """Wrapper for AiderExecutors.execute_aider_automatic."""
                 # Use asyncio.run() if the executor is async and called from sync context
                 # If initialize_aider is async, just await it. Assuming sync for now.
                 # Check if bridge is valid before calling
                 if not bridge: return _create_failed_result_dict("dependency_error", "Aider bridge not available.")
                 try:
                     # Assuming execute_aider_automatic is async
                     # Check if an event loop is already running
                     try:
                         loop = asyncio.get_running_loop()
                         # If a loop is running, schedule the coroutine and wait for it
                         # This is a simplified approach; complex scenarios might need better handling
                         logger.warning("Running async Aider tool from existing event loop. Consider refactoring caller to be async.")
                         future = asyncio.run_coroutine_threadsafe(AiderExecutors.execute_aider_automatic(params, bridge), loop)
                         return future.result() # Blocking wait
                     except RuntimeError: # No running event loop
                         return asyncio.run(AiderExecutors.execute_aider_automatic(params, bridge))
                 except Exception as e:
                      logger.exception(f"Error running aider automatic wrapper: {e}")
                      return _create_failed_result_dict("unexpected_error", f"Error running Aider tool: {e}")

            # --- Wrapper for Aider interactive ---
            def _aider_inter_wrapper(params: Dict[str, Any], bridge=self.aider_bridge) -> Dict[str, Any]:
                 """Wrapper for AiderExecutors.execute_aider_interactive."""
                 if not bridge: return _create_failed_result_dict("dependency_error", "Aider bridge not available.")
                 try:
                     # Assuming execute_aider_interactive is async
                     try:
                         loop = asyncio.get_running_loop()
                         logger.warning("Running async Aider tool from existing event loop. Consider refactoring caller to be async.")
                         future = asyncio.run_coroutine_threadsafe(AiderExecutors.execute_aider_interactive(params, bridge), loop)
                         return future.result()
                     except RuntimeError: # No running event loop
                         return asyncio.run(AiderExecutors.execute_aider_interactive(params, bridge))
                 except Exception as e:
                      logger.exception(f"Error running aider interactive wrapper: {e}")
                      return _create_failed_result_dict("unexpected_error", f"Error running Aider tool: {e}")
            # --- END Aider Wrapper Refactor ---

            aider_tools_to_register = [
                {
                    "spec": {
                        "name": "aider:automatic",
                        "description": "Executes an Aider coding task automatically based on a prompt and optional file context.",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string", "description": "The instruction for code changes."},
                                "file_context": {"type": "string", "description": "Optional JSON string array of explicit file paths."},
                                "model": {"type": "string", "description": "Optional specific model override for Aider."}
                            },
                            "required": ["prompt"]
                        }
                    },
                    # --- START Aider Wrapper Refactor ---
                    "executor": _aider_auto_wrapper # Pass defined function
                    # --- END Aider Wrapper Refactor ---
                },
                {
                    "spec": {
                        "name": "aider:interactive",
                        "description": "Starts or continues an interactive Aider coding session.",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "The initial query or follow-up instruction."},
                                "prompt": {"type": "string", "description": "Alternative to 'query'."},
                                "file_context": {"type": "string", "description": "Optional JSON string array of explicit file paths."},
                                "model": {"type": "string", "description": "Optional specific model override for Aider."}
                            },
                            # Require at least one of query or prompt
                        }
                    },
                     # --- START Aider Wrapper Refactor ---
                    "executor": _aider_inter_wrapper # Pass defined function
                     # --- END Aider Wrapper Refactor ---
                }
            ]

            # Register Aider tools with the handler
            registered_count = 0
            # Ensure AiderExecutors was imported successfully before using its methods
            if AiderExecutors:
                for tool in aider_tools_to_register:
                    # --- START Aider Wrapper Refactor ---
                    # Register the explicit wrapper directly
                    success = self.passthrough_handler.register_tool(tool["spec"], tool["executor"])
                    # --- END Aider Wrapper Refactor ---
                    if success:
                        registered_count += 1
                        logger.debug(f"Registered Aider tool: {tool['spec']['name']}")
                    else:
                        logger.warning(f"Failed to register Aider tool: {tool['spec']['name']}")
                logger.info(f"Registered {registered_count}/{len(aider_tools_to_register)} Aider tools.")
            else:
                 logger.error("AiderExecutorFunctions not available. Cannot register Aider tools.")

        except Exception as e:
            logger.exception(f"Error during Aider initialization: {e}")
            self.aider_bridge = None # Ensure bridge is None on error


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
        # Example with Anthropic provider to test tool registration
        app = Application(config={"handler_config": {"default_model_identifier": "anthropic:claude-3-5-sonnet-latest"}})

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

        # Example: Use an Anthropic tool via task command (if provider is Anthropic)
        if app.passthrough_handler.get_provider_identifier().startswith("anthropic:"):
            # Create a dummy file first
            dummy_file = "dummy_anthropic_test.txt"
            create_params = {"file_path": dummy_file, "content": "Hello Anthropic!"}
            create_result = app.handle_task_command("anthropic:create", create_params)
            print("\nAnthropic Create Result:")
            print(json.dumps(create_result, indent=2))

            if create_result.get("status") == "COMPLETE":
                # View the created file
                view_params = {"file_path": dummy_file}
                view_result = app.handle_task_command("anthropic:view", view_params)
                print("\nAnthropic View Result:")
                print(json.dumps(view_result, indent=2))

                # Clean up dummy file
                if os.path.exists(dummy_file):
                    os.remove(dummy_file)


    except Exception as main_e:
        logger.exception(f"Error in main execution block: {main_e}")
