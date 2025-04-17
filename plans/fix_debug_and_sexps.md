
**Synthesized Implementation Plan: Programmatic Execution Enhancements**

**Overall Goal:** Implement both a specific, automated Debug-Fix Loop workflow and a general-purpose S-expression based workflow capability, both accessible via the `/task` command, leveraging shared components where possible.

---

**Phase 1: Core Programmatic Backend (ADR 17 Foundation)**

*   **Goal:** Implement the fundamental backend logic for the "Thin Wrapper" approach, enabling programmatic invocation of *existing* Direct Tools and Subtask Templates via a central dispatcher, using *explicit context only*.
*   **Key Tasks:**
    1.  Implement `src/dispatcher.py` with `execute_programmatic_task` function containing routing logic (Handler Direct Tools first, then TaskSystem Templates). Include basic error catching/formatting.
    2.  Implement `TaskSystem.execute_subtask_directly(request)` method stub, including template lookup, basic `Environment` creation, and Phase 1 explicit context handling (only `request.file_paths` or template `file_paths`/`file_paths_source` of type `literal`/`command`). **No automatic lookup.** Placeholder for Evaluator call.
    3.  Setup dependency injection in `main.py`.
    4.  Unit test dispatcher routing and `execute_subtask_directly` explicit context paths.
*   **Deliverable:** Backend can route `/task` calls; `execute_subtask_directly` exists but doesn't fully execute template logic yet.

---

**Phase 2: Aider Integration & Basic `/task` REPL Command**

*   **Goal:** Integrate Aider actions as callable tasks and provide the basic REPL `/task` command interface for manual invocation (requiring explicit `file_context`).
*   **Key Tasks:**
    1.  Implement Aider executor functions (`execute_aider_automatic`, `execute_aider_interactive` in `src/executors/`) including parameter validation and `file_context` JSON parsing.
    2.  Register Aider executors as **Direct Tools** with the `Handler` in `main.py`.
    3.  Define optional Aider TaskSystem templates (`aider:automatic`, `aider:interactive`) primarily for `--help` metadata. Register them.
    4.  Implement basic `/task` command parsing in `Repl._cmd_task` (identifier, `key=value` params, basic JSON detection for values, `--help` flag).
    5.  Connect REPL command to call the dispatcher from Phase 1.
    6.  Integration test `/task aider:* ... file_context='["..."]'` flow (mocking `AiderBridge`). Test `--help`.
*   **Deliverable:** Users can run `/task aider:automatic prompt="..." file_context='["..."]'` and `/task aider:interactive query="..." file_context='["..."]'`. `--help` works.

---

**Phase 3: Implement `director_evaluator_loop` Executor & Script Integration**

*   **Goal:** Enable the system to execute the structure of a `director_evaluator_loop` task, including running embedded scripts.
*   **Key Tasks:**
    1.  Implement the core D-E loop iteration logic within the `Evaluator`'s `eval` method (or helper). Handle `max_iterations`, pass results between internal Director/Evaluator steps, check basic termination.
    2.  Ensure a Handler Direct Tool for script execution (e.g., `system:run_script`) exists and is registered.
    3.  Integrate the call to the script execution tool within the Evaluator's D-E loop logic, correctly capturing and passing `stdout`/`stderr`/`exitCode` to the Evaluator step's environment.
    4.  Unit test the D-E loop execution flow in the Evaluator (mocking the steps).
*   **Deliverable:** The system can execute the *structure* of a `director_evaluator_loop` template invoked via `/task`, including calling the script step.

---

**Phase 4: Debug-Fix Loop - Analysis & Shared Context Primitive**

*   **Goal:** Implement the test analysis step for the Debug-Fix loop and create the reusable, dynamic context lookup capability needed by both features.
*   **Key Tasks:**
    1.  Create & register the `debug:analyze_test_results` atomic template (LLM-based analysis of script output, returns structured `EvaluationResult` JSON).
    2.  Update Evaluator's D-E loop logic to correctly call this template for the `<evaluator>` step and use its `success` field for loop control.
    3.  Implement the **`system:get_context` Direct Tool executor** (`execute_get_context`). This function takes parameters (query, history, etc.), constructs `ContextGenerationInput`, calls `memory_system.get_relevant_context_for`, and returns the list of file paths.
    4.  Register `system:get_context` as a Direct Tool with the Handler.
    5.  Create & register the `debug:generate_fix` atomic template (takes error, context; returns fix proposal).
    6.  Define the Director step template for the `debug:loop`. Implement its logic: if tests failed (based on input from Evaluator step), call `system:get_context` (using `<call>`), read files (needs another tool?), call `debug:generate_fix`.
    7.  Unit test `debug:analyze_test_results` (mock LLM), `system:get_context` (mock MemorySystem), `debug:generate_fix` (mock LLM). Integration test the Director step's ability to chain these calls.
