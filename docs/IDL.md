<idl>
**--- idl guidelines ---**

**i. overview & purpose**

these guidelines define a system for creating and understanding interface definition language (idl) specifications and their corresponding code implementations. the process is designed to be **bidirectional**:

1.  **idl-to-code:** use a defined idl as a comprehensive specification to generate compliant, high-quality code.
2.  **code-to-idl:** reduce existing code to its essential idl specification, abstracting away implementation details and presentation logic to reveal the core behavioral specification and functional contract. see <code to idl>.

the goal is a clear, language- and UI-agnostic **specification (SPEC)** that defines both the *what* (the functional contract and essential behavior) and separates it from the *how* (the specific implementation details within the code).

**ii. idl creation & structure guidelines**

*(these apply both when writing idl from scratch and when reducing code to idl)*

1.  **object oriented:** structure the idl using modules and interfaces to represent logical components and entities.
2.  **dependency declaration:**
    *   **purpose:** to explicitly declare dependencies required to fulfill the interface's contract. This clarifies coupling at the design level.
    *   **syntax:** use comment lines placed immediately before the `interface` definition.
        *   For dependencies on other IDL-defined interfaces/modules:
            `# @depends_on(idl_module_or_interface_name, ...)`
        *   For dependencies on abstract types of external resources or systems:
            `# @depends_on_resource(type="Database", purpose="Storing user profiles")`
            `# @depends_on_resource(type="MessageQueue", purpose="Processing background jobs")`
    *   **target:**
        *   `@depends_on`: Names must refer to other `module` or `interface` definitions within the IDL system.
        *   `@depends_on_resource`: `type` is an abstract category (e.g., "Database", "FileSystem", "ExternalAPI"), `purpose` is a brief description.
    *   **implication:** These declarations signal requirements for the implementation. `@depends_on` implies needing access to implementations of other IDL contracts. `@depends_on_resource` implies needing access to a specific *kind* of external system or resource, configured appropriately.

### Implementation Conformance

The IDL file serves as a **strict contract**. Implementations in Python (or other languages) MUST adhere precisely to all aspects defined in the IDL, including:

*   **Interfaces and Signatures:** Class names, method names, parameter names, parameter order, type hints (mapping IDL types to language equivalents), and return types must match exactly.
*   **Behavior:** The implemented logic must fulfill the functional description provided in the `Behavior:` block.
*   **Preconditions/Postconditions:** The implementation must respect documented `Preconditions:` and guarantee `Postconditions:` upon successful execution.
*   **Data Structures:** Implementations must correctly handle data structures as defined (e.g., via `Expected JSON format`, `struct` definitions, or linked type definitions), including required keys or fields. Internal validation logic within components must align with these IDL specifications.
*   **Error Conditions:** Documented `@raises_error` conditions must be handled, either by raising the specified (or a corresponding mapped) exception or by returning a failure status as defined by the project's [Error Handling Philosophy](./system/architecture/overview.md#error-handling-philosophy).
3.  **design patterns:** utilize (when creating idl) or identify (when reducing code) interfaces supporting established design patterns like factory, builder, and strategy where they clarify the design or improve flexibility. the idl defines the *contract* and potentially the *behavioral role* of these patterns.
4.  **complex parameters (json):**
    *   **preference for structure:** if the idl syntax supports defining custom structures/records/data classes, prefer them for complex data transfer to maximize type safety at the interface level.
    *   **json fallback:** where structured types are not feasible in idl or cross-language string simplicity is paramount, use a single json string parameter.
    *   **mandatory documentation:** *always* document the exact expected json format within the idl comment block (e.g., `// expected json format: { "key1": "type1", "key2": "type2" }`).
5.  **Defining Custom Data Structures (`struct`):**

