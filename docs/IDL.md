<idl>
**--- IDL Guidelines ---**

**I. Overview & Purpose**

These guidelines define a system for creating and understanding Interface Definition Language (IDL) specifications and their corresponding code implementations. The process is designed to be **bidirectional**:

1.  **IDL-to-Code:** Use a defined IDL as a strict contract to generate compliant, high-quality code. 
2.  **Code-to-IDL:** Reduce existing code to its essential IDL specification, abstracting away implementation details to reveal the core functional contract. See <code to idl>.

The goal is a clear separation between the *what* (the functional contract defined in the IDL) and the *how* (the implementation details within the code).

**II. IDL Creation & Structure Guidelines**

*(These apply both when writing IDL from scratch and when reducing code TO IDL)*

1.  **Object Oriented:** Structure the IDL using modules and interfaces to represent logical components and entities.
2.  **Dependency Declaration:**
    *   **Purpose:** To explicitly declare which other IDL-defined modules or interfaces a given interface relies upon to fulfill its contract. This clarifies coupling at the design level.
    *   **Syntax:** Use a comment line placed immediately before the `interface` definition. The format is:
        `# @depends_on(Dependency1, Dependency2, ...)`
    *   **Target:** `Dependency1`, `Dependency2`, etc., must refer to the names of other `module` or `interface` definitions within the scope of the overall IDL system.
    *   **Implication:** This declaration signals that an implementation of the interface will likely require access (e.g., via instantiation or dependency injection) to implementations conforming to the dependent interfaces/modules. It defines a dependency on the *contract*, not a specific implementation detail.
3.  **Design Patterns:** Utilize (when creating IDL) or identify (when reducing code) interfaces supporting established design patterns like Factory, Builder, and Strategy where they clarify the design or improve flexibility. The IDL defines the *contract* for these patterns, not their internal implementation.
4.  **Complex Parameters (JSON):**
    *   **Preference for Structure:** If the IDL syntax supports defining custom structures/records/data classes, prefer them for complex data transfer to maximize type safety at the interface level.
    *   **JSON Fallback:** Where structured types are not feasible in IDL or cross-language string simplicity is paramount, use a single JSON string parameter.
    *   **Mandatory Documentation:** *Always* document the exact expected JSON format within the IDL comment block (e.g., `// Expected JSON format: { "key1": "type1", "key2": "type2" }`).
5.  **Clarity and Intent:** The IDL should clearly express the *purpose* and *expected behavior* of each interface and method through well-chosen names and comprehensive documentation (Pre/Postconditions, Invariants).
6.  **Completeness (Functional Contract):** The IDL must represent the *complete functional contract* of the component's public interface.

**III. Code-to-IDL Reduction Guidelines**

*(These specific rules apply ONLY when generating an IDL FROM existing code)*

1.  **Goal: Extract the Contract:** The primary objective is to distill the code down to its public interface and functional guarantees, omitting all non-essential implementation details.
2.  **Mapping:**
    *   Public classes/modules generally map to IDL `module` or `interface`.
    *   Public methods/functions map to IDL method definitions.
    *   Method signatures (name, parameter types, return type) must be accurately reflected.
3.  **Dependency Identification:** Identify dependencies on other components *that are also being defined via IDL*. Represent these using the **Dependency Declaration** syntax (`# @depends_on(...)`) described in Section II.2. Exclude dependencies on third-party libraries or internal implementation details not represented by an interface in the IDL.
4.  **Documentation Extraction:**
    *   Infer **Preconditions** from input validation, assertions, and documentation comments in the code.
    *   Infer **Postconditions** from return value guarantees, state changes described in documentation, or observable outcomes.
    *   Identify and document **Invariants** – properties of the object's state that hold true between public method calls.
    *   If complex objects/dictionaries are passed as parameters, represent them using the **Complex Parameters (JSON)** guideline (II.4) and document the format.
