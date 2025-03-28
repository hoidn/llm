# Architecture Decision Record: Evaluator-to-Director Feedback Flow

## Status
Accepted

## Context
The Director-Evaluator pattern is a foundational component of our architecture that allows tasks to generate output, have it evaluated, and receive feedback for further refinement. Current implementation approaches lack standardization regarding context management, data passing between components, and iteration control.

## Decision
We will implement a unified Director-Evaluator pattern with direct result passing between components, explicit context management, standardized result structures, and configurable iteration control through a dedicated task type.

## Specification

### 1. Director-Evaluator Loop Task Structure

```xml
<task type="director_evaluator_loop">
  <description>{{task_description}}</description>
  <max_iterations>5</max_iterations>
  <context_management>
    <inherit_context>none</inherit_context>
    <accumulate_data>true</accumulate_data>
    <accumulation_format>notes_only</accumulation_format>
    <fresh_context>enabled</fresh_context>
  </context_management>
  <director>
    <description>Generate solution for {{original_prompt}}</description>
    <inputs>
      <input name="original_prompt" from="user_query"/>
      <input name="feedback" from="evaluation_feedback"/>
      <input name="iteration" from="current_iteration"/>
    </inputs>
  </director>
  <evaluator>
    <description>Evaluate solution against {{original_prompt}}</description>
    <inputs>
      <input name="solution" from="director_result"/>
      <input name="original_prompt" from="user_query"/>
    </inputs>
  </evaluator>
  <script_execution>
    <!-- Optional script execution -->
    <command>{{script_path}}</command>
    <timeout>300</timeout>
    <inputs>
      <input name="script_input" from="director_result"/>
    </inputs>
  </script_execution>
  <termination_condition>
    <!-- Optional early termination -->
    <condition>evaluation.success === true</condition>
  </termination_condition>
</task>
```

### 2. Standardized Result Structure

```typescript
// Base task result structure - consistent with other task types
interface TaskResult {
    content: string;
    status: "COMPLETE" | "CONTINUATION" | "WAITING" | "FAILED";
    notes: {
        [key: string]: any;
    };
}

// Specialized structure for evaluator feedback
interface EvaluationResult extends TaskResult {
    notes: {
        success: boolean;        // Whether the evaluation passed
        feedback: string;        // Human-readable feedback message
        details?: {              // Optional structured details
            metrics?: Record<string, number>; // Optional evaluation metrics
            violations?: string[];            // Specific validation failures
            suggestions?: string[];           // Suggested improvements
            [key: string]: any;               // Extension point
        };
        scriptOutput?: {         // Present when script execution is involved
            stdout: string;      // Standard output from script
            stderr: string;      // Standard error output from script
            exitCode: number;    // Exit code from script
        };
    };
}
```

### 3. Direct Parameter Passing

The Director-Evaluator loop uses direct parameter passing rather than environment variables:

```typescript
async function executeDirectorEvaluatorLoop(task, inputs) {
  const maxIterations = task.maxIterations || 5;
  const results = [];
  
  let directorOutput = null;
  let evaluationResult = { success: false, feedback: "" };
  
  for (let iteration = 0; iteration < maxIterations; iteration++) {
    // Execute director with current state via direct parameter passing
    directorOutput = await executeTask(
      task.director,
      {
        ...inputs,
        current_iteration: iteration,
        evaluation_feedback: evaluationResult.feedback,
        previous_results: results.length > 0 ? results : undefined
      }
    );
    
    // Store the director's result
    results.push({ iteration, output: directorOutput, evaluation: null });
    
    // Execute script if present - direct parameter passing
    let scriptOutput = null;
    if (task.script_execution) {
      scriptOutput = await executeScript(task.script_execution, {
        script_input: directorOutput.content
      });
    }
    
    // Execute evaluator - direct parameter passing
    evaluationResult = await executeTask(
      task.evaluator,
      {
        solution: directorOutput.content,
        original_prompt: inputs.user_query,
        script_output: scriptOutput
      }
    );
    
    // Update stored evaluation
    results[results.length - 1].evaluation = evaluationResult;
    
    // Check termination condition
    if (evaluationResult.notes.success || 
        (task.termination_condition && evaluateCondition(task.termination_condition, evaluationResult))) {
      break;
    }
  }
  
  // Return final result and history via direct parameter passing
  return {
    final_output: directorOutput,
    final_evaluation: evaluationResult,
    success: evaluationResult.notes.success,
    iterations_completed: results.length,
    iteration_history: results
  };
}
```

### 4. Iteration Control

Director-Evaluator loops include explicit iteration control:

