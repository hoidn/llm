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


---

Notes

In the context of the **chat interface** (Use Case 1, addressed in Phases 3 & 4), the `/aider <text>` command is intended to be an **LLM-initiated tool call**.

Here's the breakdown of that flow:

1.  **User Input:** The user types `/aider Refactor the login function...` into the REPL.
2.  **REPL to Handler:** The REPL treats this as regular user input (not a special internal command like `/help` or `/mode`) and passes the *entire string* `" /aider Refactor the login function..."` to the `PassthroughHandler.handle_query`.
3.  **Handler to LLM:** The `PassthroughHandler` adds this user message to the `conversation_history`. When it calls `_send_to_model`, it sends:
    *   The full conversation history (including the message starting with `/aider`).
    *   The *definitions* of the registered tools (`aiderInteractive`, `aiderAutomatic`).
4.  **LLM Decision:** The LLM processes the conversation. Seeing the user's latest message (`/aider Refactor...`) and knowing about the available Aider tools (from their descriptions), the **LLM decides** that the user's intent is best served by using either the `aiderInteractive` or `aiderAutomatic` tool. The `/aider` prefix acts as a very strong hint, making this decision highly probable.
5.  **LLM Response (Tool Call):** The LLM sends back a response indicating it wants to call, for example, the `aiderInteractive` tool, passing `"Refactor the login function..."` as the `query` parameter.
6.  **Handler Executes Tool:** The `PassthroughHandler` detects this tool call request, extracts the tool name and parameters, and calls `_execute_tool`.
7.  **Executor Runs:** The specific executor function registered for `aiderInteractive` runs. As per the Phase 3 plan, this executor then performs the specialized context retrieval (using the passed query and chat history) *before* calling the `AiderBridge` method to actually start Aider.

**Why this approach?**

*   **Leverages LLM Capabilities:** It uses the LLM's understanding to map the user's natural language (even if prefixed with `/aider`) to the appropriate tool and parameters.
*   **Flexibility:** The user doesn't *have* to use the `/aider` prefix. They could potentially say "Use Aider to refactor the login function," and the LLM *should* still be able to figure out which tool to call. The prefix just makes it more explicit.
*   **Consistency:** It treats Aider interactions initiated from the chat the same way any other potential tool would be invoked – via the LLM's tool-use mechanism.

**Contrast with Programmatic Invocation (Phase 1):**

The plan *also* includes setting up programmatic invocation via the Task System (e.g., using a hypothetical `/task aider:automatic ...` REPL command or direct API calls). In *that* scenario:

1.  A specific `TaskSystem` template (`aider:automatic`) is explicitly targeted.
2.  `TaskSystem.execute_task` is called.
3.  The registered *programmatic executor* function is run directly.
4.  This executor calls the `AiderBridge` method.
5.  The LLM is **not involved** in deciding *to start* the Aider task (though Aider itself uses an LLM internally).

So, `/aider <text>` in the chat is designed as an **LLM-initiated tool call prompted by the user**, while `/task aider:automatic ...` (or equivalent API call) is a **direct programmatic invocation** bypassing the LLM's decision-making step for initiating the task.

---

**Addendum: Code and Specification References**

This addendum provides specific references to the project's conventions, existing code, and relevant concepts discussed during planning to clarify the implementation details for each phase.

**Phase 1: Solidify Programmatic Aider via Task System**

