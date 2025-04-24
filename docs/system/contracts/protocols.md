# System Protocols

## Overview

This document defines the core protocols used throughout the system for task execution, communication, and integration. It includes:

- XML schema for task templates
- Subtask spawning protocol
- LLM interaction protocol
- Cross-component communication standards

## Task Template Schema [Contract:Tasks:TemplateSchema:1.0]

**Note:** This document is the authoritative specification for the XML schema used to define **atomic task templates**. All workflow composition (sequences, loops, conditionals, etc.) is handled by the S-expression DSL, not by XML structure.

The atomic task template schema defines the structure for XML files that represent single, executable LLM or system tasks.

### S-expression DSL for Composition
Task composition, control flow, and multi-step workflows are defined using an S-expression based Domain Specific Language (DSL). This DSL provides primitives for binding variables (`bind`, `let`), conditional execution (`if`), mapping (`map`), calling atomic tasks (`call-atomic-task`), invoking system tools (`system:run_script`), and potentially looping or recursion. Please refer to the S-expression DSL documentation [Link TBD] for its syntax and semantics.

### Atomic Task XML Schema Definition

The following schema defines the structure for `<task type="atomic">` elements.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">

  <!-- Define complex types for reusable elements first -->
  <xs:complexType name="OutputType">
    <xs:attribute name="type" use="required">
      <xs:simpleType>
        <xs:restriction base="xs:string">
          <xs:enumeration value="json"/>
          <xs:enumeration value="text"/>
        </xs:restriction>
      </xs:simpleType>
    </xs:attribute>
    <xs:attribute name="schema" type="xs:string" use="optional"/>
  </xs:complexType>

  <xs:complexType name="ContextManagementType">
    <xs:sequence>
      <xs:element name="inherit_context">
        <xs:simpleType>
          <xs:restriction base="xs:string">
            <xs:enumeration value="full"/>
            <xs:enumeration value="none"/>
            <xs:enumeration value="subset"/>
          </xs:restriction>
        </xs:simpleType>
      </xs:element>
      <xs:element name="accumulate_data" type="xs:boolean"/>
      <xs:element name="accumulation_format">
        <xs:simpleType>
          <xs:restriction base="xs:string">
            <!-- When 'full_output' is specified, complete content+notes are preserved -->
            <xs:enumeration value="full_output"/>
            <!-- When 'notes_only' is specified, only essential metadata is preserved -->
            <xs:enumeration value="notes_only"/>
          </xs:restriction>
        </xs:simpleType>
      </xs:element>
      <xs:element name="fresh_context">
        <xs:simpleType>
          <xs:restriction base="xs:string">
            <xs:enumeration value="enabled"/>
            <xs:enumeration value="disabled"/>
          </xs:restriction>
        </xs:simpleType>
      </xs:element>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="FilePathsSourceType">
     <xs:choice>
       <xs:sequence>
         <xs:element name="path" type="xs:string" maxOccurs="unbounded"/>
       </xs:sequence>
       <xs:element name="command" type="xs:string"/>
       <xs:element name="description" type="xs:string"/>
       <!-- When source="context_description", this element holds the query string -->
       <xs:element name="context_query" type="xs:string"/>
     </xs:choice>
     <xs:attribute name="source" use="optional" default="literal">
       <xs:simpleType>
         <xs:restriction base="xs:string">
           <xs:enumeration value="literal"/>
           <xs:enumeration value="command"/>
           <xs:enumeration value="description"/>
           <xs:enumeration value="context_description"/>
         </xs:restriction>
       </xs:simpleType>
     </xs:attribute>
  </xs:complexType>

  <xs:complexType name="InputsType">
    <xs:sequence>
      <xs:element name="input" maxOccurs="unbounded">
        <xs:complexType>
          <xs:simpleContent>
            <xs:extension base="xs:string">
              <xs:attribute name="name" type="xs:string" use="required"/>
              <xs:attribute name="from" type="xs:string" use="optional"/>
            </xs:extension>
          </xs:simpleContent>
        </xs:complexType>
      </xs:element>
    </xs:sequence>
  </xs:complexType>

  <xs:complexType name="ContextRelevanceType">
     <xs:sequence>
       <xs:element name="input" maxOccurs="unbounded">
         <xs:complexType>
           <xs:attribute name="name" type="xs:string" use="required"/>
           <xs:attribute name="include" type="xs:boolean" use="required"/>
         </xs:complexType>
       </xs:element>
     </xs:sequence>
  </xs:complexType>

  <xs:complexType name="ContextAssemblyType">
     <xs:sequence>
       <xs:element name="primary_elements" type="xs:string" minOccurs="0"/>
       <xs:element name="secondary_elements" type="xs:string" minOccurs="0"/>
       <xs:element name="excluded_elements" type="xs:string" minOccurs="0"/>
     </xs:sequence>
  </xs:complexType>

  <!-- Main Atomic Task Definition -->
  <xs:element name="task">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="description" type="xs:string"/>
        <xs:element name="provider" type="xs:string" minOccurs="0"/>
        <xs:element name="model" type="xs:string" minOccurs="0"/> <!-- Added model -->
        <xs:element name="instructions" type="xs:string" minOccurs="0"/> <!-- Added instructions (taskPrompt) -->
        <xs:element name="system" type="xs:string" minOccurs="0"/> <!-- Added system (systemPrompt) -->
        <xs:element name="output_slot" type="xs:string" minOccurs="0"/>
        <xs:element name="input_source" type="xs:string" minOccurs="0"/>
        <xs:element name="output_format" type="OutputType" minOccurs="0"/>
        <xs:element name="context_management" type="ContextManagementType" minOccurs="0"/> <!-- Made optional, defaults apply -->
        <xs:element name="file_paths" type="FilePathsSourceType" minOccurs="0"/>
        <xs:element name="inputs" type="InputsType" minOccurs="0"/>
        <xs:element name="context_relevance" type="ContextRelevanceType" minOccurs="0"/>
        <xs:element name="context_assembly" type="ContextAssemblyType" minOccurs="0"/>
        <xs:element name="manual_xml" type="xs:boolean" minOccurs="0" default="false"/>
        <xs:element name="disable_reparsing" type="xs:boolean" minOccurs="0" default="false"/>
        <xs:element name="criteria" type="xs:string" minOccurs="0"/> <!-- Added criteria -->
      </xs:sequence>
      <xs:attribute name="ref" type="xs:string" use="optional"/>
      <xs:attribute name="subtype" type="xs:string" use="optional"/> <!-- e.g., standard, subtask, director, evaluator -->
      <xs:attribute name="type" use="required">
        <xs:simpleType>
          <xs:restriction base="xs:string">
            <xs:enumeration value="atomic"/>
            <!-- Removed sequential, reduce, director_evaluator_loop -->
            <!-- Keep script if it's fundamentally atomic? Let's assume script is handled by S-exp call for now -->
            <!-- <xs:enumeration value="script"/> -->
          </xs:restriction>
        </xs:simpleType>
      </xs:attribute>
    </xs:complexType>
  </xs:element>

  <!-- Function Template Definition (if kept alongside S-expressions) -->
  <!-- These define reusable atomic task structures callable via S-expression -->
  <xs:element name="template">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="name" type="xs:string"/>
        <xs:element name="params" type="xs:string"/> <!-- Comma-separated list -->
        <xs:element name="returns" type="xs:string" minOccurs="0"/>
        <!-- The body MUST be an atomic task -->
        <xs:element ref="task"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>

  <!-- Function Call (Invoked via S-expression, XML structure might be deprecated) -->
  <!-- Kept for now, assuming S-exp might parse/use this structure internally -->
  <xs:element name="call">
     <xs:complexType>
       <xs:sequence>
         <xs:element name="template" type="xs:string"/> <!-- Name of the <template> to call -->
         <xs:element name="arg" type="xs:string" maxOccurs="unbounded"/> <!-- Positional arguments -->
       </xs:sequence>
     </xs:complexType>
  </xs:element>

  <!-- Error Response Schema (Remains relevant) -->
  <xs:complexType name="TaskError">
     <xs:choice>
       <xs:element name="resource_exhaustion">
         <xs:complexType>
           <xs:sequence>
             <xs:element name="resource" type="xs:string"/>
             <xs:element name="message" type="xs:string"/>
             <xs:element name="metrics" type="xs:anyType" minOccurs="0"/> <!-- Define MetricsType if needed -->
           </xs:sequence>
         </xs:complexType>
       </xs:element>
       <xs:element name="task_failure">
         <xs:complexType>
           <xs:sequence>
             <xs:element name="reason" type="TaskFailureReason"/>
             <xs:element name="message" type="xs:string"/>
             <xs:element name="details" type="xs:anyType" minOccurs="0"/> <!-- Define DetailsType if needed -->
           </xs:sequence>
         </xs:complexType>
       </xs:element>
     </xs:choice>
  </xs:complexType>

  <xs:simpleType name="TaskFailureReason">
     <xs:restriction base="xs:string">
       <xs:enumeration value="context_retrieval_failure"/>
       <xs:enumeration value="context_matching_failure"/>
       <xs:enumeration value="context_parsing_failure"/>
       <xs:enumeration value="xml_validation_failure"/>
       <xs:enumeration value="output_format_failure"/>
       <xs:enumeration value="execution_timeout"/>
       <xs:enumeration value="execution_halted"/>
       <xs:enumeration value="subtask_failure"/>
       <xs:enumeration value="input_validation_failure"/>
       <xs:enumeration value="unexpected_error"/>
       <!-- Add S-expression specific reasons if needed -->
     </xs:restriction>
  </xs:simpleType>

