# Tests Layer Audit 10: Safe First Batch

Synthesize a conservative first batch for `tests/`.

Inputs:
- Inspect the current `tests/` tree and relevant docs.
- Prefer zero-behavior cleanup: README/index files, ignored junk deletion,
  stale path references, and clearly unused generated artifacts.

Return:
- exact delete list
- exact file edit list
- exact move list, if any, with risk
- deferrals
- verification commands