*   **Goal Clarification:** The aim is to execute Aider via `TaskSystem.execute_task`, making it a structured, repeatable action triggered by code, not by the chat LLM's decision.
*   **Key Concept:** Programmatic vs. LLM-based Template Execution (as discussed)
    *   **Reference:** See discussion on "Representing Programmatic vs. LLM-Based Templates" and the recommendation for **Option C (Explicit Programmatic Executors)**.
    *   **Code Impact (`task_system/task_system.py` - `execute_task`):** The logic needs to be added *before* the generic fallback to `handler.execute_prompt`.
        ```python
        # Inside TaskSystem.execute_task, after parameter resolution:
        task_key = f"{task_type}:{task_subtype}"

        # ---> NEW LOGIC START <---
        if task_key in self.PROGRAMMATIC_EXECUTORS: # Assuming PROGRAMMATIC_EXECUTORS dict exists
            # Requires access to aider_bridge instance, potentially passed via Application
            aider_bridge = self.application.aider_bridge # Example access pattern
            try:
                 # Execute the registered Python function directly
                 result = self.PROGRAMMATIC_EXECUTORS[task_key](resolved_inputs, aider_bridge)
                 # Ensure result is wrapped correctly if executor doesn't return full TaskResult
                 if not isinstance(result, dict) or "status" not in result:
                     # Basic wrapping, refine as needed
                     return {"status": "COMPLETE", "content": str(result), "notes": {}}
                 return result
            except Exception as e:
                 # Handle errors from the programmatic executor
                 return format_error_result(create_task_failure(f"Error executing programmatic task {task_key}: {e}", ...))
        # ---> NEW LOGIC END <---

        elif task_key == "atomic:associative_matching":
            # Existing specialized LLM logic for associative matching
            return self._execute_associative_matching(...)
        else:
            # Fallback to generic handler/LLM prompting
            handler = self._get_handler(...) # Or get handler passed in
            return handler.execute_prompt(...)
        ```
*   **Template Definition:** The new `aider:automatic` and `aider:interactive` templates should be simple dictionaries registered with `task_system.register_template`. They primarily define the `type`, `subtype`, `name`, and `parameters`.
    *   **Reference:** Similar structure to `FORMAT_JSON_TEMPLATE` in `task_system/templates/function_examples.py`, but without a `system_prompt` if purely programmatic.
*   **Executor Functions:** These are standard Python functions.
    *   **Reference:** Similar in concept to `execute_format_json` in `task_system/templates/function_examples.py`, but these will call methods on the `AiderBridge` instance.

**Phase 2: Implement Multi-Step Tool Calling**

*   **Goal Clarification:** Enhance the *chat handler* (`PassthroughHandler`) to manage sequences where the LLM requests a tool, the tool runs, and the result is sent *back* to the LLM for a follow-up response, all within one user turn.
*   **Key Concept:** LLM Tool Use Workflow (LLM -> Tool -> LLM)
    *   **Reference:** The `awaiting_tool_response` flag in `handler/model_provider.py` (`ClaudeProvider.extract_tool_calls`) and the explicit note in `PassthroughHandler._send_to_model`: `"The model is requesting to use a tool, but multi-step tool interactions are not fully implemented yet."` This phase implements that missing logic.
*   **Code Impact (`handler/passthrough_handler.py` - `_send_to_model`):** The core change involves replacing the simple `send -> extract -> maybe execute -> return` logic with a loop.
    ```python
    # Inside PassthroughHandler._send_to_model (Conceptual Structure)
    current_messages = formatted_messages # Start with history up to user query
    max_tool_calls = 5 # Example limit
    calls_made = 0

    while calls_made < max_tool_calls:
        response = self.model_provider.send_message(
            messages=current_messages,
            system_prompt=system_prompt,
            tools=tools
        )
        extracted = self.model_provider.extract_tool_calls(response)
        llm_content = extracted.get("content", "")
        tool_calls = extracted.get("tool_calls", [])
        awaiting_response = extracted.get("awaiting_tool_response", False)

        # Append LLM's turn (potentially requesting tools)
        # Need to reconstruct the actual message format the provider expects
        current_messages.append({"role": "assistant", "content": llm_content, "tool_calls": tool_calls}) # Simplified example

        if not tool_calls and not awaiting_response:
            # LLM provided final answer, break loop
            final_content = llm_content
            break # Exit loop

        if tool_calls:
            calls_made += len(tool_calls)
            tool_results_messages = [] # Collect results for next LLM call
            final_content = "" # Reset final content, expecting LLM follow-up

            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                tool_params = tool_call.get("parameters")
                tool_result = self._execute_tool(tool_name, tool_params) # Existing method

                # ---> NEW: Format tool_result for LLM <---
                # This depends heavily on the LLM provider (e.g., Anthropic's format)
                tool_result_message = self.model_provider.format_tool_result(tool_call, tool_result) # Assumes provider has this helper
                tool_results_messages.append(tool_result_message)
                # Store or log the immediate tool result if needed
                # final_content += f"\n[Tool {tool_name} Result: {tool_result.get('content', 'No content')}]" # Example for logging

            current_messages.extend(tool_results_messages) # Add tool results for next LLM call
            # Continue loop to send results back to LLM
        else:
             # No tool calls, but might be waiting? Or just finished?
             # Handle edge cases like awaiting_response=True but no calls
             final_content = llm_content # Use the last LLM content if no tools executed
             break # Exit loop

    # After loop: Process final_content, update main conversation_history
    # ... rest of the original function ...
    return final_content # Or the last tool result if that's the final action? Needs definition.

    ```
