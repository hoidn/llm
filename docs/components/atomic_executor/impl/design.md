# AtomicTaskExecutor Implementation Design

## Core Logic

The AtomicTaskExecutor focuses solely on executing the body of a single, pre-parsed atomic task template.

### Input Processing
- Receives the parsed atomic task definition (`atomic_task_def`) from the Task System. This includes elements like instructions, system prompts, and output format specifications.
- Receives a `params` dictionary from the Task System. This dictionary contains the fully evaluated input parameters for the task, keyed by the parameter names declared in the task's `<inputs>`. **It does not receive or manage a complex lexical environment.**
- Receives the prepared `context_string` and `included_files` list from the Task System.

### Parameter Substitution
- Iterates through the relevant fields of the `atomic_task_def` (e.g., instructions, system prompt).
- Uses a simple string substitution mechanism to replace `{{parameter_name}}` placeholders.
- **Crucially, substitution only uses the keys and values present in the provided `params` dictionary.** There is no lookup into any outer scope or environment.
- If a placeholder `{{variable}}` references a key not found in the `params` dictionary, a `ParameterMismatch` error (or similar) is raised, halting execution.

### Handler Invocation
- After substitution, the AtomicTaskExecutor has the fully resolved text for prompts, system messages, etc.
- It uses the `context_string` provided by the Task System.
- It constructs the `HandlerPayload` required by the Handler, including the resolved prompts, system messages, context string, and any tool definitions relevant to the task.
- It invokes the appropriate method on the `handler` instance provided by the Task System (e.g., `handler.executePrompt(payload)` or `handler._execute_llm_call(...)`).

### Output Handling
- Receives the `TaskResult` (or `TaskError`) directly from the `handler` call.
- **Output Parsing/Validation (Responsibility TBD):** The responsibility for parsing the `content` based on the `<output_format>` (e.g., parsing JSON) and validating it against a schema might reside here *or* in the Task System *after* the `execute_body` call returns. If handled here, it would:
    - Check the `atomic_task_def` for an `<output_format>` specification.
    - Attempt to parse `TaskResult.content` if `type="json"`.
    - Validate against the `schema` if provided.
    *   Add parsed content to `TaskResult.parsedContent` or populate `TaskResult.notes.parseError` / `TaskResult.notes.validationError`.
- Returns the final `TaskResult` (potentially augmented with parsed content or validation info) back to the Task System.

## What AtomicTaskExecutor Does NOT Do

- **S-expression Evaluation:** Does not parse or execute S-expressions. This is the `SexpEvaluator`'s role.
- **Workflow/Composite Task Logic:** Does not handle sequences, loops, or conditionals between tasks. This is managed by the `SexpEvaluator`.
- **Template Lookup/Matching:** Does not find or select task templates. This is the `TaskSystem`'s role.
- **Context Management Strategy:** Does not decide *how* context is inherited, accumulated, or fetched. It simply receives the final context prepared by the `TaskSystem`.
- **Environment Management:** Does not manage lexical environments (`SexpEnvironment`). It only uses the flat `params` dictionary for substitution.
- **Subtask Spawning:** Does not handle `CONTINUATION` results or spawn subtasks. This logic resides in the `SexpEvaluator`.

## Integration

- **Called By:** `TaskSystem.execute_atomic_template`
- **Calls:** `Handler.executePrompt` (or similar methods)
