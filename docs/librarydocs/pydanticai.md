# PydanticAI API Guide

This guide provides a comprehensive overview of the PydanticAI API, explaining core concepts, components, and usage patterns.

## Core Components

### Agent

The `Agent` class is the central component for LLM interactions.

```python
from pydantic_ai import Agent

# Basic instantiation
agent = Agent('openai:gpt-4o')

# With system prompt
agent = Agent(
    'anthropic:claude-3-5-sonnet-latest',
    system_prompt='Be helpful and concise.'
)

# With typed output
agent = Agent(
    'gemini:gemini-1.5-flash',
    output_type=MyOutputModel
)

# With dependency injection
agent = Agent(
    'openai:gpt-4o',
    deps_type=MyDependencies
)
```

#### Key Methods

- `run(prompt, deps=None)`: Run the agent asynchronously
- `run_sync(prompt, deps=None)`: Run the agent synchronously 
- `run_stream(prompt, deps=None)`: Run the agent with streaming output

### Models

PydanticAI supports multiple LLM providers through a unified interface.

```python
# Select models by provider:model format
agent = Agent('openai:gpt-4o')  # OpenAI
agent = Agent('anthropic:claude-3-5-sonnet-latest')  # Anthropic
agent = Agent('google-gla:gemini-1.5-flash')  # Google
agent = Agent('mistral:mistral-large-latest')  # Mistral
agent = Agent('groq:llama3-70b-8192')  # Groq
agent = Agent('cohere:command-r-plus')  # Cohere
agent = Agent('bedrock:anthropic.claude-3-5-sonnet-20240620-v1:0')  # AWS Bedrock
```

### Tools

Tools are functions the agent can call during its execution.

```python
@agent.tool
async def get_weather(ctx: RunContext[Deps], location: str) -> dict:
    """Get the current weather for a location."""
    # Implementation
    return {"temperature": 21, "condition": "Sunny"}
```

### System Prompts

System prompts can be static or dynamic.

```python
# Static system prompt
agent = Agent(
    'openai:gpt-4o',
    system_prompt='You are a helpful assistant.'
)

# Dynamic system prompt
@agent.system_prompt
async def personalized_prompt(ctx: RunContext[UserDeps]) -> str:
    return f"You are helping {ctx.deps.user_name}. Be friendly and helpful."
```

### Dependency Injection

PydanticAI provides a robust dependency injection system for tools and system prompts.

```python
from dataclasses import dataclass
from httpx import AsyncClient

@dataclass
class Dependencies:
    client: AsyncClient
    api_key: str
    user_id: int

agent = Agent('openai:gpt-4o', deps_type=Dependencies)

# Provide dependencies when running
result = await agent.run(
    "What's the weather?", 
    deps=Dependencies(
        client=AsyncClient(),
        api_key="your-api-key",
        user_id=123
    )
)
```

### Structured Output

Define output structures using Pydantic models.

```python
from pydantic import BaseModel, Field

class WeatherReport(BaseModel):
    location: str
    temperature: float = Field(description="Temperature in Celsius")
    condition: str
    humidity: float = Field(description="Humidity percentage", ge=0, le=100)

agent = Agent('openai:gpt-4o', output_type=WeatherReport)

result = await agent.run("What's the weather in London?")
print(f"Temperature: {result.output.temperature}°C")
```

### Message History

Access and manipulate conversation history.

```python
from pydantic_ai.messages import UserMessage, ModelMessage

# Add messages explicitly
history = [
    UserMessage(content="Hello"),
    ModelMessage(content="Hi there! How can I help you?")
]

result = await agent.run("What did I say first?", history=history)
```

## Manually Constructing Message History

While `pydantic-ai` handles history automatically when passing results from previous runs, you may sometimes need to construct message objects manually (e.g., when building history from scratch or within wrapper classes like `BaseHandler`).

**Important:** Do **not** attempt to instantiate the `ModelMessage` union type directly (e.g., `ModelMessage(...)`). You must use the specific message classes like `UserMessage` or `ModelResponse`.

**Required Imports:**

```python
from pydantic_ai.messages import UserMessage, ModelResponse, TextPart
```

**Example:**

