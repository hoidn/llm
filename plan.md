**Project Implementation Plan (Revised & Corrected)**

**Overall Goal:** Build a system capable of orchestrating LLM interactions, external tools (Git, Aider via MCP), and file system operations via an S-expression DSL, leveraging `pydantic-ai` for LLM calls and Pydantic for data modeling.

**Core Technologies/Patterns:**

*   S-expression DSL evaluated by `SexpEvaluator`.
*   Atomic tasks defined in XML, managed by `TaskSystem`.
*   `pydantic-ai` library for all LLM interactions via `LLMInteractionManager` within `BaseHandler`.
*   Pydantic models for data structures and validation (`src/system/models.py`, `Parse, Don't Validate`).
*   Unified Tool Interface (`BaseHandler.register_tool`) for Direct Tools (sync, Handler-executed) and Subtask Tools (async, LLM-delegated).
*   Aider integration via an external **Aider MCP Server** and an internal **AiderBridge (MCP Client)**.

---

**Phase Breakdown:**

*   **Phase 0: Foundational Utilities & Interfaces**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Establish core building blocks, types, and contracts.
    *   **Components:** Core utilities (`src.handler.file_access`, `src.handler.command_executor`), shared Pydantic models (`src.system.models`), base IDL definitions, `SexpParser`, `SexpEnvironment`.
    *   **Outcome:** Essential building blocks, Pydantic models, and contracts defined.
    *   **Readiness:** Level 0: Foundational Code.

*   **Phase 1A: Mechanical IDL-to-Python Skeleton Creation**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Create basic Python code structure from IDLs.
    *   **Components:** Empty Python class/module files matching IDLs with `__init__` and method stubs.
    *   **Outcome:** Code structure established.
    *   **Readiness:** Level 0: Foundational Code.

*   **Phase 1B: Core Component Basic Logic**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Implement basic initialization, state, and dependency injection.
    *   **Components:** `MemorySystem`, `BaseHandler`, `TaskSystem` (`__init__`, basic state, dependency injection setup), `LLMInteractionManager`, `FileContextManager` (instantiated within `BaseHandler`), simple registration methods (`register_tool`, `register_template` basic storage).
    *   **Outcome:** Core components are instantiable and manage basic state.
    *   **Readiness:** Level 1: Core Systems Bootstrapped (Start).

*   **Phase 2a: Refine `MemorySystem` Logic**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Implement core memory storage and retrieval.
    *   **Components:** `MemorySystem` (`update_global_index`, basic `get_relevant_context_for` implementation, sharding config).
    *   **Outcome:** Memory system can store metadata and perform context lookups.
    *   **Readiness:** Level 1: Core Systems Bootstrapped (+).

*   **Phase 2b: Refine `BaseHandler` & `LLMInteractionManager` Logic**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Enable LLM interaction and direct tool execution.
    *   **Components:** `BaseHandler` (`_execute_llm_call` via `LLMInteractionManager`, `_build_system_prompt`, `_execute_tool`, `execute_file_path_command`), `LLMInteractionManager` (`execute_call` using `pydantic-ai`), `FileContextManager` (`get_relevant_files`, `create_file_context`).
    *   **Outcome:** System can interact with LLMs via `pydantic-ai` and execute directly registered tools.
    *   **Readiness:** Level 1: Core Systems Bootstrapped (++).

*   **Phase 2c: Refine `TaskSystem` Logic (Orchestration) & Fix Tests + Refactoring**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Implement atomic task orchestration logic and ensure core components interact correctly.
    *   **Components:** `TaskSystem` (template finding, file path resolution via `file_path_resolver`, context mediation via `generate_context_for_memory_system`, context setting validation/merging, `execute_atomic_template` core logic), `TemplateRegistry`. Refactoring completed.
    *   **Outcome:** TaskSystem can manage templates and orchestrate atomic task execution preparation; core components are robust.
    *   **Readiness:** Level 1: Core Systems Bootstrapped (Done).

*   **Phase 3: Implement Executors & Higher-Level Handlers**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Enable execution of atomic tasks and S-expression workflows; provide basic user interaction.
    *   **Components:** `AtomicTaskExecutor` (executes template bodies based on `params`), `SexpEvaluator` (parses/runs S-expressions, implements `if`/`let`/`bind`/`quote`/`list`/`get_context`, handles task/tool invocation), `PassthroughHandler` (handles chat query, calls `_get_relevant_files`, `_create_file_context`, `_execute_llm_call`, registers `executeFilePathCommand` tool).
    *   **Outcome:** System can execute atomic tasks and complex S-expression workflows; basic user interaction via PassthroughHandler is possible.
    *   **Readiness:** Levels 2, 3, 4: Execution & Basic UI Ready.

