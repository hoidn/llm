# Task System Implementation Examples

> **Important Note:** The examples in this document demonstrate that templates and function-based templates can define any task type (atomic, sequential, reduce, etc.). While all task types can be defined as templates, only atomic task templates participate in the template matching process used for task selection based on natural language descriptions. This distinction is important for understanding how tasks, templates, and functions interact in the system.

> **Note:** For a detailed description of the Director‑Evaluator pattern, refer to [system/architecture/patterns/director-evaluator.md](./docs/system/architecture/patterns/director-evaluator.md).

## Basic Task Execution
```typescript
// Initialize TaskSystem
const taskSystem = new TaskSystem({
  maxTurns: 10,
  maxContextWindowFraction: 0.8,
  systemPrompt: "Default system prompt"
});

// Register handlers
taskSystem.onError((error) => {
  console.error('Task error:', error);
});

taskSystem.onWarning((warning) => {
  console.warn('XML validation warning:', warning.message);
});

// Execute task
const result = await taskSystem.executeTask(
  "analyze data",
  memorySystem
);

// Check XML parsing status
if (!result.outputs.some(output => output.wasXMLParsed)) {
  console.warn("XML parsing failed, using fallback string output");
}
```

## Task Management
```typescript
const taskDef: TaskDefinition = {
  name: "process_data",
  type: "atomic",
  provider: "anthropic",
  model: "claude-3-sonnet",
  body: {
    type: "atomic",
    content: `<task>
      <description>Process data using specific format</description>
      <inputs>
        <input name="raw_data">
          <description>Load and validate input data</description>
          <expected_output>
            Validated data in standard format:
            - Field validations complete
            - Type conversions applied
            - Missing values handled
          </expected_output>
        </input>
      </inputs>
      <expected_output>
        Processed data meeting format requirements:
        - Correct structure
        - Valid field types
        - Complete required fields
      </expected_output>
    </task>`
  },
  metadata: {
    isManualXML: true,
    disableReparsing: true
  }
};

// Register the task
await taskSystem.registerTask(taskDef);

// Validate task
const validation = taskSystem.validateTask(taskDef);

if (!validation.valid) {
  console.warn('Task validation warnings:', validation.warnings);
}

// Find matching tasks
const matches = await taskSystem.findMatchingTasks(
  "analyze peak patterns",
  memorySystem
);

console.log('Found matching tasks:', 
  matches.map(m => ({
    score: m.score,
    type: m.task.type,
    name: m.task.name
  }))
);
```

## Resource Management
```typescript
// Configure with resource limits
const taskSystem = new TaskSystem({
  maxTurns: 5,
  maxContextWindowFraction: 0.5,
  systemPrompt: "Resource-constrained execution"
});

try {
  const result = await taskSystem.executeTask(
    "process large dataset",
    memorySystem
  );
} catch (error) {
  if (error.type === 'RESOURCE_EXHAUSTION') {
    console.log('Resource limit exceeded:', error.resource);
    console.log('Usage metrics:', error.metrics);
  }
}
```

## Output Format Examples

### Task with JSON Output Format
```xml
<task type="atomic">
  <description>List files in directory</description>
  <output_format type="json" schema="string[]" />
</task>
```

### Template with Return Type
```xml
<template name="get_file_info" params="filepath" returns="object">
  <task>
    <description>Get metadata for {{filepath}}</description>
    <output_format type="json" schema="object" />
  </task>
</template>
```

### Function Call with JSON Result
```xml
<task type="sequential">
  <steps>
    <task>
      <description>Get directory listing</description>
    </task>
    <call template="get_file_info">
      <arg>result[0]</arg>
    </call>
  </steps>
</task>
```

