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

**6. LLM Interaction (Leveraging Pydantic-AI via Manager)**

*   **Standard:** The project now uses the **`pydantic-ai`** library for all core LLM interactions. The previous custom `ProviderAdapter` interface is deprecated.
*   **Implementation Pattern:**
    *   The `BaseHandler` utilizes an internal helper class, `LLMInteractionManager`, to encapsulate interactions with `pydantic-ai`.
    *   `BaseHandler.__init__` is responsible for instantiating `LLMInteractionManager`, which in turn initializes the underlying `pydantic-ai` `Agent` based on configuration (model identifier, API keys, base system prompt).
    *   Core LLM execution logic within `BaseHandler` (e.g., in private methods like `_execute_llm_call`) should **delegate** the actual call to the `LLMInteractionManager` instance (`self.llm_manager`).
*   **Key `pydantic-ai` Concepts:**
    *   **Agent:** The primary interface for running LLM calls (`agent.run_sync()`, `agent.run()`, etc.).
    *   **Models:** Use specific model classes (`OpenAIModel`, `AnthropicModel`, etc.) provided by `pydantic-ai` during `LLMInteractionManager` initialization.
    *   **Tools:** Tools intended for LLM use must be registered. The `BaseHandler.register_tool` method stores the tool specification and executor.
        *   **Integration Complexity:** Dynamically registering tools with an already active `pydantic-ai` Agent can be complex. The current `register_tool` implementation stores the necessary information. Further work may be needed within `LLMInteractionManager` or `BaseHandler` to make these dynamically registered tools available to the `pydantic-ai` Agent during its execution run (e.g., potentially passing them as part of the `run_sync`/`run` call if supported, or requiring agent re-initialization). Consult `pydantic-ai` documentation for best practices.
    *   **Structured Output:** Leverage `pydantic-ai`'s `output_type` parameter in the agent's `run`/`run_sync` methods (passed via `LLMInteractionManager`) when structured output (defined by a Pydantic model) is required.
*   **Reference:** Familiarize yourself with the `pydantic-ai` library documentation, potentially summarized or linked in `docs/librarydocs/pydanticai.md`.

**7. Testing Conventions**

*   **Framework:** Use `pytest`.
*   **Emphasis on Integration/Functional Tests:** While unit tests are valuable for isolated logic, prioritize testing the interactions *between* components (integration tests) and testing complete workflows from input to output (functional/end-to-end tests). Verify components work together according to their IDL contracts.

