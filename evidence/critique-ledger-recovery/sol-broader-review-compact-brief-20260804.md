# Sol judgement request (compact evidence-only brief)

Take a firm architectural position from the evidence below. Do not inspect the repository or delegate. Return under 1200 words with: (a) root-cause tree, (b) whether the current fixes are root-level or local mitigation, (c) ranked independent Luna audit directions, (d) shortest safe immediate recovery, and (e) shared-system hardening plus acceptance tests.

## Observed facts

1. The cloud session `critique-ledger-accountability-v3-r5-20260803`, plan `cl2-wbc-backed-ledger-20260803-1357`, failed at VJ8 before worker dispatch. State recorded `pre_dispatch_validation_failed`, `phase=execute`, `worker_dispatched=false`, `exit_code=1`, occurrence `validation-8a0d0d672f63643cc82e`, fingerprint `8a0d0d672f63643cc82ef81841ab9493b87bfe69671c5da9d961dc60c878c4d3`.
2. The VJ8 suite initially had 126 tests, 122 pass and 4 failures. All four were stale expectations around divergent same-idempotency-key ledger events and exact retry canonicalization. After repairing the implementation/tests, the exact suite is 130 passed.
3. Recovery was made occurrence-bound: a receipt binds the failure fingerprint, occurrence, job, source revision, passing test result, and runtime code hash. Recovery now rejects stale/mismatched evidence and does not clear real U1/quality blockers. Status now exposes latest_failure and projects `finalized` to execute because finalized is an execute-entry state.
4. The same plan is now `state=finalized`, `execution_state=ready`, `next_step=execute`, with U1/quality blockers still unresolved and authoritative.
5. The canonical local `cloud resume` wrapper failed before dispatch. Its SSH provider runs `cd <workspace> && arnold status --plan <plan>`. On the container, `arnold` resolves to `/root/.pyenv/shims/arnold`, whose installed `arnold.cli` exposes a different legacy interface and requires `--artifact-root`. The intended megaplan CLI works only when invoked through `/workspace/runtime-venvs/arnold-wbc-full-20260804/bin/python -m arnold_pipelines.megaplan ...`.
6. Earlier evidence showed: managed runner lease startup errors were swallowed; marker “launch success” could mean only tmux/state was observed; stale phase_result.json could outrank newer state.latest_failure; resident and chain code used different dirty/pinned runtime lineages; watchdog snapshots could be stale or unreadable; `/whats-cooking` could time out while collecting a snapshot.
7. Luna audits already found: no remote provider-key preflight; alias/auth allowlists are not one source of truth; resident may import dirty `/workspace/arnold` while the chain uses pinned c116; liveness must be lease/process identity, not tmux; observer responses need bounded work and stale-data labeling.

## Constraints

Do not fabricate CL1/U1 handoffs, resolve quality blockers to force progress, create a new chain, or claim liveness without a fresh lease-bound process identity. The fix must generalize to every cloud megaplan pipeline.
