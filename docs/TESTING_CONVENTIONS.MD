# Testing Conventions

This document outlines the conventions and best practices for writing tests in the `agents2` project. Adhering to these guidelines ensures consistency, maintainability, and reliability of our test suite.

## Table of Contents

1.  [Philosophy](#philosophy)
2.  [Directory Structure](#directory-structure)
3.  [Import Conventions](#import-conventions)
    *   [Imports within `src/`](#imports-within-src)
    *   [Imports within `tests/`](#imports-within-tests)
4.  [Test Dependencies and Mocking](#test-dependencies-and-mocking)
    *   [Patching Strategy](#patching-strategy)
    *   [Fixtures](#fixtures)
    *   [Handling Optional Dependencies](#handling-optional-dependencies)
5.  [Test Naming and Organization](#test-naming-and-organization)
6.  [Type Hinting](#type-hinting)
7.  [Running Tests](#running-tests)
8.  [Linting and Formatting](#linting-and-formatting)

## Philosophy

Tests are first-class citizens of our codebase. They should be:
*   **Reliable:** Consistently pass when the code is correct and fail when it's broken.
*   **Readable:** Easy to understand what is being tested and why.
*   **Maintainable:** Easy to update as the source code evolves.
*   **Independent:** Tests should ideally not depend on the state left by other tests.

Consistency in how we write tests is key to achieving these goals.

## Directory Structure

*   All tests reside in the top-level `tests/` directory.
*   The structure within `tests/` should generally mirror the structure of the `src/` directory. For example, tests for `src/handler/base_handler.py` should be located in `tests/handler/test_base_handler.py`.
*   Use subdirectories like `tests/unit/`, `tests/integration/`, `tests/performance/` if needed to categorize tests, but maintain mirroring within those categories where practical.
*   Shared fixtures applicable to multiple test modules within a directory (or globally) should be placed in `conftest.py` files.

## Import Conventions

**This is crucial for avoiding common `ImportError` and `AttributeError` issues during test collection and execution.**

### Imports within `src/`

*   **RULE:** All imports *within* the `src` directory that refer to other modules *within* `src` **MUST** use absolute imports relative to the `src` root.
*   **DO NOT** use relative imports (`from .module import X` or `from ..package import Y`).
*   **Reason:** Absolute `src.` imports are robust and work reliably both when running the application code directly (e.g., `python -m src.main`) and when `pytest` imports modules individually from the `tests/` directory, provided the tests are run from the project root. Relative imports have proven fragile under test execution.

    ```python
    # Location: src/handler/base_handler.py

    # --- CORRECT ---
    from src.memory.context_generation import ContextGenerationInput
    from src.system.errors import BaseError
    from src.task_system.task_system import TaskSystem # Assuming TaskSystem is defined here

    # --- INCORRECT (Avoid These) ---
    # from ..memory.context_generation import ContextGenerationInput # Avoid ..
    # from .utils import helper # Avoid .
    # from system.errors import BaseError # Avoid missing src. prefix
    ```

### Imports within `tests/`

*   **RULE 1:** Imports of **source code** modules (anything from `src/`) **MUST** use absolute imports relative to the `src` root.
*   **RULE 2:** Imports of **test utilities** or other test modules *within* the `tests/` directory *can* use relative imports (`.`) if it enhances clarity and locality (e.g., importing a helper from the same test directory). Avoid `..` relative imports even within tests if possible.

    ```python
    # Location: tests/handler/test_base_handler.py

    # --- CORRECT ---
    import pytest
    from unittest.mock import MagicMock
    from src.handler.base_handler import BaseHandler # Absolute src. import for source code
    from src.memory.context_generation import ContextGenerationInput # Absolute src.
    from .handler_test_utils import create_mock_context # Relative . import for test utility

    # --- INCORRECT (Avoid These) ---
    # from ..memory.test_memory_utils import setup_memory # Avoid .. within tests
    # from handler.base_handler import BaseHandler # Avoid missing src. prefix
    ```

## Test Dependencies and Mocking

### Patching Strategy

*   **RULE:** Strongly prefer **`mocker.patch.object`** (from `pytest-mock`) or **`unittest.mock.patch.object`** over string-based patching targets (`mocker.patch('some.string.path')`).
*   **Reason:** `patch.object` requires you to import the *actual object* containing the method/attribute you want to patch. This avoids the complex and sometimes fragile import path resolution that string-based patching performs, which was the source of `AttributeError: module 'src' has no attribute 'main'` type errors. It's also more refactor-friendly.
*   **Workflow:**
    1.  Import the module/class containing the *original* item to be patched.
    2.  Use `mocker.patch.object(imported_module_or_class, 'attribute_name_as_string', ...)`.

    ```python
    # tests/integration/test_debug_fix_loop.py (Example)

    import pytest
    from unittest.mock import MagicMock
    import src.task_system.templates.aider_templates # 1. Import the actual module
    from src.main import Application

    @pytest.fixture
    def app_instance(mocker):
        # 2. Use patch.object with the imported module
        mocker.patch.object(
            src.task_system.templates.aider_templates,
            'register_aider_templates', # Patch the function within its defining module
            return_value=None,
            autospec=True
        )
        # ... other patches ...
        app = Application() # Now Application uses the patched function during init
        return app
    ```

### Fixtures

*   Use `pytest` fixtures (`@pytest.fixture`) for setting up test preconditions (e.g., creating temporary directories, database connections, mocked service objects) and tearing them down.
*   Place fixtures shared across multiple test files in the nearest `conftest.py`.
*   Use fixture scope (`function`, `class`, `module`, `session`) appropriately to optimize setup/teardown.
*   Use `autouse=True` sparingly, as it can sometimes make test dependencies less explicit.

### Handling Optional Dependencies

*   **RULE:** **Do not** use `try...except ImportError:` blocks *within test code* purely to check for optional dependencies (like `aider-chat`). This contradicts the "feature detection" approach mentioned in `project_rules.md`.
*   **Preferred Approaches:**
    *   **Source Code Guard:** Implement the check for the optional dependency within the *source code* itself. The source code can then provide placeholder functionality or raise a specific error if the dependency is missing. Tests can then assert the behavior with and without the dependency present (using mocking if needed).
    *   **`pytest.importorskip`:** If a test module *absolutely requires* an optional dependency to run *at all*, use `pytest.importorskip("optional_dependency")` at the top of the test module. This will gracefully skip the entire module if the import fails.

## Test Naming and Organization

*   Follow `pytest` discovery rules:
    *   Files: `test_*.py` or `*_test.py`
    *   Classes: `Test*` (must not have an `__init__` method unless necessary for specific reasons)
    *   Functions/Methods: `test_*`
*   Use descriptive names for test functions and classes that clearly indicate what they are testing.
*   Group related tests into classes if it improves structure and allows sharing setup/teardown via class-scoped fixtures or methods.

## Type Hinting

*   Use type hints extensively in both source code (`src/`) and test code (`tests/`).
*   Type hints improve readability, help static analysis tools, and make mocking with `autospec=True` more effective.

## Running Tests

*   Run the full test suite from the project's **root directory** using:
    ```bash
    pytest
    ```
*   Useful `pytest` options:
    *   `-v`: Verbose output.
    *   `-s`: Show output from `print` statements and logs (useful for debugging).
    *   `-k <expression>`: Run tests matching the keyword expression.
    *   `--lf`: Run only the tests that failed last time.
    *   `--ff`: Run failed tests first, then the rest.
    *   `-x`: Stop after the first failure.
    *   `--log-cli-level=DEBUG` (or `INFO`, `WARNING`): Control log level output during tests.
    *   `tests/path/to/specific_test.py`: Run only tests in a specific file.
    *   `tests/path/to/specific_test.py::TestClassName::test_method_name`: Run a specific test method.

## Linting and Formatting

*   Use code formatters (like `black`) and linters (like `flake8` with plugins like `flake8-pyproject`) to enforce code style and catch potential errors automatically.
*   Configure intelligent import sorting (using `isort`) compatible with `black`.
*   Consistent formatting improves readability and reduces cognitive load when switching between files.

