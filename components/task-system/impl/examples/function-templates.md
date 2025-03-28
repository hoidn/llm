# Function Template Examples
    
This document contains examples of function-based templates in the Task System.
    
## Basic Function-Style Task Definition
    
```xml
<template name="validate_input" params="data,rules">
  <task>
    <description>Validate {{data}} against {{rules}}</description>
    <context_management>
      <inherit_context>none</inherit_context>
      <fresh_context>enabled</fresh_context>
    </context_management>
  </task>
</template>
```
    
## Function Call with Variable Arguments
    
```xml
<call template="validate_input">
  <arg>user_input</arg>        <!-- Resolved as variable if possible -->
  <arg>validation_schema</arg>  <!-- Or used as literal if no variable matches -->
</call>
```
    
## Function-Style Task with Return Type
    
```xml
<template name="extract_metrics" params="log_data" returns="object">
  <task>
    <description>Extract performance metrics from {{log_data}}</description>
    <output_format type="json" schema="object" />
  </task>
</template>
```
    
## Complex Function Composition
    
```xml
<task type="sequential">
  <steps>
    <task>
      <description>Load input data</description>
    </task>
    <call template="validate_input">
      <arg>loaded_data</arg>
      <arg>{"required": ["name", "email"], "format": {"email": "email"}}</arg>
    </call>
    <call template="process_validated_data">
      <arg>validation_result</arg>
      <arg>processing_options</arg>
    </call>
  </steps>
</task>
```
    
## Task with JSON Output Format
    
```xml
<task type="atomic">
  <description>List files in directory</description>
  <output_format type="json" schema="string[]" />
</task>
```
    
## Template with Return Type
    
```xml
<template name="get_file_info" params="filepath" returns="object">
  <task>
    <description>Get metadata for {{filepath}}</description>
    <output_format type="json" schema="object" />
  </task>
</template>
```
    
## Function Call with JSON Result
    
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
    
## TypeScript Implementation
    
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
  taskName: "analyze_data",
  arguments: [
    "data_file",         // Resolved to "sensor_readings.csv" from callerEnv
    "analysis_options"   // Resolved to the object from callerEnv
  ]
}, callerEnv);

// 4. Example with mixed variable/literal arguments
const mixedResult = await taskSystem.executeCall({
  taskName: "analyze_data",
  arguments: [
    "data_file",                     // Variable lookup
    {method: "custom", limit: 100}   // Direct literal (no lookup)
  ]
}, callerEnv);
```
    
## Related Documentation
    
For more details, see:
- [ADR 12: Function-Based Templates](../../../../system/architecture/decisions/completed/012-function-based-templates.md)
- [ADR 13: JSON Output](../../../../system/architecture/decisions/completed/013-json-output.md)
- [Function Template Implementation](../design.md#function-call-processing)
