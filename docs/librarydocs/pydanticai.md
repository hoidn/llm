# Pydantic-AI Developer Guide

Welcome to the Pydantic-AI developer guide! This document provides a comprehensive overview of Pydantic-AI, how to install and configure it, and how to develop applications using this powerful agent framework.

## Table of Contents

1. [Introduction](#introduction)
2. [Installation and Setup](#installation-and-setup)
3. [Core Concepts](#core-concepts)
4. [Agents](#agents)
5. [Models](#models)
6. [System Prompts and Instructions](#system-prompts-and-instructions)
7. [Function Tools](#function-tools)
8. [Structured Output](#structured-output)
9. [Dependencies](#dependencies)
10. [Streaming Responses](#streaming-responses)
11. [Testing](#testing)
12. [Debugging with Logfire](#debugging-with-logfire)
13. [Advanced Use Cases](#advanced-use-cases)
14. [Contributing to Pydantic-AI](#contributing-to-pydantic-ai)

## Introduction

Pydantic-AI is a Python agent framework designed to make it less painful to build production-grade applications with Generative AI. It was built by the team behind [Pydantic](https://docs.pydantic.dev) with the goal of bringing the "FastAPI feeling" to GenAI app development.

Key features include:

- **Model-agnostic**: Built-in support for OpenAI, Anthropic, Gemini, Deepseek, Ollama, Groq, Cohere, Mistral, and more
- **Type-safe**: Designed for optimal type checking and validation
- **Python-centric**: Leverages familiar Python control flow and agent composition
- **Structured Responses**: Uses Pydantic to validate and structure model outputs
- **Dependency Injection**: Provides a clean system for providing data and services to agents
- **Streamed Responses**: Stream LLM outputs continuously with immediate validation
- **Graph Support**: Define complex flows using typing hints

## Installation and Setup

### Basic Installation

```bash
pip install pydantic-ai
```

This installs the core package with all dependencies needed for the included models.

### Slim Installation

For a leaner installation targeting specific models:

```bash
pip install "pydantic-ai-slim[openai]"  # For OpenAI models only
```

Available extras include: `openai`, `anthropic`, `vertexai`, `groq`, `mistral`, `cohere`, `bedrock`, `logfire`, `evals`, `duckduckgo`, `tavily`

### Logfire Integration (Optional)

For debugging and monitoring:

```bash
pip install "pydantic-ai[logfire]"
```

### Examples

To install and run examples:

```bash
pip install "pydantic-ai[examples]"
```

## Core Concepts

Pydantic-AI revolves around a few core concepts:

- **Agents**: The primary interface for interacting with LLMs
- **Models**: Interface to specific LLM providers (OpenAI, Anthropic, etc.)
- **System Prompts**: Instructions provided to the LLM
- **Function Tools**: Functions that the LLM can call to retrieve information
- **Structured Output**: Type-safe response formats using Pydantic models
- **Dependencies**: Dependency injection system for providing data to agents

## Agents

Agents are the primary interface for interacting with LLMs. They serve as containers for:

- System prompts and instructions
- Function tools
- Structured output types
- Dependency types
- LLM model settings

### Creating an Agent

```python
from pydantic_ai import Agent

# Simple agent with default text output
agent = Agent(
    'openai:gpt-4o',
    system_prompt='Be concise, reply with one sentence.'
)

# Run the agent
result = agent.run_sync('Where does "hello world" come from?')
print(result.output)
# Output: "The first known use of "hello, world" was in a 1974 textbook about the C programming language."
```

### Running Agents

There are four ways to run an agent:

1. `agent.run()` - Asynchronous, returns a complete response
2. `agent.run_sync()` - Synchronous, returns a complete response
3. `agent.run_stream()` - Asynchronous, returns a streamable response
4. `agent.iter()` - Asynchronous, returns an iterator over the agent's graph nodes

### Continuing Conversations

To maintain context across multiple runs:

```python
# First run
result1 = agent.run_sync('Who was Albert Einstein?')

# Second run, passing previous messages
result2 = agent.run_sync(
    'What was his most famous equation?',
    message_history=result1.new_messages()
)
```

## Models

Pydantic-AI supports multiple model providers and makes it easy to switch between them:

### Supported Models

- OpenAI (and compatible providers)
- Anthropic
- Gemini
- Bedrock
- Groq
- Mistral
- Cohere
- And more

### Specifying Models

Models can be specified directly by name with a provider prefix:

```python
agent = Agent('openai:gpt-4o')  # OpenAI's GPT-4o
agent = Agent('anthropic:claude-3-5-sonnet-latest')  # Anthropic's Claude
agent = Agent('google-gla:gemini-1.5-flash')  # Google's Gemini
```

### Fallback Models

You can use `FallbackModel` to try multiple models in sequence:

```python
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.anthropic import AnthropicModel

openai_model = OpenAIModel('gpt-4o')
anthropic_model = AnthropicModel('claude-3-5-sonnet-latest')
fallback_model = FallbackModel(openai_model, anthropic_model)

agent = Agent(fallback_model)
```

## System Prompts and Instructions

There are two ways to provide instructions to LLMs in Pydantic-AI:

### Static System Prompts

```python
agent = Agent(
    'openai:gpt-4o',
    system_prompt="Use the customer's name while replying to them."
)
```

### Dynamic System Prompts

System prompts can be defined as functions that access runtime context:

```python
from pydantic_ai import Agent, RunContext

agent = Agent(
    'openai:gpt-4o',
    deps_type=str,
)

@agent.system_prompt
def add_user_name(ctx: RunContext[str]) -> str:
    return f"The user's name is {ctx.deps}."

@agent.system_prompt
def add_the_date() -> str:
    from datetime import date
    return f'The date is {date.today()}.'

result = agent.run_sync('What is the date?', deps='Frank')
```

### Instructions vs. System Prompts

- Use `instructions` when you want your request to only include system prompts for the current agent
- Use `system_prompt` when you want to retain system prompts from previous requests

```python
agent = Agent(
    'openai:gpt-4o',
    instructions='You are a helpful assistant that can answer questions and help with tasks.'
)
```

## Function Tools

Function tools allow models to call external functions to retrieve information.

### Registering Tools

Tools can be registered using decorators:

```python
@agent.tool  # For tools that need access to context
async def get_weather(ctx: RunContext[WeatherAPI], location: str) -> str:
    """Get the current weather for a location."""
    return await ctx.deps.fetch_weather(location)

@agent.tool_plain  # For tools that don't need context
def roll_die() -> str:
    """Roll a six-sided die and return the result."""
    import random
    return str(random.randint(1, 6))
```

Or via constructor parameters:

```python
agent = Agent(
    'openai:gpt-4o',
    tools=[get_weather, roll_die]
)
```

### Tool Schema and Parameters

Function parameters are extracted from signatures and docstrings:

```python
@agent.tool_plain(docstring_format='google', require_parameter_descriptions=True)
def search_database(query: str, limit: int = 10, offset: int = 0) -> list[dict]:
    """Search the database for matching records.
    
    Args:
        query: The search query string
        limit: Maximum number of results to return
        offset: Number of results to skip
    """
    # Implementation...
```

### Dynamic Tools

Tools can be dynamically included or modified using a `prepare` function:

```python
async def only_if_admin(ctx: RunContext[User], tool_def: ToolDefinition) -> Union[ToolDefinition, None]:
    if ctx.deps.is_admin:
        return tool_def
    return None

@agent.tool(prepare=only_if_admin)
def admin_action(ctx: RunContext[User], action: str) -> str:
    return f"Admin action '{action}' performed by {ctx.deps.username}"
```

## Structured Output

Pydantic-AI can ensure LLMs return structured, validated data:

```python
from pydantic import BaseModel

class UserProfile(BaseModel):
    name: str
    age: int
    bio: str

agent = Agent(
    'openai:gpt-4o',
    output_type=UserProfile,
    system_prompt='Extract a user profile from the input'
)

result = agent.run_sync('My name is Sarah, I am 29, and I love hiking and photography.')
print(result.output)
# Output: name='Sarah' age=29 bio='I love hiking and photography.'
```

### Output Validators

You can add custom validation logic:

```python
@agent.output_validator
async def validate_sql(ctx: RunContext[DatabaseConn], output: SQLQuery) -> SQLQuery:
    try:
        await ctx.deps.execute(f'EXPLAIN {output.query}')
    except QueryError as e:
        raise ModelRetry(f'Invalid query: {e}')
    return output
```

### Union Types

You can define multiple possible output types:

```python
from typing import Union

agent: Agent[None, Union[list[str], list[int]]] = Agent(
    'openai:gpt-4o-mini',
    output_type=Union[list[str], list[int]],  # type: ignore
    system_prompt='Extract either colors or sizes from the input.',
)
```

## Dependencies

Pydantic-AI uses dependency injection to provide data to agents:

```python
from dataclasses import dataclass
import httpx

@dataclass
class WeatherDeps:
    api_key: str
    http_client: httpx.AsyncClient
    
agent = Agent(
    'openai:gpt-4o',
    deps_type=WeatherDeps,
)

@agent.tool
async def get_weather(ctx: RunContext[WeatherDeps], location: str) -> str:
    """Get the weather for a location."""
    response = await ctx.deps.http_client.get(
        'https://api.weather.com/current',
        params={'location': location, 'apikey': ctx.deps.api_key}
    )
    return response.json()['description']

# Using the agent
async def main():
    async with httpx.AsyncClient() as client:
        deps = WeatherDeps('your-api-key', client)
        result = await agent.run('What's the weather like in London?', deps=deps)
        print(result.output)
```

### Overriding Dependencies for Testing

```python
@dataclass
class TestWeatherDeps(WeatherDeps):
    async def get_weather(self, location: str) -> str:
        return "Sunny and 22°C"

# In tests
test_deps = TestWeatherDeps('test-key', None)
with agent.override(deps=test_deps):
    result = application_code('What's the weather like in London?')
```

## Streaming Responses

Pydantic-AI supports streaming responses for both text and structured data:

### Streaming Text

```python
async def main():
    async with agent.run_stream('Tell me about quantum computing') as result:
        async for message in result.stream_text():
            print(message, end='', flush=True)
```

### Streaming Deltas

```python
async def main():
    async with agent.run_stream('Tell me about quantum computing') as result:
        async for delta in result.stream_text(delta=True):
            print(delta, end='', flush=True)
```

### Streaming Structured Data

```python
from typing_extensions import TypedDict

class UserProfile(TypedDict, total=False):
    name: str
    age: int
    bio: str

agent = Agent('openai:gpt-4o', output_type=UserProfile)

async def main():
    async with agent.run_stream(user_input) as result:
        async for profile in result.stream():
            print(profile)
```

## Testing

Pydantic-AI includes test utilities to help write unit tests:

### Using TestModel

```python
from pydantic_ai.models.test import TestModel

test_model = TestModel()
agent = Agent(test_model)
result = agent.run_sync("What's 2+2?")
print(result.output)  # Will return a predefined response
```

### Capturing Run Messages

```python
from pydantic_ai import capture_run_messages

with capture_run_messages() as messages:
    try:
        result = agent.run_sync('Please perform calculation')
    except Exception as e:
        print('Error:', e)
        print('Messages:', messages)
```

## Debugging with Logfire

Pydantic-AI integrates with [Pydantic Logfire](https://pydantic.dev/logfire) for observability:

### Setup

```bash
pip install "pydantic-ai[logfire]"
py-cli logfire auth
py-cli logfire projects new
```

```python
import logfire
logfire.configure()

from pydantic_ai import Agent
agent = Agent('openai:gpt-4o', instrument=True)
# Or instrument all agents
Agent.instrument_all()
```

### HTTPX Monitoring

To monitor API calls:

```python
import logfire
logfire.configure()
logfire.instrument_httpx(capture_all=True)
```

## Advanced Use Cases

### RAG (Retrieval-Augmented Generation)

Build a question answering system over your documentation:

```python
@dataclass
class RAGDeps:
    search_db: SearchDatabase
    
agent = Agent('openai:gpt-4o', deps_type=RAGDeps)

@agent.tool
async def search_docs(ctx: RunContext[RAGDeps], query: str, limit: int = 3) -> list[str]:
    """Search the documentation for relevant information."""
    return await ctx.deps.search_db.search(query, limit)

# Usage
deps = RAGDeps(SearchDatabase())
result = await agent.run("How do I configure logging?", deps=deps)
```

### Multi-Agent Applications

Create specialized agents that collaborate:

```python
# Define agents for different tasks
research_agent = Agent('anthropic:claude-3-5-sonnet-latest', output_type=ResearchFindings)
writing_agent = Agent('openai:gpt-4o', output_type=ArticleSection)

# Compose them in your application
async def generate_article(topic: str) -> Article:
    # Get research data
    research = await research_agent.run(f"Research: {topic}")
    
    # Generate sections based on research
    intro = await writing_agent.run(
        f"Write introduction for {topic}",
        deps=WritingDeps(research=research.output)
    )
    
    body = await writing_agent.run(
        f"Write main content for {topic}",
        deps=WritingDeps(research=research.output)
    )
    
    conclusion = await writing_agent.run(
        f"Write conclusion for {topic}",
        deps=WritingDeps(research=research.output)
    )
    
    return Article(
        title=topic,
        intro=intro.output,
        body=body.output,
        conclusion=conclusion.output
    )
```

## Contributing to Pydantic-AI

### Installation and Setup

```bash
git clone git@github.com:<your username>/pydantic-ai.git
cd pydantic-ai
```

Install `uv`, `pre-commit` and `deno`:

```bash
# Install uv (see https://docs.astral.sh/uv/getting-started/installation/)
# Install pre-commit
uv tool install pre-commit
# Install deno (see https://docs.deno.com/runtime/getting_started/installation/)
```

Install dependencies and pre-commit hooks:

```bash
make install
```

### Running Tests

```bash
# Run all checks (formatting, linting, type checking, tests)
make

# Run documentation server
uv run mkdocs serve
```

### Adding New Models

To contribute a new model to Pydantic-AI, check the rules in the [contributing guidelines](https://ai.pydantic.dev/contributing/#new-model-rules).

- For models with dependencies: needs >500k monthly PyPI downloads consistently
- For models using other model's logic internally: GitHub org needs >20k stars
- For URL/API key models: can add documentation paragraph with instructions
- Otherwise: consider releasing `pydantic-ai-xxx` that depends on `pydantic-ai-slim`