*   **Purpose:** To explicitly define the structure of complex data types passed between components, improving clarity and mapping directly to implementation structures (like Pydantic models). Replaces reliance on generic `dict` types with comments for complex data.
*   **Syntax:** Use a `struct` block, typically within a `module` definition.

    ```idl
    struct StructName {
        field_name1: type; // e.g., string, int, boolean, list<AnotherStruct>, dict<string, int>
        field_name2: optional type; // Use 'optional' for fields that may be absent/null
        field_name3: union<type1, type2>; // Use 'union' if a field can be one of multiple types
        // ... other fields
        // Use snake_case for field names.
    }
    ```

*   **Placement Strategy:**
    *   **`docs/types.md`:** Define globally shared structures used across many modules (e.g., `TaskResult`, `ContextGenerationInput`) in this central file.
    *   **Module-Specific `*_IDL.md`:** Define structures primarily used by interfaces within a single module directly within that module's `*_IDL.md` file (usually near the top of the `module` block).

*   **Referencing:** Use the defined `StructName` as a type name in method parameters, return types, or within other `struct` definitions.

*   **Example:**

    ```idl
    // In docs/types.md (Conceptual Example)
    struct TaskResult {
        status: string; // e.g., "COMPLETE", "FAILED", "CONTINUATION"
        content: optional Any; // Or specific union type if known
        notes: optional dict<string, Any>;
        parsedContent: optional Any; // For auto-parsed results (e.g., JSON)
    }

    // In src/memory/memory_system_IDL.md
    module src.memory.memory_system {

        // Locally defined struct (Example updated to MatchItem)
        struct MatchItem {
             id: string;
             content: string;
             relevance_score: float; // Assuming float for IDL simplicity
             content_type: string;
             source_path: optional string;
             metadata: optional dict<string, Any>;
        }

        // Struct referencing another local struct
        struct AssociativeMatchResult {
             context_summary: string;
             matches: list<MatchItem>; // Updated to use MatchItem
             error: optional string;
        }

        // Interface using the defined structs
        interface MemorySystem {
             // Method returning a locally defined struct
             AssociativeMatchResult get_relevant_context_for(union<dict<string, Any>, ContextGenerationInput> input_data);

             // Method using a globally defined struct (TaskResult assumed defined in docs/types.md)
             // Note: Actual MemorySystem might not return TaskResult directly, this is just syntax example.
             // TaskResult some_memory_operation(string param);
        }
    }
    ```
*   **Dependency Note (Optional Convention):** If an interface relies heavily on a type defined in `docs/types.md`, you *may* add a comment like `# @depends_on_type(docs.types.TaskResult)` near the interface definition for extra clarity, but this is not strictly required.

6.  **clarity and behavioral specification:** the idl must clearly express the *purpose* and *complete expected behavior* of each interface and method. this is achieved through:
    *   Well-chosen names for interfaces, methods, and parameters.
    *   **Comprehensive documentation comments:** These are critical for the SPEC. They must detail:
        *   **Preconditions:** Necessary conditions before calling.
        *   **Postconditions:** Expected outcomes, return value guarantees, and significant state changes after successful execution.
        *   **Essential Algorithms/Logic:** A conceptual description of any core algorithms or business logic the method implements, sufficient to understand its behavior without seeing the code.
        *   **Conceptual State:** Description of key internal state variables managed by the interface (if any) and how methods affect them.
        *   **Error Conditions:** Use the `@raises_error` annotation (see below) for specific, named error conditions that are part of the contract.
        *   JSON format documentation if applicable.
7.  **completeness (behavioral specification):** the idl must represent the *complete behavioral specification* of the component's public interface and its essential, observable behavior.
7.  **error condition annotation:** Use a dedicated annotation to formally define specific, named error conditions that are part of the interface's contract.
    *   **syntax:** Use comment lines within the method's documentation block.
        `// @raises_error(condition="UniqueErrorCode", description="Explanation of when this error occurs.")`
    *   **purpose:** To standardize the reporting of specific failure modes beyond simple success/failure, making the contract more precise. `condition` should be a stable identifier.
    Note: While `@raises_error` documents potential exceptions, the project's [Error Handling Philosophy](./system/architecture/overview.md#error-handling-philosophy) prefers returning FAILED `TaskResult` objects for recoverable errors where feasible.
    Note: While `@raises_error` documents potential exceptions, the project's [Error Handling Philosophy](./system/architecture/overview.md#error-handling-philosophy) prefers returning FAILED `TaskResult` objects for recoverable errors where feasible.

