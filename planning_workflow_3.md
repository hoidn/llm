<workflow>
**Revised Development Process Guide: IDL-Driven Implementation and Revision**

**Purpose:** This guide outlines a structured, step-by-step process for implementing, refactoring, or revising components based on their Interface Definition Language (IDL) specifications. Following this ensures alignment between the contract (IDL), implementation, and tests, whether creating new features, modifying existing ones, or removing obsolete parts.

**Relationship to `start_here.md`:** This workflow details the activities typically performed within the "Implementation & Testing" phase described in `docs/start_here.md`, applicable to both initial implementation and subsequent revisions.

---

## <process-step id="1">
<step-title>Understand the Target State (Based on IDL)</step-title>
<step-actions>
- **Analyze the Relevant IDL:** Thoroughly read the `*_IDL.md` file(s) for the component(s) being implemented or modified. If the IDL itself is changing, focus on the *target* (new) version.
- **Identify Key Contract Elements:** (Same as original)
    - Interface/Module Purpose & Name.
    - Method/Function Signatures (Parameters, Return Types, Type Hints).
    - Preconditions & Postconditions.
    - Documented Behavior & Logic Flow.
    - Specified Error Conditions (`@raises_error`) and expected error formatting (e.g., `TaskResult`).
    - Expected data structures (e.g., `Expected JSON format`, linked `struct`s or Pydantic models).
- **Note Dependencies:** (Same as original) List all declared dependencies (`@depends_on`, `@depends_on_resource`).
- **Identify Affected Code & Tests:** Locate the existing implementation file(s), test file(s), and specific functions/methods/classes related to the IDL section being addressed. **Note:** This step is crucial for refactoring/revision. For greenfield, these won't exist yet.
- **Assess Scope of Change:** Determine if the task involves:
    - **Addition:** Creating new components/methods/tests.
    - **Modification:** Changing existing implementation/logic/tests based on IDL updates or refactoring goals.
    - **Deletion:** Removing obsolete components/methods/tests referenced by a changed or removed IDL section.
</step-actions>
</process-step>

## <process-step id="2">
<step-title>Prepare/Adjust Implementation Components</step-title>
<step-actions>
- **Locate/Create Code Structures:**
    - **For additions:** Generate the basic Python file(s) and class/function structures matching the IDL (e.g., `ClassName`, `method_name`).
    - **For modifications/deletions:** Identify the *exact* existing functions/classes/files to be changed or removed.
- **Update Signatures & Docstrings:**
    - **For additions/modifications:** Define or update method/function signatures precisely matching the *target* IDL, including type annotations. Copy/adapt/update the behavior description from the IDL into the docstring. Update `Args:`, `Returns:`, `Raises:` based on the target IDL.
    - **For deletions:** Mark relevant code sections for removal.
- **Stub/Adjust Body:**
    - **For additions:** Add a placeholder implementation (e.g., `pass` or `raise NotImplementedError`).
    - **For modifications:** Review the existing body; identify sections needing change. Add comments (`# TODO: Update logic for X`) or temporarily comment out old logic if performing significant rewrites.
- **Identify Imports:** List necessary imports for types, dependencies, and errors based on the target IDL or planned changes. Add new imports, update existing ones, or mark unused ones for removal.
</step-actions>
</process-step>

## <process-step id="3">
<step-title>Outline Testing Strategy & Adjust Tests</step-title>
<step-actions>
- **Define Test Strategy:** (Same as original, but consider impact on existing tests) Based on IDL dependencies and project guidelines (`implementation_rules.md#testing-conventions`), decide the primary testing approach.
- **Identify/Plan Fixtures:** Determine required `pytest` fixtures. Identify existing fixtures that might need modification or new fixtures required for changed/new functionality. Plan fixture scope.
- **Map Tests to Target IDL:**
    - **Review Existing Tests:** Examine tests related to the affected code. Identify which are still valid, which need modification, and which are now obsolete (target for deletion).
    - **Identify Required Tests:** Create empty test methods (`def test_...(): pass`) or add comments (`# TODO: Add test for...`) for each key aspect of the *target* IDL contract not adequately covered by existing, valid tests:
        - Success scenarios verifying core `Behavior` and `Postconditions`.
        - Failure scenarios verifying specified `Error Conditions` (`@raises_error`).
        - Edge cases implied by `Preconditions` or parameter types.
        - **Regression tests:** Ensure core functionality *unchanged* by the refactoring/revision still works, if applicable.
