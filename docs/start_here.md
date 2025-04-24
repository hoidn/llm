**`docs/start_here.md`**

# Developer Orientation: Getting Started with the Project

**Welcome!** This document is your starting point for understanding how we build software in this project. Our approach emphasizes clear specifications and consistent implementation patterns. Please read this guide carefully before diving into the code.


**1. Core Philosophy: IDL as the Specification**

The cornerstone of our development process is the use of **Interface Definition Language (IDL)** files (`*_IDL.md`).

*   **IDL is the Contract:** Each IDL file defines a strict **contract** for a specific component (module or interface). It specifies *what* the component must do, its public interface, its expected behavior, its dependencies, and its error conditions.
*   **Specification, Not Implementation:** The IDL focuses on the **behavioral specification** and separates it from the *how* (the Python implementation details).
*   **Source of Truth:** When implementing a component, its corresponding `_IDL.md` file is the authoritative source for its requirements.
*   **Bidirectional Goal:** We use IDL both to *specify* new components before coding (IDL-to-Code) and to *document* the essential contract of existing components by abstracting away implementation details (Code-to-IDL).

> **Further Reading:** For the detailed syntax and rules for creating/reading IDL, refer to `docs/IDL.md`.

**2. Understanding the IDL Structure (`*_IDL.md` files)**

When you open an `_IDL.md` file (e.g., `src/handler/base_handler_IDL.md`), you'll typically find:

*   **`module src.some.path`**: Defines the logical grouping, corresponding to the Python module path.
*   **`# @depends_on(...)`**: Declares dependencies on *other IDL-defined interfaces/modules*. This signals required interactions.
*   **`# @depends_on_resource(...)`**: Declares dependencies on *abstract external resources* (like `FileSystem`, `Database`, `ExternalAPI`).
*   **`interface InterfaceName`**: Defines the contract for a specific class. The name typically matches the Python class name.
*   **Method Definitions (`returnType methodName(...)`)**:
    *   **Signature:** Specifies the method name, parameter names, parameter types (`string`, `int`, `list<Type>`, `dict<Key,Val>`, `optional Type`, `union<T1, T2>`, `object` for other interfaces), and the return type.
    *   **Documentation Block (CRITICAL - This IS the Spec!):**
        *   **`Preconditions:`**: What must be true *before* calling the method.
        *   **`Postconditions:`**: What is guaranteed *after* the method succeeds (return values, state changes).
        *   **`Behavior:`**: A description of the essential logic/algorithm the method performs and how it interacts with dependencies.
        *   **`Expected JSON format: { ... }`**: If a parameter or return type is a complex dictionary passed as JSON, its structure is defined here.
        *   **`@raises_error(condition="ErrorCode", ...)`**: Defines specific, contractual error conditions the method might signal.
    *   **`Invariants:`** (Optional): Properties of the component's state that should always hold true between method calls.

**3. The Development Workflow: Implementing from IDL**

When assigned to implement or modify a component specified by an IDL:

1.  **Locate the IDL:** Find the relevant `*_IDL.md` file (e.g., `src/memory/memory_system_IDL.md`).
2.  **Understand the Contract:** Read the `module` and `interface` descriptions, paying close attention to `@depends_on*`, `Preconditions`, `Postconditions`, `Behavior`, and `@raises_error` annotations for each method you need to implement.
3.  **Create/Modify Python File:** Ensure the Python file structure matches the IDL module path (e.g., `src/memory/memory_system.py`).
4.  **Implement the Class/Interface:** Create a Python class matching the IDL `interface` name.
5.  **Implement Methods:**
    *   Define methods matching the IDL signatures **exactly** (name, parameters, type hints).
    *   Use Python type hints (`str`, `int`, `bool`, `Optional`, `Union`, `List`, `Dict`, `Any`, custom classes/Pydantic models) that correspond precisely to the IDL types.
    *   Implement the logic described in the `Behavior` section.
    *   Ensure your implementation fulfills the `Postconditions`.
    *   Respect the `Preconditions` (often handled by type hints or initial checks).
    *   Handle the specific error conditions documented with `@raises_error` by raising appropriate exceptions (preferably custom exceptions from `src.system.errors` or standard Python exceptions).
6.  **Handle Dependencies:** Use **constructor injection** to receive instances of components declared in `@depends_on`.
7.  **Handle Complex Parameters:** If the IDL specifies an `Expected JSON format`, define a Pydantic model for that structure and use it for parsing/validation (see Section 5 below).
8.  **Write Tests:** Implement tests (see Section 7) that verify your code meets *all aspects* of the IDL contract (behavior, postconditions, error handling).
9.  **Adhere to Rules:** Follow all coding standards outlined below and in `docs/implementation_rules.md`.