1. **Maximum Iterations**: Default value of 5, configurable via `<max_iterations>` element
2. **Early Termination**: Configurable via `<termination_condition>` element
3. **Automatic Success Termination**: Stops when evaluator returns `success: true`
4. **Complete History**: All iterations and evaluations preserved in the result

### 5. Context Management Integration

Director-Evaluator fully integrates with the three-dimensional context management model:

- **inherit_context**: Controls whether parent context flows into the loop
  - Default: "none" (fresh start for each loop)
- **accumulate_data**: Controls whether results accumulate between iterations
  - Default: "true" (preserving iteration history)
- **accumulation_format**: Controls detail level of accumulated data
  - Default: "notes_only" (summary information)
- **fresh_context**: Controls whether additional context is retrieved
  - Default: "enabled" (allowing retrieval of relevant information)

### 6. Error Handling

Two types of errors are handled:

1. **Negative Evaluations**: Normal flow where evaluator indicates improvement needed (`success: false`)
   - Loop continues until max iterations or termination condition
   - Full details preserved in iteration_history

2. **Execution Errors**: When director, evaluator, or script execution fails:
   - Error fully captured with details, including partial results
   - Loop terminates, returning both results up to failure point and error information

## Relationship to Subtask Spawning

The Director-Evaluator Loop and Subtask Spawning mechanism are complementary features:

| Director-Evaluator Loop | Subtask Spawning Mechanism |
|-------------------------|----------------------------|
| Specialized higher-level pattern | General-purpose primitive |
| Built for iterative refinement | Ad-hoc dynamic task creation |
| Predefined iteration structure | Flexible composition pattern |
| Built-in termination conditions | Manual continuation control |

**When to use Director-Evaluator Loop:**
- Iterative refinement processes
- Create-evaluate feedback cycles
- Multiple potential iterations
- External validation via scripts

**When to use Subtask Spawning:**
- One-off subtask creation
- Dynamic task composition
- Task flows that aren't primarily iterative
- Complex task trees with varying subtypes

## Implementation Requirements

1. **Task System Enhancements**
   - Add `director_evaluator_loop` task type support
   - Implement iteration management
   - Add termination condition evaluation
   - Provide iteration history tracking

2. **Testing Requirements**
   - Unit tests for iteration control
   - Integration tests for data passing between components
   - Script execution validation tests
   - Performance tests for varying iteration counts

## Migration Guidance

### From Previous Version
1. Replace environment variable usage with direct parameter passing:
   ```typescript
   // Old approach - using environment variables
   env.set('last_evaluator_output', evaluationResult);
   
   // New approach - direct parameter passing
   return executeTask(task.director, { 
     evaluation_feedback: evaluationResult.feedback 
   });
   ```

2. Add explicit context_management blocks:
   ```xml
   <!-- Old version - implicit context -->
   <task type="director">...</task>
   
   <!-- New version - explicit context management -->
   <task type="director_evaluator_loop">
     <context_management>
       <inherit_context>none</inherit_context>
       <accumulate_data>true</accumulate_data>
       <accumulation_format>notes_only</accumulation_format>
       <fresh_context>enabled</fresh_context>
     </context_management>
     ...
   </task>
   ```

3. Standardize result structures:
   ```typescript
   // Old approach - varied formats
   return { success: true, message: "Looks good" };
   
   // New approach - standardized format
   return {
     content: "Evaluation complete",
     status: "COMPLETE",
     notes: {
       success: true,
       feedback: "Looks good",
       details: { metrics: { accuracy: 0.95 } }
     }
   };
   ```

## Performance Considerations

- **Iteration Limits**: Default max_iterations (5) suitable for most use cases; increase with caution
- **Context Growth**: Monitor accumulated context size, especially with accumulation_format="full_output"
- **Script Execution**: Apply reasonable timeouts (default: 300s) to prevent hanging loops
- **Memory Management**: Complete iteration history preserved; consider truncation for very large outputs

## Related ADRs
- **Depends on**: [ADR 7: Context Management Standardization], [ADR 8: Error Taxonomy]
- **Extends**: [ADR 9: Partial Results Policy]
- **Related to**: [ADR 11: Subtask Spawning Mechanism]

## Consequences

### Positive
- Unified representation for feedback loops
- Clear, direct data flow without environment variables
- Explicit iteration control
- Flexible termination conditions
- Consistent context management integration
- Compatibility with script execution
- Complete iteration history preserved

### Negative
- Migration effort for existing implementations
- More complex TaskSystem implementation
- Additional memory usage for iteration history
- Learning curve for configuration options
