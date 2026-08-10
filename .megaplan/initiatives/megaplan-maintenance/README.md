# Megaplan Maintenance

Canonical initiative for Megaplan maintenance research, watchdog supervision, safe repair custody, the six-hour operational unblocker, and the 24-hour efficiency auditor. `chain.yaml` is deliberately launch-ready but unlaunched; source edits here do not authorize changes to any paused or in-flight runtime.

The chain-referenced milestone briefs under `briefs/` are canonical. Architecture decisions live under `decisions/`, evidence syntheses under `research/`, and operator handoffs under `handoff/`.

## Brief canonicality

Only the `idea:` paths in `chain.yaml` are executable milestone inputs. The suffixed July copies remain for audit history and must not be used to plan or launch work.

| Milestone | Canonical brief | Deprecated non-canonical copy | Reason for disposition |
| --- | --- | --- | --- |
| M1 | `briefs/m1-containment-and-truth.md` | `briefs/m1-containment-and-truthful-control.md` | July audit copy; current M1 owns the updated containment boundary and hands off to the consumer-only M2. |
| M2 | `briefs/m2-coherent-authority.md` | `briefs/m2-coherent-evidence-and-authority.md` | July ranks/schema names and ledger language are stale; current M2 consumes M6A–M11 and Native Parity contracts. |
| M3 | `briefs/m3-independent-verification.md` | `briefs/m3-independent-verification-and-reopen.md` | July reopen/rank/model-pin copy is superseded; current M3 integrates the accepted Custody recovery and Native verification seams. |
| M4 | `briefs/m4-six-hour-operational-unblocker.md` | `briefs/m4-six-hour-feedback-product.md` | The old read-only/exact-six-hour product conflicts with the bounded-action operational product and the current next-three-hour cadence. |
| M5 | `briefs/m5-daily-efficiency-auditor.md` | — | The 24-hour efficiency product is genuinely new and has no canonical duplicate. |

The four deprecated files are explicitly bannered as historical and are not referenced by the chain.

## Resident-managed scheduling

- [Flexible resident-managed scheduling implementation and operator handoff](handoff/flexible-resident-managed-scheduling-implementation-20260716.md) — delivered single-resident control-plane foundation for durable definitions, immutable occurrences, managed-agent launch custody, time/event scheduling, lifecycle, recovery, quotas, observability, and deployment evidence.
- The live six-hour VP progress audit is the first recurrence migrated to that control plane: one fixed-delay resident definition owns recurrence, while the existing report-only handler and payload remain the occurrence target. The supported `resident schedule add/list/cancel` front door covers explicit-time one-shots, anchored intervals, cron, and timezone/DST-aware wall-clock calendars.
- Canonical requirements source: `research/flexible-resident-managed-subagent-scheduling-architecture-20260716.md`, authored by durable resident run `subagent-20260716-180912-f35a37b5`. The raw run artifacts are cited in the implementation handoff so the source analysis remains auditable even though it was produced in the separate project checkout.

## Current incident and recovery plans

- [Resident non-mutating success-chain incident — 2026-07-16](research/resident-nonmutating-success-chain-incident-20260716.md) — four-run Discord chain reconstruction, root verification/classification contract correction, regression evidence, local integration custody, and durable follow-up proof.
- [Custody control plane Superfixer recovery plan — 2026-07-16](research/custody-control-plane-superfixer-recovery-plan-20260716.md) — evidence-backed reconstruction of the `custody-control-plane-20260714` repair sessions, L1/L2/L3 failure analysis, implementation and deployment controls, and the operational automated-recovery acceptance gate.

The retired `.megaplan/initiatives/superfixer-repair-custody/` document set remains historical input. Custody Control Plane owns the authority/transition contracts; this initiative owns the operational repair and audit product. Do not launch a duplicate Superfixer initiative from the retired set.
- [Flexible resident-managed scheduling implementation and operator handoff](handoff/flexible-resident-managed-scheduling-implementation-20260716.md) — durable definitions, immutable occurrences, managed-agent launch custody, lifecycle, recovery, quotas, and observability.
- Canonical requirements: [flexible resident-managed subagent scheduling architecture](research/flexible-resident-managed-subagent-scheduling-architecture-20260716.md).