- **Draft Assertions (High-Level):** Add/update comments within new or modified test stubs outlining *what* needs to be asserted. Note assertions in obsolete tests that might be useful elsewhere before deletion.
</step-actions>
</process-step>

## <process-step id="4">
<step-title>Plan Implementation and Testing Details</step-title>
<step-actions>
- **Detail Implementation Logic:** Outline the core algorithm or sequence of steps needed to fulfill the *target* `Behavior`. For modifications, detail the *changes* required to the existing logic. For deletions, confirm removal scope.
- **Plan Parameter Validation:** Specify how input parameters will be validated against the *target* IDL types and preconditions. Detail any *changes* to existing validation.
- **Plan Error Handling:** Detail how specified `@raises_error` conditions (from the *target* IDL) will be detected/handled. Detail *changes* to existing error handling or removal of obsolete handling.
- **Plan Dependency Integration:** Document how the component will interact with its dependencies based on the *target* IDL or refactoring plan. Note any *changes* in dependency usage.
- **Refine Test Assertions:** Specify the *exact* assertions needed for each new or modified test stubbed in Step 3. Ensure assertions align with the *target* IDL.
- **Detail Fixture Behavior:** Specify the required return values or side effects for new or modified mock dependencies within test fixtures.
- **Identify Edge Cases:** Explicitly list edge cases relevant to the *changes* or *new* functionality and ensure tests cover them. Consider if existing edge case tests need updates.
- **Plan Deletions:** Clearly mark code sections, functions, classes, files, and tests slated for removal. Double-check they are genuinely obsolete according to the target IDL or refactoring scope.
</step-actions>
</process-step>

## <process-step id="5">
<step-title>Implement Changes (Code and Tests)</step-title>
<step-actions>
- **Guide the developer in Writing/Modifying/Deleting Production Code by drafting self contained developer instructions:** Implement instructions for implementing/modifying the component/function logic based on the IDL contract and the detailed plan from Step 4.
    - instruct the dev on IDL-based programming (additions/modifications).
    - state guidelines on parameter validation logic (additions/modifications).
    - guide Integration with dependencies (additions/modifications).
    - guide Implement/update comprehensive error handling (additions/modifications).
    - guide checking that results are formatted correctly (additions/modifications).
    - **Explicitly instruct on required code deletions.**
- **Write/Modify/Delete Tests:** Implement the test changes planned in Step 4.
    - Add new tests using Arrange-Act-Assert.
    - Modify existing tests to match changed behavior or assertions.
    - **Delete obsolete tests.**
    - Verify success paths, error handling, and edge cases against the *target* IDL contract.
    - Provide the fully implemented/modified tests (or instructions for deletion) as part of the developer instructions.
</step-actions>
</process-step>

## <process-step id="6">
<step-title>Verify and Finalize</step-title>
<step-actions>
- **Code Quality Checks:** (Same as original) Run linters/formatters.
- **Run Full Test Suite:** (Same as original, emphasis added) Execute the *complete* project test suite to check for unintended side effects or regressions caused by modifications/deletions.
- **Self-Review:** Read through the *changes* (diff). Check for clarity, simplicity, and adherence to:
    - The *target* IDL contract.
    - Project coding standards (`implementation_rules.md`).
    - General project conventions (`project_rules.md`).
    - **Confirm only intended code/tests were added/modified/deleted.**
- **Update Working Memory:** (Same as original) Record completion, decisions, commits.
- **Peer Review (Recommended):** (Same as original, emphasis added) Request code review focusing on contract adherence, correctness, testing adequacy, and **impact of changes/deletions**.
</step-actions>
</process-step>

