import json
import logging
import os  # Add os import for environment variable checking
import asyncio         # NEW – we’ll manage a dedicated event-loop
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Type, Union
import uuid  # ADDED for unique task identifier
from datetime import datetime  # ADDED for timestamp

# Import pydantic-ai directly
import pydantic_ai

# Import models needed for error handling
from src.system.models import TaskResult, TaskFailureError

# Define module-level logger
logger = logging.getLogger(__name__)

# --- Attempt Top-Level Import for Agent ONLY ---
try:
    # Try importing only Agent from the top level
    from pydantic_ai import Agent, Tool as PydanticTool # Import Tool as PydanticTool

    _PydanticAI_Import_Success = True
    logging.debug(
        "LLMInteractionManager: Top-level pydantic-ai import successful (Agent, Tool)."
    )
except ImportError as e:
    # Log the specific import error details
    logging.error(
        f"LLMInteractionManager: Top-level import of pydantic-ai Agent or Tool failed: {e}",
        exc_info=True,
    )
    # Set Agent to None if import fails
    Agent = None  
    PydanticTool = None # type: ignore
    _PydanticAI_Import_Success = False
# Define AIResponse as Any since we can't import it reliably
AIResponse = Any  # type: ignore
# --- End Import Attempt ---

# Use TYPE_CHECKING for type hints without runtime imports
if TYPE_CHECKING:
    # These are now potentially defined above, but keep for clarity if needed
    # or adjust based on actual usage if AIResponse is only used in hints.
    # If Agent/AIResponse are None above, these hints might cause issues
    # depending on the type checker. Consider conditional hints if necessary.
    pass  # Keep the block for potential future use or remove if empty