**iii. code-to-idl reduction guidelines**

*(these specific rules apply only when generating an idl from existing code)*

1.  **goal: extract the contract:** the primary objective is to distill the code down to its public interface and functional guarantees, omitting all non-essential implementation details.
2.  **mapping:**
    *   public classes/modules generally map to idl `module` or `interface`.
    *   public methods/functions map to idl method definitions.
    *   method signatures (name, parameter types, return type) must be accurately reflected.
3.  **dependency identification:** identify dependencies on other components *that are also being defined via idl*. represent these using the **dependency declaration** syntax (`# @depends_on(...)`) described in section ii.2. exclude dependencies on third-party libraries or internal implementation details not represented by an interface in the idl.
4.  **documentation extraction:**
    *   infer **preconditions** from input validation, assertions, and documentation comments in the code.
    *   infer **postconditions** from return value guarantees, state changes described in documentation, or observable outcomes. Document these clearly.
    *   identify and document **invariants** – properties of the object's conceptual state that hold true between public method calls.
    *   extract descriptions of **essential algorithms or core logic** from code/comments and summarize them conceptually in the method documentation.
    *   identify **specific error conditions** raised or returned that represent contractual failure modes. Document these using the `@raises_error` annotation.
    *   if complex objects/dictionaries are passed, represent them using the **complex parameters (json)** guideline (ii.4) and document the format.
5.  **exclusion criteria:** the following elements **must be excluded** from the generated idl *structure* (interfaces, methods) as they are implementation details, presentation logic, or non-functional aspects. However, *essential behavioral aspects* derived from these (like core logic or error conditions) should be *described* in the IDL documentation comments or captured via annotations.
    *   **presentation logic:** any code related to graphical user interfaces (gui), text user interfaces (tui), web page rendering, console output formatting, or specific presentation frameworks.
    *   **internal implementation code:** the *code* for private methods, helper functions, specific algorithms, internal data structures. (Note: The *behavior* or *purpose* of essential algorithms or the *conceptual* nature of key internal state *should* be documented).
    *   **type enforcement/validation code:** the *internal logic* for validation. The *requirement* for valid input is a precondition. Specific validation failure *error conditions* might be documented with `@raises_error` if contractual.
    *   **non-functional code:** logging statements, metrics collection, performance monitoring, debugging utilities, internal comments explaining *how* the code works (vs. *what* it guarantees).
    *   **language/platform specifics:** boilerplate code, language-specific idioms, environment configuration loading, build system artifacts, specific library dependencies (unless they form part of public signatures or are abstracted via `@depends_on_resource`).
    *   **internal error handling mechanisms:** specific exception types thrown/caught internally, internal error reporting. Contractual, observable error conditions should be documented using `@raises_error`. Generic internal failures are not part of the IDL spec.
    *   dependencies on concrete libraries or modules *not* represented by an IDL interface or abstracted via `@depends_on_resource`.
    *   **Internal Helper Components:** Classes, functions, or modules created solely as internal implementation details to support a public interface defined in an IDL, and not intended for direct use by other independent components. The delegation of work to such helpers *should*, however, be documented in the `Behavior` section of the public interface's method(s) that use them.

**iv. idl template**

