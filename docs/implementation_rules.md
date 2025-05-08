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
*   **Understanding External Library Data Structures:** When your component consumes or processes objects directly instantiated or returned by an external library (e.g., AST nodes from a parser like `sexpdata`, response objects from an API client like `mcp.py`), it is crucial to consult that library's documentation (or `docs/librarydocs/` if summarized internally) to understand the precise structure, attributes, and access methods for those objects. Do not assume a generic structure. This understanding should inform both implementation and test case design.
    *   **Example:** The `sexpdata.Quoted` object, returned by the parser for expressions like `'foo`, is a `namedtuple` and its content is accessed via `node.x`, not `node.val` or `node[1]`. Referencing `docs/librarydocs/sexpdata.md` would clarify this.
    *   **Impact:** Failing to understand the exact structure of external library objects can lead to `AttributeError` or `IndexError` exceptions that are hard to debug, as the object might "look" like a standard Python type (e.g., list-like) but have a specific API.
    *   **Action:** During the "Preparation & Understanding" phase (see `docs/start_here.md`), if your component relies on specific object types from an external library mentioned in `@depends_on_library` or implied by its function (e.g., a parser returning an AST), make it a point to review the documentation for those object types. This is especially important for libraries that might wrap standard types or use custom collections.

**5.x Dependency Injection & Initialization**

*   **Constructor/Setter Injection:** Components MUST receive their runtime dependencies (other components, resources specified in IDL `@depends_on`) via their constructor (`__init__`) or dedicated setter methods (e.g., `set_handler`). Avoid complex internal logic within components to locate or instantiate their own major dependencies. Document injection points clearly.
*   **Initialization Order:** In orchestrating components (like `Application` which creates other components), instantiate dependencies in the correct order *before* injecting them into dependent components that require them during their own initialization.
*   **Circular Dependencies:** Be vigilant for circular import dependencies during design and code reviews, as they can lead to subtle initialization errors (like the `pydantic-ai` import issues encountered). Minimize top-level imports in modules involved in complex interactions; prefer imports inside methods/functions where feasible. Use string type hints (e.g., `handler: 'BaseHandler'`) or `from typing import TYPE_CHECKING` blocks to break cycles needed only for type checking. If cycles are identified, prioritize refactoring.
*   **Test Instantiation:** Include tests verifying that components can be instantiated correctly with their required (real or mocked) dependencies.

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
        *   **Schema-to-Model Resolution:** When an atomic task template includes an `output_format` field with a `schema` property, use the `resolve_model_class` helper function to dynamically load the referenced Pydantic model. This function accepts a string in the format `"module.submodule.ModelName"` or just `"ModelName"` and returns the corresponding Pydantic model class. If only a model name is provided (no module path), the function will look in `src.system.models` by default.
        ```python
        # Example template using a schema reference
        template = {
            "name": "example_task",
            "instructions": "...",
            "output_format": {
                "type": "json",
                "schema": "TaskResult"  # Will resolve to src.system.models.TaskResult
            }
        }
        
        # Example using a fully qualified path
        template = {
            "name": "example_task",
            "instructions": "...",
            "output_format": {
                "type": "json",
                "schema": "custom.models.CustomResponseModel"  # Will resolve to custom.models.CustomResponseModel
            }
        }
        ```
*   **Reference:** Familiarize yourself with the `pydantic-ai` library documentation, potentially summarized or linked in `docs/librarydocs/pydanticai.md`.
*   **Verify Library Usage:** **Crucially, when integrating *any* significant third-party library (like `pydantic-ai`), carefully verify API usage** (e.g., function signatures, required arguments, expected data formats, **object constructor parameters**) against the library's official documentation and examples for the specific version being used. Do not rely solely on code examples from other sources or previous versions. **Failure to verify library APIs, especially for object construction or specific method signatures, can lead to subtle `TypeError` or `AttributeError` issues during runtime, even if type hints seem correct.** Consult `docs/librarydocs/` for internal summaries and links.
*   **Test Wrapper Interactions:** Wrapper classes (like `LLMInteractionManager`) that directly interact with external libraries should have targeted integration tests. These tests should verify the interaction (mocking the external network endpoint if necessary) and ensure data is passed to the library and results are received/processed correctly according to the library's expected behavior.

**7. Testing Conventions**

*   **Framework:** Use `pytest`.
*   **Emphasis on Integration/Functional Tests:** Prioritize integration tests that verify the collaboration between real component instances according to their IDL contracts. While unit tests are useful for isolated logic, integration tests are crucial for detecting issues arising from component interactions, dependency injection, configuration, and error propagation. Verify components work together according to their IDL contracts.

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
        *   **Use Mocks Strategically:** Mock primarily at the boundaries of the system (external APIs like LLM providers, filesystem *if absolutely necessary*, external databases, external MCP servers like the Aider server) or for components that are slow, non-deterministic, or have significant side effects not relevant to the test. Avoid mocking direct collaborators within the system's core logic where feasible. For example, when testing `TaskSystem`, inject and use a *real* (or near-real) `Handler` instance rather than mocking its methods extensively. Reserve mocking primarily for boundaries with external, non-deterministic, or slow systems (e.g., LLM APIs, databases, network services, external MCP servers).
        *   When mocking, mock the *dependency* as seen by the component under test, not deep internal implementation details.

    *   **Guideline 4a: Ensure Mock Type Fidelity for External Libraries:** When mocking methods from external libraries (like `mcp.py`, `pydantic-ai`, etc.), it is crucial that your mock return values precisely match the **expected type** returned by the real library (e.g., `mcp.types.TextContent` object, not just a dictionary or a local dummy class), especially if your implementation code relies on type checks like `isinstance()`.
        *   **Action:** Consult the external library's documentation or source code to confirm the exact return types (including wrapper objects like `CallToolResult`).
        *   **Action:** Use the real library types when constructing mock return data in your tests (e.g., `mock_response = [RealTextContent(text=...)]`).
        *   **Note:** Using `spec=OriginalLibraryClass` when creating mocks (`MagicMock(spec=...)`) helps catch *attribute* errors but **does not** guarantee type matching for `isinstance`.

    *   **Guideline 5: Mock Object Subtleties (Advanced):**
        *   Be aware that `MagicMock` instances are generally "truthy". If testing code like `if not ImportedClass:`, patching `ImportedClass` with a standard `MagicMock` might not behave as expected. Using `patch('module.ImportedClass', new_callable=MagicMock)` can sometimes help ensure the mock *class* itself is handled correctly in such checks.

