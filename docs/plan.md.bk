Implementation Priority for Remaining Critical Path Issues
Now that we've addressed Context Management Standardization, here's the recommended order for tackling the remaining critical path issues:
1. Error Taxonomy for Context Issues
Should be resolved first because:

It's foundational to all error handling in the system
Other mechanisms depend on clear error categorization
It affects control flow throughout the architecture
It's relatively straightforward to implement (adding/modifying error types)

Key decisions needed:

Whether to create a distinct CONTEXT_FAILURE error type
How to categorize different context generation failures
How errors propagate through nested operations

2. Partial Results Policy
Should be addressed second because:

It builds directly on the error taxonomy
It's needed for reliable multi-step operations
It determines how the system handles incomplete work
It affects error recovery strategies system-wide

Key decisions needed:

Whether operators should preserve intermediate outputs on failure
How partial results are structured in error responses
Whether partial outputs should be usable for recovery

3. Evaluator-to-Director Feedback Flow
Should be third because:

It's essential for the director-evaluator pattern to function
It establishes a model for task-subtask communication
It needs clear error handling and partial results policies
It's a concrete case that informs the broader subtask mechanism

Key decisions needed:

How evaluator output is passed back to the director
How context is maintained across continuation boundaries
Error handling within the feedback loop

4. Subtask Spawning Mechanism
Should be addressed last because:

It's the most complex of the critical issues
It benefits from resolving the previous issues first
It represents a broader extension of the task system
It requires careful integration with existing patterns

Key decisions needed:

How tasks dynamically create and bind subtasks
How the Evaluator creates subtasks from task notes
Control flow between parent tasks and subtasks

Implementation Strategy
This ordering minimizes rework by resolving foundational issues before their dependencies. A useful approach would be:

Draft ADRs for each issue in the recommended order
Implement each feature incrementally
Test thoroughly before moving to the next priority

This sequence ensures that core error handling is solidified before building more complex interaction patterns on top of it.

------

Implementation Priority for High Priority Items
Following Context Management and the Critical Path issues, here's the recommended order for implementing the High Priority items:
1. Memory System Version Consolidation
Should be addressed first because:

It's primarily a documentation and reference cleanup issue
It creates a clear foundation for all component interactions
It resolves ongoing confusion about Memory System interfaces
It has minimal code impact but high architectural clarity value

Key decisions needed:

Standardize on Memory System 3.0 throughout all docs
Clear separation between file metadata and content operations
Update all cross-references consistently
Document the final Memory System interface contract

Note: The previously considered "rebuild-memory" and "clear-memory" flags have been determined to be redundant with the existing context management model and will not be implemented. The same functionality can be achieved through appropriate configuration of <inherit_context>, <accumulate_data>, and <fresh_context> settings.

2. XML-to-AST Mapping
Should be second because:

It defines how configuration translates to execution structure
It's fundamental to all operator implementations
It establishes clear parsing rules for the context attributes we just defined
It bridges the gap between authored tasks and runtime representation

Key decisions needed:

Formal mapping between XML elements and AST nodes
Handling of attribute inheritance in nested structures
Namespace and versioning considerations
Validation and error reporting during parsing

3. Output Standardization
Should be third because:

It enables reliable data flow between components
It's necessary for variable binding and task composition
It builds on clear AST structures
It's relatively self-contained and can be implemented incrementally

Key decisions needed:

Whether to enforce JSON for all outputs
Schema or structure requirements for outputs
How outputs are parsed and validated
Standard conventions for error reporting in outputs

4. DSL Function Implementation
Should be fourth because:

It relies on standardized outputs for parameter passing
It needs clear XML-to-AST mapping for function definition
It represents a significant feature that builds on the previous foundations
It enables higher-level composition patterns

Key decisions needed:

Task library in-memory representation
Function definition syntax and semantics
Scope and binding rules
How to represent and execute composite functions

5. Tool vs. Subtask Distinction
Should be addressed last because:

It refines execution patterns established by earlier items
It's more concerned with semantics than infrastructure
It may benefit from experience with function implementation
It requires clear context management (which we've already addressed)

Key decisions needed:

Clear boundary definition between tools and subtasks
Interface contracts for each type
Resource management differences
Whether tools should have standardized output formats

Implementation Strategy
This ordering follows a logical dependency chain:

First consolidate the Memory System interface to provide a stable foundation
Then establish the XML-to-AST mapping to ensure consistent parsing
Standardize outputs to enable reliable data flow between components
Implement function mechanisms that depend on standardized I/O
Finally clarify the tool/subtask boundary to refine execution patterns

This sequence builds from low-level infrastructure toward higher-level patterns, minimizing rework and creating a stable foundation for each subsequent feature.
