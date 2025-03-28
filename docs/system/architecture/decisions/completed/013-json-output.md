# ADR 13: JSON-based Output Standardization (Summary)

## Status
Accepted and Implemented

## Context
The system needed a standardized approach for handling structured outputs from tasks. Previously, tasks returned outputs in arbitrary text formats, leading to type ambiguity, structure inconsistency, parsing burden, error-prone data exchange, and poor composability.

## Decision
We implemented a JSON-based output standardization mechanism with the following key features:

1. Added an `<output_format>` XML element to specify structured output requirements:
   ```xml
   <output_format type="json" schema="string[]" />
   ```

2. Added a `returns` attribute to function templates for type validation:
   ```xml
   <template name="get_file_info" params="filepath" returns="object">
   ```

3. Enhanced TaskResult interface with a `parsedContent` property to store parsed JSON data.

4. Added output format validation with specific error handling for format violations.

5. Implemented automatic JSON detection and parsing for tasks with `type="json"`.

## Consequences
- Tasks can now specify structured output formats with validation
- Function templates can declare return types
- Consumers can access parsed JSON data directly via the TaskResult interface
- Type validation ensures outputs match specified schemas
- Error handling provides clear feedback for format violations

## Implementation
The implementation includes:
- XML schema updates for `<output_format>` and `returns` attributes
- TaskResult interface enhancements
- parseTaskOutput method in TaskSystem interface
- Output validation logic
- Error handling for format violations

## References
Full ADR: ../../../../completed_plans/013-json-output.md