*   **Provider Interface (`handler/model_provider.py`):** May need a new method like `format_tool_result(tool_call_request, tool_execution_result)` in the `ProviderAdapter` and its implementations to create the correctly structured message for the specific LLM API (e.g., Anthropic uses a `tool_result` role).

**Phase 3: Refine LLM-Driven `/aider <text>` Invocation Context**

*   **Goal Clarification:** Make the Aider tools, *when invoked by the LLM during chat*, use context derived from both the specific instruction (`<text>`) and the prior chat history.
*   **Key Concept:** Contextualizing Tool Execution.
    *   **Reference:** The plan's discussion point #2 about how the tool executor gets `conversation_history`.
    *   **Code Impact (`aider_bridge/tools.py` - Tool Executors):** The executor functions need access to the handler state. Using closures (Option A) is recommended.
        ```python
        # Inside aider_bridge/tools.py -> register_automatic_tool
        def register_automatic_tool(handler: Any, aider_bridge: Any): # handler is available here
             tool_spec = ...
             # Define executor closure
             def aider_automatic_executor(input_data: Dict[str, Any]) -> Dict[str, Any]:
                 prompt = input_data["prompt"] # This is the <text> from the user's /aider command
                 # ---> NEW: Access handler state via closure <---
                 history = handler.conversation_history
                 memory = handler.memory_system
                 # ---> NEW: Construct specialized context input <---
                 # Combine prompt and history intelligently here
                 combined_query_for_context = f"Instruction: {prompt}\n\nRelevant History:\n{json.dumps(history[-5:])}" # Example
                 context_input = ContextGenerationInput(
                     template_description=combined_query_for_context,
                     # Add other fields as needed, maybe prioritize prompt via context_relevance
                     inputs = {"query": prompt}, # Pass original prompt maybe?
                     context_relevance = {"query": True} # Example relevance
                 )
                 logging.debug(f"Aider tool getting context for: {combined_query_for_context[:100]}...")
                 context_result = memory.get_relevant_context_for(context_input)
                 file_paths = [m[0] for m in context_result.matches] if hasattr(context_result, 'matches') else []
                 logging.debug(f"Aider tool determined file paths: {file_paths}")
                 # ---> Call bridge with determined files <---
                 return aider_bridge.execute_automatic_task(prompt, file_paths) # Pass determined paths

             success = handler.register_tool(tool_spec, aider_automatic_executor)
             # ... rest of function ...
        ```

**Phase 4: Implement `/plan` Command**

