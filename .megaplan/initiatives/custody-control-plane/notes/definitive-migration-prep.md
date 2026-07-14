---
type: prep
date: 2026-07-13
classification: architecture-migration-D5
---

# Holistic Run Authority runtime migration prep

## Sizing and ownership reconciliation

The follow-up is larger than two weeks and is split into eight ordered, sprint-
sized milestones. Custody M1-M4 are completed historical foundation. Run
Authority's implementation and three milestone merges are landed, but all three
current completion receipts are rejected: phase evidence is stale or missing,
landed-diff/content addresses disagree, and structural suites have collection/
import failures. Canonical verification reports three divergences. M5 repairs
that proof and retirement custody before any residual migration work.

WBC has operationalized much of the original broad plan: boundary declarations,
the durable execution-attempt/effect ledger, payload/reference policy, semantic
findings, and supported-runtime conformance. Its resident session is in flight
and this checkout has no WBC completion manifest. M5 is independent of WBC and
may start without already-accepted Run Authority receipts. M6 consumes M5's
accepted evidence and cannot complete until a current WBC manifest exists;
manifest-proven WBC rows then become prerequisite evidence. M7 implementation
also requires the accepted approval record. The epic does not reimplement or
rename C1-C6.

The earlier one-milestone post-WBC cloud-custody proposal was too narrow to be
independently legible as the requested pipeline-wide migration. It remains
lineage, while M6-M11 plus M8A absorb its constraints and cover the residual
writer, reader, planner/compiler/executor efficiency, projection, recovery/
effect, and legacy-retirement gaps.

## Per-milestone dial selection

| Milestone | Difficulty / profile | Robustness / depth | Rationale |
|---|---|---|---|
| M5 receipt reconciliation/retirement | 5/5, `partnered-5` | `thorough/high`, `+prep` | Historical content-address and structural-suite reconciliation can falsely authorize every later sprint if any receipt is waived or stale. |
| M6 contract and residual inventory | 5/5, `partnered-5` | `full/high`, `+prep` | Read-only, but an omitted owner or bypass poisons every downstream plan while local checks can remain green. |
| M7 controlled writers | 5/5, `partnered-5` | `thorough/high` | Writer ordering, fencing, and partial persistence can duplicate effects or advance authority non-locally. |
| M8 runtime adoption | 5/5, `partnered-5` | `thorough/high` | Cross-runtime adapters and compatibility paths can silently preserve a second authority. |
| M8A planner/compiler/executor efficiency | 5/5, `partnered-5` | `thorough/high` | DAG/task/retry controls are a separate domain; wrong rules can change semantics, accept stale repaired work, or hide legitimate cost. |
| M9 projections/liveness | 5/5, `partnered-5` | `thorough/high` | False liveness or optimistic status can trigger production dispatch/repair despite locally correct projections. |
| M10 retry/recovery/effects | 5/5, `partnered-5` | `thorough/high` | Crash ambiguity and non-compensable effects require adversarial critique and fault-injection evidence. |
| M11 conformance/retirement | 5/5, `partnered-5` | `thorough/high` | A globally wrong deletion/parity decision can permanently violate authority and recovery invariants. |

All milestones use Codex and high author depth. `xhigh`/`max` are not justified:
the architecture and ownership boundaries are already established; the hard
work is exhaustive reconciliation and safe adoption. M5 uses thorough plus
directed prep because it reconstructs authoritative evidence across three
historical plans. M6 uses full robustness
plus directed prep because it is observe-only. M7-M11 and M8A use thorough because each
can create or certify production-incident-class authority failures.

## Fail-closed posture

The serial chain uses manual milestone review/merge and `auto_approve: false`.
M5 is admitted without accepted Run Authority receipts; it cannot hand off
until all three are accepted, canonical verification has zero divergences, and
retirement is content-addressed. M6 requires that handoff and current WBC proof.
M7-M11 and M8A also require the accepted approval record. Chain failure, escalation,
stale evidence, or hash mismatch stops progression. Production enforcement,
mutating repair, provider effects, deployment, and deletion remain action-off
until separately authorized by their milestone gates.
