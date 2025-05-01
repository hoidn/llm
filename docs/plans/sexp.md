https://aistudio.google.com/prompts/1na9I7g_Wwkgs8M0knwLoqQnVxgA0jZC7 

**Full Revised Implementation Plan (Deferring Aider Integration)**

**Overall Goal:** Build a system capable of orchestrating LLM interactions, external tools, and file system operations via an S-expression DSL, with features for context management and Git indexing. *Code editing integration (Aider/MCP) is deferred.*

**Phase Breakdown:**

*   **Phase 0:** Foundational Utilities & Interfaces - **DONE & VERIFIED**
    *   **Components:** Core utilities (file access, command execution), shared Pydantic models (`src/system/models.py`), base IDL definitions, `SexpParser`, `SexpEnvironment`.
    *   **Outcome:** Essential building blocks and contracts defined.

*   **Phase 1A:** Mechanical IDL-to-Python Skeleton Creation - **DONE & VERIFIED**
    *   **Components:** Empty Python class/module files matching IDLs.
    *   **Outcome:** Code structure established.

*   **Phase 1B:** Core Component Basic Logic - **DONE & VERIFIED**
    *   **Components:** `MemorySystem`, `BaseHandler`, `TaskSystem` `__init__`, basic state, dependency injection, simple registration methods (`register_tool`, `register_template` storage). `LLMInteractionManager`, `FileContextManager` initialized within `BaseHandler`.
    *   **Outcome:** Core components are instantiable and manage basic state.

*   **Phase 2a:** Refine `MemorySystem` Logic - **DONE & VERIFIED**
    *   **Components:** `MemorySystem` (`update_global_index`, basic `get_relevant_context_for` keyword matching).
    *   **Outcome:** Memory system can store metadata and perform rudimentary context lookups.

*   **Phase 2b:** Refine `BaseHandler` & `LLMInteractionManager` Logic - **DONE & VERIFIED**
    *   **Components:** `BaseHandler` (`_execute_llm_call` via `LLMInteractionManager`, `_build_system_prompt`, `_execute_tool`), `LLMInteractionManager` (`execute_call` using `pydantic-ai`), `FileContextManager` (`get_relevant_files`, `create_file_context`).
    *   **Outcome:** System can interact with LLMs via `pydantic-ai` and execute directly registered tools.

*   **Phase 2c:** Refine `TaskSystem` Logic (Orchestration) & Fix Tests + Refactoring - **DONE & VERIFIED**
    *   **Components:** `TaskSystem` (template finding, file path resolution via `file_path_resolver`, context mediation via `generate_context_for_memory_system`, validation), `TemplateRegistry`.
    *   **Outcome:** TaskSystem can orchestrate atomic task execution preparation; core components are robust and interact correctly.

*   **Phase 3:** Implement Executors & Higher-Level Handlers - **DONE & VERIFIED**
    *   **Components:** `AtomicTaskExecutor` (executes template bodies), `SexpEvaluator` (parses/runs S-expressions, calls tasks/tools/primitives), `PassthroughHandler` (basic chat interaction).
    *   **Outcome:** System can execute atomic tasks and complex S-expression workflows; basic user interaction via PassthroughHandler is possible. **Achieves Feature Readiness Levels 2, 3, 4.**

*   **Phase 4:** Specialized Features (Indexers & System Tools) - **PENDING (NEXT)**
    *   **Goal:** Implement integration with Git and add specific system-level tools. *(Aider integration deferred)*.
    *   **Components:**
        *   `GitRepositoryIndexer`: Implement class based on IDL, including scanning, metadata creation (using `text_extraction` helpers and Git library/CLI), and calling `memory_system.update_global_index`.
        *   `MemorySystem.index_git_repository`: Implement method to use the indexer.
        *   `SystemExecutorFunctions`: Implement `execute_get_context` (using `MemorySystem`) and `execute_read_files` (using `FileAccessManager`) based on IDL.
    *   **Integration:** Ensure `Application` (in Phase 6) will register System tools/executors with the `PassthroughHandler`. *(No Aider tool registration needed here)*.
    *   **Testing:** Requires mocking for Git interaction.
    *   **Outcome:** System gains advanced capabilities for interacting with Git repos and using specific system utilities within workflows. **Achieves partial Feature Readiness Level 5** (Git indexing and system tools enabled, code editing feature deferred).

*   **Phase 5:** Implement `defatom` Special Form - **PENDING**
    *   **Goal:** Enhance the S-expression DSL to allow inline definition of simple atomic tasks.
    *   **Components:** `SexpEvaluator`.
    *   **Tasks:** (Same as previous plan) Implement `defatom` special form logic, test cases.
    *   **Outcome:** Users can define simple atomic LLM tasks directly within S-expression workflows, improving encapsulation and prototyping speed. DSL expressiveness increased.

