**Project Implementation Plan (Revised & Corrected - Retaining Detail)**

**Overall Goal:** Build a system capable of orchestrating LLM interactions, external tools (Git, Aider via MCP), and file system operations via an S-expression DSL, leveraging `pydantic-ai` for LLM calls and Pydantic for data modeling.

**Core Technologies/Patterns:**

*   S-expression DSL evaluated by `SexpEvaluator`.
*   Atomic tasks defined in XML/registered, managed by `TaskSystem`.
*   `pydantic-ai` library for all LLM interactions via `LLMInteractionManager` within `BaseHandler`.
*   Pydantic models for data structures and validation (`src/system.models`, `Parse, Don't Validate`).
*   Unified Tool Interface (`BaseHandler.register_tool`) for Direct Tools (sync, Handler-executed) and Subtask Tools (async, LLM-delegated).
*   Aider integration via an external **Aider MCP Server** and an internal **AiderBridge (MCP Client)**.

---

**Phase Breakdown:**

*   **Phase 0: Foundational Utilities & Interfaces**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Establish core building blocks, types, and contracts.
    *   **Components & Tasks:** Core utilities (`src.handler.file_access`, `src.handler.command_executor`), shared Pydantic models (`src.system.models`), base IDL definitions, `SexpParser`, `SexpEnvironment`.
    *   **Outcome:** Essential building blocks, Pydantic models, and contracts defined.
    *   **Readiness:** Level 0: Foundational Code.

*   **Phase 1A: Mechanical IDL-to-Python Skeleton Creation**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Create basic Python code structure from IDLs.
    *   **Components & Tasks:** Empty Python class/module files matching IDLs with `__init__` and method stubs.
    *   **Outcome:** Code structure established.
    *   **Readiness:** Level 0: Foundational Code.

*   **Phase 1B: Core Component Basic Logic**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Implement basic initialization, state, and dependency injection.
    *   **Components & Tasks:** `MemorySystem`, `BaseHandler`, `TaskSystem` (`__init__`, basic state, dependency injection setup), `LLMInteractionManager`, `FileContextManager` (instantiated within `BaseHandler`), simple registration methods (`register_tool`, `register_template` basic storage).
    *   **Outcome:** Core components are instantiable and manage basic state.
    *   **Readiness:** Level 1: Core Systems Bootstrapped (Start).

*   **Phase 2a: Refine `MemorySystem` Logic**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Implement core memory storage and retrieval.
    *   **Components & Tasks:** `MemorySystem` (`update_global_index`, basic `get_relevant_context_for` implementation, sharding config).
    *   **Outcome:** Memory system can store metadata and perform context lookups.
    *   **Readiness:** Level 1: Core Systems Bootstrapped (+).

*   **Phase 2b: Refine `BaseHandler` & `LLMInteractionManager` Logic**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Enable LLM interaction and direct tool execution.
    *   **Components & Tasks:** `BaseHandler` (`_execute_llm_call` via `LLMInteractionManager`, `_build_system_prompt`, `_execute_tool`, `execute_file_path_command`), `LLMInteractionManager` (`execute_call` using `pydantic-ai`), `FileContextManager` (`get_relevant_files`, `create_file_context`).
    *   **Outcome:** System can interact with LLMs via `pydantic-ai` and execute directly registered tools.
    *   **Readiness:** Level 1: Core Systems Bootstrapped (++).

*   **Phase 2c: Refine `TaskSystem` Logic (Orchestration) & Fix Tests + Refactoring**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Implement atomic task orchestration logic and ensure core components interact correctly.
    *   **Components & Tasks:** `TaskSystem` (template finding, file path resolution via `file_path_resolver`, context mediation via `generate_context_for_memory_system`, context setting validation/merging, `execute_atomic_template` core logic), `TemplateRegistry`. Refactoring completed.
    *   **Outcome:** TaskSystem can manage templates and orchestrate atomic task execution preparation; core components are robust.
    *   **Readiness:** Level 1: Core Systems Bootstrapped (Done).

