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

*   **Phase 7:** Code Editing Integration (Aider/MCP/Other) - **PENDING (DEFERRED)**
    *   **Goal:** Add code editing capabilities.
    *   **Tasks:** Based on the chosen approach (Direct Aider, MCP Client+Server, etc.):
        *   Implement necessary bridge/client components.
        *   Implement corresponding executor functions.
        *   Integrate with `Application` (instantiation, tool registration).
        *   Write tests (likely heavy mocking).
    *   **Outcome:** System gains code editing functionality, completing Feature Readiness Level 5.

*   **Phase 8:** Documentation Alignment & Final Review - **PENDING** (Renumbered from Phase 6)
    *   **Goal:** Ensure all documentation matches the final implementation. Perform final code review and cleanup.
    *   **Tasks:** Update IDLs, guides, examples. Final linting/formatting. Review.
    *   **Outcome:** Project is well-documented, consistent, and ready.