*   **Phase 6:** Top-Level Integration & Dispatching (`Dispatcher`, `Application`) - **PENDING**
    *   **Goal:** Create the main application entry point and the dispatcher for `/task` commands.
    *   **Components:** `Dispatcher` (`src/dispatcher.py`), `Application` (`src/main.py`).
    *   **Tasks:**
        *   Implement `DispatcherFunctions.execute_programmatic_task`: Handle parsing, routing (Sexp vs direct), invocation, result formatting.
        *   Implement `Application`: `__init__` (wire components), `handle_query`, `index_repository`, `/task` handling via Dispatcher. Implement helper for system tool registration (`_register_system_tools`). *(No Aider initialization/registration needed here)*.
    *   **Testing:** Integration tests for Dispatcher and Application.
    *   **Outcome:** System functions as a cohesive whole, callable via the `Application` class. Programmatic task execution (`/task`) is enabled. **Achieves Feature Readiness Level 6** (minus code editing).

*   **Phase 7: Provider-Specific Tool Integration (e.g., Anthropic Editor)**
    *   **Status:** PENDING
    *   **Goal:** Implement and conditionally register tools specific to certain LLM providers.
    *   **Components & Tasks:** `BaseHandler`, `LLMInteractionManager`.
        1.  Implement Python functions for provider-specific tools (e.g., Anthropic editor tools, referencing `librarydocs/MCP_TOOL_GUIDE.md`).
        2.  Modify `BaseHandler` or `Application` initialization: Check the configured provider via `LLMInteractionManager`.
        3.  Conditionally register provider-specific tools using `BaseHandler.register_tool` only if the provider matches.
    *   **Integration:** Leverages `pydantic-ai`'s handling of provider-specific tool schemas.
    *   **Testing:** Test conditional registration and tool availability based on provider configuration.
    *   **Outcome:** System can leverage powerful provider-specific tools when the appropriate LLM is in use.
    *   **Readiness:** Feature Enhancement (Builds on Level 6).

*   **Phase 8: Aider Integration (MCP Approach)**
    *   **Status:** PENDING
    *   **Goal:** Add code editing capabilities using Aider via the MCP client/server model (as defined in **ADR 19**).
    *   **Prerequisites:** Functional external `Aider MCP Server`.
    *   **Components & Tasks:** `AiderBridge`, `AiderExecutorFunctions`, `BaseHandler`.
        1.  Document Aider MCP Server setup requirement.
        2.  Refactor `AiderBridge` into an MCP Client (using `pydantic-ai`'s `MCPClient` or `mcp.py`), implementing methods to send requests to the server. Remove direct Aider calls.
        3.  Update `AiderExecutorFunctions` (`execute_aider_automatic`, `execute_aider_interactive`) to use the refactored `AiderBridge` (MCP Client).
        4.  Register `aider:automatic` and `aider:interactive` tools with `BaseHandler` using the updated executors.
    *   **Integration:** Connects to external Aider MCP Server. Invoked via standard tool mechanism.
    *   **Testing:** Integration tests for `AiderBridge` (mocking MCP server), executor functions. E2E requires running server.
    *   **Documentation:** Deprecate old Aider IDLs, update bridge/executor IDLs to reflect MCP client role. Reference **ADR 19**.
    *   **Outcome:** System gains code editing features via Aider/MCP. **Completes Feature Readiness Level 5.**
    *   **Readiness:** Advanced Feature Enabled (Builds on Level 6+7).

*   **Phase 9: `lambda` Special Form**
    *   **Status:** PENDING
    *   **Goal:** Add anonymous functions with lexical scoping (closures) to the DSL.
    *   **Components & Tasks:** `SexpEvaluator`, `SexpEnvironment`, New `Closure` class. Implement `lambda` special form, `Closure` class, function application logic (`_apply_closure`) in `SexpEvaluator`. Add extensive tests.
    *   **Integration:** Deep changes within `SexpEvaluator` and `SexpEnvironment`.
    *   **Outcome:** DSL gains significant expressive power with first-class functions and lexical scoping.
    *   **Readiness:** Core Language Enhancement (Builds on previous phases).

*   **Phase 10: Documentation Alignment & Final Review**
    *   **Status:** PENDING
    *   **Goal:** Ensure all documentation is up-to-date, consistent, and accurate. Perform final code review.
    *   **Tasks:** Update all relevant IDLs, READMEs, guides (`start_here.md`, `implementation_rules.md`), ADRs (including ensuring **ADR 19** is finalized). Add usage examples for S-expressions, Aider, Lambda, etc. Final linting, formatting, testing, and review.
    *   **Outcome:** Project is polished, well-documented, and ready for release or further development cycles.

