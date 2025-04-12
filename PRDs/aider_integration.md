**Project:** LLM Interaction & Code Assistant Framework

**Goal:** Enhance the framework to support robust, structured task execution and more capable conversational interactions, focusing on reliable Aider integration and multi-step tool use.

**Target User:** Developer using the framework via REPL or potentially a future programmatic API.

**Overall Strategy:** Build foundational capabilities first (reliable programmatic execution, multi-step interactions) before layering more complex chat-based features. Prioritize leveraging the existing Task System architecture for structure and clarity.

---

**Phase 1: Solidify Programmatic Aider via Task System**

*   **Goal:** Enable reliable, structured invocation of Aider functions (automatic and interactive) through the Task System, independent of LLM tool-calling vagaries.
*   **User Story:** "As a developer using the framework programmatically (or via a specific command), I want to reliably execute an automatic Aider code edit or start an interactive Aider session by invoking a defined Task System task, providing the necessary prompt and file context."
*   **Requirements:**
    1.  **Define Aider Task Templates:**
        *   Create two new template dictionaries (similar in structure to `ASSOCIATIVE_MATCHING_TEMPLATE` but simpler):
            *   `aider_automatic_template`: `type="aider"`, `subtype="automatic"`, `name="aider_automatic"`. Parameters: `prompt` (string, required), `file_context` (list[string], optional).
            *   `aider_interactive_template`: `type="aider"`, `subtype="interactive"`, `name="aider_interactive"`. Parameters: `query` (string, required), `file_context` (list[string], optional).
        *   These templates likely won't need complex `system_prompt` or `description` fields initially, as they are primarily for programmatic execution.
    2.  **Implement Programmatic Executors:**
        *   Follow **Option C (Explicit Programmatic Executors)** recommended previously.
        *   Create Python functions (e.g., within `aider_bridge/bridge.py` or a new `task_system/executors.py`) that wrap the corresponding `AiderBridge` methods:
            *   `execute_aider_automatic(inputs, aider_bridge)`: Extracts `prompt`, `file_context` from `inputs`, calls `aider_bridge.execute_automatic_task`, returns result.
            *   `execute_aider_interactive(inputs, aider_bridge)`: Extracts `query`, `file_context`, calls `aider_bridge.start_interactive_session`, returns result.
        *   Register these functions in a `PROGRAMMATIC_EXECUTORS` dictionary within `TaskSystem`, keyed by `"aider:automatic"` and `"aider:interactive"`. (Requires passing `aider_bridge` instance during registration or having `TaskSystem` access it via `Application`).
    3.  **Update `TaskSystem.execute_task`:**
        *   Modify the dispatching logic to check `PROGRAMMATIC_EXECUTORS` first. If a `task_type:task_subtype` key matches, call the registered executor function, passing `resolved_inputs` and potentially the `aider_bridge`.
        *   Ensure the executor's return value (which should already be a TaskResult-like dict from `AiderBridge`) is returned correctly.
    4.  **Testing:**
        *   Add unit tests for the new templates and executor functions.
        *   Add integration tests (potentially extending `test_aider_flow.py` or creating new ones) that trigger these Task System tasks programmatically and verify Aider execution.
        *   Add a REPL command (e.g., `/task <type>:<subtype> param1=value1 ...`) for manual testing.
*   **Acceptance Criteria:**
    *   A developer can successfully run `/task aider:automatic prompt='Add type hints to f1.py' file_context=['/path/f1.py']` (or equivalent programmatic call) and have Aider execute the change.
    *   A developer can successfully run `/task aider:interactive query='Refactor f1.py' file_context=['/path/f1.py']` and be dropped into an interactive Aider session.
    *   Tests confirm the correct `AiderBridge` methods are called with correct parameters.

---

**Phase 2: Implement Multi-Step Tool Calling**

