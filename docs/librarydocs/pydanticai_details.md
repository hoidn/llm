# Pydantic AI Tool System Documentation

This document provides detailed information about the tool system in Pydantic AI, including expected formats, initialization patterns, and recommended practices.

## Core Tool Format & Initialization

### Agent(tools=...) Parameter Format

The `tools` parameter for `pydantic_ai.Agent` constructor accepts several formats:

1. **List of functions (`list[Callable]`)**: You can pass regular Python functions or async functions.
   ```python
   def my_tool(a: int, b: str) -> str:
       return f"{a} {b}"
   
   agent = Agent(model='...',  tools=[my_tool])
   ```

2. **List of `Tool` objects (`list[Tool]`)**: More detailed way to define tools with additional options.
   ```python
   tool = Tool(my_tool, name="custom_name", description="Custom description")
   agent = Agent(model='...', tools=[tool])
   ```

3. **The expected format does NOT depend on the specific LLM provider** - pydantic-ai handles conversion to provider-specific formats.

### Automatic Schema/Description Extraction

Yes, pydantic-ai automatically inspects function signatures and docstrings to generate schemas, regardless of whether you use the decorator or pass functions directly:

- Type hints are used to generate JSON schema parameters
- Function docstrings are parsed to extract descriptions (including parameter descriptions)
- Pydantic models in arguments are properly converted to their corresponding schema
- This works with both `@agent.tool` decorator and when passing functions to the `tools` parameter

### Specification Schema

The tool specification follows a consistent schema internally represented by the `ToolDefinition` class:
```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters_json_schema: ObjectJsonSchema  # dict[str, Any] with JSON schema
    outer_typed_dict_key: str | None = None
    strict: bool | None = None
```

The schema is automatically generated from the function's type hints and docstring, and pydantic-ai handles converting this to provider-specific formats when communicating with different LLMs.

## Dynamic Tool Handling

### Per-Run Tool Specification

Yes, tools can be provided dynamically per-call using the `tools` parameter:
```python
# During initialization
agent = Agent(model='...', tools=[tool1, tool2])

# During a specific run
result = await agent.run(prompt="...", tools=[tool3, tool4])
```

### Per-Run vs. Init Tools

The documentation and code suggest that tools passed during a run are used *in addition to* tools provided during initialization, not replacing them. This allows for a flexible combination of default tools plus context-specific ones.

### Recommended Pattern for Dynamic Loading

For scenarios where tools might change between calls:

1. **For mostly static tools with occasional additions**: Initialize the agent with common tools, then pass additional tools during `run()` or `run_sync()` calls.

2. **For significantly different tool sets**: Create separate agent instances for different contexts, each with its own set of tools.

3. **For tool filtering based on context**: Use the `prepare` function capability to dynamically include/exclude tools based on context:
   ```python
   async def only_include_if_condition(ctx: RunContext, tool_def: ToolDefinition) -> ToolDefinition | None:
       if condition_met(ctx.deps):  # Check condition using dependencies
           return tool_def  # Include tool
       return None  # Don't include tool
   
   my_tool = Tool(function, prepare=only_include_if_condition)
   ```

## Tool Definition & Registration

### Manual Registration Equivalence

To achieve the equivalent of the `@agent.tool` decorator when registering tools manually, use the `Tool` class:

```python
from pydantic_ai import Tool, RunContext
from pydantic import BaseModel

class QueryParams(BaseModel):
    query: str
    limit: int = 10

def search_database(ctx: RunContext[Dependencies], params: QueryParams) -> list:
    # Implementation
    return []

# Register manually - equivalent to @agent.tool
search_tool = Tool(
    search_database,
    takes_ctx=True,  # Explicitly indicate it takes context
    max_retries=3,
    name="search_database",  # Optional, defaults to function name
    description="Search the database with parameters",  # Optional, defaults to docstring
    docstring_format='google',  # Optional, defaults to 'auto'
    require_parameter_descriptions=False  # Optional
)

# Use in agent
agent = Agent(model='...', tools=[search_tool])
```

The schema generation for Pydantic models in parameters will work automatically just like with the decorator.

## Error Handling

If invalid tool formats are passed:

1. **During agent initialization**: Validation happens immediately. If tools are in invalid formats or have invalid specifications, errors will be raised when the agent is initialized.

2. **During run time**: If incorrect tools are passed during a `run()` call, validation will happen before the agent starts processing the user's message.

3. **During tool execution**: If the LLM attempts to call a tool with invalid parameters, pydantic-ai will validate these parameters against the schema, and if validation fails, it generates a retry prompt to the LLM, allowing it to correct the parameters. The number of retries is controlled by the `retries` parameter.