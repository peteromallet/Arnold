# Luna review brief — Batch 3 NBF-04 attempt 5

Review `.oracle/rework/batch-3-nbf04-attempt-5.md` as a fresh, read-only
semantic/authority review. Verify the frozen hashes, exact 25-path manifest,
manifest SHA `c6cccbe732ce8b45f65779f95db4b246f0f85a433b0e304a9cb7912b971b9b5e`,
and diff SHA `04d0517706652d7e324aee4837a684bb0c5139c5e638d0bb21d38bfc15a1247c`.

Judge NBF-04 only. Trace native timeout/stall calls through the same WBC-bound
callback and confirm that the explicitly authorized immediate-timeout path
validates worker identity and PID-start identity, records TERM/KILL before each
physical callback, uses distinct deterministic dispositions, appends exactly
one terminal after observed death, and never resends an existing claim during
crash/replay. Confirm structured pending/refused ladder results are not treated
as truthy success; stale or reused confirmations remain rejected by the
canonical ladder. Check that a callback failure remains explicit unresolved
custody rather than an inferred success.

Re-run the focused disposition/lifecycle, controlled/native, WBC/managed,
launcher/resident, inventory/no-bare tests and direct live-child and
crash-replay probes. The three resident failures are explicitly stale fixtures:
missing unrelated runtime-attestation seed, OMP-vs-HERMES output expectation,
and the old 124 timeout expectation versus the current cleanup-hold return 75.
Do not silently count these as NBF-04 regressions without candidate causality.

The larger aggregate worker/WBC command may need to be rerun with a longer
output/session window; the packet records that its local run did not emit a
final summary. Do not expand into NBF-05, NBF-06, unrelated fixture migration,
status or execution logs, commit/push/merge/deploy, or epic launch.
