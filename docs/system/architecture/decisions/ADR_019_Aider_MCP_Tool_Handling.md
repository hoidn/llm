# ADR 19: Aider Integration via MCP and Unified Tool Handling

**Status:** Proposed

**Context:**

*   The system requires integration with Aider for automated code implementation based on LLM-generated plans. The initial design consideration involved a direct "AiderBridge" interacting with the Aider library/CLI.
*   An alternative is leveraging the Model Context Protocol (MCP) by running an external Aider MCP Server and having the application interact with it via an MCP client.
*   The system also needs a robust way to handle different types of tools:
    *   Generic, model-agnostic tools (File I/O, Bash).
    *   Provider-specific tools (like Anthropic's Editor Tools) that should only be available when using compatible models.
*   The existing architecture relies on `pydantic-ai` for LLM interactions, which has built-in support for tools and MCP clients.

**Decision:**

1.  **Aider Integration via MCP:** Aider integration will be implemented using an external **Aider MCP Server** process. The application's `AiderBridge` component will be refactored to act as an **MCP Client**, responsible for communicating with this server.
2.  **Tool Handling Strategy:** Leverage `pydantic-ai`'s tool definition and execution capabilities, managed primarily through the `BaseHandler` and `LLMInteractionManager`. Differentiate between model-agnostic and provider-specific tools via registration strategy.
    *   **Model-Agnostic Tools:** Registered unconditionally with `BaseHandler` and available to any configured `pydantic-ai` Agent.
    *   **Provider-Specific Tools:** Registered conditionally with `BaseHandler` based on the active LLM provider configured in `LLMInteractionManager`. Only available to compatible `pydantic-ai` Agents.

**Rationale:**

*   **Standardization (Aider):** Using MCP aligns Aider integration with a recognized standard, promoting interoperability and decoupling.
*   **Consistency (Aider & Tools):** Leverages `pydantic-ai`'s existing `MCPClient` capabilities, providing a unified approach for interacting with external tool servers (like Aider or `run-python`).
*   **Future Flexibility (Aider):** Makes it easier to integrate other MCP-compliant tools later.
*   **Clear Tool Strategy:** Explicitly defines how to handle generic vs. specialized tools within the `pydantic-ai` framework.

**Consequences:**

*   **Positive:**
    *   Standardizes external tool interactions (Aider, potentially others) via MCP.
    *   Decouples main application from Aider's specific implementation details.
    *   Provides a clear strategy for managing different tool types (agnostic vs. specific).
    *   Enhances long-term flexibility.
*   **Negative:**
    *   Requires running and managing a separate Aider MCP Server process (operational overhead).
    *   Requires refactoring the existing `AiderBridge` and related executors/IDLs.
    *   Adds a layer of network communication (even if local) for Aider calls.
    *   Requires careful implementation of conditional tool registration in the Handler/Application setup.

**Implementation Details:**

*   **Aider MCP Server:** Becomes an operational prerequisite.
*   **`AiderBridge`:** Refactored into an MCP Client using `pydantic-ai`'s `MCPClient` or `mcp.py`. Methods will send requests to the Aider MCP Server URL.
*   **`AiderExecutorFunctions`:** Updated to use the refactored `AiderBridge` (MCP Client).
*   **`BaseHandler`:** Registers `aider:automatic`/`aider:interactive` tools linked to the updated executors. Needs logic for conditional registration of provider-specific tools.
*   **Configuration:** Needs mechanism to configure Aider MCP Server URL and authentication.

**Alternatives Considered:**

*   **Direct AiderBridge Integration:** Simpler initial setup, but less standardized, tighter coupling, less future flexibility.

**Related Documents:**

*   [Pattern:ToolInterface:1.0]
*   ADR 17: Programmatic Task Invocation via Thin Wrappers
*   `docs/librarydocs/pydanticai.md`
*   `docs/librarydocs/MCP_TOOL_GUIDE.md`
*   `docs/librarydocs/aider_MCP_server.md`
