**Full Revised Implementation Plan (with `defatom`)**

**Overall Goal:** Build a system capable of orchestrating LLM interactions, external tools, and file system operations via an S-expression DSL, with features for context management, Git indexing, and Aider integration.

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

*   **Phase 4:** Specialized Features (Indexers, Aider, System Tools) - **PENDING (NEXT)**
    *   **Goal:** Implement integrations with Git, Aider, and add specific system-level tools.
    *   **Components:**
        *   `GitRepositoryIndexer`: Implement class based on IDL, including scanning, metadata creation (using `text_extraction` helpers and Git library/CLI), and calling `memory_system.update_global_index`.
        *   `MemorySystem.index_git_repository`: Implement method to use the indexer.
        *   `AiderBridge`, `AiderAutomaticHandler`, `AiderInteractiveSession`: Implement classes based on IDLs, handling Aider availability check, context management, and interaction with Aider library/CLI (requires careful design, likely involving subprocess management or Aider's Python API if available).
        *   `SystemExecutorFunctions`: Implement `execute_get_context` (using `MemorySystem`) and `execute_read_files` (using `FileAccessManager`) based on IDL.
        *   `AiderExecutorFunctions`: Implement `execute_aider_automatic` and `execute_aider_interactive` (wrapping `AiderBridge` calls) based on IDL.
    *   **Integration:** Ensure `Application` (in Phase 6) will register System and Aider tools/executors with the `PassthroughHandler`.
    *   **Testing:** Requires significant mocking for external dependencies (Git, Aider).
    *   **Outcome:** System gains advanced capabilities for interacting with Git repos, performing code edits via Aider, and using specific system utilities within workflows. **Achieves Feature Readiness Level 5.**

*   **Phase 5:** Implement `defatom` Special Form - **PENDING**
    *   **Goal:** Enhance the S-expression DSL to allow inline definition of simple atomic tasks.
    *   **Components:** `SexpEvaluator`.
    *   **Tasks:**
        1.  Modify `SexpEvaluator._eval_list`: Add `defatom` to the `special_forms` set.
        2.  Modify `SexpEvaluator._eval_special_form`: Implement the logic for `defatom` as specified in the ADR:
            *   Parse task name symbol, params list, instructions string, optional description/subtype.
            *   Validate the inputs.
            *   Construct the atomic task template dictionary.
            *   Call `self.task_system.register_template()` with the dictionary.
            *   **(Recommended):** Bind the task name symbol in the current lexical environment (`env.define(...)`) to a callable wrapper that invokes `task_system.execute_atomic_template`.
            *   Return the task name symbol.
        3.  Write Unit Tests: Create new tests in `tests/sexp_evaluator/test_sexp_evaluator.py` specifically for `defatom`, covering:
            *   Successful definition and registration.
            *   Correct handling of optional description/subtype.
            *   Invocation of a task defined via `defatom` (both via lexical binding and global lookup if applicable).
            *   Error handling for incorrect `defatom` syntax.
    *   **Outcome:** Users can define simple atomic LLM tasks directly within S-expression workflows, improving encapsulation and prototyping speed. DSL expressiveness increased.

*   **Phase 6:** Top-Level Integration & Dispatching (`Dispatcher`, `Application`) - **PENDING**
    *   **Goal:** Create the main application entry point and the dispatcher for `/task` commands.
    *   **Components:** `Dispatcher` (`src/dispatcher.py`), `Application` (`src/main.py`).
    *   **Tasks:**
        *   Implement `DispatcherFunctions.execute_programmatic_task`: Handle parsing of identifier/params/flags, differentiate S-expressions vs direct calls, route S-expressions to `SexpEvaluator.evaluate_string`, route direct calls to `TaskSystem.execute_atomic_template` or `Handler._execute_tool`, format results/errors into `TaskResult`.
        *   Implement `Application`: `__init__` to instantiate and wire all core components (`MemorySystem`, `TaskSystem`, `Handler`, `AiderBridge` etc.), load configuration. Implement methods like `handle_query` (using `PassthroughHandler`), `index_repository` (using `MemorySystem`), potentially a method to handle `/task` commands via the `Dispatcher`. Implement helper methods for tool registration (`initialize_aider`, `_register_system_tools`).
    *   **Testing:** Requires integration tests covering the Dispatcher routing and Application lifecycle.
    *   **Outcome:** System functions as a cohesive whole, callable via the `Application` class. Programmatic task execution (`/task`) is enabled. **Achieves Feature Readiness Level 6.**

*   **Phase 7:** Documentation Alignment & Final Review - **PENDING**
    *   **Goal:** Ensure all documentation (IDLs, READMEs, guides) matches the final implementation. Perform final code review and cleanup.
    *   **Tasks:** Update IDLs, `start_here.md`, `implementation_rules.md`, potentially add usage examples. Final linting/formatting. Review for consistency.
    *   **Outcome:** Project is well-documented, consistent, and ready for use/further development.

