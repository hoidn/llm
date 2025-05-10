"""
Main application entry point and orchestration layer.

Initializes and wires together the core components (MemorySystem, TaskSystem, Handler)
and provides top-level methods for interacting with the system.
"""

import os
import sys
import json
import logging
# import functools # No longer needed for anthropic/aider wrappers
import asyncio # Add asyncio import
from typing import Dict, Any, Optional, List

# Add project root to path for src imports
# Define PROJECT_ROOT at the module level
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)


# Configure logging early
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Define logger before first use

from src.memory.memory_system import MemorySystem
from src.task_system.task_system import TaskSystem
from src.handler.passthrough_handler import PassthroughHandler
from src.handler.file_access import FileAccessManager # Add import
from src.handler.file_context_manager import FileContextManager # ADDED IMPORT
from src.memory.indexers.git_repository_indexer import GitRepositoryIndexer
from src.system.models import TaskResult, TaskFailureError, TaskFailureReason
from src.executors.system_executors import SystemExecutorFunctions
from src import dispatcher # Import the dispatcher module
# Import the new tools module
from src.tools import anthropic_tools

# Import pydantic_ai.Tool for constructing tool objects
try:
    from pydantic_ai import Tool as PydanticTool
except ImportError:
    logger.error("Failed to import pydantic_ai.Tool. Tool registration will likely fail.")
    PydanticTool = None # type: ignore
# Import Aider components conditionally
logger.debug("Attempting to import Aider components...")
try:
    from src.aider_bridge.bridge import AiderBridge
    from src.executors.aider_executors import AiderExecutorFunctions as AiderExecutors
    logger.debug("Aider components imported successfully.")
    # AIDER_AVAILABLE check moved to initialize_aider method
except ImportError as e:
    logger.warning(f"AiderBridge or AiderExecutorFunctions not found. Aider integration disabled. Import error: {e}")
    AiderBridge = None # type: ignore
    AiderExecutors = None # type: ignore
    # AIDER_AVAILABLE check moved to initialize_aider method
except Exception as e:
    logger.exception(f"Unexpected error during Aider component import. Aider integration disabled. Error: {e}")
    AiderBridge = None # type: ignore
    AiderExecutors = None # type: ignore
    # AIDER_AVAILABLE check moved to initialize_aider method
# logger.info(f"Final AIDER_AVAILABLE status after import block: {AIDER_AVAILABLE}") # Removed


# --- Aider Loop Task Templates ---
GENERATE_PLAN_TEMPLATE = {
    "name": "user:generate-plan",
    "type": "atomic",
    "subtype": "standard",
    "description": "Generates a development plan for a coding task based on user prompts and context.",
    "params": {
        "user_prompts": {"type": "string", "description": "The user's request(s) for the coding task, potentially combined."},
        "initial_context": {"type": "string", "description": "Relevant context, such as file contents or project overview."}
    },
    "instructions": """
Analyze the user's request(s) provided in 'user_prompts' and the 'initial_context'.
Generate a detailed, step-by-step plan suitable for an AI coding assistant like Aider.
Identify the relevant files that need modification.
Determine the exact shell command required to run tests verifying the task's completion.

Output the result ONLY as a valid JSON object conforming to the DevelopmentPlan schema.

User Prompts:
{{user_prompts}}

Initial Context:
{{initial_context}}

**IMPORTANT:** Your response MUST contain ONLY the valid JSON object conforming to the DevelopmentPlan schema. Do NOT include any introductory text, explanations, apologies, or concluding remarks. Your entire output must be the JSON object itself, starting with `{` and ending with `}`.
""",
    "output_format": {"type": "json", "schema": "src.system.models.DevelopmentPlan"}
}

