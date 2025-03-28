# Handler Component [Component:Handler:1.0]

## Overview

The Handler manages LLM interactions, resource tracking, and tool execution. It serves as the direct interface to LLM providers while enforcing system constraints.

## Core Responsibilities

1. **LLM Interaction Management**
   - Execute prompts through provider-specific adapters
   - Manage conversation history and message formatting
   - Track resource usage (turns, context window)

2. **Resource Enforcement**
   - Monitor turn counts and context window usage
   - Enforce limits with appropriate error handling
   - Generate warnings at specified thresholds (80%)

3. **Tool Execution**
   - Provide unified tool interface to LLMs
   - Execute direct tools synchronously
   - Transform subtask requests into CONTINUATION signals

4. **Passthrough Mode**
   - Process raw queries without AST compilation
   - Maintain conversation state within subtasks
   - Apply standard context management to non-AST queries

5. **Session Management**
   - Maintain isolated execution environments for tasks
   - Track conversation state and history
   - Ensure clean resource release after execution

## Handler Visualization

### Resource Tracking
The following diagram illustrates how the Handler tracks resources:

```mermaid
flowchart TD
    HS[Handler Session] --> TC[Turn Counter]
    HS --> CW[Context Window]
    TC --> IT[Increment on<br>Assistant Message]
    CW --> TT[Track Token Usage]
    IT --> CL[Check Limits]
    TT --> CL
    CL -->|Exceeded| RE[Raise Resource<br>Exhaustion Error]
    CL -->|Within Limits| CE[Continue Execution]
    
    classDef session fill:#f96,stroke:#333
    classDef resource fill:#bbf,stroke:#333
    classDef action fill:#bfb,stroke:#333
    classDef decision fill:#f9f,stroke:#333
    
    class HS session
    class TC,CW resource
    class IT,TT,RE,CE action
    class CL decision
```

The Handler enforces strict resource limits for turns and context window usage to ensure tasks operate within defined constraints.

### Tool Interface Flow
This diagram shows how different types of tools are handled:

```mermaid
flowchart TD
    LLM[LLM] -->|Tool Call| UT[Unified Tool Interface]
    UT -->|Direct Tool| DT[Direct Execution<br>by Handler]
    UT -->|Subtask Tool| ST[CONTINUATION<br>with SubtaskRequest]
    DT -->|Synchronous| TR[Tool Result]
    ST -->|Asynchronous| TS[Task System]
    TS -->|Execute Subtask| SS[Subtask Execution]
    SS -->|Result| TS
    TS -->|Resume with Result| TR
    TR --> LLM
    
    classDef llm fill:#f96,stroke:#333
    classDef interface fill:#bbf,stroke:#333
    classDef execution fill:#bfb,stroke:#333
    classDef system fill:#f9f,stroke:#333
    
    class LLM llm
    class UT interface
    class DT,SS execution
    class ST,TS,TR system
```

This visualization shows how the Handler provides a unified tool interface that hides implementation details from the LLM, while supporting both simple direct tools and complex LLM-to-LLM subtasks.

## Key Interfaces

- **executePrompt**: Submit prompts to the LLM and process responses
- **registerDirectTool**: Register synchronous tools for direct execution
- **registerSubtaskTool**: Register tools implemented via subtask continuation
- **addToolResponse**: Add tool responses to conversation history
- **handlePassthroughQuery**: Process raw text queries without AST compilation

For detailed specifications, see:
- [Interface:Handler:1.0] in `/components/handler/spec/interfaces.md`
- [Pattern:ResourceManagement:1.0] in `/system/architecture/patterns/resource-management.md`
- [Pattern:ToolInterface:1.0] in `/system/architecture/patterns/tool-interface.md`

For a comprehensive map of all system documentation, see [Documentation Guide](/system/docs-guide.md).
