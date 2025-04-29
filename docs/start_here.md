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
*   **`struct StructName { ... }` (Optional):** Defines reusable, complex data structures. These might be defined within the IDL file itself or in a central `docs/types.md` file for globally shared types (like `TaskResult`). These struct names can then be used as types in method signatures.

<idl to code>
**3. The Development Workflow: Implementing from IDL (Expanded)**

When assigned to implement or modify a component specified by an IDL (or tackling a new feature):

**Phase 0: Preparation & Understanding**

1.  **Define Task:** Clearly understand the goal (e.g., from an issue tracker, user story).
2.  **Locate/Review IDL:** Find the relevant `*_IDL.md` file(s). If modifying existing code without a complete IDL, consider generating/updating the IDL first (Code-to-IDL).
3.  **Understand Contract:** Thoroughly read the IDL: `module`/`interface` purpose, `@depends_on*`, function/method signatures, and especially the documentation blocks (`Preconditions`, `Postconditions`, `Behavior`, `Expected JSON format`, `@raises_error`).
4.  **Review Rules:** Briefly refresh understanding of key guidelines in `docs/implementation_rules.md` and `docs/project_rules.md`.
5.  **Setup Working Memory:** Update `docs/memory.md` with your "Current Task/Focus" and initial "Next Steps".

**Phase 1: Core Implementation & Unit/Integration Testing ("Main Step")**

6.  **Create/Modify Files:** Ensure Python file/directory structure matches the IDL `module` path (e.g., `src/component/module.py` for `src.component.module`).
7.  **Implement Structure & Dependencies:**
    *   If the IDL defines an `interface`, create the corresponding Python class. Implement its constructor (`__init__`), injecting dependencies specified in `@depends_on`.
    *   If the IDL defines module-level functions, ensure the module exists. Handle any module-level setup or configuration needed. Dependencies specified in `@depends_on` might be injected into functions directly as parameters or managed via module initialization.
8.  **Implement Functions/Methods:**
    *   Define function/method signatures **exactly** matching the IDL (name, parameters, type hints corresponding to IDL types).
    *   Implement the logic described in the `Behavior` section.
    *   Use Pydantic models for complex `Expected JSON format` parameters/returns (Parse, Don't Validate).
    *   Ensure your implementation fulfills the `Postconditions`.
    *   Respect `Preconditions` (often handled by type hints or initial checks).
    *   Implement `raise` statements for specific exceptions documented with `@raises_error`.
9.  **Write Tests:**
    *   If appropriate for the component, write `pytest` tests (prioritizing integration/functional tests) that verify your implementation against the *entire* IDL contract:
        *   Does it perform the described `Behavior`?
        *   Does it meet the `Postconditions`?
        *   Does it correctly handle specified `Error Conditions` (`@raises_error`)?
        *   Does it handle edge cases implied by `Preconditions`?
10. **Log Progress:** Update `docs/memory.md` (Recent Activity, Notes, Blockers) as you make progress or encounter issues.

**Phase 2: Finalization & Sanity Checks ("Cleanup Step")**

11. **Format Code:** If possible, run the project's code formatter (e.g., `make format` or `black .`).
12. **Lint Code:** If possible, run the project's linter (e.g., `make lint` or `ruff check . --fix`) and address all reported issues.
13. **Run All Tests:** If possible, execute the full test suite (e.g., `pytest tests/` or `make test`) and ensure all tests pass.
14. **Perform Sanity Checks:**
    *   **Self-Review:** Read through your code. Is it clear? Simple? Are comments/docstrings accurate?
    *   **Implementation Rules Check:** Does the code adhere to `docs/implementation_rules.md` (imports, naming, patterns, etc.)?
    *   **Project Rules Check:** Does the code adhere to `docs/project_rules.md`?
        *   **(Guideline Check): Is any module significantly longer than the recommended limit (e.g., 300 lines)?** If yes, evaluate if refactoring/splitting the module makes sense for clarity and maintainability. *If you refactor, go back to the formatting, linting and testing steps before proceeding.*
    *   **Update Directory Structure Doc:** If your changes added, removed, or renamed files/directories, update the structure diagram in `project_rules.md` to reflect the current state.
    *   **IDL Check:** Does the final code *still* precisely match the public contract defined in the IDL (signatures, error conditions)?
    *   **(New) Configuration Check:** Verify that related configuration files (especially test setups like `tests/conftest.py`) have been updated if your changes affect shared types, interfaces, or component instantiation relied upon by tests or fixtures. Ensure imports point to the correct new locations.
15. **Finalize Working Memory:** Update `docs/memory.md` with the final status and any relevant closing thoughts or context, including lessons learned (if any debugging was done) and guidance for the next steps. 
</idl to code>

---

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
*   **LLM Interaction (via Pydantic-AI):**
    *   **Standard:** The project uses the `pydantic-ai` library for interacting with LLMs.
    *   **Practice:** `BaseHandler` uses an internal `LLMInteractionManager` to manage the `pydantic-ai` `Agent`. Implementations within `BaseHandler` delegate LLM calls to this manager. Tool registration (`register_tool`) stores tool definitions, and making them available to the live agent requires careful integration (see `implementation_rules.md`).
    *   **Reference:** See Section 6 in `docs/implementation_rules.md` and `docs/librarydocs/pydanticai.md`.

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
    *   `docs/system/contracts/types.md`: Defines shared system-wide data structures (`struct`/Pydantic model definitions) used across multiple IDL interfaces (e.g., `TaskResult`).
    *   **`docs/implementation_rules.md`**: Detailed coding and testing rules.
    *   **`docs/project_rules.md`**: General project conventions (directory structure, Git workflow).
    *   **`src/**/\*_IDL.md`**: The specific interface definitions you will implement.
*   **`README.md`**: Top-level project overview.

**9. Development Workflow & Recommended Practices**

*   **Follow the IDL:** Adhere strictly to the IDL specification (`*_IDL.md`) for the component you are implementing (See Section 3).
*   **Use Working Memory:** Maintain a running log of your development progress, current focus, and next steps in `docs/memory.md`. Update it frequently during your work session and commit it along with your code changes. This aids context retention for yourself and helps reviewers understand the development path. (See `docs/memory.md` for the template and detailed guidelines).
*   **Be Aware of Existing Code & Configuration:** When implementing new components or modifying existing ones, always consider how your changes might affect related parts of the codebase, *especially configuration files (like `tests/conftest.py`)*, test setups, and integration points. Verify that related files are updated accordingly.
*   **Test Driven:** Write tests (especially integration tests) to verify your implementation against the IDL contract (See Section 6 and `docs/implementation_rules.md`).
*   **Commit Often:** Make small, logical commits with clear messages. Follow Git guidelines in `docs/project_rules.md`.
*   **Format and Lint:** Run `make format` and `make lint` (or equivalent project commands) before committing to ensure code style compliance.
*   **Ask Questions:** Don't hesitate to ask for clarification on requirements or design if you are unsure.

---

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
