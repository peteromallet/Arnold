# Nodes Layer Audit 10: Safe Action Batch

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: produce the exact safe implementation batch for the nodes layer.

Use deletion-first policy:
- Delete shims unless a hard public contract requires keeping them.
- If keeping any shim, explain why this is an extreme-case exception.

Inspect all relevant nodes files, generator, tests, ready templates, and docs.

Return:
1. Concrete file edits to make now.
2. Files not to touch and why.
3. Commands to verify.
4. What to record in `docs/structure_cleanup/status.md`.
Keep the answer under 600 words.
