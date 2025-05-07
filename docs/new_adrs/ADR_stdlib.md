**ADR: S-expression Standard Library for Reusable Helper Functions**

**Status:** Proposed

**Context:**

*   The S-expression DSL is used for orchestrating complex workflows, including the `director-evaluator-loop` and direct task/tool invocations.
*   These workflows often involve repetitive patterns for accessing nested data within `TaskResult` objects (e.g., `(get-field (get-field task-result "notes") "error")`) or performing common checks (e.g., `(string=? (get-field task-result "status") "COMPLETE")`).
*   Defining these helper patterns inline using `lambda` for each workflow (Option 1) leads to code duplication, increased verbosity in the main workflow logic, and makes maintenance harder.
*   Implementing every conceivable helper as a new Python primitive in the `SexpEvaluator` (Option 4) would significantly increase the evaluator's complexity, make the DSL less self-contained, and reduce the ease with which users can define their own variations of such helpers.
*   A mechanism is needed to define common, reusable utility functions *within the S-expression paradigm itself* that can be shared across different S-expression workflows.

**Decision:**

1.  **Introduce an S-expression Standard Library Mechanism:**
    The system will support loading and pre-evaluating one or more S-expression files at application startup. These files will constitute a "standard library" of helper S-expression functions.

2.  **Helper Function Definition:**
    *   Helper functions will be defined within these standard library S-expression files using the existing `(lambda (params...) body...)` construct.
    *   These lambdas will be bound to names (symbols) in a base/root `SexpEnvironment` using a `(define helper-name (lambda ...))` special form or, if `define` is not yet a special form, via `(bind helper-name (lambda ...))` evaluated at the top level of the library file. The `define` approach is preferred for clarity if available.
    *   **Example Helpers:**
        ```sexp
        ;; In a file like src/sexp_stdlib/core_helpers.sexp
        (progn ;; Group multiple definitions
          (define (is-task-successful? task-result)
            (and (string=? (get-field task-result "status") "COMPLETE")
                 (null? (get-field (get-field task-result "notes") "error"))))
          
          (define (get-task-content task-result)
            (get-field task-result "content"))
          
          (define (get-task-parsed-content task-result)
            (get-field task-result "parsedContent"))

          (define (get-task-error-message task-result)
            (get-field (get-field (get-field task-result "notes") "error") "message"))
            
          (define (get-task-exit-code task-result)
            (get-field (get-field (get-field task-result "notes") "exit_code") ))
        )
        ```

3.  **Loading and Environment Population (Application Responsibility):**
    *   The `Application` class (or a dedicated initialization component) will be responsible for managing this standard library.
    *   Upon initialization, the `Application` will:
        *   Create a single, persistent base/root `SexpEnvironment` instance.
        *   Identify a designated directory for standard library S-expression files (e.g., `src/sexp_stdlib/`).
        *   Read each `.sexp` (or similarly named) file from this directory.
        *   For each file's content, call `SexpEvaluator.evaluate_string(stdlib_file_content, initial_env=base_sexp_env)`. This will execute the `(define ...)` or `(bind ...)` forms, populating the `base_sexp_env` with the helper function definitions.
    *   This `base_sexp_env` (or child environments created by `extend()`-ing it) will then be passed as the `initial_env` for all subsequent S-expression workflow evaluations (e.g., those initiated by the `Dispatcher`).

4.  **Usage:**
    *   S-expression workflows evaluated with this pre-populated environment can directly call the helper functions by their defined names, e.g., `(is-task-successful? some-task-result-var)`.

**Consequences:**

*   **Pros:**
    *   **Reusability:** Helper functions are defined once and usable across all S-expression workflows.
    *   **Reduced Verbosity:** Main workflow S-expressions become significantly cleaner and more focused on high-level logic.
    *   **Improved Readability:** Easier to understand workflows when common data access patterns are abstracted.
    *   **Maintainability:** Helper logic is centralized in dedicated library files, making updates easier.
    *   **Extensibility:** New helper functions can be easily added to the standard library by creating or editing S-expression files.
    *   **DSL Cohesion:** Keeps utility logic within the S-expression paradigm, leveraging its existing capabilities (`lambda`, primitives).
    *   **Empowers DSL Users:** Allows for a richer set of standard operations without modifying the core Python evaluator for every small utility.

*   **Cons:**
    *   **Startup Overhead:** A small, likely negligible, increase in application startup time will be incurred to read, parse, and evaluate the standard library S-expression files.
    *   **File Management:** Requires a convention for the location and organization of these standard library files.
    *   **Dependency on Evaluator Capabilities:** Relies on the `SexpEvaluator` correctly handling `(define ...)` or `(bind ... (lambda ...))` at the top level of the evaluation context used for the library files.
    *   **Potential for Name Clashes:** If many library files are loaded, or if user-defined variables in a workflow accidentally shadow library function names (though lexical scoping via `let` should generally prevent this for workflow variables). Careful naming conventions for library functions will be important.

*   **Impact:**
    *   **`Application`:**
        *   Requires new logic in `__init__` to:
            *   Instantiate and hold a base `SexpEnvironment`.
            *   Locate, read, parse, and evaluate S-expression files from a standard library directory.
        *   Must provide this populated base environment to components that trigger S-expression evaluation (e.g., `Dispatcher`).
    *   **`SexpEvaluator`:**
        *   No direct changes to its core evaluation logic are strictly required *if* it already supports `(bind symbol (lambda ...))` evaluation at the top level of an environment.
        *   If a dedicated `(define ...)` special form is preferred for the standard library, it would need to be added to `SexpEvaluator`. (Current assumption: `(bind name (lambda ...))` or an existing/easily-added `define` can achieve this).
    *   **`SexpEnvironment`:** No changes required.
    *   **`Dispatcher` (and other S-expression callers):** Will need to be modified to receive the pre-populated base `SexpEnvironment` from the `Application` instance and pass it to `SexpEvaluator.evaluate_string`.
    *   **Documentation:**
        *   A new guide or section detailing how to create and use S-expression standard library helper functions.
        *   Documentation for the standard library functions themselves.
        *   Updates to workflow examples to use these helpers.
    *   **Project Structure:** A new directory (e.g., `src/sexp_stdlib/`) will be created.

**Alternatives Considered:**

1.  **Inline Lambda Definitions per Workflow:**
    *   *Rejected because:* Leads to significant code duplication and verbosity, defeating the purpose of reusable helpers.

2.  **Python-Implemented Primitives for Every Helper:**
    *   *Rejected because:* Makes the `SexpEvaluator` (Python) overly complex for utility functions that can be expressed in the S-expression language itself. Reduces the self-contained nature and ease of extension of the DSL for its users.

3.  **Python Code Directly Populating `SexpEnvironment` with `Closure` Objects:**
    *   *Rejected because:* While technically feasible, it's less idiomatic for a Lisp-like DSL. Defining helpers in S-expression files keeps the library itself in the target language, making it more accessible for DSL writers to contribute to.

**Decision Rationale:**

This approach provides the best balance of reusability, maintainability, and consistency with the S-expression paradigm. It allows the DSL to become more powerful and expressive by building upon its own foundational elements (`lambda`, core primitives) to create a shared library of utilities. This is a common and effective pattern in Lisp-like languages. The minor startup overhead is acceptable given the significant improvements in workflow development and readability.

This approach aligns well with the existing architecture by leveraging the `SexpEvaluator` and `SexpEnvironment` without requiring fundamental changes to their core logic, assuming robust support for top-level lambda bindings.

---
