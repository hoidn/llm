# Open Architecture Questions

This document now lists only *unresolved* questions. Many items previously listed have been answered in the ADRs or clarified in the patterns. For the MVP, the matching logic is uniform for atomic tasks, and no operator‑specific matching or versioning considerations are applied.

## Unresolved Questions

1. **Context Generation Failures:** When associative matching fails, should partial outputs be preserved for re‑try? (See ADRs 002 and 005 for related discussion.)

2. **Subtask Spawning Mechanism:** How exactly should subtasks be created dynamically (beyond the Director‑Evaluator pattern)? This remains an open design area.

For additional background, see also [decisions/005-context-handling.md](decisions/005-context-handling.md) and [questions.md](questions.md) in previous revisions.
