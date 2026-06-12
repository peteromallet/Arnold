# Tests Layer Audit 01: Root Map

Audit the `tests/` directory as a structural layer.

Questions:
- What top-level test subdirectories exist, and what role does each play?
- Which files at `tests/` root earn their placement?
- Are there missing README/index docs that would reduce navigation friction?
- What must not move because pytest discovery, imports, or path literals depend on it?

Return:
- concise findings
- exact safe edits/deletions
- explicit deferrals with reason