### TypeScript Example
```typescript
// Execute task with JSON output format
const result = await taskSystem.executeTask(
  "<task><description>List files</description><output_format type='json' schema='string[]'/></task>",
  memorySystem
);

// Check if content was parsed as JSON
if (result.parsedContent) {
  // Use the parsed content as a typed value
  const files: string[] = result.parsedContent;
  console.log(`Found ${files.length} files`);
  
  // Process the files array
  const textFiles = files.filter(file => file.endsWith('.txt'));
  console.log(`Text files: ${textFiles.join(', ')}`);
} else {
  // Fall back to string content
  console.log(`Raw output: ${result.content}`);
}
```

## Task Definition and Function Calling

### Basic Function-Style Task Definition
```xml
<task name="validate_input" type="atomic" parameters="data,rules">
  <description>Validate {{data}} against {{rules}}</description>
  <context_management>
    <inherit_context>none</inherit_context>
    <fresh_context>enabled</fresh_context>
  </context_management>
</task>
```

### Context Management Mutual Exclusivity Examples

```xml
<!-- Valid: inherit_context="none" and fresh_context="enabled" -->
<task type="atomic">
  <description>Process data with fresh context only</description>
  <context_management>
    <inherit_context>none</inherit_context>
    <accumulate_data>false</accumulate_data>
    <fresh_context>enabled</fresh_context>
  </context_management>
</task>

<!-- Valid: inherit_context="full" and fresh_context="disabled" -->
<task type="atomic">
  <description>Process data with inherited context only</description>
  <context_management>
    <inherit_context>full</inherit_context>
    <accumulate_data>false</accumulate_data>
    <fresh_context>disabled</fresh_context>
  </context_management>
</task>

<!-- Invalid: inherit_context="full" and fresh_context="enabled" -->
<!-- This would cause validation failure -->
<task type="atomic">
  <description>Invalid combination</description>
  <context_management>
    <inherit_context>full</inherit_context>
    <accumulate_data>false</accumulate_data>
    <fresh_context>enabled</fresh_context>
  </context_management>
</task>
```

### Function Call with Variable Arguments
/**
 * Function Call XML Syntax
 * 
 * Arguments are evaluated in the caller's environment before being passed to the task:
 */
```xml
<call task="validate_input">
  <arg>user_input</arg>        <!-- Resolved as variable if possible -->
  <arg>validation_schema</arg>  <!-- Or used as literal if no variable matches -->
</call>
```

### Function-Style Task with Return Type
```xml
<task name="extract_metrics" type="atomic" parameters="log_data" returns="object">
  <description>Extract performance metrics from {{log_data}}</description>
  <output_format type="json" schema="object" />
</task>
```

### Complex Function Composition
```xml
<task type="sequential">
  <steps>
    <task>
      <description>Load input data</description>
    </task>
    <call task="validate_input">
      <arg>loaded_data</arg>
      <arg>{"required": ["name", "email"], "format": {"email": "email"}}</arg>
    </call>
    <call task="process_validated_data">
      <arg>validation_result</arg>
      <arg>processing_options</arg>
    </call>
  </steps>
</task>
```

/**
 * Function-Style Task and Call Example
 */
```typescript
// 1. Register function-style task with explicit parameters
await taskSystem.registerTask({
  name: "analyze_data",
  type: "atomic",
  parameters: ["dataset", "config"],  // Explicitly declared parameters
  body: {
    type: "atomic",
    content: "Analyze {{dataset}} using {{config}}",
  },
  returns: "object",
  provider: "anthropic"
});

// 2. Setup caller environment with variables
const callerEnv = new Environment({
  data_file: "sensor_readings.csv",
  analysis_options: {method: "statistical", outliers: "remove"}
});

// 3. Execute call with arguments evaluated in caller's environment
const result = await taskSystem.executeCall({
  taskName: "analyze_data",  // Changed from templateName to taskName
  arguments: [
    "data_file",         // Resolved to "sensor_readings.csv" from callerEnv
    "analysis_options"   // Resolved to the object from callerEnv
  ]
}, callerEnv);

// 4. Example with mixed variable/literal arguments
const mixedResult = await taskSystem.executeCall({
  taskName: "analyze_data",  // Changed from templateName to taskName
  arguments: [
    "data_file",                     // Variable lookup
    {method: "custom", limit: 100}   // Direct literal (no lookup)
  ]
}, callerEnv);
```