*   **Phase 3b: Structured Output Implementation (Pydantic-AI)**
    *   **Status:** IMPLEMENTED
    *   **Goal:** Implement reliable structured output (e.g., JSON parsed into Pydantic models) for atomic tasks using `pydantic-ai`'s capabilities, as per `ADR_pydantic_output.md`.
    *   **Components & Tasks:**
        1.  **Schema-to-Model Mapping:** Implement a mechanism (e.g., registry or convention-based import) within `AtomicTaskExecutor` (or an accessible helper) to resolve Pydantic model class names (strings like `"MyOutputModel"`) found in template `output_format.schema` fields into actual Python Pydantic model classes (e.g., `src.system.models.MyOutputModel`).
        2.  **`AtomicTaskExecutor` Update:** Modify `AtomicTaskExecutor.execute_body` to:
            *   Detect when `atomic_task_def.output_format` specifies `{"type": "json", "schema": "ModelName"}`.
            *   Use the mapping mechanism (from step 1) to get the corresponding Pydantic model class.
            *   Pass this resolved model class as the `output_type_override` argument when calling `handler._execute_llm_call`.
            *   Receive the parsed Pydantic model instance back from the handler (if successful).
            *   Place the received Pydantic instance directly into the `TaskResult.parsedContent` field.
        3.  **`BaseHandler`/`LLMInteractionManager` Update:** Modify `BaseHandler._execute_llm_call` and `LLMInteractionManager.execute_call` to accept the `output_type_override` parameter and pass it down to the `pydantic-ai` `agent.run_sync()` call.
        4.  **Result Handling Update:** Ensure `LLMInteractionManager` returns the parsed Pydantic instance received from `agent.run_sync()` when `output_type_override` is used successfully.
    *   **Integration:** Requires changes in `AtomicTaskExecutor`, `BaseHandler`, `LLMInteractionManager`. Relies on Pydantic models defined (likely in `src.system.models`). May allow simplification in components that previously validated JSON results manually (e.g., `MemorySystem` for context tasks).
    *   **Testing:** Add tests verifying that the `output_type_override` is passed correctly, that `pydantic-ai` performs parsing/validation, and that the resulting Pydantic object is placed in `TaskResult.parsedContent`. Test error handling for schema mapping failures or `pydantic-ai` validation errors.
    *   **Outcome:** Atomic tasks requiring structured output leverage `pydantic-ai`'s robust mechanisms, increasing reliability and simplifying validation logic.
    *   **Readiness:** Core Feature Enhancement (Builds on Phase 3).

*   **Phase 4: Specialized Features (Indexers & System Tools)**
    *   **Status:** PARTIALLY IMPLEMENTED (Core logic done, text_extraction is placeholder)
    *   **Goal:** Implement integration with Git for indexing and add specific system-level tools callable from S-expressions. Implement generic model-agnostic tools.
    *   **Components & Tasks:**
        1.  **`GitRepositoryIndexer` (`src/memory/indexers/git_repository_indexer.py`):** Implement class based on IDL. Requires `GitPython`. Implement scanning, metadata creation (using `text_extraction` helpers and GitPython), and calling `memory_system.update_global_index`.
        2.  **`MemorySystem.index_git_repository` (`src/memory/memory_system.py`):** Implement method to use the indexer.
        3.  **`SystemExecutorFunctions` (`src/executors/system_executors.py`):** Implement `execute_get_context` (using `MemorySystem`) and `execute_read_files` (using `FileAccessManager`) based on IDL. These are generic, model-agnostic tools.
        4.  **(Optional) Implement other generic File/Bash Tools:** If needed beyond `system:read_files` and the command executor, implement Python functions (e.g., `list_directory`, `write_file`) and register them with `BaseHandler` using `register_tool`.
        5.  **Testing:** Write unit/integration tests for indexer and system/generic tools. Requires mocking for Git interaction.
    *   **Integration:** `Application` (Phase 6) will need to register the System and Generic tools with the `PassthroughHandler`.
    *   **Outcome:** System gains Git indexing and useful generic system/file/bash tools accessible via S-expressions or LLM calls (handled by `pydantic-ai`).
    *   **Readiness:** Partial Level 5: Advanced Features Enabled (Git indexing and system tools available, code editing feature deferred).

*   **Phase 5: `defatom` Special Form**
    *   **Status:** IMPLEMENTED
    *   **Goal:** Enhance the S-expression DSL to allow inline definition of simple atomic tasks via global registration.
    *   **Components & Tasks:** `SexpEvaluator`. Implement `defatom` special form logic and tests as per ADR.
    *   **Outcome:** DSL usability improved; simple LLM tasks can be defined inline within workflows.
    *   **Readiness:** DSL Enhancement (Builds on Phase 4).