```idl
// == !! begin idl template !! ===
module genericsystemname {

    // optional: define shared data structures if idl syntax allows
    // optional: define shared data structures if idl syntax allows
    // struct shareddata { ... }

    // example interface demonstrating dependency declarations and annotations
    # @depends_on(anotherinterfacename, sharedmodulename) // Dependency on other IDL contracts
    # @depends_on_resource(type="KeyValueStore", purpose="Caching intermediate results") // Abstract resource dependency
    interface entityname {

        // action/method definition
        // preconditions:
        // - define necessary conditions before calling.
        // - parametername must be positive.
        // - (if using json param) expected json format: { "key1": "type1", ... }
        // postconditions:
        // - define expected outcomes and state changes after successful execution.
        // - returns the calculated result based on input.
        // - internal cache (conceptual state) may be updated.
        // behavior:
        // - describe essential algorithm/logic here, e.g., "Calculates result using the frobnitz algorithm."
        // - "If the result is found in the KeyValueStore cache, it's returned directly."
        // @raises_error(condition="InvalidInput", description="Raised if parametername is non-positive.")
        // @raises_error(condition="ResourceUnavailable", description="Raised if the KeyValueStore cannot be accessed.")
        returntype methodname(parametertype parametername);

        // additional methods...

        // invariants: (optional: define properties that always hold true for this entity's conceptual state)
        // - describe state invariants here, e.g., "Internal cache size never exceeds max limit."
    };

    // another entity or component that entityname might depend on
    interface anotherinterfacename {
        // ... methods ...
    };

    // could also be a module containing utility interfaces/functions that entityname might depend on
    module sharedmodulename {
        // ... interfaces or potentially functions if idl supports them ...
    }
};
// == !! end idl template !! ===
```

**v. code creation rules**

*(these apply when implementing code based on an idl)*

1.  **strict typing:** always use strict typing. avoid ambiguous or variant types.
2.  **primitive types focus (balanced):** prefer built-in primitive and standard collection types where they suffice. use well-defined data classes/structs for related data elements passed together. avoid "primitive obsession." match idl types precisely.
3.  **portability mandate:** write code intended for potential porting to java, go, javascript. use language-agnostic logic and avoid platform-specific dependencies or language features without clear equivalents.
4.  **minimize side effects:** strive for pure functions for data processing. clearly document all necessary side effects (state mutation, i/o, external calls) associated with methods defined in the idl, typically in the implementation's documentation, aligning with the idl's postconditions.
5.  **testability & dependency injection:** design for testability. use dependency injection, avoid tight coupling. ensure methods corresponding to idl definitions are unit-testable. pay attention to the `# @depends_on` declarations in the idl to identify required dependencies that should likely be injected.
6.  **documentation:** thoroughly document implementation details, especially nuances not obvious from the idl or code signature. link back to the idl contract being fulfilled.
7.  **contractual obligation:** the idl is a strict contract. implement *all* specified interfaces, methods, and constraints *precisely* as defined. do not add public methods or change signatures defined in the idl.

**vi. example**

*(the `tweets` example, modified to show dependency declaration)*

