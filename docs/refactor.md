# Refactoring Guide

**1. Purpose**

This guide provides conventions and a recommended workflow for refactoring code within this project. Refactoring is the process of restructuring existing computer code – changing the factoring – without changing its external behavior. It aims to improve non-functional attributes like readability, maintainability, simplicity, and adherence to design principles (like SRP).

**Related Documents:**
*   `docs/implementation_rules.md` (Coding standards)
*   `docs/project_rules.md` (Module length guideline, Git workflow)
*   `docs/memory.md` (Developer working memory log)

**2. When to Refactor**

Consider refactoring when you encounter:

*   **Code Smells:** Duplicated code, long methods/classes, complex conditional logic, excessive parameters, tight coupling, etc.
*   **Module Length:** A module significantly exceeds the guideline set in `docs/project_rules.md` (e.g., > 300 LoC).
*   **Complexity:** A component becomes difficult to understand, test, or modify.
*   **Poor Cohesion:** A module or class handles too many unrelated responsibilities.
*   **New Requirements:** Adapting existing code for new features reveals structural weaknesses.
*   **Technical Debt:** Addressing known shortcuts or suboptimal designs.

**3. General Principles**

*   **Small, Incremental Steps:** Break down large refactorings into smaller, manageable changes.
*   **Test Frequently:** Run tests after each small step to ensure behavior is preserved.
*   **Preserve External Behavior:** The primary goal is to improve internal structure *without* altering how the component interacts with others (its public contract/API). If the contract *must* change, it's technically more than just refactoring and requires careful consideration of dependents.
*   **Improve Structure:** Focus on enhancing clarity, reducing complexity, and improving modularity (e.g., better adherence to SRP).
*   **Use Version Control:** Commit frequently with clear messages describing each refactoring step.

**4. Formalized Refactoring Decision Workflow**

This section outlines a structured approach for identifying refactoring needs, analyzing candidates, choosing a strategy, and verifying the results. It complements the execution steps described in the next section.

**Phase 1: Identification & Initial Assessment**

*   **Input:**
* Code base or component under review
* Project quality metrics (if available)
* Developer observations/pain points

*   **Actions:**
* Scan for code smells (duplicated code, long methods, complex conditionals, etc.)
* Review module length against guidelines in `docs/project_rules.md`
* Identify components with high change frequency or bug density
* Note areas where developers frequently express confusion or frustration
* Check for violations of project architecture or implementation rules
* Run automated checks (e.g., line count, cyclomatic complexity) to identify overly long or complex components

*   **Output:**
* List of refactoring candidates with brief descriptions of issues
* Initial severity assessment (High/Medium/Low) based on:
  * Impact on development velocity
  * Risk of introducing bugs
  * Maintenance burden
  * Violation of core architectural principles

**Phase 2: Detailed Analysis**

*   **Input:**
* Refactoring candidates from Phase 1
* Relevant documentation (IDL files, architecture diagrams)
* Test coverage reports

*   **Actions:**
* For each high-priority candidate:
  * Analyze dependencies (what components depend on this code?)
  * Assess test coverage (is behavior well-tested?)
  * Identify specific design problems (SRP violations, tight coupling, etc.)
  * Analyze complexity metrics (e.g., cyclomatic complexity) to pinpoint complex areas within the code
  * Determine root causes (why did the code evolve this way?)
  * Estimate effort required to refactor
  * Evaluate risks (complexity, potential for regression)

*   **Output:**
* Detailed analysis document for each candidate, including:
  * Specific problems identified
  * Dependencies and potential impact areas
  * Test coverage assessment
  * Effort estimate (story points or time)
  * Risk assessment

**Phase 3: Strategy Selection**

*   **Input:**
* Detailed analysis from Phase 2
* Project priorities and constraints
* Available developer resources

*   **Actions:**
* For each refactoring candidate, select an appropriate strategy:
  * **Extract Method/Class:** For cohesive chunks of functionality that can be isolated
  * **Move Method/Field:** For functionality in the wrong place
  * **Replace Conditional with Polymorphism:** For complex conditional logic
  * **Introduce Parameter Object:** For methods with too many parameters
  * **Replace Temp with Query:** For complex calculations with intermediate variables
  * **Decompose Conditional:** For complex conditional expressions
  * **Extract Interface:** For clients that use only a subset of a class's methods
  * **Introduce Dependency Injection:** For tight coupling to concrete implementations
  * **Rename:** For unclear or misleading names
  * **Inline Method/Class:** For unnecessary indirection
  * **Consolidate Duplicate Conditional Fragments:** For repeated code in conditionals
  * **Replace Magic Number with Symbolic Constant:** For unexplained literals
  * **Encapsulate Field:** For direct field access that should be controlled
  * **Replace Exception with Test:** For using exceptions for control flow
  * **Introduce Assertion:** For assumptions that should be explicit

*   **Output:**
* Refactoring plan for each candidate, including:
  * Selected strategy or combination of strategies
  * Specific steps to implement the strategy
  * Acceptance criteria for the refactored code
  * Prioritization relative to other refactoring tasks

**Phase 4: Planning & Preparation**

*   **Input:**
* Refactoring plans from Phase 3
* Project schedule and priorities
* Test infrastructure status

*   **Actions:**
* Break down large refactorings into smaller, incremental steps
* Identify or create tests that verify the current behavior
* Ensure test coverage is adequate before starting
* Schedule refactoring work, considering:
  * Project deadlines and priorities
  * Developer availability and expertise
  * Dependencies between refactoring tasks
  * Risk level (higher risk = more careful planning)