## Global Index Example
```typescript
// Minimal memory object focusing on file metadata
const memory = {
  getGlobalIndex() {
    return new Map([
      ['data.txt', 'metadata'],
      ['config.json', 'metadata'],
      ['history.log', 'metadata']
    ]);
  },
  updateGlobalIndex(index) {}
};

// Now we can pass this memory object to the taskSystem
const result = await taskSystem.executeTask("analyze recent changes", memory);
```

## Specialized Task Types

### Reparse Task Example
```typescript
const reparseTemplate: TaskTemplate = {
  taskPrompt: `<task type="reparse">
    <description>Decompose large task into smaller units</description>
    <failed_task>
      <error type="RESOURCE_EXHAUSTION">
        <resource>context</resource>
        <message>Context window limit exceeded</message>
      </error>
      <original_prompt>Process entire codebase</original_prompt>
    </failed_task>
  </task>`,
  systemPrompt: "Decomposition specialist",
  model: "claude-3-sonnet",
  isManualXML: true
};

try {
  const result = await taskSystem.executeTask(
    reparseTemplate.taskPrompt,
    memorySystem,
    "reparse"
  );
} catch (error) {
  console.error('Reparse failed:', error);
}
```

### Memory Task Example
```typescript
const memoryTemplate: TaskTemplate = {
  taskPrompt: `<task type="associative_memory">
    <description>Find relevant context for implementation</description>
    <query>error handling patterns</query>
    <constraints>
      <max_results>3</max_results>
      <relevance_threshold>0.8</relevance_threshold>
    </constraints>
  </task>`,
  systemPrompt: "Context retrieval specialist",
  model: "claude-3-sonnet"
};

const memoryResult = await taskSystem.executeTask(
  memoryTemplate.taskPrompt,
  memorySystem,
  "associative_memory"
);

console.log('Retrieved context:', memoryResult.content);
```

---

// Example of error handling with simplified structure
try {
  const result = await taskSystem.executeTask(taskDefinition, memorySystem);
  // Success case: content is complete
  console.log("Task completed successfully:", result.content);
} catch (error) {
  if (error.type === 'RESOURCE_EXHAUSTION') {
    console.log(`Resource limit exceeded: ${error.resource}`);
  } else if (error.type === 'TASK_FAILURE') {
    // Access partial content directly from content field
    console.log(`Partial output before failure: ${error.content}`);
    console.log(`Execution stage: ${error.notes.executionStage || "unknown"}`);
    console.log(`Completion: ${error.notes.completionPercentage || 0}%`);
  }
}

<!-- Example: Sequential Task with Default Context Management -->
<task type="sequential">
    <description>Process and analyze data</description>
    <!-- No context_management block - using defaults:
         inherit_context: full
         accumulate_data: true
         accumulation_format: notes_only
         fresh_context: enabled -->
    <steps>
        <task>
            <description>Load dataset</description>
            <inputs>
                <input name="data_file" from="csv_file_path"/>
            </inputs>
        </task>
        <task>
            <description>Filter invalid rows</description>
        </task>
    </steps>
</task>

<!-- Example: Sequential Task with Custom Context Management -->
<task type="sequential">
    <description>Process and analyze data</description>
    <context_management>
        <inherit_context>none</inherit_context>
        <accumulate_data>true</accumulate_data>
        <accumulation_format>full_output</accumulation_format>
        <fresh_context>enabled</fresh_context>
    </context_management>
    <steps>
        <task>
            <description>Load dataset</description>
            <inputs>
                <input name="data_file" from="csv_file_path"/>
            </inputs>
        </task>
        <task>
            <description>Filter invalid rows</description>
        </task>
    </steps>
</task>

