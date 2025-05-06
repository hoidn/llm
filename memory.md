<description>Developer's working memory log for tracking current task, progress, next steps, and context.</description>
# Developer Working Memory

## Current Task/Focus (As of: 2025-05-01)

**Goal:** Phase 9: System Tool Implementation & Refinement.

**Current Sub-task:** Phase 9.3: Implement Multi-LLM Routing/Execution.

**Relevant Files:**
- `src/handler/llm_interaction_manager.py`
- `src/handler/llm_interaction_manager_IDL.md`
- `src/handler/base_handler.py`
- `src/handler/base_handler_IDL.md`
- `tests/handler/test_llm_interaction_manager.py`
- `tests/handler/test_base_handler.py`
- `src/main.py` (For config structure context)
- `docs/implementation_rules.md`
- `docs/system/contracts/types.md`

**Related IDLs:**
- `src/handler/llm_interaction_manager_IDL.md`
- `src/handler/base_handler_IDL.md`

## Recent Activity Log

- **(Previous) Implementation of core components:** Created basic structures for `MemorySystem`, `TaskSystem`, `BaseHandler`.
- **(Previous) Implementation of non-deferred methods:** Implemented non-deferred methods in core components.
- **(Previous) Test implementation:** Created tests for non-deferred methods.
- **(Previous) Bug fix:** Fixed `TaskSystem.find_template` name collision issue.
- **Refactoring `BaseHandler` (Part 1):** Extracted file context logic to `FileContextManager`. Commit `03e2338`.
- **Refactoring `BaseHandler` (Part 2):** Extracted LLM interaction logic to `LLMInteractionManager`. Commit `5a785c8`.
- **Reflection & Guide:** Created `docs/refactor.md`.
- **Implement MemorySystem Context Retrieval (Phase 2a):** Added logic to `MemorySystem.get_relevant_context_for` and `get_relevant_context_with_description`. Commit `f37c09e`.
- **Fix MemorySystem Tests (Part 1 & 2):** Corrected assertions, removed obsolete tests, removed `NotImplementedError`. Commits `841d680`, `a3e5032`.
- **Start Phase 3 Implementation:** Implemented `AtomicTaskExecutor`, `SexpEnvironment`, `SexpEvaluator`, `PassthroughHandler` logic and tests. Adhered to IDLs and Unified ADR mandates. (Assumed completed based on previous state).
- **Phase 4 - Stream 1: Git Indexer Implementation:** Implemented `GitRepositoryIndexer` and related `MemorySystem` method. Added tests, refactored tests to use integration approach with `git_repo` fixture. Commits `8119e2a`, `c8604ad`.
- **Phase 4 - Stream 2: Implement System Executors:** Implemented `SystemExecutorFunctions` and tests. Fixed test failures. Commits `5f9a56e`, `cfeff54`, `d61b395`.
- **Phase 5: Implement `defatom` Special Form:** Added `_eval_defatom` to `SexpEvaluator`, updated IDL, added tests. Fixed dispatch logic and test assertions. Commits `4fc75ac`, `bd304a5`, `47c3d1a`.
- **Phase 6: Fix Dispatcher Tests:** Iteratively fixed failures in `tests/test_dispatcher.py`. Commits `30ef927`, `8db23da`, `022ff9b`, `3362198`, `19403d9`.
- **Phase 6: Fix `file_contents` Substitution:** Simplified placeholder in `src/main.py`. Updated docs. Commits `ca0c431`, `8699af2`.
- **Phase 6: Fix `phase6.py` Script:** Corrected `sys.path` and `REPO_TO_INDEX`. Commits `f5d5d9e`, `dd11e79`.
- **Phase 6: Clarify Indexing Documentation:** Updated IDLs regarding `repo_path` and `include_patterns`.
- **Phase 3b: Implemented Pydantic-AI Integration for Structured Output:** Added `resolve_model_class`, updated `LLMInteractionManager`, `AtomicTaskExecutor`, `BaseHandler`. Added tests and updated docs.
- **Phase 3b: Added Provider Identifier Support:** Added `get_provider_identifier` methods and tests.
- **Phase 7: Implement Anthropic Editor Tools:** Created `src/tools/anthropic_tools.py`. Added conditional registration logic in `src/main.py`. Added unit and integration tests. Commit `0c0e827`.
- **Phase 7: Fix Tests:** Addressed failures in `test_main.py` (abspath, tool count) and `test_anthropic_tools.py` (newline, resolve_path, assertion). Addressed deprecation warnings in `test_base_handler.py`. Commit `2e4a11b`.
- **Phase 7: Fix Handler Tool Logic:** Corrected `BaseHandler._execute_llm_call` to pass executors/definitions correctly based on precedence. Fixed related tests in `test_base_handler.py`. Commit `0bc2f51`.
- **Phase 7: Documentation Update (Cycle 1):** Updated IDLs (`main`, `base_handler`, `llm_interaction_manager`), core guides (`start_here`, `implementation_rules`), and library docs (`pydanticai`, `pydanticai_details`, `MCP_TOOL_GUIDE`). Updated `memory.md`.
- **Phase 7: Documentation Update (Cycle 2):** Performed final review and refinement of documentation related to tool handling logic (`llm_interaction_manager_IDL.md`, `implementation_rules.md`, `start_here.md`, `pydanticai.md`, `pydanticai_details.md`). Updated `memory.md`.
- **Phase 7: Documentation Update (Cycle 3):** Reviewed `atomic_executor_IDL.md` and `phase6.py`. Confirmed consistency with recent changes. Updated `memory.md`.
- **Phase 9.2: Implement Shell Execution Tool:** Added `execute_shell_command` instance method to `SystemExecutorFunctions`. Updated IDL. Registered tool in `Application._register_system_tools`. Added tests in `test_system_executors.py`. Updated `test_main.py` to verify registration. Updated `memory.md`.
- **Phase 9.3: Implement Multi-LLM Routing/Execution:** Added `model_override` parameter to `LLMInteractionManager.execute_call` and `BaseHandler._execute_llm_call`. Implemented logic in `LLMInteractionManager` to handle override by looking up config and instantiating a temporary `pydantic-ai Agent`. Updated relevant IDLs. Updated `memory.md`. (This commit).