```python
from pydantic_ai.messages import UserMessage, ModelResponse, TextPart

# Creating a user message (simple string content)
user_msg_obj = UserMessage(content="Tell me about Pydantic.")

# Creating an assistant message (simple text response)
# Note: Content MUST be wrapped in a TextPart within the 'parts' list.
assistant_content_str = "Pydantic is a data validation library..."
assistant_msg_obj = ModelResponse(parts=[TextPart(content=assistant_content_str)])

# Creating history list for agent.run_sync or agent.run
manual_history = [
    # UserMessage(content="Previous user turn..."), # If needed
    # ModelResponse(parts=[TextPart(content="Previous assistant turn...")]), # If needed
]

# You can then pass this list to the agent:
# result = agent.run_sync("Follow up question", message_history=manual_history)
```

*   **Key Points:**
    *   Import `UserMessage`, `ModelResponse`, and `TextPart` directly.
    *   Use `UserMessage(content="...")` for user turns.
    *   Use `ModelResponse(parts=[TextPart(content="...")])` for assistant turns containing simple text.
    *   Refer to `pydantic-ai` documentation for handling other content types (e.g., tool calls) within `ModelResponse.parts`.

## Agent.run_sync

`Agent.run_sync` is a synchronous method for running an agent with a user prompt. This method provides a synchronous interface to the underlying asynchronous Agent architecture, returning a complete response.

### Signature

```python
def run_sync(
    self,
    user_prompt: str | Sequence[UserContent] | None = None,
    *,
    output_type: type[RunOutputDataT] | ToolOutput[RunOutputDataT] | None = None,
    message_history: list[ModelMessage] | None = None,
    model: Model | KnownModelName | str | None = None,
    deps: AgentDepsT = None,
    model_settings: ModelSettings | None = None,
    usage_limits: UsageLimits | None = None,
    usage: Usage | None = None,
    infer_name: bool = True,
) -> AgentRunResult[Any]
```

### Description

This method executes the agent by wrapping the async `run()` method with `loop.run_until_complete()`. It runs the agent synchronously with the provided user prompt, model, and other parameters, and returns a result containing the model's final output.

You should use this method when:
- You need a synchronous interface to the agent
- You're working in a non-async context
- You need a simple way to get a complete result from the agent

### Parameters

- `user_prompt`: User input to start/continue the conversation. Can be a string or sequence of UserContent objects.
- `output_type`: Optional custom output type to use for this run. May only be used if the agent has no output validators.
- `message_history`: Optional list of ModelMessage objects representing previous conversation history.
- `model`: Optional model to use for this run. Required if no model was set when creating the agent.
- `deps`: Optional dependencies to use for this run.
- `model_settings`: Optional settings to use for this model's request.
- `usage_limits`: Optional limits on model request count or token usage.
- `usage`: Optional usage to start with. Useful for resuming a conversation or agents used in tools.
- `infer_name`: Whether to try to infer the agent name from the call frame if it's not set.

### Returns

- `AgentRunResult[OutputDataT]`: The result of the run, containing the model's output and metadata.

### Examples

**Basic usage:**

```python
from pydantic_ai import Agent

agent = Agent('openai:gpt-4o')
result = agent.run_sync('What is the capital of France?')
print(result.output)
#> Paris
```

**With custom output type:**

```python
from pydantic import BaseModel
from pydantic_ai import Agent

class Location(BaseModel):
    city: str
    country: str

agent = Agent('openai:gpt-4o')
result = agent.run_sync(
    'What is the capital of France?',
    output_type=Location
)
print(result.output)
#> Location(city='Paris', country='France')
```

**With message history:**

```python
from pydantic_ai import Agent

agent = Agent('openai:gpt-4o')

# First run
result1 = agent.run_sync('Who was Albert Einstein?')
print(result1.output)
#> Albert Einstein was a German-born theoretical physicist...

# Second run, continuing the conversation
result2 = agent.run_sync(
    'What was his most famous equation?',
    message_history=result1.new_messages()
)
print(result2.output)
#> E = mc²
```

**With model settings and usage limits:**

```python
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

agent = Agent('openai:gpt-4o')
result = agent.run_sync(
    'Summarize the history of France in one paragraph.',
    model_settings={'temperature': 0.2, 'max_tokens': 100},
    usage_limits=UsageLimits(response_tokens_limit=120)
)
print(result.output)
```

