# Megaplan Maintenance

Canonical initiative for Megaplan maintenance research, watchdog supervision, safe repair custody, the six-hour operational unblocker, and the 24-hour efficiency auditor. `chain.yaml` is deliberately launch-ready but unlaunched; source edits here do not authorize changes to any paused or in-flight runtime.

The chain-referenced milestone briefs under `briefs/` are canonical. Architecture decisions live under `decisions/`, evidence syntheses under `research/`, and operator handoffs under `handoff/`.

## Resident-managed scheduling

- [Flexible resident-managed scheduling implementation and operator handoff](handoff/flexible-resident-managed-scheduling-implementation-20260716.md) — delivered single-resident control-plane foundation for durable definitions, immutable occurrences, managed-agent launch custody, time/event scheduling, lifecycle, recovery, quotas, observability, and deployment evidence.
- The live six-hour VP progress audit is the first recurrence migrated to that control plane: one fixed-delay resident definition owns recurrence, while the existing report-only handler and payload remain the occurrence target. The supported `resident schedule add/list/cancel` front door covers explicit-time one-shots, anchored intervals, cron, and timezone/DST-aware wall-clock calendars.
- Canonical requirements source: `research/flexible-resident-managed-subagent-scheduling-architecture-20260716.md`, authored by durable resident run `subagent-20260716-180912-f35a37b5`. The raw run artifacts are cited in the implementation handoff so the source analysis remains auditable even though it was produced in the separate project checkout.

## Current incident and recovery plans

- [Resident non-mutating success-chain incident — 2026-07-16](research/resident-nonmutating-success-chain-incident-20260716.md) — four-run Discord chain reconstruction, root verification/classification contract correction, regression evidence, local integration custody, and durable follow-up proof.
- [Custody control plane Superfixer recovery plan — 2026-07-16](research/custody-control-plane-superfixer-recovery-plan-20260716.md) — evidence-backed reconstruction of the `custody-control-plane-20260714` repair sessions, L1/L2/L3 failure analysis, implementation and deployment controls, and the operational automated-recovery acceptance gate.

The retired `.megaplan/initiatives/superfixer-repair-custody/` document set remains historical input. Custody Control Plane owns the authority/transition contracts; this initiative owns the operational repair and audit product. Do not launch a duplicate Superfixer initiative from the retired set.
