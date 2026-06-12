# Package Layer Audit 10: Safe First Batch

Synthesize a conservative first package-internals batch.

Inputs:
- Inspect `vibecomfy/` current tree and package docs/tests.
- Prefer zero-behavior changes: README files, ignored junk deletion, stale
  unreferenced files, and clarified boundaries.
- Do not recommend moving public modules or CLI entrypoints unless every import
  and doc reference is accounted for.

Return:
- exact delete list
- exact file edit/create list
- exact move list, if any, with risk
- deferrals
- verification commands
