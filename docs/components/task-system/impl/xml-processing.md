# XML Processing Implementation

> **Overview and References:** This document focuses on the Task System's XML processing implementation. For the complete XML schema definition and template guidelines, please refer to [Contract:Tasks:TemplateSchema:1.0](../../../system/contracts/protocols.md).

## Overview

The XML Processing implementation handles:
- Validation of XML against the schema
- Template processing and registration
- Output parsing and validation
- Error handling for invalid XML

## Schema Validation

### Core Schema Requirements
- Based on [Contract:Tasks:TemplateSchema:1.0]
- Required elements:
  * `instructions` (maps to taskPrompt)
  * `system` (maps to systemPrompt)
  * `model` (maps to model)
- Optional elements:
  * `inputs` with named input definitions
  * `manual_xml` flag
  * `disable_reparsing` flag

### Validation Rules
- All required fields must be present
- Input names must be unique
- Boolean fields must be "true" or "false"
- Model must be a valid LLM identifier

## Template Processing

### Template Validation
- Schema conformance checking
- Required field validation
- Type checking for known fields
- Warning generation for non-critical issues

### Manual XML Tasks
- Direct structure usage without reparsing
- Schema validation still applies
- Support for disable_reparsing flag
- No automatic restructuring

## Output Processing

### XML Generation
```xml
<!-- Example Output Structure -->
<task type="sequential">
    <description>Task description</description>
    <steps>
        <task>
            <description>Step description</description>
            <inputs>
                <input name="input_name">
                    <task>
                        <description>Input task</description>
                    </task>
                </input>
            </inputs>
        </task>
    </steps>
</task>
```

### Output Validation
- Structure validation against schema
- Required field presence checking
- Type validation for known fields
- XML well-formedness checking

### Output Format Validation
- Format specification via `<output_format>` element
- JSON detection process:
  * Attempts to parse content as JSON
  * Validates parsed content against schema attribute
  * Returns original content if parsing fails
- Type validation against schema attribute:
  * "object" - Validates as JavaScript object
  * "array" or "[]" - Validates as array
  * "string[]" - Validates as array of strings
  * "number" - Validates as numeric value
  * "boolean" - Validates as boolean value
- Error handling for format violations:
  * Generates TASK_FAILURE with reason "output_format_failure"
  * Includes expected vs actual type information
  * Preserves original output in error details
- Template return type validation:
  * Function templates can specify return types using the `returns` attribute
  * Return types are validated against actual output
  * Type mismatches generate validation errors

Example XML showing proper usage:
```xml
<task>
  <description>Get repository statistics</description>
  <output_format type="json" schema="object" />
</task>

<!-- With template return type -->
<template name="get_stats" params="repo_path" returns="object">
  <task>
    <description>Get statistics for {{repo_path}}</description>
    <output_format type="json" schema="object" />
  </task>
</template>
```

### Fallback Behavior
- Return unstructured string on parse failure
- Collect and surface warnings
- Maintain original content
- Include parsing error details

## Error Handling

### Validation Errors
```typescript
interface XMLError {
  type: 'XML_PARSE_ERROR' | 'VALIDATION_ERROR';
  message: string;
  location?: string;
  violations?: string[];
}
```

### Recovery Strategies
- Attempt partial content recovery
- Generate fallback string output
- Preserve original content
- Surface all validation issues

## Integration Points

### Template Management
- Load and validate schemas
- Process template definitions
- Handle manual XML flags
- Track template versions

### Task Execution
- Validate output structure
- Handle parsing failures
- Surface warnings appropriately
- Maintain execution context

## Related Documentation

For more examples, see:
- [Function Template Examples](./examples/function-templates.md)
- [XML Schema Definition](../../../system/contracts/protocols.md#xml-schema-definition)
- [ADR 13: JSON Output](../../../system/architecture/decisions/completed/013-json-output.md)
