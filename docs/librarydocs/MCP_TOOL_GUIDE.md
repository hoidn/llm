# Pydantic AI MCP and Tool Integration Guide

This comprehensive guide outlines how to leverage Pydantic AI's Model Context Protocol (MCP) and implement various tool systems including Anthropic's text editor tools and general LLM tool interfaces.

## Table of Contents
1. [Overview](#overview)
2. [MCP Fundamentals](#mcp-fundamentals)
3. [General Tool Use in Pydantic AI](#general-tool-use-in-pydantic-ai)
4. [Pydantic-Based Tool Definitions](#pydantic-based-tool-definitions)
5. [Anthropic Text Editor Tool Integration](#anthropic-text-editor-tool-integration)
6. [Model-Agnostic Tool Use](#model-agnostic-tool-use)
7. [MCP Run Python Integration](#mcp-run-python-integration)
8. [Building Custom MCP Servers](#building-custom-mcp-servers)
9. [Error Handling for Tools](#error-handling-for-tools)
10. [Multi-Modal Tool Integration](#multi-modal-tool-integration)
11. [Tool Use with Dependency Injection](#tool-use-with-dependency-injection)
12. [Security Considerations](#security-considerations)
13. [Advanced MCP and Tool Patterns](#advanced-mcp-and-tool-patterns)
14. [Best Practices](#best-practices)

## Overview

Model Context Protocol (MCP) provides a standardized way for AI applications to connect with external tools and services. Combined with Pydantic's structured data validation and Anthropic's tool use capabilities, you can build powerful, type-safe, tool-augmented AI systems.

## MCP Fundamentals

MCP in Pydantic AI enables:

1. Agents as MCP clients (connecting to MCP servers to use their tools)
2. Agents embedded within MCP servers 
3. Building custom MCP servers to extend functionality

The Model Context Protocol (MCP) is designed to create a standardized communication layer between AI models and external services or tools.

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPClient

# Create an agent with MCP client
agent = Agent('anthropic:claude-3-5-sonnet-latest')

# Add MCP client with options
mcp_client = MCPClient(
    url="https://run-python.ai.pydantic.dev",
    timeout=30.0,  # Timeout in seconds
    verify_ssl=True,  # Verify SSL certificates
    auth_token=None,  # Optional authentication token
)
agent.add_mcp_client(mcp_client)

# Run agent with MCP tool access
result = await agent.run("Please calculate the factorial of 5")
```

### Configuring MCP Clients

MCP clients can be configured with several options:

```python
# Full client configuration
mcp_client = MCPClient(
    url="https://run-python.ai.pydantic.dev",
    timeout=30.0,  # Request timeout
    verify_ssl=True,  # Verify SSL certificates 
    headers={  # Custom headers for requests
        "X-Custom-Header": "value"
    },
    auth_token="your-secret-token",  # Authentication token
    metadata={  # Custom metadata
        "client_id": "unique-id",
        "version": "1.0.0"
    }
)
```

## General Tool Use in Pydantic AI

Before diving into MCP, let's understand how tools work generally in Pydantic AI:

```python
from pydantic_ai import Agent, RunContext

agent = Agent('openai:gpt-4o')

# Basic tool without parameters
@agent.tool
async def get_current_time(ctx: RunContext) -> str:
    """Get the current server time."""
    from datetime import datetime
    return datetime.now().isoformat()

# Tool with parameters
@agent.tool
async def multiply(ctx: RunContext, a: int, b: int) -> int:
    """Multiply two numbers together."""
    return a * b

# Run the agent with access to these tools
result = await agent.run("What time is it? Also, what is 12 times 34?")
```

### Tool Response Types

Tools can return various data types:

```python
# Return string
@agent.tool
async def hello(ctx: RunContext, name: str) -> str:
    return f"Hello, {name}!"

# Return dictionary
@agent.tool
async def user_info(ctx: RunContext, user_id: int) -> dict:
    return {
        "id": user_id,
        "name": "Example User",
        "email": "user@example.com"
    }

# Return Pydantic model
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str
    email: str

@agent.tool
async def get_user(ctx: RunContext, user_id: int) -> User:
    return User(id=user_id, name="Example User", email="user@example.com")
```

## Pydantic-Based Tool Definitions

Define tools with strict typing using Pydantic models for better validation and documentation:

```python
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from typing import List, Optional

# Define a Pydantic model for tool parameters
class WeatherParams(BaseModel):
    location: str = Field(description="City name or zip code")
    units: str = Field(default="metric", description="Temperature units (metric/imperial)")
    forecast_days: Optional[int] = Field(default=1, description="Number of forecast days", ge=1, le=7)

# Use the model as a single parameter
@agent.tool
async def get_weather(ctx: RunContext, params: WeatherParams) -> dict:
    """
    Get current weather and forecast for a location.
    
    Returns detailed weather information including temperature, conditions, 
    and forecast for the specified number of days.
    """
    # Implementation
    return {
        "location": params.location,
        "current": {"temperature": 21, "condition": "Sunny"},
        "forecast": [
            {"day": 1, "temperature": 22, "condition": "Partly Cloudy"} 
            for _ in range(params.forecast_days)
        ]
    }
```

### Tool Documentation 

Comprehensive documentation helps LLMs use your tools correctly:

```python
@agent.tool
async def search_database(
    ctx: RunContext, 
    query: str = Field(description="SQL query to execute"),
    limit: int = Field(default=10, description="Maximum number of records to return", ge=1, le=100)
) -> List[dict]:
    """
    Execute a SQL query against the database and return matching records.
    
    The query should be a valid SQL SELECT statement. The results will be limited
    to the specified number of records.
    
    Examples:
      - search_database("SELECT * FROM users WHERE age > 21")
      - search_database("SELECT name, email FROM customers", limit=5)
    
    Returns a list of matching records as dictionaries.
    """
    # Implementation
    return [{"id": 1, "name": "Example"}]
```

## Anthropic Text Editor Tool Integration

Implement Anthropic's text editor tools with Pydantic AI. These tools are available for Claude 3.5 and 3.7 Sonnet models and provide a structured way to interact with files.

```python
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from typing import Optional, List, Union
import os
from pathlib import Path

# Define tool parameter models
class ViewParams(BaseModel):
    path: str = Field(description="File or directory path")
    view_range: Optional[List[int]] = Field(default=None, description="Line range [start, end]")

class StrReplaceParams(BaseModel):
    path: str = Field(description="File path")
    old_str: str = Field(description="Exact text to replace (including whitespace)")
    new_str: str = Field(description="New text to insert")

class CreateParams(BaseModel):
    path: str = Field(description="File path")
    file_text: str = Field(description="Content for the new file")

class InsertParams(BaseModel):
    path: str = Field(description="File path")
    insert_line: int = Field(description="Line number for insertion (1-indexed)")
    new_str: str = Field(description="Text to insert")

class UndoEditParams(BaseModel):
    path: str = Field(description="File path")

# Helper function for path normalization (from single-file-agents)
def normalize_path(path: str) -> str:
    """Normalize path for cross-platform compatibility."""
    # Convert to absolute path if relative
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    
    # Normalize path separators
    return os.path.normpath(path)

# Create agent with text editor tools
agent = Agent('anthropic:claude-3-5-sonnet-latest')

# Track file edit history for undo functionality
file_history = {}

@agent.tool
async def view(ctx: RunContext, params: ViewParams) -> str:
    """
    View file or directory contents.
    
    If path points to a directory, lists all files and subdirectories.
    If path points to a file, returns its contents.
    Optional view_range can be provided to view specific line ranges.
    """
    path = normalize_path(params.path)
    
    # Handle directory listing
    if os.path.isdir(path):
        items = os.listdir(path)
        return f"Directory contents of {path}:\n" + "\n".join(items)
    
    # Handle file reading
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.readlines()
        
        # Handle line range if provided
        if params.view_range:
            start = max(0, params.view_range[0] - 1)  # Convert to 0-indexed
            end = min(len(content), params.view_range[1])
            content = content[start:end]
        
        return "".join(content)
    except Exception as e:
        return f"Error viewing file: {str(e)}"

@agent.tool
async def str_replace(ctx: RunContext, params: StrReplaceParams) -> str:
    """
    Replace specific text in a file.
    
    Replaces all occurrences of old_str with new_str.
    Requires exact match including whitespace and newlines.
    """
    path = normalize_path(params.path)
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Save current content for undo
        if path not in file_history:
            file_history[path] = []
        file_history[path].append(content)
        
        # Check if the text exists
        if params.old_str not in content:
            return f"Error: Text not found in {path}"
        
        # Replace and write back
        updated_content = content.replace(params.old_str, params.new_str)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        return f"Successfully replaced text in {path}"
    except Exception as e:
        return f"Error replacing text: {str(e)}"

@agent.tool
async def create(ctx: RunContext, params: CreateParams) -> str:
    """
    Create a new file with the specified content.
    
    If the file already exists, it will be overwritten.
    Creates parent directories if they don't exist.
    """
    path = normalize_path(params.path)
    
    try:
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Save empty file content for undo if file exists
        if os.path.exists(path):
            if path not in file_history:
                file_history[path] = []
            with open(path, 'r', encoding='utf-8') as f:
                file_history[path].append(f.read())
        else:
            if path not in file_history:
                file_history[path] = []
            file_history[path].append("")  # Empty content for new file
        
        # Write content to file
        with open(path, 'w', encoding='utf-8') as f:
            f.write(params.file_text)
        
        return f"Successfully created file: {path}"
    except Exception as e:
        return f"Error creating file: {str(e)}"

@agent.tool
async def insert(ctx: RunContext, params: InsertParams) -> str:
    """
    Insert text at a specific line number in a file.
    
    Line numbers are 1-indexed (first line is 1).
    If the line number exceeds the file length, text is appended to the end.
    """
    path = normalize_path(params.path)
    
    try:
        # Read current content
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Save current content for undo
        if path not in file_history:
            file_history[path] = []
        file_history[path].append("".join(lines))
        
        # Handle insertion
        insert_idx = min(len(lines), params.insert_line - 1)
        if insert_idx < 0:
            insert_idx = 0
        
        # Insert new line and ensure it ends with newline
        new_content = params.new_str
        if not new_content.endswith('\n'):
            new_content += '\n'
        
        lines.insert(insert_idx, new_content)
        
        # Write back
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        return f"Successfully inserted text at line {params.insert_line} in {path}"
    except Exception as e:
        return f"Error inserting text: {str(e)}"

@agent.tool
async def undo_edit(ctx: RunContext, params: UndoEditParams) -> str:
    """
    Undo the last edit to a file.
    
    Restores the file to its state before the last str_replace, create, or insert operation.
    """
    path = normalize_path(params.path)
    
    try:
        if path not in file_history or not file_history[path]:
            return f"No edit history found for {path}"
        
        # Restore previous content
        previous_content = file_history[path].pop()
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(previous_content)
        
        return f"Successfully undid last edit to {path}"
    except Exception as e:
        return f"Error undoing edit: {str(e)}"
```

### Using Anthropic Text Editor Tools

Once defined, you can use these tools by running queries that involve file operations:

```python
# Example usage
result = await agent.run("""
I need to work with the project's configuration file.
1. Show me the contents of config.json
2. Update the "api_version" field to "2.0"
3. Add a new "logging" section that enables debug mode
""")
```

## Model-Agnostic Tool Use

Make your tools work across multiple LLM providers:

```python
# Create agents with different providers but same tools
openai_agent = Agent('openai:gpt-4o')
anthropic_agent = Agent('anthropic:claude-3-5-sonnet-latest') 
gemini_agent = Agent('gemini:gemini-1.5-flash')
mistral_agent = Agent('mistral:mistral-large-latest')
cohere_agent = Agent('cohere:command-r-plus')

# File Operations tool set - reusable across models
def add_file_tools(agent_instance):
    """Add a standardized set of file tools to any agent."""
    
    @agent_instance.tool
    async def read_file(ctx: RunContext, file_path: str) -> str:
        """Read the contents of a file."""
        try:
            with open(file_path, 'r') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"
    
    @agent_instance.tool
    async def write_file(ctx: RunContext, file_path: str, content: str) -> str:
        """Write content to a file."""
        try:
            with open(file_path, 'w') as f:
                f.write(content)
            return f"Successfully wrote to {file_path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"
    
    @agent_instance.tool
    async def list_directory(ctx: RunContext, directory_path: str = ".") -> List[str]:
        """List files and subdirectories in the specified directory."""
        try:
            return os.listdir(directory_path)
        except Exception as e:
            return f"Error listing directory: {str(e)}"

# Add tools to all agents
for agent in [openai_agent, anthropic_agent, gemini_agent, mistral_agent, cohere_agent]:
    add_file_tools(agent)
```

### Adapting Tools for Different Models

Different models may have different capabilities and limitations for tool use:

```python
# Create model-specific tools
def add_model_specific_tools(agent_instance):
    """Add tools with adaptations for specific model capabilities."""
    model_name = str(agent_instance.model).lower()
    
    if "openai" in model_name or "anthropic" in model_name:
        # These models support more complex parameter types
        @agent_instance.tool
        async def advanced_search(
            ctx: RunContext, 
            query: dict
        ) -> List[dict]:
            """Execute complex search with filters."""
            # Implementation
            return [{"id": 1, "title": "Result"}]
    else:
        # Simpler implementation for other models
        @agent_instance.tool
        async def advanced_search(
            ctx: RunContext, 
            keywords: str,
            max_results: int = 10
        ) -> List[dict]:
            """Execute search with basic parameters."""
            # Implementation
            return [{"id": 1, "title": "Result"}]
```

## MCP Run Python Integration

Pydantic AI includes a built-in MCP server for Python code execution in a sandboxed environment.

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPClient

# Create agent with Python execution capabilities
agent = Agent('anthropic:claude-3-5-sonnet-latest')
agent.add_mcp_client(MCPClient(url="https://run-python.ai.pydantic.dev"))

# The agent can now execute Python code in a sandboxed environment
result = await agent.run("""
Can you help me calculate the first 10 Fibonacci numbers?
Please write and execute a Python function to do this.
""")
```

### Configuring Run Python MCP

The Run Python MCP server has several configuration options:

```python
from pydantic_ai.mcp import MCPClient

# Advanced configuration
python_mcp = MCPClient(
    url="https://run-python.ai.pydantic.dev",
    timeout=60.0,  # Extended timeout for complex calculations
    metadata={
        "execution_mode": "safe",
        "allowed_modules": ["numpy", "pandas", "matplotlib"],
        "matplotlib_format": "png"  # Return matplotlib figures as images
    }
)

agent.add_mcp_client(python_mcp)
```

### Local Run Python MCP Setup

For development or offline use, you can run the Python MCP server locally:

```python
from pydantic_ai.mcp import run_python_server

# Start server (run in separate process or thread)
async def start_server():
    await run_python_server(
        host="localhost",
        port=8000,
        allowed_modules=["numpy", "pandas"],
        max_execution_time=30,  # seconds
        memory_limit=512  # MB
    )

# Connect agent to local server
agent.add_mcp_client(MCPClient(url="http://localhost:8000"))
```

## Building Custom MCP Servers

Create your own MCP server with specialized tools:

```python
from pydantic_ai.mcp import MCPServer, MCPFunction
from pydantic import BaseModel, Field
from typing import List, Optional

# Define parameter and return models
class DatabaseQueryParams(BaseModel):
    query: str = Field(description="SQL query string")
    limit: int = Field(default=10, description="Maximum records to return")
    offset: int = Field(default=0, description="Records to skip")

class DatabaseRecord(BaseModel):
    id: int
    name: str
    value: Optional[float] = None

class DatabaseResult(BaseModel):
    records: List[DatabaseRecord]
    count: int
    query_time_ms: float

# Define MCP function
@MCPFunction
async def query_database(params: DatabaseQueryParams) -> DatabaseResult:
    """
    Execute SQL query against the database and return matching records.
    
    The query should be a valid SQL SELECT statement. Records will be paginated
    according to limit and offset parameters.
    """
    # Implementation to query your database
    import time
    start_time = time.time()
    
    # Simulate database query
    records = [
        DatabaseRecord(id=i, name=f"Record {i}", value=i * 1.5)
        for i in range(params.offset, params.offset + params.limit)
    ]
    
    query_time = (time.time() - start_time) * 1000
    
    return DatabaseResult(
        records=records,
        count=len(records),
        query_time_ms=query_time
    )

# Create and run server
server = MCPServer(
    functions=[query_database],
    name="Database Service",
    description="MCP server providing database access",
    version="1.0.0"
)

# Start server
async def start_server():
    await server.run(
        host="0.0.0.0",  # Listen on all interfaces
        port=8080,
        log_level="info",
        cors_origins=["*"],  # For development only
        auth_required=True,
        auth_token="your-secret-token"
    )
```

### Advanced MCP Server Features

```python
from pydantic_ai.mcp import MCPServer, MCPFunction, Resource
from pydantic import BaseModel
from typing import Dict, Any, Optional

# Custom authentication handler
async def authenticate(request):
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        return False
    return token[7:] == "your-secret-token"

# Function returning multi-modal content
@MCPFunction
async def generate_chart(params: Dict[str, Any]) -> Resource:
    """Generate a chart from data and return as image."""
    import matplotlib.pyplot as plt
    import io
    
    # Create chart
    plt.figure(figsize=(10, 6))
    plt.plot([1, 2, 3, 4], [10, 20, 25, 30])
    plt.title("Sample Chart")
    
    # Convert to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    
    # Return as image resource
    return Resource(
        data=buf.getvalue(),
        media_type="image/png",
        description="Generated chart"
    )

# Create server with more options
server = MCPServer(
    functions=[query_database, generate_chart],
    name="Advanced MCP Server",
    description="Server with multi-modal capabilities",
    authenticator=authenticate,
    rate_limit=100,  # requests per minute
    timeout=30.0,  # seconds
    max_request_size=10 * 1024 * 1024  # 10 MB
)
```

## Error Handling for Tools

Proper error handling is critical for tools to provide useful feedback:

```python
from pydantic_ai import Agent, RunContext, ToolError
from pydantic_ai.exceptions import ToolExecutionError

@agent.tool
async def fetch_data(ctx: RunContext, url: str) -> dict:
    """Fetch data from an external API."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()  # Raise exception for 4xx/5xx status codes
            return response.json()
    except httpx.TimeoutException:
        # Informative error for timeouts
        raise ToolError("The request timed out. The external service may be slow or unavailable.")
    except httpx.HTTPStatusError as e:
        # Different handling based on status code
        if e.response.status_code == 404:
            raise ToolError(f"Resource not found at {url}")
        elif e.response.status_code == 403:
            raise ToolError("Access denied. Check API permissions.")
        else:
            raise ToolError(f"HTTP error {e.response.status_code}: {e.response.reason_phrase}")
    except httpx.RequestError:
        # General connection errors
        raise ToolError("Failed to connect to the server. Check the URL and network connection.")
    except ValueError:
        # JSON parsing errors
        raise ToolError("Received invalid data that couldn't be parsed as JSON.")
    except Exception as e:
        # Fallback for unexpected errors
        raise ToolError(f"An unexpected error occurred: {str(e)}")
```

### Structured Error Responses

For more detailed error information:

```python
from pydantic import BaseModel
from pydantic_ai.exceptions import ToolError

class APIError(BaseModel):
    code: int
    message: str
    details: str

@agent.tool
async def perform_operation(ctx: RunContext, params: dict) -> dict:
    """Perform complex operation with detailed error reporting."""
    try:
        # Implementation
        return {"result": "success", "data": {}}
    except ValueError as e:
        error = APIError(code=400, message="Invalid parameters", details=str(e))
        raise ToolError(f"Error: {error.message}", error_data=error.dict())
    except TimeoutError:
        error = APIError(code=408, message="Operation timed out", details="The operation took too long to complete")
        raise ToolError(f"Error: {error.message}", error_data=error.dict())
```

## Multi-Modal Tool Integration

Tools can process and return multi-modal content:

```python
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import Image, BinaryContent, Document, UserMessage
import io
from PIL import Image as PILImage
import matplotlib.pyplot as plt

@agent.tool
async def generate_chart(ctx: RunContext, data: List[float], title: str) -> Image:
    """Generate a chart from data and return as image."""
    # Create chart with matplotlib
    plt.figure(figsize=(10, 6))
    plt.plot(data)
    plt.title(title)
    
    # Save to bytes buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    
    # Return as Image
    return Image(
        data=BinaryContent(
            data=buf.getvalue(),
            media_type="image/png"
        )
    )

@agent.tool
async def extract_text_from_image(ctx: RunContext, image: Image) -> str:
    """Extract text from an image using OCR."""
    # Implementation with an OCR library
    try:
        import pytesseract
        from PIL import Image as PILImage
        import io
        
        # Convert from BinaryContent to PIL Image
        image_data = image.data.data
        pil_image = PILImage.open(io.BytesIO(image_data))
        
        # Extract text
        text = pytesseract.image_to_string(pil_image)
        return text
    except Exception as e:
        raise ToolError(f"OCR failed: {str(e)}")

# Using multi-modal tools with message history
async def process_image_input():
    # Process an image the user uploaded
    image = Image(url="https://example.com/receipt.jpg")
    message = UserMessage(content=["Extract the total amount from this receipt", image])
    
    result = await agent.run(message)
    print(f"Extracted amount: {result.output}")
```

## Tool Use with Dependency Injection

Dependency injection provides a clean way to supply tools with external resources:

```python
from dataclasses import dataclass
from httpx import AsyncClient
from databases import Database
import redis.asyncio as redis
from pydantic_ai import Agent, RunContext

@dataclass
class Dependencies:
    http_client: AsyncClient
    database: Database
    redis: redis.Redis
    api_key: str
    config: dict

# Create agent with dependencies
agent = Agent('openai:gpt-4o', deps_type=Dependencies)

# Define tools that use dependencies
@agent.tool
async def search_products(
    ctx: RunContext[Dependencies], 
    query: str,
    category: Optional[str] = None
) -> List[dict]:
    """Search for products in the database."""
    # Access dependencies through ctx.deps
    db = ctx.deps.database
    
    # Build query
    sql = "SELECT * FROM products WHERE name LIKE :query"
    params = {"query": f"%{query}%"}
    
    if category:
        sql += " AND category = :category"
        params["category"] = category
    
    # Execute query
    results = await db.fetch_all(sql, params)
    return [dict(r) for r in results]

@agent.tool
async def fetch_weather(ctx: RunContext[Dependencies], location: str) -> dict:
    """Get weather information for a location."""
    client = ctx.deps.http_client
    api_key = ctx.deps.api_key
    
    # Check cache first
    cache_key = f"weather:{location}"
    cached = await ctx.deps.redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Fetch from API if not cached
    response = await client.get(
        "https://api.weather.com/v1/current",
        params={"location": location, "apikey": api_key}
    )
    data = response.json()
    
    # Cache the result
    await ctx.deps.redis.set(cache_key, json.dumps(data), ex=1800)  # 30 min expiry
    
    return data

# Provide dependencies when running the agent
async def run_with_dependencies():
    async with AsyncClient() as http_client:
        db = Database("postgresql://user:pass@localhost/products")
        await db.connect()
        
        redis_client = redis.Redis(host='localhost', port=6379, db=0)
        
        dependencies = Dependencies(
            http_client=http_client,
            database=db,
            redis=redis_client,
            api_key="your-api-key",
            config={"debug": True}
        )
        
        result = await agent.run(
            "Find me weather-resistant outdoor furniture",
            deps=dependencies
        )
        
        # Clean up
        await db.disconnect()
        await redis_client.aclose()
```

### System Prompts with Dependencies

Customize system prompts based on dependencies:

```python
@dataclass
class UserSession:
    user_id: int
    username: str
    preferences: dict
    is_premium: bool

# Create agent with user session dependency
agent = Agent('anthropic:claude-3-5-sonnet-latest', deps_type=UserSession)

# Dynamic system prompt
@agent.system_prompt
async def personalized_prompt(ctx: RunContext[UserSession]) -> str:
    """Generate personalized system prompt based on user session."""
    user = ctx.deps
    
    # Base prompt
    prompt = f"You are assisting {user.username}. "
    
    # Add customizations based on user preferences
    if "formal_tone" in user.preferences:
        prompt += "Use a formal and professional tone. "
    else:
        prompt += "Use a friendly and conversational tone. "
    
    # Add premium features
    if user.is_premium:
        prompt += "As a premium user, offer comprehensive and detailed responses. "
    else:
        prompt += "Provide helpful but concise responses. "
    
    return prompt
```

## Security Considerations

When implementing tools and MCP servers, security is paramount:

### Tool Security Best Practices

```python
# UNSAFE - allows arbitrary command execution
@agent.tool
async def unsafe_execute(ctx: RunContext, command: str) -> str:
    """NEVER implement a tool like this - allows arbitrary code execution."""
    import subprocess
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout

# BETTER - limited to specific commands with validation
@agent.tool
async def safe_file_info(ctx: RunContext, file_path: str) -> dict:
    """Get information about a file safely."""
    # Validate path to prevent path traversal attacks
    import os
    from pathlib import Path
    
    # Normalize and resolve path
    path = Path(file_path).resolve()
    
    # Check if path is within allowed directory
    allowed_dir = Path("/safe/directory").resolve()
    if not str(path).startswith(str(allowed_dir)):
        raise ToolError("Access denied: file is outside of allowed directory")
    
    # Check if file exists
    if not path.exists():
        raise ToolError("File not found")
    
    # Return safe information
    return {
        "name": path.name,
        "size": path.stat().st_size,
        "last_modified": path.stat().st_mtime,
        "is_directory": path.is_dir()
    }
```

### MCP Server Security

```python
from pydantic_ai.mcp import MCPServer, MCPFunction
import logging

# Configure security for MCP Server
server = MCPServer(
    functions=[safe_function1, safe_function2],
    # Security settings
    auth_required=True,  # Require authentication
    auth_token="your-secret-token",  # Token for authentication
    cors_origins=["https://your-app.com"],  # Restrict CORS
    rate_limit=60,  # Limit requests per minute
    max_request_size=1024 * 1024,  # 1MB max request size
    timeout=30.0,  # 30 second timeout
)

# Add request logging
@server.middleware
async def log_request(request, call_next):
    logging.info(f"Request from {request.client.host} to {request.url.path}")
    return await call_next(request)

# Add IP blocking
blocked_ips = ["192.168.1.100", "10.0.0.5"]
@server.middleware
async def block_ips(request, call_next):
    if request.client.host in blocked_ips:
        return Response(status_code=403, content="Access denied")
    return await call_next(request)
```

## Advanced MCP and Tool Patterns

### Chained Tool Execution

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPClient

agent = Agent('anthropic:claude-3-5-sonnet-latest')
mcp_client = MCPClient(url="https://run-python.ai.pydantic.dev")
agent.add_mcp_client(mcp_client)

# The agent can execute complex workflows involving multiple tool calls
result = await agent.run("""
I want to analyze weather data for New York City:
1. Fetch historical weather data for NYC for the past week
2. Clean the data and remove any outliers
3. Generate a chart showing temperature trends
4. Calculate the average daily temperature
5. Create a forecast for the next 3 days
""")
```

### Streaming with Tool Use

```python
from pydantic_ai import Agent
import asyncio

agent = Agent('anthropic:claude-3-5-sonnet-latest')

# Add tools
@agent.tool
async def long_running_task(ctx, iterations: int = 10) -> str:
    """Simulates a long-running task with progress updates."""
    results = []
    for i in range(iterations):
        # Simulate work
        await asyncio.sleep(1)
        results.append(f"Step {i+1} completed")
    return "\n".join(results)

# Stream results including tool calls
async def stream_with_tools():
    async for chunk in agent.run_stream(
        "Please perform a task with 5 iterations and give me updates as they happen."
    ):
        if chunk.delta:
            print(chunk.delta, end="", flush=True)
        
        # You can also access tool calls in progress
        if chunk.tool_calls:
            for call in chunk.tool_calls:
                if call.status == "in_progress":
                    print(f"\n[Tool call in progress: {call.name}]")
                elif call.status == "completed":
                    print(f"\n[Tool completed: {call.name}]")
```

### Combining Anthropic Text Editor with MCP Run Python

```python
# Agent can both modify files and execute Python code
agent = Agent('anthropic:claude-3-5-sonnet-latest')
agent.add_mcp_client(MCPClient(url="https://run-python.ai.pydantic.dev"))

# Add file editing tools
@agent.tool
async def view(ctx, path: str) -> str:
    """View file contents."""
    with open(path, 'r') as f:
        return f.read()

@agent.tool
async def str_replace(ctx, path: str, old_str: str, new_str: str) -> str:
    """Replace specific text in a file."""
    with open(path, 'r') as f:
        content = f.read()
    
    if old_str not in content:
        return f"Error: Text not found in {path}"
    
    updated_content = content.replace(old_str, new_str)
    with open(path, 'w') as f:
        f.write(updated_content)
    
    return f"Successfully replaced text in {path}"

@agent.tool
async def create(ctx, path: str, file_text: str) -> str:
    """Create a new file with specified content."""
    with open(path, 'w') as f:
        f.write(file_text)
    
    return f"Successfully created file: {path}"

# Now the agent can modify files and execute the modified code
result = await agent.run("""
1. Create a Python script that calculates prime numbers
2. Execute the script 
3. Improve the efficiency of the algorithm based on the results
4. Execute the improved script and compare performance
""")
```

### Tool Composition and Delegation

```python
# Create specialized agents
data_agent = Agent('openai:gpt-4o')
viz_agent = Agent('anthropic:claude-3-5-sonnet-latest')

# Add domain-specific tools
@data_agent.tool
async def analyze_data(ctx, dataset_path: str) -> dict:
    """Perform statistical analysis on the dataset."""
    # Implementation
    return {"mean": 42.0, "median": 40.5, "std_dev": 5.2}

@viz_agent.tool
async def create_visualization(ctx, data: dict, chart_type: str) -> Image:
    """Create a visualization from data."""
    # Implementation
    return Image(url="https://example.com/chart.png")

# Compose agents for a complete workflow
async def composed_workflow(dataset_path: str):
    # Step 1: Analyze data with data agent
    analysis_result = await data_agent.run(f"Analyze the dataset at {dataset_path}")
    
    # Step 2: Use analysis results to create visualization
    viz_result = await viz_agent.run(
        f"Create a bar chart visualization for this data: {analysis_result.output}"
    )
    
    return viz_result.output
```

## Best Practices

1. **Type Everything**: Use Pydantic models to define all tool parameters and return types.
   ```python
   class QueryParams(BaseModel):
       search_term: str
       filters: dict = Field(default_factory=dict)
       limit: int = Field(default=10, ge=1, le=100)
   
   @agent.tool
   async def search(ctx: RunContext, params: QueryParams) -> List[dict]:
       # Implementation with type safety
   ```

2. **Document Thoroughly**: Add detailed docstrings to tools to help LLMs understand their purpose.
   ```python
   @agent.tool
   async def analyze_sentiment(ctx: RunContext, text: str) -> dict:
       """
       Analyze the sentiment of a text passage.
       
       Returns a dictionary with sentiment scores:
       - score: Overall sentiment (-1.0 to 1.0)
       - positive: Positive sentiment score (0.0 to 1.0)
       - negative: Negative sentiment score (0.0 to 1.0)
       - neutral: Neutral sentiment score (0.0 to 1.0)
       
       Example: analyze_sentiment("I love this product!")
       """
   ```

3. **Handle Errors Gracefully**: Provide informative error messages when tools fail.
   ```python
   @agent.tool
   async def process_file(ctx: RunContext, file_path: str) -> dict:
       try:
           # Implementation
       except FileNotFoundError:
           raise ToolError(f"File not found: {file_path}")
       except PermissionError:
           raise ToolError(f"Permission denied for file: {file_path}")
       except Exception as e:
           raise ToolError(f"Unexpected error processing file: {str(e)}")
   ```

4. **Test with Multiple Models**: Ensure tools work consistently across different providers.
   ```python
   # Define test scenarios
   scenarios = [
       "Search for weather in New York",
       "What's the forecast for tomorrow?",
       "Show me temperature trends for the past week"
   ]
   
   # Test with different models
   for model_name in ["openai:gpt-4o", "anthropic:claude-3-5-sonnet-latest"]:
       agent = Agent(model_name)
       add_weather_tools(agent)
       
       for scenario in scenarios:
           result = await agent.run(scenario)
           # Assert result meets expectations
   ```

5. **Validate Inputs and Outputs**: Leverage Pydantic's validation to prevent unexpected behavior.
   ```python
   class SafePath(BaseModel):
       path: str
       
       @field_validator('path')
       def validate_path(cls, v):
           # Prevent path traversal attacks
           if '..' in v or v.startswith('/'):
               raise ValueError("Invalid path")
           return v
   
   @agent.tool
   async def read_safe_file(ctx: RunContext, params: SafePath) -> str:
       # Implementation with validated path
   ```

6. **Security First**: Never expose sensitive credentials in tool implementations.
   ```python
   # GOOD: Use dependencies for credentials
   @agent.tool
   async def query_api(ctx: RunContext[ApiDeps], endpoint: str) -> dict:
       # Get API key from deps, not hardcoded
       api_key = ctx.deps.api_key
       # Implementation
   ```

7. **Log and Monitor Tools**: Track usage and performance of tools.
   ```python
   @agent.tool
   async def monitored_function(ctx: RunContext, params: dict) -> dict:
       import time
       import logging
       
       start_time = time.time()
       logging.info(f"Tool call started: monitored_function with params {params}")
       
       try:
           # Implementation
           result = {"status": "success", "data": {}}
           return result
       except Exception as e:
           logging.error(f"Tool error: {str(e)}")
           raise
       finally:
           execution_time = time.time() - start_time
           logging.info(f"Tool call completed in {execution_time:.2f}s")
   ```

8. **Combine Tools and Structured Output**: Use Pydantic models for tool outputs and agent responses.
   ```python
   class AnalysisResult(BaseModel):
       summary: str
       sentiment: float
       key_topics: List[str]
   
   agent = Agent('openai:gpt-4o', output_type=AnalysisResult)
   
   @agent.tool
   async def fetch_article(ctx: RunContext, url: str) -> str:
       # Fetch article content
   
   # Agent will use the tool and return structured output
   result = await agent.run("Analyze the article at https://example.com/news/123")
   print(f"Sentiment score: {result.output.sentiment}")
   ```

This comprehensive guide demonstrates how to leverage the powerful combination of Pydantic AI's MCP capabilities, structured tool definitions, and the integration with tool systems like Anthropic's text editor tools. Together, these approaches create flexible, type-safe AI systems that can interact with external tools and services in a robust and secure manner.