*   **Goal:** Enable the `PassthroughHandler` to manage a sequence of interactions where the LLM calls a tool, receives the result, and continues the conversation based on that result within a single logical user turn.
*   **User Story:** "As a user interacting with the chat interface, when I ask a question that requires information retrieval followed by an action (e.g., 'Find the config file and tell me the database host'), I want the system to use the necessary tools sequentially and provide a final answer incorporating the tool results, without me having to manually chain the commands."
*   **Requirements:**
    1.  **Refactor `PassthroughHandler._send_to_model`:**
        *   Introduce a loop or recursive structure to handle multiple LLM calls within one `handle_query` invocation.
        *   **Input:** Initial user query + conversation history.
        *   **Loop:**
            *   Call `model_provider.send_message`.
            *   Call `model_provider.extract_tool_calls` on the response.
            *   **If NO tool calls AND `awaiting_tool_response` is FALSE:** Break loop, return final LLM content.
            *   **If tool calls detected:**
                *   Append the LLM's message (requesting the tool) to a *temporary* history for this turn.
                *   For each tool call: Execute via `_execute_tool`.
                *   Format the tool execution result(s) into the LLM provider's required format (e.g., Anthropic's `tool_result` role/content structure).
                *   Append the tool result message(s) to the temporary history.
                *   Continue loop (make next `send_message` call with the temporary history).
            *   **If NO tool calls BUT `awaiting_tool_response` is TRUE:** Append the LLM's message, maybe append a placeholder "Waiting for tool input" message, and potentially break/return indicating waiting state (this needs clearer definition - maybe prompt user?). *Initial focus: Handle the case where tools ARE called.*
    2.  **Conversation History Management:** Ensure the *final* assistant response (after all tool calls in a turn) and the intermediate tool request/result messages are correctly appended to the main `conversation_history` before `handle_query` returns.
    3.  **Add Safety Limits:** Implement a maximum number of tool calls per user turn to prevent infinite loops or excessive cost.
    4.  **Testing:**
        *   Unit tests for the new loop logic in `_send_to_model`.
        *   Integration tests simulating multi-step scenarios:
            *   LLM asks for files -> Handler executes `executeFilePathCommand` -> LLM receives file list -> LLM asks to edit a file -> Handler executes `aiderAutomatic`.
            *   Mock the `model_provider` to return sequences of responses simulating tool requests and final answers.
*   **Acceptance Criteria:**
    *   A query like "Find all *.py files about 'auth' and then add a docstring to the first one found using Aider" can be processed in a single user turn, invoking both `executeFilePathCommand` and `aiderAutomatic`.
    *   The `conversation_history` correctly reflects the LLM's tool requests and the corresponding tool results.
    *   A maximum tool call limit prevents runaway execution.

---

**Phase 3: Refine LLM-Driven `/aider` Tool Invocation Context**

*   **Goal:** Ensure that when the `/aider` tool is invoked via the LLM in chat mode, the file context provided to Aider is intelligently determined using both the specific instruction and the chat history.
*   **User Story:** "As a user chatting with the system, if I say '/aider Refactor the login function based on our previous discussion about security', I want the system to automatically identify the relevant files using both my specific instruction ('Refactor the login function') and the context from our chat history ('previous discussion about security') before starting Aider."
*   **Requirements:**
    1.  **Modify Aider Tool Executors:**
        *   Update the `aider_interactive_executor` and `aider_automatic_executor` functions defined/registered in `aider_bridge/tools.py`.
        *   Ensure these functions have access to the `handler` instance (using the closure pattern recommended - Option A).
        *   Inside the executor, before calling the `AiderBridge` method:
            *   Extract the specific instruction (`<text>`) from `input_data`.
            *   Access `handler.conversation_history` and `handler.memory_system`.
            *   Construct a `ContextGenerationInput` specifically for this Aider context lookup:
                *   Use `<text>` as `template_description`.
                *   Optionally, summarize or select key parts of `conversation_history` to include in `inherited_context` or `previous_outputs`.
                *   Consider using `context_relevance` to strongly weight the `template_description`.
            *   Call `handler.memory_system.get_relevant_context_for(...)`.
            *   Extract the resulting file paths.
            *   Pass these dynamically determined file paths to `aider_bridge.start_interactive_session` or `execute_automatic_task`.
    2.  **Testing:**
        *   Unit tests for the modified executor functions, mocking `memory_system.get_relevant_context_for`.
        *   Integration tests using the REPL:
            *   Have a short conversation.
            *   Use the `/aider` command with a specific instruction.
            *   Verify (potentially through debug logs or mocked `AiderBridge` calls) that the file context passed to Aider was determined based on both the instruction and history.