ANALYZE_AIDER_RESULT_TEMPLATE = {
    "name": "user:analyze-aider-result",
    "type": "atomic",
    "subtype": "standard",
    "description": "Analyzes the result of an Aider execution iteration and provides feedback.",
    "params": {
        "aider_result_content": {"type": "string", "description": "The content/output/error message from the Aider execution."},
        "aider_result_status": {"type": "string", "description": "The status of the Aider execution (e.g., 'COMPLETE', 'FAILED')."},
        "original_prompt": {"type": "string", "description": "The prompt given to Aider for this iteration."},
        "iteration": {"type": "integer", "description": "The current iteration number."},
        "max_retries": {"type": "integer", "description": "The maximum number of retries allowed."}
    },
    "instructions": """Analyze the Aider execution result from iteration {{iteration}} of {{max_retries}}.

Aider Status: {{aider_result_status}}
Aider Output/Error: {{aider_result_content}}

Original Prompt: {{original_prompt}}

Based on the above information, determine if:
1. The execution was successful and the task is complete
2. The execution failed but can be retried with a revised prompt
3. The execution failed and should be aborted

Output the result ONLY as a valid JSON object conforming to the FeedbackResult schema.

**IMPORTANT:** Your response MUST contain ONLY the valid JSON object conforming to the FeedbackResult schema. Do NOT include any introductory text, explanations, apologies, or concluding remarks. Your entire output must be the JSON object itself, starting with `{` and ending with `}`.""",
    "output_format": {"type": "json", "schema": "src.system.models.FeedbackResult"}
}


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
        self.mcp_server_configs: Dict[str, Dict[str, Any]] = {}
        self._load_mcp_config()
        self.memory_system: Optional[MemorySystem] = None
        self.task_system: Optional[TaskSystem] = None
        self.passthrough_handler: Optional[PassthroughHandler] = None
        self.aider_bridge: Optional['AiderBridge'] = None # Initialize as None
        self.indexed_repositories: List[str] = []
        self.file_access_manager: Optional[FileAccessManager] = None # Add attribute
        self.system_executors: Optional[SystemExecutorFunctions] = None # Add attribute

        logger.info("Initializing Application components...")
        try:
            # --- START MODIFICATION ---
            # 1. Instantiate components with fewer dependencies first
            # Use the module-level PROJECT_ROOT
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
            # Pass FileAccessManager instance to Handler during init
            handler_config['file_manager'] = self.file_access_manager
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
            
            # Re-initialize FileContextManager in BaseHandler with the correct MemorySystem
            if self.passthrough_handler and self.passthrough_handler.file_manager and self.memory_system:
                self.passthrough_handler.file_context_manager = FileContextManager(
                    memory_system=self.memory_system,
                    file_manager=self.passthrough_handler.file_manager
                )
                logger.info("Re-initialized FileContextManager in BaseHandler with correct MemorySystem.")
            else:
                logger.warning("Could not re-initialize FileContextManager: handler, file_manager, or memory_system missing.")

            logger.info("Cross-dependencies wired.")
            # --- END MODIFICATION ---

            logger.info("Components instantiated and wired.")

            # --- Core Template Registration ---
            logger.info("Registering core and user task templates...")
            try:
                # Define CONTENT-based template
                assoc_matching_content_template = {
                    "name": "internal:associative_matching_content", # New name
                    "type": "atomic",
                    "subtype": "associative_matching", # Keep subtype consistent
                    "description": "Internal task to find relevant files based on query and FULL FILE CONTENT.",
                    "parameters": {
                        "context_input": { "description": "Input query/context details (as dict)" },
                        "file_contents": { "description": "A single string containing file contents wrapped in `<file path=...>...</file>` tags" }
                    },
                    "params": {
                        "context_input": { "description": "Input query/context details (as dict)" },
                        "file_contents": { "description": "A single string containing file contents wrapped in `<file path=...>...</file>` tags" }
                    },
                    "instructions": """Analyze the user query details in 'context_input'.
Review the **full file contents** provided in the 'file_contents' parameter.
Based on the query and the **provided file contents**, select up to 10 relevant file paths.
For each relevant piece of context, provide the following information:
- id: A unique identifier (e.g., filename or chunk ID).
- content: The textual content of the match.
- relevance_score: A numerical score from 0.0 to 1.0 indicating relevance.
- content_type: A string describing the type of content (e.g., "file_content_chunk", "code_summary").
- source_path: (Optional) The original source file path if applicable.
- metadata: (Optional) A JSON object containing any additional relevant metadata (e.g., line numbers, language).
Provide a brief 'context_summary' explaining the relevance based on the selected files' content.
Output the result as a JSON object conforming to the AssociativeMatchResult schema.

Query Details: {{context_input.query}}

File Contents Snippet (Example Format - Actual input is the full dict):
{{file_contents}}

Select the best matching paths *from the provided file contents*.
**IMPORTANT:** Your response MUST contain ONLY the valid JSON object conforming to the AssociativeMatchResult schema specified above. Do NOT include any introductory text, explanations, apologies, or concluding remarks. Your entire output must be the JSON object itself, starting with `{` and ending with `}`.""",
                    "output_format": {"type": "json", "schema": "AssociativeMatchResult"}
                }
                self.task_system.register_template(assoc_matching_content_template)
                logger.info(f"Registered template: {assoc_matching_content_template['name']}")

                # Define METADATA-based template
                assoc_matching_metadata_template = {
                    "name": "internal:associative_matching_metadata", # New name
                    "type": "atomic",
                    "subtype": "associative_matching",
                    "description": "Internal task to find relevant files based on query and pre-generated METADATA.",
                     "parameters": {
                        "context_input": { "description": "Input query/context details (as dict)" },
                        "metadata_snippet": { "description": "Dictionary mapping candidate file paths to their metadata strings" }
                    },
                    "params": {
                        "context_input": { "description": "Input query/context details (as dict)" },
                        "metadata_snippet": { "description": "Dictionary mapping candidate file paths to their metadata strings" }
                    },
                   "instructions": """Analyze the user query details in 'context_input'.
Review the **file metadata** provided in the 'metadata_snippet' parameter (a dictionary mapping paths to metadata strings).
Based on the query and the **provided metadata**, select the top 3-5 most relevant file paths.
For each relevant piece of context, provide the following information:
- id: A unique identifier (e.g., filename or chunk ID).
- content: The textual content of the match (this would be the metadata string itself in this case).
- relevance_score: A numerical score from 0.0 to 1.0 indicating relevance.
- content_type: A string describing the type of content (e.g., "file_summary", "metadata_entry").
- source_path: (Optional) The original source file path if applicable (this would be the key from metadata_snippet).
- metadata: (Optional) A JSON object containing any additional relevant metadata.
Provide a brief 'context_summary' explaining the relevance based on the selected files' metadata.
Output the result as a JSON object conforming to the AssociativeMatchResult schema.

Query Details: {{context_input.query}}

Metadata Snippet (Example Format - Actual input is the full dict):
{{ metadata_snippet | dict_slice(10) | format_dict_snippet(250) }}

Select the best matching paths *from the provided metadata* and output the JSON.""",
                    "output_format": {"type": "json", "schema": "AssociativeMatchResult"}
                }
                self.task_system.register_template(assoc_matching_metadata_template)
                logger.info(f"Registered template: {assoc_matching_metadata_template['name']}")

                # Register NEW templates
                if self.task_system: # Ensure task_system is initialized
                    self.task_system.register_template(GENERATE_PLAN_TEMPLATE)
                    logger.info(f"Registered template: {GENERATE_PLAN_TEMPLATE['name']}")

                    self.task_system.register_template(ANALYZE_AIDER_RESULT_TEMPLATE)
                    logger.info(f"Registered template: {ANALYZE_AIDER_RESULT_TEMPLATE['name']}")
                else:
                    # This indicates a programming error in the init sequence
                    logger.error("TaskSystem not initialized before template registration attempt.")
                    raise RuntimeError("TaskSystem must be initialized before registering templates.")


            except AttributeError as ae:
                 logger.exception(f"Failed to register templates - likely missing register_template method: {ae}")
                 raise # Re-raise as this is critical
            except Exception as e:
                logger.exception(f"Failed to register templates: {e}")
                raise # Re-raise as this is critical

            # Instantiate SystemExecutorFunctions
            from src.executors.system_executors import SystemExecutorFunctions
            from src.handler import command_executor

            self.system_executors = SystemExecutorFunctions(
                memory_system=self.memory_system,
                file_manager=self.file_access_manager,
                command_executor_module=command_executor
            )
            logger.info("SystemExecutorFunctions instance created in Application.")

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
                        def _anthropic_tool_wrapper(params: Dict[str, Any]) -> str: 
                            if not fm_instance: return "Error: File manager not available"
                            try:
                                return tool_func(fm_instance, **params)
                            except Exception as e:
                                logger.exception(f"Error executing Anthropic tool {tool_func.__name__}: {e}")
                                return f"Error executing tool: {e}" 
                        # Manually set name and doc if pydantic_ai relies on them from the wrapper
                        _anthropic_tool_wrapper.__name__ = tool_func.__name__ 
                        _anthropic_tool_wrapper.__doc__ = tool_func.__doc__
                        return _anthropic_tool_wrapper
                    # --- END Anthropic Wrapper Refactor ---

                    anthropic_tool_pairs = [
                        (anthropic_tools.ANTHROPIC_VIEW_SPEC, anthropic_tools.view),
                        (anthropic_tools.ANTHROPIC_CREATE_SPEC, anthropic_tools.create),
                        (anthropic_tools.ANTHROPIC_STR_REPLACE_SPEC, anthropic_tools.str_replace),
                        (anthropic_tools.ANTHROPIC_INSERT_SPEC, anthropic_tools.insert),
                    ]

                    for tool_spec, tool_func in anthropic_tool_pairs:
                        executor_wrapper = create_anthropic_wrapper(tool_func, self.passthrough_handler.file_manager)

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

            # Initialize Aider integration (if available and enabled)
            self.initialize_aider() # Call the helper method
            logger.info("Aider integration initialization check complete.") # Updated log message


            # Determine active tools based on provider AFTER registration
            active_tools_specs = self._determine_active_tools(provider_id)

            # Set active tools on the handler AFTER registration
            if active_tools_specs:
                self.passthrough_handler.set_active_tool_definitions(active_tools_specs)
                logger.info(f"Set {len(active_tools_specs)} active tool definitions on handler")


            # Retrieve tools for agent initialization AFTER registration
            agent_pydantic_tools = [] # Initialize to empty list first
            # Modified to get List[PydanticTool] directly
            if PydanticTool is None:
                logger.error("pydantic_ai.Tool not imported. Cannot prepare tools for agent.")
                # agent_pydantic_tools remains an empty list
            elif self.passthrough_handler: # Ensure handler exists
                agent_pydantic_tools = self.passthrough_handler.get_tools_for_agent() # This method now returns List[PydanticTool]
            else:
                logger.error("PassthroughHandler not available to get tools for agent.")
                # agent_pydantic_tools remains an empty list
            
            logger.info(f"Retrieved {len(agent_pydantic_tools)} pydantic_ai.Tool objects for agent initialization.")

            # Trigger agent initialization in the manager AFTER registration
            if self.passthrough_handler and self.passthrough_handler.llm_manager:
                self.passthrough_handler.llm_manager.initialize_agent(tools=agent_pydantic_tools) # Pass List[PydanticTool]
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
                # tool_data IS the spec dictionary here
                if tool_name.startswith('system_'):
                    # --- START FIX: Append tool_data directly ---
                    active_tool_specs.append(tool_data) # Append the spec dict itself
                    # --- END FIX ---
                    logger.debug(f"Including system tool spec: {tool_name}")
                    # Removed warning as tool_data is the spec

        # Add provider-specific tools based on the provider_identifier
        if provider_identifier:
            if provider_identifier.startswith('anthropic:'):
                logger.debug("Including Anthropic tool specs.")
                # Add Anthropic tool specs from registered_tools
                if self.passthrough_handler and hasattr(self.passthrough_handler, 'registered_tools'):
                     for tool_name, tool_data in self.passthrough_handler.registered_tools.items():
                         if tool_name.startswith('anthropic_'):
                             # --- START FIX: Append tool_data directly ---
                             active_tool_specs.append(tool_data) # Append the spec dict itself
                             # --- END FIX ---
                             logger.debug(f"Including Anthropic tool spec: {tool_name}")
                             # Removed warning

            # Add other provider-specific logic here if needed
            # elif provider_identifier.startswith('openai:'):
            #     pass

        # Add Aider tools if dependencies were imported successfully
        aider_imported_successfully = AiderBridge is not None and AiderExecutors is not None
        if aider_imported_successfully:
            logger.debug("Including Aider tool specs (dependencies present).")
            if self.passthrough_handler and hasattr(self.passthrough_handler, 'registered_tools'):
                 for tool_name, tool_data in self.passthrough_handler.registered_tools.items():
                     if tool_name.startswith('aider:'):
                         # --- START FIX: Append tool_data directly ---
                         active_tool_specs.append(tool_data) # Append the spec dict itself
                         # --- END FIX ---
                         logger.debug(f"Including Aider tool spec: {tool_name}")
                         # Removed warning


        logger.info(f"Determined {len(active_tool_specs)} active tool specifications: {[t.get('name', 'unnamed') for t in active_tool_specs]}")
        return active_tool_specs

    def _register_system_tools(self):
        """Registers system-level tools with the handler."""
        if not self.passthrough_handler:
            logger.error("Cannot register system tools: Handler not initialized.")
            return
        if not hasattr(self, 'system_executors') or not self.system_executors:
            logger.error("Cannot register system tools: SystemExecutorFunctions not initialized.")
            return

        tools_to_register = [
            {
                "spec": {
                    "name": "system_get_context",
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
                "executor": self.system_executors.execute_get_context # Pass instance method directly
            },
            {
                "spec": {
                    "name": "system_read_files",
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
                "executor": self.system_executors.execute_read_files # Pass instance method directly
            },
            {
                "spec": {
                    "name": "system_list_directory",
                    "description": "Lists the contents of a specified directory.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "directory_path": {"type": "string", "description": "Path to the directory to list."}
                        },
                        "required": ["directory_path"]
                    }
                },
                "executor": self.system_executors.execute_list_directory # Pass instance method directly
            },
            {
                "spec": {
                    "name": "system_write_file",
                    "description": "Writes content to a specified file.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to the file to write."},
                            "content": {"type": "string", "description": "Content to write to the file."},
                            "overwrite": {"type": "boolean", "description": "Whether to overwrite if the file exists (default: false)."}
                        },
                        "required": ["file_path", "content"]
                    }
                },
                "executor": self.system_executors.execute_write_file # Pass instance method directly
            },
            {
                "spec": {
                    "name": "system_execute_shell_command",
                    "description": "Executes a shell command safely.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "The shell command to execute."},
                            "cwd": {"type": "string", "description": "Optional working directory for the command."},
                            "timeout": {"type": "integer", "description": "Optional timeout in seconds."}
                        },
                        "required": ["command"]
                    }
                },
                "executor": self.system_executors.execute_shell_command # Pass instance method directly
            }
        ]

        registered_count = 0
        for tool in tools_to_register:
            try:
                # Check if dependencies for the executor are met before registering
                if tool['spec']['name'] == 'system:get_context' and not self.memory_system:
                    logger.error("Skipping registration of system:get_context: MemorySystem not initialized.")
                    continue
                # Check file_manager dependency for file-related tools
                if tool['spec']['name'] in ['system:read_files', 'system:list_directory', 'system:write_file'] and not self.passthrough_handler.file_manager:
                    logger.error(f"Skipping registration of {tool['spec']['name']}: FileAccessManager not initialized in handler.")
                    continue
                # Check command_executor dependency for shell command tool
                if tool['spec']['name'] == 'system:execute_shell_command' and not self.system_executors.command_executor:
                    logger.error(f"Skipping registration of {tool['spec']['name']}: Command executor module not available.")
                    continue


                success = self.passthrough_handler.register_tool(tool["spec"], tool["executor"])
                if success:
                    registered_count += 1
                else:
                    logger.warning(f"Failed to register system tool: {tool['spec']['name']}")
            except Exception as e:
                logger.exception(f"Error registering system tool {tool['spec']['name']}: {e}")
        logger.info(f"Registered {registered_count}/{len(tools_to_register)} system tools.")


    def _load_mcp_config(self, config_path: str = ".mcp.json"):
        """Loads MCP server configurations from a JSON file."""
        # Use the module-level PROJECT_ROOT
        abs_config_path = os.path.join(PROJECT_ROOT, config_path)
        logger.info(f"Attempting to load MCP server config from: {abs_config_path}")
        try:
            if os.path.exists(abs_config_path):
                with open(abs_config_path, 'r') as f:
                    loaded_data = json.load(f)
                # Basic validation
                if "mcpServers" in loaded_data and isinstance(loaded_data["mcpServers"], dict):
                    self.mcp_server_configs = loaded_data["mcpServers"]
                    logger.info(f"Loaded {len(self.mcp_server_configs)} MCP server configurations: {list(self.mcp_server_configs.keys())}")
                else:
                    logger.warning(f"MCP config file '{abs_config_path}' found but missing 'mcpServers' dictionary or invalid format.")
            else:
                logger.warning(f"MCP config file not found at '{abs_config_path}'. No servers loaded from file.")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing MCP config file '{abs_config_path}': {e}")
        except Exception as e:
            logger.error(f"Error loading MCP config file '{abs_config_path}': {e}")

    def initialize_aider(self) -> None:
        """
        Initializes the AiderBridge and registers Aider tools if available and enabled.
        Prioritizes config flag, then environment variable for enablement.
        """
        aider_enabled = False
        config_aider_settings = self.config.get("aider", {})
        
        if isinstance(config_aider_settings, dict):
            aider_enabled_config_value = config_aider_settings.get("enabled")
            if isinstance(aider_enabled_config_value, bool):
                aider_enabled = aider_enabled_config_value
                if aider_enabled:
                    logger.info("Aider integration ENABLED via Application config ('aider.enabled': true).")
                else:
                    logger.info("Aider integration DISABLED via Application config ('aider.enabled': false).")
            else: # Not specified in config, check environment
                aider_enabled_env_val = os.environ.get('AIDER_ENABLED')
                aider_enabled = aider_enabled_env_val is not None and aider_enabled_env_val.lower() == 'true'
                if aider_enabled:
                    logger.info(f"Aider integration ENABLED via environment variable (AIDER_ENABLED='{aider_enabled_env_val}').")
                else:
                    logger.info(f"Aider integration DISABLED (AIDER_ENABLED env var is '{aider_enabled_env_val}', not 'true', and not set in app config).")
        elif isinstance(config_aider_settings, bool): # Handle if self.config['aider'] is just a boolean
            aider_enabled = config_aider_settings
            if aider_enabled:
                logger.info("Aider integration ENABLED via Application config ('aider': true).")
            else:
                logger.info("Aider integration DISABLED via Application config ('aider': false).")
        else: # Fallback to environment if 'aider' key is not a dict or bool
            aider_enabled_env_val = os.environ.get('AIDER_ENABLED')
            aider_enabled = aider_enabled_env_val is not None and aider_enabled_env_val.lower() == 'true'
            if aider_enabled:
                logger.info(f"Aider integration ENABLED via environment variable (AIDER_ENABLED='{aider_enabled_env_val}'). Config 'aider' key missing or invalid type.")
            else:
                logger.info(f"Aider integration DISABLED (AIDER_ENABLED env var is '{aider_enabled_env_val}', not 'true', and config 'aider' key missing or invalid).")


        if not aider_enabled:
            self.aider_bridge = None 
            logger.info("Skipping Aider initialization as it's disabled.")
            return

        # Check if Aider dependencies were imported successfully (still necessary)
        aider_imported_successfully = AiderBridge is not None and AiderExecutors is not None
        if not aider_imported_successfully:
             logger.info("Aider integration is unavailable (missing dependencies). Skipping initialization.")
             self.aider_bridge = None # Ensure it's None
             return

        # Check if config was actually found and passed
        aider_server_id = "aider-mcp-server"  # The key used in .mcp.json
        aider_mcp_config_loaded = self.mcp_server_configs.get(aider_server_id)

        if aider_mcp_config_loaded is None:
            logger.warning("Aider initialization skipped: Configuration for Aider not found in loaded MCP configs.")
            self.aider_bridge = None
            return

        # Check if transport is stdio
        if aider_mcp_config_loaded.get("transport") != "stdio":
            logger.error(f"Aider initialization skipped: Configuration requires 'stdio' transport, found '{aider_mcp_config_loaded.get('transport')}'.")
            self.aider_bridge = None
            return

        # Check if command is present (AiderBridge init will also check, but good here too)
        if not aider_mcp_config_loaded.get("command"):
            logger.error("Aider initialization skipped: STDIO configuration missing 'command'.")
            self.aider_bridge = None
            return

        # Proceed only if enabled AND dependencies available
        if not self.passthrough_handler:
            logger.error("Cannot initialize Aider: PassthroughHandler not available.")
            return
        if not self.memory_system:
             logger.error("Cannot initialize Aider: MemorySystem not available.")
             return
        if not self.file_access_manager:
             logger.error("Cannot initialize Aider: FileAccessManager not available.")
             return

        logger.info("Aider is available and configured via JSON. Initializing AiderBridge...")
        try:
            # Instantiate AiderBridge, passing the specific config dict loaded from JSON
            self.aider_bridge = AiderBridge(
                memory_system=self.memory_system,
                file_access_manager=self.file_access_manager,
                config=aider_mcp_config_loaded  # Pass the specific dict here
            )
            logger.info("AiderBridge (MCP Client) instantiated using specific JSON config.")

            def create_aider_wrapper(tool_executor_method):
                def sync_wrapper(params: Dict[str, Any], bridge=self.aider_bridge) -> Dict[str, Any]:
                    if not bridge:
                        return _create_failed_result_dict("dependency_error", "Aider bridge not available for tool execution.")
                    try:
                        # Check if an event loop is already running
                        try:
                            loop = asyncio.get_running_loop()
                            # If a loop is running, schedule the coroutine and wait for it
                            logger.warning("Running async Aider tool from existing event loop. Consider refactoring caller to be async.")
                            future = asyncio.run_coroutine_threadsafe(tool_executor_method(params, bridge), loop)
                            return future.result(timeout=120) # Add a timeout
                        except RuntimeError: # No running event loop
                            return asyncio.run(tool_executor_method(params, bridge))
                    except asyncio.TimeoutError:
                        logger.error(f"Aider tool execution timed out: {tool_executor_method.__name__}")
                        return _create_failed_result_dict("execution_timeout", "Aider tool execution timed out.")
                    except Exception as e:
                        logger.exception(f"Error running Aider tool '{tool_executor_method.__name__}' via wrapper: {e}")
                        return _create_failed_result_dict("unexpected_error", f"Error running Aider tool '{tool_executor_method.__name__}': {e}")
                # Manually set name and doc if needed
                sync_wrapper.__name__ = tool_executor_method.__name__
                sync_wrapper.__doc__ = tool_executor_method.__doc__
                return sync_wrapper

            aider_tools_to_register = [
                {
                    "spec": {
                        "name": "aider_automatic",
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
                    "executor_method_name": "execute_aider_automatic"
                },
                {
                    "spec": {
                        "name": "aider_interactive",
                        "description": "Starts or continues an interactive Aider coding session.",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "The initial query or follow-up instruction."},
                                "prompt": {"type": "string", "description": "Alternative to 'query'."},
                                "file_context": {"type": "string", "description": "Optional JSON string array of explicit file paths."},
                                "model": {"type": "string", "description": "Optional specific model override for Aider."}
                            },
                        }
                    },
                    "executor_method_name": "execute_aider_interactive"
                }
            ]

            registered_count = 0
            if AiderExecutors:
                logger.info(f"Attempting to register {len(aider_tools_to_register)} Aider tools...")
                for tool_info in aider_tools_to_register:
                    tool_spec = tool_info["spec"]
                    method_name = tool_info["executor_method_name"]
                    
                    # Get the async method from AiderExecutors class
                    async_executor_method = getattr(AiderExecutors, method_name, None)
                    if not async_executor_method or not asyncio.iscoroutinefunction(async_executor_method):
                        logger.error(f"Could not find async executor method '{method_name}' in AiderExecutors.")
                        continue
                        
                    # Create the synchronous wrapper
                    sync_executor_wrapper = create_aider_wrapper(async_executor_method)
                    
                    logger.debug(f"Registering tool: {tool_spec['name']} with executor wrapper for {method_name}")
                    success = self.passthrough_handler.register_tool(tool_spec, sync_executor_wrapper)
                    logger.debug(f"Registration result for {tool_spec['name']}: {success}")

                    if success:
                        registered_count += 1
                        # logger.debug(f"Registered Aider tool: {tool_spec['name']}") # Covered by log above
                    else:
                        logger.warning(f"Failed to register Aider tool: {tool_spec['name']}")
                logger.info(f"Registered {registered_count}/{len(aider_tools_to_register)} Aider tools.")
                # --- START: Add Logging ---
                # Add check immediately after registration
                logger.info(f"Handler tool executors after Aider registration: {list(self.passthrough_handler.tool_executors.keys())}")
                # --- END: Add Logging ---
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
                memory_system=self.memory_system # Pass memory_system here
                # optional_history_str=self.passthrough_handler.get_history_string() # If needed
            )
            logger.debug(f"Task command result status: {result_dict.get('status')}")
            return result_dict
        except Exception as e:
            logger.exception(f"Error handling task command '{identifier}': {e}")
            return _create_failed_result_dict("unexpected_error", f"Unexpected error during task command execution: {e}")


