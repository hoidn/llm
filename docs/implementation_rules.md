**`docs/implementation_rules.md`**

# Implementation Rules and Developer Guidelines

**1. Purpose**

This document outlines the standard conventions, patterns, and rules for implementing Python code within this project. Adhering to these guidelines ensures consistency, maintainability, testability, and portability across the codebase, especially when translating IDL specifications into concrete Python implementations.

**2. Core Principles**

*   **Consistency:** Code should look and feel consistent regardless of who wrote it. Follow established patterns and conventions.
*   **Clarity & Readability:** Prioritize clear, understandable code over overly clever or complex solutions. Code is read more often than it is written.
*   **Simplicity (KISS & YAGNI):** Implement the simplest solution that meets the current requirements. Avoid unnecessary complexity or features. (See `docs/project_rules.md` for details).
*   **Testability:** Design code with testing in mind. Use dependency injection and avoid tight coupling.
*   **Portability:** While written in Python, aim for logic that is reasonably portable to other languages (Java, Go, JS) by minimizing reliance on Python-specific idioms where simpler, universal constructs exist.
*   **Parse, Don't Validate:** Structure data transformations such that input is parsed into well-defined, type-safe structures upfront, minimizing the need for scattered validation checks later in the code. (See "Parse, Don't Validate" section below).

**3. Project Structure and Imports**

*   **Directory Structure:** Strictly follow the established directory structure outlined in `docs/project_rules.md`. Place new modules and files in their logical component directories.
*   **Import Conventions:**
    *   Use **absolute imports** starting from the `src` directory for all internal project modules.
        ```python
        # Good
        from src.handler.base_handler import BaseHandler
        from src.system.errors import TaskError

        # Bad (Avoid relative imports beyond the same package)
        # from ..system.errors import TaskError
        ```
    *   Group imports in the standard order: standard library, third-party, project (`src.*`).
    *   Place imports at the top of the module. Avoid imports inside functions/methods unless absolutely necessary for specific reasons (e.g., avoiding circular dependencies, optional heavy imports) and document the reason clearly.

**4. Coding Style and Formatting**

*   **PEP 8:** Strictly adhere to PEP 8 guidelines (use linters like `ruff` or `flake8` and formatters like `black`).
*   **Type Hinting:**
    *   **Mandatory:** All function and method signatures (parameters and return types) **must** include type hints using the `typing` module.
    *   Use `Optional` for parameters that can be `None`.
    *   Use specific types (`str`, `int`, `bool`, `list[str]`, `dict[str, Any]`) rather than just `Any` whenever possible. Use `Any` only when the type is truly unknown or variable.
    *   For complex dictionary structures passed as parameters (especially from IDL `Expected JSON format`), define a `TypedDict` or a Pydantic model for clarity and validation.
*   **Docstrings:**
    *   **Mandatory:** All modules, classes, functions, and methods must have docstrings.
    *   Use **Google Style** docstrings.
    *   Clearly document parameters (`Args:`), return values (`Returns:`), and any exceptions raised (`Raises:`).
    *   Explain the *purpose* and *behavior*, not just *what* the code does.
*   **Naming:** Follow PEP 8 naming conventions (snake_case for variables/functions/methods, CamelCase for classes). Use descriptive names.

**5. Data Handling: Parse, Don't Validate (Leveraging Pydantic)**

*   **Principle:** Instead of passing raw dictionaries or loosely typed data and validating fields throughout the code, parse external/untrusted data (e.g., API responses, LLM outputs, configuration files, parameters described via IDL JSON) into **Pydantic models** at the boundaries of your system or component.
*   **Benefits:**
    *   **Upfront Validation:** Data validity is checked once during parsing.
    *   **Type Safety:** Subsequent code operates on validated, type-hinted objects.
    *   **Reduced Boilerplate:** Eliminates repetitive validation checks (`if 'key' in data and isinstance(data['key'], str): ...`).
    *   **Clear Data Contracts:** Pydantic models serve as clear definitions of expected data structures.
*   **Implementation:**
    *   Define Pydantic `BaseModel` subclasses for structured data, especially complex parameters specified in IDL "Expected JSON format".
    *   Use these models in function signatures where appropriate.
    *   Parse incoming data using `YourModel.model_validate(data)` or `YourModel.model_validate_json(json_string)`.
    *   Handle `pydantic.ValidationError` during parsing to manage invalid input gracefully.

    ```python
    from pydantic import BaseModel, ValidationError
    from typing import Optional

    # IDL: Expected JSON format: { "name": "string", "retries": "int" }
    class TaskParams(BaseModel):
        name: str
        retries: Optional[int] = 3 # Example with default

    def process_task(raw_params: dict):
        try:
            # Parse the raw dictionary into a validated Pydantic model
            params = TaskParams.model_validate(raw_params)
            # Now work with params.name, params.retries with type safety
            print(f"Processing task: {params.name} with {params.retries} retries")
            # ... rest of the logic using the validated params object ...
        except ValidationError as e:
            print(f"Invalid task parameters: {e}")
            # Handle the validation error (e.g., return error TaskResult)
    ```