*   **Goal Clarification:** Allow users to type `/plan <request>` in the chat to get an LLM-generated plan wrapped in `<plan>` tags.
*   **Code Impact (`handler/passthrough_handler.py`):** Modify prompt construction logic.
    *   **Reference:** The specification for `PassthroughHandler` mentions extending the `base_system_prompt`. This phase might involve further additions or conditional logic based on user input.
    ```python
    # Inside PassthroughHandler.handle_query or _send_to_model

    user_query = query # Original user input e.g., "/plan do something"
    final_query_to_llm = user_query
    additional_system_instructions = ""

    if user_query.lower().startswith("/plan "):
        plan_request = user_query[len("/plan "):].strip()
        # Modify the query/prompt sent to the LLM
        final_query_to_llm = f"Generate a step-by-step plan for the following request: {plan_request}"
        # Inject instruction into system prompt (or append to user query)
        additional_system_instructions = "\n\nIMPORTANT: Enclose the generated plan within <plan> and </plan> XML tags."
        # This instruction needs to be added to the system_prompt sent to the model_provider
        # E.g., Modify how system_prompt is built or passed in _send_to_model

    # ... rest of the logic to build system_prompt and call model_provider ...
    # Make sure 'additional_system_instructions' gets included in the final system prompt if needed.
    # E.g., system_prompt = self._build_system_prompt(...) + additional_system_instructions
    response = self.model_provider.send_message(messages=..., system_prompt=..., ...)
    ```
*   **Dependency:** Relies heavily on Phase 2 if the plan needs to be executed step-by-step using tools later. Plan *generation* itself does not strictly require Phase 2.

---

This addendum provides specific code touchpoints and references the prior discussion to ensure the developer understands the *how* and *why* behind each phase, connecting the plan back to the existing codebase and architectural decisions.

---

**Addendum 2: Clarification on Task Invocation Flows**

This addendum clarifies the distinct pathways for initiating tasks and tool usage within the system, based on the architecture defined in the referenced `.md` files. Understanding these pathways is crucial for implementing both user-driven interactions and potential autonomous agent workflows.

**1. LLM-Initiated Actions: Tool Calls**

*   **Specification:** The primary mechanism for the LLM to request actions during a conversation (e.g., via `PassthroughHandler`) is **standard tool calling**.
    *   **Reference:** [Pattern:ToolInterface:1.0](./system/architecture/patterns/tool-interface.md) - Describes the unified interface presented to the LLM.
    *   **Reference:** [Interface:Handler:1.0](./components/handler/spec/interfaces.md) - Defines `register_tool`, `registerDirectTool`, `registerSubtaskTool` methods for exposing capabilities *to the LLM* as tools.
    *   **Reference:** `PassthroughHandler._send_to_model` implementation detail - Logic focuses on detecting `tool_calls` in the LLM response.
*   **Flow:**
    1.  User query (e.g., `/aider <text>` or natural language like "Use Aider to...") is sent to the LLM along with registered tool definitions.
    2.  The **LLM decides** which tool to use (e.g., `aiderAutomatic`) and specifies parameters (e.g., `prompt`).
    3.  The `Handler` detects this tool call request.
    4.  The `Handler` calls `_execute_tool`, running the corresponding registered Python executor function.
*   **Key Point:** The LLM interacts via a predefined set of tools, initiating actions through this specific mechanism. It does not directly request `TaskSystem` template execution.

**2. Programmatic Task Execution**

*   **Specification:** The `TaskSystem` is designed for structured task execution initiated *programmatically*.
    *   **Reference:** [Interface:TaskSystem:1.0](./components/task-system/api/interfaces.md) - Defines `executeTask` and `executeCall` as the public API for programmatic execution.
    *   **Reference:** Plan Phase 1 ("Solidify Programmatic Aider via Task System") - Explicitly aims to enable *programmatic* Aider invocation via `TaskSystem`.
    *   **Reference:** Discussion on "Representing Programmatic vs. LLM-Based Templates" & Recommendation C - Proposes distinguishing programmatic execution logic within `TaskSystem.execute_task`.
*   **Flow:**
    1.  External code (e.g., a script, test, REPL command handler for `/task`, or future autonomous agent logic) identifies a specific task template (`type:subtype`).
    2.  This code calls `TaskSystem.execute_task(...)` or `TaskSystem.executeCall(...)` directly, providing the necessary inputs.
    3.  The `TaskSystem` finds the template and executes its associated logic (either a registered programmatic Python function or LLM-based prompting via a Handler).
