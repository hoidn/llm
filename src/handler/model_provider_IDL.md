// == !! BEGIN IDL TEMPLATE !! ===
module src.handler.model_provider {

    // Abstract interface for all model provider adapters.
    // Defines the common methods required for interacting with different LLM providers.
    interface ProviderAdapter {

        // Sends a message sequence to the LLM provider.
        // Preconditions:
        // - messages is a list of dictionaries, each with 'role' and 'content'.
        // - system_prompt is an optional string.
        // - tools is an optional list of tool specifications in the provider's specific format.
        // Expected JSON format for messages: [ { "role": "user|assistant", "content": "string" }, ... ]
        // Expected JSON format for tools: Provider specific, e.g., [ { "name": "string", "description": "string", "input_schema": { ... } }, ... ]
        // Postconditions:
        // - Returns the raw response from the provider. This can be a simple string or a structured dictionary depending on the provider and whether tools were used/called.
        // Behavior:
        // - Implementations must format the request according to the specific provider's API.
        // - Handles communication with the LLM API endpoint.
        // @raises_error(condition="APIError", description="Raised if communication with the LLM provider API fails.")
        // @raises_error(condition="NotImplementedError", description="Raised if called on the abstract base class.")
        union<string, dict<string, Any>> send_message(
            list<dict<string, string>> messages,
            optional string system_prompt,
            optional list<dict<string, Any>> tools
        );

        // Extracts tool calls and text content from the provider's raw response.
        // Preconditions:
        // - response is the raw response object/string received from `send_message`.
        // Postconditions:
        // - Returns a standardized dictionary containing:
        //   - 'content': The main text response from the model (string).
        //   - 'tool_calls': A list of extracted tool calls, each being a dictionary with 'name' (string) and 'parameters' (dict). Empty list if no calls.
        //   - 'awaiting_tool_response': A boolean indicating if the model stopped specifically to wait for a tool result.
        // Behavior:
        // - Parses the provider-specific response format (e.g., checking for specific keys, stop reasons).
        // - Standardizes the extracted information into the defined dictionary structure.
        // @raises_error(condition="NotImplementedError", description="Raised if called on the abstract base class.")
        // Expected JSON format for return value: { "content": "string", "tool_calls": [ { "name": "string", "parameters": { ... } } ], "awaiting_tool_response": "boolean" }
        dict<string, Any> extract_tool_calls(union<string, dict<string, Any>> response);
    };

    # @depends_on_resource(type="ExternalAPI", purpose="Anthropic Claude LLM API")
    // Concrete implementation for the Anthropic Claude provider.
    // Inherits from ProviderAdapter. (Note: IDL syntax may not support explicit 'extends', documentation indicates inheritance).
    interface ClaudeProvider { // conceptually extends ProviderAdapter

        // Constructor: Initializes the Claude provider.
        // Preconditions:
        // - api_key is an optional string; if None, ANTHROPIC_API_KEY environment variable is used.
        // - model is an optional string specifying the Claude model (defaults to a specific version).
        // Postconditions:
        // - Initializes the Anthropic client if an API key is found.
        // - Sets the target model and default parameters (temperature, max_tokens).
        // - Prints a warning if no API key is available (runs in mock mode).
        void __init__(optional string api_key, optional string model);

        // Sends messages to the Claude API.
        // Implements ProviderAdapter.send_message.
        // Preconditions:
        // - messages is a list of dictionaries (role, content).
        // - system_prompt is an optional string.
        // - tools is an optional list of tool specifications in Anthropic format.
        // - temperature and max_tokens are optional overrides for default parameters.
        // Expected JSON format for messages: [ { "role": "user|assistant", "content": "string" }, ... ]
        // Expected JSON format for tools: [ { "name": "string", "description": "string", "input_schema": { ... } }, ... ]
        // Postconditions:
        // - Returns the Claude API response object (typically a dict with content, tool_calls, stop_reason, etc.) on success.
        // - Returns a mock response string if no API key was provided during initialization.
        // - Returns an error message string if the API call fails.
        // Behavior:
        // - Constructs the API request parameters including model, system prompt, messages, tools, temperature, and max_tokens.
        // - Calls the Anthropic client's `messages.create` method.
        // - Handles potential exceptions during the API call.
        // @raises_error(condition="APIError", description="Handled internally, returns an error string.")
        union<string, dict<string, Any>> send_message(
            list<dict<string, string>> messages,
            optional string system_prompt,
            optional list<dict<string, Any>> tools,
            optional float temperature,
            optional int max_tokens
        );

        // Extracts tool calls and content from a Claude API response.
        // Implements ProviderAdapter.extract_tool_calls.
        // Preconditions:
        // - response is the raw response object/string received from the Claude API via send_message.
        // Postconditions:
        // - Returns a standardized dictionary as defined in ProviderAdapter.extract_tool_calls.
        // Behavior:
        // - Handles both string responses (no tools) and dictionary responses.
        // - Parses Claude's specific structure (content list, tool_calls list, stop_reason).
        // - Extracts text content, tool names, and tool input parameters.
        // - Sets 'awaiting_tool_response' to true if the stop_reason is 'tool_use'.
        // Expected JSON format for return value: { "content": "string", "tool_calls": [ { "name": "string", "parameters": { ... } } ], "awaiting_tool_response": "boolean" }
        dict<string, Any> extract_tool_calls(union<string, dict<string, Any>> response);
    };
};
// == !! END IDL TEMPLATE !! ===