</xs:schema>
            <!-- When 'full_output' is specified, complete content+notes are preserved -->
            <xs:enumeration value="full_output"/>
            <!-- When 'notes_only' is specified, only essential metadata is preserved -->
            <xs:enumeration value="notes_only"/>
<!-- Removed complexType definitions for steps, inner_task, reduction_task, director_evaluator_loop, cond, case -->
<!-- Removed script execution example within sequential task -->

### Aider Integration Templates (Atomic)

These remain valid as they are atomic tasks.

#### Interactive Mode Template
```xml
<task type="atomic" subtype="aider_interactive">
  <description>Start interactive Aider session for {{task_description}}</description>
  <context_management>
    <inherit_context>subset</inherit_context>
    <accumulate_data>true</accumulate_data> <!-- Note: accumulate_data primarily affects sequential/reduce history, less relevant for single atomic task unless part of larger S-exp flow -->
    <accumulation_format>notes_only</accumulation_format>
    <fresh_context>enabled</fresh_context>
  </context_management>
  <inputs>
    <input name="initial_query" from="user_query"/>
  </inputs>
  <file_paths source="context_description">
     <context_query>Files relevant to: {{task_description}}</context_query>
  </file_paths>
</task>
```

#### Automatic Mode Template
```xml
<task type="atomic" subtype="aider_automatic">
  <description>Execute Aider code editing for {{task_description}}</description>
  <context_management>
    <inherit_context>subset</inherit_context>
    <accumulate_data>false</accumulate_data>
    <accumulation_format>notes_only</accumulation_format>
    <fresh_context>enabled</fresh_context>
  </context_management>
  <inputs>
    <input name="prompt" from="user_query"/>
  </inputs>
   <file_paths source="context_description">
     <context_query>Files relevant to: {{task_description}}</context_query>
  </file_paths>
</task>
```