<!-- Example: Static Director-Evaluator Loop with Script Execution -->
<task type="director_evaluator_loop">
  <description>Process and evaluate code</description>
  <max_iterations>3</max_iterations>
  <context_management>
    <inherit_context>none</inherit_context>
    <accumulate_data>true</accumulate_data>
    <accumulation_format>notes_only</accumulation_format>
    <fresh_context>enabled</fresh_context>
  </context_management>
  <director>
    <description>Generate Python code to solve problem: {{problem_statement}}</description>
    <inputs>
      <input name="problem_statement" from="user_query"/>
      <input name="feedback" from="evaluation_feedback"/>
      <input name="iteration" from="current_iteration"/>
    </inputs>
  </director>
  <script_execution>
    <command>python3 -c "{{script_input}}"</command>
    <timeout>5</timeout>
    <inputs>
      <input name="script_input" from="director_result"/>
    </inputs>
  </script_execution>
  <evaluator>
    <description>Evaluate code quality and execution results</description>
    <inputs>
      <input name="code" from="director_result"/>
      <input name="execution_output" from="script_output"/>
      <input name="execution_errors" from="script_errors"/>
      <input name="exit_code" from="script_exit_code"/>
    </inputs>
  </evaluator>
  <termination_condition>
    <condition>evaluation.success === true || iteration >= 3</condition>
  </termination_condition>
</task>

## Subtask Spawning Examples

### Basic Subtask Request Example

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

// Example of subtask tool execution
async function executeWithSubtasks() {
  // Create a Handler with session preservation
  const handler = new Handler(handlerConfig);
  
  // Register subtask tool
  handler.registerSubtaskTool("analyzeData", ["data_analysis", "statistical"]);
  
  // Execute the task (internal handling of continuations)
  const result = await taskSystem.executeTask("process complex data", memorySystem);
  
  // TaskSystem automatically:
  // 1. Detects CONTINUATION status
  // 2. Executes the subtask
  // 3. Adds result as tool response to parent's session
  // 4. Continues parent execution
  
  console.log("Final result:", result.content);
}

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

### Example with Explicit File Paths

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
```

### Error Handling Example

```typescript
// Simplified error handling example
try {
  const result = await taskSystem.executeTask("analyze complex document");
  console.log("Analysis complete:", result.content);
} catch (error) {
  // Standard error types without complex partial results
  if (error.type === 'RESOURCE_EXHAUSTION') {
    console.log(`Resource limit exceeded: ${error.resource}`);
  } else if (error.type === 'TASK_FAILURE') {
    console.log(`Task failed: ${error.message}`);
    
    // If this was a subtask failure, the error contains the original request
    if (error.reason === 'subtask_failure') {
      console.log(`Failed subtask: ${error.details.subtaskRequest.description}`);
    }
  }
}
```

### Context Integration Example

```xml
<!-- Parent task that spawns a subtask -->
<task type="atomic">
  <description>Analyze code repository structure</description>
  <context_management>
    <inherit_context>full</inherit_context>
    <fresh_context>enabled</fresh_context>
  </context_management>
  
  <!-- This task will return CONTINUATION status with a subtask_request -->
</task>

<!-- Example of how the subtask request would be structured -->
<!-- This is not XML that would be written directly, but represents
     the structure that would be in the subtask_request -->
<task type="atomic">
  <description>Analyze specific module dependencies</description>
  <context_management>
    <inherit_context>subset</inherit_context>
    <fresh_context>enabled</fresh_context>
  </context_management>
  <inputs>
    <input name="module_path" from="parent_analysis.target_module"/>
    <input name="depth" from="parent_analysis.analysis_depth"/>
  </inputs>
