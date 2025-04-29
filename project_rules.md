# Project Rules and Conventions

## Directory Structure

```
project_root/
├── src/                     # Main source code
│   ├── aider_bridge/        # Aider integration components
│   │   ├── __init__.py
│   │   ├── automatic.py     # Automatic Aider handler
│   │   ├── bridge.py        # Bridge component for Aider integration
│   │   ├── interactive.py   # Interactive Aider session manager
│   │   ├── result_formatter.py # Formats Aider operation results
│   │   └── tools.py         # Aider tool specifications
│   │
│   ├── evaluator/           # Evaluator components
│   │   ├── __init__.py
│   │   ├── evaluator.py     # Main Evaluator implementation
│   │   └── interfaces.py    # Evaluator interfaces
│   │
│   ├── handler/             # Handler components
│   │   ├── __init__.py
│   │   ├── base_handler.py  # Base handler implementation
│   │   ├── command_executor.py # Command execution utilities
│   │   ├── file_access.py   # File access manager
│   │   ├── model_provider.py # Model provider adapters
│   │   └── passthrough_handler.py # Passthrough mode handler
│   │
│   ├── memory/              # Memory system components
│   │   ├── __init__.py
│   │   ├── memory_system.py # Main Memory System implementation
│   │   └── indexers/        # File indexing modules
│   │       ├── __init__.py
│   │       ├── git_repository_indexer.py
│   │       └── text_extraction.py
│   │
│   ├── repl/                # REPL interface
│   │   ├── __init__.py
│   │   └── repl.py
│   │
│   ├── scripts/             # Utility scripts
│   │   ├── test_aider_flow.py
│   │   └── test_handler_manual.py
│   │
│   ├── system/              # System-wide utilities
│   │   ├── __init__.py
│   │   └── errors.py        # Error handling utilities
│   │
│   ├── task_system/         # Task system components
│   │   ├── __init__.py
│   │   ├── ast_nodes.py     # AST node definitions
│   │   ├── mock_handler.py  # Mock handler for testing
│   │   ├── task_system.py   # Main Task System implementation
│   │   ├── template_processor.py # Template processing utilities
│   │   ├── template_utils.py # Template utility functions
│   │   └── templates/       # Task templates
│   │       ├── __init__.py
│   │       ├── associative_matching.py
│   │       └── function_examples.py # Function template examples
│   │
│   └── main.py              # Application entry point
│
├── tests/                   # Test directory (mirrors src structure)
│   ├── __init__.py
│   ├── conftest.py          # Common test fixtures
│   ├── evaluator/           # Evaluator tests
│   │   └── test_evaluator.py
│   ├── handler/             # Handler tests
│   │   ├── test_command_executor.py
│   │   └── test_handler_passthrough.py
│   ├── integration/         # Integration tests
│   │   └── test_enhanced_file_paths.py
│   ├── memory/              # Memory system tests
│   │   └── test_memory_system_indexing.py
│   ├── task_system/         # Task system tests
│   │   ├── test_file_path_resolution.py
│   │   ├── test_function_call_integration.py
│   │   └── test_integration.py
│   └── test_tool_invocation.py
│
├── devdocs/                 # Development documentation
│   └── examples/
│       └── sysprompt.py
│
├── test_aider_integration.py # Aider integration tests
├── test_matching.py         # Associative matching tests
├── pytest.ini               # pytest configuration
└── README.md                # Project documentation
```

### IDL File Conventions

Interface Definition Language (IDL) files (`*_IDL.md`) are the primary specification for public component contracts.

*   **Primary Location:** The authoritative IDL file defining the public contract for a Python module or class **should reside directly alongside its implementation file** in the `src/` directory (e.g., `src/handler/base_handler_IDL.md` alongside `src/handler/base_handler.py`). This ensures the specification and implementation are co-located.
*   **Internal Helpers:** Internal helper classes or modules designed solely to support the implementation of a public interface (and not intended for direct use by other independent components) generally **do not require their own separate IDL file**. However, the delegation of work to such helpers should be documented in the `Behavior` section of the public interface's method(s) that use them (see `docs/IDL.md`). Examples include `FileContextManager` and `LLMInteractionManager` within `src/handler/`.
*   **API Documentation vs. IDL Contract:** High-level API summaries or alternative representations *may* exist under `docs/components/<component>/api/interfaces.md`. However, for implementation purposes, the `_IDL.md` file located within the `src/` directory is considered the **definitive contract**. Any discrepancies should favor the `_IDL.md` file, and the `.md` API docs should ideally be kept in sync or clearly marked as supplementary.
*   **Pending/Top-Level Components:** IDLs for components whose implementation is pending (e.g., `SexpEvaluator`, `Dispatcher` in early phases) or whose primary execution script does not reside under `src/` (e.g., `main.py`) might temporarily exist at a higher level (like `src/`). Upon implementation, these IDLs should ideally be moved to be adjacent to their corresponding code.
*   **(Maintainer Note):** The project structure diagram in this document should be periodically verified against the actual `src/` and `tests/` directory layout to ensure accuracy, especially regarding component locations.

