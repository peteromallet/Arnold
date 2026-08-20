# Host-side canonical status preflight — 2026-08-05

Command: `python -m arnold_pipelines.megaplan cloud status --all --compact`
against the exact r5 workspace/spec and cloud host `159.69.51.216`.

## Observed facts

- The box snapshot was stale (`142302s` old at capture; freshness limit 300s),
  so the command fell back to the legacy remote listing. This is an observer
  limitation, not proof that a live runner exists.
- The listing contained 21 session rows, with summary
  `blocked=2`, `complete=9`, `stopped=10`, and `watchdog_repairing=0`.
- The authoritative-looking r5 row was
  `critique-ledger-accountability-v3-r5-20260803`, workspace
  `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold`, plan
  `cl2-wbc-backed-ledger-20260803-1357`, status `blocked`, process `dead`, and
  last activity `2026-08-04T20:30:48.294730+00:00`.
- A duplicate display/session row for the same r5 identifier had status
  `stopped`, `should_run=yes`, and no workspace. A second duplicate display
  (`critique-ledger`) pointed at the blocked workspace. These are projection
  conflicts, not three runnable occurrences.
- The r5 launch outcome was `launch_not_advanced`; a later attempt recorded
  `chain_execution_binding_drift` with
  `editable_runtime_import_root_mismatch` and required an explicit
  operator-authorized content-addressed rebind.
- The watchdog evidence in the response was timestamped
  `2026-08-03T17:52:40.425404+00:00` and said `session already alive`, which is
  stale relative to the blocked/dead process evidence. It cannot be used as a
  current liveness assertion.

## Decision

Do not resume or relaunch this occurrence from the legacy listing. The host
preflight confirms Sol's quarantine decision: obtain a fresh authoritative
snapshot and the complete identity tuple, then use the supported
operator-authorized migration/new-occurrence path. Until that receipt exists,
the safe state is `INDETERMINATE`/quarantined; no marker, PID, tmux row, or
stale watchdog report can authorize a new effect.

Raw command output is retained at `/tmp/r5-status-20260805.out` for this
capture; it is diagnostic scratch space, not an authority record.