## <key-lessons>
<lesson-title>Lessons Learned</lesson-title>
<lessons>
1.  **IDL is the Contract**: The IDL (or its updated version) defines *what* the target state should be.
2.  **Plan Before Changing**: Identifying affected code/tests and planning additions, modifications, *and deletions* clarifies scope and reduces errors.
3.  **Test the Contract (and Regressions)**: Focus tests on verifying the target IDL. Ensure existing functionality isn't unintentionally broken by changes (regression testing). Remove obsolete tests.
4.  **Dependency-Aware Testing**: Testing strategy must account for component dependencies, especially if interactions change.
5.  **Iterative Refinement**: Continuously test and refine the implementation *and existing code* against the plan and the target IDL contract.
6.  **Mindful Deletion**: Be deliberate when removing code and tests, ensuring they are truly obsolete based on the target IDL or refactoring goals.
</lessons>
</key-lessons>

---

## <example-developer-instructions>
<example-title>Example Developer Instructions (Phase 9.3 - Multi-LLM Routing)</example-title>

*   **Task Name/ID:** Phase 9.3: Implement Multi-LLM Routing/Execution
*   **Assigned To:** \[Junior Developer Name]
*   **Assigned By:** \[Tech Lead Name]
*   **Date Assigned:** \[Date]
*   **Relevant IDLs/Docs:**
    *   `src/handler/base_handler_IDL.md` (Target: Modify `_execute_llm_call`)
    *   `src/handler/llm_interaction_manager_IDL.md` (Target: Modify `execute_call`)
    *   `docs/implementation_rules.md`
    *   `docs/librarydocs/pydanticai.md`
    *   Planning Doc (Phase 9.3 Sub-Plan from Step 4)

---

**1. Task Goal:**

Modify the `LLMInteractionManager` and `BaseHandler` to allow the LLM provider/model to be specified dynamically per-call using a `model_override` parameter, enabling flexible LLM routing.

**2. Context & Requirements:**

*   **Target IDLs:** Ensure your implementation matches the updated signatures and behavior described in the target IDLs for `LLMInteractionManager.execute_call` and `BaseHandler._execute_llm_call`, specifically the addition and handling of the `model_override: optional string` parameter.
*   **Dependencies:** The `LLMInteractionManager` will need to dynamically instantiate `pydantic_ai.Agent` if an override is requested. It requires access to application configuration (assumed available via `self.config`) to find settings (like API keys) for the override model.
*   **Override Mechanism:** The `model_override` string (e.g., `"openai:gpt-4o"`) will be passed down from `BaseHandler` to `LLMInteractionManager`.

**3. Implementation Plan (Production Code):**

*   **A. Modify `LLMInteractionManager.execute_call`:**
    *   **File:** `src/handler/llm_interaction_manager.py`
    *   **IDL Adherence:** Add `model_override: Optional[str] = None` to the signature, matching the IDL.
    *   **Parameter Validation:** No explicit validation needed for the optional string beyond type hints.
    *   **Dependency Integration & Logic:**
        1.  Inside the `try...except` block, before the `agent.run_sync` call:
        2.  Initialize `target_agent = self.agent` (the default agent).
        3.  Add the override check: `if model_override and model_override != self.default_model_identifier:`.
        4.  Inside the `if`:
            *   Log the override attempt.
            *   Look up configuration for `model_override` (e.g., `override_config = self.config.get('llm_providers', {}).get(model_override)`).
            *   **Error Handling:** If `override_config` is `None`, log an error and `return` the standard FAILED result dictionary (`{"success": False, "error": "Config not found...", ...}`).
            *   Get tools from the default agent (`current_tools = self.agent.tools`). **Error Handling:** Check if `self.agent` or `self.agent.tools` are unavailable; if so, log error and return FAILED result dict (reason `dependency_error`).
            *   Combine base agent config (`self._agent_config`) with `override_config`.
            *   Instantiate `temp_agent = Agent(model=model_override, tools=current_tools, **combined_config)` within its own `try...except Exception as agent_init_error:`. **Error Handling:** On exception, log error and return FAILED result dict (reason `llm_error` or `configuration_error`, include `agent_init_error` in message).
            *   Set `target_agent = temp_agent`.
        5.  **Error Handling:** Before calling `run_sync`, check `if not target_agent:`. If `None`, log error and return FAILED result dict (reason `dependency_error`).
        6.  Use `target_agent.run_sync(...)` for the actual LLM call.
    *   **Result Formatting:** Ensure the existing logic correctly handles the response from `run_sync` and returns the standard result dictionary (`{"success": True/False, ...}`).