*   **Phase 3: Implement Executors & Higher-Level Handlers**
    *   **Status:** DONE & VERIFIED
    *   **Goal:** Enable execution of atomic tasks and S-expression workflows; provide basic user interaction.
    *   **Components & Tasks:** `AtomicTaskExecutor` (executes template bodies based on `params`), `SexpEvaluator` (parses/runs S-expressions, implements `if`/`let`/`bind`/`quote`/`list`/`get_context`, handles task/tool invocation), `PassthroughHandler` (handles chat query, calls `_get_relevant_files`, `_create_file_context`, `_execute_llm_call`, registers `executeFilePathCommand` tool).
    *   **Outcome:** System can execute atomic tasks and complex S-expression workflows; basic user interaction via PassthroughHandler is possible.
    *   **Readiness:** Levels 2, 3, 4: Execution & Basic UI Ready.

*   **Phase 3b: Structured Output Implementation (Pydantic-AI)**
    *   **Status:** IMPLEMENTED
    *   **Goal:** Implement reliable structured output (e.g., JSON parsed into Pydantic models) for atomic tasks using `pydantic-ai`'s capabilities, as per `ADR_pydantic_output.md`.
    *   **Components & Tasks:**
        1.  **Schema-to-Model Mapping:** Implement `resolve_model_class` helper function.
        2.  **`AtomicTaskExecutor` Update:** Modify `execute_body` to detect schema, use `resolve_model_class`, pass `output_type_override` to `handler._execute_llm_call`, and place result in `TaskResult.parsedContent`.
        3.  **`BaseHandler`/`LLMInteractionManager` Update:** Modify `_execute_llm_call` and `execute_call` to accept and pass `output_type_override` to `pydantic-ai` `agent.run_sync()`.
        4.  **Result Handling Update:** Ensure `LLMInteractionManager` returns the parsed Pydantic instance from `agent.run_sync()`.
    *   **Integration:** Requires changes in `AtomicTaskExecutor`, `BaseHandler`, `LLMInteractionManager`. Relies on Pydantic models. May simplify callers.
    *   **Testing:** Add tests verifying `output_type_override` passing, `pydantic-ai` parsing/validation, `TaskResult.parsedContent` population, and error handling.
    *   **Outcome:** Atomic tasks requiring structured output leverage `pydantic-ai`'s robust mechanisms, increasing reliability and simplifying validation logic.
    *   **Readiness:** Core Feature Enhancement (Builds on Phase 3).

*   **Phase 4: Specialized Features (Indexers & System Tools)**
    *   **Status:** PARTIALLY IMPLEMENTED (Core logic done, text_extraction is placeholder)
    *   **Goal:** Implement integration with Git for indexing and add specific system-level tools callable from S-expressions. Implement generic model-agnostic tools.
    *   **Components & Tasks:**
        1.  **`GitRepositoryIndexer` (`src/memory/indexers/git_repository_indexer.py`):** Implement class based on IDL. Requires `GitPython`. Implement scanning, metadata creation (using **placeholder** `text_extraction` helpers and GitPython), and calling `memory_system.update_global_index`.
        2.  **`MemorySystem.index_git_repository` (`src/memory/memory_system.py`):** Implement method to use the indexer.
        3.  **`SystemExecutorFunctions` (`src/executors/system_executors.py`):** Implement `execute_get_context` (using `MemorySystem`) and `execute_read_files` (using `FileAccessManager`) based on IDL.
        4.  **(Optional) Implement other generic File/Bash Tools:** (Not implemented yet).
        5.  **Testing:** Write unit/integration tests for indexer and implemented system tools. Requires mocking for Git interaction.
    *   **Integration:** `Application` (Phase 6) registers the implemented System tools with the `PassthroughHandler`.
    *   **Outcome:** System gains Git indexing and core system tools (`get_context`, `read_files`) accessible via S-expressions or LLM calls.
    *   **Readiness:** Partial Level 5: Advanced Features Enabled (Git indexing and core system tools available, text extraction placeholders).