In both templates:
- The `file_paths` element is populated either by associative matching (using `context_description` source) or explicit specification.
- The `subtype` attribute determines whether Aider runs in interactive or automatic mode.
- Context management settings control how context is prepared for this specific atomic task execution.

### Script Execution Support (via S-expression)

Executing external scripts is now handled by invoking a specific primitive within the S-expression DSL, for example: `(system:run_script "bash_command" (input director_output.content))`.

The S-expression workflow manages passing inputs (like director output) to the script primitive and capturing its results (stdout, stderr, exit code) for subsequent steps (like evaluation). Script execution errors result in a `TASK_FAILURE` from the primitive, allowing the S-expression to handle it.

### Output Format Specification (for Atomic Tasks)

Tasks can specify structured output format:

```xml
<task>
  <description>List files in directory</description>
  <output_format type="json" schema="string[]" />
</task>
```

The `schema` attribute provides basic type information:
- "object" - JSON object
- "array" or "[]" - JSON array
- "string[]" - Array of strings
- "number" - Numeric value
- "boolean" - Boolean value

Initial implementation provides basic type validation to ensure the result matches the specified type. When validation fails, a structured error is returned with error_type, message, and location information. More comprehensive schema validation may be implemented in future phases as needed.

When output_format type is "json", the system will:
1. Attempt to parse the content as JSON
2. Store the parsed result in the parsedContent property of TaskResult
3. Keep the original string content in the content property
4. Record any parsing errors in notes.parseError

