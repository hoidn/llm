## Key Features

*   **S-expression DSL:** Define complex workflows involving sequential execution, conditionals (`if`), variable bindings (`let`), loops (`loop`), custom function definitions (`lambda` with lexical closures), inline atomic task definitions (`defatom`), and iterative patterns (`director-evaluator-loop`).
*   **Atomic Task Execution:** Register and execute parameterized "atomic" tasks (often LLM calls or simple operations) via the `TaskSystem`.
*   **Unified Tool Integration:** Seamlessly integrate and invoke various types of tools:
    *   **System Tools:** Built-in functions for interacting with the system's memory and file system (e.g., `system:get_context`, `system:read_files`, `system:write_file`, `system:list_directory`, `system:execute_shell_command`).
    *   **Provider-Specific Tools:** Leverage specialized tools offered by certain LLM providers (e.g., Anthropic Editor Tools).
    *   **External Tools via MCP:** Integrate with external services like the Aider coding assistant via the Model Context Protocol (MCP).
*   **Memory System & Indexing:**
    *   Maintain an index of file metadata from specified directories or Git repositories (`/index` command).
    *   Retrieve relevant file context for LLM tasks using associative matching (`get_context` S-expression primitive).
*   **Session Context Management:** Explicitly load, clear, and refine a set of files as the active context for an interactive session using the `/context` command.
*   **LLM Interaction (`pydantic-ai`):** Robust integration with various LLM providers (OpenAI, Anthropic, Google Gemini, etc.) via the `pydantic-ai` library, supporting structured output generation using Pydantic models.
*   **IDL-Driven Development:** Components are specified using Interface Definition Language (`*_IDL.md` files) defining strict contracts for implementation and testing.

## Architecture Overview

The system follows a modular, component-based architecture:

*   **`Application`:** The main entry point, responsible for initializing and wiring components, handling top-level commands (REPL commands like `/index`, `/context`, `/task`).
*   **`Dispatcher`:** Routes `/task` commands to the appropriate execution mechanism (S-expression evaluator, Task System, or direct tool).
*   **`SexpEvaluator`:** Parses and executes the S-expression DSL, managing environments, closures, special forms, primitives, and invoking tasks/tools.
*   **`TaskSystem`:** Manages the registration and orchestration of *atomic* task templates.
*   **`MemorySystem`:** Manages the global index of file metadata and handles associative matching requests to retrieve relevant context.
*   **`BaseHandler` / `PassthroughHandler`:** Handles LLM interactions, manages conversation history, registers and executes direct tools, manages session context (`/context`), and coordinates with helper managers.
*   **`LLMInteractionManager`:** Encapsulates interaction with the `pydantic-ai` library and the configured LLM agent.
*   **`FileContextManager` / `FileAccessManager`:** Provide safe and managed access to the file system for reading content and context generation.
*   **`GitRepositoryIndexer`:** Scans specified directories (especially Git repos) and generates metadata for the `MemorySystem`.
*   **`AiderBridge`:** Acts as an MCP client to communicate with an external Aider MCP Server for code editing tasks.
*   **Executors (`AtomicTaskExecutor`, `SystemExecutorFunctions`, `AiderExecutorFunctions`):** Implement the logic for specific task types or direct tools.

The architecture heavily relies on the **IDL-as-contract** principle, ensuring components adhere to their specified interfaces and behaviors. Dependency injection is used extensively for testability and decoupling.

## Dependencies

