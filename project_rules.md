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