*   **Phase 6: Top-Level Integration & Dispatching (`Dispatcher`, `Application`)**
    *   **Status:** IMPLEMENTED
    *   **Goal:** Create the main application entry point and the dispatcher for `/task` commands, wiring all components together.
    *   **Components & Tasks:** `Dispatcher` (`src/dispatcher.py`), `Application` (`src/main.py`). Implement `DispatcherFunctions.execute_programmatic_task` (routing S-exp vs direct ID). Implement `Application` class (`__init__` wiring components, `handle_query`, `index_repository`, `handle_task_command` using Dispatcher). Implement helper `_register_system_tools` to register generic tools from Phase 4.
    *   **Testing:** Integration tests for Dispatcher routing logic and basic `Application` functionality.
    *   **Outcome:** System functions as a cohesive unit, accessible via `Application` methods and the `/task` dispatcher.
    *   **Readiness:** Level 6: Fully Integrated System (Initial - minus provider tools, Aider, Lambda).

*   **Phase 7: Provider-Specific Tool Integration (e.g., Anthropic Editor)**
    *   **Status:** PENDING
    *   **Goal:** Implement and conditionally register tools specific to certain LLM providers (e.g., Anthropic Editor tools), making them available to the `pydantic-ai` agent only when the corresponding provider is active.
    *   **Detailed Steps:**
        1.  **Identify & Define Provider-Specific Tools:** Research and define functionality (e.g., Anthropic Editor tools).
        2.  **Implement Tool Logic:** Create Python functions for the tools (e.g., in `src/tools/anthropic_tools.py`).
        3.  **Define Tool Specifications (`tool_spec`):** Create `tool_spec` dictionaries (`name`, `description`, `input_schema`) compatible with the provider and `pydantic-ai`.
        4.  **Implement Unit Tests for Tool Logic:** Write `pytest` unit tests for the new tool functions, mocking dependencies.
        5.  **Implement Conditional Registration in `Application`:** Modify `Application.__init__` to check `handler.get_provider_identifier()` and conditionally call `handler.register_tool()` for provider-specific tools. This registration must happen before the LLMInteractionManager is initialized.
        6.  **Modify `LLMInteractionManager` Initialization:** Update `LLMInteractionManager._initialize_pydantic_ai_agent` to retrieve the complete list of registered tools from the BaseHandler and pass this full list to the pydantic-ai Agent constructor (e.g., `Agent(..., tools=all_registered_tools)`).
        7.  **Implement Integration Tests:** Verify conditional registration in `Application` based on provider config. Verify the pydantic-ai Agent is initialized with the correct complete set of tools.
        8.  **Update Documentation:** Update relevant IDLs, `implementation_rules.md`, `plan.md`, and add docs for new tools.
    *   **Integration:** Leverages `pydantic-ai`'s handling of provider-specific tool schemas. The AI model itself will determine which tools from the available set are appropriate to use based on their descriptions.
    *   **Testing:** Test conditional registration and tool availability based on provider configuration.
    *   **Outcome:** System can leverage powerful provider-specific tools when the appropriate LLM is in use.
    *   **Readiness:** Feature Enhancement (Builds on Level 6 & Phase 3b).