Output validation ensures the result matches the specified type.

## Subtask Spawning Protocol [Protocol:SubtaskSpawning:1.0]

The subtask spawning protocol defines how tasks can dynamically create and execute subtasks.

### Request Structure

```typescript
interface SubtaskRequest {
  // Required fields
  type: TaskType;                      // Type of subtask to spawn
  description: string;                 // Description of the subtask
  inputs: Record<string, any>;         // Input parameters for the subtask
  
  // Optional fields
  template_hints?: string[];           // Hints for template selection
  context_management?: {               // Override default context settings
    inherit_context?: 'full' | 'none' | 'subset';
    accumulate_data?: boolean;
    accumulation_format?: 'notes_only' | 'full_output';
    fresh_context?: 'enabled' | 'disabled';
  };
  max_depth?: number;                  // Override default max nesting depth
  subtype?: string;                    // Optional subtype for atomic tasks
  file_paths?: string[];               // Specific files to include in context
}
```

### Execution Flow

1. **Request Generation**: A parent task returns a result with `status: "CONTINUATION"` and includes a `subtask_request` in its notes.

2. **Request Validation**: The system validates the subtask request structure, ensuring all required fields are present and correctly formatted.

3. **Template Selection**: The system selects an appropriate template based on:
   - The `type` and optional `subtype` fields
   - The `description` field for associative matching
   - Any provided `template_hints`

4. **Depth Control**: The system checks:
   - Current nesting depth against maximum allowed depth (default: 5)
   - Cycle detection to prevent recursive spawning of identical tasks
   - Resource usage across the entire subtask chain

5. **Subtask Execution**: The system executes the subtask with:
   - Direct parameter passing from the `inputs` field
   - Context management according to defaults or overrides
   - Resource tracking linked to the parent task

6. **Result Handling**: The subtask result is passed back to the parent task when execution resumes, with the parent receiving the complete TaskResult structure.

### Default Context Management Settings

Subtasks have specific default context management settings:

| Setting | Default Value | Description |
|---------|---------------|-------------|
| inherit_context | subset | Inherits only relevant context from parent |
| accumulate_data | false | Does not accumulate previous step outputs |
| accumulation_format | notes_only | Stores only summary information |
| fresh_context | enabled | Generates new context via associative matching |

## LLM Interaction Protocol [Protocol:LLMInteraction:1.0]

The Handler-LLM interaction follows a standardized protocol using the `HandlerPayload` structure:

```typescript
interface HandlerPayload {
  systemPrompt: string;
  messages: Array<{
    role: "user" | "assistant" | "system";
    content: string;
    timestamp?: Date;
  }>;
  context?: string;        // Context from Memory System
  tools?: ToolDefinition[]; // Available tools
  metadata?: {
    model: string;
    temperature?: number;
    maxTokens?: number;
    resourceUsage: ResourceMetrics;
  };
}
```

### Protocol Flow

1. The Task System creates a Handler instance with configuration
2. The Handler creates a HandlerSession to manage conversation state
3. The Evaluator ensures all placeholders are substituted
4. The Handler constructs a HandlerPayload via session.constructPayload()
5. Provider-specific adapters transform the payload to appropriate formats
6. LLM response is processed via handler.processLLMResponse()
7. Tool calls (including user input requests) are handled
8. Session state is updated with new messages
9. Resource usage is tracked and limits enforced

