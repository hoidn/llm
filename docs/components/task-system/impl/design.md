# Task System Implementation Design

## Terminology and References

 - **Handler**, **SexpEvaluator**, **AtomicTaskExecutor** definitions are standardized elsewhere (see component docs).
 - XML schema definitions for atomic tasks are available in [Contract:Tasks:TemplateSchema:1.0] (../../../system/contracts/protocols.md).
 - For detailed resource tracking implementation (Handler-centric), see [resource-management.md](./resource-management.md).
 - For XML processing details (parsing, validation, and fallback behavior), refer to [xml-processing.md](./xml-processing.md).
 - For implementation examples, see the [examples/](./examples/) directory.

## Handler Implementation

### Session Management Strategy
- Handler creates a HandlerSession for each task execution
- Session maintains complete conversation state and message history
- Provider-agnostic HandlerPayload structure for LLM interactions
- Clean session termination on completion
- Tool-based approach for user input requests
  
### Resource Tracking Implementation
- Turn counter integrated with HandlerSession
- Turns incremented only for assistant messages
- Context window tracks all messages and context
- Token usage monitored across full conversation
- Resource metrics available via session.getResourceMetrics()
- Limits enforced during session operations

### Payload Construction
- HandlerPayload provides unified structure for LLM requests
- Includes: systemPrompt, messages, context, tools, metadata
- Provider-specific adapters transform to appropriate format
- Session constructs payload via constructPayload() method
- Full conversation history included in structured format

## Atomic Task Template Management

### Registration (`register_template`)
- Receives a dictionary representing an *atomic* task template.
- Validates the structure against the XML schema ([Contract:Tasks:TemplateSchema:1.0]).
- Ensures required fields like `name`, `type` ('atomic'), and parameter declarations (`params` attribute or `<inputs>`) are present.
- Stores the validated template definition in an internal dictionary (`self.templates`), keyed by `name`.
- Updates an index (`self.template_index`) mapping `type:subtype` (e.g., "atomic:code_edit") to the template name for faster lookup.

### Lookup (`find_template`)
- Receives an identifier string.
- First, attempts direct lookup by `name` in `self.templates`.
- If not found, attempts lookup by `type:subtype` in `self.template_index`.
- Returns the template definition dictionary if found, otherwise `None`. Used by `SexpEvaluator` and `Dispatcher`.

### Matching (`find_matching_tasks`)
- Matches a natural language `input_text` against registered *atomic* task templates.
- Calculates similarity scores (e.g., Jaccard index) between the input and template descriptions.
- Returns a sorted list of matching atomic templates above a threshold. Used by Dispatcher/Handler for routing user queries.

## Atomic Task Execution Orchestration (`execute_atomic_template`)

This method is the core of the Task System's role during runtime, invoked by the `SexpEvaluator` to run an atomic step.

### Input
- `request: SubtaskRequest`: Contains `type` ('atomic'), `name`/`subtype`, resolved `inputs` dictionary, optional resolved `file_paths` list, optional resolved `context_management` overrides. **Crucially, the `env` parameter is removed.** The caller (`SexpEvaluator`) must resolve all values *before* calling.

### Processing Steps
1.  **Validation:** Ensure `request.type` is 'atomic'.
2.  **Template Lookup:** Find the atomic template using `self.find_template(request.name or f"atomic:{request.subtype}")`. Return error if not found.
3.  **Context Determination:**
    *   Determine the effective `ContextManagement` settings by merging defaults (based on template subtype), template `<context_management>`, and `request.context_management` overrides (request takes highest precedence).
    *   Validate constraints (e.g., mutual exclusivity of `fresh_context` and `inherit_context`).
    *   Determine the final list of `file_paths` using precedence: `request.file_paths` > template `<file_paths>`.
4.  **Context Preparation:**
    *   If `fresh_context` is enabled in effective settings:
        *   Construct `ContextGenerationInput` using template info and `request.inputs`.
        *   Call `MemorySystem.get_relevant_context_for(context_input)`.
        *   Store the resulting context summary and file paths.
    *   If `inherit_context` is 'full' or 'subset': Retrieve appropriate context from the parent (Note: Requires mechanism to access parent context, potentially passed implicitly or via a shared object).
    *   Assemble the final context string and list of file contents to be passed to the Handler (Handler performs file I/O).
5.  **Parameter Preparation:** The `request.inputs` dictionary is used directly as the `params` for the `AtomicTaskExecutor`. No further resolution is done here.
6.  **Handler Instantiation:** Get or create a `Handler` instance, configured with appropriate resource limits based on the task template or system defaults.
7.  **Executor Invocation:**
    *   Instantiate `AtomicTaskExecutor`.
    *   Call `atomicTaskExecutor.execute_body(parsed_template_def, request.inputs, handler_instance)`.
