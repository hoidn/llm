**Draft PRD: Automated Debug-Fix Loop (`/task debug:loop`)**

**1. Introduction / Overview**

*   **Problem:** Manually debugging code involves a repetitive cycle: run tests, see a failure, analyze the error, find relevant code, attempt a fix, re-run tests. This can be time-consuming, especially for common or simple errors.
*   **Proposed Solution:** Implement an automated "Debug-Fix Loop" feature, accessible via a programmatic `/task` command (`/task debug:loop`). This feature will leverage existing testing tools, LLM analysis/fix generation, and automated code application (via Aider) to attempt to automatically fix failing tests within a defined scope.
*   **Benefit:** Reduce developer time spent on simple debugging cycles, allowing focus on more complex issues. Provide a demonstration of autonomous task execution within the framework.

**2. Goals**

*   Provide a REPL command (`/task debug:loop`) to initiate an automated test-analysis-fix-retest cycle.
*   Allow users to specify the test command to run.
*   Allow users to optionally specify target files to focus the fixing effort and context lookup.
*   Automatically analyze test failures to guide fix generation.
*   Utilize an LLM to propose code fixes based on failure analysis and code context.
*   Automatically apply proposed fixes using the integrated Aider tool.
*   Repeat the cycle until tests pass or a maximum number of attempts is reached.
*   Provide clear feedback to the user on the loop's progress and final outcome.

**3. Non-Goals**

*   Guaranteeing a successful fix for all types of test failures.
*   Handling complex build steps or environment setup required before running tests.
*   Debugging errors that require runtime analysis or interactive debugging sessions.
*   Implementing the underlying `director_evaluator_loop` execution engine (this PRD assumes it exists or is built separately).
*   Implementing the core `MemorySystem` context lookup or the `AiderBridge` fix application (this PRD assumes those components/tools exist and are callable).
*   Replacing human oversight entirely; the loop provides assistance, not guaranteed solutions.
*   Sophisticated strategies for selecting *which* fix to apply if multiple are proposed.

**4. Target Audience**

*   Developers using the system via the REPL interface for coding and debugging tasks.

**5. User Stories**

*   As a developer, I want to run `/task debug:loop --test_cmd="pytest -k test_my_new_feature"` so that the system automatically tries to fix failures related to `test_my_new_feature` and re-runs the test until it passes or times out.
*   As a developer, after seeing a test fail in `src/logic.py`, I want to run `/task debug:loop --test_cmd="pytest" --target_files='["src/logic.py"]'` so the system focuses its context lookup and fix attempts primarily on that file.
*   As a developer, I want the debug loop to stop after 3 attempts if the test still fails, by running `/task debug:loop --test_cmd="pytest" --max_cycles=3`, to prevent runaway processes.
*   As a developer, when the loop finishes, I want to see a summary indicating whether the tests passed, how many cycles ran, and which files (if any) were modified by Aider.

**6. Functional Requirements (FRs)**

*   **FR-DFL-1 (Invocation):** The feature must be invokable via the REPL command `/task debug:loop`.
*   **FR-DFL-2 (Parameters):** The command must accept:
    *   `--test_cmd="<command_string>"` (Required): The exact shell command to execute tests.
    *   `--target_files='<json_list_string>'` (Optional): A JSON string representation of a list of file paths to focus context lookup and fix attempts.
    *   `--max_cycles=<integer>` (Optional): The maximum number of fix attempts (test-analyze-fix-apply cycles) to perform. Defaults to a reasonable value (e.g., 3 or 5).
*   **FR-DFL-3 (Template):** A `director_evaluator_loop` template named `debug:loop` must be registered in the `TaskSystem`. This template orchestrates the workflow.
*   **FR-DFL-4 (Execution Flow):** The `debug:loop` template execution must perform the following cycle:
    1.  Run the specified `test_cmd` using the script execution capability.
    2.  Analyze the results (exit code, stdout, stderr).
    3.  If tests passed (e.g., exit code 0), terminate the loop successfully.
    4.  If tests failed:
        *   Perform context lookup via `MemorySystem` (using error details, target files, potentially history if enabled later) to get relevant code snippets.
        *   Generate a proposed code fix using an LLM task (passing error details and code context).
        *   Apply the proposed fix using the `aider:automatic` tool/task (passing the fix and relevant target files).
    5.  Repeat from step 1 until tests pass or `max_cycles` is reached.