5.  **EXCLUSION CRITERIA:** The following elements **MUST BE EXCLUDED** from the generated IDL as they are considered implementation details or non-functional aspects:
    *   **Presentation Logic:** Any code related to Graphical User Interfaces (GUI), Text User Interfaces (TUI), web page rendering, console output formatting, or specific presentation frameworks.
    *   **Internal Implementation Details:** Private methods, helper functions not part of the public API, internal data structures (unless their *structure* is inherently part of the public contract, e.g., via JSON), specific algorithms used (unless the choice of algorithm is selectable via the interface, like a Strategy pattern).
    *   **Type Enforcement/Validation Code:** The *internal logic* for validating inputs or enforcing type constraints (e.g., `if` checks, `try-except` blocks for type errors, calls to validation libraries). The *requirement* for valid input should be captured as a Precondition.
    *   **Non-Functional Code:** Logging statements, metrics collection, performance monitoring, debugging utilities, internal comments explaining *how* the code works (vs. *what* it guarantees).
    *   **Language/Platform Specifics:** Boilerplate code generated by frameworks (unless it directly defines a public contract method), language-specific idioms with no direct equivalent, environment configuration loading, build system artifacts, specific library dependencies (unless they form part of the public method signatures).
    *   **Error Handling Mechanisms:** Specific exception types thrown/caught internally, error reporting mechanisms. The IDL should focus on the successful execution path (Postconditions) and potentially define expected error *conditions* or *states* abstractly if they are part of the contract, rather than specific language exceptions.
    *   Dependencies on concrete libraries or modules *not* represented by an IDL interface within the system.

**IV. IDL Template**

```idl
// == !! BEGIN IDL TEMPLATE !! ===
module GenericSystemName {

    // Optional: Define shared data structures if IDL syntax allows
    // struct SharedData { ... }

    // Example interface demonstrating dependency declaration
    # @depends_on(AnotherInterfaceName, SharedModuleName)
    interface EntityName {

        // Action/method definition
        // Preconditions:
        // - Define necessary conditions before calling.
        // - (If using JSON param) Expected JSON format: { "key1": "type1", ... }
        // Postconditions:
        // - Define expected outcomes and state changes after successful execution.
        returnType methodName(parameterType parameterName);

        // Additional methods...

        // Invariants: (Optional: Define properties that always hold true for this entity)
        // - Describe state invariants here.
    };

    // Another entity or component that EntityName might depend on
    interface AnotherInterfaceName {
        // ... methods ...
    };

    // Could also be a module containing utility interfaces/functions that EntityName might depend on
    module SharedModuleName {
        // ... interfaces or potentially functions if IDL supports them ...
    }
};
// == !! END IDL TEMPLATE !! ===
```

**V. Code Creation Rules**

*(These apply when implementing code BASED ON an IDL)*

1.  **Strict Typing:** Always use strict typing. Avoid ambiguous or variant types.
2.  **Primitive Types Focus (Balanced):** Prefer built-in primitive and standard collection types where they suffice. Use well-defined data classes/structs for related data elements passed together. Avoid "primitive obsession." Match IDL types precisely.
3.  **Portability Mandate:** Write code intended for potential porting to Java, Go, JavaScript. Use language-agnostic logic and avoid platform-specific dependencies or language features without clear equivalents.
4.  **Minimize Side Effects:** Strive for pure functions for data processing. Clearly document all necessary side effects (state mutation, I/O, external calls) associated with methods defined in the IDL, typically in the implementation's documentation, aligning with the IDL's Postconditions.
5.  **Testability & Dependency Injection:** Design for testability. Use dependency injection, avoid tight coupling. Ensure methods corresponding to IDL definitions are unit-testable. Pay attention to the `# @depends_on` declarations in the IDL to identify required dependencies that should likely be injected.
6.  **Documentation:** Thoroughly document implementation details, especially nuances not obvious from the IDL or code signature. Link back to the IDL contract being fulfilled.
7.  **Contractual Obligation:** The IDL is a strict contract. Implement *all* specified interfaces, methods, and constraints *precisely* as defined. Do not add public methods or change signatures defined in the IDL.