## Script Conventions

### Script Organization

1. **Script Structure**:
   - All scripts should have a shebang line: `#!/usr/bin/env python`
   - Include a descriptive docstring at the top of the file
   - Add usage examples in the docstring
   - Use `if __name__ == "__main__":` pattern for executable scripts

2. **Path Management**:
   - Always add the project root to the Python path at the beginning of scripts:
     ```python
     # Add the project root to the Python path
     sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
     ```
   - Use absolute paths when working with files
   - Handle path resolution consistently across different operating systems

3. **Command-line Arguments**:
   - Use `argparse` for scripts that require command-line arguments
   - Provide helpful descriptions for each argument
   - Include default values where appropriate
   - Add `--help` output that explains script usage

4. **Error Handling**:
   - Include appropriate error handling for file operations
   - Provide clear error messages for common failure scenarios
   - Use try/except blocks to gracefully handle exceptions
   - Exit with appropriate status codes

## Coding Guidelines

### General Principles

1. **KISS (Keep It Simple, Stupid)**: 
   - Prefer simple, direct implementations over complex abstractions
   - Solve the problem at hand, not potential future problems
   - Implement only what's needed to satisfy requirements

2. **YAGNI (You Aren't Gonna Need It)**:
   - Don't add functionality until it's necessary
   - Avoid speculative features
   - Focus on current requirements

3. **Duck Typing**:
   - Leverage Python's dynamic typing
   - Avoid unnecessary abstract base classes or formal interfaces
   - Document expected behavior with docstrings

4. **Shared System Types:**
   - System-wide shared data structures (e.g., Pydantic models for `TaskResult`, `ContextGenerationInput`, `TaskError`) used across multiple components **MUST** be defined in the designated shared types module: `src/system/models.py`.
   - Avoid defining these common types within specific component directories.

### Code Formatting and Style

1. **Follow PEP 8**:
   - 4 spaces for indentation
   - 79 character line limit (88 if using Black)
   - Use snake_case for variables, functions, and methods
   - Use CamelCase for classes

2. **Docstrings and Comments**:
   - Use Google style docstrings
   - Document all classes, methods, and functions
   - Include parameter descriptions and return value information
   - Add type hints to complement docstrings

3. **Imports**:
   - Group imports in the following order:
     1. Standard library imports
     2. Related third-party imports
     3. Local application/library specific imports
   - Use absolute imports for clarity

4. **Import Placement**:
   - Place imports at the module level, not inside functions or methods
   - Exception: Only use local imports when absolutely necessary to avoid circular imports or 
     to defer importing optional dependencies that might be unavailable
   - Document any local imports with a comment explaining the rationale
   - For optional dependencies, provide a fallback mechanism and clear error messages

### Type Hints

1. **Usage**:
   - Add type hints to all function and method signatures
   - Use the typing module for complex types
   - Include return type annotations
   - Use Optional for parameters that might be None

2. **Type Hint Style**:
   ```python
   from typing import Dict, List, Optional, Any

   def example_function(param1: str, param2: Optional[int] = None) -> Dict[str, Any]:
       """Example function with type hints.
       
       Args:
           param1: Description of param1
           param2: Description of param2, defaults to None
           
       Returns:
           Dictionary with string keys and values of any type
       """
       pass
   ```

### Module Length Guideline

*   **Guideline:** Strive to keep Python modules (`.py` files) concise. **Aim for modules to be no longer than 300 lines of code (LoC)**, excluding blank lines and comments where reasonable to estimate.
*   **Rationale:** Shorter modules are generally easier to read, understand, test, and maintain. This guideline encourages adherence to the Single Responsibility Principle (SRP), prompting developers to break down complex functionality into smaller, more focused units (e.g., separate classes or functions in different modules).
*   **Action:** If a module is approaching or exceeding this limit, consider if:
    *   Classes or utility functions can be extracted into separate files within the same package.
    *   The module is trying to do too many distinct things and can be split logically.
*   **Exceptions:** This is a guideline, not a strict rule enforced by tooling (unless configured separately). If keeping related logic together necessitates exceeding the limit for clarity, that may be acceptable, but be prepared to justify it during code review. Use your judgment – a well-structured 350-line file can be better than two poorly split 175-line files.

## Testing Strategy

### Test Organization

1. **Directory Structure**:
   - Test directory mirrors main code structure
   - Test files named with `test_` prefix
   - Test classes named with `Test` prefix
   - Test methods named with `test_` prefix

2. **Test Categorization**:
   - Unit tests: Test individual components in isolation
   - Integration tests: Test interactions between components
   - Mark tests appropriately using pytest markers

3. **Test File Naming**:
   - `test_[module].py` for module tests
   - Place test files in directories mirroring the module structure

### Test Design Patterns

1. **Arrange-Act-Assert**:
   - Structure tests with clear arrangement, action, and assertion phases
   - Keep test setup code minimal and focused on what's being tested
   - Use descriptive variable names that clarify test intent

2. **Test Doubles**:
   - Use the appropriate test double for each situation:
     * Stubs: For providing indirect inputs
     * Mocks: For verifying indirect outputs
     * Spies: For verifying indirect outputs without breaking tests
     * Fakes: For simulating complex components
   - Create reusable test doubles for commonly used dependencies

### Test Implementation

1. **pytest as Testing Framework**:
   - Use pytest fixtures for test setup
   - Use parametrize for testing multiple cases
   - Use markers to categorize tests

2. **Mocking Strategy**:
   - Use pytest's monkeypatch or unittest.mock
   - Create mock objects for external dependencies
   - Use fixtures in conftest.py for common mocks

3. **Testing Patterns**:
   - Test initialization and simple behaviors for all components
   - Create stubs for methods that will be implemented later
   - Use descriptive test method names that explain what's being tested

4. **Test Coverage**:
   - Aim for high test coverage of business logic
   - Test both success and failure paths
   - Include edge cases in tests

5. **Testing with External Dependencies**:
   - Create dedicated mock objects for external libraries
   - Use feature detection pattern in code rather than try/except for imports in tests
   - For optional dependencies, test both presence and absence code paths
   - Consider using pytest skipif markers for tests that require specific dependencies
   - Use side_effect in mocks to return appropriate values for different inputs

6. **Mock Verification**:
   - Always verify that mocked methods were called as expected
   - Check both call count and arguments passed to mocks
   - Use assert_called_once(), assert_called_with() and similar methods
   - For complex interactions, use mock.call_args_list to verify call sequence

### Integration Testing

1. **Component Integration Tests**:
   - Test interactions between directly related components
   - Use realistic test data
   - Mock external dependencies

2. **End-to-End Tests**:
   - Test the entire flow from user input to response
   - Limit to key workflows to avoid brittleness
   - Use integration test markers

## Component Interaction Rules

1. **Dependency Management**:
   - Pass dependencies explicitly via constructor
   - Avoid global state
   - Use dependency injection for testability

2. **Error Handling**:
   - Use exceptions for error conditions
   - Document exceptions in docstrings
   - Handle exceptions at appropriate levels

3. **Context Management**:
   - Follow the established context management approach
   - Use standard settings for consistent behavior
   - Document any deviations from standard patterns

## Git Workflow

1. **Branching Strategy**:
   - main/master: Stable releases
   - develop: Integration branch
   - feature branches: New features (feature/name-of-feature)
   - fix branches: Bug fixes (fix/issue-description)

2. **Commit Guidelines**:
   - Write descriptive commit messages
   - Use present tense in commit messages
   - Reference issue numbers when applicable

3. **Code Review Process**:
   - All code changes require review
   - Tests must pass before merging
   - Documentation updates should accompany code changes

### Key Libraries and Standards

*   **S-Expression Parsing:** For parsing programmatic workflow definitions provided as S-expressions (e.g., via the `/task` command), this project uses the **`sexpdata`** library.
    *   **Rationale:** `sexpdata` is chosen for its simplicity, direct focus on S-expression syntax, and its ability to parse input strings into standard Python data structures (lists, tuples, symbols, literals) that are easily processed by the `SexpEvaluator`.
    *   **Usage:** Primarily used by the `SexpParser` component.
