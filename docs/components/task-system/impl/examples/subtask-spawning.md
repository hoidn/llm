# Subtask Spawning Examples
    
This document contains examples of subtask spawning in the Task System.
    
## Basic Subtask Request Example
    
```typescript
// Parent task implementation
async function processComplexTask(input: string): Promise<TaskResult> {
  // Determine if we need to spawn a subtask
  if (isComplexInput(input)) {
    // Return a continuation with subtask request
    return {
      content: "Need to process complex input with a specialized subtask",
      status: "CONTINUATION",
      notes: {
        subtask_request: {
          type: "atomic",
          description: "Process complex data structure",
          inputs: {
            data: input,
            format: "json",
            validation_rules: { required: ["id", "name"] }
          },
          template_hints: ["data_processor", "validator"],
          context_management: {
            inherit_context: "subset",
            fresh_context: "enabled"
          }
        }
      }
    };
  }
  
  // Process simple input directly
  return {
    content: `Processed: ${input}`,
    status: "COMPLETE",
    notes: { dataUsage: "Simple processing completed" }
  };
}
```
    
## Example with Explicit File Paths
    
```typescript
// Subtask with explicit files
return {
  status: "CONTINUATION",
  notes: {
    subtask_request: {
      type: "atomic",
      description: "Analyze code modules",
      inputs: { analysis_depth: "detailed" },
      context_management: { inherit_context: "subset" },
      file_paths: ["/src/main.py", "/src/utils.py"]
    }
  }
};
```
    
## Subtask Tool Implementation
    
```typescript
// Example of what happens internally in taskSystem.executeTask
async function internalTaskSystemFlow(task, context) {
  // Get or create a Handler
  const handler = this.getHandlerForTask(task);
  
  // Execute the initial prompt
  const result = await handler.executePrompt(task.taskPrompt);
  
  // Check for continuation
  if (result.status === "CONTINUATION" && result.notes?.subtask_request) {
    // Execute the subtask
    const subtaskResult = await this.executeSubtask(result.notes.subtask_request);
    
    // Add subtask result as a tool response to parent's session
    handler.addToolResponse(
      this.getToolNameFromRequest(result.notes.subtask_request),
      subtaskResult.content
    );
    
    // Continue parent execution
    return handler.executePrompt("Continue based on the tool results.");
  }
  
  return result;
}
```
    
## Tool vs. Subtask Implementation
    
```typescript
// Example of Handler registering both tool types
handler.registerDirectTool("readFile", async (path) => {
  return await fs.readFile(path, 'utf8');
});

handler.registerSubtaskTool("analyzeData", ["data_analysis", "statistical"]);

// LLM usage looks similar for both
const fileContent = tools.readFile("data.csv");
const analysis = tools.analyzeData({ 
  data: fileContent,
  method: "statistical"
});

// But implementations differ:
// Direct tool implementation (in Handler)
async function executeReadFile(path) {
  return await fs.readFile(path, 'utf8');
}

// Subtask tool implementation (via CONTINUATION)
async function executeAnalyzeData(params) {
  return {
    status: "CONTINUATION",
    notes: {
      subtask_request: {
        type: "atomic",
        description: `Analyze data using ${params.method}`,
        inputs: params,
        template_hints: ["data_analysis"]
      }
    }
  };
}
```
    
## Context Integration Example
    
```typescript
// TypeScript implementation showing context flow
async function executeWithContextIntegration() {
  // Execute parent task
  const parentResult = await taskSystem.executeTask(
    "<task><description>Analyze code repository structure</description></task>",
    memorySystem
  );
  
  // Check for continuation with subtask request
  if (parentResult.status === "CONTINUATION" && 
      parentResult.notes.subtask_request) {
    
    const subtaskRequest = parentResult.notes.subtask_request;
    
    // Context management settings from request (or defaults)
    const contextSettings = subtaskRequest.context_management || {
      inherit_context: "subset",
      fresh_context: "enabled"
    };
    
    // Get appropriate context based on settings
    let subtaskContext;
    if (contextSettings.inherit_context === "full") {
      subtaskContext = parentContext;
    } else if (contextSettings.inherit_context === "subset") {
      // Get relevant subset via associative matching
      subtaskContext = await memorySystem.getRelevantContextFor({
        taskText: subtaskRequest.description,
        inheritedContext: parentContext
      });
    } else {
      // No inherited context
      subtaskContext = null;
    }
    
    // Execute subtask with appropriate context
    const subtaskResult = await taskSystem.executeSubtask(
      subtaskRequest,
      subtaskContext
    );
    
    // Resume parent task with subtask result
    const finalResult = await taskSystem.resumeTask(
      parentResult,
      { subtask_result: subtaskResult }
    );
    
    console.log("Final analysis:", finalResult.content);
  }
}
```
    
## Related Documentation
    
For more details, see:
- [ADR 11: Subtask Spawning Mechanism](../../../../system/architecture/decisions/completed/011-subtask-spawning.md)
- [Pattern:ToolInterface:1.0](../../../../system/architecture/patterns/tool-interface.md)
- [Subtask Spawning Implementation](../design.md#subtask-spawning-implementation)