*   **Acceptance Criteria:**
    *   Invoking `/aider <text>` causes the registered executor to run.
    *   The executor calls `memory_system.get_relevant_context_for` with inputs derived from `<text>` and the chat history.
    *   The file paths returned by the memory system are correctly passed to the `AiderBridge`.

---

**Phase 4: Implement `/plan` Command**

*   **Goal:** Allow users to ask the LLM to generate a multi-step plan within the chat interface.
*   **User Story:** "As a developer planning a feature, I want to type `/plan Create a new API endpoint for user profiles, including database schema changes and unit tests` and have the system generate a step-by-step plan enclosed in `<plan>` tags."
*   **Requirements:**
    1.  **REPL Command Handling:** Add `/plan` to `Repl.commands` and have it call `_handle_query` (or a dedicated handler method) with the plan request.
    2.  **Prompt Engineering:** Modify the `PassthroughHandler`'s system prompt (or add logic in `handle_query`/`_send_to_model`) to instruct the LLM: "If the user starts their query with `/plan`, generate a step-by-step plan to accomplish the request and enclose the entire plan within `<plan>...</plan>` XML tags."
    3.  **(Optional) Plan Execution:** While not strictly required by the story *generating* the plan, future work enabled by Phase 2 could involve detecting the `<plan>` tags in the LLM response and potentially allowing the user (or LLM) to trigger execution of individual steps using tools. This is beyond the scope of *this* phase.
    4.  **Testing:**
        *   Manual REPL testing: Use `/plan <request>` and verify the LLM output includes `<plan>` tags.
        *   Potentially add integration tests mocking the LLM to return a plan, verifying the handler processes it correctly.
*   **Acceptance Criteria:**
    *   Entering `/plan <request>` in the REPL results in an LLM response containing a plan.
    *   The generated plan is enclosed within `<plan>` and `</plan>` tags.

---

**Cross-Cutting Concerns (Address throughout):**

*   **Refine Error Handling:** Gradually replace `print` statements and basic error returns with `logging` and/or standardized error objects/exceptions.
*   **Configuration:** Implement the configuration loading recommended earlier (Phase 1 Low Hanging Fruit).
*   **Testing:** Maintain and expand unit and integration tests for all new and modified components.

This plan prioritizes building reliable core execution paths before adding more complex interactive features, while ensuring the critical multi-step tool capability is addressed relatively early.


---

Long version

**Enhanced Project Plan / PRD**

**Project:** LLM Interaction & Code Assistant Framework

**Goal:** Enhance the framework to support robust, structured task execution and more capable conversational interactions, focusing on reliable Aider integration and multi-step tool use.

**Target User:** Developer using the framework via REPL or potentially a future programmatic API.

**Overall Strategy:** Build foundational capabilities first (reliable programmatic execution, multi-step interactions) before layering more complex chat-based features. Prioritize leveraging the existing Task System architecture for structure and clarity. Establish clear execution paths for both programmatic tasks and LLM-driven tool use.

**Key Component Relationships:**

