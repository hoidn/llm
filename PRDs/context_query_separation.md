**Planning & Requirements Document: Separate Context Query in Task Templates**

**1. Introduction / Overview**

*   **Problem:** Currently, the `TaskSystem` primarily uses the main task description (or user query in passthrough mode) to determine relevant file context via the `MemorySystem` and the `associative_matching` template. This tightly couples context retrieval with the main task execution prompt. For complex tasks or future DSL capabilities, it's often desirable to use a more specific or different query to find relevant files than the prompt used to instruct the LLM for the main task execution.
*   **Proposed Solution:** Enhance the task template schema and the `TaskSystem`'s context resolution logic to allow templates to declaratively specify a distinct query or description to be used *exclusively* for finding relevant file context via the `MemorySystem`'s associative matching capabilities.

**2. Goals**

*   Enable task templates to define a context-specific query/description, separate from the main task description/prompt.
*   Integrate this functionality seamlessly into the existing `TaskSystem` and `MemorySystem` context retrieval flow (`resolve_file_paths`, `get_relevant_context_for`).
*   Support the use of template variables within the context-specific query, allowing it to be dynamic based on task inputs.
*   Maintain backward compatibility: Existing templates without this explicit separation should continue to function as they do now (using the main description for context).
*   Provide a clear and declarative mechanism suitable for future integration with a Domain Specific Language (DSL) for task definition.

**3. Non-Goals**

*   Implementing the DSL itself.
*   Fundamentally changing the underlying `associative_matching` mechanism or its LLM prompt (unless strictly necessary to accommodate the separated input).
*   Introducing entirely new context-finding strategies (e.g., vector search) in this specific enhancement.
*   Modifying the user-facing REPL interface directly; this is a backend/template enhancement.
*   Allowing *multiple* different context queries for a single task execution step in this phase.

**4. Background & Motivation**

*   **Improved Context Relevance:** A specific query tailored for file finding can yield more accurate context than a general task prompt intended for LLM execution. For instance, a task prompt might be "Refactor the authentication logic for performance", while the optimal context query might be "files related to user login, session management, and database user schema".
*   **Reduced Prompt Pollution:** Separating the context query prevents potentially long or detailed file-finding instructions from cluttering the main system prompt sent to the LLM for task execution.
*   **DSL Enablement:** A future DSL needs a structured way to define how tasks gather their context. This feature provides a declarative primitive for the DSL to target.
*   **Task Complexity:** As tasks become more complex, the information needed to *find* relevant code might differ significantly from the instructions on *what to do* with that code.

**5. Proposed Solution: Enhance `file_paths_source`**

The recommended approach is to extend the existing `file_paths_source` dictionary within the task template schema.

*   Introduce a new `type`: `"context_description"`.
*   When `type` is `"context_description"`, the `value` field will contain the string to be used as the primary query for finding relevant files via `MemorySystem.get_relevant_context_for`.
*   This `value` field can contain literal text and/or template variables (e.g., `{{ some_input_param }}`) which will be resolved using the task's current `Environment` before being passed to the `MemorySystem`.

**6. Technical Design**

*   **Template Schema Modification:**
    *   The `file_paths_source` object within a task template can now optionally have `type: "context_description"`.
    *   **Example (Literal Value):**
        ```json
        "file_paths_source": {
          "type": "context_description",
          "value": "Find all Python files related to user authentication and session handling."
        }
        ```
    *   **Example (Variable Value):**
        ```json
        // Assuming a template parameter named "context_focus" exists
        "parameters": {
            "main_prompt": { ... },
            "context_focus": { "type": "string", "description": "Area to focus context search on" }
        },
        "file_paths_source": {
          "type": "context_description",
          "value": "Find files related to {{ context_focus }}"
        }
        ```

*   **`TaskSystem.resolve_file_paths` Logic Update:**
    1.  Check the `file_paths_source` type.
    2.  **If `type == "context_description"`:**
        *   Get the `value` string from `file_paths_source`.
        *   Resolve any template variables within the `value` string using the current task `Environment`.
        *   Create a `ContextGenerationInput` instance:
            *   Set `template_description` to the *resolved value* from `file_paths_source.value`.
            *   Populate `inputs`, `context_relevance`, `inherited_context`, `previous_outputs` based on the *main task's* template definition and current execution state, as is done currently for the default context generation path. (Consider if *only* the resolved value should be the input, or if main task inputs marked relevant should also be included - start with resolved value as primary).
        *   Call `memory_system.get_relevant_context_for(context_input)`.
        *   Extract file paths from the `AssociativeMatchResult.matches`.
        *   Return the resolved file paths.
    3.  **Else (type is `literal`, `command`, or unspecified/default):**
        *   Follow the existing logic for handling literal paths or executing commands.