*   **FR-DFL-5 (Test Analysis):** The analysis step must correctly identify success (exit code 0) vs. failure and extract relevant error messages from `stderr` for use in fix generation.
*   **FR-DFL-6 (Context Lookup):** The context lookup step (if tests failed) must use the test error information and any provided `target_files` to query the `MemorySystem`.
*   **FR-DFL-7 (Fix Generation):** A dedicated LLM task/template must be called to generate a code fix suggestion based on the error and context.
*   **FR-DFL-8 (Fix Application):** The `aider:automatic` task/tool must be invoked correctly with the generated fix and target files.
*   **FR-DFL-9 (Loop Termination):** The loop must terminate under three conditions: tests pass, `max_cycles` reached, or an unrecoverable error occurs within a step (e.g., context lookup fails critically, fix generation fails, Aider fails to apply).
*   **FR-DFL-10 (Output):** Upon termination, the final `TaskResult`'s `content` should clearly state the outcome (success, failure after max cycles, error) and the number of cycles run. The `notes` should include details like the final test status and a list of files modified by Aider during the loop.
*   **FR-DFL-11 (Error Handling):** Failures within loop steps (context lookup, fix gen, Aider apply) should be handled gracefully, ideally terminating the loop and reporting the failure step in the final `TaskResult`.

**7. Non-Functional Requirements (NFRs)**

*   **NFR-DFL-1 (Reliability):** The loop should execute consistently and terminate reliably under the defined conditions. Internal errors should be reported clearly.
*   **NFR-DFL-2 (Performance):** Each cycle should complete within a reasonable timeframe (highly dependent on test suite speed, LLM response time, Aider speed). Provide feedback if steps are taking long.
*   **NFR-DFL-3 (Usability):** The `/task` command should be easy to use. The final output should be clear and informative.
*   **NFR-DFL-4 (Resource Usage):** The loop should operate within the general resource constraints of the TaskSystem/Handler (though multiple LLM calls and Aider runs will consume turns/tokens).

**8. Design & Technical Approach (High-Level)**

*   Implement as a `director_evaluator_loop` template registered with `TaskSystem`.
*   Utilize separate atomic templates/tasks for distinct steps: `debug:analyze_test_results`, `debug:generate_fix`.
*   Utilize the existing script execution capability (via Handler tool) for running tests.
*   Utilize the existing `MemorySystem` context lookup capability (likely via a `system:get_context` task/tool called by the Director step).
*   Utilize the existing `aider:automatic` Direct Tool for applying fixes.

**9. Success Metrics & Acceptance Criteria (ACs)**

*   **AC-DFL-1:** User can invoke `/task debug:loop --test_cmd="pytest ..."`.
*   **AC-DFL-2:** If the test command initially passes, the loop terminates after 1 cycle reporting success.
*   **AC-DFL-3:** If the test command fails, the system attempts context lookup (verifiable via mock/log), fix generation (mock/log), and Aider application (mock/log).
*   **AC-DFL-4:** If the fix applied by (mocked) Aider leads to the (mocked) test command passing on the next cycle, the loop terminates reporting success and listing modified files.
*   **AC-DFL-5:** If the test command consistently fails (mocks ensure this), the loop terminates after `max_cycles` reporting failure.
*   **AC-DFL-6:** Providing `--target_files` influences the files passed to the context lookup and Aider application steps (verify via mocks).
*   **AC-DFL-7:** The final `TaskResult` accurately reflects the outcome (success/failure/error) and includes cycle count and modified files in notes.
*   **AC-DFL-8:** Critical errors within a step (e.g., mocked Aider failure) cause the loop to terminate early with an appropriate error status.

**10. Open Questions / Future Considerations**

*   How to handle tests requiring specific environment variables or setup? (Likely out of scope for v1).
*   Strategy for handling *multiple* test failures in one run? (Focus on the first failure initially).
*   More sophisticated fix generation prompts or techniques?
*   Allowing user intervention or confirmation during the loop? (Out of scope for this automated version).

