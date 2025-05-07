# Aider MCP Server - Developer Documentation

## Overview

Aider MCP Server is an experimental project that enables Claude Code to offload AI coding tasks to Aider, an open-source AI coding assistant. This integration allows Claude Code to delegate coding tasks through a Model Context Protocol (MCP) server, resulting in reduced costs, more control over the coding model used, and enabling Claude Code to work in an orchestrative way to review and revise code.

## Prerequisites and Operational Requirements

- **Git Repository Requirement**: The Aider MCP Server process **MUST** be launched with its current working directory set to the root of a valid Git repository. Failure to do so will result in a startup error.
- **API Keys**: Valid API keys for the AI models you intend to use must be configured (via environment variables or .env file)
- **Python Environment**: Python 3.10+ with required dependencies installed

## Project Structure

```
aider-mcp-server/
├── README.md                     # User documentation
├── pyproject.toml                # Project configuration and dependencies
├── src/
│   └── aider_mcp_server/         # Main package
│       ├── __init__.py
│       ├── __main__.py           # Entry point
│       ├── server.py             # Core MCP server implementation
│       └── atoms/                # Pure functional components
│           ├── __init__.py
│           ├── data_types.py     # Pydantic model definitions
│           ├── logging.py        # Logging utilities
│           ├── utils.py          # Helper functions
│           └── tools/            # MCP tool implementations
│               ├── __init__.py
│               ├── aider_ai_code.py   # AI coding tool
│               └── aider_list_models.py # Model listing tool
└── tests/                        # Test suite
    └── ...
```

## Architecture

The project follows a modular architecture with clean separation of concerns:

1. **Server Layer**: Implements the MCP protocol server
2. **Atoms Layer**: Contains pure functional components with minimal dependencies
   - **Tools**: Implements specific capabilities
   - **Utils**: Provides constants and helper functions
   - **Data Types**: Defines type definitions using Pydantic models

## MCP Interface Specification

This section details the specific MCP interface exposed by *this* server implementation, as required by MCP clients like the project's `AiderBridge`.

**Transport:** This server implementation uses the STDIO transport (`mcp.server.stdio.stdio_server`). Clients connecting to this server instance should use the corresponding `mcp.client.stdio.stdio_client` transport.

**Authentication:** This implementation does not include built-in authentication.

**Supported Tools:**

The server registers and handles the following tools:

