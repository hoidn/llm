import logging
import os  # Add os import for environment variable checking
from typing import Any, Dict, List, Optional, Callable, Type, TYPE_CHECKING
import json

# Define module-level logger
logger = logging.getLogger(__name__)

# --- Attempt Top-Level Import for Agent ONLY ---
try:
    # Try importing only Agent from the top level
    from pydantic_ai import Agent
    _PydanticAI_Import_Success = True
    logging.debug("LLMInteractionManager: Top-level pydantic-ai import successful (Agent).")
except ImportError as e:
    # Log the specific import error details
    logging.error(f"LLMInteractionManager: Top-level import of pydantic-ai Agent failed: {e}", exc_info=True)
    # Set Agent to None if import fails
    Agent = None # type: ignore
    _PydanticAI_Import_Success = False
# Define AIResponse as Any since we can't import it reliably
AIResponse = Any # type: ignore
# --- End Import Attempt ---

# Use TYPE_CHECKING for type hints without runtime imports
if TYPE_CHECKING:
    # These are now potentially defined above, but keep for clarity if needed
    # or adjust based on actual usage if AIResponse is only used in hints.
    # If Agent/AIResponse are None above, these hints might cause issues
    # depending on the type checker. Consider conditional hints if necessary.
    pass # Keep the block for potential future use or remove if empty

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
            config: Dictionary for configuration (e.g., API keys, base_system_prompt).
        """
        self.config = config or {}
        self.default_model_identifier = default_model_identifier or self.config.get("default_model_identifier")
        self.base_system_prompt = self.config.get("base_system_prompt", "You are a helpful assistant.")
        self.debug_mode = False
        self.agent: Optional[Any] = self._initialize_pydantic_ai_agent()

        if self.agent:
            logging.info(f"LLMInteractionManager initialized with agent for model: {self.default_model_identifier}")
        else:
            logging.warning("LLMInteractionManager initialized, but pydantic-ai agent creation failed.")

    def _initialize_pydantic_ai_agent(self) -> Optional[Any]:
        """
        Initializes the pydantic-ai Agent instance.
        (Implementation deferred to Phase 1B - Now Implemented)
        """
        logger.debug("Attempting to initialize pydantic-ai Agent...")

        # --- REVERT CHECK ---
        # Remove internal import logic
        # Check module-level Agent variable
        logger.debug(f"Value of module-level Agent before check: {Agent} (Type: {type(Agent)})")
        if not Agent:
            logger.error("Cannot initialize agent: pydantic-ai Agent class is None or unavailable (Import failed).")
            return None
        # --- END REVERT ---

        # Log relevant config values
        logger.debug(f"  Default Model Identifier: {self.default_model_identifier}")
        logger.debug(f"  Base System Prompt: {self.base_system_prompt}")
        logger.debug(f"  Raw Config Passed: {self.config}")

        # Check for common API keys in environment
        openai_key_present = "OPENAI_API_KEY" in os.environ and bool(os.environ["OPENAI_API_KEY"])
        anthropic_key_present = "ANTHROPIC_API_KEY" in os.environ and bool(os.environ["ANTHROPIC_API_KEY"])
        google_key_present = "GOOGLE_API_KEY" in os.environ and bool(os.environ["GOOGLE_API_KEY"])
        logger.debug(f"  Env Keys Check: OpenAI={openai_key_present}, Anthropic={anthropic_key_present}, Google={google_key_present}")

        if not self.default_model_identifier:
            logger.error("Cannot initialize agent: No default_model_identifier provided or found in config.")
            logger.error("Cannot initialize agent: No default_model_identifier provided or found in config.")
            return None

        try:
            # Basic initialization - assumes model identifier string is sufficient
            # More complex setup (API keys, specific model args) might be needed
            # depending on pydantic-ai's requirements and the config structure.
            # API keys might need to be passed explicitly or set as environment variables.
            agent_config = self.config.get("pydantic_ai_agent_config", {}) # Allow passing extra config
            logger.debug(f"  Using Agent Config additions: {agent_config}")

            # Example: Extracting potential API key from config
            # api_key = self.config.get("llm_api_key")
            # if api_key:
            #     agent_config['api_key'] = api_key # Adjust key name based on pydantic-ai model needs

            # Call the constructor using the module-level Agent
            agent = Agent(
                model=self.default_model_identifier,
                system_prompt=self.base_system_prompt, # Base prompt set here
                # tools=... # Tools are typically passed per-call or registered differently
                **agent_config # Pass any additional config
            )
            logger.info(f"pydantic-ai Agent initialized successfully for model: {self.default_model_identifier}")
            return agent
        except Exception as e:
            # Log the full exception details
            logger.error(f"Failed to initialize pydantic-ai Agent for model '{self.default_model_identifier}': {e}", exc_info=True)
            return None

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

    def execute_call(
        self,
        prompt: str,
        conversation_history: List[Dict[str, Any]], # Pass history in
        system_prompt_override: Optional[str] = None,
        tools_override: Optional[List[Callable]] = None, # Or tool specs? Check pydantic-ai docs
        output_type_override: Optional[Type] = None,
    ) -> Dict[str, Any]:
        """
        Executes a call to the configured pydantic-ai agent.

        Args:
            prompt: The user's input prompt for the current turn.
            conversation_history: The history of the conversation up to this point.
            system_prompt_override: An optional system prompt to use for this specific call.
            tools_override: Optional list of tools (functions or specs) for this call.
            output_type_override: Optional Pydantic model for structured output.

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
        logger = logging.getLogger(__name__) # Use specific logger

        if not self.agent:
            logger.error("Cannot execute LLM call: Agent is not initialized.")
            return {"success": False, "error": "LLM Agent not initialized."}

        try:
            # Determine the system prompt to use
            current_system_prompt = system_prompt_override if system_prompt_override is not None else self.base_system_prompt

            # Prepare keyword arguments separately
            run_kwargs = {
                "message_history": conversation_history, # Pass history here
                "system_prompt": current_system_prompt,
            }

            # Log the full prompt and context to a file for debugging
            try:
                log_data = {
                    "system_prompt": current_system_prompt,
                    "conversation_history": conversation_history,
                    "prompt": prompt
                }
                with open("llm_full_prompt.log", "w") as _f:
                    _f.write(json.dumps(log_data, indent=2))
                logger.info("LLM full prompt written to llm_full_prompt.log")
            except Exception as _e:
                logger.error(f"Failed to write full LLM prompt to file: {_e}")
            if tools_override:
                run_kwargs["tools"] = tools_override
                logging.debug(f"Executing agent call with {len(tools_override)} tools.")
            if output_type_override:
                run_kwargs["output_type"] = output_type_override
                logging.debug(f"Executing agent call with output_type: {output_type_override.__name__}")

            # Log the arguments being passed
            logger.debug(f"LLMInteractionManager: Calling agent.run_sync with prompt='{prompt[:100]}...' and kwargs={run_kwargs}")

            if self.debug_mode:
                # Redundant logging now, keep or remove
                logger.debug(f"Calling agent.run_sync with prompt='{prompt[:100]}...' and kwargs={run_kwargs}")

            # Call the agent with prompt as positional arg, others as kwargs
            # Use Optional[Any] for the type hint as AIResponse import failed
            response: Optional[Any] = self.agent.run_sync(prompt, **run_kwargs)

            if self.debug_mode:
                logging.debug(f"Agent response received: {response}")

            # Process the response
            # The exact structure of 'response' depends on pydantic-ai version and call type
            # Adapt the extraction logic based on the actual AIResponse object structure
            content = getattr(response, 'output', None) # Common attribute for text output
            tool_calls = getattr(response, 'tool_calls', []) # Check for tool calls
            usage = getattr(response, 'usage', {}) # Check for usage data

            # Ensure content is stringified if it's a structured output model
            if content is not None and not isinstance(content, str):
                 # Attempt to convert Pydantic models or other objects to string/dict
                if hasattr(content, 'model_dump_json'):
                    content_str = content.model_dump_json()
                elif hasattr(content, 'model_dump'):
                     content_str = str(content.model_dump()) # Or format as needed
                else:
                    content_str = str(content)
            else:
                content_str = content


            return {
                "success": True,
                "content": content_str,
                "tool_calls": tool_calls,
                "usage": usage,
                "error": None,
            }

        except Exception as e:
            logging.error(f"Error during pydantic-ai agent execution: {e}", exc_info=True)
            return {
                "success": False,
                "content": None,
                "tool_calls": None,
                "usage": None,
                "error": f"Agent execution failed: {e}",
            }
