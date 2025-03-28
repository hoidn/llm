# ADR 15: Notes Field Standardization

## Status
Accepted

## Context
The task system currently has an artificial distinction between `notes` and `partialOutput` fields in the TaskResult interface. This creates unnecessary complexity and inconsistency across the codebase:

1. Some documents state partial results are not preserved, while others describe preservation mechanisms
2. Sequential task results have separate `output` and `notes` fields for each step
3. The `accumulation_format` currently has values `notes_only` and `full_output` which are not intuitive
4. Error handling structures have inconsistent approaches to storing partial results

## Decision
We will simplify the task output structure by eliminating the artificial distinction between `notes` and `partialOutput` fields:

1. Use `notes` as the universal container for all task metadata, including partial results
2. Modify accumulation format values from `notes_only`/`full_output` to `minimal`/`full`
3. Update all error handling structures to store partial results directly in the notes field
4. Standardize terminology around `notes` across all documentation

### Simplified TaskResult Interface
```typescript
export interface TaskResult {
    content: string;
    status: ReturnStatus;
    criteria?: string;
    parsedContent?: any;
    notes: {
        dataUsage?: string;
        successScore?: number;
        // Partial results are directly included in notes
        [key: string]: any;
    };
}
```

### Simplified TaskOutput Interface
```typescript
export interface TaskOutput {
    stepId: string;  // or step index
    notes: any;      // Task notes field (always preserved, may include partial results)
    timestamp: Date;
}
```

### Simplified Accumulation Format
```typescript
// Simplified behavior:
enum AccumulationFormat {
    MINIMAL,  // Preserves only success/failure status and critical metadata
    FULL      // Preserves all notes content including partial results
}
```

## Consequences
### Positive
- Reduced complexity in the task output structure
- More intuitive naming for accumulation formats
- Consistent approach to partial results across the system
- Simplified error handling structures
- Better alignment with how LLMs naturally structure output

### Negative
- Requires updates to existing documentation and code
- May require migration for existing implementations

## Implementation
1. Update TaskResult interface to remove partialOutput field
2. Update TaskOutput interface to remove output field
3. Update accumulation format values in XML schema
4. Update operator default settings to use minimal/full values
5. Update error handling documentation to reflect the simplified approach
6. Ensure backward compatibility where possible

## Related Documents
- [Pattern:Error:1.0]
- [Contract:Tasks:TemplateSchema:1.0]
- [Component:TaskSystem:1.0]