# Example Usage (Optional)
if __name__ == "__main__":
    logger.info("Running basic Application example...")
    try:
        app = Application(config={"handler_config": {"default_model_identifier": "anthropic:claude-3-5-sonnet-latest"}})
        query_result = app.handle_query("What is the capital of France?")
        print("\nQuery Result:")
        import json
        def json_serializable(obj):
            if callable(obj):
                return str(obj)
            if isinstance(obj, PydanticTool): # Handle PydanticTool objects
                return f"<PydanticTool name='{obj.name}'>"
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
        print(json.dumps(query_result, indent=2, default=json_serializable))
        task_result = app.handle_task_command('(list "hello" "world")')
        print("\nTask Command Result:")
        print(json.dumps(task_result, indent=2, default=json_serializable))
        tool_result = app.handle_task_command("system:read_files", {"file_paths": ["src/main.py"]})
        print("\nSystem Tool Result:")
        print(json.dumps(tool_result, indent=2, default=json_serializable))
        if app.passthrough_handler.get_provider_identifier().startswith("anthropic:"):
            dummy_file = "dummy_anthropic_test.txt"
            create_params = {"file_path": dummy_file, "content": "Hello Anthropic!"}
            create_result = app.handle_task_command("anthropic:create", create_params)
            print("\nAnthropic Create Result:")
            print(json.dumps(create_result, indent=2, default=json_serializable))
            if create_result.get("status") == "COMPLETE":
                view_params = {"file_path": dummy_file}
                view_result = app.handle_task_command("anthropic:view", view_params)
                print("\nAnthropic View Result:")
                print(json.dumps(view_result, indent=2, default=json_serializable))
                if os.path.exists(dummy_file):
                    os.remove(dummy_file)
    except Exception as main_e:
        logger.exception(f"Error in main execution block: {main_e}")
