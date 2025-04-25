<description>Developer's working memory log for tracking current task, progress, next steps, and context.</description>
# Developer Working Memory (`docs/memory.md`)

**Purpose:** To maintain a running log of the development process for the current task or feature set. This helps maintain context for yourself (especially after breaks), assists reviewers in understanding the development journey, and provides a scratchpad for thoughts, questions, and next steps related to the work in progress.

**Instructions:**
*   **Update Frequently:** Update this file at the start and end of work sessions, when switching significant sub-tasks, or when important decisions/observations are made.
*   **Be Concise:** Use brief bullet points. Link to relevant files, IDLs, issue trackers, or discussions where appropriate.
*   **Timestamps:** Use dates (YYYY-MM-DD) or timestamps (YYYY-MM-DD HH:MM) for log entries.
*   **Most Recent First:** Add new entries to the *top* of relevant sections (like Recent Activity, Notes) for easy scanning.
*   **Commit Regularly:** Commit this file along with your code changes. It's part of the development history.
*   **Scope:** Focus on the current development cycle. Archive or clear older entries when starting a significantly new, unrelated feature branch if desired.

---

## Current Task/Focus (As of: YYYY-MM-DD HH:MM)

*   **Goal:** [Describe the high-level goal, e.g., "Implement the SexpEvaluator based on sexp_evaluator_IDL.md"]
*   **Current Sub-task:** [Describe the specific part being worked on, e.g., "Implementing the `_eval` logic for the `let` primitive."]
*   **Relevant Files:**
    *   `src/sexp_evaluator/sexp_evaluator.py`
    *   `src/sexp_evaluator/sexp_environment.py`
    *   `docs/sexp_evaluator/sexp_evaluator_IDL.md`
    *   `tests/sexp_evaluator/test_sexp_evaluator.py`
*   **Related IDL:** `src/sexp_evaluator/sexp_evaluator_IDL.md`

---

## Recent Activity Log

*   **(YYYY-MM-DD HH:MM):** Implemented basic structure for `SexpEvaluator` class and `evaluate_string` method, including parsing call and initial environment setup. Added basic test case for syntax error.
*   **(YYYY-MM-DD HH:MM):** Completed implementation readiness checklist for `sexp_evaluator_IDL.md`. Marked as Ready for Implementation. Added missing version marker to IDL.
*   **(YYYY-MM-DD HH:MM):** Reviewed IDL-to-Code instructions in project docs. Confirmed understanding of implementation requirements.

---

## Next Steps

*   Implement `_eval` logic for literal types (string, number, bool, null).
*   Implement `_eval` logic for symbol lookup using `SexpEnvironment.lookup`.
*   Write tests for literal evaluation and symbol lookup (including unbound symbol errors).
*   Implement `_eval` logic for the `let` primitive, including environment extension.
*   Write tests for `let` binding and scoping.

---

## Open Questions / Blockers

*   *(YYYY-MM-DD HH:MM):* Need clarification on how exactly named arguments in S-expressions (e.g., `(task :arg1 val1 :arg2 val2)`) should be mapped to the `params` dictionary expected by `TaskSystem.execute_subtask_directly` or `Handler.tool_executors`. Will assume a simple keyword-to-dict-key mapping for now. [Link to discussion if any]
*   *(Cleared YYYY-MM-DD HH:MM):* Was unsure if `SexpEvaluator` handles parsing - IDL confirms it does internally or uses a dependency like `SexpParser`.

---

## Notes & Context

*   *(YYYY-MM-DD HH:MM):* The Dispatcher is responsible for formatting the final `Any` return value from `SexpEvaluator.evaluate_string` into a `TaskResult` if the S-expression itself doesn't produce one. This simplifies the evaluator's return logic.
*   *(YYYY-MM-DD HH:MM):* Remember the lookup order for function calls specified in the IDL: Handler Direct Tools (`tool_executors`) first, then TaskSystem atomic templates (`find_template`).
*   *(YYYY-MM-DD HH:MM):* The `SexpEnvironment` needs careful implementation to handle lexical scoping correctly, especially for `let` and `map`.

---
</file>
```

**Integration with Project Docs:**

You should also add a reference to this `memory.md` file and its purpose in `docs/start_here.md` or `docs/project_rules.md`, perhaps under a section about developer workflow or recommended practices.

Example addition to `docs/start_here.md`:

```markdown
**9. Developer Workflow & Recommended Practices**

*   **Follow the IDL:** Adhere strictly to the IDL specification (`*_IDL.md`) for the component you are implementing (See Section 3).
*   **Use Working Memory:** Maintain a log of your development progress, current focus, and next steps in `docs/memory.md`. Update it frequently and commit it with your changes. This aids context retention and review. (See `docs/memory.md` for template and guidelines).
*   **Test Driven:** Write tests (especially integration tests) to verify your implementation against the IDL contract (See Section 6).
*   **Commit Often:** Make small, logical commits with clear messages.
*   **Format and Lint:** Run `make format` and `make lint` before committing.
*   **Ask Questions:** Don't hesitate to ask for clarification on requirements or design.
