# Luna review brief — Batch 3 NBF-04 attempt 4

Review the cumulative NBF-04 candidate bound by
`.oracle/rework/batch-3-nbf04-attempt-4.md`. Verify the frozen identity hashes,
the exact 24-path source/test manifest and diff hashes, and the validation
results in that packet.

Judge NBF-04 only. Confirm record-before-signal, distinct durable TERM/KILL
confirmations, dynamic same-incarnation rereads and PID-reuse rejection,
already-dead handling, exactly-once disposition/terminal linkage, replay without
resignal, strict missing-context cleanup holds, and terminal reconciliation.
Trace every native, OMP, managed, handler, launcher, fan, resident, operator,
orphan, and timeout signal request to the existing WBC/disposition authority;
child certification must remain additive evidence on the same admitted WBC
attempt. Confirm invalid native cause labels fail closed and resident refused
cleanup never waits on an uncertified live child.

The four `runtime/batch.py` terminate/kill sites are neutral validation-shard
cleanup and are explicitly classified by the live Python inventory. Treat them
as a narrow NBF-05/transitive follow-up, not as managed-worker authority, unless
you find evidence that an admitted worker reaches them.

Re-run the focused suites and direct probes named in the integration packet.
The two resident-suite failures are documented stale/baseline fixtures (missing
unrelated runtime-attestation seed and OMP-vs-HERMES fixture output); do not
reclassify them as NBF-04 regressions without evidence of candidate causality.

Do not expand into NBF-05 shell wrappers/generated inventory, NBF-06, unrelated
fixture migration, status or execution-log changes, commit/push/merge/deploy,
or epic launch/resume.

This is one of the three default Luna reviews for this segment. A single Sol
oracle review may follow the Luna gate; do not spend additional Sol reviews on
this segment.
