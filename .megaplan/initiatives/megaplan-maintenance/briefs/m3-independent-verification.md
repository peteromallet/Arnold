# M3 — Fenced custody and independent verification

## Outcome

Separate detection, request, claim, attempt, install, retrigger, verification, closure, and recurrence so recovery is terminal only when an independent later observer proves the original blocker cleared.

## Scope (about one sprint; no more than two weeks)

In scope: one claim per occurrence; renewable lease and monotonic fencing token; stale-worker rejection; occurrence/action idempotency keys; source/install/retrigger receipts; blocker-specific negative controls; immediate, 5-minute, 1-hour, and 6-hour checkpoints; independent verifier identity; delayed verification scheduling/catch-up; recurrence/reopen links; human custody with owner/deadline; canary install and rollback; compatibility for future 24-hour/7-day observations; full custody fault matrix.

Out of scope: daily efficiency clustering; broad production autonomy; any second transition writer; self-verification; force-proceed or human-gate waiver.

## Locked decisions

- Claim key is the operational occurrence; lease/fence is required for every effect and transition.
- Action idempotency includes schema, occurrence, action type, policy version, and target identity.
- Repair actors cannot author terminal verification. Unknown or contradictory evidence leaves custody open.
- PID/tmux health and fresh activity are corroboration only.
- Verified recurrence creates a new occurrence linked to the prior closure/root-cause cluster.
- Source change, installation, retrigger, resumed progress, and verification are distinct events/receipts.

## Open questions / human gate

Approve lease duration/renewal grace, verifier service ownership, safe-repair allowlist, canary target, rollback owner, and unresolved-escalation owner before any automatic effect is enabled.

## Done criteria and handoff

- Concurrency tests prove one valid claim/effect per occurrence and reject stale fencing tokens after lease expiry/reclaim.
- Crash/replay between every lifecycle edge produces neither duplicate effects nor false closure.
- Fault matrix covers alive-but-blocked, legitimate long calls, stale terminal state, failed/wrong install hash, retrigger failure, recurrence, and true human gate.
- Only blocker-cleared negative controls plus resumed-progress evidence close custody; self-verification is rejected.
- One controlled canary proves install → retrigger → immediate/5m/1h/6h verification; forced failure proves rollback and truthful receipts.
- Handoff to M4: stable claim/request API, checkpoint scheduler, recurrence semantics, and verification fixtures that the six-hour loop consumes without owning transition truth.

## Parallelism and anti-scope

Evidence capture and independent tests may fan out. Claim, install/retrigger effects, TransitionWriter mutation, and terminal verification are serialized. Do not alter daily analytics or active-chain topology.
