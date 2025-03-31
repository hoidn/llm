# TODOS and Implementation Plan

This document categorizes all remaining tasks and provides a prioritized implementation plan. The goals are to ensure system consistency, complete documentation, and implement remaining features in a logical order.

## Status Categories

Tasks are organized into four categories:

1. **Complete**: Implemented and documented in the system architecture
2. **Incomplete**: Well-defined goals that need implementation
3. **Inconsistent**: Items that conflict with other components or decisions
4. **Unclear**: Items requiring clarification before implementation

## Complete ✓

### Interface and Memory System
- Memory System interface version defined [Interface:Memory:3.0]
- File content type handling standardized (Handler tools)
- Unified storage approach defined in ADR
- Memory Component Separation with clear interfaces and integration documentation
- File tracking ownership decided (Memory System owns metadata, Handler owns file operations)
- Resource tracking responsibilities documented in Pattern:ResourceManagement:1.0
- File operation responsibility boundaries clearly defined:
  * Memory System: Manages ONLY metadata (file paths and descriptive strings)
  * Handler: Performs ALL file I/O operations using appropriate tools (including Anthropic's computer use tools for Anthropic models)
  * Clear separation of concerns between metadata management and file operations
- Memory System version consistently referenced as 3.0 across all documentation
- updateContext method references removed; documentation consistently reflects read-only context model
- Tool calls vs. subtasks boundaries clearly defined:
  * Tool calls: Handler-managed deterministic operations with rigid APIs
  * Subtasks: LLM-to-LLM interactions using continuation mechanism
  * Clear component responsibilities established for each type

### Context Management
- Document best practices (ADR 004, ADR 14)
- Define efficient subtask patterns (sequential)
- Extend `inherit_context` to map/reduce operators (ADR 14)
- Provide partial-result guidance via accumulation_format (ADR 9, ADR 14)
- Consolidate environment usage across context types
- Add context reuse mechanisms via context_management block
- Update error taxonomy for context failures (ADR 8)

### Task Type System & Patterns
- Basic task types defined and implemented
- Subtask support via standardized mechanism (ADR 11)
- Map operator implementation
- Director-Evaluator pattern with script execution integration
- Function-based templates with parameter declaration (ADR 12)
- Task continuation protocol via CONTINUATION status
- JSON-based output standardization (ADR 13)
- Partial results policy implemented (ADR 9)

## Incomplete ❌

### Phase 1: Documentation and Interface Consistency
1. **Update Task System implementation to use Memory System 3.0**
   - Ensure all Task System documentation references Memory System 3.0
   - Update interface method references to match current Memory System interface
   - Verify correct usage of file operations vs. metadata operations

2. **Remove or reconcile deprecated memory structures**
   - Remove references to `updateContext` method (deprecated in Memory System 3.0)
   - Update code examples to use current interface methods
   - Ensure consistent handling of read-only context model

3. **Align version numbers across documentation**
   - Audit all component version references
   - Ensure consistency in interface versions
   - Update any outdated references to match current architecture

4. **Update cross-references systematically**
   - Fix broken references between documents
   - Ensure cross-references point to canonical sources
   - Validate all [Interface:X:Y.Z] references

### Phase 2: Core Implementation Improvements
5. **Interface updates to align with current patterns**
   - Review interface definitions for consistency with architecture decisions
   - Update type signatures and method names as needed
   - Ensure interfaces follow established patterns (Memory System is read-only, etc.)

6. **Document context management patterns for common scenarios**
   - Create comprehensive examples for context clearing and regeneration
   - Update documentation with recommended settings for different use cases
   - Ensure consistent guidance across all component documentation

7. **Summary output handling in evaluator**
   - Implement mechanism for efficient summary outputs between tasks
   - Define standard summary format
   - Document integration with context management

8. **Document subtask usage patterns with context**
   - Create comprehensive documentation for subtask patterns
   - Include examples of context inheritance models
   - Demonstrate common subtask usage patterns

9. **Provide complete implementation examples**
   - Create end-to-end examples of task execution
   - Include error handling, context management, and file operations
   - Demonstrate component interactions

### Phase 3: Architecture and Use Cases
10. **Architecture Documentation standardization**
    - Ensure consistent documentation structure across components
    - Standardize terminology and diagram formats
    - Create consistent interaction descriptions

11. **Add missing cross-component documentation**
    - Document how components interact
    - Create diagrams showing data flow between components
    - Ensure integration points are clearly described

12. **Write user stories and examples**
    - Create comprehensive user stories showing system usage
    - Include examples of different workflows
    - Demonstrate system capabilities through concrete examples

### Phase 4: Advanced Features
13. **Multiple tries/selection of best candidate result**
    - Design mechanism for generating multiple solution candidates
    - Implement evaluation criteria
    - Create selection process for best results

14. **Agent file storage and recall mechanisms**
    - Design system for agents to store and recall information
    - Define file format and organization
    - Implement access methods

15. **Advanced debugging capabilities**
    - Implement comprehensive logging
    - Add step-by-step execution tracking
    - Create context inspection tools

16. **Agent features (history storage, REPL)**
    - Design and implement storage for agent conversation history
    - Create REPL interface for interactive task execution
    - Integrate with existing components

17. **Multi-LLM support**
    - Design abstraction layer for different LLM providers
    - Implement adapters for each provider's API
    - Ensure consistent behavior across models

18. **DSL optimization or alternative language support**
    - Evaluate current DSL performance and usability
    - Identify optimization opportunities
    - Consider alternative syntax or language support

## Inconsistent ⚠️

~~2. **Task-subtask context inheritance**~~
   ~~- Multiple conflicting descriptions exist~~
   ~~- Standardize on the approach defined in ADR 14~~
   
   *Completed: Implemented atomic task subtypes with different context management defaults. Standard atomic tasks inherit context but don't generate fresh context, while subtasks don't inherit context but do generate fresh context.*

## Unclear ❓

1. **"Genetic" behavior implementation**
   - Clarify how multiple tries and result selection would work
   - Define evaluation criteria for selecting best solutions

2. **Subtask spawning and evaluator interaction**
   - Detail exactly how subtasks spawned by task system work with evaluator
   - Specify control flow and context handling

3. **Architecture documentation "self-similarity"**
   - Define what "self-similarity in structure" means for documentation
   - Provide concrete examples of desired documentation patterns

4. **Agent-style workflow patterns**
   - Clarify implementation of "conversation → json → map spec prompts" pattern
   - Provide examples of intended workflow

5. **Chat queue implementation**
   - Specify requirements for chat queue management
   - Define integration with task system

6. **Shell node integration**
   - Clarify how "shell" nodes fit into the architecture
   - Define interaction with Director-Evaluator pattern

7. **Model temperature/selection handling**
   - Determine whether model parameters should be handled at system level
   - Define configuration approach

8. **Multi-try evaluation criteria**
   - Specify how to implement evaluation criteria for selecting best results
   - Define scoring mechanisms and decision process

## Dependencies and Critical Path

The critical path for completing the system involves:

1. Documentation and interface consistency (Phase 1)
2. Core implementation improvements (Phase 2)
3. Architecture documentation and use cases (Phase 3)
4. Advanced features (Phase 4)

Items within Phase 1 should be completed first as they provide the foundation for all subsequent work. Within each phase, items are listed in priority order based on dependencies and impact.


user story:
make plan docs interactively (or with a prompt queue), write them to file; add them to heritable context; gen spec prompts; subtask -> try to impl spec prompt, up to 3 round of debugging; on failure return to parent task 
CONTINUATION with failure notes; parent tries to debug (either itself or with full context subtask) or maybe something else. 
bonus: failure notes get interpreted as lessons and are used to update plan or project_rules.md

- does handler need a 'dumb' llm backend to prompt the main agent to continue?
- how will git integration work?
- get rid of natural language -> xml path, just use natural language -> dsl. this avoids nested xml ugliness, clarifies the use of xml as formatting for a single prompt
- option to pass list of file paths to subtask

## Resolved Questions

- ✓ RESOLVED: Template substitution is an Evaluator responsibility. The Evaluator resolves all {{variable_name}} placeholders before dispatching tasks to the Handler.


---

- use aider's repo map to identify needed files? or use git grep by default in associative matching?
https://old.reddit.com/r/ChatGPTCoding/comments/1jnkhjw/context_control_for_local_llms_how_do_you_handle/
Sometimes I run aider in aider. I have a shell script called aider-plan that launches aider with different settings and leaves a summary finding in the clipboard so you can run /paste or /editor to import them in to the main aider.

It also instructs to use !git grep to find files that are missed from the map.

```bash $ aider

!aider-plan ask> What files do I modify to ... ask> /exit /paste ```

Or single-shot usage.

```bash $ aider

!aider-plan -m 'What files do I modify to ...' /paste ```

There's a similar new /context command, but its not quite enough for my use. I may make a feature request to add config/options for context-map-tokens and context-model. Then I can delete my script.

I also have aider-rag for searching docs (including markdown and javadocs/pydocs/tsdoc) and a few other aider-in-aider utility scripts.

- formalize a plan - execute - review cycle
- inboxes
- some kind of file persistet inntetion or high level plan at the top level
- other tools are getting better at context management. how to stay ahead? maybe by indexing?
- reintroduce non file based context retrievall