*   **Key Point:** This path bypasses the conversational LLM's decision-making *for initiating the task*. The choice of task is made by the calling code.

**3. Subtasks: An Internal Mechanism (Often Triggered by Tools)**

*   **Specification:** Subtasks, as defined by the `CONTINUATION` status and `subtask_request` ([Protocol:SubtaskSpawning:1.0](./system/contracts/protocols.md)), are an *internal* mechanism for chaining operations, often initiated *as a result* of an LLM tool call.
    *   **Reference:** [Pattern:ToolInterface:1.0](./system/architecture/patterns/tool-interface.md) - Explicitly links "Subtask Tools" (registered with the Handler) to the `CONTINUATION` mechanism managed by the Task System/Evaluator.
    *   **Reference:** [ADR 11: Subtask Spawning Mechanism](./system/architecture/decisions/completed/011-subtask-spawning.md) - Details the flow where a parent task (often the executor function for an LLM-invoked tool) returns `CONTINUATION` to trigger a subtask.
*   **Flow (Example with LLM calling a Subtask Tool):**
    1.  LLM calls Tool `X`.
    2.  Handler executes the executor function for Tool `X`.
    3.  Executor function determines a subtask is needed and returns `status: "CONTINUATION"` with `notes: {subtask_request: {...}}`.
    4.  The `TaskSystem`/`Evaluator` handles this continuation, finds the appropriate template for the subtask, and executes it (potentially involving *another* LLM call for the subtask itself).
    5.  The subtask result is eventually passed back to the Handler.
    6.  The Handler formats this as the *result of the original Tool X call* and sends it back to the LLM (requires multi-step, Phase 2).
*   **Key Point:** Subtasks are not *directly* initiated by the LLM's primary response. They are an implementation detail hidden behind the tool interface, enabling complex operations to be performed in response to a single tool call from the LLM's perspective.

**Implications for Autonomous LLM Agent (Scenario C):**

*   If the agent LLM decides to perform an action corresponding to a registered *tool* (like `aiderAutomatic`), the agent code should trigger the `Handler`'s tool call flow (as in User-Driven Scenario A).
*   If the agent LLM decides to perform a complex operation defined *only* as a `TaskSystem` template (e.g., a custom multi-step refactoring template), the agent code must parse this intent and make a *programmatic* call to `TaskSystem.execute_task` (as in Scenario B).

**Open Questions (Regarding Invocation and Tooling):**

1.  **LLM Tool Calling Conventions:** How reliably can current LLMs (Claude, GPT-4, etc.) *consistently* choose the correct tool (`aiderInteractive` vs. `aiderAutomatic`) and provide *perfectly formatted* parameters based *only* on natural language instructions and tool descriptions? How much prompt engineering around the tool descriptions and user input handling (like the `/aider` prefix) is needed?
2.  **Error Handling for Failed Tool Calls:** If the LLM makes a tool call with invalid parameters (e.g., wrong type, missing required field), how should this be handled? Should the Handler attempt to fix it, return an error *to the LLM* for correction (requires multi-step), or fail the turn?
3.  **Granularity of Tools vs. Tasks:** What is the right balance? Should complex operations be exposed as single, complex "subtask tools" (simpler for the LLM to call, complex internal logic), or should they be broken down into sequences of simpler "direct tools" that the LLM needs to chain together (requires robust multi-step handling and more complex reasoning from the LLM)?
4.  **Discoverability:** How does the LLM (or an autonomous agent) discover *which* Task System templates are available for programmatic execution if it needs to request one? Does the agent need a "list\_available\_tasks" tool?
5.  **Unified Invocation Interface?** Is there value in creating a single entry point (e.g., in `Application`) that could accept either a raw chat query (goes to `PassthroughHandler`) or a structured task request (goes to `TaskSystem`), simplifying the interface for external callers or agents?

Addressing these questions will be important as the multi-step capabilities and potentially more autonomous workflows are developed.

---
