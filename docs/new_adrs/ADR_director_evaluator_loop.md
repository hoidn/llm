**ADR: Implementing a `director-evaluator-loop` Special Form for Iterative Workflows**

**Status:** Proposed

**Context:**

*   The S-expression DSL is used for orchestrating complex workflows, including those involving LLM calls, tool execution, and iterative refinement (e.g., the Aider coding loop).
*   Implementing such iterative loops (Director-Executor-Evaluator-Controller) using only basic primitives (`lambda`, `if`, `set!`, `get-field`) can be verbose, error-prone, and obscure the high-level pattern.
*   Phase 9b introduced a `(loop <count> <body>)` primitive for fixed iterations. Phase 10 introduced `lambda` for functional abstraction. Phase 10b is planned to add data access (`get-field`) and comparison primitives.
*   A more declarative, higher-level construct is desired to make defining these common iterative patterns simpler, more robust, and easier to read within the DSL.

**Decision:**

Introduce a new **special form** to the S-expression DSL: `(director-evaluator-loop ...)` designed to explicitly support the Director-Executor-Evaluator-Controller pattern for iterative workflows.

**Syntax:**

```sexp
(director-evaluator-loop
  ;; -- Configuration for the loop --
  (max-iterations <number-expr>)      ; Max number of loop iterations.
  (initial-director-input <expr>)   ; Expression evaluating to the input for the *first* director call.

  ;; -- User-defined phase functions (lambdas or names of S-expression functions) --
  (director   <director-function-expr>)
  (executor   <executor-function-expr>)
  (evaluator  <evaluator-function-expr>)
  (controller <controller-function-expr>)
)
```

**Arguments to the Special Form:**

* **(max-iterations <number-expr>):**
  * **<number-expr>:** An S-expression that must evaluate to a non-negative integer. Defines the maximum number of full D-E-E-C cycles.

* **(initial-director-input <expr>):**
  * **<expr>:** An S-expression that is evaluated once at the beginning. Its result becomes the input to the first call of the director function.

* **(director <director-function-expr>):**
  * **<director-function-expr>:** An S-expression that must evaluate to a callable S-expression function (e.g., a lambda or a symbol bound to a lambda).
  * **Signature:** This function will be called by the loop with (current-input iteration-number).
    * **current-input:** For the first iteration, this is the result of initial-director-input. For subsequent iterations, it's the next-director-input provided by the controller function from the previous cycle.
    * **iteration-number:** The current iteration count (e.g., 1-indexed).
  * **Returns:** The "plan" or "action" to be passed to the executor function.

* **(executor <executor-function-expr>):**
  * **<executor-function-expr>:** An S-expression that must evaluate to a callable S-expression function.
  * **Signature:** This function will be called by the loop with (plan/action-from-director iteration-number).
  * **Returns:** The result of the execution.

* **(evaluator <evaluator-function-expr>):**
  * **<evaluator-function-expr>:** An S-expression that must evaluate to a callable S-expression function.
  * **Signature:** This function will be called by the loop with (execution-result plan/action-from-director iteration-number).
  * **Returns:** Feedback on the execution, typically a structure containing a status.

* **(controller <controller-function-expr>):**
  * **<controller-function-expr>:** An S-expression that must evaluate to a callable S-expression function.
  * **Signature:** This function will be called by the loop with (evaluation-feedback plan/action-from-director execution-result iteration-number).
  * **Returns:** A list of two elements:
    * **'(continue <next-director-input>):** To continue the loop. <next-director-input> will be passed to the director in the next iteration.
    * **'(stop <final-loop-value>):** To terminate the loop. <final-loop-value> will be the result of the entire director-evaluator-loop form.

**Evaluation Logic (SexpEvaluator._eval_special_form for director-evaluator-loop):**

