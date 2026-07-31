---
id: 01KYVJ7A47TMH4BRGEV9JFTK10
title: Implement an honest backend-neutral deployed workflow canary runner
status: open
source: human
tags:
- release
- cloud
- canary
- acceptance
codebase_id: null
created_at: '2026-07-31T07:46:35.271850+00:00'
last_edited_at: '2026-07-31T07:46:35.271850+00:00'
epics: []
---

The M11 release must not treat caller-authored observations, labels, booleans, timestamps, or self-hashed JSON as deployed proof. The current pending contract deliberately cannot verify the four live scenarios.

Implement after the present custody release correction, before the release umbrella can close:

- one executable deployed runner bound before launch to exact deployment target/id, full source revision, canonical runtime-receipt digest, and immutable evidence root;
- backend-neutral WBC access (SQLite and PostgreSQL) through canonical read-only APIs;
- one non-stitchable identity join across manifest id/hash, journal run id and evidence window, WBC attempt identity, committed acceptance transaction plus loaded content-addressed snapshot/verdict, plan identity, source revision, and runtime identity;
- fresh-plan proof from canonical manifest admission through accepted completion;
- suspension proof with canonical checkpoint/cursor, WBC RESUMED, distinct reentry/backend invocation, and terminal completion;
- at least three iterations of a real authored megaplan:gate node, not arbitrary route-kind events;
- all four authored megaplan:tiebreaker_* phases plus a declared, projected decision transition ordered before accepted terminal;
- frozen stores and verdict before an independent verifier re-derives the result; conformance must require exact re-derivation and reject shape/self-hash-only artifacts;
- bounded timestamps from the admitted evidence window, uniqueness of scenario roots/attempts/run IDs, accepted transaction mode/snapshot/verdict checks, and adversarial cross-stitch/forgery tests;
- exact cloud commands, fixture, rollback, and canary-summary integration in the promotion runbook.

Acceptance: the pending-only conformance gate can be replaced only after a real deployed run produces all four independently re-derived proofs. Until then deployed_proof_status remains pending and the release umbrella stays open.