```idl
module socialmediaplatform {

    // assume these interfaces are defined elsewhere in the idl system
    // interface usermanagement { ... } // Manages user existence and validation
    // interface notificationqueue { ... } // Handles sending notifications

    # @depends_on(usermanagement) // Depends on the user management contract
    # @depends_on_resource(type="TweetStore", purpose="Persisting tweet, like, and retweet data") // Needs a data store
    # @depends_on_resource(type="NotificationService", purpose="Sending notifications on mentions/likes") // Needs a notification mechanism
    interface tweets {
        // preconditions:
        // - user referenced by userid in tweetjson exists (verified via usermanagement).
        // - tweet content is non-null and within allowable size limits (e.g., 280 chars).
        // expected json format: { "userid": "string", "content": "string" }
        // postconditions:
        // - a new tweet is created and persisted in the TweetStore.
        // - if content contains mentions (@username), a notification task may be queued via NotificationService.
        // behavior:
        // - validates input json structure.
        // - checks user existence via usermanagement.
        // - checks content length.
        // - persists tweet data to TweetStore.
        // - parses content for @mentions and potentially triggers notifications.
        // @raises_error(condition="InvalidTweetFormat", description="JSON format is incorrect.")
        // @raises_error(condition="UserNotFound", description="User specified in userid does not exist.")
        // @raises_error(condition="ContentTooLong", description="Tweet content exceeds the size limit.")
        // @raises_error(condition="StorageFailure", description="Failed to persist tweet to TweetStore.")
        void posttweet(string tweetjson);

        // preconditions:
        // - user referenced by userid exists (verified via usermanagement).
        // - tweet referenced by tweetid exists (verified via TweetStore lookup).
        // postconditions:
        // - the tweet with tweetid is marked as liked by userid in the TweetStore.
        // - a notification may be sent to the original tweet author via NotificationService.
        // behavior:
        // - validates user and tweet existence.
        // - updates like status in TweetStore.
        // - potentially triggers notification.
        // @raises_error(condition="UserNotFound", description="Liking user specified by userid does not exist.")
        // @raises_error(condition="TweetNotFound", description="Tweet specified by tweetid does not exist.")
        // @raises_error(condition="AlreadyLiked", description="User has already liked this tweet.")
        // @raises_error(condition="StorageFailure", description="Failed to update like status in TweetStore.")
        void liketweet(string userid, string tweetid);

        // preconditions:
        // - user referenced by userid in retweetjson exists (verified via usermanagement).
        // - original tweet referenced by originaltweetid in retweetjson exists (verified via TweetStore lookup).
        // expected json format: { "userid": "string", "originaltweetid": "string" }
        // postconditions:
        // - a new retweet linked to the original is created and persisted in the TweetStore.
        // behavior:
        // - validates input, user existence, and original tweet existence.
        // - creates and persists retweet data.
        // @raises_error(condition="InvalidRetweetFormat", description="JSON format is incorrect.")
        // @raises_error(condition="UserNotFound", description="Retweeting user does not exist.")
        // @raises_error(condition="TweetNotFound", description="Original tweet does not exist.")
        // @raises_error(condition="CannotRetweetOwn", description="User attempted to retweet their own tweet.")
        // @raises_error(condition="StorageFailure", description="Failed to persist retweet to TweetStore.")
        void retweet(string retweetjson);

        // preconditions:
        // - tweet referenced by tweetid exists (verified via TweetStore lookup).
        // postconditions:
        // - returns the details of the tweet (content, author, stats) as a json string.
        // behavior:
        // - retrieves tweet data from TweetStore.
        // - formats data into the specified JSON structure.
        // @raises_error(condition="TweetNotFound", description="Tweet specified by tweetid does not exist.")
        // @raises_error(condition="StorageFailure", description="Failed to retrieve tweet details from TweetStore.")
        string gettweetdetails(string tweetid);

        // invariants:
        // - TweetStore maintains referential integrity between tweets, retweets, and likes.
        // - all userids referenced in tweets/likes/retweets exist according to usermanagement.
    };

} // end module socialmediaplatform
```
</idl>
<code to idl>
**--- Instructions for Iterative IDL Generation ---**

**Phase 1: Initial Project Analysis & Strategic Ordering**

1.  **File Discovery:**
    *   Review all files within the provided `<code context>`. Use `<brainstorming>` tags to identify relevant Python source files (`.py`).
    *   Create two lists:
        *   `to_process_idl`: List of absolute or relative paths for all identified Python files potentially requiring an IDL.
        *   `processed_idl`: Initially empty list.
    *   Display both lists.
    *   Stop and ask the user to confirm the file list or provide adjustments before proceeding.

2.  **Strategic Module Ordering (Dependency-Aware):**
    *   Analyze the imports and potential interactions within the files listed in `to_process_idl`. Identify:
        *   Core/foundational modules (e.g., base classes, shared data structures, core utilities).
        *   Highly imported modules (depended upon by many others).
        *   Potential dependency chains (A uses B which uses C).
        *   Likely API/interface modules (defining primary entry points or contracts).
    *   Create a reordered `to_process_idl` list prioritizing:
        1.  Foundational/core modules first.
        2.  Highly imported modules early.
        3.  Modules before their likely dependents (where discernible).
        4.  Group potentially related modules (e.g., within the same sub-package) together.
    *   *Self-Correction:* Note any apparent circular dependencies discovered during this analysis. These will need careful handling during generation and refinement.
    *   Present:
        *   The original `to_process_idl` list.
        *   The reordered `to_process_idl` list.
        *   A brief rationale for the ordering, highlighting key modules and any identified challenges (like cycles).
    *   This reordered list will guide the first pass of IDL generation.

