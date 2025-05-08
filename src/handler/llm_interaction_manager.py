import json
import logging
import os  # Add os import for environment variable checking
import asyncio         # NEW – we’ll manage a dedicated event-loop
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Type, Union

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


    def execute_call(
        self,
        prompt: str,
        conversation_history: List[Any],  # Updated to accept ModelMessage objects
        system_prompt_override: Optional[str] = None,
        tools_override: Optional[List[Callable]] = None,  # Executors
        output_type_override: Optional[Type] = None,
        active_tools: Optional[List[Dict[str, Any]]] = None,  # Tool definitions
        model_override: Optional[str] = None, # ADDED PARAMETER
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

        # --- START: Model Override Logic ---
        target_agent = self.agent # Start with the default agent
        target_model_id_for_log = self.default_model_identifier

        if model_override and model_override != self.default_model_identifier:
            logger.info(f"Model override requested: '{model_override}'")
            target_model_id_for_log = model_override # Update for logging
            try:
                # Look up configuration for the override model
                # Assumes config structure: self.config['llm_providers'][model_override]
                override_provider_config = self.config.get('llm_providers', {}).get(model_override)
                if override_provider_config is None: # Check explicitly for None
                    error_msg = f"Configuration not found for model override: {model_override}"
                    logger.error(error_msg)
                    error_details = TaskFailureError(type="TASK_FAILURE", reason="configuration_error", message=error_msg)
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

        # Ensure target_agent is valid before proceeding
        if not target_agent:
             error_msg = "LLM Agent not available (Initialization likely failed or default agent missing)."
             logger.error(f"Cannot execute call: {error_msg}")
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

        # Cache the previously-active loop (if any) *once* so we can restore it later
        _prev_loop: Optional[asyncio.AbstractEventLoop] = None
        try:
            try:
                _prev_loop = asyncio.get_event_loop()
            except RuntimeError:
                _prev_loop = None  # No running loop in this thread – that’s fine

            # Make our dedicated loop the current one for the upcoming run_sync
            asyncio.set_event_loop(self._event_loop)

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
                    log_data = {
                        "system_prompt": current_system_prompt,
                        "conversation_history": [msg.model_dump(exclude_none=True, round_trip=True) if hasattr(msg, 'model_dump') else str(msg) for msg in conversation_history],
                        "prompt": prompt,
                        "model_used": target_model_id_for_log, # Log which model was used
                    }
                    with open("llm_full_prompt.log", "w") as _f:
                        _f.write(json.dumps(log_data, indent=2))
                    logger.info("LLM full prompt written to llm_full_prompt.log")
                except Exception as _e:
                    logger.error(f"Failed to write full LLM prompt to file: {_e}")

                # Handle tools_override and active_tools
                # --- START FIX for tools precedence ---
                if tools_override:
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

                try:
                    # Normal path – we are NOT inside a loop
                    response = target_agent.run_sync(prompt, **run_kwargs)
                except RuntimeError as exc:
                    if "event loop is already running" not in str(exc):
                        raise
                    # We *are* inside a loop → schedule coroutine on that loop
                    loop = asyncio.get_running_loop()
                    coro = target_agent.run(prompt, **run_kwargs)
                    response = loop.run_until_complete(asyncio.ensure_future(coro))

                if self.debug_mode:
                    logging.debug(f"Agent response received: {response}")

                # Process the response
                # The exact structure of 'response' depends on pydantic-ai version and call type
                # Adapt the extraction logic based on the actual AIResponse object structure
                content = getattr(
                    response, "output", None
                )  # Common attribute for text output
                tool_calls = getattr(response, "tool_calls", [])  # Check for tool calls
                
                # --- START: Process usage data ---
                raw_usage = getattr(response, "usage", None)
                actual_usage_data: Optional[Dict[str, Any]] = None

                if raw_usage is not None:
                    if callable(raw_usage):
                        try:
                            actual_usage_data = raw_usage() 
                            logger.debug(f"Called response.usage() method, got: {actual_usage_data}")
                        except Exception as e_usage_call:
                            logger.warning(f"Could not call response.usage() method: {e_usage_call}. Storing as string.")
                            actual_usage_data = {"raw_usage_representation": str(raw_usage)}
                    elif isinstance(raw_usage, dict):
                        actual_usage_data = raw_usage
                        logger.debug(f"response.usage was a dict: {actual_usage_data}")
                    else:
                        logger.warning(f"response.usage is of unexpected type: {type(raw_usage)}. Storing as string.")
                        actual_usage_data = {"raw_usage_representation": str(raw_usage)}
                else:
                    logger.debug("No 'usage' attribute found in pydantic-ai response.")
                # --- END: Process usage data ---
                
                usage = actual_usage_data # Use the processed data

                # Initialize parsed_content to None
                parsed_content = None

                # If we have a pydantic model output, use it directly as parsed_content
                if content is not None and hasattr(content, "model_dump"):
                    parsed_content = (
                        content  # Store the full Pydantic model for structured output
                    )

                # Ensure content is stringified if it's a structured output model
                if content is not None and not isinstance(content, str):
                    # Attempt to convert Pydantic models or other objects to string/dict
                    if hasattr(content, "model_dump_json"):
                        content_str = content.model_dump_json()
                    elif hasattr(content, "model_dump"):
                        content_str = str(content.model_dump())  # Or format as needed
                    else:
                        content_str = str(content)
                else:
                    content_str = content

                return {
                    "success": True,
                    "content": content_str,
                    "parsed_content": parsed_content,  # Include the parsed Pydantic model if available
                    "tool_calls": tool_calls,
                    "usage": usage,
                    "error": None,
                }
            except Exception as e:
                logging.error(
                    f"Error during pydantic-ai agent execution: {e}", exc_info=True
                )
                return {
                    "success": False,
                    "content": None,
                    "tool_calls": None,
                    "usage": None,
                    "error": f"Agent execution failed: {e}",
                }
        finally:
            # Always restore whatever loop was active before we hijacked it.
            asyncio.set_event_loop(_prev_loop)
