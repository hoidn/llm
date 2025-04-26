# AtomicTaskExecutor Implementation Design

This document describes the implementation design of the AtomicTaskExecutor component.

## Parameter Environment

The `AtomicTaskExecutor` receives a simple dictionary mapping parameter names (from the atomic task's declared `<inputs>`) to their evaluated values (passed by the `TaskSystem` from the `SubtaskRequest`). It does not require a complex, nested `Environment` object with parent pointers for its core operation. Substitution uses this flat dictionary directly.

## Template Variable Substitution

The AtomicTaskExecutor performs template variable substitution (`{{parameter_name}}`) before passing tasks to the Handler. This process strictly adheres to the function-style template model:
1.  The executor receives an execution environment (a simple dictionary) containing bindings only for the parameters declared in the atomic task's `<inputs>` definition, mapped from the arguments provided in the `SubtaskRequest`.
2.  Placeholders like `{{parameter_name}}` within the template's body (e.g., in `<description>` or prompts) are resolved by looking up `parameter_name` *only* within this provided parameter dictionary.
3.  References to variables not declared as parameters for the template will result in an execution error. There is no fallback to searching any other environment.

## Metacircular Approach (S-expression Context)

The system retains a metacircular aspect, but the AtomicTaskExecutor plays a specific role:
> The S-expression Evaluator orchestrates workflows and calls atomic tasks. The TaskSystem invokes the AtomicTaskExecutor to run the body of these atomic tasks. Some atomic tasks involve LLM calls (via the Handler, invoked by the AtomicTaskExecutor). An LLM called by an atomic task might generate S-expression code as output. This output string is returned in the TaskResult. Subsequent steps in the S-expression workflow (managed by the S-expression Evaluator) could then parse and evaluate this generated code.

The AtomicTaskExecutor executes the atomic step, potentially involving an LLM, but does not itself evaluate any generated S-expressions.

## Context Management Implementation (via Task System & Primitives)

The AtomicTaskExecutor itself does not manage context. The Task System prepares the final context (including file content fetched via the Handler) *before* invoking the AtomicTaskExecutor. The executor simply receives the final prompts and context string to pass to the Handler.

## Associative Matching Invocation

The AtomicTaskExecutor does not invoke associative matching. This is handled by the Task System or S-expression primitives *before* the executor is called.

## Subtask Spawning Implementation (Handling CONTINUATION)

The AtomicTaskExecutor does not handle `CONTINUATION`. If the Handler returns a result indicating a subtask request (e.g., via tool use), this result is passed back through the AtomicTaskExecutor to the TaskSystem and then to the S-expression Evaluator, which orchestrates the spawning.

## Tool Interface Integration (Primitives)

The AtomicTaskExecutor does not directly execute S-expression primitives. It invokes the Handler, which might execute its own registered tools as part of fulfilling the atomic task's request.
