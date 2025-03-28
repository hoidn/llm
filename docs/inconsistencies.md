# Inconsistencies Requiring Subjective Choices

Below are areas where the documents highlight open design questions or competing approaches. Each needs a decision to remove ambiguity.

## Partial-Results Policy for Failing Operators

Options:
- A: Discard partial outputs on sub‐task failure, treating the entire operator as a single unit of success/failure.
- B: Preserve partial outcomes (e.g. in TaskResult.notes.partialResults) so higher‐level tasks can decide how to handle them.

Recommendation: If your use cases frequently require partial data (e.g., some parallel tasks succeed while others fail), choose (B) and store partial results. If the system rarely benefits from partial data, keep (A) for simplicity.

## Context-Generation Failure as Its Own Error

Options:
- A: New error type (CONTEXT_GENERATION_FAILURE) in errorspec.md, distinctly recognized so that tasks can handle it differently than normal "task failures."
- B: Keep a single TASK_FAILURE category and rely on message or reason to identify context errors.

Recommendation: If you plan to handle context failures with specialized fallback or re-tries, choose (A). If context issues are not special in your system's eyes, keep (B) to avoid error-type proliferation.

## Inherited Context for Map and Reduce - RESOLVED

This issue has been resolved in ADR 14 (Operator Context Configuration). All operators now support the `<inherit_context>` setting with consistent semantics, following the hybrid configuration approach with operator-specific defaults:

| Operator Type | inherit_context | accumulate_data | accumulation_format | fresh_context |
|---------------|-----------------|-----------------|---------------------|---------------|
| atomic        | full            | false           | notes_only          | enabled       |
| sequential    | full            | true            | notes_only          | enabled       |
| reduce        | none            | true            | notes_only          | enabled       |
| script        | full            | false           | notes_only          | disabled      |
| director_evaluator_loop | none  | true            | notes_only          | enabled       |

These defaults apply when no explicit context_management block is provided. When present, explicit settings override the defaults, providing both consistency and flexibility.

## Handler Tools API (Read-Only vs. Read/Write)

Question: "Do tasks need to modify or delete files, or is read-only enough?"

Options:
- A: Provide readFile, writeFile, deleteFile from the start.
- B: Provide only readFile, and mention a future extension for writes.

Recommendation: Decide based on real usage. If you have no short-term need for writes, option (B) keeps it simpler, adding write methods later if necessary.

## Summary

To maintain consistency going forward:
1. Pick one approach for partial results behavior
2. Choose error taxonomy for context generation failures
3. Decide on context inheritance scope
4. Finalize Handler tools API requirements
5. Document these decisions clearly to prevent future ambiguity