*   **[NEW] Guideline 6: Verify Mock Calls Correctly:** When asserting mock calls (`assert_called_once_with`, `assert_called`), ensure you are checking the correct mock object. If you used `with patch.object(...)` or `@patch.object(...)`, assert against the mock object created by the patcher (often passed into the test function or available as the `as` target in the `with` statement). If you passed a mock instance during DI (Guideline 1), assert against that original mock instance variable.

*   **Guideline 7.X: Mock Configuration for Multiple or Complex Interactions:**
    *   **Context:** When a single test function involves multiple calls to a method that uses a mocked dependency, or when a shared mock fixture is used by multiple tests, precise mock configuration for each interaction is crucial.
    *   **Rule:** Ensure the mock is configured (e.g., `return_value`, `side_effect`) appropriately *before each specific interaction* you intend to test. Mocks generally do not "remember" configurations from previous calls within the same test function unless explicitly designed to do so (e.g., with a `side_effect` list that provides sequential return values). Reconfigure or reset mocks as needed if their behavior should change for different parts of a test or between tests using a shared fixture.
    *   **Example:**
        ```python
        # In a test function
        def test_component_with_multiple_dependency_calls(component_under_test, mock_dependency):
            # Interaction 1: Configure mock for the first call
            mock_dependency.some_method.return_value = "result_for_input1"
            output1 = component_under_test.process("input1")
            assert output1 == "expected_for_input1"
            mock_dependency.some_method.assert_called_with("input1_to_mock")

            # Interaction 2: Re-configure mock for the second call
            mock_dependency.some_method.return_value = "result_for_input2"
            output2 = component_under_test.process("input2")
            assert output2 == "expected_for_input2"
            # If asserting call for this specific interaction after others, consider call counts
            # or use mock_dependency.some_method.assert_any_call("input2_to_mock")
            # or reset the mock if appropriate: mock_dependency.some_method.reset_mock()
        ```
    *   **Arrange-Act-Assert:** Remember that the "Arrange" phase applies to each logical step of your test. If a step involves a mocked call, its specific arrangement (mock setup) should precede its "Act" and "Assert".

*   **Guideline 7a: Maintain Test Environment Dependency Parity:** Critical runtime dependencies (e.g., `mcp.py`, `pydantic-ai`, `GitPython`, `sexpdata`) **MUST** be installed and importable in the environment used for running unit and integration tests.
    *   **Avoid Fallbacks:** Do **not** rely on dummy classes or import fallbacks (e.g., `try...except ImportError...`) within test setup code. This practice masks real environment configuration problems and leads to misleading test results where tests might pass using dummies but fail against the real implementation types (as seen with `TextContent`).
    *   **Action:** Ensure your `requirements-dev.txt`, `pyproject.toml`, or equivalent dependency management file includes all packages needed for both running the code *and* running the tests against realistic mocks. Use consistent virtual environments for development and testing. CI pipelines should build the environment from these definitions.

