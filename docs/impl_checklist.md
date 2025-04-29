**IDL Implementation Readiness Checklist**

**Project:** [Your Project Name]
**IDL File(s) Reviewed:** _________________________

**Instructions:** For each IDL file defining interfaces, modules, or types intended for implementation, review against the following criteria. Mark each item as Yes (✅), No (❌), or N/A. Provide comments for any "No" answers, detailing the required changes or clarifications. An IDL is generally considered "implementation ready" when all applicable items are marked "Yes".

**I. Feature / User Story Coverage**

*   *(List the key features/user stories this IDL is intended to support. Examples below - **replace/add specific stories relevant to the IDL being reviewed**)*

| Feature/Story | Relevant Methods/Types | Sufficiently Specified? | Comments / Missing Details |
|---|---|---|---|
| **Ex: Execute single atomic task via S-expression:** `/task '(atomic_task_1 (input "simple_value") (config (quote (("key" "value") ("size" 10)))))'` | `SexpEvaluator.evaluate_string`, `TaskSystem.execute_subtask_directly`, `TaskSystem.find_template` (atomic), `Template Evaluator._eval` (atomic body) | ☐ ✅ ☐ ❌ ☐ N/A | _Example now shows passing literal list data using quote. Need clarity on how SexpEvaluator passes named args to TaskSystem._ |
| **Ex: Execute sequence via S-expression:** `/task '(let ((r1 (atomic_task_1 "input"))) (atomic_task_2 r1))'` | `SexpEvaluator._eval` (for `let` primitive), `TaskSystem.execute_atomic_template` (invoked by SexpEvaluator for `atomic_task_1`, `atomic_task_2`) | ☐ ✅ ☐ ❌ ☐ N/A | _e.g., `let`/`bind` primitive behavior needs full definition._ |
| **Ex: Map task over list via S-expression:** `/task '(map (atomic_task_1 item) (list "a" "b"))'` | `SexpEvaluator._eval` (for `map`, `list` primitives), `SexpEnvironment` (for `item` binding), `TaskSystem.execute_atomic_template` (invoked by SexpEvaluator) | ☐ ✅ ☐ ❌ ☐ N/A | _e.g., Details of nested environment creation/`map` behavior needed._ |
| **Ex: Dynamic context fetching in S-expression:** `/task '(t1 (files (get_context ...)))'` | `SexpEvaluator._eval` (for `get_context`), `MemorySystem.get_relevant_context_for`, Handling of `(files ...)` arg in SexpEvaluator invocation logic | ☐ ✅ ☐ ❌ ☐ N/A | _e.g., How does SexpEvaluator parse/pass the files list extracted from get_context?_ |
| **Ex: Execute Direct Tool via S-expression:** `/task '(system:run_script ...)'` | `SexpEvaluator._eval` (invocation logic), `BaseHandler.tool_executors` lookup | ☐ ✅ ☐ ❌ ☐ N/A | _e.g., Confirmed lookup path specified._ |
| **Ex: Define Atomic Task (XML):** LLM generates atomic task XML. | `system/contracts/protocols.md` (Schema), `TaskSystem.register_template` | ☐ ✅ ☐ ❌ ☐ N/A | _e.g., Schema clearly defines elements/attributes, **including mandatory 'params'**._ |
| **Ex: Handle S-expression Errors:** User provides invalid S-expression. | `SexpEvaluator.evaluate_string` (error handling), `Dispatcher.execute_programmatic_task` (error formatting) | ☐ ✅ ☐ ❌ ☐ N/A | _e.g., Need specific error types documented for SexpSyntaxError vs SexpEvaluationError._ |
| *(Add other relevant features/stories)* | | | |

**II. Interface Definition & Clarity (`interface ...`)**

| # | Criteria | Status | Comments / Required Changes |
|---|---|---|---|
| 2.1 | **Clear Name:** Is the interface name clear, concise, and accurately reflect its purpose (e.g., `MemorySystem`, `SexpEvaluator`)? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 2.2 | **Purpose Defined:** Is the overall purpose/responsibility of the interface clearly stated in the module or interface docstring/comment block? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 2.3 | **Dependencies Declared:** Are all significant dependencies (other modules/interfaces, external resources like Filesystem, Shell, Git, Aider) explicitly listed using `@depends_on` or `@depends_on_resource`? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 2.4 | **Inheritance Clear:** If the interface conceptually extends another (e.g., `PassthroughHandler extends BaseHandler`), is this clearly stated in comments? | ☐ ✅ ☐ ❌ ☐ N/A |  |

**III. Method / Function Signatures (`returnType methodName(...)`)**