*   Python 3.10+
*   [Pydantic](https://docs.pydantic.dev/): For data validation and modeling.
*   [pydantic-ai](https://github.com/pydantic/pydantic-ai): For interacting with LLM providers.
*   [mcp.py](https://github.com/anthropics/mcp.py): For Model Context Protocol communication (Aider integration).
*   [sexpdata](https://github.com/jd-boyd/sexpdata): For parsing S-expressions.
*   [pytest](https://docs.pytest.org/): For testing.
*   [GitPython](https://gitpython.readthedocs.io/en/stable/) (Optional, for enhanced Git indexing features).

## Getting Started

### Prerequisites

1.  **Python:** Version 3.10 or higher recommended.
2.  **Git:** Required for version control and potentially by the `GitRepositoryIndexer`.
3.  **Virtual Environment:** Recommended (e.g., `venv`, `conda`).
    ```bash
    python -m venv .venv
    source .venv/bin/activate # or .\.venv\Scripts\activate on Windows
    ```
4.  **(Optional) Aider MCP Server:** If using Aider integration (`/task aider:...`), you need the [Aider MCP Server](https://github.com/paul-gauthier/aider-mcp-server) running and configured (see step 6).
5.  **(Optional) LLM API Keys:** For interacting with actual LLMs, you'll need API keys from providers like OpenAI, Anthropic, Google, etc.
6.  **Configuration:**
    *   **API Keys:** Create a `.env` file in the project root and add your API keys:
        ```dotenv
        OPENAI_API_KEY=sk-...
        ANTHROPIC_API_KEY=sk-ant-...
        GOOGLE_API_KEY=...
        # etc.
        ```
    *   **(Optional) MCP Server Config:** If using external tools like Aider via MCP, create a `.mcp.json` file in the project root to configure the connection (see `docs/librarydocs/aider_MCP_server.md` and `docs/librarydocs/mcp_client_developer_guide.md` for expected format, especially for STDIO). Example for Aider:
        ```json
        {
          "mcpServers": {
            "aider-mcp-server": {
              "command": "python",
              "args": ["-m", "aider_mcp_server", "--port", "auto"],
              "env": {},
              "transport": "stdio"
            }
          }
        }
        ```
        *(Adjust `command` and `args` based on your Aider MCP Server installation)*

### Installation

1.  Clone the repository:
    ```bash
    git clone <your-repo-url>
    cd <your-repo-name>
    ```
2.  Activate your virtual environment (if using one).
3.  Install dependencies (including development/testing tools):
    ```bash
    # Using pip directly (if requirements*.txt files exist)
    pip install -r requirements-dev.txt # Or requirements.txt + test deps
    pip install -e . # Install project in editable mode

    # Or using Make (if defined)
    # make install

    # Or using uv (if defined)
    # uv sync --dev
    ```

### Running the REPL (**Work In Progress**)

The REPL (Read-Eval-Print Loop) is the primary interactive interface. **Note: The REPL is currently under development and may have limited functionality or change.**

To run the REPL:

```bash
python src/repl/repl.py
```

## Usage Examples (REPL - **WIP**)

*(Note: Examples below assume the REPL is functional)*

1.  **Index a Directory:** Add files from a directory (relative to project root) to the system's memory.
    ```
    (passthrough) > /index src/ include="*.py" exclude="**/__init__.py"
    Indexing path: /path/to/project/src...
    Path indexed: /path/to/project/src (X files processed by indexer).
    ```

2.  **Load Session Context:** Find files related to a topic and make them the active context.
    ```
    (passthrough) > /context load TaskSystem execution logic
    Thinking...
    Context loaded: 3 files related to 'TaskSystem execution logic'. Summary: The TaskSystem orchestrates atomic tasks...
    ```

3.  **Passthrough Query (Using Session Context):** Ask a question related to the loaded context.
    ```
    (passthrough) > How does the TaskSystem execute an atomic template?
    Thinking...

    Response:
    The TaskSystem's `execute_atomic_template` method finds the template, resolves context settings, potentially fetches files using `resolve_file_paths`, prepares context, and then invokes the `AtomicTaskExecutor`'s `execute_body` method with the template definition and parameters...
    ```

4.  **Clear Session Context:**
    ```
    (passthrough) > /context clear
    Session context cleared.
    ```

5.  **Execute S-expression Task:** Run a workflow defined in S-expression.
    ```
    (passthrough) > /task (let ((paths (get_context (query "LLMInteractionManager configuration")))) (system:read_files (file_paths paths)))
    Thinking...

    Result:
    Status: COMPLETE
    Content:
    --- File: src/handler/llm_interaction_manager.py ---
    import json
    import logging
    ... (file content) ...
    --- End File: src/handler/llm_interaction_manager.py ---

    --- File: src/handler/base_handler.py ---
    ... (file content) ...
    --- End File: src/handler/base_handler.py ---
    --- End of Files ---

    Notes:
    {
      "execution_path": "s_expression",
      ...
    }
    ```

6.  **Execute Direct Tool:**
    ```
    (passthrough) > /task system:list_directory directory_path="src/handler"
    Thinking...

    Result:
    Status: COMPLETE
    Content: ["__init__.py", "base_handler.py", "command_executor.py", ...]
    Notes:
    { ... }
    ```

7.  **Run Demo Scripts:**
    *   Explore advanced DSL features: `python src/scripts/lambda_llm_code_processing_demo.py`
    *   Explore iterative loops: `python src/scripts/director_loop_coding_demo.py`
    *   Test Aider integration interactively: `python src/scripts/interactive_aider_demo.py --repo .`

## Development Workflow

This project follows an **IDL-Driven Development** process:

1.  **Specification:** Define component contracts (interfaces, methods, behavior, errors) in Interface Definition Language (`*_IDL.md`) files.
2.  **Implementation:** Write Python code that strictly adheres to the IDL contract.
3.  **Testing:** Write tests (primarily integration tests) that verify the implementation against the IDL specification.

**Key Developer Guides:**

*   **`docs/start_here.md`:** The primary onboarding document for developers. **READ THIS FIRST.**
*   **`docs/IDL.md`:** Guidelines for reading and writing IDL files.
*   **`docs/implementation_rules.md`:** Detailed coding standards, patterns (Dependency Injection, Parse Don't Validate, LLM/Aider integration), and testing conventions.
*   **`docs/project_rules.md`:** General project conventions (directory structure, Git workflow).
*   **`docs/memory.md`:** Template and guidelines for the developer's working memory log (track tasks, progress, context).

## Testing

Tests are written using `pytest`. The testing strategy emphasizes integration tests to verify component collaboration against IDL contracts, minimizing mocking where possible.

*   Run all tests:
    ```bash
    pytest tests/
    ```
*   Run specific tests:
    ```bash
    pytest tests/handler/test_base_handler.py
    pytest tests/handler/test_base_handler.py::TestBaseHandler::test_tool_registration
    ```

Refer to `docs/implementation_rules.md#testing-conventions` for detailed testing guidelines.

## Documentation

*   **`docs/start_here.md`:** Developer Orientation.
*   **`docs/IDL.md`:** IDL Syntax and Guidelines.
*   **`docs/implementation_rules.md`:** Coding Rules & Patterns.
*   **`docs/project_rules.md`:** Project Structure & Conventions.
*   **`docs/plan.md`:** High-level implementation plan.
*   **`docs/system/`:** Architecture overviews, decisions (ADRs), contracts, protocols, patterns.
    *   **`docs/system/contracts/types.md`:** Authoritative definitions for shared Pydantic models/types.
*   **`docs/components/`:** Detailed specifications and notes for individual components (linking to their `src/**/_IDL.md`).
*   **`docs/librarydocs/`:** Notes and guides for key external libraries (`pydantic-ai`, `mcp.py`, `sexpdata`, etc.).
*   **`docs/dev_workflows/`:** Standard procedures for tasks like refactoring or tech lead preparation.
*   **`src/**/_IDL.md`:** The Interface Definition Language files defining component contracts.