*   **B. Modify `BaseHandler._execute_llm_call`:**
    *   **File:** `src/handler/base_handler.py`
    *   **IDL Adherence:** Add `model_override: Optional[str] = None` to the signature, matching the IDL.
    *   **Dependency Integration:** Locate the call to `self.llm_manager.execute_call`. Add `model_override=model_override` to the keyword arguments passed.

**4. Implementation Plan (Tests):**

*   **A. Add/Modify Tests for `LLMInteractionManager.execute_call`:**
    *   **File:** `tests/handler/test_llm_interaction_manager.py`
    *   **Implement Tests (as drafted previously):**
        *   `test_execute_call_uses_default_agent_no_override`:
            *   Arrange: Use `initialized_llm_manager` fixture. Configure `manager.agent.run_sync` mock.
            *   Act: Call `execute_call` with `model_override=None`.
            *   Assert: `manager.agent.run_sync` called. `mock_agent_constructor` (patched) NOT called.
        *   `test_execute_call_with_model_override_success`:
            *   Arrange: Patch `Agent` constructor -> `mock_temp_agent`. Configure `manager.config` with override details. Configure `mock_temp_agent.run_sync`.
            *   Act: Call `execute_call` with `model_override="override:model"`.
            *   Assert: `mock_agent_constructor` called with override ID. `mock_temp_agent.run_sync` called. Default agent `run_sync` NOT called. Result is success.
        *   `test_execute_call_override_config_lookup_fail`:
            *   Arrange: Ensure override ID is missing from `manager.config`.
            *   Act: Call `execute_call` with override ID.
            *   Assert: Result dict has `success: False`, correct error message, reason `configuration_error`. Constructor/`run_sync` not called.
        *   `test_execute_call_override_agent_creation_fail`:
            *   Arrange: Patch `Agent` constructor to raise `Exception`. Configure manager config.
            *   Act: Call `execute_call` with override ID.
            *   Assert: Result dict has `success: False`, correct error message (including exception), reason `llm_error`/`configuration_error`. `run_sync` not called.
        *   `test_execute_call_with_model_and_tool_overrides`: (Verify interaction)
            *   Arrange: Set up override model config. Patch `Agent` constructor -> `mock_temp_agent`. Define `tool_override_list`.
            *   Act: Call `execute_call` with `model_override` and `tools_override`.
            *   Assert: `mock_agent_constructor` called with override model. `mock_temp_agent.run_sync` called with `tools=tool_override_list`.
*   **B. Add/Modify Tests for `BaseHandler._execute_llm_call`:**
    *   **File:** `tests/handler/test_base_handler.py`
    *   **Modify Existing:** Update `test_base_handler_execute_llm_call_success` and `failure` assertions to expect `model_override=None` in the `execute_call` mock assertion.
    *   **Implement New:** `test_execute_llm_call_passes_model_override`:
        *   Arrange: Use `base_handler_instance` fixture.
        *   Act: Call `handler._execute_llm_call(..., model_override="test:model")`.
        *   Assert: `handler.llm_manager.execute_call.assert_called_once_with(..., model_override="test:model")`.

**5. Definition of Done:**
*   [ ] `LLMInteractionManager.execute_call` modified per plan.
*   [ ] `BaseHandler._execute_llm_call` modified per plan.
*   [ ] New/modified tests implemented for `LLMInteractionManager` and `BaseHandler`.
*   [ ] All tests related to this feature pass.
*   [ ] Full project test suite passes.
*   [ ] Code passes linting (`make lint`) and formatting (`make format`).
*   [ ] `docs/memory.md` updated with progress.
*   [ ] Relevant IDLs (`llm_interaction_manager_IDL.md`, `base_handler_IDL.md`) updated and committed.

</example-developer-instructions>
---

</workflow>
