**ADR: Leveraging Pydantic-AI for Structured Output in Atomic Tasks**

**Status:** Proposed

**Context:**

*   The system uses atomic task templates (defined via registration, potentially including `defatom`) executed by `AtomicTaskExecutor`.
*   Some atomic tasks need to produce structured data (e.g., JSON) as output, conforming to predefined schemas (like Pydantic models defined in `src.system.models`).
*   The current implementation relies on:
    1.  Instructing the LLM via text prompts within the template's `instructions` to generate a JSON string matching the desired structure.
    2.  The `AtomicTaskExecutor` performing a basic `json.loads()` on the LLM's string output if the template's `output_format` specifies `{"type": "json"}`.
    3.  The *caller* of the task (e.g., `MemorySystem` calling the internal context task) performing the final validation against a specific Pydantic model.
*   The underlying LLM interaction library, `pydantic-ai`, provides built-in features (`output_type` parameter in `agent.run`/`run_sync`) specifically designed to handle structured output requests reliably, often using provider-specific mechanisms (function calling, tool use) and performing automatic parsing and validation against Pydantic models.
*   The current approach doesn't leverage these library features, potentially leading to less reliable JSON generation by the LLM and requiring manual parsing/validation logic distributed across different components.

**Decision:**

1.  **Utilize `pydantic-ai`'s `output_type`:** Modify the system to leverage the `output_type` parameter of `pydantic-ai`'s `Agent.run_sync` (or `run`) method for atomic tasks requiring structured JSON output.
2.  **Template Schema Definition:** Task template definitions requiring structured output will include an `output_format` field specifying `{"type": "json", "schema": "ModelName"}` where `"ModelName"` is a string identifier corresponding to a Pydantic model defined within the project (likely in `src.system.models`).
3.  **Executor Responsibility (Mapping & Passing):**
    *   `AtomicTaskExecutor` will be responsible for identifying when a template specifies a JSON output format with a schema.
    *   It must resolve the `"ModelName"` string from the schema definition into the actual Python Pydantic model class. This requires a lookup mechanism (e.g., a registry mapping names to classes, dynamic imports based on convention).
    *   When invoking the LLM via `handler._execute_llm_call`, the executor will pass the resolved Pydantic model class as the `output_type_override` argument.
4.  **Handler/Manager Plumbing:** `BaseHandler._execute_llm_call` and `LLMInteractionManager.execute_call` will pass the `output_type_override` down to the `agent.run_sync` call.
5.  **Result Handling:**
    *   `LLMInteractionManager` will receive the result from `pydantic-ai`. If successful, the result object should contain the parsed and validated Pydantic model instance (e.g., in `response.output`). The manager should return this instance.
    *   `AtomicTaskExecutor` will receive the Pydantic model instance from the handler. It should place this instance directly into the `TaskResult.parsedContent` field. The raw LLM output (if available and different) can still go into `TaskResult.content`.
    *   Callers (like `MemorySystem`) that previously performed Pydantic validation on the result may simplify their logic, as the object received in `parsedContent` should already be a validated instance of the expected type.

**Consequences:**

*   **Pros:**
    *   **Increased Reliability:** Leverages provider-specific features (function calling, tool use) via `pydantic-ai` for more robust structured data generation compared to pure text prompting.
    *   **Automatic Validation:** Parsing and Pydantic model validation occur automatically within `pydantic-ai`, catching errors closer to the LLM response.
    *   **Simplified Executor:** Removes the need for manual `json.loads()` and potential schema validation logic within `AtomicTaskExecutor`.
    *   **Potentially Cleaner Prompts:** Reduces the need for extensive JSON format examples within the main task instructions.
    *   **Consistency:** Aligns with the intended usage patterns of the `pydantic-ai` library.
*   **Cons:**
    *   **Schema-to-Model Mapping:** Requires implementing and maintaining a mechanism within `AtomicTaskExecutor` (or an accessible service) to map schema name strings (from templates) to actual Pydantic model classes.
    *   **Executor Complexity:** Adds complexity to the executor related to model lookup/import.
    *   **Tighter Library Coupling:** Ties the structured output mechanism more directly to `pydantic-ai`'s implementation details.
    *   **Error Handling:** Requires handling potential validation or parsing errors raised by `pydantic-ai` during the `agent.run_sync` call.
*   **Impact:**
    *   Requires modification of `AtomicTaskExecutor` to handle `output_format.schema`, perform model lookup, and pass `output_type_override`.
    *   Requires modification of `BaseHandler` and `LLMInteractionManager` to plumb the `output_type_override` parameter through.
    *   Requires defining a convention for referencing Pydantic models in template schemas (e.g., by class name string).
    *   Requires implementing the model name-to-class lookup mechanism.
    *   May allow simplification of result validation logic in callers like `MemorySystem`.

**Alternatives Considered:**

1.  **Status Quo:** Continue relying on text prompting for JSON structure and manual `json.loads()` in the executor. (Rejected: Less reliable, distributes validation logic).
2.  **Executor Performs Pydantic Validation:** Keep text prompting, but have the executor perform `Model.model_validate_json(content)` instead of just `json.loads()`. (Rejected: Still less reliable generation than using library features, requires executor to know about all possible models).

**Decision Rationale:**

Leveraging the structured output capabilities built into `pydantic-ai` is the most robust and idiomatic approach. While it introduces the complexity of mapping schema names to model classes, the significant benefits in terms of generation reliability and automatic validation outweigh this drawback. It shifts the burden of correct formatting from complex prompt engineering to using the library's features designed for this purpose, leading to more maintainable and reliable structured data generation from atomic tasks.

---
