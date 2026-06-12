Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Audit `agentic/evidence/` and references to `actions.jsonl`,
`compiled_api.json`, and `metadata.json`. Determine whether the tracked files in
`agentic/evidence/` are canonical fixtures, accidental generated output, or
examples that should live somewhere clearer.

Use `rg` and focused reads. Return:

1. What currently references `agentic/evidence/` or those file names.
2. Whether moving the tracked evidence files is safe.
3. The best destination if they should move, with rationale.
4. Tests/docs that would need updates.

Keep the answer under 500 words.
