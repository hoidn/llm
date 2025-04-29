# MCP Client Developer Guide

This document provides detailed documentation for developers working with the MCP (Multi-Component Protocol) client library in the Python SDK.

## Table of Contents

1. [Introduction](#introduction)
2. [Client Architecture](#client-architecture)
3. [Transport Layers](#transport-layers)
4. [Session Management](#session-management)
5. [Client Capabilities](#client-capabilities)
6. [Resource Handling](#resource-handling)
7. [Tool Execution](#tool-execution)
8. [Prompt Management](#prompt-management)
9. [Error Handling](#error-handling)
10. [Best Practices](#best-practices)
11. [Example Implementations](#example-implementations)

## Introduction

The MCP (Multi-Component Protocol) client library enables communication with MCP-compliant servers. The library provides a structured way to:

- Establish connections to servers via different transport layers
- Negotiate protocol versions
- Execute tools provided by the server
- Access and manage resources
- Retrieve and use prompts
- Handle progress reporting and logging

The client is built on a fully asynchronous architecture using Python's `asyncio` and `anyio` libraries, allowing for efficient and non-blocking communication.

## Client Architecture

### Core Components

The client architecture consists of several key components:

1. **ClientSession**: The primary interface for client-server communication
2. **Transport Layers**: Different ways to connect to servers (WebSocket, SSE, STDIO)
3. **Callbacks**: Handlers for specific server requests and notifications
4. **Request-Response Handling**: Mechanism for sending requests and receiving responses

### ClientSession Class

The `ClientSession` class (in `mcp.client.session`) is the main entry point for interacting with MCP servers:

```python
from mcp import ClientSession
from mcp.client.stdio import stdio_client

# Create transport
async with stdio_client(server_params) as (read_stream, write_stream):
    # Create session using the transport
    async with ClientSession(read_stream, write_stream) as session:
        # Initialize protocol
        await session.initialize()
        
        # Use session methods
        tools = await session.list_tools()
```

The `ClientSession` inherits from `BaseSession` and implements:
- MCP protocol initialization
- Request and notification handling
- Server method invocation

## Transport Layers

The client supports multiple transport mechanisms:

### 1. WebSocket Transport

For connecting to remote MCP servers over WebSockets:

```python
from mcp.client.websocket import websocket_client

async with websocket_client(websocket_url) as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:
        # Use session...
```

### 2. SSE Transport

For long-lived connections using Server-Sent Events:

```python
from mcp.client.sse import sse_client

async with sse_client(sse_url) as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:
        # Use session...
```

### 3. STDIO Transport

For local server execution with stdin/stdout communication:

```python
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="server_executable",
    args=["--arg1", "value1"],
    env={"ENV_VAR": "value"}
)

async with stdio_client(server_params) as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:
        # Use session...
```

## Session Management

### Initialization

The initialization process establishes the protocol version and capabilities between client and server:

```python
# Create session with custom client information and callbacks
session = ClientSession(
    read_stream,
    write_stream,
    client_info=types.Implementation(name="my-client", version="1.0.0"),
    sampling_callback=my_sampling_callback,
    list_roots_callback=my_roots_callback,
    logging_callback=my_logging_callback,
)

# Initialize protocol
initialize_result = await session.initialize()
```

The `initialize` method:
1. Sends client capabilities to the server
2. Negotiates protocol version
3. Verifies server compatibility
4. Sends the initialized notification

### Custom Callbacks

The client supports several callbacks for handling server requests:

```python
async def sampling_callback(
    context: RequestContext["ClientSession", Any],
    params: types.CreateMessageRequestParams
) -> types.CreateMessageResult | types.ErrorData:
    # Handle sampling request
    return types.CreateMessageResult(...)

async def list_roots_callback(
    context: RequestContext["ClientSession", Any]
) -> types.ListRootsResult | types.ErrorData:
    # Return filesystem roots
    return types.ListRootsResult(...)

async def logging_callback(
    params: types.LoggingMessageNotificationParams
) -> None:
    # Handle logging message
    print(f"[{params.level}] {params.message}")
```

## Client Capabilities

During initialization, the client reports its capabilities to the server:

### Sampling Capability

Indicates if the client can handle sampling requests:

```python
sampling = types.SamplingCapability()
```

### Roots Capability

Indicates if the client supports filesystem access:

```python
roots = types.RootsCapability(listChanged=True)
```

## Resource Handling

### Listing Resources

To get a list of available resources from the server:

```python
resources = await session.list_resources()
for resource in resources:
    print(f"Resource: {resource.name}, URI: {resource.uri}")
```

### Reading Resources

To read a specific resource:

```python
from pydantic import AnyUrl

resource_uri = AnyUrl("mcp://example.com/resource")
resource_data = await session.read_resource(resource_uri)
print(f"Content: {resource_data.content}")
```

### Resource Subscriptions

To subscribe to resource changes:

```python
# Subscribe to resource
await session.subscribe_resource(resource_uri)

# Later, unsubscribe when no longer needed
await session.unsubscribe_resource(resource_uri)
```

## Tool Execution

### Listing Available Tools

To get a list of tools provided by the server:

```python
tools_result = await session.list_tools()
for tool_group in tools_result:
    if isinstance(tool_group, tuple) and tool_group[0] == "tools":
        tools = tool_group[1]
        for tool in tools:
            print(f"Tool: {tool.name}, Description: {tool.description}")
```

### Calling Tools

To execute a tool on the server:

```python
result = await session.call_tool(
    name="example_tool",
    arguments={"param1": "value1", "param2": 42}
)
print(f"Tool result: {result}")
```

## Prompt Management

### Listing Prompts

To get a list of available prompts:

```python
prompts = await session.list_prompts()
for prompt in prompts:
    print(f"Prompt: {prompt.name}, Description: {prompt.description}")
```

### Getting Prompt Content

To get a specific prompt, with optional arguments:

```python
prompt = await session.get_prompt(
    name="example_prompt",
    arguments={"variable": "value"}
)
print(f"Prompt content: {prompt.content}")
```

## Error Handling

Implement robust error handling for server communication:

```python
try:
    result = await session.call_tool("example_tool", {"param": "value"})
    # Process successful result
except Exception as e:
    # Handle exceptions (connection issues, protocol errors, etc.)
    print(f"Error executing tool: {e}")
```

For robust applications, implement retry logic with exponential backoff:

```python
async def execute_with_retry(tool_name, arguments, max_retries=3, base_delay=1.0):
    attempt = 0
    while attempt < max_retries:
        try:
            return await session.call_tool(tool_name, arguments)
        except Exception as e:
            attempt += 1
            if attempt >= max_retries:
                raise
            wait_time = base_delay * (2 ** (attempt - 1))
            print(f"Retry in {wait_time} seconds...")
            await asyncio.sleep(wait_time)
```

## Progress Reporting

For long-running operations, report progress to the server:

```python
async def process_with_progress(progress_token, total_steps):
    for step in range(total_steps):
        # Do work
        progress = (step + 1) / total_steps
        await session.send_progress_notification(
            progress_token=progress_token,
            progress=step + 1,
            total=total_steps
        )
```

## Best Practices

### Concurrency Management

Use `AsyncExitStack` for proper resource management:

```python
from contextlib import AsyncExitStack

async def run_client():
    stack = AsyncExitStack()
    try:
        transport = await stack.enter_async_context(stdio_client(server_params))
        read, write = transport
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        
        # Use session...
        
    finally:
        await stack.aclose()
```

### Cleanup and Resource Management

Always ensure proper cleanup of resources:

```python
async def cleanup_servers(servers):
    cleanup_tasks = [
        asyncio.create_task(server.cleanup()) for server in servers
    ]
    if cleanup_tasks:
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)
```

### Connection State Management

Implement proper state tracking for server connections:

```python
class ServerConnection:
    def __init__(self):
        self.session = None
        self.initialized = asyncio.Event()
        self._cleanup_lock = asyncio.Lock()
        
    async def initialize(self):
        # Setup connection
        # ...
        self.initialized.set()
        
    async def ensure_initialized(self):
        if not self.initialized.is_set():
            await self.initialize()
        return self.session
```

## Example Implementations

### Simple MCP Client

A basic client connecting to a server and listing available tools:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="npx",
        args=["@anthropic-ai/mcp-example-server"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List tools
            tools = await session.list_tools()
            for tool_group in tools:
                if isinstance(tool_group, tuple) and tool_group[0] == "tools":
                    for tool in tool_group[1]:
                        print(f"Tool: {tool.name}")
                        print(f"Description: {tool.description}")
                        print("---")

if __name__ == "__main__":
    asyncio.run(main())
```

### Tool Execution Client

A client that executes a specific tool and processes the result:

```python
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def execute_tool():
    server_params = StdioServerParameters(
        command="./path/to/server",
        args=["--config", "config.json"],
        env={"API_KEY": "your-api-key"}
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Call a tool
            result = await session.call_tool(
                "search_tool", 
                {"query": "python", "limit": 5}
            )
            
            # Process results
            print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(execute_tool())
```

### Chatbot Client

A client that integrates with an LLM to provide interactive capabilities:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run_chatbot():
    server_params = StdioServerParameters(
        command="npx",
        args=["@anthropic-ai/mcp-tools-server"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Get available tools
            tools_result = await session.list_tools()
            tools = []
            for tool_group in tools_result:
                if isinstance(tool_group, tuple) and tool_group[0] == "tools":
                    tools.extend(tool_group[1])
            
            # Format tools for LLM
            tools_description = "\n".join([
                f"Tool: {tool.name}\nDescription: {tool.description}"
                for tool in tools
            ])
            
            # Implement chatbot logic with tools
            # ...

if __name__ == "__main__":
    asyncio.run(run_chatbot())
```

## Managing Server Configurations (Claude Code `.mcp.json` Compatibility)

Applications using the `mcp.py` client library often need to manage connection details for multiple MCP servers. While the library handles the connection given the parameters, storing and retrieving these parameters is an application-level concern.

One common approach, used by tools like Anthropic's Claude Code, is to utilize a project-specific JSON configuration file, typically named `.mcp.json`, located at the project root. This file allows server configurations, particularly for locally executed tools via STDIO, to be shared among team members via version control.

### `.mcp.json` Format (STDIO Servers)

To maintain compatibility with the format used by Claude Code for project-scoped servers, your application should expect and potentially generate `.mcp.json` files with the following structure *specifically for STDIO servers*:

```json
{
  "mcpServers": {
    "<server_id_1>": {
      "command": "executable_path_or_command",
      "args": ["list", "of", "string", "arguments"],
      "env": {
        "ENV_VAR_NAME": "string_value",
        "ANOTHER_VAR": "another_value"
      }
    },
    "<server_id_2>": {
      "command": "another_command",
      "args": [],
      "env": {}
    }
    // ... more STDIO server definitions
  }
}
```

**Fields Explained:**

*   **`mcpServers` (object)**: The required top-level key.
*   **`<server_id>` (string key)**: A unique identifier for the server within the project (e.g., `"shared-coder"`, `"local-linter"`). This is the name used to reference the server.
*   **`command` (string)**: The command or path to the executable for the MCP server.
*   **`args` (list<string>)**: A list of command-line arguments to pass to the executable.
*   **`env` (object)**: An object mapping environment variable names (strings) to their string values, to be set for the server process.

**Important Considerations for Compatibility:**

*   **STDIO Focus:** The documented `.mcp.json` format in Claude Code examples explicitly shows the structure for `stdio` transport servers. It does **not** specify how `websocket` or `sse` transports would be represented within this file.
*   **No Metadata:** This format does not include fields for `display_name`, `description`, `enabled` status, or explicit `transport` type within the `.mcp.json` structure itself. Applications needing such metadata might need to manage it separately or infer it.
*   **Loading Logic:** Your application's configuration loader should parse this structure. When connecting to a server specified in `.mcp.json`, it would extract the `command`, `args`, and `env` to instantiate `StdioServerParameters` and then use `stdio_client`.
*   **Other Transports:** If your application needs to support WebSocket or SSE servers configured similarly across a team, you might need to:
    *   Extend the `.mcp.json` format with additional fields (e.g., `url`, `transport`), acknowledging this deviates from the documented Claude Code structure for STDIO.
    *   Use separate configuration files or mechanisms (like user-scoped config) for non-STDIO servers, similar to how `claude mcp add --transport ...` might store them outside `.mcp.json`.
*   **Security:** As recommended by Claude Code, applications loading configurations from a project `.mcp.json` should consider security implications, potentially prompting users before connecting to execute local commands defined therein.

### Runtime Usage Pattern (Loading `.mcp.json`)

An application component responsible for managing MCP connections would:

1.  **Locate & Load:** Find and parse the `.mcp.json` file from the project root.
2.  **Lookup Server:** Access the `mcpServers` object and find the entry matching the desired `<server_id>`.
3.  **Extract Parameters:** Retrieve the `command`, `args`, and `env` values.
4.  **Instantiate `StdioServerParameters`:** Create the parameters object required by `stdio_client`.
5.  **Connect:** Use `async with stdio_client(server_params) as (read, write): ...` to establish the connection.
6.  **Create & Use Session:** Proceed to create and use the `ClientSession`.

By adhering to this structure for STDIO servers defined in `.mcp.json`, you can achieve compatibility with the pattern used by Claude Code for sharing project-specific local MCP server configurations. Remember to handle other transport types and additional metadata through potentially different configuration mechanisms if needed.

## Conclusion

The MCP client library provides a powerful framework for creating clients that can communicate with MCP-compliant servers. By following the patterns and practices outlined in this guide, you can build robust, scalable applications that leverage the full capabilities of the protocol.

For more detailed information, refer to the API documentation and explore the example implementations included in the repository.