*   **`MemorySystem` / `ContextGenerationInput`:** No changes required. `get_relevant_context_for` already accepts `ContextGenerationInput` where the driving query comes from `template_description`.

*   **Backward Compatibility:**
    *   Templates *without* `file_paths_source` or with `type: "literal"` or `type: "command"` will be handled by the existing logic within `resolve_file_paths`.
    *   The default context generation path (using the main task `description` when no explicit `file_paths_source` triggers context generation) within `TaskSystem.execute_task` remains the fallback if `resolve_file_paths` doesn't yield paths via an explicit source.

**7. User Experience (Developer / DSL Author)**

A developer defining a task template (or a future DSL generating one) can now control context generation more precisely.

*   **Before:**
    ```json
    {
      "type": "atomic",
      "subtype": "refactor_auth",
      "description": "Refactor authentication logic in files related to login and sessions for performance.",
      // Context found based *only* on the description above
      "parameters": { ... },
      "system_prompt": "You are a code optimization expert. Refactor the provided code...",
      ...
    }
    ```

*   **After:**
    ```json
    {
      "type": "atomic",
      "subtype": "refactor_auth",
      "description": "Refactor authentication logic for performance.", // Main task prompt
      "parameters": { ... },
      "file_paths_source": {
        "type": "context_description",
        "value": "Find Python files containing authentication, login, session management code." // Specific context query
      },
      "system_prompt": "You are a code optimization expert. Refactor the provided code...",
      ...
    }
    ```
    This allows the main `description` and `system_prompt` to focus solely on the refactoring task, while `file_paths_source` handles finding the relevant code.

**8. Success Metrics**

*   Unit tests for `TaskSystem.resolve_file_paths` verify correct handling of the `"context_description"` type, including variable substitution.
*   Integration tests demonstrate that `TaskSystem.execute_task` retrieves context based on the `file_paths_source.value` when specified, and uses the main `template.description` for the LLM execution prompt.
*   Manual testing confirms expected file context is retrieved for templates using the new feature.
*   No regressions in context retrieval for existing templates not using the new feature.
*   Code coverage for the modified `resolve_file_paths` logic is adequate.

**9. Rollout / Implementation Plan**

1.  **Update `TaskSystem.resolve_file_paths`:** Implement the logic to handle `type: "context_description"`, including variable substitution on the `value` field and calling `memory_system.get_relevant_context_for` with the appropriately constructed `ContextGenerationInput`.
2.  **Unit Testing:** Add specific unit tests for `TaskSystem.resolve_file_paths` covering:
    *   Handling of `type: "context_description"`.
    *   Correct variable substitution in the `value`.
    *   Correct creation of `ContextGenerationInput`.
    *   Fallback to default behavior for other types.
3.  **Integration Testing:** Create integration tests involving `TaskSystem` and `MemorySystem` (with mocked `associative_matching.execute_template`) to verify:
    *   A template using the new feature retrieves files based *only* on the context description.
    *   A template *not* using the feature retrieves files based on the main description (existing behavior).
4.  **Documentation:** Update any documentation related to task template schema and context generation to include this new option.
5.  **(Optional) Refactor Examples:** Update example templates (e.g., in `scripts/` or `devdocs/`) to showcase the new feature where appropriate.

**10. Open Questions / Future Considerations**

*   **Context Input Richness:** When using `type: "context_description"`, should *any* of the main task's input parameters (those marked relevant via `context_relevance`) *also* be included in the `ContextGenerationInput` passed to `memory_system.get_relevant_context_for`?
    *   **Decision:** Start simple. Primarily use the resolved `file_paths_source.value` as the `template_description`. Adding other relevant inputs might be a future enhancement if needed.
*   **Naming:** Is `context_description` the clearest name for the `type`? Alternatives: `associative_query`, `context_query`.
    *   **Decision:** `context_description` seems reasonable for now as it describes the *purpose* of the value string.
*   **Error Handling:** How should errors during variable substitution within the `file_paths_source.value` be handled? (e.g., variable not found).
    *   **Decision:** Propagate the error, likely resulting in a task failure, similar to errors in main description substitution.

---