**6. LLM Interaction (Leveraging Pydantic-AI - Conceptual)**

*   **Goal:** Achieve a provider-agnostic interface for core LLM interactions (sending prompts, getting responses, handling tool calls).
*   **Approach (Conceptual - Requires `pydantic-ai` integration):**
    *   Define core LLM interactions using `pydantic-ai`'s `Agent` concept where feasible.
    *   Use `pydantic-ai` Models (`OpenAIModel`, `AnthropicModel`, etc.) to abstract provider details.
    *   Leverage `pydantic-ai`'s built-in support for structured output (`output_type=YourPydanticModel`) and tool definition/calling (`@agent.tool`).
    *   Use `pydantic-ai` dependencies (`deps_type`, `RunContext`) for passing context/services to tools.
*   **Current State Mapping:** The existing `ProviderAdapter` interface in `model_provider_IDL.md` serves a similar purpose. If/when integrating `pydantic-ai`, this adapter could potentially be replaced or refactored to wrap `pydantic-ai` models and agents. For now, implement the `ProviderAdapter` interface as defined, keeping `pydantic-ai` principles in mind for future integration.

**7. Testing Conventions**

*   **Framework:** Use `pytest`.
*   **Emphasis on Integration/Functional Tests:** While unit tests are valuable for isolated logic, prioritize testing the interactions *between* components (integration tests) and testing complete workflows from input to output (functional/end-to-end tests).
*   **Minimize Mocking:**
    *   **Avoid excessive mocking.** Mocks can make tests brittle and hide integration problems.
    *   Prefer testing with real component instances where feasible, especially for core logic.
    *   **Use Mocks Strategically:** Mock primarily at the boundaries of the system (external APIs like LLM providers, filesystem *if absolutely necessary*, external databases) or for components that are slow, non-deterministic, or have significant side effects not relevant to the test.
    *   When mocking, mock the *dependency* as seen by the component under test, not deep internal implementation details.
    *   Use `pytest` fixtures (`conftest.py`) to provide real or fake/stub instances of dependencies where appropriate.
*   **Test Doubles:** Use `pytest` fixtures, `unittest.mock`, or simple stub classes. Choose the right type (Stub, Mock, Fake) for the job.
*   **Arrange-Act-Assert:** Structure tests clearly.
*   **Fixtures:** Use `pytest` fixtures extensively for setting up test environments, component instances, and test data. Define shared fixtures in `conftest.py`.
*   **Markers:** Use `pytest.mark` to categorize tests (e.g., `@pytest.mark.integration`, `@pytest.mark.llm`, `@pytest.mark.skipif(not aider_available)`).
*   **End-to-End Tests:** Define key user workflows (e.g., REPL query -> context -> LLM -> response; `/task` -> dispatcher -> tool execution; `/task` -> S-expression -> multiple steps -> result) and implement them as integration tests, mocking only the outermost boundaries (LLM API).

**8. Error Handling**

*   Use custom exception classes defined in `src.system.errors` (like `TaskError`) where appropriate for application-specific errors.
*   Catch specific exceptions rather than generic `Exception`.
*   Provide informative error messages.
*   Format errors into the standard `TaskResult` structure (`status: "FAILED"`, details in `content`/`notes`) at the appropriate boundary (e.g., in the Dispatcher, Handler, or Evaluator error handling).

**9. IDL to Python Implementation**

*   **Contractual Obligation:** The IDL file for a module is the source of truth. The Python implementation **must** match the interfaces, method signatures (including type hints), preconditions, postconditions, and described behavior precisely.
*   **Naming:** Python class/module names should correspond directly to the IDL interface/module names (e.g., `MemorySystem` interface in IDL maps to `MemorySystem` class in Python). Method names must match exactly.
*   **Parameters:** Parameter names and types must match the IDL. Use Pydantic models for complex "Expected JSON format" parameters.
*   **Return Types:** Return types must match the IDL. Use Pydantic models or `TypedDict` if the IDL specifies a structured dictionary return.
*   **Error Raising:** Implement error conditions described in `@raises_error` by raising appropriate Python exceptions (custom `TaskError` subclasses or built-in exceptions). Ensure error handling logic (e.g., returning a FAILED `TaskResult`) matches the IDL description for handled errors.
*   **Dependencies:** Implement dependencies (`@depends_on`) using constructor injection.

**10. Missing Items?**

*   **Configuration Management:** How is configuration (API keys, default models, resource limits, feature flags) loaded and accessed consistently? (Consider a dedicated config module/class).
*   **AsyncIO Usage:** Conventions for using `async`/`await` if asynchronous operations are prevalent (especially LLM calls, potentially parallel map).
*   **Logging Conventions:** Specific formatting, levels, and context to include in log messages (though basic setup exists).
*   **Concurrency/Parallelism:** Guidelines if/when introducing threading or multiprocessing (likely not needed initially).
*   **Security Considerations:** Handling sensitive data (API keys), input sanitization (especially for script execution).

These "Missing Items" can be added as the project evolves and these needs become clearer. The current set provides a strong foundation.