8.  **Result Handling:**
    *   Receive `TaskResult` or `TaskError` from the executor.
    *   Add execution metadata (template used, context source/count) to `TaskResult.notes`.
    *   Return the final `TaskResult` or `TaskError`.

### Context Management Implementation Details
The Task System implements the hybrid configuration logic for atomic tasks:

1.  **Determine Subtype:** Identify the `subtype` of the atomic task (e.g., `standard`, `subtask`, `director`, `aider_interactive`) from the XML template or the `SubtaskRequest`.
2.  **Get Defaults:** Retrieve the default `ContextManagement` settings for that subtype (see table in `protocols.md`).
3.  **Apply Template Overrides:** Merge the defaults with any explicit `<context_management>` settings defined in the task's XML template.
4.  **Apply Request Overrides:** Further merge the result with any `context_management` overrides provided in the `SubtaskRequest` object passed to `execute_atomic_template`. **Request overrides take precedence over template overrides.**
5.  **Determine File Paths:** Resolve the final list of file paths using the precedence: `request.file_paths` > template `<file_paths>` > automatic lookup (if `fresh_context` enabled).
6.  **Enforce Constraints:** Validate the final effective settings (e.g., mutual exclusivity of `fresh_context` and `inherit_context`).
7.  **Prepare Context:** Use the final settings and file paths to assemble the context (fetch fresh, inherit, include files) before invoking the Handler/AtomicTaskExecutor.

```typescript
// Conceptual merging logic
function getEffectiveContextSettings(request: SubtaskRequest, template: ParsedAtomicTask): ContextManagement {
    const subtype = request.subtype || template.subtype || 'standard';
    const defaults = DEFAULT_ATOMIC_CONTEXT_SETTINGS[subtype] || DEFAULT_ATOMIC_CONTEXT_SETTINGS.standard;
    // Assuming template definition includes a parsed context_management object
    const templateOverrides = template.context_management || {};
    const requestOverrides = request.context_management || {};

    const merged = { ...defaults, ...templateOverrides, ...requestOverrides };

    validateContextSettings(merged); // Ensure constraints are met

    return merged;
}
```

This ensures consistent application of defaults and overrides for every atomic task execution orchestrated by the Task System.

## Template Substitution Process (Atomic Tasks)

The AtomicTaskExecutor (invoked by the Task System) handles template variable substitution (`{{parameter_name}}`) within an atomic task's body before execution by the Handler. The `SexpEvaluator` (when processing a `call`) evaluates the named arguments provided in the S-expression and constructs the `inputs` dictionary within the `SubtaskRequest`. The `TaskSystem` passes this dictionary to the `AtomicTaskExecutor`. The substitution process within the `AtomicTaskExecutor` exclusively follows the function-style model mandated by ADR 18, resolving placeholders *only* against the keys present in this received `inputs` dictionary.

## Integration Points

### Memory System Integration
- Task System calls `MemorySystem.getRelevantContextFor` when effective context settings require `fresh_context`.
- Task System uses the `AssociativeMatchResult` to prepare context for the `AtomicTaskExecutor`.
- Follows clear separation: Memory handles metadata/matching, Handler handles file I/O.

### SexpEvaluator Integration
- `SexpEvaluator` calls `TaskSystem.find_template` to identify atomic tasks.
- `SexpEvaluator` calls `TaskSystem.execute_atomic_template` to run atomic steps, providing a resolved `SubtaskRequest`.
- Task System returns `TaskResult`/`TaskError` to `SexpEvaluator`.

### AtomicTaskExecutor Integration
- Task System instantiates `AtomicTaskExecutor`.
- Task System calls `AtomicTaskExecutor.execute_body`, passing the parsed template definition, resolved `params` dictionary, and a `Handler` instance.
- Task System receives `TaskResult`/`TaskError` from `AtomicTaskExecutor`.

### Handler Integration
- Task System obtains/creates `Handler` instances, configuring them with resource limits for specific atomic task executions.
- Task System passes the `Handler` instance to the `AtomicTaskExecutor`.

### Compiler Integration
- The Compiler's primary role related to the Task System is validating the XML schema of atomic task templates during `register_template`. It's not directly involved in the runtime execution flow managed by TaskSystem.

## Resource Management Coordination
- The Task System determines the resource limits (based on template or defaults).
- It configures the `Handler` instance with these limits before passing it to the `AtomicTaskExecutor`.
- The `Handler` enforces these limits during the execution managed by the `AtomicTaskExecutor`.
- Resource exhaustion errors are propagated back through `AtomicTaskExecutor` -> `TaskSystem` -> `SexpEvaluator`.