*   **7.y Vertical Slice Testing:** Incorporate integration tests early in the development cycle that cover a key 'vertical slice' of functionality, exercising the main path through multiple collaborating components (e.g., Dispatcher -> SexpEvaluator -> MemorySystem -> TaskSystem -> Executor -> Handler). Even if some deeper dependencies within the slice are initially mocked or simplified, these tests validate the core wiring and data flow sooner.
*   **7.z Testing Failure Paths:** Explicitly design integration tests to verify how errors propagate between components. Test scenarios where a dependency returns a FAILED `TaskResult` or raises a documented exception, and assert that the calling component handles it correctly according to the [Error Handling Philosophy](../system/architecture/overview.md#error-handling-philosophy) and its own IDL contract.

*   **[NEW] Guideline 7b: Testing Wrapper Interactions / Library Boundaries:** When testing methods that prepare arguments for and call external library functions (e.g., `BaseHandler._execute_llm_call` preparing history for `llm_manager.execute_call`), aim to test the argument preparation logic (like history conversion) separately from the external call itself (which can often be mocked). This helps isolate errors, such as `TypeError` during object construction required by the library, from potential errors in the external call.

    *   **[NEW] Guideline 6: Verify Mock Calls Correctly:** When asserting mock calls (`assert_called_once_with`, `assert_called`), ensure you are checking the correct mock object. If you used `with patch.object(...)` or `@patch.object(...)`, assert against the mock object created by the patcher (often passed into the test function or available as the `as` target in the `with` statement). If you passed a mock instance during DI (Guideline 1), assert against that original mock instance variable.

*   **Guideline 7.X: Testing Internally Complex Components (Evaluators, State Machines, etc.)**
    *   **Challenge:** Unit testing components with significant internal logic, recursion (like `SexpEvaluator._eval`), or complex state management (like loop handlers) can be challenging and lead to brittle tests if relying heavily on mocking internal methods.
    *   **Prioritize Integration:** Whenever feasible, prioritize integration tests that exercise the component's public interface (e.g., `SexpEvaluator.evaluate_string`) with real or minimally mocked *external* dependencies (TaskSystem, Handler, MemorySystem). This verifies the overall contract more robustly.
    *   **Internal Mocking (Use Sparingly):** Mocking internal methods (methods within the class under test or its private helpers) should be reserved for cases where:
        *   Specific internal logic paths are too complex or difficult to trigger via the public interface alone.
        *   You need to isolate a sub-component's logic completely.
        *   **Justification:** If choosing this path, briefly justify the need for internal mocking in test comments or related documentation.
    *   **If Mocking Internals:**
        *   **Targeted Patching:** Strongly prefer `with patch.object(instance_or_class, 'method_name', ...)` scoped tightly within the specific test function/block needing it. Avoid global patching (`@patch` at class/module level, `autouse=True`) for internal methods.
        *   **Mock the Interface/Result:** Configure mocks to return the *expected result* of the internal call, not necessarily to simulate its internal steps. Ensure the mock return *type* matches the real method's return type, especially if the code under test uses `isinstance()`.
        *   **Verify Mock Calls:** Use `assert_called_with`, `call_count`, etc., on the *correct mock object* (the one created by `patch` or injected). Refer back to Guideline 6 for verifying calls on the correct mock.
        *   **Brittleness Warning:** Be aware that tests mocking internal details are highly sensitive to refactoring of the component's internal structure and may break even if the external behavior is unchanged. Factor in the maintenance cost.
        *   **Debugging Aid:** When debugging failing tests involving internal mocks, add temporary logging (`logging.debug(...)` or `print(...)`) inside the *production method* being tested to observe the actual arguments passed to, and values returned by, the mocked internal methods at runtime. This helps diagnose discrepancies between expected and actual mock behavior.

*   **Test Doubles:** Use `pytest` fixtures, `unittest.mock`, or simple stub classes. Choose the right type (Stub, Mock, Fake) for the job.
*   **Arrange-Act-Assert:** Structure tests clearly.
*   **Fixtures:** Use `pytest` fixtures extensively for setting up test environments, component instances (often with injected mocks as per Guideline 1), and test data. Define shared fixtures in `conftest.py`.
*   **Markers:** Use `pytest.mark` to categorize tests (e.g., `@pytest.mark.integration`, `@pytest.mark.llm`).
*   **End-to-End Tests:** Define key user workflows and implement them as integration tests, mocking only the outermost boundaries (LLM API, external services).
*   **7.x Testing Error Conditions:** When writing tests (`pytest`) to verify error handling logic:
    *   **Verify Status:** Always assert the overall status is `FAILED` (e.g., `assert result['status'] == 'FAILED'`).
    *   **Prefer Asserting Type/Reason:** Instead of matching exact error message strings, prioritize asserting the `type` and `reason` fields within the structured error object found in `notes['error']`. This verifies the correct error *category* was identified.
        ```python
        assert result['notes']['error']['type'] == 'TASK_FAILURE'
        assert result['notes']['error']['reason'] == 'template_not_found'
        ```
    *   **Check Key Details:** Assert the presence and validity of essential data within the error `details` object/dictionary if the test scenario requires specific details to be preserved.
        ```python
        assert 'details' in result['notes']['error']
        assert result['notes']['error']['details']['failing_param'] == 'expected_value'
        ```
    *   **Use Message Checks Sparingly:** If checking the error message string is necessary:
        *   Prefer checking for the presence of key *substrings* (`assert 'important part' in error_message`) over exact equality (`==`), as formatting might change slightly.
        *   If exact equality is required, consider defining the expected error message format using shared constants or helpers used by both production code and tests to avoid drift.
    *   **Test Exception Raising:** If testing code that *raises* an exception (as documented in IDL `@raises_error`), use `pytest.raises`:
        ```python
        import pytest
        from src.system.errors import SpecificError # Replace with actual error type

        with pytest.raises(SpecificError) as exc_info:
            component.method_that_raises(invalid_input)
        # Optionally assert specific attributes of the caught exception
        assert "specific detail" in str(exc_info.value)
        ```
    *   **[NEW] Testing Serialized/Dumped Structures:** When asserting the structure of complex return values, especially dictionaries derived from Pydantic models (like `TaskResult` containing nested error objects), be mindful of how serialization (`.model_dump(exclude_none=True)`, `json.dumps()`) affects the output. **Assert against the actual structure and keys present in the *returned dictionary*, not just the conceptual object structure.** Nested models might result in nested dictionaries. If assertions fail unexpectedly on structure, use debugging (`print()`, `breakpoint()`) to inspect the actual dictionary returned by the code under test before the assertion.
*   **Unit Test Complex Logic:** While integration tests are prioritized, complex internal algorithms or utility functions (e.g., parameter substitution, complex parsing, intricate validation logic) should have dedicated unit tests with broad coverage of inputs and edge cases.

**7.Y Testing Layered Systems (e.g., Parsers, Interpreters, Compilers)**

When testing systems composed of distinct processing layers (e.g., Lexer -> Parser -> AST -> Evaluator/Interpreter), adopt the following practices to improve test reliability and fault isolation:

*   **7.Y.1. Test Layers Independently:**
    *   Strive to unit test each layer in isolation. For example, test your Parser thoroughly to ensure it correctly transforms input strings into the specified AST structure, independently of how the Evaluator might later process that AST.

*   **7.Y.2. Verify and Document Parser/Transformer Output:**
    *   For components like parsers or data transformers, explicitly document the expected output structure (e.g., the AST format, specific type conversions) for various inputs.
    *   Write dedicated tests to verify that the parser/transformer produces these exact structures and performs documented conversions (e.g., S-expression `true` symbol to Python `True` boolean).

*   **7.Y.3. Use Verified Outputs for Downstream Layer Tests:**
    *   When testing a downstream layer (e.g., an AST Evaluator), its unit tests should ideally consume inputs that match the *verified output format* of the preceding layer (e.g., the Parser).
    *   **Preferred:** If feasible, use the actual (mocked if necessary for speed) preceding layer component to generate inputs for the layer under test.
    *   **Alternative:** If manually constructing inputs (like ASTs for an evaluator test), ensure these manually created structures precisely match what the real preceding layer would produce for the conceptual input they represent. Discrepancies here can lead to tests passing with unrealistic inputs or failing due to subtle differences.

*   **7.Y.4. Understand Data Transformations Between Layers:**
    *   Be explicit about any data transformations or type conversions that occur at the boundary of each layer. For instance, if a parser converts the S-expression symbol `true` to a Python boolean `True`, ensure downstream layers (like S-expression primitives) and their tests correctly anticipate receiving a Python `True` object, not a symbol.

**[NEW] Debugging Mock Failures**

*   **`AttributeError: Mock object has no attribute 'x'`**: The code under test tried to access attribute `x` on a mock instance. Ensure your test fixture or setup configures the mock instance with `mock_instance.x = ...` *before* the code under test runs. Use `spec=OriginalClass` when creating mocks (`MagicMock(spec=...)`) to help catch attribute typos.
*   **`AssertionError` on `assert_called_with(...)` or `assert_called_once()`**: Print `mock_object.mock_calls` just before the assertion to see the *actual* calls made with their arguments and counts. Compare this list carefully to your expectation.
*   **`fixture not found` for a mock parameter**: Check if the parameter name in the test signature matches the one injected by `@patch`. Ensure you actually *need* that mock object in your test logic (see Guideline 6: Managing `@patch` Parameters).

**Debugging Test Failures**

**[NEW] Inspect Actual vs. Expected:** When an assertion like `assert x == y` fails, don't just assume *why* it failed. Use `print(x)` / `print(y)` or a debugger immediately before the assertion to inspect the *actual runtime values and types* involved. This often reveals the root cause quickly (e.g., asserting an object instance equals a dictionary, slight differences in strings/lists).

**Test Setup for Error Conditions**

**[NEW] Satisfy Preconditions for Errors:** When writing tests to verify specific error handling (e.g., catching an exception, returning a FAILED status), ensure the "Arrange" phase of your test provides all necessary valid inputs and setup to satisfy the preconditions *up to the point where the error is expected to occur*. Don't let the test fail early due to unrelated issues like missing input parameters needed by code paths executed *before* the intended error point.

**Testing Configurable Behavior and Constants**

**[NEW] Handling Constants and Thresholds:** Be mindful when production code logic depends on constants or configurable thresholds (e.g., `MATCH_THRESHOLD`, timeout values).
    *   **Less Brittle Assertions:** Where possible, write assertions that test the *behavioral outcome* rather than being rigidly tied to the exact constant value. For example, instead of `assert len(results) == 5` (which depends on the threshold), assert that the *highest-scoring* result is the expected one and that its score is *above* the threshold, or that other specific items are *below* it.
    *   **Review Tests on Change:** If you modify a constant or configuration value that affects logic flow or thresholds in the production code, make it a practice to search for and review tests that might be impacted by this change. Update assertions accordingly.

*   **7.x Testing Error Conditions:** When writing tests (`pytest`) to verify error handling logic:
    *   **Verify Status:** Always assert the overall status is `FAILED` (e.g., `assert result['status'] == 'FAILED'`).
    *   **Prefer Asserting Type/Reason:** Instead of matching exact error message strings, prioritize asserting the `type` and `reason` fields within the structured error object found in `notes['error']`. This verifies the correct error *category* was identified.
        ```python
        assert result['notes']['error']['type'] == 'TASK_FAILURE'
        assert result['notes']['error']['reason'] == 'template_not_found'
        ```
    *   **Check Key Details:** Assert the presence and validity of essential data within the error `details` object/dictionary if the test scenario requires specific details to be preserved.
        ```python
        assert 'details' in result['notes']['error']
        assert result['notes']['error']['details']['failing_param'] == 'expected_value'
        ```
    *   **Use Message Checks Sparingly:** If checking the error message string is necessary:
        *   Prefer checking for the presence of key *substrings* (`assert 'important part' in error_message`) over exact equality (`==`), as formatting might change slightly.
        *   If exact equality is required, consider defining the expected error message format using shared constants or helpers used by both production code and tests to avoid drift.
    *   **Test Exception Raising:** If testing code that *raises* an exception (as documented in IDL `@raises_error`), use `pytest.raises`:
        ```python
        import pytest
        from src.system.errors import SpecificError # Replace with actual error type

        with pytest.raises(SpecificError) as exc_info:
            component.method_that_raises(invalid_input)
        # Optionally assert specific attributes of the caught exception
        assert "specific detail" in str(exc_info.value)
        ```

**X.Y Host Language Semantics in DSL Implementation**

When implementing a Domain-Specific Language (DSL) within a host language like Python, be mindful of how the host language's built-in type system and operator behaviors can implicitly influence your DSL's semantics.

*   **Awareness:** For example, Python's `bool` type is a subclass of `int` (where `True` is `1` and `False` is `0`). If your DSL parser converts DSL boolean symbols (e.g., S-expression `true`) into Python boolean objects, then arithmetic primitives in your DSL might implicitly inherit Python's behavior (e.g., `True + 1` evaluating to `2`).
*   **Explicit DSL Semantics:** If your DSL requires stricter or different semantics than the host language (e.g., DSL booleans should not be valid in arithmetic operations), your DSL primitives or evaluation logic must explicitly enforce these stricter type checks, even if the host language itself is more permissive. Document these DSL-specific semantics clearly.

**8. Error Handling**

*   Use custom exception classes defined in `src.system.errors` (like `TaskError`) where appropriate for application-specific errors.
*   Catch specific exceptions rather than generic `Exception`.
*   Provide informative error messages.
*   Format errors into the standard `TaskResult` structure (`status: "FAILED"`, details in `content`/`notes`) at the appropriate boundary (e.g., in the Dispatcher, Handler, or Evaluator error handling).
*   Adhere to the project's [Error Handling Philosophy](../system/architecture/overview.md#error-handling-philosophy) regarding returning FAILED `TaskResult` vs. raising exceptions.
*   **8.x Consistent Error Formatting in Orchestrators:** Components responsible for calling other components and orchestrating workflows (e.g., `Dispatcher`, `SexpEvaluator`, `TaskSystem` when calling executors) MUST implement a consistent mechanism for handling both raised exceptions and returned FAILED `TaskResult` objects from their dependencies.
    *   Use dedicated internal helper functions (like `_create_failed_result_dict` used in `Dispatcher`) to standardize the creation of FAILED `TaskResult` dictionaries.
    *   Ensure these helpers correctly populate the `notes['error']` field with a structured error object/dictionary (e.g., based on `TaskFailureError`), preserving details from the original error where possible.
    *   Apply this consistent formatting mechanism uniformly across all error paths within the orchestrator (e.g., in `try...except` blocks and when processing returned FAILED statuses) before returning the final `TaskResult` to the orchestrator's own caller. This ensures uniform error reporting structure regardless of how the error originated in a dependency.
*   **8.y Defensive Handling of Returned Data Structures:** When receiving complex data structures (especially dictionaries or objects like `TaskResult` containing variant or optional fields like `notes['error']`) returned from other components or external sources (even after initial parsing/validation):
    *   Perform defensive checks using `isinstance()` or `dict.get()` with defaults before accessing nested attributes or keys.
    *   Do not assume the structure perfectly matches expectations, especially for fields that can hold different types (e.g., `notes['error']` might contain a `TaskFailureError` object or a dictionary representation) or optional fields that might be absent.
    *   Example:
        ```python
        # Instead of directly accessing: details = result.notes['error']['details']
        error_info = result.notes.get('error')
        details = None
        if isinstance(error_info, TaskFailureError):
            details = error_info.details
        elif isinstance(error_info, dict):
            details = error_info.get('details')
        # Now safely use 'details' if it's not None
        ```
    *   This practice prevents common `AttributeError` or `KeyError` exceptions during result processing and makes the code more resilient to variations in returned data.
*   Adhere to the project's [Error Handling Philosophy](../system/architecture/overview.md#error-handling-philosophy) regarding returning FAILED `TaskResult` vs. raising exceptions.
*   **8.x Consistent Error Formatting in Orchestrators:** Components responsible for calling other components and orchestrating workflows (e.g., `Dispatcher`, `SexpEvaluator`, `TaskSystem` when calling executors) MUST implement a consistent mechanism for handling both raised exceptions and returned FAILED `TaskResult` objects from their dependencies.
    *   Use dedicated internal helper functions (like `_create_failed_result_dict` used in `Dispatcher`) to standardize the creation of FAILED `TaskResult` dictionaries.
    *   Ensure these helpers correctly populate the `notes['error']` field with a structured error object/dictionary (e.g., based on `TaskFailureError`), preserving details from the original error where possible.
    *   Apply this consistent formatting mechanism uniformly across all error paths within the orchestrator (e.g., in `try...except` blocks and when processing returned FAILED statuses) before returning the final `TaskResult` to the orchestrator's own caller. This ensures uniform error reporting structure regardless of how the error originated in a dependency.
*   **8.y Defensive Handling of Returned Data Structures:** When receiving complex data structures (especially dictionaries or objects like `TaskResult` containing variant or optional fields like `notes['error']`) returned from other components or external sources (even after initial parsing/validation):
    *   Perform defensive checks using `isinstance()` or `dict.get()` with defaults before accessing nested attributes or keys.
    *   Do not assume the structure perfectly matches expectations, especially for fields that can hold different types (e.g., `notes['error']` might contain a `TaskFailureError` object or a dictionary representation) or optional fields that might be absent.
    *   Example:
        ```python
        # Instead of directly accessing: details = result.notes['error']['details']
        error_info = result.notes.get('error')
        details = None
        if isinstance(error_info, TaskFailureError):
            details = error_info.details
        elif isinstance(error_info, dict):
            details = error_info.get('details')
        # Now safely use 'details' if it's not None
        ```
    *   This practice prevents common `AttributeError` or `KeyError` exceptions during result processing and makes the code more resilient to variations in returned data.

**9. IDL to Python Implementation**

*   **Contractual Obligation:** The IDL file for a module is the source of truth. The Python implementation **must** match the interfaces, method signatures (including type hints), preconditions, postconditions, and described behavior precisely. Strict adherence is crucial; deviations, even seemingly minor ones, can lead to subtle bugs, broken contracts between components, and difficult-to-diagnose test failures (e.g., unexpected name collisions or incorrect behavior).
*   **Naming:** Python class/module names should correspond directly to the IDL interface/module names (e.g., `MemorySystem` interface in IDL maps to `MemorySystem` class in Python). Method names must match exactly.
*   **Parameters:** Parameter names and types must match the IDL. Use Pydantic models for complex "Expected JSON format" parameters.
*   **Return Types:** Return types must match the IDL. Use Pydantic models or `TypedDict` if the IDL specifies a structured dictionary return.
*   **Error Raising:** Implement error conditions described in `@raises_error` by raising appropriate Python exceptions (custom `TaskError` subclasses or built-in exceptions). Ensure error handling logic (e.g., returning a FAILED `TaskResult`) matches the IDL description for handled errors.
*   **Dependencies:** Implement dependencies (`@depends_on`) using constructor injection.
*   **Parameter Substitution (AtomicTaskExecutor):** Be aware that the current `AtomicTaskExecutor` uses a simple regex-based substitution mechanism (`{{variable}}` or `{{variable.attribute}}`) and **does not support template engine features like filters or complex logic within placeholders**. See `src/executors/atomic_executor_IDL.md` for details. If complex templating is needed, the executor would require enhancement (e.g., integrating Jinja2).

**10. Logging Conventions**

Consistent logging is crucial for debugging and monitoring.

*   **10.1. Early Configuration:** Configure logging using `logging.basicConfig()` or a more advanced setup (like `logging.config.dictConfig`) as the **very first step** in application entry-point scripts (e.g., `src/main.py`, `scripts/*.py`, test runners) **before importing any application modules** (`src.*`).
    *   **Rationale:** Python's logging system initializes loggers when modules are imported. Configuring the root logger *after* module imports may not correctly apply the desired level or formatting to already-existing module loggers.
    *   **Example (Entry Point Script):**
        ```python
        import logging
        import os
        import sys
        # --- Logging Setup FIRST ---
        LOG_LEVEL = logging.DEBUG # Or get from args/env
        logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s...')
        logging.getLogger().setLevel(LOG_LEVEL) # Optional: Force root level
        print(f"Logging configured to level: {logging.getLevelName(LOG_LEVEL)}")

        # --- Path Setup (After logging) ---
        # ... sys.path modification ...

        # --- Application Imports (After logging) ---
        from src.main import Application
        # ... other imports ...

        # --- Main script logic ---
        # ...
        ```

*   **10.2. Module Loggers:** Use `logger = logging.getLogger(__name__)` at the top of each module to get a specific logger for that module.
*   **10.3. Setting Specific Levels:** If DEBUG logs from a specific module are not appearing despite setting the overall level in `basicConfig`, explicitly set the level for that module's logger *after* the `basicConfig` call in your entry point script:
    ```python
    # In your entry point script, after basicConfig:
    logging.getLogger("src.handler.base_handler").setLevel(logging.DEBUG)
    ```

**11. Missing Items?**

*   **Configuration Management:** How is configuration (API keys, default models, resource limits, feature flags) loaded and accessed consistently? (Consider a dedicated config module/class).
*   **AsyncIO Usage:** Conventions for using `async`/`await` if asynchronous operations are prevalent (especially LLM calls, potentially parallel map).
*   **Logging Conventions:** Specific formatting, levels, and context to include in log messages (though basic setup exists).
*   **Concurrency/Parallelism:** Guidelines if/when introducing threading or multiprocessing (likely not needed initially).
*   **Security Considerations:** Handling sensitive data (API keys), input sanitization (especially for script execution).

These "Missing Items" can be added as the project evolves and these needs become clearer. The current set provides a strong foundation.

**11. Utility Scripts**

Guidelines for helper, demo, or utility scripts located outside the main `src` or `tests` directories (e.g., in a `scripts/` directory):

*   **Path Setup:** Scripts MUST include robust path setup logic (e.g., calculating the project root relative to the script's `__file__` location) to ensure they can reliably import project modules (`src.*`). Assume scripts might be run from different working directories; ideally, design them to be run from the project root.
*   **Execution Location:** Document the intended execution location (e.g., "Run this script from the project root directory: `python scripts/my_script.py`") within the script's docstring or comments.
*   **Environment Consistency:** Ensure scripts are run using the project's standard Python environment (e.g., the activated virtual environment) to guarantee access to the correct dependencies. Avoid relying on globally installed packages. Dependencies required only by a script should be documented.

**11. DSL / Interpreter Implementation Guidelines**

When implementing components that parse and evaluate Domain-Specific Languages or complex recursive structures (e.g., `SexpEvaluator`), adhere to the following principles to enhance clarity, robustness, and debuggability:

*   **11.1. Principle of Explicit Intent:**
    *   Ensure the DSL syntax provides unambiguous ways to express core concepts, particularly the distinction between executable code and literal data.
    *   Avoid relying on implicit evaluator heuristics where explicit syntax (e.g., a `quote` mechanism for literal data) can provide clarity. Use `quote` or specific data constructors (like `list`) for literal data.
    *   **Quoting Symbols as Data:** When constructing literal lists that include symbols intended as data (e.g., keys in an association list), it is recommended to use `(quote your-symbol)` or the shorthand `'your-symbol` to prevent unintended evaluation if `your-symbol` could be bound. For example: `(list (quote key1) "value1" (quote key2) "value2")` or `(list 'key1 "value1" 'key2 "value2")`.
    *   **`defatom` Special Form Syntax:** The `defatom` special form, used for defining atomic tasks, has a specific argument order. The `(instructions "...")` block *must* appear immediately after the task name, followed by `(params (...))` if parameters are defined, then `(output_format ...)` and other optional clauses. Example: `(defatom my-task-name (instructions "Do this: {{param1}}") (params (param1 string)) (output_format ((type "text"))))`

**12. Data Merging Conventions**

When merging data from multiple sources (e.g., configuration layers, default values, runtime parameters, results from different components), the code MUST clearly implement the intended precedence rules.

*   **Document Precedence:** Briefly document the merging logic and precedence rules in comments or docstrings where the merge occurs.
*   **Establish Conventions:** For common merging scenarios, establish a project convention. For example:
    *   **Status Notes Merging:** When an orchestrator (like `Dispatcher` or `TaskSystem`) receives a `TaskResult` from a called component, the notes from the *component's result* typically take precedence over any default or contextual notes generated by the orchestrator itself for that specific operation.
*   **Implement Correctly:** Ensure the code implements the desired precedence. For dictionary merging where `component_data` should overwrite `orchestrator_defaults` on key collision:
    ```python
    # Correct precedence: component_data overwrites orchestrator_defaults
    final_data = orchestrator_defaults.copy()
    final_data.update(component_data)

    # Incorrect precedence (defaults overwrite component data):
    # final_data = component_data.copy()
    # final_data.update(orchestrator_defaults) # Avoid this if component data is primary
    ```

**14. Tool Registration and Naming Conventions**

When registering tools with the `BaseHandler` and using them in S-expressions or with LLM providers, adhere to these naming conventions:

*   **Tool Name Constraints:** The `name` field within a tool_spec dictionary (used when calling `BaseHandler.register_tool`) **MUST** conform to the naming constraints of the target LLM providers:
    *   For Anthropic and most providers: `^[a-zA-Z0-9_-]{1,64}$` (alphanumeric, underscore, hyphen)
    *   Special characters like colons (`:`) are generally disallowed by providers in this field

*   **Tool Lookup and Invocation:**
    *   The key used to register the tool's executor in `BaseHandler.tool_executors` (which is taken from `tool_spec["name"]`) is the identifier that the `SexpEvaluator` will use to look up and invoke the tool if called from an S-expression.
    *   When an S-expression like `(tool-symbol arg1 val1 ...)` is evaluated, and `tool-symbol` resolves to a string that is a key in `BaseHandler.tool_executors`, that specific executor is called.

*   **Naming Recommendation:** For simplicity and to avoid complex mapping layers:
    *   Use tool names that are valid for both LLM providers and S-expression symbols (e.g., prefer `(my_tool_name ...)` over `(my:tool:name ...)` in S-expressions if `my_tool_name` is the name registered with the handler and sent to the LLM).
    *   If S-expression symbols must contain characters invalid for LLM tool names (e.g., colons for namespacing), then the `SexpEvaluator`'s invocation logic or the `BaseHandler`'s registration would need a translation layer, which adds complexity.

*   **Registration Flow:**
    1. Instantiate core components (Handler, TaskSystem, MemorySystem, etc.)
    2. Register all system, provider-specific, and other tools with the Handler instance
    3. Call `handler.get_provider_identifier()` and determine active tools
    4. Call `handler.set_active_tool_definitions()` with these tools
    5. Call `handler.llm_manager.initialize_agent(tools=handler.get_tools_for_agent())` to create the pydantic-ai agent with the fully resolved set of tools

**13. Aider Integration (MCP Client)**

*   **Standard:** The project uses the **`mcp.py`** library for integration with the Aider MCP Server. This enables delegating coding tasks to an external Aider instance.
*   **Implementation Pattern:**
    *   The `AiderBridge` class serves as the MCP client for communicating with the Aider MCP Server.
    *   `AiderExecutorFunctions` provides the interface for executing Aider tools, with methods like `execute_aider_automatic` and `execute_aider_interactive`.
    *   `Application.initialize_aider()` is responsible for initializing the `AiderBridge` and registering Aider tools conditionally.
*   **Key Considerations:**
    *   **Parameter Handling:** When constructing parameters for the Aider MCP Server, always send an empty list `[]` for `relative_readonly_files` instead of `None` to avoid server-side errors.
    *   **Response Processing:** The `AiderBridge.call_aider_tool` method must properly handle the `CallToolResult` wrapper object returned by `session.call_tool`, including checks for the wrapper type, `isError` flag, and extraction of the content list.
    *   **Error Handling:** Implement robust error handling for both client-side exceptions (connection issues, timeouts) and server-side errors (returned in the response payload).
    *   **Server Working Directory:** The Aider MCP Server process **MUST** be launched with its current working directory set to the root of a valid Git repository. Failure to do so will result in a startup error. When configuring the server (typically via `.mcp.json`), ensure that the `cwd` parameter for `StdioServerParameters` points to a valid Git repository root. If `cwd` is not specified, the server process will inherit the CWD of the AiderBridge's host process.
    *   **Parameter Type Handling:** When a Python function is registered as a tool executor and invoked from an S-expression, the arguments passed will be the evaluated Python objects from the S-expression. If a tool's IDL specifies a parameter as a "JSON string array" (like `file_context`), but receives a Python list directly from an S-expression, the implementation should handle both formats. It's often more robust to expect Python objects directly if frequently called from S-expressions.
*   **Reference:** Familiarize yourself with the Aider MCP Server documentation in `docs/librarydocs/aider_MCP_server.md` for details on the server's API and behavior.

*   **11.2. Separate Evaluation from Application:**
    *   Design the core evaluation function (e.g., `_eval`) with the primary responsibility of determining the *value* of a given expression/node in the current context/environment.
    *   Isolate the logic that *applies* a function, operator, or procedure to its arguments. This application logic should operate on *already evaluated* arguments.
    *   Be cautious that the process of evaluating arguments does not itself incorrectly trigger function application or execution side-effects on the intermediate results.
    *   **Let Binding Scope:** The `let` special form evaluates all binding expressions in the outer environment before any bindings are established. This means a binding's value expression cannot reference other variables defined in the same `let` bindings list. For sequential binding (where later bindings can reference earlier ones), use nested `let` forms: `(let ((var1 <val1_expr>)) (let ((var2 (f var1))) <body>))`.

*   **11.3. Implement Robust and Explicit Dispatch Logic:**
    *   For functions that handle different types of language constructs (e.g., `_eval_list` handling special forms, primitives, invocations), ensure the dispatching rules are clear, explicit, and cover all expected cases.
    *   Define specific behavior for unrecognized or invalid constructs (e.g., encountering an undefined function name or an invalid list structure). Prefer raising clear, specific errors over implicit fall-throughs or attempting to interpret ambiguous structures (e.g., raise "Undefined function 'foo'" instead of trying to treat `(foo ...)` as data).

*   **11.4. Validate Inputs at Key Boundaries (Defensive Programming):**
    *   Functions designed to handle specific structural inputs passed from the evaluator (e.g., an invocation handler expecting `(key value_expr)` arguments) should perform basic validation on those inputs. While correct dispatch logic is the primary goal, these checks can prevent cryptic errors if the function is inadvertently called with malformed data during development or due to complex evaluation paths.

*   **11.5. Ensure Contextual Error Reporting:**
    *   Design error handling (`raise` statements, exception messages) to pinpoint the semantic source of the error as accurately as possible (e.g., "Undefined function 'foo' in expression (foo 1)" is better than "Type error processing arguments").
    *   Include relevant context in error messages, such as the specific expression or node being processed when the error occurred.

*   **11.6. Python Orchestration Pattern (Recommended Usage):**
    *   **Guideline:** Leverage Python for complex data preparation and manipulation tasks before invoking the S-expression evaluator. Avoid replicating extensive Python standard library functionality (especially complex string, list, or dictionary manipulation) as DSL primitives.
    *   **Recommended Pattern:**
        1.  **Prepare Data in Python:** Use standard Python code (f-strings, loops, file I/O via `FileAccessManager`, library calls) to construct complex data structures or strings (e.g., prompts assembled from multiple file contents).
        2.  **Create SexpEnvironment:** Instantiate `src.sexp_evaluator.sexp_environment.SexpEnvironment`.
        3.  **Bind Data:** Populate the environment's initial bindings dictionary, mapping desired S-expression variable names (strings) to the prepared Python objects.
        4.  **Write Focused S-expression:** Create the S-expression string. This string should primarily focus on workflow logic (sequences, conditionals), invoking tasks/tools, and referencing the variables bound in the environment for complex data inputs.
        5.  **Call `evaluate_string`:** Invoke `SexpEvaluator.evaluate_string(sexp_string, initial_env=prepared_env)`.
        6.  **Process Result in Python:** Handle the Python object returned by the evaluator.
    *   **Example:**
        ```python
        # --- Python Orchestration Code ---
        from src.sexp_evaluator.sexp_environment import SexpEnvironment
        # Assume 'evaluator' is an initialized SexpEvaluator instance

        # 1. Prepare complex data (e.g., prompt) in Python
        file1_content = "..." # Read file 1
        file2_content = "..." # Read file 2
        complex_prompt = f"Context:\nFile 1:\n{file1_content}\n\nFile 2:\n{file2_content}\n\nTask: Analyze."

        # 2. Create Environment
        # 3. Bind Data
        env = SexpEnvironment(bindings={
            "analysis_prompt_data": complex_prompt,
            "analysis_threshold": 0.7
        })

        # 4. Write S-expression using variables
        sexp_to_run = """
            (if (> analysis_threshold 0.5)
                (run_analysis_task (prompt analysis_prompt_data))
                (log_message "Threshold too low, skipping analysis")
            )
        """ # Assumes run_analysis_task and log_message are defined tasks/tools

        # 5. Call Evaluator
        result = evaluator.evaluate_string(sexp_to_run, initial_env=env)

        # 6. Process Result
        print(result)
        ```
    *   **Rationale:** This pattern leverages Python's strengths for general-purpose programming and data manipulation, keeping the S-expression DSL focused on its core orchestration role and simplifying the `SexpEvaluator` implementation by reducing the need for numerous custom primitives. The introduction of `lambda` expressions with lexical closures within the S-expression DSL itself now provides more powerful capabilities for defining inline abstractions and helper functions directly within the S-expression code, complementing the Python-first data preparation approach.

**12. Data Merging Conventions**

When merging data from multiple sources (e.g., configuration layers, default values, runtime parameters, results from different components), the code MUST clearly implement the intended precedence rules.

*   **Document Precedence:** Briefly document the merging logic and precedence rules in comments or docstrings where the merge occurs.
*   **Establish Conventions:** For common merging scenarios, establish a project convention. For example:
    *   **Status Notes Merging:** When an orchestrator (like `Dispatcher` or `TaskSystem`) receives a `TaskResult` from a called component, the notes from the *component's result* typically take precedence over any default or contextual notes generated by the orchestrator itself for that specific operation.
*   **Implement Correctly:** Ensure the code implements the desired precedence. For dictionary merging where `component_data` should overwrite `orchestrator_defaults` on key collision:
    ```python
    # Correct precedence: component_data overwrites orchestrator_defaults
    final_data = orchestrator_defaults.copy()
    final_data.update(component_data)

    # Incorrect precedence (defaults overwrite component data):
    # final_data = component_data.copy()
    # final_data.update(orchestrator_defaults) # Avoid this if component data is primary
    ```
