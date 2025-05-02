**Document 1: Tech Lead Workflow: Task Preparation & Instruction Generation**

**`docs/dev_workflows/tech_lead_task_prep.md`**

# Tech Lead Workflow: Task Preparation & Instruction Generation

**Purpose:** This guide outlines the standard process for a Tech Lead (TL) to prepare a development task based on requirements and Interface Definition Language (IDL) specifications. The key output of this process is a detailed instruction document for the implementing developer (e.g., a Junior Developer - JD).

**Goal:** To ensure tasks are well-defined, architecturally sound, and have a clear implementation and testing plan before coding begins, facilitating a smooth handoff and successful implementation.

---

**Phase 0: Preparation & Context Gathering**

*   **Goal:** Thoroughly understand the task requirements, the primary component's contract (IDL), and the context of its dependencies and interactions.
*   **Actions:**
    1.  **Define Task:** Clearly understand the overall goal (e.g., from an issue tracker, user story, feature request). Identify the scope and desired outcome.
    2.  **Locate Primary IDL(s):** Find the main `*_IDL.md` file(s) for the component(s) being implemented or modified. If no IDL exists for modifications, consider creating/updating one first.
    3.  **Analyze IDL Contract:**
        *   Read the primary IDL(s) carefully.
        *   Identify: Interface/Module Purpose, Method/Function Signatures (Params, Returns, Types), Preconditions, Postconditions, Documented Behavior, Error Conditions (`@raises_error`), Expected Data Structures (`Expected JSON format`, `struct`s). Note any ambiguities or areas needing clarification.
    4.  **Identify & Review Dependencies:**
        *   List all declared dependencies (`@depends_on`, `@depends_on_resource`) from the primary IDL(s).
        *   Locate and **review the IDLs** for any internal components listed in `@depends_on`. Understand *their* contracts and how the target component is expected to interact with them.
    5.  **Study Relevant External/Internal APIs & Libraries:**
        *   Based on the task goal and dependencies, identify relevant external libraries (e.g., `pydantic-ai`), third-party tools (e.g., Aider via MCP Server), internal APIs, or system primitives (e.g., S-expression `get_context`) that will be used.
        *   **Action:** **Thoroughly consult** the relevant documentation:
            *   `docs/librarydocs/` for key project libraries.
            *   `docs/system/contracts/` for internal APIs/protocols/types.
            *   Specific component IDLs for internal dependencies.
            *   Official external documentation for third-party libraries/tools.
        *   **Goal:** Fully understand the specific functions/methods/endpoints to call, required parameters/authentication, expected data formats (request/response), and error handling mechanisms of these dependencies. Identify potential complexities or integration challenges.
    6.  **Review Related Project Docs:** Check relevant ADRs (`docs/system/architecture/decisions/`), architectural patterns (`docs/system/architecture/patterns/`), and project rules (`implementation_rules.md`, `project_rules.md`) that might influence the implementation approach or impose constraints.
    7.  **Formulate Testing Strategy:** Based on dependencies and project guidelines (`implementation_rules.md#testing-conventions`), decide the primary testing approach (e.g., prioritize integration tests, identify necessary unit tests for complex logic, determine key boundaries for mocking).
    8.  **Update Working Memory:** Record the task, key findings, reviewed documents, identified risks/ambiguities, and initial testing strategy in `docs/memory.md`.

**Phase 1: Stubbing & Plan Generation**

*   **Goal:** Create the necessary code/test skeletons and generate a detailed, actionable instruction document for the implementing developer.
*   **Actions:**
    1.  **Stub Skeleton Code:** Create the basic Python file(s) and class/function structures matching the IDL. Implement exact signatures with type hints. Copy/adapt IDL documentation into docstrings (`Args:`, `Returns:`, `Raises:`). Add placeholder bodies (`pass` or `raise NotImplementedError`).
    2.  **Stub Tests & Outline Strategy:** Create empty test methods (`def test_...(): pass`) in the appropriate test file(s) corresponding to the key aspects identified in Phase 0 (success paths, error conditions, edge cases, dependency interactions). Briefly outline the overall testing strategy (e.g., "Integration test using real Handler, mock MemorySystem").
    3.  **Compile Detailed Implementation Plan for JD:**
        *   Based on the IDL behavior, dependency knowledge (Phase 0, Step 5), and architectural constraints, outline the specific implementation steps.
        *   Specify algorithms, data structures (Pydantic models from `types.md` or new ones to define), and critical logic flow.
        *   Detail *exactly* how to interact with dependencies (methods, parameters, handling results/errors).
        *   Specify precise error handling logic (e.g., "If `dependency.call()` raises `SpecificError`, catch it and return a FAILED `TaskResult` with reason `X` and details Y").
    4.  **Compile Detailed Testing Plan for JD:**
        *   For each stubbed test function:
            *   Specify required `pytest` fixtures.
            *   Detail necessary mock configurations (e.g., `mock_dependency.method.return_value = Z`, `mock_dependency.method.side_effect = SpecificException`).
            *   List the *exact* assertions needed (`assert result.status == ...`, `mock_dependency.method.assert_called_once_with(...)`, `with pytest.raises(SpecificException): ...`).
    5.  **Add Execution & Debugging Guidance for JD:**
        *   Provide specific commands to run the relevant tests (e.g., `pytest tests/component/test_file.py::TestClass::test_specific_case`).
        *   Include debugging tips relevant to the task (e.g., "Add logging inside the loop to check variable X", "Use `breakpoint()` before calling dependency Y", "Watch out for potential `None` values from function Z").
        *   Clarify when and how the JD should seek help from the TL.
    6.  **Define Definition of Done:** Create a checklist outlining the criteria for task completion (e.g., code implemented per plan, all specified tests passing, linting/formatting clean, self-review done).
    7.  **Assemble Instruction Document:** Collate all the above details (Task Goal, Context, Stubs, Implementation Plan, Testing Plan, Execution/Debugging Guidance, DoD) into the **Junior Developer Task Instruction Template** (see Document 2). Ensure clarity, precision, and completeness.

**Phase 2: Handoff & Follow-up**

*   **Goal:** Assign the task with clear instructions and ensure the necessary code stubs are available.
*   **Actions:**
    1.  **Finalize & Review Instructions:** Read through the completed instruction template for clarity, accuracy, and completeness. Ensure all necessary context and details are included.
    2.  **Commit Stubs:** Commit the stubbed code and test files created in Phase 1.
    3.  **Assign Task:** Assign the task to the JD via the issue tracker, linking to the detailed instruction document and the relevant commit/branch.
    4.  **Plan Code Review:** Mentally note or schedule time for reviewing the JD's implementation upon completion.

