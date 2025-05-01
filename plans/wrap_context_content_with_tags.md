# Plan: Wrap Context Content with File Path Tags

**Goal:** Modify the internal context matching task (`internal:associative_matching_content`) so that the file content provided to it is formatted as a single string containing XML-like tags that include the file path, similar to the format used by `FileContextManager`.

**Steps:**

1.  **Modify `src/memory/memory_system.py` (`MemorySystem.get_relevant_context_for`):**
    *   Locate the `if strategy == 'content':` block.
    *   Change the loop that currently builds the `file_contents` dictionary.
    *   Instead, create a list of strings. For each successfully read file, format a string like: `<file path="{path}">{content}</file>`.
    *   Join this list of strings into a single string, separated by double newlines (`\n\n`).
    *   Update the `inputs_for_llm` dictionary to store this single formatted string under the key `"file_contents"`.

2.  **Modify `src/main.py` (Template Definition):**
    *   Locate the definition of the `assoc_matching_content_template` dictionary.
    *   Update the `instructions` string within this template:
        *   Clarify that the `{{file_contents}}` variable contains a single string with multiple file contents, each wrapped in `<file path="...">...</file>` tags.
        *   Instruct the LLM to extract the relevant file paths *from the `path` attribute within the tags* when generating the `matches` list in the output JSON.

3.  **Update `src/memory/memory_system_IDL.md`:**
    *   In the `Behavior` description for the `get_relevant_context_for` method:
        *   Update step 4 (or equivalent) for the 'content' strategy to state that `inputs_for_llm["file_contents"]` is now a single string containing the content of candidate files, each wrapped in `<file path="...">...</file>` tags.

4.  **Update `src/main_IDL.md`:**
    *   In the `__init__` method's description, update the note about the registered `internal:associative_matching_content` template.
    *   Clarify that its `file_contents` parameter (defined in `params`) now expects a single string containing file contents wrapped in `<file path="...">...</file>` tags.

**Rationale:**

This change standardizes the format of file content provided to LLM tasks, whether it's for the main passthrough handler or internal tasks like context matching. It ensures the LLM always receives the file path alongside the content, which is crucial for tasks that need to identify *which* file the relevant information came from.