*   **Mocking and Patching Strategy:**
    *   **Guideline 1: Test Dependency Injection by Passing Mocks:**
        *   **Context:** Many classes receive their dependencies via their constructor (`__init__`) - this is Dependency Injection (DI).
        *   **Rule:** The best way to test these classes is usually to create mock *objects* (using `unittest.mock.MagicMock` or similar) for the dependencies and pass these *mock instances* directly into the constructor when creating the object under test in your test setup (e.g., within a `pytest` fixture).
        *   **Testing Methods on Injected Mocks:** When you need to assert calls to methods on these injected mock *instances* or control their return values/side effects *within a specific test*, use `with patch.object(mock_instance, 'method_name', ...)` inside your test function or fixture. This precisely targets the method on the instance you care about for that test's scope. Avoid patching the method on the dependency's *class* globally if you already have a mock instance.
        *   **Avoid:** Globally patching the dependency *classes* themselves when testing a class that uses DI, as it's often unnecessary and can be complex.
        *   **Example:**
            ```python
            # In your test file or conftest.py
            from unittest.mock import MagicMock
            # Assume MyService needs a dependency 'worker'
            mock_worker_instance = MagicMock(spec=WorkerClass)
            service_under_test = MyService(worker=mock_worker_instance)
            # Now you can configure mock_worker_instance and assert calls on it
            mock_worker_instance.do_work.return_value = 'mocked result'
            service_under_test.perform_action()
            mock_worker_instance.do_work.assert_called_once()
            ```
            
            ```python
            # [NEW Example for patching instance method]:
            # In your test file or conftest.py
            def test_service_action_with_worker_failure(service_under_test, mock_worker_instance):
                 # service_under_test created with mock_worker_instance injected

                 # Patch the 'do_work' method *on the specific mock_worker_instance*
                 # for the duration of this 'with' block
                 with patch.object(mock_worker_instance, 'do_work', side_effect=SomeException("Boom!")) as patched_method:
                     # Act: Call the method on the service that uses the worker
                     with pytest.raises(SomeException):
                         service_under_test.perform_action()

                     # Assert: Check the call on the patched method
                     patched_method.assert_called_once()
                 # Outside the 'with' block, the patch is removed.
            ```

    *   **Guideline 2: Patch Where It's Looked Up:**
        *   **Context:** When you *do* need to patch (e.g., to replace a class used internally, a module function, or a built-in), you use `unittest.mock.patch`.
        *   **Rule:** The `target` string you provide to `patch` must be the path to the object *where it is looked up*, not necessarily where it was originally defined.
        *   **Examples:**
            *   If `my_module.py` has `import other_module; result = other_module.some_function()`, you patch `'my_module.other_module.some_function'`.
            *   If `my_module.py` has `from other_module import some_function; result = some_function()`, you patch `'my_module.some_function'`.
            *   Patching built-ins requires `patch('builtins.open', ...)` for example.
            *   **Patching Internal Component Instances:** If the class under test creates its *own* internal instance of another component (e.g., `self._internal_helper = HelperClass()`), and you need to mock methods on that *internal instance*, you should typically patch the method directly on the instance *after* the object under test is created. Use `with patch.object(object_under_test._internal_helper, 'method_to_mock', ...)` within your test. Avoid patching the `HelperClass` globally if possible.

    *   **Guideline 3: Prefer Specific Patching:**
        *   **Context:** You can apply patches globally (e.g., in fixtures with `autouse=True`) or specifically to tests/fixtures.
        *   **Rule:** Prefer applying patches only where needed using `@patch` decorators on test functions/fixtures or `with patch(...)` context managers inside tests. This makes dependencies clearer and avoids unintended side effects. Avoid broad, `autouse=True` patching unless the scope is very well understood.
        *   **Examples:**
            ```python
            from unittest.mock import patch

            # Decorator for a test function
            @patch('my_module.dependency_function')
            def test_my_function_behavior(mock_dep_func):
                mock_dep_func.return_value = 123
                # ... test code ...

            # Context manager inside a test
            def test_another_behavior():
                with patch('another_module.HelperClass') as MockHelper:
                    mock_instance = MockHelper.return_value
                    mock_instance.get_value.return_value = 456
                    # ... test code ...
            ```

    *   **Guideline 4: Minimize Mocking (Strategic Use):**
        *   **Avoid excessive mocking.** Mocks can make tests brittle and hide integration problems.
        *   Prefer testing with real component instances where feasible, especially for core logic within a component.
        *   **Use Mocks Strategically:** Mock primarily at the boundaries of the system (external APIs like LLM providers, filesystem *if absolutely necessary*, external databases) or for components that are slow, non-deterministic, or have significant side effects not relevant to the test.
        *   When mocking, mock the *dependency* as seen by the component under test, not deep internal implementation details.

    *   **Guideline 5: Mock Object Subtleties (Advanced):**
        *   Be aware that `MagicMock` instances are generally "truthy". If testing code like `if not ImportedClass:`, patching `ImportedClass` with a standard `MagicMock` might not behave as expected. Using `patch('module.ImportedClass', new_callable=MagicMock)` can sometimes help ensure the mock *class* itself is handled correctly in such checks.

    *   **[NEW] Guideline 6: Verify Mock Calls Correctly:** When asserting mock calls (`assert_called_once_with`, `assert_called`), ensure you are checking the correct mock object. If you used `with patch.object(...)` or `@patch.object(...)`, assert against the mock object created by the patcher (often passed into the test function or available as the `as` target in the `with` statement). If you passed a mock instance during DI (Guideline 1), assert against that original mock instance variable.

*   **Test Doubles:** Use `pytest` fixtures, `unittest.mock`, or simple stub classes. Choose the right type (Stub, Mock, Fake) for the job.
*   **Arrange-Act-Assert:** Structure tests clearly.
*   **Fixtures:** Use `pytest` fixtures extensively for setting up test environments, component instances (often with injected mocks as per Guideline 1), and test data. Define shared fixtures in `conftest.py`.
*   **Markers:** Use `pytest.mark` to categorize tests (e.g., `@pytest.mark.integration`, `@pytest.mark.llm`).
*   **End-to-End Tests:** Define key user workflows and implement them as integration tests, mocking only the outermost boundaries (LLM API, external services).

**Debugging Test Failures**

**[NEW] Inspect Actual vs. Expected:** When an assertion like `assert x == y` fails, don't just assume *why* it failed. Use `print(x)` / `print(y)` or a debugger immediately before the assertion to inspect the *actual runtime values and types* involved. This often reveals the root cause quickly (e.g., asserting an object instance equals a dictionary, slight differences in strings/lists).

