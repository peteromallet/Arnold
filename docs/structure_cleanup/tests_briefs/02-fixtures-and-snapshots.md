# Tests Layer Audit 02: Fixtures And Snapshots

Audit test fixtures, snapshots, golden data, sample workflows, and generated
expected outputs under `tests/`.

Questions:
- Which fixture/snapshot directories are authored source of truth?
- Which are generated outputs that should be ignored or moved under `out/`?
- Which fixture paths are referenced by tests, docs, or tools?
- Are there stale fixture files that can be deleted without changing behavior?

Return exact paths and safe first actions only.
