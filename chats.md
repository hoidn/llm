4/25
(
1.  **Core Architecture Shift (Strict Separation):** We decided to move away from defining composite tasks (like `sequential`, `reduce`, `director_evaluator_loop`) in XML. The new architecture is:
    *   **XML:** Used **only** for defining **atomic task templates** (their description, inputs, context needs, output format, etc.).
    *   **S-expression DSL:** Used for **all workflow composition** (sequences, mapping, conditionals, loops, context fetching) invoked via the `/task '(...)` command.

2.  **S-Expression DSL Definition (v1):**
    *   Adopted S-expression syntax for programmatic workflows.
    *   Defined the core primitives needed for v1 to replace XML composites:
        *   **Invocation:** `(<identifier> <arg>*)` - Calls atomic XML templates or Handler direct tools. Handles special `(context ...)` and `(files ...)` arguments for template calls.
        *   **Binding:** `(bind <symbol> <expression>)` or `(let ((sym expr)...) body...)` - Essential for sequential data flow.
        *   **Conditional:** `(if <cond> <then> <else>)` - Needed for logic like D-E loop termination.
        *   **Mapping:** `(map <task_expr> <list_expr>)` - For applying tasks to lists.
        *   **List Creation:** `(list <item>*)` - For creating literal lists.
        *   **Context Fetching:** `(get_context <option>*)` - For dynamic file context retrieval via `MemorySystem`.
    *   A new `SexpEvaluator` component will parse and execute this DSL, interacting with `TaskSystem`, `Handler`, and `MemorySystem`.

3.  **XML Schema & Core Evaluator Simplification:**
    *   The XML schema (`protocols.md`) will be significantly simplified, removing definitions for `sequential`, `reduce`, `director_evaluator_loop`, etc.
    *   The core `Evaluator` (handling XML/AST) simplifies its role to primarily executing the body of *atomic* task templates.

4.  **Director-Evaluator Pattern:** Decided explicitly that the D-E pattern will **not** be a specific XML task type but will be implemented as a workflow **within the S-expression DSL** using its primitives (`bind`/`let`, `if`, invocation, potentially looping later).

5.  **Function/Parameter Handling:** Clarified the mapping:
    *   Atomic XML templates define named `<inputs>`.
    *   S-expression calls pass arguments primarily as named pairs `(key value_expression)` corresponding to those inputs.
    *   The `TaskSystem` bridges this via the `SubtaskRequest` and the core `Environment` when executing atomic templates invoked from the DSL.

6.  **Tool Registration Simplification:** Confirmed the plan (from previous steps/intern instructions) to unify Handler tool registration using only `BaseHandler.register_tool`.

7.  **Documentation Updates:**
    *   Identified numerous architecture documents (`overview.md`, `patterns/*.md`, `protocols.md`, `types.md`, component READMEs/designs/specs/examples, specific ADRs) that require significant updates to remove references to XML composites and reflect the new S-expression composition model.
    *   Generated detailed, step-by-step instructions for an intern to update the IDL files (`*_IDL.md`) to reflect the architectural changes (XML composite removal, S-expression integration points, Evaluator simplification, tool registration changes).
    *   Created a new conceptual IDL for the `SexpEvaluator`.

8.  **Developer Guidance:**
    *   Reviewed and confirmed the adequacy of the "Parse, Don't Validate" section in the `implementation_rules.md`.
    *   Drafted a `developer_orientation.md` document to guide new developers on the IDL-centric workflow and project conventions.
    *   Drafted an `IDL Implementation Readiness Checklist` including a section for mapping features/user stories to IDL specifications.

In essence, we pivoted to a cleaner architectural model with a stricter separation of concerns, defined the initial requirements for a more powerful S-expression DSL, and outlined the extensive documentation and IDL updates needed to reflect this significant change.

https://aistudio.google.com/prompts/17fLLFV6Vha0_Ykr6tazOXZsroWrw4xGQ
)
