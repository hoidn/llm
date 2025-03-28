# Project Rules and Conventions

## Directory Structure

```
project_root/
├── memory/                  # Memory system components
│   ├── __init__.py
│   ├── memory_system.py     # Main Memory System implementation
│   └── indexers/            # File indexing modules
│       ├── __init__.py
│       └── git_repository_indexer.py
│
├── handler/                 # Handler components
│   ├── __init__.py
│   ├── handler.py           # Main Handler implementation
│   └── passthrough_handler.py  # Passthrough mode extension
│
├── task_system/             # Task system components
│   ├── __init__.py
│   ├── task_system.py       # Main Task System implementation
│   └── templates/           # Task templates
│       ├── __init__.py
│       └── associative_matching.py
│
├── repl/                    # REPL interface
│   ├── __init__.py
│   └── repl.py
│
├── tests/                   # Test directory (mirrors main structure)
│   ├── __init__.py
│   ├── conftest.py          # Common test fixtures
│   ├── memory/              # Memory system tests
│   ├── handler/             # Handler tests
│   ├── task_system/         # Task system tests
│   └── repl/                # REPL tests
│
├── main.py                  # Application entry point
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