This standardized protocol ensures consistent handling of LLM interactions across different providers while maintaining proper conversation tracking and resource management.

### Request Structure

```typescript
interface SubtaskRequest {
  // Required fields
  type: TaskType;                      // Type of subtask to spawn
  description: string;                 // Description of the subtask
  inputs: Record<string, any>;         // Input parameters for the subtask
  
  // Optional fields
  template_hints?: string[];           // Hints for template selection
  context_management?: {               // Override default context settings
    inherit_context?: 'full' | 'none' | 'subset';
    accumulate_data?: boolean;
    accumulation_format?: 'notes_only' | 'full_output';
    fresh_context?: 'enabled' | 'disabled';
  };
  max_depth?: number;                  // Override default max nesting depth
  subtype?: string;                    // Optional subtype for atomic tasks
  
  /**
   * Optional list of specific file paths to include in subtask context.
   * Takes precedence over associative matching when provided.
   * Paths can be absolute or relative to repo root.
   * Invalid paths will generate warnings but execution will continue.
   */
  file_paths?: string[];
}
```

### Execution Flow

1. **Request Generation**: A parent task returns a result with `status: "CONTINUATION"` and includes a `subtask_request` in its notes.

2. **Request Validation**: The system validates the subtask request structure, ensuring all required fields are present and correctly formatted.

3. **Template Selection**: The system selects an appropriate template based on:
   - The `type` and optional `subtype` fields
   - The `description` field for associative matching
   - Any provided `template_hints`

4. **Depth Control**: The system checks:
   - Current nesting depth against maximum allowed depth (default: 5)
   - Cycle detection to prevent recursive spawning of identical tasks
   - Resource usage across the entire subtask chain

5. **Subtask Execution**: The system executes the subtask with:
   - Direct parameter passing from the `inputs` field
   - Context management according to defaults or overrides
   - Resource tracking linked to the parent task

6. **Result Handling**: The subtask result is passed back to the parent task when execution resumes, with the parent receiving the complete TaskResult structure.

### Error Handling

If a subtask fails, a standardized error structure is generated:

```typescript
{
  type: 'TASK_FAILURE',
  reason: 'subtask_failure',
  message: 'Subtask execution failed',
  details: {
    subtaskRequest: SubtaskRequest;    // The original request
    subtaskError: TaskError;           // The error from the subtask
    nestingDepth: number;              // Current nesting depth
    partialOutput?: string;            // Any partial output if available
  }
}
```

This structure preserves the complete error context, allowing for potential recovery strategies.

### Depth Control Mechanisms

To prevent infinite recursion and resource exhaustion:

1. **Maximum Nesting Depth**: Default limit of 5 levels of nested subtasks
2. **Cycle Detection**: Prevention of tasks spawning identical subtasks
3. **Resource Tracking**: Monitoring of total resource usage across the subtask chain
4. **Timeout Enforcement**: Overall time limits for the complete subtask chain

These mechanisms ensure that subtask spawning remains controlled and resource-efficient.

### Function-Based Templates

The XML schema now supports function-based templates with explicit parameter declarations:

```xml
<template name="analyze_data" params="dataset,config">
  <task>
    <description>Analyze {{dataset}} using {{config}}</description>
  </task>
</template>
```

And function calls with positional arguments:

```xml
<call template="analyze_data">
  <arg>weather_data</arg>
  <arg>standard_config</arg>
</call>
```

This enforces strict scope boundaries - templates can only access explicitly passed parameters.

### Template-Level Function Call Syntax

In addition to the structured XML syntax, the system supports an inline function call syntax within template fields that use variable substitution:

```
{{function_name(arg1, arg2, named_arg=value)}}
```

This syntax can be used in fields like `description`, `taskPrompt` (instructions), and `systemPrompt`:

```xml
<description>Analysis results: {{calculate_metrics(data, method="advanced")}}</description>
```

Both syntaxes are internally processed using the same execution flow. The template-level syntax is parsed and translated into the standard FunctionCallNode structure before execution.

#### Function Call Argument Types

