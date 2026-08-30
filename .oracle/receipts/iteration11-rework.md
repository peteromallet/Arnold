# Arnold Batch 2 iteration 11 rework receipt

## Binding

- Worktree: `/Users/peteromalley/Documents/Arnold-batch2-iteration5`
- Starting candidate: `dbc7d012963afccb6e74218f1ea43c5a13a9c898`
- Starting evidence checkpoint: `b596ea36ce7bbea140b34ca7a9ed1c80704dc169`
- Scope: producer-bound process custody, canonical OMP launch argv, coherent
  Codex Node/script identity, offline Claude catalog/liveness, and managed-child
  producer attestation with live-at-birth proof.
- OMP was not promoted, pushed, resumed, or otherwise externally launched.

## Root repairs

- Process snapshots issued inside `ControlledFinalLaunch` carry private,
  producer-owned one-shot custody bound to receipt, logical dispatch, and
  semantic fingerprint. Unbound snapshots, copied mappings, cross-receipt first
  use, and replay are rejected.
- OMP is launched with an explicitly resolved Bun executable and trusted
  `cli.js`, beginning exactly `[bun, cli.js, --mode, rpc]`; post-prefix flags
  are allowlisted and eval/path injection is rejected.
- Codex admission and completion bind the observed Node executable and trusted
  `codex.js` script, including both executable/script digests.
- Claude liveness is an offline local catalog check and the real worker returns
  the verified child identity captured by the canonical process boundary.
- Managed completed identities require a supervisor-issued, one-shot custody
  attestation bound to the canonical manifest and verified live-at-birth
  process tuple; caller-self-hashed nonexistent PIDs are rejected.

## Exact validation

- NBF02 frozen suite: **259 passed in 117.21s**.
- NBF03 frozen suite: **59 passed in 78.53s**.
- Auto-recovery suite: **29 passed in 6.28s**.
- Focused production/adversarial suite: **9 passed in 3.83s**; the four
  existing normalization/replay/real-OMP focused regressions also passed in
  **4 passed in 2.35s**.
- Authority checker: `python scripts/check_worker_admission_authority.py --check`
  returned `{"diagnostics": [], "ok": true}`.
- Raw-symbol scan for forbidden runtime-launch bypasses: **clean**.
- Changed-file `py_compile`: **passed**.
- `git diff --check`: **passed**.

The NBF02/NBF03 suites preserve the prior normalization, replay, cross-receipt,
native/OMP, linked-child, nullable, transition, authority, and no-WBC gates.

## Source diff identity

Before this receipt was added, the tracked production/test diff against the
starting evidence checkpoint had SHA-256:

`87f0309b5f9efe210d32cd0c4fc41dd12bc9844352e846bd2763e8a07cf7c1e7`

The new adversarial module was also validated and is included in this commit:
`tests/cloud/test_batch2_iteration11.py`.
