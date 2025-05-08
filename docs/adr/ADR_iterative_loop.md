# ADR: iterative-loop Special Form for LLM-Driven Iterative Workflows

**Status:** Proposed

## Context:
- The S-expression DSL is used for orchestrating complex workflows, including those involving LLM calls, tool execution, and iterative refinement (e.g., coding tasks with test feedback).
- Implementing such iterative loops using only basic primitives (if, lambda, set!, task calls) can be verbose, error-prone, and obscure the high-level pattern.
- Previous loop proposals (e.g., basic loop, original director-evaluator-loop) either lacked flexibility (fixed iterations), had overly complex signatures, or lacked robust mechanisms for handling state and loop control based on iteration outcomes.
- A common pattern involves executing an action, validating it programmatically (e.g., running tests), using an LLM to analyze the results of both steps, and then deciding whether to stop or retry with modifications.
- A declarative S-expression construct is needed to cleanly represent this Execute-Validate-Analyze-Decide pattern, integrating LLM analysis into the loop's control flow.

## Decision:
Introduce a new special form to the S-expression DSL: `(iterative-loop ...)` designed to explicitly support this pattern.

### 1. Syntax:
```sexp
(iterative-loop
  ;; -- Loop Configuration --
  (max-iterations <number-expr>)       ; Max loop cycles (non-negative integer)
  (initial-input <structured-expr>)   ; Structured input for the *first* executor call
  (test-command <cmd-string-expr>)    ; Command string for the validator phase

  ;; -- User-Provided Phase Functions --
  (executor   <executor-function-expr>)   ; Executes the main task
  (validator  <validator-function-expr>)  ; Runs programmatic validation (e.g., tests)
  (controller <controller-function-expr>) ; Calls LLM analysis task & decides next step
)
```

### 2. Defined Data Types:
```typescript
/** TaskResult from Executor [Type Reference: System:TaskResult:1.0] */
type TaskResult = dict<string, Any>; // { status: "COMPLETE"|"FAILED", content: Any, notes: dict }

/** ValidationResult from Validator [Type: Loop:ValidationResult:1.0] */
interface ValidationResult {
    stdout: string; stderr: string; exit_code: int; error?: string;
}

/** ControllerDecision returned by Controller [Type: Loop:ControllerDecision:1.0] */
type ControllerDecision =
    | list<'continue', Any> // Value is structured input for next executor call
    | list<'stop', Any>;     // Value is the final result of the loop

/** Structured output from the Controller's internal LLM analysis task [Type: Loop:StructuredAnalysisResult:1.0] */
interface StructuredAnalysisResult {
    success: boolean;             // True if the iteration's goal was met.
    analysis: string;             // Explanation/summary of the iteration's outcome.
    next_input?: string;          // The prompt/input for the *next* executor iteration (required if success=false).
    new_files?: list<string>;     // Optional list of new files identified during analysis to add to the context for the next iteration.
}
```

(A corresponding Pydantic model, `StructuredAnalysisResult`, should be defined in `src.system.models` or similar).

### 3. Loop Configuration Arguments:
- `(max-iterations <number-expr>)`: Evaluated once. Must result in a non-negative integer. Defines the maximum number of full E-V-C cycles.
- `(initial-input <structured-expr>)`: Evaluated once. Must result in a structured value (e.g., dictionary, S-expression association list) containing the necessary input(s) for the first executor call (e.g., `(list (list 'prompt "...") (list 'files '("f1")))`).
- `(test-command <cmd-string-expr>)`: Evaluated once. Must result in a string representing the shell command to be executed by the validator phase in each iteration.

### 4. Phase Function Contracts:
- `(executor <executor-function-expr>)`:
  - Signature: `(lambda (current_structured_input: Dict|AssocList, iteration_number: int) -> TaskResult)`
  - Action: Executes the primary task for the iteration based on `current_structured_input`.
  - Returns: `TaskResult` dictionary.

- `(validator <validator-function-expr>)`:
  - Signature: `(lambda (test_command_string: string, iteration_number: int) -> ValidationResult)`
  - Action: Runs the `test_command_string` programmatically (e.g., via `system:execute_shell_command`).
  - Returns: Structured `ValidationResult` dictionary.

- `(controller <controller-function-expr>)`:
  - Signature: `(lambda (executor_result: TaskResult, validation_result: ValidationResult, current_structured_input: Dict|AssocList, iteration_number: int) -> ControllerDecision)`
  - Action: Orchestrates analysis of `executor_result` and `validation_result`. Assumed to internally invoke a separate LLM analysis task (e.g., `user:analyze-iteration-structured`) designed to produce `StructuredAnalysisResult` JSON. Parses this JSON, then constructs and returns the appropriate `ControllerDecision` list (`'(continue <next_structured_input>)` or `'(stop <final_loop_result>)`).
  - Returns: `ControllerDecision` list.

