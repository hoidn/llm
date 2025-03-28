# Task System Requirements

This document outlines the high-level functional and non‑functional requirements for the Task System.

## Key Requirements Summary

1. **XML-based Task Templates:**  
   - All task templates must conform to [Contract:Tasks:TemplateSchema:1.0].  
   - Both LLM‑generated and manual XML structures are supported, with options to disable reparsing.

2. **Handler and Resource Management:**  
   - One Handler is created per task execution with immutable configuration and strict resource tracking.
   - Resource limits (turn counts, context window) are enforced by the Handler. For details, see [Pattern:ResourceManagement:1.0].

3. **Task Matching:**  
   - The system matches natural language inputs and AST nodes to candidate task templates (up to 5 candidates) using numeric scoring.

4. **Memory Integration:**  
   - The Task System uses a read‑only Memory System interface for context retrieval. See [Interface:Memory:3.0].

5. **Script Execution Support:**  
   - XML schema extensions support specifying external command details for script tasks. Clear input/output contracts must be defined.

For detailed operational behavior, see the Behaviors document. Additional system‑level details are available in the central contracts and architecture documents.

## See Also

 - [Task System Behaviors](behaviors.md)
 - [Task System Interfaces](interfaces.md)
 - System-level contracts: [Contract:Tasks:TemplateSchema:1.0] and [Pattern:ResourceManagement:1.0]