### Notes

- This method cannot be used inside async code or if there's an active event loop.
- If you need to stream the response or access individual steps of the execution, use `agent.run_stream()` or `agent.iter()` instead.
- The method will infer the agent name from the call frame if `infer_name=True` and `name` wasn't set when creating the agent.

## Advanced Features

### Streaming

Stream agent outputs in real-time.

```python
async for chunk in agent.run_stream("Tell me a story"):
    print(chunk.output, end="", flush=True)
```

### Multi-Modal Content

Handle images and other media.

```python
from pydantic_ai.messages import UserMessage, Image

# Send image to model
image = Image(url="https://example.com/cat.jpg")
message = UserMessage(content=[
    "What's in this image?",
    image
])

result = await agent.run(message)
```

### Error Handling

Handle errors in tool execution.

```python
@agent.tool
async def risky_operation(ctx: RunContext) -> str:
    try:
        # Some operation that might fail
        return "Success"
    except Exception as e:
        # Report error to the model
        raise ToolError(f"Operation failed: {str(e)}")
```

### Agent Graphs

Define complex agent workflows using Pydantic Graph.

```python
from pydantic_graph import Graph
from pydantic_ai import Agent

# Define node types
class WeatherNode(BaseNode):
    location: str
    
    async def run(self, ctx: GraphContext) -> WeatherResult:
        # Implementation
        return WeatherResult(temperature=21)

# Define graph
class MyGraph(Graph):
    start: WeatherNode
    
    class Config:
        starting_node = "start"

# Run graph
graph = MyGraph(start=WeatherNode(location="London"))
result = await graph.run()
```

## Settings and Configuration

Configure PydanticAI with environment variables or programmatically.

```python
from pydantic_ai.settings import Settings

# Configure programmatically
settings = Settings(
    openai_api_key="your-api-key",
    anthropic_api_key="your-api-key",
)

# Or use environment variables
# PYDANTIC_AI_OPENAI_API_KEY=your-api-key
# PYDANTIC_AI_ANTHROPIC_API_KEY=your-api-key
```

## Testing

Test agents with test models.

```python
from pydantic_ai.models import TestModel

# Create test model with predefined responses
test_model = TestModel(responses=[
    "This is a test response",
    "This is another test response",
])

# Use test model in agent
agent = Agent(test_model)

# Run tests
result = await agent.run("Test query")
assert result.output == "This is a test response"
```

## Common Patterns

### Validation and Retry

PydanticAI automatically retries failed validations.

```python
class StrictOutput(BaseModel):
    answer: str = Field(min_length=10, max_length=100)
    confidence: float = Field(ge=0.0, le=1.0)

agent = Agent('openai:gpt-4o', output_type=StrictOutput)
```

### Composing Agents

Build complex applications by composing multiple agents.

```python
research_agent = Agent('anthropic:claude-3-5-sonnet-latest')
summarization_agent = Agent('openai:gpt-4o')

async def process_query(query: str) -> str:
    # Research with first agent
    research_result = await research_agent.run(f"Research: {query}")
    
    # Summarize with second agent
    summary_result = await summarization_agent.run(
        f"Summarize this research: {research_result.output}"
    )
    
    return summary_result.output
```

### Tool Function Return Types

Tools can return various types of data.

```python
# Return dictionary
@agent.tool
async def get_data(ctx: RunContext) -> dict:
    return {"key": "value"}

# Return Pydantic model
@agent.tool
async def get_user(ctx: RunContext, user_id: int) -> User:
    return User(id=user_id, name="John")

# Return image
from pydantic_ai.messages import Image
@agent.tool
async def generate_image(ctx: RunContext, prompt: str) -> Image:
    return Image(url="https://example.com/generated.jpg")
```

## Best Practices

1. **Type Annotations**: Always use type annotations for better IDE support and runtime validation.

2. **Docstrings**: Add detailed docstrings to tools to help the LLM understand their purpose.

3. **Error Handling**: Use appropriate error handling in tools to provide meaningful feedback.

4. **Dependency Management**: Use dependency injection for external resources to simplify testing.

5. **Output Validation**: Define structured outputs with validation rules to ensure consistent responses.