## Next Steps

1.  **Phase 9.3 Testing:** Implement unit tests for `LLMInteractionManager` and `BaseHandler` to verify the `model_override` logic, including success and failure cases (config lookup, agent creation). Add optional integration test for Dispatcher.
2.  **Phase 8: Aider Integration:**
    *   Implement `AiderBridge` (likely as an MCP client or direct wrapper).
    *   Define Aider tool specifications (`src/aider_bridge/tools.py`).
    *   Implement Aider executor functions (`src/executors/aider_executors.py`).
    *   Add logic to `Application.initialize_aider` to register Aider tools conditionally or based on configuration.
    *   Update `Application._determine_active_tools` if needed.
    *   Add integration tests for Aider workflows.
3.  **Merge Streams:** Ensure all Phase 4-9 changes are integrated cleanly.
4.  **Implement Remaining Deferred Methods (Phase 2 Dependencies):**
    *   Review and finalize implementations for:
        *   `TaskSystem`: `execute_atomic_template`, find/generate/resolve methods.
        *   `MemorySystem`: `get_relevant_context_for` (sharding/mediation logic).
        *   Other deferred methods.
5.  **Write Tests for Deferred Methods:** Add tests for the methods implemented in step 4.
6.  **Integration Testing:** Enhance integration tests covering workflows involving SexpEvaluator -> TaskSystem -> AtomicTaskExecutor -> Handler -> LLMManager and MemorySystem indexing/retrieval. Ensure integration tests cover key scenarios previously handled by removed unit tests where appropriate.
7.  **Review Tool Registration & Execution:** Finalize how tools registered in `BaseHandler` are made available during `SexpEvaluator` execution (via `Handler._execute_tool`) and LLM calls.
8.  **Update Documentation:** Ensure IDLs, rules, and diagrams reflect the fully implemented state after Phase 8.

## Notes & Context

- Phase 9.3 successfully added the `model_override` parameter and the core logic for handling it in `LLMInteractionManager`.
- The implementation assumes a configuration structure like `config['llm_providers'][model_id]` for override details.
- Error handling for missing configuration and temporary agent initialization failures has been added.
- The temporary agent reuses tools from the default agent.
- IDLs have been updated to reflect the new parameter.
- Next step is to write tests for this new functionality.
