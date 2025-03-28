# Architecture Questions
    
This document tracks architecture-level questions, both resolved and unresolved.
    
## Resolved Questions
    
### Context Management
    
**Q: How is context inherited in complex tasks?**  
A: Context inheritance is controlled by the three-dimensional context management model:
- `inherit_context`: Controls whether a task inherits "full" parent context, "none", or a "subset" based on relevance
- `accumulate_data`: Controls whether outputs from prior steps are accumulated
- `fresh_context`: Controls whether new context is generated via associative matching
    
See [ADR 14: Operator Context Configuration](../architecture/decisions/completed/014-operator-ctx-config.md) for the complete decision.
    
**Q: Should rebuild-memory and clear-memory flags be added?**  
A: No. The same functionality can be achieved through appropriate configuration of `<inherit_context>`, `<accumulate_data>`, and `<fresh_context>` settings. Adding separate flags would be redundant.
    
**Q: How should context inheritance work in reduce operations?**  
A: The `reduce` operator now supports the same context management model as other operators, with different defaults:
- `inherit_context`: "none" (default)
- `accumulate_data`: "true" (default)
- `fresh_context`: "enabled" (default)
    
See [ADR 14: Operator Context Configuration](../architecture/decisions/completed/014-operator-ctx-config.md) for details.
    
### Error Handling
    
**Q: Should there be a distinct error type for context failures?**  
A: No. Context failures are categorized under the standard `TASK_FAILURE` type with specific reason codes:
- `context_retrieval_failure`: Failure to retrieve context data
- `context_matching_failure`: Failure in associative matching algorithm
- `context_parsing_failure`: Failure to parse or process retrieved context
    
See [ADR 8: Error Taxonomy](../architecture/decisions/8-errors.md) for the complete decision.
    
**Q: How should partial results be handled on failure?**  
A: Partial results are preserved in standardized error structures specific to each task type:
- Atomic tasks: Store partial content in `content` field with FAILED status
- Sequential tasks: Store step outputs in `details.partialResults` array
- Reduce tasks: Store processed inputs and current accumulator
    
See [ADR 9: Partial Results Policy](../architecture/decisions/completed/009-partial-results.md) for details.
    
### Component Integration
    
**Q: How should Director and Evaluator components interact?**  
A: The Director-Evaluator pattern now supports both dynamic and static variants with direct parameter passing:
- Dynamic: Director returns CONTINUATION status with evaluation_request
- Static: Predefined director_evaluator_loop task type with explicit components
    
See [ADR 10: Evaluator-to-Director Feedback Flow](../architecture/decisions/completed/010-evaluator-director.md) for details.
    
**Q: Should subtasks use environment variables or direct parameter passing?**  
A: Direct parameter passing. Subtasks use a standardized SubtaskRequest structure with explicit inputs, and results are passed back directly through the task return value. Environment variables are not used for data flow.
    
See [ADR 11: Subtask Spawning Mechanism](../architecture/decisions/completed/011-subtask-spawning.md) for details.
    
**Q: What is the boundary between tools and subtasks?**  
A: Tools are Handler-managed operations with deterministic APIs, while subtasks are LLM-to-LLM interactions using the continuation mechanism. The Unified Tool Interface pattern provides a consistent interface for both, with different implementation strategies.
    
See [Pattern:ToolInterface:1.0](../architecture/patterns/tool-interface.md) for details.
    
## Unresolved Questions
    
### 1. Genetic Testing Approach
    
**Q: How should multiple solution candidates be generated and evaluated?**  
    
This remains an open design area focused on:
- Generating multiple solution approaches to the same problem
- Evaluating each approach against defined criteria
- Selecting the best solution based on evaluation results
    
This may be implemented as an extension of the Director-Evaluator pattern or as a new pattern entirely.
    
### 2. Agent-Style Workflow Patterns
    
**Q: How should the system implement conversation → JSON → map spec prompts workflow?**
    
This workflow pattern would allow:
- Converting natural language conversation to structured data
- Using that data to generate specification prompts
- Executing those prompts in parallel
    
The implementation details and integration with existing patterns are still under consideration.
    
### 3. Multi-LLM Coordination
    
**Q: How should the system coordinate different LLM types for specialized tasks?**
    
This question involves:
- Selecting appropriate LLM types for different subtasks
- Managing context flow between different LLM providers
- Optimizing resource usage across multiple LLMs
    
This may require extensions to the Handler abstraction and Provider-specific adapters.