**Test Setup for Error Conditions**

**[NEW] Satisfy Preconditions for Errors:** When writing tests to verify specific error handling (e.g., catching an exception, returning a FAILED status), ensure the "Arrange" phase of your test provides all necessary valid inputs and setup to satisfy the preconditions *up to the point where the error is expected to occur*. Don't let the test fail early due to unrelated issues like missing input parameters needed by code paths executed *before* the intended error point.

**Testing Configurable Behavior and Constants**

**[NEW] Handling Constants and Thresholds:** Be mindful when production code logic depends on constants or configurable thresholds (e.g., `MATCH_THRESHOLD`, timeout values).
    *   **Less Brittle Assertions:** Where possible, write assertions that test the *behavioral outcome* rather than being rigidly tied to the exact constant value. For example, instead of `assert len(results) == 5` (which depends on the threshold), assert that the *highest-scoring* result is the expected one and that its score is *above* the threshold, or that other specific items are *below* it.
    *   **Review Tests on Change:** If you modify a constant or configuration value that affects logic flow or thresholds in the production code, make it a practice to search for and review tests that might be impacted by this change. Update assertions accordingly.

**8. Error Handling**

*   Use custom exception classes defined in `src.system.errors` (like `TaskError`) where appropriate for application-specific errors.
*   Catch specific exceptions rather than generic `Exception`.
*   Provide informative error messages.
*   Format errors into the standard `TaskResult` structure (`status: "FAILED"`, details in `content`/`notes`) at the appropriate boundary (e.g., in the Dispatcher, Handler, or Evaluator error handling).

**9. IDL to Python Implementation**

*   **Contractual Obligation:** The IDL file for a module is the source of truth. The Python implementation **must** match the interfaces, method signatures (including type hints), preconditions, postconditions, and described behavior precisely. Strict adherence is crucial; deviations, even seemingly minor ones, can lead to subtle bugs, broken contracts between components, and difficult-to-diagnose test failures (e.g., unexpected name collisions or incorrect behavior).
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

**11. DSL / Interpreter Implementation Guidelines**

When implementing components that parse and evaluate Domain-Specific Languages or complex recursive structures (e.g., `SexpEvaluator`), adhere to the following principles to enhance clarity, robustness, and debuggability:

*   **11.1. Principle of Explicit Intent:**
    *   Ensure the DSL syntax provides unambiguous ways to express core concepts, particularly the distinction between executable code and literal data.
    *   Avoid relying on implicit evaluator heuristics where explicit syntax (e.g., a `quote` mechanism for literal data) can provide clarity. Use `quote` or specific data constructors (like `list`) for literal data.

*   **11.2. Separate Evaluation from Application:**
    *   Design the core evaluation function (e.g., `_eval`) with the primary responsibility of determining the *value* of a given expression/node in the current context/environment.
    *   Isolate the logic that *applies* a function, operator, or procedure to its arguments. This application logic should operate on *already evaluated* arguments.
    *   Be cautious that the process of evaluating arguments does not itself incorrectly trigger function application or execution side-effects on the intermediate results.

*   **11.3. Implement Robust and Explicit Dispatch Logic:**
    *   For functions that handle different types of language constructs (e.g., `_eval_list` handling special forms, primitives, invocations), ensure the dispatching rules are clear, explicit, and cover all expected cases.
    *   Define specific behavior for unrecognized or invalid constructs (e.g., encountering an undefined function name or an invalid list structure). Prefer raising clear, specific errors over implicit fall-throughs or attempting to interpret ambiguous structures (e.g., raise "Undefined function 'foo'" instead of trying to treat `(foo ...)` as data).

*   **11.4. Validate Inputs at Key Boundaries (Defensive Programming):**
    *   Functions designed to handle specific structural inputs passed from the evaluator (e.g., an invocation handler expecting `(key value_expr)` arguments) should perform basic validation on those inputs. While correct dispatch logic is the primary goal, these checks can prevent cryptic errors if the function is inadvertently called with malformed data during development or due to complex evaluation paths.

*   **11.5. Ensure Contextual Error Reporting:**
    *   Design error handling (`raise` statements, exception messages) to pinpoint the semantic source of the error as accurately as possible (e.g., "Undefined function 'foo' in expression (foo 1)" is better than "Type error processing arguments").
    *   Include relevant context in error messages, such as the specific expression or node being processed when the error occurred.
```