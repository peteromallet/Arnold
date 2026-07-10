# M5 — Startup/Continuous Recovery, Migration, and Backward Compatibility

## Outcome

Make the unified lifecycle self-healing across resident restarts and continuously reconcile partial current and legacy states, then provide a reversible migration/cutover path that preserves existing manifests and Discord behavior.

## Scope

In scope: startup recovery before accepting new work; continuous bounded reconciliation; reclaim expired leases; replay incomplete inbound turns; reconcile ambiguous/orphaned launches and sends; legacy record discovery/import/projection; additive backfill; dual-read/write compatibility as justified; feature flags and cutover/rollback; repair commands through constrained resident interfaces; recovery metrics. Keep the sprint within roughly two human-weeks.

Out of scope: destructive legacy deletion, unrelated chain/workspace cleanup, broad data-store replacement, or final production rollout execution.

## Locked decisions

- Startup reconciliation precedes ingress readiness.
- Continuous recovery is idempotent, fence-aware, safe under concurrent workers, and uses ledger transitions rather than silent file mutation.
- Migration is additive, versioned, observable, and reversible; existing `arnold-resident-agent-run-v1` plus older readable manifests/fields remain supported.
- Ambiguous external outcomes are surfaced and reconciled; they are not guessed terminal.

## Open questions for the plan

- Which legacy combinations can be deterministically imported and which must become operator-visible `unknown` cases?
- What bounded startup budget permits readiness while ensuring owned work is not bypassed?
- What exact flag sequence supports shadow/dual-write, canary authority switch, and rollback without split-brain truth?

## Constraints

No destructive mutation of unrelated active chains/workspaces. No arbitrary remote shell commands. Recovery queries must be indexed/bounded, and failure to reconcile must degrade visibly rather than blocking forever without status.

## Done criteria and acceptance evidence

- A seeded-state matrix covers every lifecycle boundary: accepted-only, grouped/unclaimed, claimed/expired, launch-intended, ambiguous-running, result-ready, ack/terminal pending, sending/expired, unknown, dead-letter, and terminal.
- Repeated startup and continuous sweeps converge idempotently with no duplicate execution/send and no terminal regression.
- Legacy fixtures—including current and prior manifest schemas and mutable delivery-field combinations—remain readable and receive deterministic migration/projection outcomes.
- Feature-flag tests prove old-only, shadow/dual, new-authority, and rollback modes; split-brain writes are detected and alerted.
- Operator recovery is available through constrained canonical commands/tools and records audited transitions.

## Touchpoints

Expected areas: resident startup/runtime/scheduler or recovery worker, store migrations, subagent discovery/sweep, config/service readiness, status/hot context, and migration/recovery tests.

## Anti-scope

Do not remove compatibility code or delete/backfill unrelated runtime state. Do not modify other active cloud session markers.
