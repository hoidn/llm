## ADR: Python Orchestration with Embedded S-expression Evaluation

**Status:** Proposed

**Context:**

*   The system architecture includes core Python components (`TaskSystem`, `MemorySystem`, `BaseHandler`) and a custom S-expression DSL evaluated by `SexpEvaluator`.
*   The S-expression DSL is intended for orchestrating tasks, tool calls, and workflow logic.
*   Analysis of complex workflow requirements (e.g., multi-stage prompt engineering like "Vibecoding", general data preparation) revealed a need for significant data manipulation capabilities, particularly complex string construction (reading multiple files, formatting, concatenation) and potentially list/dict operations.
*   Implementing a comprehensive set of data manipulation primitives (e.g., `string-append`, `string-join`, `string-split`, file reading orchestration) directly within the custom `SexpEvaluator` would:
    *   Require significant development effort.
    *   Duplicate functionality already robustly available in Python's standard library.
    *   Increase the complexity and maintenance burden of the `SexpEvaluator`.
*   Alternative approaches like embedding arbitrary Python execution (`py-eval`) introduce unacceptable security risks and integration complexity.

**Decision:**

1.  **Primary Orchestration in Python:** High-level workflow control, complex data preparation (especially multi-source string construction for prompts), data fetching (e.g., reading multiple files needed for a single prompt), and iterative logic (loops over data) should primarily be implemented in **Python code**.
2.  **Role of S-expression DSL:** The S-expression DSL, executed via `SexpEvaluator.evaluate_string`, will be used as an **embedded component invoked by Python**. Its primary roles will be:
    *   Executing registered atomic tasks and tools using their symbolic names.
    *   Defining and executing specific, self-contained sub-workflows where the DSL's syntax or abstraction provides clarity (e.g., simple conditional task calls).
    *   Potentially representing configuration or rules in a data-like format.
3.  **Interaction Pattern:**
    *   Python code will prepare the necessary data context (e.g., build complex prompt strings, fetch lists of items).
    *   Python code will instantiate `SexpEnvironment`.
    *   Python code will bind the prepared data to variable names within the `SexpEnvironment`'s bindings.
    *   Python code will call `SexpEvaluator.evaluate_string(sexp_string, initial_env=env)`, passing the S-expression *string* and the populated environment.
    *   The S-expression string will primarily reference the pre-bound variables for complex data and focus on invoking tasks/tools or simple DSL control flow.
    *   Python code will receive and process the results returned by `evaluate_string`.
4.  **Limit New DSL Primitives:** Avoid adding new primitives to the `SexpEvaluator` that primarily duplicate standard Python data manipulation capabilities (especially for strings, lists, dicts). Focus new primitives on core DSL control flow (`if`, `let`, etc.) or essential interactions with system components (`get_context`).

**Consequences:**

*   **Pros:**
    *   Leverages Python's mature and powerful standard library for complex data manipulation (especially strings), reducing development effort.
    *   Simplifies the `SexpEvaluator` by avoiding the need to implement and maintain numerous data manipulation primitives.
    *   Avoids the security risks and complexity associated with `py-eval` or similar arbitrary code execution embeddings.
    *   Provides a clear separation: Python for general-purpose logic and data prep, S-expression DSL for task/tool invocation and domain-specific workflow steps.
    *   Likely easier for developers primarily familiar with Python to implement complex orchestration logic.
    *   Effectively resolves the bottleneck identified for building complex prompts dynamically.
*   **Cons:**
    *   Overall workflow logic may be split between Python files and S-expression strings/files, potentially reducing the self-contained nature of S-expression workflows.
    *   Requires a Python orchestration layer to prepare data and call the evaluator; S-expressions are less likely to be run standalone without a Python caller providing context.
    *   Requires careful management of the data passed between Python and the `SexpEnvironment`.
    *   May slightly increase the overhead for workflows that *could* have been done purely in S-expressions if more primitives were available (though often negligible).
*   **Impact:**
    *   Development patterns will shift towards Python for high-level orchestration and data preparation.
    *   `SexpEvaluator` feature scope is contained, focusing on evaluation and core primitives/special forms.
    *   Project documentation and examples must clearly illustrate this interaction pattern.

**Alternatives Considered:**

1.  **Full Primitives in DSL:** Implement extensive Python-like primitives (strings, lists, etc.) in `SexpEvaluator`. Rejected due to high implementation effort, complexity, and duplication of Python capabilities.
2.  **Embedded Python (`py-eval`):** Add a primitive to execute arbitrary Python strings. Rejected due to security risks and integration complexity (environment bridging, error handling).
3.  **HyLang:** Replace the custom evaluator entirely with HyLang. Rejected as potentially overkill, a major architectural shift, and adds a significant new dependency, when the current evaluator infrastructure is mostly functional.
4.  **Python Builds AST (`evaluate_ast`):** Python constructs the S-expression AST directly as Python lists/objects. Considered viable and similar in benefit to the chosen approach, but potentially more verbose for developers than writing S-expression strings. The chosen approach allows S-expression snippets to still be stored/loaded as strings easily.

**Decision Rationale:**

This approach provides the most pragmatic balance between leveraging the existing S-expression evaluation infrastructure and utilizing the power and familiarity of Python for tasks it excels at (like complex data preparation and string manipulation). It directly addresses the limitations encountered when trying to perform complex prompt engineering solely within the current DSL, without requiring extensive additions to the DSL primitives or introducing the risks of arbitrary code execution. It keeps the `SexpEvaluator` focused on its core task evaluation and invocation capabilities while allowing Python to handle the general-purpose programming needs surrounding it.

---