*   **Phase 8: Aider Integration (MCP Approach)**
    *   **Status:** DONE
    *   **Goal:** Add code editing capabilities using Aider via the MCP client/server model (as defined in ADR 19).
    *   **Prerequisites:** Functional external `Aider MCP Server`.
    *   **Components & Tasks:** `AiderBridge`, `AiderExecutorFunctions`, `BaseHandler`.
        1.  Document Aider MCP Server setup requirement.
        2.  Refactor `AiderBridge` into an MCP Client (using `pydantic-ai`'s `MCPClient` or `mcp.py`), implementing methods to send requests to the server. Remove direct Aider calls.
        3.  Update `AiderExecutorFunctions` (`execute_aider_automatic`, `execute_aider_interactive`) to use the refactored `AiderBridge` (MCP Client).
        4.  Register `aider:automatic` and `aider:interactive` tools with `BaseHandler` using the updated executors.
    *   **Integration:** Connects to external Aider MCP Server. Invoked via standard tool mechanism.
    *   **Testing:** Integration tests for `AiderBridge` (mocking MCP server), executor functions. E2E requires running server.
    *   **Documentation:** Deprecate old Aider IDLs, update bridge/executor IDLs to reflect MCP client role. Reference ADR 19.
    *   **Outcome:** System gains code editing features via Aider/MCP. **Completes Feature Readiness Level 5.**
    *   **Readiness:** Advanced Feature Enabled (Builds on Level 6, Phase 7).

**Phase 9: Core Agentic Tooling & Multi-LLM Support**

*   **Status:** PENDING
*   **Goal:** Enhance the system's ability to act as an agent by providing essential generic file system tools and enabling flexible LLM selection.
*   **Components & Tasks:**
    1.  **Generic File System Tools:**
        *   Implement provider-agnostic tools: `system:write_file`, `system:list_directory`, potentially `system:create_directory`.
        *   Leverage `FileAccessManager` for safe execution.
        *   Register these tools unconditionally in `Application._register_system_tools` alongside `system:read_files` and `system:get_context`.
        *   Write unit/integration tests for the new tool executors.
    2.  **Multi-LLM Routing/Execution:**
        *   Design and implement a mechanism to allow selecting or routing to different LLM providers/models during execution (e.g., via parameters in `evaluate_string` or task definitions, dynamic agent configuration, or managing multiple handlers). Choose one approach (e.g., dynamic configuration or parameter passing).
        *   Modify `BaseHandler`/`LLMInteractionManager` accordingly.
        *   Update `_execute_llm_call` and potentially task/tool invocation logic to handle model selection/routing.
        *   Add tests verifying that calls can be routed to different (mocked) providers/models.
*   **Integration:** Generic tools become available alongside provider-specific ones. Multi-LLM support enhances flexibility for all LLM calls originating from the Handler.
*   **Outcome:** System gains essential generic file manipulation tools usable by any LLM/DSL workflow and the flexibility to utilize different LLMs dynamically. Enables step 1 of the Vibecoding methodology (multi-model calls).
*   **Readiness:** Enhanced Agent Capabilities & Flexibility.

**Phase 10: S-expression `lambda` and Closures**

*   **Status:** PENDING
*   **Goal:** Implement anonymous functions with lexical scoping (closures) in the S-expression DSL, as per `ADR_lambdas.md`.
*   **Components & Tasks:** `SexpEvaluator`, `SexpEnvironment`, New `Closure` class.
    1.  Implement the `lambda` special form parsing/handling in `_eval_list`.
    2.  Define the internal `Closure` object to store parameters, body AST, and the definition environment.
    3.  Modify `_eval_list` (or `_handle_invocation`) to detect when the operator evaluates to a `Closure`.
    4.  Implement the function application logic: create new environment frame, link to closure's environment, bind arguments, evaluate body.
    5.  Write extensive unit tests covering closure creation, lexical scope capture (accessing variables from defining environment), argument binding, and recursive calls.
    6.  Update `SexpEvaluator_IDL.md`, `SexpEnvironment_IDL.md`, and DSL documentation/examples.
*   **Integration:** Deep changes within `SexpEvaluator` and `SexpEnvironment`. Enables significantly more complex and modular logic within S-expression workflows.
*   **Outcome:** DSL gains first-class functions and lexical scoping, dramatically increasing its expressive power.
*   **Readiness:** Core Language Enhancement.

**Phase 11: Workflow State Management & Resumption (Interactive Mode)**

*   **Status:** PENDING
*   **Goal:** Enable workflows to be suspended, have their state persisted, and be resumed later, potentially after external input (e.g., user feedback). Required for fully interactive agentic processes like Vibecoding.
*   **Components & Tasks:** This likely requires significant new components or major refactoring.
    1.  **Design State Representation:** Define how workflow state (current step, variable bindings/environment, generated artifacts/paths, etc.) will be represented.
    2.  **Design Persistence Mechanism:** Choose and implement how state will be saved/loaded (e.g., JSON files, database). Address serialization challenges (especially for `SexpEnvironment` if complex objects/closures are involved).
    3.  **Implement Suspend/Resume Points:** Define how workflows signal suspension (e.g., specific return status like `CONTINUATION` with state payload, explicit `(wait-for-input)` primitive). Modify the Python orchestrator or `SexpEvaluator` to handle suspension.
    4.  **Develop Resumption Logic:** Create mechanisms (e.g., a command, API endpoint, background process) to load state and resume workflow execution, potentially incorporating new input.
    5.  **Implement Error Handling & Recovery:** Address how to handle failures during suspended or resumed workflows.
    6.  Write comprehensive tests covering suspension, persistence, resumption, and error recovery.
*   **Integration:** Major architectural addition. Deeply impacts how workflows are defined and executed.
*   **Outcome:** System supports long-running, interactive, and potentially recoverable workflows. Enables full automation of processes requiring user-in-the-loop or interruption tolerance.
*   **Readiness:** Advanced Agent Interactivity & Reliability.

**Phase 12: Final Documentation Alignment & Review**

*   **Status:** PENDING
*   **Goal:** Ensure all documentation (IDLs, guides, ADRs, examples) is fully updated, consistent, and accurate, reflecting all implemented features including Lambda and State Management (if built). Perform final code review, testing, and potential release preparation.
*   **Components & Tasks:** Project-wide documentation review and updates, final testing sweep, code cleanup, potentially creating release notes.
*   **Integration:** N/A (Documentation phase).
*   **Outcome:** Project is polished, comprehensively documented, and ready for its next lifecycle stage.
*   **Readiness:** Final Polish & Release Readiness.

