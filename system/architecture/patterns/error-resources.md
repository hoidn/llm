# Error Condition Resource Pattern [Pattern:ErrorResource:1.0]

## Resource Handling During Errors

From task-system/spec/behaviors.md and impl/resource-management.md:

### Required Actions
On error detection:
- Stop resource usage
- Complete resource accounting
- Begin cleanup process
- Surface error with metrics

### Cleanup Requirements
From task-system/impl/resource-management.md:
- Handler cleanup
- Resource release
- Memory cleanup
- Metric collection

## Implementation

```typescript
interface ErrorResourceMetrics {
    // From task-system/spec/types.md
    turns: {
        used: number;
        limit: number;
    };
    context: {
        used: number;
        limit: number;
        peakUsage: number;
    };
}
```