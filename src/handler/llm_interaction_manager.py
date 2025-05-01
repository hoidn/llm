import logging
import os  # Add os import for environment variable checking
from typing import Any, Dict, List, Optional, Callable, Type, TYPE_CHECKING

# Use TYPE_CHECKING for type hints without runtime imports
if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.models import AIResponse

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
        logger = logging.getLogger(__name__) # Use specific logger
        logger.debug("Attempting to initialize pydantic-ai Agent...")

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
            return None

        try:
            # Import Agent right before use
            try:
                from pydantic_ai import Agent
                logger.debug("Successfully imported pydantic_ai.Agent inside _initialize_pydantic_ai_agent.")
            except ImportError as import_err:
                logger.error(f"Failed to import pydantic_ai within _initialize_pydantic_ai_agent: {import_err}", exc_info=True)
                return None
                
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

            # Call the constructor using the locally imported Agent
            agent = Agent(
                model=self.default_model_identifier,
                system_prompt=self.base_system_prompt, # Base prompt set here
                # tools=... # Tools are typically passed per-call or registered differently
                **agent_config # Pass any additional config
            )
            logging.info(f"pydantic-ai Agent initialized successfully for model: {self.default_model_identifier}")
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
        # Import needed types here
        try:
            from pydantic_ai.models import AIResponse
        except ImportError:
            logging.error("Failed to import pydantic_ai response type in execute_call.")
            return {"success": False, "error": "Pydantic-AI type import failed."}
            
        if not self.agent:
            logging.error("Cannot execute LLM call: Agent is not initialized.")
            return {"success": False, "error": "LLM Agent not initialized."}

        try:
            # Prepare messages for the agent
            messages = conversation_history + [{"role": "user", "content": prompt}]

            # Determine the system prompt to use
            current_system_prompt = system_prompt_override if system_prompt_override is not None else self.base_system_prompt

            # Prepare arguments for run_sync
            agent_args = {
                "messages": messages,
                "system_prompt": current_system_prompt,
            }
            if tools_override:
                # Ensure tools_override format matches pydantic-ai expectations
                # It might expect functions, Pydantic models, or specific tool objects
                agent_args["tools"] = tools_override
                logging.debug(f"Executing agent call with {len(tools_override)} tools.")
            if output_type_override:
                agent_args["output_type"] = output_type_override
                logging.debug(f"Executing agent call with output_type: {output_type_override.__name__}")

            if self.debug_mode:
                logging.debug(f"Calling agent.run_sync with args: {agent_args}")

            # Call the agent (synchronously for now)
            response = self.agent.run_sync(**agent_args)

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
