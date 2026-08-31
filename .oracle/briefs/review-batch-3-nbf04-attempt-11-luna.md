# Luna review brief — Batch 3 NBF-04 attempt 11

Review `.oracle/rework/batch-3-nbf04-attempt-11.md` as a fresh, read-only
semantic and authority review. Bind the review to base checkpoint
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e` on
`reconcile/nbf-attempt4-2297`.

Verify the six frozen input hashes from the packet, the 25-path manifest
`c6cccbe732ce8b45f65779f95db4b246f0f85a433b0e304a9cb7912b971b9b5e`, and the
canonical framed NBF04-DIFF-V1 aggregate
`b3945b43cc62136d463745c2c18e2066ee7b1ff8a4d2d81b3c41b4a2c6963f4b`.
The reproducible source of that identity is
`.oracle/scripts/nbf04_diff_v1.py` (SHA-256
`967b9f41bd588ea1265b3eddf22e97b9ce1d8d37e3a5e49b20b23d6b2651a612`) run
with `.oracle/scripts/nbf04-attempt-11.manifest` (SHA-256
`c6cccbe732ce8b45f65779f95db4b246f0f85a433b0e304a9cb7912b971b9b5e`). The
deterministic JSON output SHA-256 is
`eb849a52235b2e1d63a7adf995738c5ce33c6271814fb8ecc28caae73a06b342`.

Judge NBF-04 only. Adversarially inspect the attempt-10/11 control-side
changes:

* unresolved production outcomes must match all seven admission-bound fields,
  and must have exactly one matching durable cleanup handoff;
* supplied cleanup handles must match the registered PID and dynamic
  process-start identity before retention, polling, reaping, or terminal
  reconciliation;
* a failed or mismatched later handle must not clear or replace an already
  validated retained handle;
* a globally selected handoff must match the receiving adapter's reservation,
  plan, phase, projection, family, logical dispatch, receipt, fingerprint,
  selected spec, physical door, and execution-context identity before any
  custody mutation or ledger write;
* cross-adapter natural-death and permanent-hold attempts must return typed
  unresolved custody with zero writes and leave the owning adapter unchanged.

Re-run the focused controlled/native, custody, WBC, managed, ladder,
inventory, and no-bare checks as practical. The packet records 229 cumulative
passes plus 11 attempt-11 checks; the fresh controlled-launch run recorded 26
passes, with compile and diff-check clean. Treat only causally related
failures as blockers. Known stale baselines are the unrelated attestation-seed
absence, OMP-vs-HERMES fake-output fixture, and old timeout-124 expectation
versus cleanup-hold-75 contract.

Return PASS or REWORK with exact file:line evidence. Do not edit source or
Oracle artifacts, commit, push, merge, deploy, touch main/NBF-05, or launch the
epic.