*   **Phase 5: `defatom` Special Form**
    *   **Status:** IMPLEMENTED
    *   **Goal:** Enhance the S-expression DSL to allow inline definition of simple atomic tasks via global registration.
    *   **Components & Tasks:** `SexpEvaluator` (`_eval_defatom` logic and tests).
    *   **Outcome:** DSL usability improved; simple LLM tasks can be defined inline within workflows.
    *   **Readiness:** DSL Enhancement (Builds on Phase 4).

*   **Phase 6: Top-Level Integration & Dispatching (`Dispatcher`, `Application`)**
    *   **Status:** IMPLEMENTED
    *   **Goal:** Create the main application entry point and the dispatcher for `/task` commands, wiring all components together.
    *   **Components & Tasks:** `Dispatcher` (`DispatcherFunctions.execute_programmatic_task`), `Application` (`__init__` wiring components, `handle_query`, `index_repository`, `handle_task_command` using Dispatcher). Implement helper `_register_system_tools` to register generic tools from Phase 4.
    *   **Testing:** Integration tests for Dispatcher routing logic and basic `Application` functionality.
    *   **Outcome:** System functions as a cohesive unit, accessible via `Application` methods and the `/task` dispatcher.
    *   **Readiness:** Level 6: Fully Integrated System (Initial).

*   **Phase 7: Provider-Specific Tool Integration (e.g., Anthropic Editor)**
    *   **Status:** **IMPLEMENTED** *(Updated)*
    *   **Goal:** Implement and conditionally register tools specific to certain LLM providers (e.g., Anthropic Editor tools), making them available to the `pydantic-ai` agent only when the corresponding provider is active.
    *   **Components & Tasks:** Implemented provider-specific tool logic (`src/tools/anthropic_tools.py`), defined tool specifications, implemented conditional registration in `Application`, updated `BaseHandler` (`set_active_tool_definitions`, `get_tools_for_agent`), updated `LLMInteractionManager` (`initialize_agent`, `execute_call` handling), added unit and integration tests.
    *   **Integration:** Leverages `pydantic-ai`'s handling of provider-specific tool schemas. Agent initialized with the correct toolset based on provider.
    *   **Testing:** Tested conditional registration and tool availability based on provider configuration.
    *   **Outcome:** System can leverage powerful provider-specific tools when the appropriate LLM is in use.
    *   **Readiness:** Feature Enhancement (Builds on Level 6 & Phase 3b).

*   **Phase 8: Aider Integration (MCP Approach)**
    *   **Status:** DONE
    *   **Goal:** Add code editing capabilities using Aider via the MCP client/server model (as defined in ADR 19).
    *   **Prerequisites:** Functional external `Aider MCP Server`.
    *   **Components & Tasks:** Documented Aider MCP Server setup requirement. Refactored `AiderBridge` into an MCP Client. Updated `AiderExecutorFunctions` to use the MCP Client. Registered `aider:automatic` and `aider:interactive` tools with `BaseHandler`.
    *   **Integration:** Connects to external Aider MCP Server. Invoked via standard tool mechanism.
    *   **Testing:** Integration tests for `AiderBridge` (mocking MCP server), executor functions. E2E requires running server.
    *   **Documentation:** Deprecated old Aider IDLs, updated bridge/executor IDLs to reflect MCP client role. Referenced ADR 19.
    *   **Outcome:** System gains code editing features via Aider/MCP. **Completes Feature Readiness Level 5.**
    *   **Readiness:** Advanced Feature Enabled (Builds on Level 6, Phase 7).