1.  **`aider_ai_code`**
    *   **Description:** Runs Aider to perform AI coding tasks based on the provided prompt and files.
    *   **Input Parameters (`arguments` in `call_tool`):**
        *   `ai_coding_prompt` (string, **required**): The prompt/instructions for the AI coding task.
        *   `relative_editable_files` (list[string], **required**): Relative paths (from the server's `working_dir`) of files Aider is allowed to edit.
        *   `relative_readonly_files` (list[string], optional): Relative paths of files Aider can read for context but not edit.
        *   `model` (string, optional): Specific AI model identifier for Aider to use (overrides the server's default `editor_model`).
    *   **Response Format:**
        *   The `call_tool` function returns `list[mcp.types.TextContent]`.
        *   The `.text` attribute of the `TextContent` object contains a JSON string.
        *   **On Success:** The parsed JSON dictionary has the format:
            ```json
            {
              "success": true,
              "diff": "..."
            }
            ```
            Where `"diff"` contains the git diff output of the changes made (or fallback file content if git diff fails).
        *   **On Failure (Application Level):** The parsed JSON dictionary has the format:
            ```json
            {
              "success": false,
              "diff": "Error message..."
            }
            ```
            (Note: The `diff` key might still contain partial diffs or error details).

2.  **`list_models`**
    *   **Description:** Lists available Aider models, optionally filtered by a substring.
    *   **Input Parameters (`arguments` in `call_tool`):**
        *   `substring` (string, optional): Substring to filter model names (case-insensitive matching). Defaults to empty string (list all).
    *   **Response Format:**
        *   The `call_tool` function returns `list[mcp.types.TextContent]`.
        *   The `.text` attribute of the `TextContent` object contains a JSON string.
        *   The parsed JSON dictionary has the format:
            ```json
            {
              "models": ["model_id_1", "model_id_2", ...]
            }
            ```

**Error Handling:**

*   **Communication Errors:** The underlying `mcp.py` client library will raise exceptions for connection issues, timeouts, or protocol errors. The client (`AiderBridge`) must handle these.
*   **Application Errors:** Errors occurring *within* the tool execution on the server (e.g., invalid parameters after initial MCP parsing, Aider execution failure, file processing errors) are typically reported by returning a JSON payload containing an `"error"` key (as handled in `server.py`'s `handle_request` exception block) or by setting `"success": false` in the `aider_ai_code` response. The client must check for the `"error"` key or the `"success"` field in the parsed JSON response.

## Core Components

### 1. MCP Server (`server.py`)

The server is the main entry point that:
- Initializes the MCP server
- Registers available tools
- Handles incoming requests
- Routes requests to appropriate tool implementations
- Returns responses following the MCP protocol

### 2. MCP Tools

#### a. `aider_ai_code.py`

This tool delegates coding tasks to Aider. It:
- Takes a prompt describing the desired code changes
- Takes file paths (both editable and read-only)
- Executes Aider to implement the requested changes
- Returns success status and a diff of changes

```python
def run(
    prompt: str,
    editable_paths: list[str],
    read_only_paths: list[str] = None,
    model: str = None,
    working_dir: str = None,
) -> AiderRunResponse:
    """
    Executes Aider to implement code changes based on the prompt.
    
    Args:
        prompt: Instructions for the desired code changes
        editable_paths: Files that can be modified
        read_only_paths: Files that can be read but not modified
        model: AI model to use (defaults to configured model)
        working_dir: Directory to operate in
        
    Returns:
        AiderRunResponse with success status and diff of changes
    """
```

#### b. `aider_list_models.py`

This tool provides model discovery capabilities:
- Lists available AI models that match a given substring
- Helps discover which models are supported and available

```python
def run(match_substring: str = None) -> ListModelsResponse:
    """
    Lists available AI models, optionally filtered by substring.
    
    Args:
        match_substring: Optional filter to match against model names
        
    Returns:
        ListModelsResponse with array of matching model names
    """
```

### 3. Data Types (`data_types.py`)

Defines Pydantic models for request/response structures:

```python
class AiderRunRequest(BaseModel):
    prompt: str
    editable_paths: list[str]
    read_only_paths: list[str] = []
    model: Optional[str] = None
    working_dir: Optional[str] = None

class AiderRunResponse(BaseModel):
    success: bool
    diff: str = ""
    error: Optional[str] = None
```

## Configuration

### Default Settings

- Default editor model: `gemini/gemini-2.5-pro-exp-03-25`
- Working directory must be a git repository
- Configuration can be provided through:
  - Command line arguments
  - Environment variables
  - `.env` file for API keys

### Supported Models

The server supports various models including:
- Gemini models (2.5 Pro)
- GPT-4o
- Claude models (Sonnet, Opus)
- Mistral models
- LLaMA 4 models

## Development Workflow

### Setting Up the Development Environment

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/aider-mcp-server.git
   cd aider-mcp-server
   ```

2. Install dependencies:
   ```
   pip install -e .
   ```

3. Configure API keys:
   Create a `.env` file in the project root with required API keys:
   ```
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   GOOGLE_API_KEY=...
   ```

### Running the Server

Start the server with:
```
python -m aider_mcp_server --working-dir /path/to/git/repo
```

### Running Tests

```
pytest
```

## MCP Protocol Integration

### Request Format

Requests to the server follow the MCP protocol format:

```json
{
  "name": "aider_ai_code",
  "parameters": {
    "prompt": "Implement a function to calculate fibonacci numbers",
    "editable_paths": ["src/math.py"],
    "read_only_paths": ["src/utils.py"]
  }
}
```

### Response Format

Responses follow the MCP protocol format:

```json
{
  "success": true,
  "diff": "--- a/src/math.py\n+++ b/src/math.py\n@@ -1,3 +1,12 @@\n ...",
  "error": null
}
```

## Error Handling

The system includes comprehensive error handling:
- Input validation using Pydantic models
- Runtime error catching and logging
- Clear error messages returned to clients

## Extending the Server

### Adding a New Tool

1. Create a new module in `src/aider_mcp_server/atoms/tools/`
2. Implement the tool functionality with a `run()` function
3. Define request/response models in `data_types.py`
4. Register the tool in `server.py`

Example:

```python
# In new_tool.py
from typing import Optional
from ..data_types import NewToolRequest, NewToolResponse

def run(param1: str, param2: Optional[int] = None) -> NewToolResponse:
    # Implement tool functionality
    return NewToolResponse(success=True, result="Tool output")

# In server.py
from .atoms.tools import new_tool

# Register in initialize_server()
tool_registry.register_tool("new_tool", new_tool)
```

## Debugging Tips

1. Enable debug logging:
   ```
   python -m aider_mcp_server --log-level debug
   ```

2. Inspect API calls:
   - Check logs for detailed API request/response information
   - Use the `--verbose` flag for more detailed logging

3. Common issues:
   - Working directory not a git repository
   - Missing API keys for selected models
   - Invalid file paths in requests

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes with tests
4. Run the test suite to ensure all tests pass
5. Submit a pull request with a detailed description

## License

This project is licensed under [LICENSE] - see the LICENSE file for details.
