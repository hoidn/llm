**ADR: Inline Atomic Task Definition via `defatom`**

**Status:** Proposed

**Context:**

*   Currently, atomic tasks (primarily LLM-driven operations) must be defined externally (e.g., XML, Python code) and pre-registered with the `TaskSystem`.
*   Users writing S-expression workflows cannot define simple, reusable LLM tasks directly within their workflow definitions.
*   This requires external setup even for straightforward, workflow-specific LLM prompts, hindering rapid prototyping and encapsulation within the DSL.
*   Implementing full lexical function definition (`define`/`lambda` with closures and direct `llm-call`) is significantly complex and represents a major architectural shift beyond the current roadmap.
*   A mechanism is needed to allow inline definition for convenience, without the full complexity of lexical closures for task bodies, using a concise syntax.

**Decision:**

1.  Introduce a new **special form** to the S-expression DSL: `defatom`.
2.  **Syntax:**
    ```sexp
    (defatom <task-name-symbol>
      (params (<param1-symbol> <param2-symbol> ...)) ;; Defines expected parameters
      (instructions "<prompt-template-string-with-{{param}}->") ;; Core LLM prompt/instructions
      [(description "<description-string>")] ;; Optional user-facing description
      [(subtype "<subtype-string>")] ;; Optional, defaults to "standard"
      ;; Potentially other optional metadata like (model ...) later
    )
    ```
    *Self-Contained Edit:* Added square brackets `[]` around the `(description ...)` part to indicate it is optional.

3.  **Evaluation Logic (`SexpEvaluator._eval_special_form`):**
    *   The evaluator will parse the components of the `defatom` form without evaluating them as standard arguments. It must handle the optional presence of `description` and `subtype`.
    *   It will construct a dictionary representing an atomic task template:
        *   `name`: String version of `<task-name-symbol>`.
        *   `type`: Hardcoded to `"atomic"`.
        *   `params`: Auto-generated dictionary mapping parameter symbol strings to basic definitions (e.g., `{"type": "any", "description": "(inline)"}`). *(Future enhancement: Could potentially parse richer type/description info from the `params` list if a specific format is defined)*.
        *   `description`: Provided `<description-string>` **or a default value (e.g., empty string or "Inline task definition") if omitted.**
        *   `instructions`: Provided `<prompt-template-string...>`.
        *   `subtype`: Provided `<subtype-string>` or `"standard"`.
    *   It will call `self.task_system.register_template()` with this dictionary, adding/overwriting the task in the **global registry**. Standard registry behavior (e.g., overwriting existing tasks with the same name with a warning) applies.
    *   **(Recommended)** It will bind `<task-name-symbol>` in the *current lexical environment* (`env.define(...)`) to a callable wrapper. This wrapper, when called, will format its arguments into a `SubtaskRequest` and invoke `self.task_system.execute_atomic_template(<task-name-string>, ...)`.
    *   The `defatom` form will return the `<task-name-symbol>`.
4.  **Execution:** Tasks defined via `defatom` are executed using the standard `TaskSystem` -> `AtomicTaskExecutor` pathway, using the globally registered template definition. They can be called either via the lexical wrapper (if present in scope) or via the standard task lookup mechanism if the wrapper isn't in scope.

**Consequences:**

*   **Pros:**
    *   Allows users to define simple, reusable LLM tasks directly within S-expression workflows using concise syntax.
    *   Improves workflow readability and encapsulation for common LLM patterns.
    *   Leverages the existing, tested `TaskSystem` registry and `AtomicTaskExecutor` infrastructure.
    *   Significantly lower implementation complexity compared to adding full lexical closures and function application for tasks.
    *   The optional lexical binding makes defined tasks immediately callable in the current scope.
    *   Makes simple definitions slightly less verbose by not requiring a description.
*   **Cons:**
    *   Defined tasks are added to the **global** namespace, potentially causing collisions if not managed carefully by users.
    *   Does not provide true lexical scoping for task definitions (they don't disappear when the S-expression scope ends).
    *   The definition mechanism is specific to *atomic tasks* and doesn't allow defining complex procedural logic within the task body itself (the body remains an LLM prompt template).
    *   The auto-generated `params` definition in the registry will be basic; complex type validation for inline tasks isn't included initially.
    *   Omitting the description might slightly hinder discoverability if relying on tools that parse descriptions (though the task name should still be clear).
*   **Impact:**
    *   Requires modification of `SexpEvaluator` to add the new `defatom` special form logic, including handling the optional `description`.
    *   Requires modification of `SexpEnvironment`'s usage if the recommended lexical binding is implemented.
    *   `TaskSystem`, `TemplateRegistry`, and `AtomicTaskExecutor` require minimal or no changes.
    *   Requires updates to DSL documentation and examples.

**Alternative Considered:**

*   **Full Lexical Functions (`define`/`lambda` + `llm-call`):** Rejected for now due to significantly higher implementation complexity and architectural impact. It remains a potential future evolution.
*   **Longer Name (`define-atomic-task`):** Rejected in favor of the more concise `defatom`.
*   **Mandatory Description:** Rejected in favor of allowing optional description for simpler inline definitions.

**Decision Rationale:**

`defatom` provides a pragmatic balance, offering the desired inline definition capability with manageable implementation effort by reusing existing components. Making the description optional enhances convenience for simple, self-explanatory inline tasks. The recommended lexical binding provides immediate usability within scope. The global registration aspect is accepted as a trade-off for simplicity compared to full closures.