1. Parse and validate the structure of the director-evaluator-loop form itself (ensure all required clauses are present).
2. Evaluate <number-expr> from (max-iterations ...) to get max_iter_val. Validate it's a non-negative integer.
3. Evaluate <expr> from (initial-director-input ...) to get current_director_input_val.
4. Evaluate each <*-function-expr> (for director, executor, evaluator, controller) to get the actual S-expression callable functions. Store these.
5. Initialize current_iteration = 1.
6. Initialize loop_result = nil (or a sensible default for premature exit).
7. Loop:
   a. If current_iteration > max_iter_val, terminate the loop. The loop_result (likely the result from the last controller's 'stop' or the last execution result before max iterations hit) is returned.
   b. Director Phase: Call the director function: plan_val = apply(director_fn, current_director_input_val, current_iteration).
   c. Executor Phase: Call the executor function: exec_result_val = apply(executor_fn, plan_val, current_iteration).
   d. Evaluator Phase: Call the evaluator function: eval_feedback_val = apply(evaluator_fn, exec_result_val, plan_val, current_iteration).
   e. Controller Phase: Call the controller function: decision_val = apply(controller_fn, eval_feedback_val, plan_val, exec_result_val, current_iteration).
   f. Validate decision_val: It must be a list of two elements, with the first being the symbol 'continue or 'stop.
   g. If (car decision_val) is 'stop:
      i. loop_result = (cadr decision_val).
      ii. Terminate the loop.
   h. If (car decision_val) is 'continue:
      i. current_director_input_val = (cadr decision_val).
      ii. loop_result = exec_result_val (or eval_feedback_val, TBD: what's the result if loop is continued but then hits max_iter?). Storing exec_result_val seems more aligned with returning the last "work product".
      iii. current_iteration = current_iteration + 1.
      iv. Go to step 7a.
   i. If decision_val is malformed, raise SexpEvaluationError.
8. Return loop_result.

(Note: apply here is a conceptual representation of invoking the S-expression functions with arguments. The actual mechanism will use SexpEvaluator._handle_invocation or similar.)

**Consequences:**

**Pros:**
* **Declarative Pattern:** Clearly expresses the Director-Executor-Evaluator-Controller flow.
* **Reduced Boilerplate:** Users don't need to implement the recursive loop structure, iteration counting, or state handoff manually using lower-level primitives.
* **Improved Readability:** S-expressions using this form will be easier to understand for this common pattern.
* **Centralized Loop Logic:** The core loop mechanics are handled robustly by the SexpEvaluator, reducing user error.
* **Flexibility via Lambdas:** Users retain full control over the logic within each phase by providing custom lambdas, which can call any other tasks or primitives (including those from Phase 10b like get-field).
* **Minimal New Primitives for Users:** This special form itself is the main addition. It leverages existing/planned general-purpose primitives within the user-supplied lambdas, rather than requiring many new primitives just for this loop.

**Cons:**
* **Increased SexpEvaluator Complexity:** Adds a significant new special form to the evaluator.
* **Prescriptive Structure:** While the lambdas are flexible, the overall four-phase structure (D-E-E-C) is fixed by the special form. More divergent iterative patterns would still need to be built with lower-level primitives.
* **Debugging:** Debugging issues within the user-supplied lambdas will still rely on general DSL debugging capabilities. Errors in the special form's own logic would require evaluator-level debugging.

**Impact:**
* Requires significant modification of SexpEvaluator to add _eval_director_evaluator_loop.
* Requires updates to sexp_evaluator_IDL.md to document the new special form.
* Requires updates to DSL documentation and examples.
* Relies on the robust implementation of Phase 10 (lambda) and the planned primitives of Phase 10b (get-field, comparison functions, list construction for the controller's return value).

**Alternatives Considered:**

1. **Pure S-expression Function (Composite DSL Procedure):**
   * Implement the loop using lambda, if, set!, etc., as a user-level S-expression function.
   * Rejected because: Too verbose for users, error-prone, and doesn't make the pattern a first-class citizen of the DSL. The special form provides better control over evaluation.

2. **Python-based Orchestrator:**
   * Implement the loop logic in Python, calling S-expression tasks for each phase.
   * Rejected because: Moves the orchestration out of the DSL, which is counter to the goal of having the DSL manage these workflows.

**Decision Rationale:**

The director-evaluator-loop special form provides the best balance of usability, expressiveness, and maintainability for this common and important iterative pattern. It significantly simplifies writing such loops in the DSL by abstracting the core iteration and state-passing mechanics, while still allowing full flexibility within each phase through user-defined S-expression functions. This approach leverages the planned general-purpose primitives (Phase 10b) effectively, rather than requiring a large new set of specialized primitives just for this loop.