* Update `docs/memory.md` with the refactoring task

*   **Output:**
* Detailed, step-by-step refactoring plan with:
  * Specific files and code sections to modify
  * Order of operations to minimize merge conflicts
  * Test strategy for each step
  * Rollback plan if problems arise
  * Documentation updates needed

**Phase 5: Verification & Cleanup**

*   **Input:**
* Completed refactoring changes
* Test results
* Code review feedback

*   **Actions:**
* Verify all tests pass (existing and new)
* Conduct code review to ensure the refactoring meets quality standards
* Check for any unintended side effects or regressions
* Update documentation to reflect the new structure
* Remove any dead code or unused imports
* Run linters and formatters
* Update `docs/memory.md` with the completed refactoring

*   **Output:**
* Verified, clean, refactored code
* Updated documentation
* Lessons learned for future refactorings

Once a refactoring strategy is chosen (Phase 3) and planned (Phase 4), the execution steps often follow the patterns described in the next section.

**6. Recommended Refactoring Workflow**

This workflow is based on successful refactoring patterns observed in this project:

1.  **Identify & Plan:**
    *   Clearly define the scope: What specific code section or responsibility are you refactoring? (e.g., "Extract file context logic from BaseHandler").
    *   Determine the target structure: Will you extract a function, a class, move code to a different module?
    *   Update `docs/memory.md` with your refactoring task.

2.  **Ensure Test Coverage (Before Refactoring):**
    *   Review existing tests for the code being refactored. Do they adequately cover its current *external behavior*?
    *   **Crucial:** If coverage is insufficient, **write tests first** to capture the current behavior before changing anything. These tests act as a safety net.

3.  **Extract Mechanically:**
    *   Create the new function, class, or module.
    *   Carefully move the identified code block(s) to the new location.
    *   Ensure necessary imports are added to the new location.

4.  **Delegate / Integrate:**
    *   Modify the original code location to *call* or *use* the newly extracted code/component.
    *   Pass necessary data or dependencies to the new code.
    *   Ensure imports are updated in the original location.

5.  **Adapt Tests (After Refactoring):**
    *   Run the existing tests. They will likely fail.
    *   **Modify Original Tests:**
        *   Identify tests that now fail because they relied on the *internal implementation* that was moved.
        *   Update these tests to mock the *newly extracted dependency* (the function/class you created).
        *   Change assertions to verify that the original code now correctly *delegates* the call to the mock with the expected arguments.
        *   Remove assertions that tested the internal logic which is now gone from the original component.
    *   **Add New Tests:**
        *   Write new, focused tests specifically for the *extracted component*. These tests should cover the logic that was moved, treating the extracted component as the unit under test. Mock *its* dependencies if necessary.
    *   Run all relevant tests again until they pass.

6.  **Clean Up:**
    *   Remove any dead code (e.g., unused private methods, old imports) from the original location.
    *   Run linters and formatters (`make lint`, `make format`).
    *   Review the changes for clarity and simplicity.

7.  **Document:**
    *   Update `docs/memory.md` reflecting the completed refactoring step and commit hash.
    *   If the refactoring changed any public interfaces or introduced significant structural changes visible to other components, consider if corresponding IDL files or architecture diagrams need updates.

**7. Common Pitfalls & How to Avoid Them**

*   **Breaking Behavior:** Accidentally changing what the code does.
    *   **Avoidance:** Ensure good test coverage *before* starting. Test frequently after small steps.
*   **Brittle Tests:** Tests failing due to internal restructuring, even if external behavior is correct.
    *   **Avoidance:** Design tests to verify the component's *contract* and *behavior*, not its specific internal implementation steps. Mock primarily at the boundaries of the component under test.
*   **Incorrect Mocking:** `patch` failing or mocks not behaving as expected.
    *   **Avoidance:** Remember to `patch` the target where it's *looked up* (usually where it's imported or used), not necessarily where it's defined. Use `spec=OriginalClass` in `MagicMock` for better error checking. Verify mock calls (`assert_called_once_with`, etc.).
*   **Scope Issues in Tests:** Mock instances or fixtures not being available where needed.
    *   **Avoidance:** Understand `pytest` fixture scopes. Define mocks within the test function if they aren't provided by a fixture used by that specific test.
*   **Trying to Do Too Much:** Making too many changes at once makes it hard to track down errors.
    *   **Avoidance:** Stick to small, incremental steps. Commit after each logical step passes tests.
*   **Forgetting Cleanup:** Leaving behind unused imports, variables, or methods.
    *   **Avoidance:** Explicitly review for dead code after tests pass. Use linters that detect unused code.

**8. Example (Conceptual: Extracting a Helper Function)**

1.  **Identify:** A complex calculation is repeated within a method `process_data`.
2.  **Test (Before):** Ensure `test_process_data` covers cases involving this calculation.
3.  **Extract:** Create a new private method `_perform_calculation(input)`. Move the calculation logic there.
4.  **Delegate:** Replace the calculation logic in `process_data` with a call to `self._perform_calculation(input)`.
5.  **Test (After):**
    *   Run `test_process_data`. It should ideally still pass (as external behavior is unchanged). If it fails due to mocking internals, adapt it.
    *   Add `test__perform_calculation` to specifically test the extracted method's logic with various inputs.
6.  **Clean Up:** Run formatter/linter.
7.  **Document:** Update `memory.md`.

By following this guide, we can iteratively improve the codebase's quality while minimizing disruption and maintaining correctness.