*   **Phase 9: Core Agentic Tooling & Multi-LLM Support**
    *   **Status:** **PARTIALLY IMPLEMENTED / PENDING** *(Updated)*
    *   **Goal:** Enhance the system's ability to act as an agent by providing essential generic file system tools, **shell execution**, and enabling flexible LLM selection.
    *   **Components & Tasks:**
        1.  **Generic File System Tools:** Implement `system:write_file`, `system:list_directory`. Register them. (PENDING)
        2.  **Shell Execution Tool:** Implement `system:execute_shell_command` using `command_executor.py`. Register it. (PENDING - Critical for simplified workflow)
        3.  **Multi-LLM Routing/Execution:** Design and implement a mechanism to allow selecting or routing to different LLM providers/models during execution. Modify `BaseHandler`/`LLMInteractionManager`. Add tests. (PENDING - Critical for simplified workflow)
    *   **Integration:** Generic tools become available alongside provider-specific ones. Multi-LLM support enhances flexibility. Shell execution enables test running.
    *   **Testing:** Add unit/integration tests for new tools. Add tests verifying model selection/routing.
    *   **Outcome:** System gains essential generic file/shell tools and the flexibility to utilize different LLMs dynamically.
    *   **Readiness:** Enhanced Agent Capabilities & Flexibility (Partial).

*   **Phase 9b: DSL `loop` Primitive** *(NEW PHASE)*
    *   **Status:** **PENDING / NEW REQUIREMENT**
    *   **Goal:** Add a dedicated `(loop <count-expr> <body-expr>)` special form to the S-expression DSL to support fixed iterations, enabling the simplified iterative workflow.
    *   **Components & Tasks:** Modify `SexpEvaluator` to recognize and implement the `loop` special form logic (evaluate count, repeat body evaluation). Update `SexpEvaluator_IDL.md`. Add unit tests.
    *   **Rationale:** Prioritized over `lambda` to directly support the simplified iterative workflow.
    *   **Integration:** Enhances the DSL's control flow capabilities.
    *   **Testing:** Add unit tests verifying loop execution, count evaluation, body evaluation, and return value.
    *   **Outcome:** DSL supports basic fixed looping constructs.
    *   **Readiness:** Core Language Enhancement (Enabler for simplified workflow).