6. **Streaming**: Use streaming for long-running operations to provide real-time feedback.

7. **Testing**: Create test models to verify agent behavior deterministically.

## Common Tools

PydanticAI includes common tools for web search, RAG, and other frequent use cases.

```python
from pydantic_ai.common_tools.duckduckgo import add_duckduckgo_search

# Add DuckDuckGo search tool to your agent
add_duckduckgo_search(agent)

# Use in a query
result = await agent.run("What is the latest news about Pydantic?")
```

## Logging and Monitoring

Integrate with Pydantic Logfire for comprehensive monitoring.

```python
import logfire
from pydantic_ai import Agent

# Initialize logfire
logfire.configure()

# Create agent - all interactions will be logged
agent = Agent('openai:gpt-4o')
```

## Error Handling and Debugging

Handle common errors and debug agent interactions.

```python
try:
    result = await agent.run("Query")
except Exception as e:
    print(f"Error: {e}")
    
# Access full conversation history
for message in result.history:
    print(f"{message.role}: {message.content}")
```
Okay, let's analyze the provided `pydantic-ai` source code snippets to answer the questions about the `tools` parameter format.

**Analysis:**

1.  **`Agent.__init__` (`pydantic_ai/agent.py`):**
    *   The constructor accepts `tools: Sequence[Tool[AgentDepsT] | ToolFuncEither[AgentDepsT, ...]] = ()`.
    *   It iterates through this sequence. If an item is *not* already a `Tool` instance, it wraps it using `Tool(tool)`.
    *   It then calls `self._register_tool(tool_instance)` for each processed tool.
    *   This confirms `Agent.__init__` accepts a sequence containing either `Tool` instances or raw callables (`ToolFuncEither`).

2.  **`Tool.__init__` (`pydantic_ai/tools.py`):**
    *   Accepts `function: ToolFuncEither[AgentDepsT]`.
    *   Accepts optional explicit `name`, `description`, `max_retries`, `prepare`, `docstring_format`, `require_parameter_descriptions`, `schema_generator`, `strict`.
    *   Crucially, it calls `f = _pydantic.function_schema(...)` using the provided `function`.
    *   It uses the *explicitly passed* `name` and `description` if provided, otherwise it falls back to the values inferred by `function_schema` (`f['description']`, `function.__name__`).

3.  **`_pydantic.function_schema` (`pydantic_ai/_pydantic.py`):**
    *   This function is responsible for introspection.
    *   Uses `inspect.signature`, `_typing_extra.get_function_type_hints` to get signature and types.
    *   Uses `_griffe.doc_descriptions` to parse the function's docstring (handling Google, Numpy, Sphinx, or Auto-detecting format) to get the main description and parameter descriptions.
    *   Uses Pydantic internals (`_generate_schema.GenerateSchema`) to build the `core_schema` from type hints.
    *   Uses the passed `schema_generator` (defaulting to `GenerateToolJsonSchema`) to convert the `core_schema` to a JSON schema dictionary (`ObjectJsonSchema`).
    *   Handles the `takes_ctx` flag to potentially ignore the first `RunContext` parameter.

4.  **Provider-Specific Tool Mapping (`pydantic_ai/models/*.py`):**
    *   Classes like `OpenAIModel`, `AnthropicModel`, `CohereModel`, etc., have methods like `_get_tools` or `_map_tool_definition`.
    *   These methods receive `ModelRequestParameters`, which contains a list of the *standardized* `ToolDefinition` objects.
    *   They then translate these `ToolDefinition` objects into the specific format required by that provider's API (e.g., `openai.types.chat.ChatCompletionToolParam`, `anthropic.types.ToolParam`, `cohere.ToolV2`).

5.  **Runtime Tool Handling (`Agent.run`/`iter`):**
    *   Looking at the signatures for `Agent.run`, `Agent.run_sync`, and `Agent.iter` in `pydantic_ai/agent.py`, **none of them accept a `tools` parameter.**
    *   Tools are configured at the `Agent` level during initialization or via decorators.
    *   Dynamic tool availability per run is handled via the `Tool.prepare` mechanism, which allows a `Tool` instance to decide whether it should be included or how its `ToolDefinition` should be modified based on the `RunContext`.