Both XML and template-level function calls support the same argument types:
- String literals: `"value"` or `'value'`
- Numbers: `123` or `45.67`
- Boolean literals: `true` or `false`
- Null values: `null`
- Variables: `variable_name` or `{{variable_name}}`
- Named arguments: `name="value"` or `name=variable_name`

#### Usage Guidance

- **XML Syntax**: Preferred for standalone function calls or when the result needs to be used as a structured value
- **Template Syntax**: Preferred for embedding function calls within text fields or for simple function invocations

Both syntaxes are supported and maintained, with the same execution semantics and environment handling.

#### Parameter Resolution

- Parameter names are declared in the comma-separated `params` attribute
- Inside templates, `{{...}}` placeholders only reference declared parameters
- Arguments are evaluated in the caller's environment before being passed to the template
- String arguments can be either variable references or literal values

#### Return Types

Templates can optionally specify a return type using the `returns` attribute:

```xml
<template name="get_file_info" params="filepath" returns="object">
  <task>
    <description>Get metadata for {{filepath}}</description>
    <output_format type="json" schema="object" />
  </task>
</template>
```

This aids in type validation and enables better composition between templates.

### Output Format Specification

Tasks can specify structured output format:

```xml
<task>
  <description>List files in directory</description>
  <output_format type="json" schema="string[]" />
</task>
```

The `schema` attribute provides basic type information:
- "object" - JSON object
- "array" or "[]" - JSON array
- "string[]" - Array of strings
- "number" - Numeric value
- "boolean" - Boolean value

Output validation ensures the result matches the specified type.

### Context Management Configuration (for Atomic Tasks)

The optional `<context_management>` element within an atomic task's XML definition controls how context is prepared *for that specific task's execution*.

```xml
<context_management>
    <inherit_context>full|none|subset</inherit_context>
    <accumulate_data>true|false</accumulate_data> <!-- Primarily relevant for how Handler manages context during execution, less about multi-step accumulation -->
    <accumulation_format>notes_only|full_output</accumulation_format> <!-- Affects potential partial result format on failure -->
    <fresh_context>enabled|disabled</fresh_context>
</context_management>
```
If omitted, the defaults for the specific atomic task subtype apply (see table below).

## XML Validation Rules (for Atomic Tasks)

### Required Field Validation
- All required fields must be present
- Input names must be unique
- Boolean fields must be "true" or "false"
- Model must be a valid LLM identifier

### Context Management Constraints
1. **Mutual Exclusivity**: `fresh_context="enabled"` cannot be combined with `inherit_context="full"` or `inherit_context="subset"`
   - If `inherit_context` is "full" or "subset", `fresh_context` must be "disabled"
   - If `fresh_context` is "enabled", `inherit_context` must be "none"

2. **Validation Errors**: Templates violating these constraints will fail validation with clear error messages

### Function Template Validation
- Template names must be unique within the TaskLibrary
- Parameter lists must use valid identifiers
- Templates must have a valid body task
- Function calls must reference existing templates
- Argument counts must match parameter counts

## Related Documentation

For implementation details, see:
- [XML Processing Implementation](../../components/task-system/impl/xml-processing.md)
- [Function Template Examples](../../components/task-system/impl/examples/function-templates.md)
- [Subtask Spawning Examples](../../components/task-system/impl/examples/subtask-spawning.md)

Default context management settings apply when the `<context_management>` element is omitted from an atomic task definition. These depend on the task's `subtype`:

| Atomic Task Subtype | inherit_context | accumulate_data | accumulation_format | fresh_context |
|---------------------|-----------------|-----------------|---------------------|---------------|
| standard            | full            | false           | notes_only          | disabled      |
| subtask             | subset          | false           | notes_only          | enabled       |
| director            | full            | false           | notes_only          | disabled      |
| evaluator           | full            | false           | notes_only          | disabled      |
| aider_interactive   | subset          | true            | notes_only          | enabled       |
| aider_automatic     | subset          | false           | notes_only          | enabled       |
| *(default)*         | full            | false           | notes_only          | disabled      |

*(Defaults are based on ADR 14 and typical usage patterns)*

When the `<context_management>` element is present in the XML, its settings override these defaults for that specific task execution.

### Field Definitions (Atomic Tasks)

