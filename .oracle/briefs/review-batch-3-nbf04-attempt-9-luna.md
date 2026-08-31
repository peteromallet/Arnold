# Luna review brief — Batch 3 NBF-04 attempt 9

Review `.oracle/rework/batch-3-nbf04-attempt-9.md` as a fresh, read-only
semantic and authority review. Verify the candidate checkpoint
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`, the six frozen input hashes in the
packet, the exact 25-path manifest, manifest SHA
`c6cccbe732ce8b45f65779f95db4b246f0f85a433b0e304a9cb7912b971b9b5e`, and diff
SHA `1c4087c1ab54e275e881895aa9e5219d3e52dc02d3308e8d0600d405f46067dd`.

Judge NBF-04 only. Trace every native timeout/stall path through the single
WBC-bound controlled-launch authority. Confirm the explicit plan allowance for
immediate timeout is durable and does not masquerade as two-scan confirmation;
TERM/KILL claims and PID/start validation remain record-before-signal and
replay-safe.

Adversarially inspect the attempt-7/8/9 custody contract:

* `SpawnCleanupHold` wrappers must unwrap and retain the actual Popen handle,
  preserve hold metadata, and return the canonical persisted handoff/event ID;
* handoff identity must bind receipt, semantic fingerprint, worker identity,
  PID/start, registration/certification IDs, context, route, and error reason;
* accepted natural death must append one canonical observation and ordinary
  terminal, return the exact existing JSON-normalized events on replay, and
  reap only through a lawful retained parent handle;
* restart-style reconciliation must use PID/start evidence without requiring a
  Popen handle, fail closed on PID reuse or unsafe missing-start liveness, and
  never signal;
* death before an accepted marker must remain a permanent custody hold without
  inferred worker terminal/disposition;
* `ControlledFinalLaunch.run` must return typed `unresolved_launch` custody
  outcomes rather than rejecting them through the accepted-result filter or a
  generic `TypeError`.

Re-run the focused controlled/native, common-WBC, managed-signal, ladder,
launcher/resident, Python-inventory, and no-bare checks as practical. Existing
218-pass cumulative evidence is valid input; the attempt-9 rerun recorded 51
focused passes plus 8 handoff/unresolved passes. Treat only causally related
failures as blockers. The known stale fixtures are unrelated attestation-seed
absence, OMP-vs-HERMES fake output, and the old timeout `124` expectation
versus the current cleanup-hold `75` contract.

Return PASS or REWORK with exact file:line evidence. Do not edit source or
Oracle artifacts, commit, push, merge, deploy, touch main/NBF-05, or launch the
epic.
