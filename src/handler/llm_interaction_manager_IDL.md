// == !! BEGIN IDL TEMPLATE !! ===
module src.handler.llm_interaction_manager {

    # @depends_on_resource(type="LLMAgentService", purpose="Orchestrating LLM calls via pydantic-ai") // Represents the configured pydantic-ai agent
    interface LLMInteractionManager {

        // Constructor: Initializes the LLM interaction manager.
        // Preconditions:
        // - default_model_identifier is an optional string identifying the pydantic-ai model (e.g., "anthropic:claude-3-5-sonnet-latest").
        // - config is an optional dictionary for configuration settings (e.g., base_system_prompt, API keys for pydantic-ai).
        // Postconditions:
        // - Stores configuration (model ID, base prompt, agent config) internally.
        // - The internal `pydantic-ai Agent` instance (`self.agent`) is initialized to None.
        // - Agent creation is deferred until `initialize_agent` is called.
        // Behavior:
        // - Stores configuration parameters like model identifier and base prompt.
        // - Does **not** create the `pydantic-ai Agent` instance at this time.
        void __init__(
            optional string default_model_identifier, // e.g., "anthropic:claude-3-5-sonnet-latest"
            optional dict<string, Any> config
        );

        // Initializes the underlying pydantic-ai Agent instance.
        // This method MUST be called after the manager is created and all necessary tools
        // have been registered with the handler, before any execution calls are made.
        // Preconditions:
        // - Manager is initialized (`__init__` called).
        // - `tools` is a list representing the tools to be passed to the Agent constructor.
        //   (**Note:** The exact required format - list of callables, list of specs (dicts) -
        //   depends on the `pydantic-ai` library version and needs verification).
        // Postconditions:
        // - The internal `self.agent` attribute holds an initialized `pydantic-ai Agent` instance.
        // - If called again, may log a warning or re-initialize based on implementation.
        // Behavior:
        // - Uses stored configuration (model ID, base prompt, agent config) and the provided `tools` list.
        // - Instantiates the `pydantic-ai Agent`.
        // - Stores the created agent instance in `self.agent`.
        // @raises_error(condition="AgentInitializationError", description="Raised if the pydantic-ai Agent fails to initialize (e.g., invalid config, missing API key).")
        void initialize_agent(list<Any> tools); // Type 'Any' pending verification of required tool format

        // Executes an LLM call with the given prompt and optional overrides.
        // Preconditions:
        // - `initialize_agent` must have been called successfully (`self.agent` is not `None`).
        // - prompt is a non-empty string.
        // - conversation_history is a list of message dictionaries (typically with 'role' and 'content' keys).
        // - Optional overrides for system prompt, tools, and output type can be provided.
        // Postconditions:
        // - Returns a dictionary containing the LLM response, typically structured like a TaskResult.
        // Behavior:
        // - Checks if `self.agent` is initialized, raises error if not.
        // - Delegates to the pydantic-ai Agent's run_sync method.
        // - Handles potential errors during the LLM call.
        // - Formats the result into a TaskResult-like structure.
        // - Passes the `active_tools` list (received from BaseHandler) to `agent.run_sync(tools=...)`.
        // @raises_error(condition="LLMInteractionError", description="If the LLM call fails.")
        // @raises_error(condition="AgentNotInitializedError", description="Raised if called before `initialize_agent`.")
        dict<string, Any> execute_call(
            string prompt,
            list<dict<string, Any>> conversation_history,
            optional string system_prompt_override,
            optional list<function> tools_override, // Keep for now
            optional type output_type_override,
            optional list<dict<string, Any>> active_tools // ADDED PARAMETER (list of tool specs/definitions)
        );

        // Enables or disables the internal debug logging flag.
        // Preconditions:
        // - enabled is a boolean value.
        // Postconditions:
        // - The internal `debug_mode` flag is set to the value of `enabled`.
        // - A message indicating the new debug mode status is logged (if debug was already enabled or just got enabled).
        void set_debug_mode(boolean enabled);

        // Retrieves the configured LLM provider/model identifier string.
        // Preconditions: None.
        // Postconditions:
        // - Returns the identifier string (e.g., "anthropic:claude-3-5-sonnet-latest") stored during initialization.
        // - Returns None if no identifier was configured.
        optional string get_provider_identifier();

        // Internal method to initialize the pydantic-ai Agent.
        // Preconditions:
        // - Configuration parameters (model identifier, base prompt) must be set.
        // Postconditions:
        // - Returns the initialized pydantic-ai Agent instance.
        // - Returns None if initialization fails.
        // Behavior:
        // - Uses the pydantic-ai library to create an Agent instance.
        // - Configures the Agent with the stored model identifier and other settings.
        // - Handles potential errors during Agent initialization.
        // @raises_error(condition="AgentInitializationError", description="If Agent initialization fails.")
        optional object _initialize_pydantic_ai_agent();
    };
};
// == !! END IDL TEMPLATE !! ===