- `description`: Human-readable description of the task.
- `provider`, `model`: Optional LLM provider and model hints.
- `instructions`: The main prompt or instructions for the LLM (maps to `taskPrompt`).
- `system`: An optional system prompt specific to this task (extends base system prompt).
- `output_slot`, `input_source`: (Potentially deprecated/unused).
- `output_format`: Specifies expected output format (JSON/text) and optional schema validation.
- `context_management`: Overrides default context settings for this task execution.
- `file_paths`: Specifies explicit files or sources for context.
- `inputs`: Defines named inputs expected by the task template (used for `{{variable}}` substitution).
- `context_relevance`, `context_assembly`: Hints for context generation.
- `manual_xml`, `disable_reparsing`: Flags for LLM interaction control.
- `criteria`: Optional free-form string for dynamic evaluation template selection.
- `ref`: Optional reference to another registered template (usage TBD with S-expressions).
- `subtype`: Refines the atomic task type (e.g., `standard`, `subtask`, `director`, `evaluator`, `aider_interactive`).
- `type`: Must be `"atomic"`.

### Example Atomic Task Template

```xml
<task>
  <instructions>Analyze the given code for readability issues.</instructions>
  <system>You are a code quality expert focused on readability.</system>
  <model>claude-3-sonnet</model>
  <!-- The criteria element provides a free-form description used for dynamic evaluation template selection via associative matching -->
  <criteria>validate, log</criteria>
  <inputs>
    <input name="code">The code to analyze</input>
  </inputs>
  <output_format type="json" schema="object" />
  <manual_xml>false</manual_xml>
  <disable_reparsing>false</disable_reparsing>
</task>
```

### Validation Rules (Atomic Tasks)

1. Required fields (`description`, `type="atomic"`) must be present.
2. Input names within `<inputs>` must be unique.
3. Boolean fields (`manual_xml`, `disable_reparsing`, `accumulate_data`) must be "true" or "false".
4. Enumerated values (e.g., in `context_management`, `output_format type`) must be valid.
5. Context management constraints (mutual exclusivity of fresh_context and inherit_context) must be respected.
6. Output schema must match basic type validation rules if specified.

### Error Response Schema

```xml
<xs:complexType name="TaskError">
  <xs:choice>
    <xs:element name="resource_exhaustion">
      <xs:complexType>
        <xs:sequence>
          <xs:element name="resource" type="xs:string"/>
          <xs:element name="message" type="xs:string"/>
          <xs:element name="metrics" type="MetricsType" minOccurs="0"/>
        </xs:sequence>
      </xs:complexType>
    </xs:element>
    <xs:element name="task_failure">
      <xs:complexType>
        <xs:sequence>
          <xs:element name="reason" type="TaskFailureReason"/>
          <xs:element name="message" type="xs:string"/>
          <xs:element name="details" type="DetailsType" minOccurs="0"/>
        </xs:sequence>
      </xs:complexType>
    </xs:element>
  </xs:choice>
</xs:complexType>

<xs:simpleType name="TaskFailureReason">
  <xs:restriction base="xs:string">
    <xs:enumeration value="context_retrieval_failure"/>
    <xs:enumeration value="context_matching_failure"/>
    <xs:enumeration value="context_parsing_failure"/>
    <xs:enumeration value="xml_validation_failure"/>
    <xs:enumeration value="output_format_failure"/>
    <xs:enumeration value="execution_timeout"/>
    <xs:enumeration value="execution_halted"/>
    <xs:enumeration value="subtask_failure"/>
    <xs:enumeration value="input_validation_failure"/>
    <xs:enumeration value="unexpected_error"/>
  </xs:restriction>
</xs:simpleType>
```

### Interface Mapping

This schema is used by the TaskSystem component. For implementation details and interface definitions, see:
- TaskTemplate interface in spec/types.md [Type:TaskSystem:TaskTemplate:1.0]
- Template validation in `TaskSystem.validateTemplate()`
- Template parsing in `TaskSystem` constructor or loading mechanism

Note: The `ref` and `subtype` attributes apply to atomic tasks. Composition patterns like Map/Reduce are implemented using the S-expression DSL.