*   **Application (`main.py`):** Initializes and holds references to core components (`TaskSystem`, `MemorySystem`, `PassthroughHandler`, `AiderBridge`). Orchestrates REPL startup and potentially future API endpoints.
*   **REPL (`repl.py`):** User interface. Interacts primarily with `Application` to handle queries (`handle_query`) and commands (like `/task`, `/index`, `/reset`).
*   **PassthroughHandler (`handler/passthrough_handler.py`):** Manages chat state (`conversation_history`). Interacts with `MemorySystem` (via `_get_relevant_files`) for context paths, `FileAccessManager` (`_create_file_context`) for file content, `ModelProvider` (`_send_to_model`) for LLM calls, and `BaseHandler`'s tool mechanism (`_execute_tool`) for executing functions requested by the LLM.
*   **TaskSystem (`task_system/task_system.py`):** Manages templates. `execute_task` method acts as the entry point for structured tasks. It interacts with `TemplateProcessor`, `Evaluator`, potentially `MemorySystem` (for context within tasks), and dispatches execution either to programmatic functions or potentially back to a `Handler` for LLM-based steps. Mediates context generation for `MemorySystem`.
*   **Evaluator (`evaluator/evaluator.py`):** Called by `TaskSystem` (explicitly or implicitly) to evaluate AST nodes, specifically `FunctionCallNode`s found within templates. Interacts with `TaskSystem` (as a `TemplateLookupInterface`) to find templates for called functions.
*   **MemorySystem (`memory/memory_system.py`):** Stores file index. `get_relevant_context_for` is its primary interface for context retrieval, relying on the `TaskSystem` (via `generate_context_for_memory_system`) to perform the actual LLM-based relevance matching using the `associative_matching` template.
*   **AiderBridge (`aider_bridge/bridge.py`):** Encapsulates Aider logic. Provides programmatic methods (`execute_automatic_task`, `start_interactive_session`). Interacts with `MemorySystem` (`get_context_for_query`) to find files. Its functions are made available via registered tools (`aider_bridge/tools.py`) or potentially wrapped by TaskSystem templates.
*   **ModelProvider (`handler/model_provider.py`):** Abstract interface for LLM communication. `ClaudeProvider` is the concrete implementation. Handles API calls, including passing tool definitions and extracting tool calls/content from responses. Called by `Handler` and potentially specific TaskSystem templates (like `associative_matching`).

---

**Phase 1: Solidify Programmatic Aider via Task System**

*   **Goal:** Establish a reliable, programmatic path for invoking Aider actions using the structured Task System.
*   **Component Impact:**
    *   **TaskSystem:**
        *   New template dictionaries (`aider_automatic_template`, `aider_interactive_template`) added to `self.templates` and `self.template_index` during registration (e.g., in `main.py` or a dedicated template registration module).
        *   Implement the `PROGRAMMATIC_EXECUTORS` dictionary (Option C).
        *   Modify `execute_task` dispatch logic to check `PROGRAMMATIC_EXECUTORS` *before* falling back to the generic handler path. Requires access to the `AiderBridge` instance (likely passed down from `Application` or held as a member).
    *   **AiderBridge:** No changes needed, relies on existing `execute_automatic_task` and `start_interactive_session`.
    *   **Application:** Needs to instantiate `AiderBridge` and potentially pass it to `TaskSystem` during initialization so `execute_task` can access it for the programmatic executors.
    *   **REPL:** (Optional but recommended for testing) Add `/task` command to parse `type:subtype` and parameters, then call `Application.execute_task_programmatically` (a new method might be needed in `Application` to wrap `TaskSystem.execute_task`).
*   **Interfaces:** `TaskSystem.execute_task` interface remains the same, but internal logic changes. New programmatic executor functions are created.
*   **Benefit:** Creates a testable, reliable way to use Aider independent of LLM chat flow. Forms a building block for more complex workflows.

---

**Phase 2: Implement Multi-Step Tool Calling**