*   **Phase 10: S-expression `lambda` and Closures**
    *   **Status:** **PENDING (Lower Priority)** *(Updated Priority)*
    *   **Goal:** Implement anonymous functions with lexical scoping (closures) in the S-expression DSL, as per `ADR_lambdas.md`.
    *   **Components & Tasks:** `SexpEvaluator`, `SexpEnvironment`, New `Closure` class.
        1.  Implement the `lambda` special form parsing/handling in `_eval_list`.
        2.  Define the internal `Closure` object (params, body AST, definition environment).
        3.  Modify `_eval_list` (or `_handle_invocation`) to detect `Closure` operators.
        4.  Implement function application logic (new frame, link environment, bind args, eval body).
        5.  Write extensive unit tests covering closure creation, lexical scope, argument binding, recursion.
        6.  Update `SexpEvaluator_IDL.md`, `SexpEnvironment_IDL.md`, and DSL documentation.
    *   **Priority Note:** While valuable long-term, this is now lower priority than the `loop` primitive (Phase 9b) for enabling the immediate target workflow.
    *   **Integration:** Deep changes within `SexpEvaluator` and `SexpEnvironment`.
    *   **Outcome:** DSL gains first-class functions and lexical scoping, dramatically increasing its expressive power.
    *   **Readiness:** Core Language Enhancement.

    **Phase 10b: DSL Primitives for Feedback Loop and Data Manipulation**

    *   **Status:** **PARTIALLY IMPLEMENTED (Placeholders for Demo)**
    *   **Goal:** Enhance the S-expression DSL with necessary primitives for data structure access, comparison, and potentially state updates, enabling the full expression of conditional feedback loops (like the Aider retry loop) within the DSL itself. This phase complements Phase 10 (`lambda`) and Phase 9b (`loop`).
    *   **Prerequisites:** Phase 10 (`lambda` and closures) implemented. Existing `if` special form.
    *   **Components & Tasks:**
        1.  **`SexpEvaluator`: Implement Data Access Primitives:**
            *   **Primitive:** `(get-field <object-or-dict> <field-name-string-or-symbol>)` or `(access <object-or-dict> <field-name-string-or-symbol>)`
                *   **Status:** Placeholder implemented for demo script `lambda_llm_code_processing_demo.py`.
                *   **Behavior:** If `<object-or-dict>` is a dictionary, return the value associated with `<field-name-string-or-symbol>` (after evaluating it if it's a symbol representing a string key). If `<object-or-dict>` is a Pydantic model instance (or other custom object recognized by the evaluator), attempt to get an attribute with that name.
                *   **Error Handling:** Raise `SexpEvaluationError` if the field/attribute doesn't exist or if the first argument is not a suitable type.
                *   **Example:** `(get-field feedback-result "status")`
            *   **Primitive (Optional but Recommended):** `(get-path <object-or-dict> <path-string-or-list-of-keys>)`
                *   **Behavior:** Accesses nested data. `<path-string-or-list-of-keys>` could be a dot-separated string like `"notes.error.reason"` or a list of keys `'(notes error reason)`.
                *   **Error Handling:** Raise `SexpEvaluationError` for invalid paths or types.

        2.  **`SexpEvaluator`: Implement Comparison Primitives:**
            *   **Primitive:** `(eq? <val1> <val2>)` or `(equal? <val1> <val2>)`
                *   **Behavior:** Performs general equality comparison between two evaluated S-expression values. Should handle numbers, strings, booleans, symbols (by name), and potentially lists (structural equality).
                *   **Returns:** `true` or `false`.
            *   **Primitive:** `(string=? <str1> <str2>)`
                *   **Status:** Placeholder implemented for demo script `lambda_llm_code_processing_demo.py`.
                *   **Behavior:** Performs case-sensitive string equality.
                *   **Returns:** `true` or `false`.
                *   **Error Handling:** Raise `SexpEvaluationError` if arguments are not strings.
            *   **Primitive:** `(null? <val>)` or `(nil? <val>)`
                *   **Behavior:** Checks if `<val>` evaluates to `None` (Python `None`) or potentially an empty list `[]` (if `nil` is treated as empty list).
                *   **Returns:** `true` or `false`.
            *   **Numeric Comparison Primitives (Optional, but useful):** `(> <n1> <n2>)`, `(< <n1> <n2>)`, `(>= <n1> <n2>)`, `(<= <n1> <n2>)`.

        3.  **`SexpEvaluator` & `SexpEnvironment`: Implement State Update Primitive (Rebinding):**
            *   **Primitive:** `(set! <symbol-name> <new-value-expr>)`
                *   **Behavior:** Evaluates `<new-value-expr>`. Finds `<symbol-name>` in the current environment or its parent scopes. Updates (rebinds) the existing variable in the scope where it was *first found* to the new value.
                *   **Error Handling:** Raise `SexpEvaluationError` if `<symbol-name>` is not already bound in any accessible scope (i.e., `set!` cannot define new variables, only update existing ones).
                *   **Returns:** The `<new-value-expr>`.
                *   **Environment Change:** `SexpEnvironment.set_value(name, value)` method would be needed, which searches up the parent chain to find and update the binding.
            *   **Alternative/Consideration:** Instead of `set!`, a more constrained approach might be to enhance `let` or introduce a new binding form that allows rebinding only within its lexical scope, to avoid widespread side effects. However, for direct feedback loop state management, `set!` is more idiomatic in Lisp-like languages.

        4.  **`SexpEvaluator`: Implement Basic Arithmetic (for retry counters):**
            *   **Primitive:** `(+ <num1> <num2> ...)`
            *   **Primitive:** `(- <num1> <num2>)`
            *   **Behavior:** Standard arithmetic operations.
            *   **Error Handling:** Raise `SexpEvaluationError` for non-numeric arguments.
        4.  **`SexpEvaluator`: Implement Utility Primitives (for Demo):**
            *   **Primitive:** `(log-message <expr1> ...)`
                *   **Status:** Placeholder implemented for demo script `lambda_llm_code_processing_demo.py`.
                *   **Behavior:** Evaluates arguments, converts to string, and logs them.

        5.  **Documentation & IDL Updates:**
            *   Update `src/sexp_evaluator/sexp_evaluator_IDL.md` to document all new primitives (`get-field`, `string=?`, `log-message`), their syntax, behavior, and error conditions.
            *   Update `src/sexp_evaluator/sexp_environment_IDL.md` if `set!` requires changes to the environment interface.
            *   Update DSL guides and examples to showcase usage of these new primitives, especially in the context of conditional loops and data handling.

        6.  **Testing:**
            *   Write comprehensive unit tests for each new primitive in `SexpEvaluator`, covering:
                *   Correct evaluation with valid inputs.
                *   Correct return types.
                *   Proper error handling for invalid inputs or conditions (e.g., `get-field` on non-dict/obj, `string=?` on non-strings, `set!` on unbound variable).
            *   Write integration tests demonstrating a complete feedback loop (like the Aider retry loop) implemented *entirely* using S-expressions, leveraging `lambda`, `if`, `set!`, `get-field`, `eq?`, etc. This test would mock the underlying `user:analyze-aider-result` and `aider:automatic` tasks to return controlled sequences of feedback.

    *   **Integration:**
        *   These primitives will be directly used within S-expressions passed to `SexpEvaluator.evaluate_string`.
        *   They significantly enhance the DSL's capability to inspect results from tasks and control workflow based on that data.
    *   **Outcome:** The S-expression DSL becomes self-sufficient for implementing the Aider-style feedback loop, including inspecting the `FeedbackResult` Pydantic model (as a dictionary), comparing its status, updating retry counters, and conditionally re-invoking tasks with new prompts. This reduces the reliance on Python orchestration for this specific loop pattern.
    *   **Readiness:** Advanced DSL Capabilities (Enables complex internal state management and data-driven control flow within S-expressions).


*   **Phase 11: Workflow State Management & Resumption (Interactive Mode)**
    *   **Status:** PENDING
    *   **Goal:** Enable workflows to be suspended, have their state persisted, and be resumed later, potentially after external input.
    *   **Components & Tasks:** This likely requires significant new components or major refactoring.
        1.  **Design State Representation:** Define how workflow state will be represented.
        2.  **Design Persistence Mechanism:** Choose and implement how state will be saved/loaded. Address serialization.
        3.  **Implement Suspend/Resume Points:** Define how workflows signal suspension. Modify evaluator/orchestrator.
        4.  **Develop Resumption Logic:** Create mechanisms to load state and resume workflow.
        5.  **Implement Error Handling & Recovery:** Address failures during suspended/resumed workflows.
        6.  Write comprehensive tests covering suspension, persistence, resumption, and error recovery.
    *   **Integration:** Major architectural addition. Deeply impacts workflow execution.
    *   **Outcome:** System supports long-running, interactive, and potentially recoverable workflows.
    *   **Readiness:** Advanced Agent Interactivity & Reliability.

*   **Phase 12: Final Documentation Alignment & Review**
    *   **Status:** PENDING
    *   **Goal:** Ensure all documentation (IDLs, guides, ADRs, examples) is fully updated, consistent, and accurate, reflecting all implemented features including `loop` primitive and Phase 7 completion. Perform final code review, testing, and potential release preparation.
    *   **Components & Tasks:** Project-wide documentation review and updates, final testing sweep, code cleanup, potentially creating release notes.
    *   **Integration:** N/A (Documentation phase).
    *   **Outcome:** Project is polished, comprehensively documented, and ready for its next lifecycle stage.
    *   **Readiness:** Final Polish & Release Readiness.
