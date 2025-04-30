**Project Implementation Plan (Revised)**

**Overall Goal:** Build a system capable of orchestrating LLM interactions, external tools (Git), and file system operations via an S-expression DSL, with features for context management, Git indexing, inline task definition (`defatom`), anonymous functions (`lambda`), and a top-level dispatcher. Code editing integration (Aider/MCP) is deferred.

**Phase Breakdown:**

*   **Phase 0: Foundational Utilities & Interfaces**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Establish core building blocks, types, and contracts.
    *   **Components:** Core utilities (`src.handler.file_access`, `src.handler.command_executor`), shared Pydantic models (`src.system.models`), base IDL definitions, `SexpParser`, `SexpEnvironment`.
    *   **Outcome:** Essential building blocks and contracts defined.
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

---
*   **Phase 4: Specialized Features (Indexers & System Tools)**
    *   **Status:** PENDING (NEXT)
    *   **Goal:** Implement integration with Git for indexing and add specific system-level tools callable from S-expressions. *(Aider integration deferred)*.
    *   **Components & Tasks:**
        1.  **`GitRepositoryIndexer` (`src/memory/indexers/git_repository_indexer.py`):** Implement class based on IDL. Requires `GitPython`. Implement file scanning (`scan_repository`), text file identification (`is_text_file`), metadata creation (`create_metadata` using GitPython and `text_extraction` helpers), and the main `index_repository` orchestration method.
        2.  **`MemorySystem.index_git_repository` (`src/memory/memory_system.py`):** Implement method to instantiate and run `GitRepositoryIndexer`, passing `self` and options.
        3.  **`SystemExecutorFunctions` (`src/executors/system_executors.py`):** Implement executor functions based on IDL:
            *   `execute_get_context`: Takes params dict and `MemorySystem` instance, calls `memory_system.get_relevant_context_for`, returns `TaskResult`.
            *   `execute_read_files`: Takes params dict and `FileAccessManager` instance, calls `file_manager.read_file` for paths, returns `TaskResult`.
        4.  **Testing:** Write unit tests for all new components/methods. Requires significant mocking for `GitPython`, `os` file operations, `glob`, `MemorySystem`, `FileAccessManager`.
    *   **Integration:** Note that `Application` (Phase 6) will need to register the system tools (`system:get_context`, `system:read_files`) with the `Handler`.
    *   **Outcome:** System gains Git indexing capability and useful system tools for workflows.
    *   **Readiness:** Partial Level 5: Advanced Features Enabled (Git indexing and system tools available).

*   **Phase 5: Implement `defatom` Special Form**
    *   **Status:** PENDING
    *   **Goal:** Enhance the S-expression DSL to allow inline definition of simple atomic tasks via global registration.
    *   **Components & Tasks:**
        1.  **`SexpEvaluator` (`src/sexp_evaluator/sexp_evaluator.py`):**
            *   Add `"defatom"` to the `special_forms` set in `_eval_list`.
            *   Implement `defatom` logic in `_eval_special_form` as per the ADR: parse name/params/instructions/etc., construct template dict, call `task_system.register_template()`, optionally bind name lexically via `env.define()` to a callable wrapper. Return task name symbol.
        2.  **Testing (`tests/sexp_evaluator/test_sexp_evaluator.py`):** Add new unit tests covering `defatom` syntax, registration, invocation (lexical and global), optional arguments, and error handling.
    *   **Integration:** Relies on `TaskSystem` for registration. The optional lexical binding interacts with `SexpEnvironment`.
    *   **Outcome:** DSL usability improved; simple LLM tasks can be defined inline within workflows.
    *   **Readiness:** DSL Enhancement (Builds on Level 4/5).

*   **Phase 6: Top-Level Integration & Dispatching (`Dispatcher`, `Application`)**
    *   **Status:** PENDING
    *   **Goal:** Create the main application entry point and the dispatcher for `/task` commands, wiring all components together.
    *   **Components & Tasks:**
        1.  **`DispatcherFunctions` (`src/dispatcher.py`):** Implement `execute_programmatic_task` based on IDL: parse input, check if S-expression (route to `SexpEvaluator`) or direct call (route to `TaskSystem` for atomic tasks or `Handler` for direct tools), handle results/errors, format into `TaskResult`.
        2.  **`Application` (`src/main.py`):** Implement class based on IDL:
            *   `__init__`: Instantiate `MemorySystem`, `TaskSystem`, `PassthroughHandler` (passing dependencies), potentially `MCPClientManager` if/when added. Load configuration.
            *   Implement helper methods `_register_system_tools` (registers `system:get_context`, `system:read_files` with handler) and potentially `_initialize_mcp` (if/when MCP is added). Call these helpers in `__init__`.
            *   Implement `handle_query` (delegates to `PassthroughHandler`).
            *   Implement `index_repository` (delegates to `MemorySystem`).
            *   Implement method to handle `/task` commands (uses `Dispatcher`).
        3.  **Testing:** Write integration tests for `Dispatcher` routing logic and basic `Application` functionality (component wiring, command handling).
    *   **Integration:** This phase ties all previously built components together.
    *   **Outcome:** System functions as a cohesive unit, accessible via `Application` methods and the `/task` dispatcher.
    *   **Readiness:** Level 6: Fully Integrated System (minus code editing).

*   **Phase 7: Implement `lambda` Special Form**
    *   **Status:** PENDING
    *   **Goal:** Add anonymous functions with lexical scoping (closures) to the DSL.
    *   **Components & Tasks:**
        1.  **`Closure` Class (`src/sexp_evaluator/closure.py` - New File):** Define class to store params, body AST, and captured definition environment.
        2.  **`SexpEvaluator` (`src/sexp_evaluator/sexp_evaluator.py`):**
            *   Add `"lambda"` to `special_forms`.
            *   Implement `lambda` logic in `_eval_special_form` to create and return `Closure` objects, capturing the current environment.
            *   Modify `_eval_list` dispatch logic to recognize evaluated `Closure` objects.
            *   Implement function application logic (e.g., in `_apply_closure` helper): evaluate call arguments, create new environment frame linked via parent to *captured* environment, bind params, evaluate body in new frame.
        3.  **Testing (`tests/sexp_evaluator/test_sexp_evaluator.py`):** Add extensive unit tests for closure creation, lexical scope behavior (capture, shadowing), argument binding, body evaluation, and errors.
    *   **Integration:** Deep changes within `SexpEvaluator` and its use of `SexpEnvironment`.
    *   **Outcome:** DSL gains significant expressive power with first-class functions and lexical scoping.
    *   **Readiness:** Core Language Enhancement (Builds on Level 6).

*   **Phase 8: Code Editing Integration (Aider/MCP/Other - Deferred)**
    *   **Status:** PENDING (DEFERRED)
    *   **Goal:** Add code editing capabilities using the chosen strategy (Direct Aider, MCP Client+Server, etc.).
    *   **Tasks:** Implement bridge/client components, executor functions, integrate with `Application` (configuration, registration), write tests (heavy mocking likely required).
    *   **Outcome:** System gains code editing features.
    *   **Readiness:** Completes Level 5 Feature Set.

*   **Phase 9: Documentation Alignment & Final Review**
    *   **Status:** PENDING
    *   **Goal:** Ensure all documentation is up-to-date, consistent, and accurate. Perform final code review.
    *   **Tasks:** Update all relevant IDLs, READMEs, `start_here.md`, `implementation_rules.md`, ADRs. Add usage examples. Final linting, formatting, and review.
    *   **Outcome:** Project is polished, well-documented, and ready for release or further development cycles.

