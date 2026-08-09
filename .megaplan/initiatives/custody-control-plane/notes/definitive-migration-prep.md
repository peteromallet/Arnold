---
type: prep
date: 2026-07-13
classification: architecture-migration-D5
---

# Holistic Run Authority runtime migration prep

## Sizing and ownership reconciliation

The follow-up is larger than two weeks and is split into nine ordered, sprint-
sized milestones. Custody M1-M4 are completed historical foundation. Run
Authority's implementation and three milestone merges are landed, but all three
current completion receipts are rejected: phase evidence is stale or missing,
landed-diff/content addresses disagree, and structural suites have collection/
import failures. Canonical verification reports three divergences. M5 repairs
that proof and retirement custody before any residual migration work.

WBC has defined much of the original broad contract: boundary declarations,
execution-attempt/effect evidence schemas, provenance, payload/reference policy,
semantic findings, and supported-runtime conformance metadata. Read-only audit
of completed candidate `cbe69337…` found the ledger is explicitly schema-only,
with no production store/API, and only 5 auto-matched plus 8 manual-emission
contracts versus 13 declared-only and 9 unknown. The support manifest cannot be
treated as universal adoption proof.
Candidate `cbe69337…` is landed by audited no-ff merge `24afce00…`. The old
four-milestone cloud terminal state is not a completion manifest for the current
C1-C6 chain, so the custody chain never claims it as such. M5 remains
semantically independent of WBC and may start with rejected Run Authority
receipts after the audited merge launch precondition passes. M6 consumes M5's
accepted evidence and binds the exact merge to current ancestry/support/runtime
proof while generating a call-site/runtime boundary
inventory. M6A then implements the WBC-owned transactional store/API and
migration/data-policy substrate; M8 adopts every producer. M6A and later
implementation also require the accepted approval record. The epic preserves
C1-C6 identity and WBC ownership.

The settled split is conjunctive, not hierarchical: Run Authority owns grants,
subject attempts, accepted claims/decisions and coordinator fences; WBC owns
boundary/attempt/effect evidence; Custody owns action-target and repair-
occurrence leases, custody epochs, transfer/reclaim/recovery/reconciliation.
Projections can block or diagnose but cannot positively authorize an action.

The earlier one-milestone post-WBC cloud-custody proposal was too narrow to be
independently legible as the requested pipeline-wide migration. It remains
lineage, while M6-M11 plus M6A/M8A absorb its constraints and cover the residual
writer, reader, planner/compiler/executor efficiency, projection, recovery/
effect, and legacy-retirement gaps.

## Per-milestone dial selection

| Milestone | Difficulty / profile | Robustness / depth | Rationale |
|---|---|---|---|
| M5 receipt reconciliation/retirement | 5/5, `partnered-5` | `thorough/high`, `+prep` | Historical content-address and structural-suite reconciliation can falsely authorize every later sprint if any receipt is waived or stale. |
| M6 contract and residual inventory | 5/5, `partnered-5` | `full/high`, `+prep` | Read-only, but an omitted owner or bypass poisons every downstream plan while local checks can remain green. |
| M6A WBC transactional ledger foundation | 5/5, `partnered-5` | `thorough/high`, `+prep` | Store/API ordering, crash ambiguity, payload governance, and migration failure can make every later producer appear adopted while durable evidence is absent or false. |
| M7 controlled writers | 5/5, `partnered-5` | `thorough/high` | Custody lease/epoch design, dual-fence writer ordering, and partial persistence can duplicate effects or advance authority non-locally. |
| M8 runtime adoption | 5/5, `partnered-5` | `thorough/high` | Cross-runtime adapters and compatibility paths can silently preserve a second authority. |
| M8A planner/compiler/executor efficiency | 5/5, `partnered-5` | `thorough/high` | DAG/task/retry controls are a separate domain; wrong rules can change semantics, accept stale repaired work, or hide legitimate cost. |
| M9 projections/liveness | 5/5, `partnered-5` | `thorough/high` | False liveness or optimistic status can trigger production dispatch/repair despite locally correct projections. |
| M10 retry/recovery/effects | 5/5, `partnered-5` | `thorough/high` | Crash ambiguity and non-compensable effects require adversarial critique and fault-injection evidence. |
| M11 acceptance/conformance/retirement | 5/5, `partnered-5` | `thorough/high` | A globally wrong cross-contract gate or deletion/parity decision can permanently violate authority and recovery invariants. |

All milestones use Codex and high author depth. `xhigh`/`max` are not justified:
the architecture and ownership boundaries are already established; the hard
work is exhaustive reconciliation and safe adoption. M5 uses thorough plus
directed prep because it reconstructs authoritative evidence across three
historical plans. M6 uses full robustness
plus directed prep because it is observe-only. M6A, M7-M11 and M8A use thorough because each
can create or certify production-incident-class authority failures.

## Fail-closed posture

The serial chain uses manual milestone review/merge and `auto_approve: false`.
Chain entry first requires the audited WBC merge evidence and immutable
initiative/runtime binding; it explicitly rejects old S1-S4 terminal state as
current C1-C6 completion. M5 is then admitted
without accepted Run Authority receipts; it cannot hand off
until all three are accepted, canonical verification has zero divergences, and
retirement is content-addressed. M6 requires that handoff and current WBC
ancestry/support/runtime proof.
M6A, M7-M11 and M8A also require the accepted approval record. Chain failure, escalation,
stale evidence, or hash mismatch stops progression. Production enforcement,
mutating repair, provider effects, deployment, and deletion remain action-off
until separately authorized by their milestone gates.
