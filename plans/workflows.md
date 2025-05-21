**Project Plan: `SequentialWorkflow` Implementation (Version 3.1 - Corrected Phase 0 & Integrated Test Updates)**

**Overall Goal:** Implement the `SequentialWorkflow` component as defined in `src/orchestration/sequential_workflow_IDL.md`, enabling Python-fluent orchestration of pre-registered tasks with explicit input/output mapping. The component will be designed with robustness, clarity, and future async compatibility in mind, and will be supported by comprehensive testing and documentation, including a practical demo script.

**Key Design Decisions Incorporated (Recap):**
*   `TaskResult` is a Pydantic model instance.
*   `input_mappings` supports dot-separated strings and list-of-strings paths.
*   `initial_context` is deep-copied.
*   `SequentialWorkflow.run` is `async def`. `Dispatcher.execute_programmatic_task` (and its chain) is also `async`.
*   Contextual logging.
*   Cycle detection at the start of `run()`.
*   `run()` returns a `WorkflowOutcome` Pydantic model.
*   Fail-fast error handling where `run()` returns a `WorkflowOutcome` with `success=false` for operational errors (like step failures or input resolution issues), while `InvalidWorkflowDefinition` is raised for setup errors.

---

**Phase 0: Prerequisites & Foundational Adjustments (System-Wide)**