| # | Criteria | Status | Comments / Required Changes |
|---|---|---|---|
| 3.1 | **Clear Method Names:** Are method names clear, using standard conventions (e.g., snake_case), and accurately describing the action performed? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 3.2 | **Accurate Return Types:** Is the return type specified using appropriate primitives (`string`, `int`, `boolean`, `list<T>`, `dict<K,V>`) or defined types (`TaskResult`, `object` representing another interface)? Is `optional` used correctly for potentially null/None returns? Is `union` used correctly? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 3.3 | **Accurate Parameter Types:** Are all parameters clearly named and typed using primitives, defined types, `optional`, or `union`? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 3.4 | **Complex Parameter Formats:** For complex dictionary/JSON parameters, is the expected structure clearly documented via `Expected JSON format: { ... }` comment? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 3.5 | **Preconditions Documented:** Are the necessary conditions required *before* calling the method clearly listed under "Preconditions"? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 3.6 | **Postconditions Documented:** Are the expected outcomes, state changes, or guarantees *after* successful method execution clearly listed under "Postconditions"? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 3.7 | **Behavior Described:** Is the core logic and sequence of actions performed by the method clearly described under "Behavior"? Does it mention interactions with dependencies? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 3.8 | **Error Conditions Declared:** Are potential error conditions and how they are signaled (e.g., raised exception type, specific return value like FAILED TaskResult) documented using `@raises_error` or within Behavior/Postconditions? Are errors related to pydantic-ai calls or manager interactions documented? | ☐ ✅ ☐ ❌ ☐ N/A |  |

**IV. Type Definitions (If applicable, e.g., in `types.md` or within module)**

| # | Criteria | Status | Comments / Required Changes |
|---|---|---|---|
| 4.1 | **Clear Type Names:** Are custom type names (e.g., `TaskResult`, `GlobalIndex`, `ContextGenerationInput`) clear and descriptive? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 4.2 | **Structure Defined:** Is the structure of custom types (e.g., fields within an interface/dictionary, elements of a list/tuple) clearly defined with types for each element? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 4.3 | **Consistency:** Are types used consistently across different IDL files where they are referenced? | ☐ ✅ ☐ ❌ ☐ N/A |  |

**V. Architectural Alignment**

| # | Criteria | Status | Comments / Required Changes |
|---|---|---|---|
| 5.1 | **Component Responsibilities:** Does the interface adhere to component responsibilities (e.g., MemorySystem no file I/O, Handler delegates, **`AtomicTaskExecutor` runs ONLY parameterized atomic bodies with no env access, `SexpEvaluator` handles ALL composition**)? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 5.2 | **Removed Composites (XML):** Does the IDL avoid defining or referencing **any** XML composite task types (e.g., `sequential`, `map`, `director_evaluator_loop`)? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 5.3 | **S-expression Role:** Does the IDL correctly reflect that workflow composition is handled **exclusively** by the S-expression DSL and its evaluator? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 5.4 | **Atomic Executor Isolation:** Does the `AtomicTaskExecutor` IDL behavior forbid implicit environment access and mandate use of only passed parameters? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 5.5 | **Task System Scope:** Does the `TaskSystem` IDL behavior restrict its scope to handling **only atomic** templates (registration, finding, execution triggering)? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 5.6 | **Dispatcher Routing:** Does the `Dispatcher` IDL routing logic correctly state lookups in `TaskSystem` are **only for atomic** templates? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 5.7 | **Tool Registration:** Does the Handler IDL reflect the unified `register_tool` approach? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 5.5 | **Data Handling:** Does the design encourage parsing into specific types (aligning with "Parse, Don't Validate") rather than passing raw dicts/lists widely? (Assessed via parameter types and JSON format comments). | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 5.6 | **IDL Versioning:** Is the interface version clearly marked (e.g., `[Interface:Memory:3.0]`) and consistent with related documentation? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 5.7 | **LLM Interaction:** Does the interface correctly use LLMInteractionManager and pydantic-ai for LLM interactions where applicable? | ☐ ✅ ☐ ❌ ☐ N/A |  |

**VI. Overall Readiness**

| # | Criteria | Status | Comments / Required Changes |
|---|---|---|---|
| 6.1 | **Completeness:** Does the IDL provide enough detail to implement the described functionality *for the targeted features/stories* without significant ambiguity? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 6.2 | **Consistency:** Is the terminology, naming, and style consistent within the file and with other project IDLs? | ☐ ✅ ☐ ❌ ☐ N/A |  |
| 6.3 | **Actionability:** Can a developer reasonably translate this IDL specification into Python code following the project's implementation rules? | ☐ ✅ ☐ ❌ ☐ N/A |  |

**Summary:**

*   **Feature Coverage Assessment:** ___________________________________________________________
    *(Summarize if the IDLs sufficiently cover the necessary interfaces/types/behaviors for the target features)*
*   **Overall Readiness:** ☐ Ready for Implementation / ☐ Needs Revision
*   **Key Issues / Blockers (if any):**
    *   ___________________________________________________________
    *   ___________________________________________________________
    *   ___________________________________________________________
*   **Next Steps:** ___________________________________________________________

