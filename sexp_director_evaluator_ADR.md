**ADR: Director-Evaluator Pattern Implementation via S-Expression DSL**

**Status:** Accepted

**Context:**

1.  The Director-Evaluator (D-E) pattern is a valuable workflow for tasks requiring iterative refinement based on feedback (e.g., code generation and testing, plan generation and validation).
2.  Previous architectural discussions and documentation (e.g., ADR 10, pattern documents) considered or described implementing this pattern via a dedicated XML composite task type (e.g., `<task type="director_evaluator_loop">`), which would be parsed into an internal AST node and executed with specific logic within the core Template Evaluator.
3.  A subsequent architectural decision established a "Strict Separation" model: XML is used *only* for defining **atomic task templates**, while an **S-expression DSL** is introduced to handle **all workflow composition** (sequences, mapping, conditionals, loops, etc.), invoked programmatically (e.g., via `/task`).
4.  This creates a conflict: implementing the D-E loop as an XML composite type would violate the Strict Separation principle and require the core Template Evaluator to retain complex control-flow logic that should ideally reside within the workflow composition language (the S-expression DSL).
5.  Therefore, a decision is needed on how to implement the D-E pattern within the new architecture.

**Decision:**

1.  The Director-Evaluator pattern **will NOT be implemented** as a dedicated XML composite task type (e.g., `<task type="director_evaluator_loop">`). Definitions related to such a type will be removed from the XML schema and the core Template Evaluator's responsibilities.
2.  The logic of the Director-Evaluator iterative loop **will be expressed and executed using the S-expression DSL**.
3.  Implementing the D-E pattern in S-expressions will rely on core DSL primitives, including:
    *   **Invocation (`(<identifier> <arg>*)`):** To call the atomic tasks acting as the Director and Evaluator components (which are defined in XML), and any optional script execution tools (like `system:run_script`).
    *   **Binding (`(bind <symbol> <expression>)` or `(let (...) ...)`):** To capture the outputs of the Director, script (if used), and Evaluator steps within each iteration and pass data (like feedback) between iterations.
    *   **Conditionals (`(if <cond> <then> <else>)`):** To check the Evaluator's result (`success` status) and the current iteration count against the maximum limit to determine whether to terminate or continue the loop.
    *   **(Potentially) Looping/Recursion:** While simple loops might be initially implemented by generating unrolled S-expression sequences using `bind` and `if`, a robust implementation will likely require either a dedicated `(loop ...)` primitive or support for defining and calling recursive functions within the S-expression DSL in a future iteration.
4.  The `SexpEvaluator` component will be responsible for executing these S-expression workflows.

**Rationale:**

*   **Architectural Consistency:** This decision aligns strictly with the "XML for Atomic Definitions, S-expressions for Composition" principle. All complex control flow, including iteration and conditionals inherent in the D-E pattern, resides within the dedicated workflow language.
*   **Avoids Logic Duplication:** It prevents implementing looping and conditional logic within the core Template Evaluator (for an XML type) when similar primitives (`if`, potentially `loop`/recursion) are needed in the `SexpEvaluator` anyway.
*   **Simplifies Core Components:** The XML schema becomes simpler by removing the composite D-E type. The core Template Evaluator simplifies its role, focusing only on executing atomic task bodies.
*   **Leverages DSL Power:** Utilizes the expressiveness and compositionality of the S-expression DSL to implement a sophisticated pattern. The pattern can be adapted or customized more easily within the DSL than via a rigid XML structure.

**Alternatives Considered:**

1.  **Implement `<task type="director_evaluator_loop">` in XML/Core Evaluator:**
    *   *Rejected because:* It violates the Strict Separation principle decided upon. It would require the core Template Evaluator to handle complex iteration and state management, duplicating logic needed in the S-expression DSL. It makes the XML schema and core Evaluator more complex.

**Consequences:**

*   **Positive:**
    *   Maintains a clean architectural separation between static definitions (atomic XML) and dynamic workflows (S-expressions).
    *   Simplifies the XML schema and the core Template Evaluator.
    *   Consolidates complex control-flow logic within the `SexpEvaluator`.
    *   Allows for potentially more flexible and customizable D-E implementations via the DSL.
*   **Negative:**
    *   Increases the required capabilities of the initial S-expression DSL implementation (must include binding and conditionals from the start).
    *   Requires users or LLMs to generate potentially more complex S-expression workflows to achieve the D-E pattern, instead of using a single XML tag.
    *   May require dedicated looping or recursion primitives in the S-expression DSL for elegant D-E implementation, potentially increasing DSL complexity later.
    *   Requires significant updates to existing documentation (like the D-E pattern document, ADR 10) that described the XML implementation.

**Related Documents:**

*   ADR: [Link to ADR establishing Strict Separation / S-expression DSL] (Or PRD)
*   IDL: `src/sexp_evaluator/sexp_evaluator_IDL.md` (Defines required primitives like `bind`, `if`, invocation)
*   IDL: `src/evaluator/evaluator_IDL.md` (Shows simplified role of core Template Evaluator)
*   IDL: `src/system/contracts/protocols.md` (Shows removal of composite XML types)
*   Pattern: `docs/system/architecture/patterns/director-evaluator.md` (Needs update to describe S-expression implementation)
*   ADR 10: Evaluator-to-Director Feedback Flow (Context is relevant, but XML implementation details are superseded by this ADR)