**Phase 2: First Pass - Chunked Initial IDL Generation**

1.  **Process in Chunks:** Process the modules from the reordered `to_process_idl` list in chunks (e.g., 2-3 modules per chunk, adjustable based on complexity).

2.  **For each module within the current chunk:**
    *   **a. State File Path:** Clearly indicate the file path being processed (e.g., `Processing: src/module/path.py`).
    *   **b. Generate Initial IDL:**
        *   **Mapping Convention:**
            *   Each processed Python file (e.g., `src/module/path.py`) **MUST** map to an IDL `module` within its corresponding `_IDL.md` file. Derive the IDL `module` name from the Python module path (e.g., `src.module.path`).
            *   Public classes within the Python file **MUST** map to IDL `interface` definitions nested within that IDL `module`. Use the Python class name as the IDL `interface` name.
            *   Public, top-level functions within the Python file should be grouped into a dedicated `interface` named something like `ModuleFunctions` or `{ModuleName}Functions` within the IDL `module`.
        *   Apply the **Code-to-IDL Reduction Guidelines (Section III)** from the established `<idl>` guidelines based on the mapping above.
        *   Focus on mapping public classes/functions to interfaces/methods per the convention.
        *   Extract preliminary Pre/Postconditions and Invariants from docstrings and code structure.
        *   Identify direct dependencies on *other modules/classes within the project* based on imports and usage. Add these to a preliminary `# @depends_on(...)` list in the generated IDL.
            *   **Dependency Naming:** The names used in `@depends_on` **MUST** correspond to the IDL `module` or `interface` names generated according to the mapping convention (e.g., `src.module.dependency` for a module dependency, or `ClassName` for an interface dependency). Ensure a consistent naming convention for cross-module interface references if needed.
        *   Strictly apply the **EXCLUSION CRITERIA** (Section III.5).
        *   **File Naming:** The generated IDL for a source file like `src/module/path.py` **MUST** be placed in a parallel file named `src/module/path_IDL.md` (e.g., `src/orchestration/coding_workflow_orchestrator_IDL.md` for `src/orchestration/coding_workflow_orchestrator.py`).
        *   Format the output within `// == !! BEGIN IDL TEMPLATE !! ===` and `// == !! END IDL TEMPLATE !! ===` markers within the designated `_IDL.md` file.
        *   *Self-Correction/Skipping:* If a module seems purely internal or contains no significant public interface according to the exclusion criteria, note this and skip generating a formal IDL file, explaining why.
        *   **Error Handling:** If a file cannot be parsed or processed due to errors, note the error, generate a minimal or empty IDL file with a comment indicating the failure, and add it to the `refinement_required` list (Phase 3) for manual review. Do not halt the entire process unless critical.
    *   **c. Track Dependencies:** Maintain a separate, cumulative list/structure (`dependency_tracker`) storing:
        *   `source_module`: The module being processed (e.g., `src.module.path`).
        *   `target_idl_element`: The IDL `module` or `interface` name depended upon (e.g., `src.other.dependency` or `ClassName`).
        *   `status`: `resolved` (if target element's IDL was generated in a previous chunk) or `unresolved` (if target element's IDL is later in the processing order or not yet generated). The `unresolved` status is for the *tracker only* and **MUST NOT** appear in the generated IDL file itself. The `@depends_on` list in the IDL should contain the best-guess target name.

