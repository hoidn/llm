**Project Plan: `SequentialWorkflow` Implementation (Version 2 - Revised)**

**Overall Goal:** Implement the `SequentialWorkflow` component, enabling Python-fluent orchestration of pre-registered tasks with explicit input/output mapping. The component will be designed with robustness, clarity, and future async compatibility in mind, and will be supported by comprehensive testing and documentation, including a practical demo script.

**Key Design Decisions Incorporated:**

1.  **TaskResult Type:** `Dispatcher.execute_programmatic_task` (and its callers/implementers) MUST return a Pydantic `TaskResult` model instance. `SequentialWorkflow` will consume these instances.
2.  **Path Syntax for `input_mappings`:** Primarily dot-separated strings (e.g., `"source.parsedContent.field"`). A list of strings (e.g., `["source", "parsedContent", "field.with.dots"]`) will be supported as an alternative for keys containing special characters.
3.  **`initial_context` Immutability:** `SequentialWorkflow.run` will use `copy.deepcopy()` on the provided `initial_context`.
4.  **Async Design:** `SequentialWorkflow.run` will be designed as `async def run(...)`. This presumes that `Dispatcher.execute_programmatic_task` (or `Application.handle_task_command`) will also be `async` or can be called appropriately from an async context (e.g., via `asyncio.to_thread` if it's blocking I/O, though a native async dispatcher is preferred).
5.  **Logging:** Contextual information (step index, task name, output name) will be included in log messages.
6.  **Cycle Detection:** Cycle detection for task dependencies defined in `input_mappings` will be performed at the beginning of the `run()` method.
7.  **Return Type of `run()`:** Will return a `WorkflowOutcome` Pydantic model/dataclass containing success status, the results context, and error information if applicable.
8.  **Error Handling:** Fail-fast policy; `WorkflowExecutionError` will be raised on the first significant error during `run()`.

---

**Phase 0: Prerequisites & Foundational Adjustments**

*   **Tasks:**
    1.  **Standardize `TaskResult` Return Type:**
        *   Ensure `TaskResult` is defined as a Pydantic model in `src/system/models.py`.
        *   Modify `DispatcherFunctions_IDL.md` and `Application_IDL.md`:
            *   Change return type of `execute_programmatic_task` / `handle_task_command` from `dict<string, Any>` to `object` (representing the `TaskResult` Pydantic model).
            *   Update postconditions to state "Returns a `TaskResult` Pydantic model instance...".
        *   **Crucial:** Update the implementations of `Dispatcher.execute_programmatic_task`, `Application.handle_task_command`, and any underlying task execution logic (e.g., `TaskSystem.execute_atomic_template`, `BaseHandler._execute_tool`) to ensure they construct and return an actual `TaskResult` Pydantic model instance. This might involve refactoring how results are created in those components.
    2.  **Async Task Execution Path (Decision & Potential Refactor):**
        *   **Analyze:** Determine if `Dispatcher.execute_programmatic_task` (and its dependencies like `TaskSystem.execute_atomic_template`, `BaseHandler._execute_llm_call`, `BaseHandler._execute_tool`) can be made `async`.
        *   **If Yes (Preferred):** Refactor these methods to be `async def`. This is a significant undertaking affecting multiple components.
        *   **If No (Fallback):** Document that `SequentialWorkflow.run` will need to use `await asyncio.to_thread(self.app_or_dispatcher_instance.execute_programmatic_task, ...)` if the dispatcher call is blocking. This is less ideal but allows `SequentialWorkflow` to be async.
        *   This decision heavily influences the implementation details of `SequentialWorkflow.run`.
*   **Testing (Phase 0):**
    *   Update existing tests for `Dispatcher` and `Application` to assert that they return `TaskResult` Pydantic model instances.
    *   If refactoring to async, ensure all affected components' tests are updated and pass.
*   **Deliverables:**
    *   Consistently used `TaskResult` Pydantic model.
    *   Updated IDLs for `Dispatcher` and `Application`.
    *   Decision and potential refactoring for async task execution path completed.
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
        *   Store task configuration (dict or internal dataclass) in `self._task_sequence`.
        *   Return `self`.
*   **Testing (Phase 1):**
    *   Create `tests/orchestration/test_sequential_workflow.py`.
    *   Unit tests for `__init__`, `clear`, and `add_task` (as detailed in previous plan).
*   **Deliverables:**
    *   `src/orchestration/sequential_workflow.py` with `__init__`, `add_task`, `clear`, custom exceptions, `WorkflowOutcome`.
    *   Passing unit tests for Phase 1.
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
    *   Implemented and tested `_get_value_from_source`.
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
    3.  **Implement `async def _execute_task_internal(self, task_name, params)`:**
        *   This private helper will contain the logic for calling `self.app_or_dispatcher_instance.execute_programmatic_task`.
        *   If `execute_programmatic_task` is async: `return await self.app_or_dispatcher_instance.execute_programmatic_task(...)`.
        *   If `execute_programmatic_task` is sync: `return await asyncio.to_thread(self.app_or_dispatcher_instance.execute_programmatic_task, ...)`.
*   **Testing (Phase 3):**
    *   Unit tests for `_build_dependency_graph_and_detect_cycles` (valid graphs, graphs with cycles).
    *   Integration tests for `run` (mocking `app_or_dispatcher_instance.execute_programmatic_task`, as detailed in previous plan), ensuring `WorkflowOutcome` is returned.
    *   Test `InvalidWorkflowDefinition` for empty sequence and for cyclic dependencies.
    *   Test additional edge cases suggested (no-param steps, input key collision precedence).
*   **Deliverables:**
    *   Implemented `run()` method with cycle detection and async execution.
    *   Passing integration tests for `run()` (mocked dispatcher).
    *   `docs/memory.md` updated.

---

**Phase 4: Error Handling Refinements & Full Integration Tests**

*   **Tasks:**
    1.  **Finalize `WorkflowExecutionError`:** Ensure it stores `failing_step_name`, `original_exception`, and `details` (like the FAILED `TaskResult` or resolution error info) effectively.
    2.  Thoroughly review all error raising and catching paths in `run()` for consistency and detail.
*   **Testing (Phase 4):**
    *   Integration tests for `run` (mocked dispatcher, focus on errors, as detailed in previous plan). Ensure `WorkflowOutcome` correctly reflects failures.
*   **Deliverables:**
    *   Robust error handling in `run()` returning detailed `WorkflowOutcome`.
    *   Comprehensive integration tests for failure scenarios.
    *   `docs/memory.md` updated.

---

**Phase 5: Documentation, Demo Script, and Final Review**

*   **Tasks:**
    1.  **Python Docstrings:** Finalize all docstrings in `sequential_workflow.py`.
    2.  **IDL Review:** Update `src/orchestration/sequential_workflow_IDL.md` to reflect the `async run` signature, the `WorkflowOutcome` return type, cycle detection, list-of-strings path support, and any other refinements. Ensure sequence diagram is accurate.
    3.  **Non-Interactive Demo Script:** Create `src/scripts/sequential_workflow_demo.py` (as detailed in previous plan).
        *   Ensure it can run with an `async` main function if `SequentialWorkflow.run` is async.
        *   Demonstrate path syntax alternatives if applicable.
    4.  **Update Orchestration Guide:**
        *   Edit/Create `docs/examples/python_orchestration_guide.md`.
        *   Include example from demo script.
        *   Add YAML/JSON conceptual depiction of a workflow.
        *   Add a troubleshooting table (common exceptions -> cause -> fix).
*   **Testing (Phase 5):**
    *   Manually run and verify `sequential_workflow_demo.py`.
    *   Review all documentation.
    *   Full `pytest` suite run.
*   **Deliverables:**
    *   Fully implemented and tested `SequentialWorkflow` component.
    *   Completed `src/scripts/sequential_workflow_demo.py`.
    *   Updated and accurate IDL, docstrings, and usage guides.
    *   `docs/memory.md` updated.