*   **Deliverable:** The debug loop can run tests, correctly analyze pass/fail using an LLM, dynamically look up context based on failure, and generate a fix proposal (LLM mocked). The shared `system:get_context` tool is functional.

---

**Phase 5: Complete Debug-Fix Loop (Aider Integration & Final Template)**

*   **Goal:** Integrate Aider fix application into the loop and define the final, runnable `debug:loop` template.
*   **Key Tasks:**
    1.  Update the Director step template (from Phase 4) to take the proposed fix and call the `aider:automatic` Direct Tool (using `<call>`), passing the fix and relevant files.
    2.  Define the final, top-level `debug:loop` template (`type="director_evaluator_loop"`) referencing the Director step template, the `debug:analyze_test_results` template (for the Evaluator step), the `script_execution` details, and termination conditions. Register it.
    3.  Write end-to-end integration tests for `/task debug:loop ...`, mocking the test script, context lookup, fix generation LLM, and Aider application, verifying the loop flow and termination conditions.
*   **Deliverable:** Fully functional `/task debug:loop` command executing the test-analyze-context-fix-apply cycle (using mocks for external/LLM parts).

---

**Phase 6: S-Expression Parser & Basic `call` Evaluation**

*   **Goal:** Implement the S-expression parser and the core evaluator logic to handle the `call` primitive, invoking existing registered targets.
*   **Key Tasks:**
    1.  Implement/choose S-expression parser -> AST.
    2.  Implement `SExprEvaluator` with `eval` method and simple `SExprEnvironment`.
    3.  Implement `call` primitive logic within `SExprEvaluator.eval`, including recursive argument evaluation and routing to Handler Direct Tools or `TaskSystem.execute_subtask_directly`.
    4.  Adapt REPL/Dispatcher to route S-expression strings `'(...)'` to `SExprEvaluator.eval`.
    5.  Unit test parser and evaluator `call` logic (mocking underlying targets). Test REPL/Dispatcher routing.
*   **Deliverable:** User can execute `/task '(call math:add (x 1) (y 2))'` and `/task '(call aider:automatic ...)'`. Nested calls work.

---

**Phase 7: S-Expression Workflow Primitives (`map`, `list`)**

*   **Goal:** Enable list processing within S-expressions by implementing `map` and `list`.
*   **Key Tasks:**
    1.  Implement `map` primitive logic in `SExprEvaluator.eval`. Handle evaluation of list expression, iteration, temporary `item` environment binding, recursive evaluation of task expression per item, and result collection. Ensure JSON list results from `call` are handled correctly.
    2.  Implement optional but recommended `list` primitive: `(list expr1 expr2 ...)` -> evaluates expressions and returns Python list.
    3.  Unit test `map` and `list` primitives extensively (different list inputs, task expressions, nested maps, error handling).
*   **Deliverable:** User can execute the target workflow via nesting: `/task '(map (call aider:automatic ...) (map (call plan:step_to_instructions ...) (call plan:generate ...)))'`.

---

**Phase 8: S-Expression Context Handling (`get_context`)**

*   **Goal:** Allow S-expression workflows to dynamically retrieve context.
*   **Key Tasks:**
    1.  Implement `get_context` primitive logic in `SExprEvaluator.eval`. It should evaluate its arguments, construct `ContextGenerationInput`, and internally call the **shared `system:get_context` Direct Tool executor** (implemented in Phase 4).
    2.  Modify `call` primitive logic to parse/evaluate an optional `(files <list_expression>)` argument and pass the result to the underlying target invocation (`SubtaskRequest` or Direct Tool).
    3.  Ensure initial history string from REPL/Dispatcher is available in the top-level `SExprEnvironment`.
    4.  Unit test `get_context` primitive. Integration test `call` with the `(files ...)` argument, including using a nested `get_context` call.
*   **Deliverable:** User can execute `/task '(call aider:automatic (prompt "...") (files (get_context ...)))'`.

---

**Phase 9: Refinement, Documentation & Comprehensive Testing**

*   **Goal:** Ensure robustness, usability, and maintainability of both the Debug-Fix Loop and S-Expression features.
*   **Key Tasks:**
    1.  **Testing:** Add comprehensive integration tests covering interactions between Debug-Fix Loop steps, complex S-expression workflows, error propagation in both systems, context handling edge cases.
    2.  **Error Handling:** Refine all error messages (parser, evaluator, loop steps) for clarity. Ensure consistent `TaskResult` error formatting.
    3.  **Performance:** Basic checks for Debug-Fix Loop cycle time and S-expression evaluation overhead.
    4.  **Documentation:** Update REPL `/help`. Document `debug:loop` task and its parameters. Document S-expression syntax, supported primitives (`call`, `map`, `get_context`, `list`), and provide examples. Update relevant component READMEs, patterns, and ADR statuses.
    5.  **Code Cleanup:** Address TODOs, refactor for clarity, ensure adherence to standards.
*   **Deliverable:** Well-tested, documented, robust Debug-Fix Loop and S-Expression workflow features.