### 5. Evaluation Logic (SexpEvaluator._eval_special_form):
1. Parses and validates the loop's structure and clauses.
2. Evaluates `max-iterations`, `initial-input`, and `test-command` expressions once. Validates types.
3. Evaluates phase function expressions, ensuring they result in callable S-expression functions (e.g., Closure objects).
4. Initializes loop state (`current_iteration`, `current_loop_input`, `loop_result`).
5. Enters the loop, checking `current_iteration <= max_iter_val`.
6. Calls `executor_fn` with `current_loop_input` and `iteration_number`.
7. Calls `validator_fn` with `test_cmd_string` and `iteration_number`.
8. Calls `controller_fn` with results from executor and validator, plus `current_loop_input` and `iteration_number`.
9. Validates the format of the returned `decision_val` (`(list 'continue|stop <value>)`).
10. If 'stop, stores the associated value as `loop_result` and terminates the loop.
11. If 'continue, updates `current_loop_input` with the associated value, stores the current `executor_result` as the potential `loop_result` (if max iterations is hit), increments `current_iteration`, and continues the loop.
12. If the loop finishes due to `max_iterations`, returns the stored `loop_result` (the result from the last successful executor call).
13. Propagates any `SexpEvaluationError` raised during configuration or phase execution.

### 6. Required Helper LLM Task:
- Effective use of this `iterative-loop` pattern relies on the pre-definition (e.g., via `defatom`) of an atomic LLM task responsible for the analysis step within the controller.
- This analysis task (e.g., `user:analyze-iteration-structured`) must accept relevant inputs (executor status/output, validator stdout/stderr/exit code, original prompt, etc.) and be prompted to reliably produce JSON output conforming precisely to the `StructuredAnalysisResult` schema (`{success: bool, analysis: str, next_input?: str, new_files?: list[str]}`).

## Consequences:

### Pros:
- Provides a clear, declarative structure for a common iterative pattern (Execute -> Validate -> Decide).
- Reduces boilerplate S-expression code compared to manual implementation with if/lambda/set!.
- Enforces explicit loop control (continue/stop), allowing early termination on success or failure.
- Explicitly separates programmatic validation (validator) from higher-level analysis and decision-making (controller).
- Integrates LLM-based analysis naturally within the controller phase via standard task invocation.
- Structured input/output for phases improves clarity and robustness.

### Cons:
- Adds a new complex special form to the SexpEvaluator.
- The structure is prescriptive for the E-V-C pattern; significantly different iteration types would still require lower-level primitives.
- Relies heavily on a well-defined and reliably implemented helper LLM analysis task (`user:analyze-iteration-structured`) for the controller phase. Prompt engineering for this task is crucial.
- Debugging involves tracing state through loop iterations and potentially debugging the LLM analysis task called by the controller.

### Impact:
- Requires significant modification of SexpEvaluator to add the `_eval_iterative_loop` handler.
- Requires defining the `StructuredAnalysisResult` Pydantic model.
- Requires updates to `sexp_evaluator_IDL.md` and DSL documentation/examples.
- May necessitate list/dictionary manipulation primitives within the DSL (e.g., for combining file lists in the controller) if not already present.

## Alternatives Considered:
- **Pure S-expression Function**: Implementing the loop using lambda, if, set!, etc. Rejected: Too verbose, complex state management for users, error-prone.
- **Python-based Orchestrator**: Moving the loop logic outside the DSL. Rejected: Counter to the goal of DSL-driven orchestration.
- **Original 4-Phase D-E-E-C Loop**: More complex signature, potentially unnecessary director phase within the loop if planning happens upfront.
- **Simplified Loops**: Loops stopping only on max-iterations or using simpler controller feedback (e.g., (bool, str)). Rejected: Lacks explicit control flow needed for practical iteration (early stop on success/failure), ambiguous state transfer.

## Decision Rationale:
The proposed 3-phase `iterative-loop` (E-V-C) provides the best balance for this specific pattern:
- It offers a declarative structure significantly simpler than manual implementation.
- It retains explicit loop control (continue/stop), crucial for efficiency and correctness.
- It separates the mechanical validation (validator) from the potentially complex analysis/decision logic (controller).
- The controller naturally accommodates LLM-driven analysis by invoking a dedicated, structured-output LLM task.
- The use of structured data for state (`current_structured_input`) ensures clarity in data flow.

While requiring a helper LLM task, this approach centralizes the complex analysis logic within that task, keeping the S-expression structure of the loop itself focused on orchestration. This model is deemed more robust and practical than alternatives lacking explicit control or structured feedback.
