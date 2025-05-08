# Memory System

## Implementation Notes

### Tool Management Centralization (Phase 7)

The system now centralizes active tool determination in the Application class, with these key features:

1. **Active Tool Definitions**:
   - Tools are stored as specification dictionaries rather than executor functions
   - `BaseHandler` now has an `active_tool_definitions` list to store tool specs
   - Added `set_active_tool_definitions(tool_definitions)` method to replace `set_active_tools`
   - Made `set_active_tools(tool_names)` deprecated with a warning

2. **Centralized Tool Determination**:
   - `Application` class gets provider identifier from handler
   - Added `_determine_active_tools(provider_identifier)` method to select appropriate tools
   - System tools and provider-specific tools are combined based on provider
   - Tool definitions are set on the handler during initialization

3. **LLM Integration**:
   - `LLMInteractionManager.execute_call()` updated to accept `active_tools` parameter
   - Tool definitions are passed directly to the agent's `run_sync(tools=...)` method
   - Tools precedence maintained: explicit `tools_override` > `active_tools` > none

4. **Deferred Agent Initialization**:
   - LLM agent initialization is now deferred until after all tools are registered
   - `LLMInteractionManager` initializes with agent=None and stores tools_for_agent
   - Added `initialize_agent_with_tools(tools)` method to perform deferred initialization
   - `BaseHandler` provides `get_tools_for_agent()` method to collect tools for agent initialization
   - `Application.__init__` calls `_initialize_llm_agent()` after registering all tools
   - Agent initialization triggered only once with the complete set of tools available

This implementation enables better control over which tools are available to each LLM provider while maintaining a consistent interface throughout the application. The deferred agent initialization ensures all tools are available when the agent is created, eliminating the need to reinitialize the agent or to handle complex dynamic tool registration.