*   **Goal:** Enable conversational flows where the LLM can sequentially invoke tools and use their results within a single user query.
*   **Component Impact:**
    *   **PassthroughHandler:**
        *   Major refactoring of `_send_to_model` to implement the execution loop (LLM -> Tool -> LLM).
        *   Requires careful management of a temporary conversation history *within* the loop vs. the main `self.conversation_history`.
        *   Need to correctly format tool results (`tool_result` messages) for the `ModelProvider`.
        *   Implement safety limits (max calls per turn).
    *   **ModelProvider:** Needs to correctly handle receiving `tool_result` type messages in the `messages` list (the `ClaudeProvider` likely supports this already, but needs verification). `extract_tool_calls` logic remains crucial.
    *   **BaseHandler:** `_execute_tool` remains the core execution mechanism. No changes likely needed here.
    *   **AiderBridge/Tools:** No changes needed here *for this phase*. The tools are already registered; this phase enables the *handler* to manage multi-step sequences involving them.
*   **Interfaces:** The core `handle_query` interface remains, but the internal implementation of `_send_to_model` changes significantly. The interaction pattern with `ModelProvider` becomes more complex (multiple calls per `handle_query`).
*   **Benefit:** Unlocks sophisticated conversational interactions and enables features like `/plan` execution and complex LLM-driven Aider tasks. This is the most critical enhancement for Use Case 1.

---

**Phase 3: Refine LLM-Driven `/aider <text>` Invocation Context**

*   **Goal:** Improve the relevance of file context when Aider tools are invoked by the LLM based on chat history.
*   **Component Impact:**
    *   **AiderBridge Tools (`aider_bridge/tools.py`):**
        *   The executor functions defined/registered here (e.g., `aider_automatic_executor`) need modification.
        *   Implement the closure pattern (Option A) to capture the `handler` instance during registration (`register_aider_tools`).
        *   Inside the executor:
            *   Access `handler.conversation_history` and `handler.memory_system`.
            *   Construct the specialized `ContextGenerationInput` (prioritizing `<text>`, including history).
            *   Call `handler.memory_system.get_relevant_context_for` to get file paths.
            *   Pass these paths to the `AiderBridge` method.
    *   **PassthroughHandler:** Needs to make its `conversation_history` and `memory_system` accessible to the executor functions (which the closure pattern handles).
    *   **MemorySystem:** `get_relevant_context_for` interface is used as-is, but receives more carefully constructed input.
*   **Interfaces:** The tool executor function signature effectively changes (implicitly gaining access to handler state via closure). The interface between the Handler and the Tool Executor becomes richer.
*   **Dependency:** This phase *relies* on Phase 2 being complete if the goal is for the LLM to *act upon* the result of the Aider call within the same turn. However, the context refinement *within* the tool executor can be implemented even before Phase 2 is fully done, it just means the LLM won't get the Aider result back immediately. Implementing it after Phase 2 makes more sense.
*   **Benefit:** Makes the conversational `/aider` command much more contextually aware and useful.

---

**Phase 4: Implement `/plan` Command**

*   **Goal:** Allow users to request structured plans from the LLM via a chat command.
*   **Component Impact:**
    *   **REPL:** Add `/plan` command handling, passing the request to `Application.handle_query`.
    *   **PassthroughHandler:**
        *   Modify `handle_query` or `_send_to_model` to detect the `/plan` prefix.
        *   Inject specific instructions into the system prompt or user message sent to the `ModelProvider` to request plan generation within `<plan>` tags.
    *   **ModelProvider:** No changes needed. Receives the modified prompt.
    *   **TaskSystem/Evaluator:** Not directly involved in *generating* the plan text itself.
*   **Interfaces:** Primarily affects REPL command parsing and prompt construction logic within the `PassthroughHandler`.
*   **Dependency:** While plan *generation* can work without Phase 2, making the plan *actionable* (e.g., executing steps) heavily relies on Phase 2 (Multi-Step Tool Calling).
*   **Benefit:** Adds a valuable planning capability to the conversational interface.

