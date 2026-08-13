# M3 — Custody-bound independent verification

## Outcome

Integrate Maintenance's detection-to-verification product with the accepted Custody and Native Parity substrates so recovery is terminal only when an independent later observer proves the original blocker cleared. M3 consumes, rather than reimplements, the M7 lease/epoch and writer contracts, M10 recovery/effect contract, M11 conformance suite, and C1/C2/S1/S2R evidence/occurrence handoffs.

## Scope (about one sprint; no more than two weeks)

In scope: bind each Maintenance occurrence to the canonical M7 `RepairOccurrenceKey`, `CustodyLease`, custody epoch, Run Authority grant/fence, and M6A WBC attempt identity; use the shared action validator's durable rereads at every authority-increasing edge; add blocker-specific negative controls and independent verifier provenance over C2 proof modes; schedule immediate, 5-minute, 1-hour, and canonical `next_three_hour` checkpoints with legacy six-hour naming only as compatibility; implement delayed verification catch-up, recurrence/reopen links, human escalation references, and Maintenance-owned canary/rollback runbooks that invoke the unified fixer seam; and consume the M11/S2R fault/conformance fixtures without creating a second suite.

Out of scope: implementing M6A's WBC store/outbox; implementing M7 leases, epochs, action validator, controlled-writer registry, TransitionWriter, or repair-receipt substrate; implementing M8–M11 recovery/effect/conformance ownership; implementing C1/C2 completion kernel or S1/S2R Native runtime primitives; daily efficiency clustering; broad production autonomy; any second transition writer; self-verification; force-proceed or human-gate waiver.

## Locked decisions

- Claim key is the operational occurrence, but the occurrence and lease are canonical M7 records; Maintenance stores only the join/reference and never creates a repair-custody store.
- Every effect and transition consumes the current M7 Custody lease/epoch plus Run Authority grant/fence and required M6A WBC evidence; a projection or receipt alone cannot authorize it.
- Action idempotency includes schema, occurrence, action type, policy version, and target identity.
- Repair actors cannot author terminal verification. Unknown or contradictory evidence leaves custody open.
- The verifier is a distinct principal with durable provenance and direct owner-source reads; process separation or a self-declared verifier label is insufficient.
- PID/tmux health and fresh activity are corroboration only.
- Verified recurrence creates a new occurrence linked to the prior closure/root-cause cluster.
- Source change, installation, retrigger, resumed progress, and verification are distinct events/receipts.

## Open questions / human gate

Approve the inherited lease duration/renewal grace and verifier service ownership, safe-repair allowlist, canary target, rollback owner, and unresolved-escalation owner before any automatic effect is enabled.

## Done criteria and handoff

- Integration tests prove Maintenance submits exactly one occurrence-bound request/effect to the canonical M7/M10 seams and rejects stale fencing/epoch evidence after lease expiry/reclaim; they do not test a locally invented lease store.
- Crash/replay between every lifecycle edge produces neither duplicate effects nor false closure.
- Fault matrix covers alive-but-blocked, legitimate long calls, stale terminal state, failed/wrong install hash, retrigger failure, recurrence, and true human gate.
- Only blocker-cleared negative controls plus resumed-progress evidence close custody; self-verification is rejected.
- One controlled canary through the accepted installed runtime proves install → retrigger → immediate/5m/1h/next-three-hour verification; forced failure proves rollback and truthful receipts. The M11 installed-runtime and independent-verifier evidence is consumed, not recreated.
- Handoff to M4: stable owner-source join/request API, checkpoint scheduler, recurrence semantics, and verification fixtures that the operational loop consumes without owning transition truth.

## Parallelism and anti-scope

Evidence capture and independent tests may fan out. Claim, install/retrigger effects, TransitionWriter mutation, and terminal verification are serialized. Do not alter daily analytics or active-chain topology.
