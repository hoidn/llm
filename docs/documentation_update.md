**`docs/documentation_update.md`**

# Guide: Keeping Documentation Consistent

**1. Purpose**

This guide outlines the standard process for reviewing and updating project documentation to ensure it accurately reflects the current state of the codebase, architecture, and development practices. Consistent and up-to-date documentation is crucial for onboarding new developers, maintaining architectural integrity, and reducing confusion.

**2. When to Use This Process**

This process should be triggered:

*   **After Significant Technical Changes:** Following the merge of code that implements a major feature, refactoring, architectural decision (ADR), or change in core dependencies (like the pivot to `pydantic-ai`).
*   **Before Starting Major New Work:** As part of the preparation phase for a new feature that builds upon existing components, verifying the documentation for those components is accurate.
*   **Periodically:** As part of scheduled maintenance to catch drift between documentation and implementation over time.

**3. Goal**

To identify and rectify inconsistencies, inaccuracies, or outdated information within the project's documentation (`docs/` directory and potentially `_IDL.md` files in `src/`).

**4. The Process**

**Phase 1: Define Scope & Identify Affected Documents**

1.  **Identify the Trigger/Scope:** Clearly define the technical change or area of focus that necessitates the documentation review.
    *   *Example Trigger:* "ADR-18 (Pivot to pydantic-ai) has been accepted and Phase 1B/2b implementing it are notionally complete."
    *   *Example Scope:* "Review documentation related to LLM interaction, Handler implementation, and core developer guides."

2.  **List Potentially Affected Documents:** Brainstorm and list all documentation files that *might* be impacted by the change or are relevant to the area of focus. Start broadly and narrow down if needed.
    *   **Core Guides:** Always check `start_here.md`, `project_rules.md`, `implementation_rules.md`, `IDL.md`.
    *   **Related ADRs:** Review the ADR itself and any ADRs it supersedes or relates to.
    *   **Component Docs:** Identify components directly affected by the change. Check their READMEs, specs (`spec/`), API docs (`api/`), implementation notes (`impl/`), and associated IDLs (`src/.../*_IDL.md`).
    *   **Contracts & Protocols:** Check `docs/system/contracts/` and `docs/system/protocols/` if the change impacts interfaces, types, or schemas.
    *   **Patterns:** Check `docs/system/architecture/patterns/` if the change implements or modifies a core pattern.
    *   **Search:** Use tools like `git grep` or IDE search for keywords related to the change across the `docs/` and potentially `src/` directories (for IDLs) to find less obvious references.
    *   *Example Output for pydantic-ai pivot:* `start_here.md`, `implementation_rules.md`, `project_rules.md` (re: helpers), `base_handler_IDL.md`, `model_provider_IDL.md` (deprecate), `librarydocs/pydanticai.md` (add/review).

**Phase 2: Review and Analyze**

1.  **Read Through Identified Documents:** Carefully read each document identified in Phase 1.
2.  **Compare Against Reality:** Compare the documentation against:
    *   The **specific technical changes** that triggered the review (e.g., Does the LLM interaction section reflect `pydantic-ai` usage?).
    *   The **current codebase structure** (e.g., Does `project_rules.md` match the output of `git ls-files` or `tree src/`?).
    *   The **current behavior** of the code (if known or testable).
    *   Other **related documentation** (check for contradictions between documents).
3.  **Identify Gaps and Inconsistencies:** Look for:
    *   **Outdated Information:** Descriptions, code examples, diagrams, or procedures that no longer match the implementation.
    *   **Contradictions:** Information that conflicts with the implemented changes or other documentation.
    *   **Inconsistent Terminology:** Using different names for the same concept across documents.
    *   **Broken Links/References:** Cross-references pointing to non-existent files or sections.
    *   **Missing Information:** Failure to document new components, features, patterns, or conventions introduced by the change.
    *   **Ambiguity:** Sections that are unclear or open to multiple interpretations.
    *   *Example Gaps Found:* `implementation_rules.md` described old `ProviderAdapter`; `start_here.md` pointed to wrong types file; `project_rules.md` lacked clarity on IDL placement for helpers.

**Phase 3: Draft and Apply Updates**

1.  **Draft Targeted Edits:** For each identified gap, draft the specific changes needed.
    *   Focus on correcting the inaccuracies or adding the missing information. Avoid unnecessary rewrites unless a section is fundamentally flawed.
    *   Ensure the changes align with the project's documentation style and tone.
    *   Update code examples, diagrams, and cross-references as needed.
    *   Reference the trigger (e.g., "Updated to reflect `pydantic-ai` usage per ADR-18").
    *   *Example Draft:* The drafted updates provided in the previous step for `implementation_rules.md`, `start_here.md`, etc.
2.  **Apply Changes:** Edit the documentation files, incorporating the drafted updates.
3.  **Self-Review:** Read through your changes. Do they accurately address the identified gaps? Are they clear and easy to understand? Do they introduce any new inconsistencies?

**Phase 4: Review and Commit**

1.  **Peer Review (Recommended):** If possible, have another team member review the documentation changes for clarity and accuracy, especially if the changes are substantial.
2.  **Commit Changes:** Use clear, specific commit messages explaining the purpose of the documentation update. Reference the triggering change if applicable.
    *   *Example Commit Message:* `docs: Align LLM interaction guides with pydantic-ai pivot`
    *   *Example Commit Message:* `docs: Clarify IDL placement rules in project_rules.md`

**5. Key Considerations**

*   **Scope:** Keep the update focused on the triggering change or area under review. Avoid expanding the scope unnecessarily.
*   **Single Source of Truth:** Ensure that information is updated in the *authoritative* source document. Avoid duplicating detailed explanations across multiple files; use cross-references instead. (e.g., IDLs in `src/` are the contract, API docs in `docs/` might summarize).
*   **Clarity:** Write for someone unfamiliar with the specific change or component. Define terms or link to definitions where necessary.
*   **Consistency:** Ensure terminology, formatting, and style are consistent with surrounding documentation.

By following this process, we can maintain accurate, consistent, and helpful documentation that reflects the ongoing evolution of the project.