*   **Goal:** Standardize `TaskResult` to Pydantic model, make core execution path `async`.
*   **Implementation Tasks (Phase 0 - System-Wide):**
    1.  **Standardize `TaskResult` Return Type:**
        *   Ensure `TaskResult` is robustly defined as a Pydantic model in `src/system/models.py`.
        *   Modify `DispatcherFunctions_IDL.md` and `Application_IDL.md`:
            *   Change return type of `execute_programmatic_task` / `handle_task_command` from `dict<string, Any>` to `object` (representing the `TaskResult` Pydantic model).
            *   Update postconditions to state "Returns a `TaskResult` Pydantic model instance...".
        *   **Crucial:** Update the implementations of `Dispatcher.execute_programmatic_task`, `Application.handle_task_command`, and any underlying task execution logic (e.g., `TaskSystem.execute_atomic_template`, `AtomicTaskExecutor.execute_body` if it directly creates the final `TaskResult`, `BaseHandler._execute_tool`) to ensure they construct and return an actual `TaskResult` Pydantic model instance. This might involve refactoring how results are created in those components.
    2.  **Async Task Execution Path (Decision & Refactor):**
        *   **Analyze & Implement:** Refactor `Dispatcher.execute_programmatic_task` and its primary downstream dependencies (`TaskSystem.execute_atomic_template`, `AtomicTaskExecutor.execute_body`'s call to handler, `BaseHandler._execute_llm_call`, `BaseHandler._execute_tool`, `LLMInteractionManager.execute_call`, `MemorySystem.get_relevant_context_for`, relevant SexpEvaluator methods, and AiderExecutor functions) to be `async def` and use `await` appropriately.
        *   This is a significant undertaking. If full async refactor of all dependencies is too large *immediately*, the call from `SequentialWorkflow._execute_task_internal` to `app_or_dispatcher_instance.execute_programmatic_task` will use `await asyncio.to_thread(...)` as a bridge, but the target is to make the core path async.
    3.  **Update Relevant IDLs (System-Wide):**
        *   For all methods changed to `async def` in step 2, update their respective IDL files. Add a comment (e.g., `// Asynchronous method`) to denote this, as our IDL syntax doesn't have a native `async` keyword.
        *   Ensure return types in IDLs reflect Pydantic `TaskResult` objects where applicable.

*   **Test Update Tasks (Phase 0 - System-Wide):**
    1.  **All Affected Test Files:**
        *   Add `@pytest.mark.asyncio` to test functions calling newly async methods.
        *   Change test function signatures to `async def`.
        *   Use `await` for all calls to newly async production methods.
        *   Update assertions to expect Pydantic `TaskResult` objects (attribute access like `result.status`) instead of dictionaries.
        *   For mocked async methods, use `unittest.mock.AsyncMock` and assert with `assert_awaited_once()` or `assert_awaited_once_with()`.
    2.  **Specific Files Requiring Major Test Updates (as detailed in previous response):**
        *   `tests/test_dispatcher.py`
        *   `tests/test_main.py` (incl. fixing `isinstance` and `KeyError` issues noted in previous review)
        *   `tests/task_system/test_task_system.py`
        *   `tests/executors/test_atomic_executor.py`
        *   `tests/handler/test_base_handler.py`
        *   `tests/handler/test_llm_interaction_manager.py` (Note: `initialize_agent` remains sync).
        *   `tests/handler/test_passthrough_handler.py`
        *   `tests/memory/test_memory_system.py` (Fix `AttributeError: 'coroutine' object has no attribute 'status'` by ensuring `get_relevant_context_for` awaits its async call to `TaskSystem`).
        *   `tests/aider_bridge/test_bridge.py` (If `get_context_for_query` becomes async).
        *   `tests/executors/test_aider_executors.py`
        *   `tests/sexp_evaluator/test_sexp_evaluator.py`
*   **Deliverables (Phase 0):**
    *   Consistently used `TaskResult` Pydantic model across the system.
    *   Core execution path refactored to `async/await` (or bridged with `asyncio.to_thread` where full refactor is deferred).
    *   Updated IDLs for affected components.
    *   All existing tests in affected files updated for async and `TaskResult` objects, and all passing.
    *   `docs/memory.md` updated.

---

**Phase 1: Core `SequentialWorkflow` Class Structure and `add_task` Method**

*   **Tasks:**
    1.  **Create Python File:** `src/orchestration/sequential_workflow.py`.
    2.  **Define Custom Exceptions:** In `src/orchestration/sequential_workflow.py` (or `src/orchestration/errors.py`):
        *   `class DuplicateOutputNameError(ValueError): pass`
        *   `class InvalidWorkflowDefinition(ValueError): pass`
        *   `class WorkflowExecutionError(RuntimeError): def __init__(self, message, failing_step_name=None, original_exception=None, details=None): ...`
        *   `class ValueResolutionError(KeyError): pass # Or ValueError`
    3.  **Define `WorkflowOutcome` Model:** In `src/orchestration/sequential_workflow.py` (or `src/system/models.py` if deemed system-wide):
        ```python
        from typing import Dict, Any, Optional
        from pydantic import BaseModel, Field
        # from src.system.models import TaskResult # Assuming TaskResult is a Pydantic model

        class WorkflowOutcome(BaseModel):
            success: bool
            results_context: Dict[str, Any] = Field(default_factory=dict) # Dict[str, TaskResult model instance]
            error_message: Optional[str] = None
            failing_step_name: Optional[str] = None
            details: Optional[Dict[str, Any]] = None # For richer error details
        ```
    4.  **Implement `SequentialWorkflow` Class:**
        *   `__init__(self, app_or_dispatcher_instance)`: Store dependency, `self._task_sequence = []`, `self._defined_output_names = set()`.
        *   `clear(self)`: Reset internal state.
    5.  **Implement `add_task` Method:**
        *   Signature: `add_task(self, task_name: str, output_name: str, static_inputs: Optional[dict] = None, input_mappings: Optional[dict] = None) -> 'SequentialWorkflow':`
        *   Validate `output_name` uniqueness (raise `DuplicateOutputNameError`).
        *   Store task configuration.
        *   Return `self`.
*   **Test Tasks (Phase 1 - For `SequentialWorkflow`):**
    1.  Create `tests/orchestration/test_sequential_workflow.py`.
    2.  **Unit Tests for `__init__` and `clear`:** (Synchronous tests)
        *   Test successful instantiation (pass a mock `app_or_dispatcher_instance`).
        *   Test `clear()` resets internal state.
    3.  **Unit Tests for `add_task`:** (Synchronous tests)
        *   Test adding single/multiple tasks, correct storage of config.
        *   Test `static_inputs` and `input_mappings` (as `None`, empty, or populated with string or list-of-string paths) are stored.
        *   Test `DuplicateOutputNameError`.
        *   Test fluent chaining.
*   **Deliverables:**
    *   `src/orchestration/sequential_workflow.py` with `__init__`, `add_task`, `clear`, custom exceptions, `WorkflowOutcome`.
    *   Passing unit tests for Phase 1 functionality.
    *   `docs/memory.md` updated.

---

**Phase 2: Input Resolution Logic (`_get_value_from_source` Helper)**

*   **Tasks:**
    1.  **Implement `_get_value_from_source` Helper:**
        *   Private method: `_get_value_from_source(self, source_container: Any, value_path: Union[str, List[str]]) -> Any`.
        *   If `value_path` is a string, split by `.` to get segments. If it's a list, use segments directly.
        *   Iteratively traverse `source_container` using `getattr` (for objects) and `dict.get` (for dicts).
        *   Handle `None` intermediates and missing keys/attributes by raising `ValueResolutionError`.
*   **Testing (Phase 2):**
    *   Unit tests for `_get_value_from_source` (as detailed in previous plan), including tests for list-of-strings path.
*   **Deliverables:**
    *   Implemented and tested `_get_value_from_source` helper.
    *   `docs/memory.md` updated.

---

**Phase 3: `run()` Method Implementation & Cycle Detection**

*   **Tasks:**
    1.  **Implement `_build_dependency_graph_and_detect_cycles` Helper:**
        *   Private method called at the start of `run()`.
        *   Iterates `self._task_sequence`. For each step, identifies source `output_name`s from its `input_mappings`.
        *   Builds a directed graph (e.g., `output_name` -> list of `output_name`s it depends on).
        *   Uses a standard algorithm (e.g., DFS-based) to detect cycles. If a cycle is found, raise `InvalidWorkflowDefinition("Cycle detected in task dependencies.")`.
    2.  **Implement `async def run(self, initial_context: Optional[dict] = None) -> WorkflowOutcome:`**
        *   Call `_build_dependency_graph_and_detect_cycles()`.
        *   Check if `self._task_sequence` is empty (raise `InvalidWorkflowDefinition`).
        *   Initialize `workflow_results_context = {}`.
        *   Store deepcopy of `initial_context`: `workflow_results_context["_initial_"] = copy.deepcopy(initial_context) if initial_context else {}`.
        *   Loop `idx, task_config` through `enumerate(self._task_sequence)`:
            *   `logger.debug(f"Step {idx} ({task_config['output_name']}): Starting task {task_config['task_name']}...")`
            *   Try/except block for the step:
                *   Assemble `current_task_params` from `static_inputs` and resolved `input_mappings` (using `_get_value_from_source`). Handle `ValueResolutionError` by wrapping in `WorkflowExecutionError`.
                *   `logger.debug(f"Step {idx} ({task_config['output_name']}): Executing with params: {current_task_params}")`
                *   Execute task: `task_result: TaskResult = await self._execute_task_internal(task_config["task_name"], current_task_params)` (This internal method will handle the `asyncio.to_thread` if dispatcher is sync, or direct await if dispatcher is async).
                *   `workflow_results_context[task_config["output_name"]] = task_result`.
                *   `logger.info(f"Step {idx} ({task_config['output_name']}): Completed with status {task_result.status}")`.
                *   If `task_result.status == "FAILED"`, raise `WorkflowExecutionError(...)`.
            *   Catch `WorkflowExecutionError` from current step: log, populate `WorkflowOutcome` with error details, and return it.
            *   Catch other unexpected exceptions: log, wrap in `WorkflowExecutionError`, populate `WorkflowOutcome`, and return.
        *   If loop completes, return `WorkflowOutcome(success=True, results_context=workflow_results_context)`.
    3.  Implement `async def _execute_task_internal(self, task_name, params)` helper.
*   **Test Tasks (Phase 3 - For `SequentialWorkflow`):**
    1.  **Unit tests for `_build_dependency_graph_and_detect_cycles`**.
    2.  **Integration Tests for `run()` (mocking `app_or_dispatcher_instance.execute_programmatic_task`):**
        *   All these tests: `async def`, `@pytest.mark.asyncio`.
        *   Mock `app_or_dispatcher_instance.execute_programmatic_task` as an `AsyncMock`.
        *   Test successful simple workflows (static inputs, various `input_mappings`). Verify `WorkflowOutcome.success == True` and correct `results_context` (containing `TaskResult` objects).
        *   Test `input_mappings` precedence.
        *   Test `InvalidWorkflowDefinition` for empty sequence and cyclic dependencies (raised before async loop).
        *   Test workflow with a step that takes no parameters.
*   **Deliverables:**
    *   Implemented `run()` method.
    *   Passing unit and integration tests for `run()` (mocked dispatcher).
    *   `docs/memory.md` updated.

---

**Phase 4: Error Handling Refinements in `run()`**

*   **Implementation Tasks:**
    1.  Ensure `WorkflowExecutionError` (if still used for unexpected internal errors) and `WorkflowOutcome` (for operational errors) capture comprehensive diagnostic information.
    2.  Review all error paths in `run()` for consistent `WorkflowOutcome` generation.
*   **Test Tasks (Phase 4 - For `SequentialWorkflow`):**
    1.  **Integration Tests for `run()` (mocked dispatcher, focus on errors):**
        *   All these tests: `async def`, `@pytest.mark.asyncio`.
        *   Test `WorkflowOutcome` (with `success=False`) for:
            *   `input_mappings` referring to non-existent `output_name`.
            *   `input_mappings` path invalid within a `TaskResult` (`_get_value_from_source` failure).
            *   Source task for `input_mappings` having `status="FAILED"`.
            *   `execute_programmatic_task` (mocked) raising an unhandled exception.
            *   `execute_programmatic_task` (mocked) returning a `TaskResult` with `status="FAILED"`.
        *   Verify relevant error fields in `WorkflowOutcome` are populated.
*   **Deliverables:**
    *   Robust error handling in `run()` returning detailed `WorkflowOutcome`.
    *   Comprehensive integration tests for failure scenarios.
    *   `docs/memory.md` updated.

---

**Phase 5: Documentation, Demo Script, and Final Review**

*   **Implementation Tasks:**
    1.  Finalize Python Docstrings in `sequential_workflow.py`.
    2.  **Non-Interactive Demo Script:** Create `src/scripts/sequential_workflow_demo.py`.
        *   Use `async def main()` and `asyncio.run(main())`.
        *   Mock tasks and dispatcher (as `AsyncMock`).
        *   Demonstrate all key features and path syntax alternatives.
        *   Show handling of `WorkflowOutcome`.
*   **Documentation Update Tasks (Phase 5):**
    1.  **IDL Finalization:** Update `src/orchestration/sequential_workflow_IDL.md` to precisely match final `async run` signature, `WorkflowOutcome` return, cycle detection, list-of-strings path support, and refined error reporting via `WorkflowOutcome`. Update sequence diagram.
    2.  **Update Orchestration Guide:** Update `docs/examples/python_orchestration_guide.md` with the `async` example, `WorkflowOutcome` handling, YAML/JSON conceptual workflow, and troubleshooting table.
*   **Testing (Phase 5):**
    *   Manually run and verify `sequential_workflow_demo.py`.
    *   Review all documentation.
    *   Full `pytest` suite run to ensure no regressions anywhere in the system.
*   **Deliverables:**
    *   Fully implemented and tested `SequentialWorkflow` component.
    *   Completed `src/scripts/sequential_workflow_demo.py`.
    *   Updated and accurate IDL, docstrings, and usage guides.
    *   `docs/memory.md` updated.