class LLMInteractionManager:
    """
    Manages interaction with the LLM provider via pydantic-ai.

    Encapsulates agent initialization and execution logic.
    """

    def __init__(
        self,
        default_model_identifier: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initializes the LLMInteractionManager.

        Args:
            default_model_identifier: String identifying the pydantic-ai model (e.g., "openai:gpt-4o").
            config: Dictionary for configuration (e.g., API keys, base_system_prompt, llm_providers).
        """
        self.config = config or {}
        self.default_model_identifier = default_model_identifier or self.config.get(
            "default_model_identifier"
        )
        self.base_system_prompt = self.config.get(
            "base_system_prompt", "You are a helpful assistant."
        )
        self.debug_mode = False
        self._model_id = self.default_model_identifier # Keep track of the default
        self._base_prompt = self.base_system_prompt
        self._agent_config = self.config.get("pydantic_ai_agent_config", {})
        self.agent: Optional[Any] = None # The default, pre-initialized agent

        # --- NEW: create a single reusable event-loop ---
        # All pydantic-ai calls made by this manager will run on this loop,
        # preventing “object bound to a different event loop” errors.
        self._event_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        # Do *not* start run_forever(); we’ll drive it with run_until_complete ad-hoc

        logging.info("LLMInteractionManager initialized (Agent creation deferred).")

    def _initialize_pydantic_ai_agent(self) -> Optional[Any]:
        """
        Initializes the pydantic-ai Agent instance.
        (Implementation deferred to Phase 1B - Now Implemented)
        """
        logger.debug("Attempting to initialize pydantic-ai Agent...")

        # --- REVERT CHECK ---
        # Remove internal import logic
        # Check module-level Agent variable
        logger.debug(
            f"Value of module-level Agent before check: {Agent} (Type: {type(Agent)})"
        )
        if not Agent:
            logger.error(
                "Cannot initialize agent: pydantic-ai Agent class is None or unavailable (Import failed)."
            )
            return None
        # --- END REVERT ---

        # Log relevant config values
        logger.debug(f"  Default Model Identifier: {self.default_model_identifier}")
        logger.debug(f"  Base System Prompt: {self.base_system_prompt}")
        logger.debug(f"  Raw Config Passed: {self.config}")

        # Check for common API keys in environment
        openai_key_present = "OPENAI_API_KEY" in os.environ and bool(
            os.environ["OPENAI_API_KEY"]
        )
        anthropic_key_present = "ANTHROPIC_API_KEY" in os.environ and bool(
            os.environ["ANTHROPIC_API_KEY"]
        )
        google_key_present = "GOOGLE_API_KEY" in os.environ and bool(
            os.environ["GOOGLE_API_KEY"]
        )
        logger.debug(
            f"  Env Keys Check: OpenAI={openai_key_present}, Anthropic={anthropic_key_present}, Google={google_key_present}"
        )

        if not self.default_model_identifier:
            logger.error(
                "Cannot initialize agent: No default_model_identifier provided or found in config."
            )
            return None

        try:
            # Basic initialization - assumes model identifier string is sufficient
            # More complex setup (API keys, specific model args) might be needed
            # depending on pydantic-ai's requirements and the config structure.
            # API keys might need to be passed explicitly or set as environment variables.
            agent_config = self.config.get(
                "pydantic_ai_agent_config", {}
            )  # Allow passing extra config
            logger.debug(f"  Using Agent Config additions: {agent_config}")

            # Example: Extracting potential API key from config
            # api_key = self.config.get("llm_api_key")
            # if api_key:
            #     agent_config['api_key'] = api_key # Adjust key name based on pydantic-ai model needs

            # Call the constructor using the module-level Agent
            agent = Agent(
                model=self.default_model_identifier,
                system_prompt=self.base_system_prompt,  # Base prompt set here
                # tools=... # Tools are typically passed per-call or registered differently
                **agent_config,  # Pass any additional config
            )
            logger.info(
                f"pydantic-ai Agent initialized successfully for model: {self.default_model_identifier}"
            )
            return agent
        except Exception as e:
            # Log the full exception details
            logger.error(
                f"Failed to initialize pydantic-ai Agent for model '{self.default_model_identifier}': {e}",
                exc_info=True,
            )
            return None

    def initialize_agent(self, tools: List[PydanticTool]) -> None: # Changed type hint
        """
        Initializes the pydantic-ai Agent instance with the provided tools.
        """
        if self.agent is not None:
            logging.warning("Agent is already initialized.")
            return
        if not self._model_id:
            raise RuntimeError(
                "Cannot initialize agent: No model identifier configured."
            )
        if not Agent: # Check module-level Agent
            raise RuntimeError(
                "Cannot initialize agent: pydantic-ai Agent class unavailable."
            )
        if not PydanticTool and tools: # Check module-level PydanticTool if tools are provided
            raise RuntimeError(
                 "Cannot initialize agent with tools: pydantic_ai.Tool class unavailable."
            )
        try:
            # Agent constructor takes Sequence[Tool | Callable].
            # We are now passing List[PydanticTool] which is compatible.
            self.agent = Agent(
                model=self._model_id,
                system_prompt=self._base_prompt,
                tools=tools,
                **self._agent_config,
            )
            logging.info(f"pydantic-ai Agent initialized for model: {self._model_id} with {len(tools)} tools.")
        except Exception as e:
            logging.exception(f"Failed to initialize agent: {e}")
            self.agent = None
            raise RuntimeError(f"AgentInitializationError: {e}") from e

    def set_debug_mode(self, enabled: bool) -> None:
        """
        Sets the debug mode flag. May enable instrumentation in the future.

        Args:
            enabled: Boolean value to enable/disable debug mode.
        """
        self.debug_mode = enabled
        logging.info(f"LLMInteractionManager debug mode set to: {enabled}")
        # TODO: Potentially enable pydantic-ai instrumentation if debug_mode is True
        # if self.agent and hasattr(self.agent, 'instrument'):
        #     self.agent.instrument(enabled=enabled) # Hypothetical instrumentation call

    def get_provider_identifier(self) -> Optional[str]:
        if not self.agent:
            logging.warning("Cannot get provider identifier: Agent is not initialized.")
            return None
            
        if hasattr(self.agent, 'model') and isinstance(self.agent.model, str):
            if self.agent.model:
                return self.agent.model
            else:
                logging.warning("LLMInteractionManager: Agent's model attribute is an empty string. Falling back to default.")
        if not self.default_model_identifier:
            logging.warning("LLMInteractionManager: No default_model_identifier configured.")
        return self.default_model_identifier


    async def execute_call(
        self,
        prompt: str,
        conversation_history: List[Any],  # Updated to accept ModelMessage objects
        system_prompt_override: Optional[str] = None,
        tools_override: Optional[List[Callable]] = None,  # Executors
        output_type_override: Optional[Type] = None,
        active_tools: Optional[List[Dict[str, Any]]] = None,  # Tool definitions
        model_override: Optional[str] = None, # ADDED PARAMETER
        history_config: Optional[Any] = None, # Add history_config parameter
    ) -> Dict[str, Any]:
        """
        Executes a call to the configured pydantic-ai agent, potentially using an override model.

        Args:
            prompt: The user's input prompt for the current turn.
            conversation_history: The history of the conversation up to this point.
            system_prompt_override: An optional system prompt to use for this specific call.
            tools_override: Optional list of tools (functions or specs) for this call.
            output_type_override: Optional Pydantic model for structured output.
            active_tools: Optional list of tool definitions (specs) for this call.
            model_override: Optional string identifying a specific model to use for this call.

        Returns:
            A dictionary containing the result:
            {
                "success": bool,
                "content": Optional[str], # Assistant's response content
                "tool_calls": Optional[List[Any]], # Any tool calls made by the agent
                "usage": Optional[Dict[str, int]], # Token usage, etc.
                "error": Optional[str] # Error message if success is False
            }
        """
        logger = logging.getLogger(__name__)  # Use specific logger

        # --- START: Detailed LLM Call Logging Initialization ---
        call_task_id = str(uuid.uuid4())
        call_timestamp_start_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        # Use a distinct log_filename_base for the comprehensive interaction log
        interaction_log_filename_base = f"llm_interaction_{call_timestamp_start_str}_{call_task_id}"
        
        log_data_entry: Dict[str, Any] = {
            "task_id": call_task_id,
            "timestamp_request": call_timestamp_start_str,
        }
        # --- END: Detailed LLM Call Logging Initialization ---

        # --- START: Model Override Logic ---
        target_agent = self.agent # Start with the default agent
        target_model_id_for_log = self.default_model_identifier
        log_data_entry["model_to_be_used"] = target_model_id_for_log # Initial assumption for logging

        if model_override and model_override != self.default_model_identifier:
            logger.info(f"Model override requested: '{model_override}'")
            target_model_id_for_log = model_override # Update for logging
            log_data_entry["model_to_be_used"] = target_model_id_for_log # Update with override
            try:
                # Look up configuration for the override model
                # Assumes config structure: self.config['llm_providers'][model_override]
                override_provider_config = self.config.get('llm_providers', {}).get(model_override)
                if override_provider_config is None: # Check explicitly for None
                    error_msg = f"Configuration not found for model override: {model_override}"
                    logger.error(error_msg)
                    error_details = TaskFailureError(type="TASK_FAILURE", reason="configuration_error", message=error_msg)
                    
                    log_data_entry["error_details"] = error_details.model_dump(exclude_none=True)
                    # Ensure all potential keys for final_manager_result are present, even if None
                    log_data_entry["final_manager_result"] = {"success": False, "content": None, "parsed_content": None, "tool_calls": None, "usage": None, "error": error_msg}
                    try:
                        with open(f"{interaction_log_filename_base}_FAIL_CONFIG.json", "w") as f_json: json.dump(log_data_entry, f_json, indent=2, default=lambda o: repr(o))
                        logger.info(f"LLM Interaction details (FAIL_CONFIG) logged to {interaction_log_filename_base}_FAIL_CONFIG.json")
                    except Exception as log_e: logger.error(f"Error writing LLM Interaction log file on config failure: {log_e}", exc_info=True)
                    
                    return {
                        "success": False,
                        "content": None,
                        "tool_calls": None,
                        "usage": None,
                        "error": error_msg,
                        "parsed_content": None,
                        "notes": {
                            "error": error_details.model_dump(exclude_none=True)
                        }
                    }

                # Get tools from the default agent (assuming tools are compatible)
                # Ensure self.agent is initialized before accessing .tools
                if not self.agent or not hasattr(self.agent, 'tools'):
                     error_msg = "Default agent or its tools not available for override."
                     logger.error(error_msg)
                     error_details = TaskFailureError(type="TASK_FAILURE", reason="dependency_error", message=error_msg)
                     
                     log_data_entry["error_details"] = error_details.model_dump(exclude_none=True)
                     log_data_entry["final_manager_result"] = {"success": False, "content": None, "parsed_content": None, "tool_calls": None, "usage": None, "error": error_msg}
                     try:
                         with open(f"{interaction_log_filename_base}_FAIL_AGENT_TOOLS.json", "w") as f_json: json.dump(log_data_entry, f_json, indent=2, default=lambda o: repr(o))
                         logger.info(f"LLM Interaction details (FAIL_AGENT_TOOLS) logged to {interaction_log_filename_base}_FAIL_AGENT_TOOLS.json")
                     except Exception as log_e: logger.error(f"Error writing LLM Interaction log file on agent tools failure: {log_e}", exc_info=True)
                     
                     return TaskResult(status="FAILED", content=error_msg, notes={"error": error_details.model_dump(exclude_none=True)}).model_dump(exclude_none=True)

                current_tools = self.agent.tools # Get tools from the initialized default agent

                # Combine base agent config with specific override config
                # Ensure override_provider_config only contains valid Agent args
                combined_agent_config = self._agent_config.copy()
                # Filter override_provider_config for valid Agent kwargs if necessary, or assume it's clean
                combined_agent_config.update(override_provider_config) # Override specific keys

                logger.debug(f"Instantiating temporary Agent for override: {model_override}")
                # Ensure Agent class is available
                if not Agent:
                    raise RuntimeError("pydantic-ai Agent class not imported/available")

                # Determine the system prompt for the temporary agent
                temp_agent_system_prompt = system_prompt_override if system_prompt_override is not None else self.base_system_prompt

                # Instantiate the temporary agent
                temp_agent = Agent(
                    model=model_override,
                    system_prompt=temp_agent_system_prompt,
                    tools=current_tools, # Pass tools from default agent
                    **combined_agent_config # Pass combined config
                )
                target_agent = temp_agent # Use the temporary agent for this call
                logger.info(f"Temporary Agent created for model: {model_override}")

            except Exception as agent_init_error:
                logger.exception(f"Failed to initialize temporary Agent for override '{model_override}': {agent_init_error}")
                error_msg = f"Failed to initialize agent for model: {model_override}"
                error_details = TaskFailureError(type="TASK_FAILURE", reason="llm_error", message=f"{error_msg}: {agent_init_error}")
                
                log_data_entry["error_details"] = error_details.model_dump(exclude_none=True)
                log_data_entry["final_manager_result"] = {"success": False, "content": None, "parsed_content": None, "tool_calls": None, "usage": None, "error": f"{error_msg}: {agent_init_error}"}
                try:
                    with open(f"{interaction_log_filename_base}_FAIL_TEMP_AGENT_INIT.json", "w") as f_json: json.dump(log_data_entry, f_json, indent=2, default=lambda o: repr(o))
                    logger.info(f"LLM Interaction details (FAIL_TEMP_AGENT_INIT) logged to {interaction_log_filename_base}_FAIL_TEMP_AGENT_INIT.json")
                except Exception as log_e: logger.error(f"Error writing LLM Interaction log file on temp agent init failure: {log_e}", exc_info=True)
                
                return {
                    "success": False,
                    "content": None,
                    "tool_calls": None,
                    "usage": None,
                    "error": f"{error_msg}: {agent_init_error}",
                    "parsed_content": None,
                    "notes": {
                        "error": error_details.model_dump(exclude_none=True)
                    }
                }
        else:
             logger.debug(f"Using default agent: {self.default_model_identifier}")
        # --- END: Model Override Logic ---
        
        log_data_entry["model_used"] = target_model_id_for_log # Final confirmation of model used for the call

        # Ensure target_agent is valid before proceeding
        if not target_agent:
             error_msg = "LLM Agent not available (Initialization likely failed or default agent missing)."
             logger.error(f"Cannot execute call: {error_msg}")
             
             log_data_entry["error_details"] = {"type": "AgentNotInitializedError", "message": error_msg}
             log_data_entry["final_manager_result"] = {"success": False, "content": None, "parsed_content": None, "tool_calls": None, "usage": None, "error": error_msg}
             try:
                 with open(f"{interaction_log_filename_base}_FAIL_NO_AGENT_AVAILABLE.json", "w") as f_json: json.dump(log_data_entry, f_json, indent=2, default=lambda o: repr(o))
                 logger.info(f"LLM Interaction details (FAIL_NO_AGENT_AVAILABLE) logged to {interaction_log_filename_base}_FAIL_NO_AGENT_AVAILABLE.json")
             except Exception as log_e: logger.error(f"Error writing LLM Interaction log file when no agent available: {log_e}", exc_info=True)
             
             # --- START FIX: Return consistent failure dict ---
             return {
                 "success": False,
                 "content": None,
                 "tool_calls": None,
                 "usage": None,
                 "error": "AgentNotInitializedError: LLM Agent not initialized.",
                 "parsed_content": None # Ensure all keys are present
             }
             # --- END FIX ---

        # Original check for default agent initialization (still relevant if no override)
        # if self.agent is None: # This check is now covered by the target_agent check above
        #     logger.error(
        #         "Cannot execute LLM call: Agent not initialized. Call initialize_agent first."
        #     )
        #     return {
        #         "success": False,
        #         "content": None,
        #         "tool_calls": None,
        #         "usage": None,
        #         "error": "AgentNotInitializedError: LLM Agent not initialized.",
        #     }

        try:
            # Determine the system prompt to use for the call
            current_system_prompt = (
                system_prompt_override
                if system_prompt_override is not None
                else self.base_system_prompt
            )

            # Prepare keyword arguments separately
            run_kwargs = {
                "message_history": conversation_history,  # Pass history here
                "system_prompt": current_system_prompt,
            }

            # Log the full prompt and context to a file for debugging
            try:
                task_id = str(uuid.uuid4())
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                log_filename_base = f"llm_full_prompt_{timestamp}_{task_id}"
                
                log_data = {
                    "task_id": task_id,
                    "timestamp": timestamp,
                    "system_prompt": current_system_prompt,
                    "conversation_history": [msg.model_dump(exclude_none=True, round_trip=True) if hasattr(msg, 'model_dump') else str(msg) for msg in conversation_history],
                    "prompt": prompt,
                    "model_used": target_model_id_for_log, # Log which model was used
                }

                # Write to .log file (human-readable, might be same as JSON or different format if preferred)
                log_file_path = f"{log_filename_base}.log"
                with open(log_file_path, "w") as _f:
                    _f.write(json.dumps(log_data, indent=2)) # Currently same as JSON
                logger.info(f"LLM full prompt written to {log_file_path}")

                # Write to .json file (structured data)
                json_file_path = f"{log_filename_base}.json"
                with open(json_file_path, "w") as _f_json:
                    json.dump(log_data, _f_json, indent=2)
                logger.info(f"LLM full prompt JSON data written to {json_file_path}")

            except Exception as _e:
                logger.error(f"Failed to write full LLM prompt to file(s): {_e}")

            # --- START: Populate log_data_entry with agent request details ---
            log_data_entry["main_user_prompt_to_agent"] = prompt
            log_data_entry["final_system_prompt_to_agent"] = run_kwargs.get("system_prompt")
            
            # Serialize conversation history
            history_for_log = []
            raw_history = run_kwargs.get("message_history", [])
            for msg in raw_history:
                if hasattr(msg, 'model_dump'):
                    history_for_log.append(msg.model_dump(exclude_none=True, round_trip=True))
                else:
                    history_for_log.append(str(msg))
            log_data_entry["history_to_agent"] = history_for_log
            
            # Determine tools for the agent call (will be added to run_kwargs later)
            tools_for_agent_run = None
            if tools_override: # Prioritize tools_override
                tools_for_agent_run = tools_override
            elif active_tools: # Fallback to active_tools (definitions)
                tools_for_agent_run = active_tools
            
            # Serialize tools for logging
            tools_arg_for_log = []
            if tools_for_agent_run:
                for t_item in tools_for_agent_run:
                    if PydanticTool is not None and isinstance(t_item, PydanticTool):
                        tools_arg_for_log.append({
                            "type": "PydanticTool", "name": t_item.name, 
                            "description": t_item.description, 
                            "schema": t_item.schema # schema is already a dict
                        })
                    elif callable(t_item):
                        tools_arg_for_log.append({
                            "type": "callable", "name": getattr(t_item, '__name__', str(t_item)),
                            "docstring": getattr(t_item, '__doc__', None) # Using docstring for description
                        })
                    elif isinstance(t_item, dict): # Tool spec dictionary
                        tools_arg_for_log.append({"type": "dict_spec", **t_item})
                    else: # Fallback for other types
                        tools_arg_for_log.append({"type": str(type(t_item)), "value_repr": repr(t_item)})
            log_data_entry["tools_to_agent"] = tools_arg_for_log
            
            # Log output_type if provided
            if output_type_override:
                log_data_entry["output_type_to_agent"] = f"{output_type_override.__module__}.{output_type_override.__name__}"
            else:
                log_data_entry["output_type_to_agent"] = None
            # --- END: Populate log_data_entry with agent request details ---

            # Handle tools_override and active_tools
            # --- START FIX for tools precedence ---
            if tools_override: # This was already correct, tools_for_agent_run is now set above
                run_kwargs["tools"] = tools_override # Prioritize tools_override
                logging.debug(f"Using tools_override ({len(tools_override)}) for agent.run_sync")
            elif active_tools:
                run_kwargs["tools"] = active_tools # Fallback to active_tools (definitions)
                logging.debug(f"Using active_tools ({len(active_tools)}) for agent.run_sync")
            # --- END FIX for tools precedence ---

            if output_type_override:
                run_kwargs["output_type"] = output_type_override
                logging.debug(
                    f"Executing agent call with output_type: {output_type_override.__name__}"
                )

            # Log the arguments being passed
            logger.debug(
                f"LLMInteractionManager: Calling agent.run_sync (Model: '{target_model_id_for_log}') with prompt='{prompt[:100]}...' and kwargs={run_kwargs}"
            )

            # Add concise logging for key parameters
            logger.debug(f"Calling run_sync for model: {target_model_id_for_log}")
            logger.debug(f"Prompt type: {type(prompt)}, length: {len(prompt)}")
            logger.debug(f"System prompt: {run_kwargs.get('system_prompt')[:100]}...")
            
            # Log tool and output type information without full dumps
            if 'tools' in run_kwargs:
                tool_info = run_kwargs.get('tools')
                if isinstance(tool_info, list):
                    tool_count = len(tool_info)
                    tool_names = [getattr(t, '__name__', str(t)) for t in tool_info[:5]] if callable(tool_info[0]) else [t.get('name', 'unnamed') for t in tool_info[:5]]
                    logger.debug(f"Using {tool_count} tools: {', '.join(tool_names)}{' and more...' if tool_count > 5 else ''}")
            
            if 'output_type' in run_kwargs:
                output_type = run_kwargs.get('output_type')
                logger.debug(f"Output type: {getattr(output_type, '__name__', str(output_type))}")

            if self.debug_mode:
                # Redundant logging now, keep or remove
                logger.debug(
                    f"Calling agent.run_sync with prompt='{prompt[:100]}...' and kwargs={run_kwargs}"
                )

            response = await target_agent.run(prompt, **run_kwargs)

            if self.debug_mode:
                logging.debug(f"Agent response received: {response}")

            # --- START: Log pydantic_ai agent response and prepare manager result ---
            log_data_entry["timestamp_response"] = datetime.now().isoformat()
            
            pydantic_ai_response_log_data = {}
            # Serialize response.output for logging
            raw_output_from_agent = getattr(response, "output", None)
            if hasattr(raw_output_from_agent, "model_dump"):
                pydantic_ai_response_log_data["output"] = raw_output_from_agent.model_dump(exclude_none=True, round_trip=True)
            elif raw_output_from_agent is not None:
                pydantic_ai_response_log_data["output"] = str(raw_output_from_agent)
            else:
                pydantic_ai_response_log_data["output"] = None

            # Serialize response.tool_calls for logging
            raw_tool_calls_from_agent = getattr(response, "tool_calls", [])
            if raw_tool_calls_from_agent:
                serialized_tool_calls_for_log = []
                for tc in raw_tool_calls_from_agent:
                    if hasattr(tc, 'model_dump'):
                        serialized_tool_calls_for_log.append(tc.model_dump(exclude_none=True, round_trip=True))
                    else:
                        serialized_tool_calls_for_log.append(str(tc))
                pydantic_ai_response_log_data["tool_calls"] = serialized_tool_calls_for_log
            else:
                pydantic_ai_response_log_data["tool_calls"] = []

            # Serialize response.usage for logging (reusing existing logic)
            raw_usage_attr = getattr(response, "usage", None)
            actual_usage_data_for_log: Optional[Dict[str, Any]] = None
            if raw_usage_attr is not None:
                if callable(raw_usage_attr):
                    try: actual_usage_data_for_log = raw_usage_attr()
                    except Exception as e_usage_call_log: actual_usage_data_for_log = {"raw_usage_representation": str(raw_usage_attr), "error_calling_usage": str(e_usage_call_log)}
                elif isinstance(raw_usage_attr, dict): actual_usage_data_for_log = raw_usage_attr
                elif hasattr(raw_usage_attr, "model_dump"): actual_usage_data_for_log = raw_usage_attr.model_dump(exclude_none=True, round_trip=True)
                else: actual_usage_data_for_log = {"raw_usage_representation": str(raw_usage_attr)}
            pydantic_ai_response_log_data["usage"] = actual_usage_data_for_log
            
            log_data_entry["pydantic_ai_agent_response"] = pydantic_ai_response_log_data
            # --- END: Log pydantic_ai agent response ---

            # Process response for manager return value (using original logic)
            content = getattr(response, "output", None)
            tool_calls = getattr(response, "tool_calls", []) # These are Pydantic models from agent
            
            # Reuse the processed usage data for the manager's return value
            usage = actual_usage_data_for_log 

            parsed_content = None
            if content is not None and hasattr(content, "model_dump"):
                parsed_content = content # Store the Pydantic model

            content_str = str(content) if content is None or isinstance(content, str) else \
                          (content.model_dump_json() if hasattr(content, "model_dump_json") else 
                           (str(content.model_dump()) if hasattr(content, "model_dump") else str(content)))

            manager_result_dict = {
                "success": True, "content": content_str, "parsed_content": parsed_content, 
                "tool_calls": tool_calls, "usage": usage, "error": None,
            }

            # Prepare final_manager_result for logging (serialize Pydantic models within manager_result_dict)
            logged_final_manager_result = {
                "success": manager_result_dict["success"],
                "content": manager_result_dict["content"], # Already string
                "parsed_content": manager_result_dict["parsed_content"].model_dump(exclude_none=True, round_trip=True) if hasattr(manager_result_dict["parsed_content"], "model_dump") else manager_result_dict["parsed_content"],
                "tool_calls": [tc.model_dump(exclude_none=True, round_trip=True) if hasattr(tc, "model_dump") else tc for tc in manager_result_dict["tool_calls"]] if manager_result_dict["tool_calls"] else [],
                "usage": manager_result_dict["usage"], # Already processed dict or None
                "error": manager_result_dict["error"],
            }
            log_data_entry["final_manager_result"] = logged_final_manager_result
            
            # Write the comprehensive interaction log file
            try:
                with open(f"{interaction_log_filename_base}.json", "w") as f_json:
                    # Custom default handler for non-serializable objects
                    def fallback_serializer(obj):
                        if PydanticTool is not None and isinstance(obj, PydanticTool): # Must check before callable
                            return {"type": "PydanticTool", "name": obj.name, "description": obj.description, "schema_repr": repr(obj.schema)}
                        if callable(obj): 
                            return f"<callable {getattr(obj, '__name__', 'unnamed')}>"
                        if isinstance(obj, type): 
                            return f"<type {obj.__module__}.{obj.__name__}>"
                        # Fallback for other Pydantic models not caught by explicit model_dump elsewhere
                        if hasattr(obj, 'model_dump'):
                            try: return obj.model_dump(exclude_none=True, round_trip=True)
                            except: pass # Fall through to repr
                        return repr(obj) 
                    json.dump(log_data_entry, f_json, indent=2, default=fallback_serializer)
                logger.info(f"LLM Interaction details logged to {interaction_log_filename_base}.json")
            except Exception as log_e:
                logger.error(f"Error writing LLM Interaction log file: {log_e}", exc_info=True)

            return manager_result_dict # Return original manager_result_dict with Pydantic models intact
        except Exception as e:
            logging.error(
                f"Error during pydantic-ai agent execution: {e}", exc_info=True
            )
            # Populate log_data_entry with error before writing
            log_data_entry["error_during_agent_execution"] = str(e)
            log_data_entry["timestamp_response"] = datetime.now().isoformat() # Add response timestamp even on error
            
            final_error_result = { # Ensure all keys are present
                "success": False, "content": None, "parsed_content": None, "tool_calls": None, 
                "usage": None, "error": f"Agent execution failed: {e}",
            }
            log_data_entry["final_manager_result"] = final_error_result # Already serializable
            
            try:
                with open(f"{interaction_log_filename_base}_AGENT_EXEC_ERROR.json", "w") as f_json: json.dump(log_data_entry, f_json, indent=2, default=lambda o: repr(o))
                logger.info(f"LLM Interaction details (AGENT_EXEC_ERROR) logged to {interaction_log_filename_base}_AGENT_EXEC_ERROR.json")
            except Exception as log_e: logger.error(f"Error writing LLM Interaction log file on agent execution error: {log_e}", exc_info=True)

            return final_error_result # Return the consistent error structure
        finally:
            pass # Event loop management removed