</task>
```

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

<!-- Example: Context Management Patterns -->

<!-- Pattern 1: Clear All Context (Fresh Start) -->
<task type="atomic">
    <description>Start with completely fresh context</description>
    <context_management>
        <inherit_context>none</inherit_context>
        <accumulate_data>false</accumulate_data>
        <fresh_context>enabled</fresh_context>
    </context_management>
</task>

## Unified Tool Interface Examples

### Direct vs. Subtask Tool Examples

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

<!-- Pattern 2: Rebuild Context While Preserving History -->
<task type="sequential">
    <description>Rebuild context while keeping step history</description>
    <context_management>
        <inherit_context>none</inherit_context>
        <accumulate_data>true</accumulate_data>
        <accumulation_format>notes_only</accumulation_format>
        <fresh_context>enabled</fresh_context>
    </context_management>
    <steps>
        <task>
            <description>First step</description>
        </task>
        <task>
            <description>Second step with fresh context but notes from first step</description>
        </task>
    </steps>
</task>

<!-- Pattern 3: Complete Context Preservation -->
<task type="sequential">
    <description>Preserve all context</description>
    <context_management>
        <inherit_context>full</inherit_context>
        <accumulate_data>true</accumulate_data>
        <accumulation_format>full_output</accumulation_format>
        <fresh_context>disabled</fresh_context>
    </context_management>
    <steps>
        <task>
            <description>First step</description>
        </task>
        <task>
            <description>Second step with all context preserved</description>
        </task>
    </steps>
</task>

```typescript
// Example of context pattern usage in TypeScript

// Pattern 1: Clear All Context (Fresh Start)
const clearContextResult = await taskSystem.executeTask(
  "<task type='atomic'><description>Fresh context task</description><context_management><inherit_context>none</inherit_context><accumulate_data>false</accumulate_data><fresh_context>enabled</fresh_context></context_management></task>",
  memorySystem
);

// Pattern 2: Rebuild Context While Preserving History
const rebuildWithHistoryResult = await taskSystem.executeTask(
  "<task type='sequential'><description>Sequential with history</description><context_management><inherit_context>none</inherit_context><accumulate_data>true</accumulate_data><fresh_context>enabled</fresh_context></context_management></task>",
  memorySystem
);

// Pattern 3: Complete Context Preservation
const preserveAllContextResult = await taskSystem.executeTask(
  "<task type='sequential'><description>Preserve all context</description><context_management><inherit_context>full</inherit_context><accumulate_data>true</accumulate_data><fresh_context>disabled</fresh_context></context_management></task>",
  memorySystem
);
```

## File Paths Examples

### Atomic Task with File Paths

```xml
<!-- Example: Atomic Task with File Paths -->
<task type="atomic">
    <description>Analyze the main source files</description>
    <context_management>
        <inherit_context>none</inherit_context>
        <fresh_context>disabled</fresh_context>
    </context_management>
    <file_paths>
        <path>./src/main.py</path>
        <path>./src/utils.py</path>
    </file_paths>
</task>
```

### TypeScript Usage Example

```typescript
// Execute atomic task with specific file paths
const result = await taskSystem.executeTask(
  "<task type='atomic'><description>Analyze source files</description><file_paths><path>./src/main.py</path><path>./src/utils.py</path></file_paths></task>",
  memorySystem
);

// Create subtask request with file paths
return {
  status: "CONTINUATION",
  notes: {
    subtask_request: {
      type: "atomic",
      description: "Analyze specific modules",
      inputs: { level: "detailed" },
      context_management: { inherit_context: "subset" },
      file_paths: ["./src/main.py", "./src/utils.py"]
    }
  }
};
```

### Combining File Paths with Context Management

```xml
<!-- Example: Combining File Paths with fresh_context -->
<task type="atomic">
    <description>Analyze code with base context and specific files</description>
    <context_management>
        <inherit_context>none</inherit_context>
        <fresh_context>enabled</fresh_context>
    </context_management>
    <file_paths>
        <path>./src/main.py</path>
        <path>./src/utils.py</path>
    </file_paths>
</task>
```

This combination:
1. Doesn't inherit any parent context
2. Explicitly includes the specified files
3. Uses associative matching to find additional relevant context