> **Key Rule:** The IDL is a **strict contract**. Your Python implementation **must** fulfill all requirements specified in the IDL for the public interface. Do not change signatures or deviate from the documented behavior.

**4. Key Coding Standards**

*   **Python Version:** [Specify target Python version, e.g., 3.10+]
*   **Formatting:** PEP 8 compliant, enforced by Black & Ruff (run `make format` / `make lint`).
*   **Type Hinting:** **Mandatory** for all signatures. Use standard `typing` types. Be specific.
*   **Docstrings:** **Mandatory** for all modules, classes, functions, methods. Use **Google Style**.
*   **Imports:** Use **absolute imports** from `src`. Group imports correctly. Top-level only unless exceptional reason exists (document it).
*   **Naming:** PEP 8 (snake_case for functions/variables, CamelCase for classes).

> **Further Reading:** See `docs/implementation_rules.md` and `docs/project_rules.md` for complete details.

**5. Important Patterns & Principles**

*   **Parse, Don't Validate (with Pydantic):**
    *   **Concept:** Instead of validating raw data (like dicts) inside your logic, parse it into a Pydantic `BaseModel` at the component boundary. This ensures you work with validated, typed objects internally.
    *   **Practice:** Define Pydantic models for complex data structures (especially those documented via `Expected JSON format` in IDL). Use `YourModel.model_validate(data)` in a `try...except ValidationError` block to parse inputs.
    *   **Reference:** See Section 5 in `docs/implementation_rules.md`.
*   **Dependency Injection:**
    *   **Concept:** Components receive their dependencies (other components, resources) via their constructor (`__init__`). Avoid global state or direct instantiation of dependencies within methods.
    *   **Practice:** Identify dependencies from IDL (`@depends_on`). Add corresponding parameters to your class `__init__` method with type hints. Store references as instance attributes (e.g., `self.memory_system = memory_system`).
*   **(Conceptual) Provider-Agnostic LLM Interface:**
    *   **Goal:** Interact with different LLMs (OpenAI, Anthropic) through a consistent interface.
    *   **Practice:** Use the `ProviderAdapter` interface (`src/handler/model_provider_IDL.md`) for LLM calls. Consider `pydantic-ai` patterns if integrating that library later.
    *   **Reference:** See Section 6 in `docs/implementation_rules.md`.

**6. Testing Strategy**

*   **Framework:** `pytest`.
*   **Focus:** Prioritize **Integration and Functional/End-to-End tests** over isolated unit tests. Verify components work together correctly.
*   **Mocking:** **Minimize mocking.** Mock only at external boundaries (LLM APIs, external services) or where strictly necessary for isolation/speed. Prefer using real instances or simple fakes/stubs configured for the test case.
*   **Fixtures:** Use `pytest` fixtures (`tests/conftest.py`) for test setup (e.g., creating component instances with test configurations or mocked boundaries).
*   **Structure:** Follow the `Arrange-Act-Assert` pattern. Mirror the `src` directory structure in `tests`.

> **Further Reading:** See Section 7 in `docs/implementation_rules.md`.

**7. Project Navigation**

*   **`src/`**: Main Python source code, organized by component.
*   **`tests/`**: Pytest tests, mirroring the `src` structure.
*   **`docs/`**: All project documentation, including architecture, decisions (ADRs), component specs, and these rules.
    *   **`docs/IDL.md`**: Defines the IDL guidelines themselves.
    *   **`docs/implementation_rules.md`**: Detailed coding and testing rules.
    *   **`docs/project_rules.md`**: General project conventions (directory structure, Git workflow).
    *   **`src/**/\*_IDL.md`**: The specific interface definitions you will implement.
*   **`README.md`**: Top-level project overview.

**8. Getting Started Checklist**

1.  [ ] Read this document (`developer_orientation.md`).
2.  [ ] Read `docs/IDL.md` to understand IDL syntax and guidelines.
3.  [ ] Read `docs/implementation_rules.md` for detailed coding/testing rules.
4.  [ ] Read `docs/project_rules.md` for project structure and Git workflow.
5.  [ ] Review the main `README.md` and key architecture diagrams (`docs/system/README.md`, `docs/system/architecture/overview.md`).
6.  [ ] Set up your local development environment (Python version, dependencies via `make install` or `uv sync`, pre-commit hooks).
7.  [ ] Browse the `src/` directory and a few `*_IDL.md` files to see the structure in practice.
8.  [ ] Try running the tests (`pytest tests/`).
9.  [ ] Ask questions!

Welcome aboard! By following these guidelines, we can build a robust, maintainable, and consistent system together.
