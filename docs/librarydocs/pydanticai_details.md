# Pydantic AI Tool System Documentation

This document provides detailed information about the tool system in Pydantic AI, including expected formats, initialization patterns, and recommended practices.

## Core Tool Format & Initialization

### Agent(tools=...) Parameter Format

The `tools` parameter for the `pydantic_ai.Agent` constructor accepts:

1.  **List of functions/methods (`Sequence[Callable]`)**: You can pass regular Python functions or async functions directly. `pydantic-ai` will automatically introspect them.
    ```python
    def my_tool(a: int, b: str) -> str:
        """My tool description."""
        return f"{a} {b}"

    agent = Agent(model='...', tools=[my_tool])
    ```

2.  **List of `Tool` objects (`Sequence[Tool]`)**: Use the `pydantic_ai.tools.Tool` class to wrap callables when you need more control (e.g., overriding name/description, using `prepare` function).
    ```python
    from pydantic_ai import Tool

    tool_obj = Tool(my_tool, name="custom_name", description="Custom description")
    agent = Agent(model='...', tools=[tool_obj])
    ```

3.  **Mixed List**: A sequence containing both callables and `Tool` objects.

4.  **Not Accepted**: It does **not** directly accept a `list[dict]` containing tool specifications in the constructor.

### Automatic Schema/Description Extraction

Yes, `pydantic-ai` **automatically** inspects function signatures and docstrings to generate schemas and descriptions when you pass callables directly *or* when you use the `Tool` class without explicitly providing `name` or `description`.

-   Type hints (including Pydantic models, `Optional`, `Union`, etc.) are used for the JSON schema.
-   Docstrings are parsed (Google, Numpy, Sphinx, Auto) for the main description and parameter descriptions. Ensure your docstrings are well-formatted.
-   The optional `RunContext` parameter is correctly handled and excluded from the LLM schema.

### Specification Schema

Internally, `pydantic-ai` uses a standardized `ToolDefinition` dataclass. This internal representation is then translated by the specific `Model` class (e.g., `OpenAIModel`) into the format required by the target LLM provider's API. You generally don't interact with `ToolDefinition` directly unless customizing schema generation.

## Dynamic Tool Handling

### Per-Run Tool Specification

The `agent.run()`, `agent.run_sync()`, and `agent.iter()` methods **do not accept a `tools` parameter**. You cannot override or add tools dynamically for a specific run using a parameter to these methods.

### Per-Run vs. Init Tools

Tools are defined at the `Agent` initialization level. The set of tools available during a run is determined by the tools provided during `Agent` creation.

### Recommended Pattern for Dynamic Loading/Availability

If you need tools to be dynamically available or modified based on runtime context (e.g., user permissions, current state):

1.  **Use `Tool.prepare`:** Register your tool using the `pydantic_ai.Tool` class and provide a `prepare` async function. This function receives the `RunContext` and the default `ToolDefinition` and can return `None` (to exclude the tool for that run) or a modified `ToolDefinition`.
    ```python
    from pydantic_ai import Tool, RunContext
    from pydantic_ai.tools import ToolDefinition # Import needed

    async def prepare_admin_tool(ctx: RunContext[MyDeps], tool_def: ToolDefinition) -> ToolDefinition | None:
        if ctx.deps.is_admin: # Check context from dependencies
            return tool_def # Include tool for admins
        return None # Exclude tool for non-admins

    admin_callable = ... # Your tool function
    admin_tool = Tool(admin_callable, prepare=prepare_admin_tool)
    agent = Agent(model='...', tools=[admin_tool])
    ```

2.  **Separate Agent Instances:** For fundamentally different toolsets, consider creating and using separate `Agent` instances configured for specific contexts.

## Tool Definition & Registration

### Manual Registration Equivalence

To achieve the equivalent of the `@agent.tool` decorator when registering tools manually for the `Agent` constructor, you primarily pass the callable directly:

```python
# Tool function
def search_database(ctx: RunContext[Dependencies], query: str) -> list:
    """Searches the database."""
    # Implementation
    return []

# Pass callable directly to Agent constructor
agent = Agent(model='...', tools=[search_database])
# pydantic-ai handles wrapping in Tool and introspection automatically.
```

If you need to override the name/description or use advanced features (like prepare), wrap the callable with the Tool class:
```python
from pydantic_ai import Tool

search_tool_obj = Tool(
    search_database,
    name="database_query_tool", # Override name
    description="Performs a query against the main product database." # Override description
)
agent = Agent(model='...', tools=[search_tool_obj])
```

## Error Handling

If invalid tool formats are passed:

1. **During agent initialization**: Validation happens immediately. If tools are in invalid formats or have invalid specifications, errors will be raised when the agent is initialized.

2. **During run time**: If incorrect tools are passed during a `run()` call, validation will happen before the agent starts processing the user's message.

3. **During tool execution**: If the LLM attempts to call a tool with invalid parameters, pydantic-ai will validate these parameters against the schema, and if validation fails, it generates a retry prompt to the LLM, allowing it to correct the parameters. The number of retries is controlled by the `retries` parameter.