3.  **Chunk Summary & Update:**
    *   After processing all modules in a chunk, present:
        *   The file paths processed in this chunk.
        *   The generated initial IDLs for each module (or notes about skipped/errored files).
        *   A summary of new entries added to the `dependency_tracker` from this chunk, highlighting `unresolved` dependencies *in the summary*.
    *   Move the processed file paths from `to_process_idl` to `processed_idl`.
    *   Display the updated `to_process_idl` and `processed_idl` lists.
    *   Stop and ask the user if they want to proceed to the next chunk, reminding them this is an opportunity for feedback on the generated chunk.

**Phase 3: Global Analysis & Refinement Planning (After First Pass)**

1.  **First Pass Completion:** Once `to_process_idl` is empty, the first pass is complete.
2.  **Consolidated Review:** Present:
    *   All generated initial IDLs (from all chunks).
    *   The complete `dependency_tracker` list, clearly separating resolved and unresolved dependencies *based on the tracker status*.
3.  **Inconsistency Analysis:**
    *   `<thinking> Review the collected IDLs and the dependency_tracker globally. Look for: </thinking>`
    *   **Unresolved Dependencies:** Any dependencies still marked `unresolved` in the tracker. This indicates the target IDL might be missing or was skipped.
    *   **Missing Definitions:** Cases where module A depends on `B.methodX` (or `InterfaceB.methodX`), but `methodX` is missing from the generated IDL for module B / Interface B.
    *   **Signature Mismatches:** Cases where module A calls `B.methodX(int)` but B's IDL defines `methodX(string)`.
    *   **Interface Completeness:** Assess if the generated interfaces seem functionally complete.
    *   **Circular Dependencies:** Review any circular dependencies noted earlier. Mutual `@depends_on` declarations between IDL modules or interfaces (e.g., A depends on B, B depends on A) are generally acceptable in the IDL if they reflect the code's design, but flag them for user awareness during review.
4.  **Refinement Plan:**
    *   Based on the analysis, create a list (`refinement_required`) of modules/files whose IDLs need revision or creation (including those that errored).
    *   For each item in `refinement_required`, briefly state the reason(s) (e.g., "Add missing method `methodX` required by ModuleA", "Correct signature for `methodY`", "Resolve dependency on ModuleC", "File errored during generation, requires manual check").
    *   Present the analysis findings and the proposed `refinement_required` list with reasons.
    *   Ask the user to confirm or modify the refinement plan.

**Phase 4: Iterative Refinement**

1.  **Refinement Cycle:** While the `refinement_required` list is not empty:
    *   Select a module/file (or a small group) from `refinement_required`.
    *   **Re-generate/Update IDL:** Re-apply the **Code-to-IDL Reduction Guidelines (Section III)** and the **Mapping Convention (Phase 2.b)** to the selected module(s)/file(s), specifically addressing the issues identified. This may involve:
        *   Adding missing methods/interfaces.
        *   Correcting method signatures.
        *   Updating Pre/Postconditions.
        *   Correcting/adding `# @depends_on(...)` lists using the proper naming convention.
    *   **Update Dependency Tracker:** Update the `status` of relevant entries in the `dependency_tracker` if dependencies are now resolved.
    *   **Present Changes:** Show the updated IDL(s) for the revised module(s).
    *   Remove the processed item(s) from `refinement_required`.
    *   *Self-Correction/Re-Analysis:* Briefly re-assess if this change introduces new inconsistencies or resolves dependencies impacting *other* modules still needing refinement. Update `refinement_required` if necessary.
    *   Ask the user to confirm the changes before proceeding.
2.  **Cycle Completion:** If `refinement_required` is empty, and a final check reveals no outstanding unresolved dependencies (in the tracker) or major inconsistencies, the phase is complete. If issues remain, perform another round of **Global Analysis & Refinement Planning (Phase 3)**.

**Phase 5: Final Output**

1.  **Present Final IDLs:** Display the complete, consistent set of generated IDLs for all relevant modules in the project.
2.  **Final Dependency Overview:** Optionally, present a final summary derived from the `@depends_on` lists in the final IDLs.
</code to idl>