**VI. Example**

*(The `Tweets` example, modified to show dependency declaration)*

```idl
module SocialMediaPlatform {

    // Assume these interfaces are defined elsewhere in the IDL system
    // interface UserManagement { ... }
    // interface StorageService { ... }

    # @depends_on(UserManagement, StorageService)
    interface Tweets {
        // Preconditions:
        // - User referenced by userID in tweetJSON exists (verified via UserManagement).
        // - tweetContent is non-null and within allowable size limits.
        // Postconditions:
        // - A new tweet is created and stored (via StorageService).
        // Expected JSON format: { "userID": "string", "content": "string" }
        void postTweet(string tweetJSON);

        // Preconditions:
        // - User referenced by userID exists (verified via UserManagement).
        // - Tweet referenced by tweetID exists (verified via StorageService).
        // Postconditions:
        // - The tweet with tweetID is marked as liked by userID (via StorageService).
        void likeTweet(string userID, string tweetID);

        // Preconditions:
        // - User referenced by userID in retweetJSON exists (verified via UserManagement).
        // - Original tweet referenced by originalTweetID in retweetJSON exists (verified via StorageService).
        // Postconditions:
        // - A new retweet linked to the original is created and stored (via StorageService).
        // Expected JSON format: { "userID": "string", "originalTweetID": "string" }
        void retweet(string retweetJSON);

        // Preconditions:
        // - Tweet referenced by tweetID exists (verified via StorageService).
        // Postconditions:
        // - Returns the details of the tweet as a JSON string (retrieved via StorageService).
        string getTweetDetails(string tweetID);

        // Invariants:
        // - StorageService maintains a consistent list of tweets, likes, and retweets.
        // - All userIDs referenced in tweets/likes/retweets exist according to UserManagement.
    };

} // End module SocialMediaPlatform
```
<idl>
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
    *   **a. State File Path:** Clearly indicate the file path being processed.
    *   **b. Generate Initial IDL:**
        *   Apply the **Code-to-IDL Reduction Guidelines (Section III)** from the established `<idl>` guidelines.
        *   Focus on mapping public classes/functions to interfaces/methods.
        *   Extract preliminary Pre/Postconditions and Invariants from docstrings and code structure.
        *   Identify direct dependencies on *other modules within the project* based on imports and usage. Add these to a *preliminary* `# @depends_on(...)` list in the generated IDL. Mark dependencies targeting modules not yet processed in this pass as potentially `[unresolved]`.
        *   Strictly apply the **EXCLUSION CRITERIA** (Section III.5).
        *   **File Naming:** The generated IDL for a source file like `src/module/path.py` **MUST** be placed in a parallel file named `src/module/path_IDL.md`.
        *   Format the output within `// == !! BEGIN IDL TEMPLATE !! ===` and `// == !! END IDL TEMPLATE !! ===` markers within the designated `_IDL.md` file.
        *   *Self-Correction:* If a module seems purely internal or contains no significant public interface according to the exclusion criteria, note this and potentially skip generating a formal IDL file, explaining why.
    *   **c. Track Dependencies:** Maintain a separate, cumulative list/structure (`dependency_tracker`) storing:
        *   `source_module`: The module being processed.
        *   `target_module`: The module depended upon.
        *   `target_element` (optional): Specific class/function used, if easily identifiable.
        *   `status`: `resolved` (if target module's IDL was generated in a previous chunk) or `unresolved` (if target module is later in the processing order or its IDL hasn't been generated yet).

3.  **Chunk Summary & Update:**
    *   After processing all modules in a chunk, present:
        *   The file paths processed in this chunk.
        *   The generated initial IDLs for each module.
        *   A summary of new entries added to the `dependency_tracker` from this chunk, highlighting `unresolved` dependencies.
    *   Move the processed file paths from `to_process_idl` to `processed_idl`.
    *   Display the updated `to_process_idl` and `processed_idl` lists.
    *   Stop and ask the user if they want to proceed to the next chunk.

