Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Synthesize a safe first cleanup batch for `scripts/` and `tools/`.

Constraints:

- Avoid moving files referenced by tests, GitHub Actions, or docs unless the
  reference updates are trivial and clearly scoped.
- Do not delete tracked scripts unless clearly obsolete.
- Ignored caches and `.DS_Store` can be cleaned.

Return ordered actions, deferrals, and verification commands. Under 650 words.
