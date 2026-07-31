---
id: 01KYVJ7A47TMH4BRGEV9JFTK10
title: Implement an honest deployed workflow canary runner
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
- canonical read-only access to the current deployed WBC backend;
- one non-stitchable identity join across manifest id/hash, journal run id and evidence window, WBC attempt identity, committed acceptance transaction plus loaded content-addressed snapshot/verdict, plan identity, source revision, and runtime identity;
- fresh-plan proof from canonical manifest admission through accepted completion;
- suspension proof with canonical checkpoint/cursor, WBC RESUMED, distinct reentry/backend invocation, and terminal completion;
- at least three iterations of a real authored megaplan:gate node, not arbitrary route-kind events;
- all four authored megaplan:tiebreaker_* phases plus a declared, projected decision transition ordered before accepted terminal;
- frozen stores and verdict before an independent verifier re-derives the result; conformance must require exact re-derivation and reject shape/self-hash-only artifacts;
- bounded timestamps from the admitted evidence window, uniqueness of scenario roots/attempts/run IDs, accepted transaction mode/snapshot/verdict checks, and adversarial cross-stitch/forgery tests;
- exact cloud commands, fixture, rollback, and canary-summary integration in the promotion runbook.

Acceptance: the pending-only conformance gate can be replaced only after a real deployed run produces all four independently re-derived proofs. Until then deployed_proof_status remains pending and the release umbrella stays open.

## 2026-07-31 implementation split after cloud inspection

The live Hetzner runtime is still bound to `b3ad38ab26ff...`, and the completed
M11 plan has a large events journal but no phase/execute/worker WBC SQLite
store and no `_acceptance` transaction/snapshot store. The current phase-WBC
implementation is SQLite-only; the machine has no configured PostgreSQL WBC
backend. The CLI also referenced `tiebreaker-run` and `tiebreaker decide`
without registering either parser surface.

Keep this ticket as the immediate release owner, but scope it to the actual
supported backend and one narrow truthful proof:

- register the existing canonical tiebreaker handlers as public commands;
- preserve each gate decision and boundary receipt immutably instead of
  overwriting the only copy;
- emit WBC lifecycle evidence for revise, tiebreaker, suspension, resume, and
  terminal completion through the existing ledger;
- run isolated real-backend scenarios that deterministically exercise fresh
  completion, two ITERATE decisions followed by a third gate, a durable
  suspension/resume with distinct reentry, and tiebreaker decision routing;
- execute the accepted terminal path through the existing atomic/enforce chain
  acceptance transaction, freeze the joined evidence manifest, and independently
  re-read it before enabling a verified verdict.

Backend-neutral SQLite/PostgreSQL persistence, universal durable-step
instrumentation, and retirement of split legacy stores are deliberately
separated into `01KYVKPN6JHD19ZRM3WQF9XV8S`, associated with Native Parity and
Platformization. They remain mandatory platform work, but they do not prevent
this concrete release from proving the backend it actually deploys.