**Phase 3: Global Analysis & Refinement Planning (After First Pass)**

1.  **First Pass Completion:** Once `to_process_idl` is empty, the first pass is complete.
2.  **Consolidated Review:** Present:
    *   All generated initial IDLs (from all chunks).
    *   The complete `dependency_tracker` list, clearly separating resolved and unresolved dependencies.
3.  **Inconsistency Analysis:**
    *   `<thinking> Review the collected IDLs and the dependency_tracker globally. Look for: </thinking>`
    *   **Unresolved Dependencies:** Any dependencies marked `unresolved` in the tracker.
    *   **Missing Definitions:** Cases where module A depends on `B.methodX`, but `methodX` is missing from the generated IDL for module B.
    *   **Signature Mismatches:** Cases where module A calls `B.methodX(int)` but B's IDL defines `methodX(string)`. (This might require deeper analysis or be inferred from usage patterns if not explicit in docstrings).
    *   **Interface Completeness:** Assess if the generated interfaces seem functionally complete based on their apparent roles and how they are used by other modules. Are crucial operations missing?
    *   **Circular Dependencies:** Review any circular dependencies noted earlier and how they manifest in the IDLs and tracker.
4.  **Refinement Plan:**
    *   Based on the analysis, create a list (`refinement_required`) of modules whose IDLs need revision.
    *   For each module in `refinement_required`, briefly state the reason(s) for revision (e.g., "Add missing method `methodX` required by ModuleA", "Correct signature for `methodY`", "Resolve dependency on ModuleC").
    *   Present the analysis findings and the proposed `refinement_required` list with reasons.
    *   Ask the user to confirm or modify the refinement plan.

**Phase 4: Iterative Refinement**

1.  **Refinement Cycle:** While the `refinement_required` list is not empty:
    *   Select a module (or a small group of related modules) from the `refinement_required` list.
    *   **Re-generate/Update IDL:** Re-apply the **Code-to-IDL Reduction Guidelines (Section III)** to the selected module(s), specifically addressing the issues identified in the refinement plan. This may involve:
        *   Adding missing methods/interfaces.
        *   Correcting method signatures (`returnType`, `parameterType`).
        *   Updating Pre/Postconditions to be more accurate based on cross-module context.
        *   Updating the `# @depends_on(...)` list, potentially resolving previously unresolved dependencies.
    *   **Update Dependency Tracker:** Update the `status` of relevant entries in the `dependency_tracker` if dependencies are now resolved by the updated IDL.
    *   **Present Changes:** Show the updated IDL(s) for the revised module(s).
    *   Remove the processed module(s) from `refinement_required`.
    *   *Self-Correction/Re-Analysis:* After each refinement, briefly re-assess if this change introduces new inconsistencies or resolves dependencies for *other* modules still needing refinement. Update the `refinement_required` list if necessary.
    *   Ask the user to confirm the changes before proceeding with the next item in `refinement_required`.
2.  **Cycle Completion:** If the `refinement_required` list becomes empty, and a brief final check reveals no outstanding unresolved dependencies or major inconsistencies, the refinement phase is complete. If inconsistencies remain, perform another round of **Global Analysis & Refinement Planning (Phase 3)**.

**Phase 5: Final Output**

1.  **Present Final IDLs:** Display the complete, consistent set of generated IDLs for all relevant modules in the project.
2.  **Final Dependency Overview:** Optionally, present a final summary of the resolved dependencies, perhaps formatted like the `# @depends_on` lists for clarity.

This iterative process allows for building up the IDL specifications incrementally, using the global context gathered after the first pass to refine and ensure consistency across the entire project, much like your Mermaid example built up the overall dependency graph.
</code to idl>

