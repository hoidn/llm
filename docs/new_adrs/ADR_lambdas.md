**ADR: Adding `lambda` with Closures and Lexical Scoping**

**Status:** Proposed / Accepted (Adjust status based on team decision)

**Context:**

*   The current S-expression DSL allows workflow orchestration by calling pre-registered atomic tasks (via `TaskSystem`) and direct tools (via `BaseHandler`).
*   Atomic tasks are defined externally via templates, providing a mechanism for parameterized LLM interactions but lacking inline definition or true functional abstraction within the DSL.
*   A previous ADR proposed `defatom` to allow inline *definition* of atomic tasks, but these are still registered globally and do not provide lexical scoping or first-class function semantics.
*   There is a desire for greater expressiveness within the DSL, allowing users to define anonymous functions, create higher-level abstractions directly in S-expressions, and utilize standard lexical scoping for more complex or reusable workflow logic, particularly for encapsulating sequences of LLM calls or custom data transformations.
*   This capability aligns the DSL more closely with functional programming paradigms and standard Lisp dialects.

**Decision:**

Implement anonymous function definition using the `lambda` special form, including support for closures and lexical scoping, within the `SexpEvaluator`.

1.  **Introduce `lambda` Special Form:** Add `lambda` to the set of special forms recognized by the `SexpEvaluator`.
    *   **Syntax:** `(lambda (<param1> ...) <body-expr1> ...)`
    *   **Behavior:** Evaluation of a `lambda` expression will *not* evaluate the parameter list or body. It will create and return a **Closure** object.
2.  **Implement Closures:** Define an internal representation (e.g., a `Closure` class) that encapsulates:
    *   The function's parameter list (symbols).
    *   The function's body (AST nodes).
    *   A reference to the lexical environment (`SexpEnvironment` instance) active when the `lambda` expression was evaluated (the definition environment).
3.  **Implement Function Application:** Modify the `SexpEvaluator`'s list evaluation logic (`_eval_list`) to handle cases where the evaluated operator is a `Closure` object. This application process involves:
    *   Evaluating arguments passed in the *calling* expression within the *calling* environment.
    *   Creating a *new environment frame*.
    *   Linking this new frame's parent to the *Closure's captured environment* (ensuring lexical scope).
    *   Binding parameters to evaluated arguments in the new frame.
    *   Evaluating the Closure's body within the new frame.
    *   Returning the result of the body's evaluation.
4.  **Update IDLs:** Modify `sexp_evaluator_IDL.md` and `sexp_environment_IDL.md` to document the `lambda` special form, the concept of Closures, the function application process, and the role of the environment in lexical scoping.

**Consequences:**

*   **Pros:**
    *   **Increased Expressiveness:** Enables definition of anonymous functions, local helper functions, and potentially higher-order functions (passing functions as arguments).
    *   **True Lexical Scoping:** Provides standard, predictable variable scoping based on where functions are defined, not where they are called.
    *   **Encapsulation:** Allows users to better encapsulate reusable logic (including sequences of LLM calls or data transformations) directly within the DSL.
    *   **Alignment with Lisp:** Brings the DSL closer in capability and feel to established functional languages.
    *   **Reduces Reliance on Global Registry (Potentially):** Offers an alternative to defining every small operation as a globally registered atomic task.
*   **Cons:**
    *   **Significant Implementation Complexity:** Implementing closures, lexical scope capture, and the function application stack within the `SexpEvaluator` is considerably more complex than previous features (`defatom`, primitives). Requires careful handling of environments and recursion.
    *   **Increased Debugging Difficulty:** Debugging user-defined functions with closures and lexical scope can be more challenging than debugging linear workflows or simple task calls.
    *   **Steeper User Learning Curve:** Users need to understand lambda functions, scope, and closures to use the feature effectively.
    *   **Potential Performance Impact:** Recursive evaluation of user-defined functions might introduce minor performance overhead compared to direct task/tool calls (though likely insignificant relative to LLM/IO operations).
    *   **Architectural Impact:** May reduce the prominence or necessity of the `TaskSystem` registry and `AtomicTaskExecutor` for certain use cases, potentially requiring future refactoring or rethinking of their roles if `lambda` + `llm-call` (a potential future primitive) becomes dominant.
*   **Impact:**
    *   Requires major additions and modifications to `SexpEvaluator`.
    *   May require minor adjustments to `SexpEnvironment`.
    *   Requires significant new testing efforts focused on closures, scope, and application.
    *   Requires substantial updates to DSL documentation and user guides.

**Alternatives Considered:**

1.  **No Inline Functions:** Rely solely on globally registered atomic tasks (`TaskSystem`) and direct tools (`BaseHandler`). (Rejected: Limits DSL expressiveness and encapsulation).
2.  **Only `defatom`:** Implement inline definition via global registration (`defatom` ADR). (Considered: A viable, less complex intermediate step, but doesn't provide lexical scope or true first-class functions). `defatom` could potentially coexist with `lambda`.
3.  **Full Macro System:** Implement Lisp-style macros (`defmacro`). (Rejected: Even higher complexity than `lambda`, not justified at this stage).

**Decision Rationale:**

While significantly more complex to implement than `defatom`, adding `lambda` provides fundamental expressive power common to functional languages and Lisps, enabling true lexical scoping and first-class functions. This allows users to create more sophisticated, modular, and maintainable workflows directly within the DSL. The benefits of proper abstraction and encapsulation are deemed to outweigh the implementation complexity for the long-term evolution of the DSL, especially for orchestrating complex sequences involving LLM calls and data manipulation. This feature provides a foundation for more advanced DSL capabilities in the future. The implementation complexity is acknowledged, and this feature should likely be tackled after other core integrations (like Phase 4) are stable.
