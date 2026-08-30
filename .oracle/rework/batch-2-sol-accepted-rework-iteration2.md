# Batch 2 Sol accepted-issues rework — iteration 2 finding

- Worktree: `/Users/peteromalley/Documents/Arnold-batch2-rework`
- Branch: `rework/batch2-sol-accepted`
- Iteration base: `7fc162b8227fba08600cb2db48d4b512aa68ab84`
- Original frozen checkpoint: `5da26ec5be4d13559948fe4256a114ad7626482b`
- Scope: remaining sealed Luna/Sol blockers only; no merge, push, or Batch 3.

## Corrections

1. Controlled acceptance now requires an explicit launcher-supplied worker
   identity with a positive PID, host, and boot identity. Missing or malformed
   proof records `ambiguous`; the adapter never fabricates the supervisor PID.
   `LaunchResult` carries identity and timing across the acceptance boundary.
2. Native admission always runs the canonical installed-backend exact-model
   probe. A caller route resolver can provide diagnostics but cannot mint native
   admission. Runtime provenance, configured seed, and configured manifest
   claims are compared with machine-owned observations when present.
3. Integer, boolean, `None`, and untyped compatibility returns cannot become
   successful terminal outcomes. Direct worker-identity mappings remain the
   explicit compatibility form; all other doors must return typed evidence.
4. Managed babysitter launches derive the real child PID and start/finish
   evidence from the durable managed manifest. Native and OMP doors preserve a
   typed identity when their worker boundary supplies one and otherwise fail
   closed rather than claiming acceptance.
5. Linked-child request construction optionally rereads the authoritative
   ledger, requiring a canonical terminal parent, matching plan/phase/logical/
   physical context, and a persisted canonical authorizer. No-launch and
   unresolved parents remain rejected.
6. The auto compatibility path no longer owns a cooldown sleep/retry door;
   scheduling is returned to the canonical admission seam. The authority
   checker now verifies door ownership and typed worker-return mode in addition
   to raw authority and duplicate-door checks.

## Validation

- Exact frozen NBF-02 command from `.oracle/tasklist.md`: **242 passed in
  183.70s** (writable `TMPDIR`; includes `tests/workers/test_omp_adapter.py`).
- Exact frozen NBF-03 command from `.oracle/tasklist.md`: **45 passed in
  20.29s**. Its four stale babysitter routing/renderer assertions were updated
  to the current single-OMP-controller contract; no red test remains.
- Targeted admission/controlled/reconciliation/linked-child tests: **11
  passed**.
- Authority checker: **exit 0**.
- Integer/no-identity negative probes: **PASS**; persisted states were exactly
  `not_started`, `entered`, `ambiguous`.
- Required raw-symbol scan: **PASS**.
- Changed-file `py_compile`: **PASS**.
- `git diff --check`: **PASS**.

The auto compatibility test now explicitly asserts the contract change:
`paused` with no local sleep/retry loop.

## Identity evidence

- Source/test diff SHA-256: `6c907b043bf3063820deec2788d0b03ee9f9d9f7ebbcee1166a681b78626a3cc`.
- Changed production files: `auto.py`, `cloud/babysitter/launch.py`,
  `cloud/controlled_final_launch.py`, `cloud/worker_dispatch.py`,
  `workers/_impl.py`, `workers/omp.py`, and
  `scripts/check_worker_admission_authority.py`.
