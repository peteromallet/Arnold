# Megaplan Prep Record — Neutral Managed-Agent Lifecycle Standardization

Date: 2026-07-16

## Evidence and baseline

Prep reconciled the canonical initiative, its initialized five-milestone
history, the superseded eleven- and three-sprint shapes, related initiatives,
ticket `01KTPVVVVV002AGENTRUNTIME`, WBC/Run Authority/Custody ownership records,
and the primary research produced by durable run
`subagent-20260716-155100-6d5344d7` (raw manifest:
`.megaplan/plans/resident-subagents/subagent-20260716-155100-6d5344d7/manifest.json`).
Its SHA-256 is
`74492ebbf31a7b96f3b0214bc4bf47abd05133760477fd1251968ba6eb5a7f10`.

Planning mutations were based on local target
`refs/heads/consolidate/arnold-runtime-activation-20260714` at
`c267920b6719fb35636e1da0071b5863ec5b2a0c`. The project and resident launch
checkouts were concurrently dirty and were read only. This baseline is planning
custody, not a future implementation target guarantee; L1 must re-inventory the
selected target revision.

## Sizing

Epic: eight sequential sprint-equivalents, each approximately two skilled-human
weeks. Three lifecycle migration sprints precede the original five compiler
sprints. The work cannot safely fit a single Megaplan: it spans additive public
schemas, durable transaction/identity rules, three caller families, cross-
backend conformance, privacy/authority boundaries, five compiler product
verticals, and explicit reviewed handoffs.

The serial graph is L1 -> L2 -> L3 -> C1 -> C2 -> C3 -> C4 -> C5. L1/L2 may
enable provisional C1 experiments, but C1 completion depends on L3 coverage.
Every successor consumes one reviewed content-addressed handoff; no milestone
depends only on prose or a mutable status view.

## Dial choices

- **L1:** Overall plan difficulty 5/5; selected profile `partnered-5`; because a
  locally valid schema/store split can silently create a competing authority
  ledger, duplicate starts, or privacy leakage. Robustness `full`; depth `high`;
  directed prep.
- **L2:** Overall plan difficulty 5/5; selected profile `partnered-5`; because
  resident delivery and automatic repair can pass focused tests while restart,
  observer classification, or dual-write behavior duplicates effects. Robustness
  `full`; depth `high`; directed prep.
- **L3:** Overall plan difficulty 5/5; selected profile `partnered-5`; because
  wrapping a shared worker seam can accidentally absorb Megaplan gate, retry,
  session, acceptance, or authorization semantics. Robustness `full`; depth
  `high`; directed prep.
- **C1:** Overall plan difficulty 5/5; selected profile `partnered-5`; because
  wrong evidence ownership, native position, eligibility, or transaction
  boundaries can skip/double-count source ranges while tests appear green.
  Robustness `full`; depth `high`; directed prep.
- **C2:** Overall plan difficulty 5/5; selected profile `partnered-5`; because
  claim/evidence classification and direct-model validation are durable public
  data contracts that can silently turn inference/proposal into fact.
  Robustness `full`; depth `high`; directed prep.
- **C3:** Overall plan difficulty 5/5; selected profile `partnered-5`; because
  correction, synthesis, hierarchy, and scoped search can create a mutable or
  leaking parallel truth source. Robustness `full`; depth `high`; directed prep.
- **C4:** Overall plan difficulty 5/5; selected profile `partnered-5`; because
  stale, contradictory, or over-authorized promoted knowledge can mislead work
  beyond the producing run. Robustness `full`; depth `high`; directed prep.
- **C5:** Overall plan difficulty 4/5; selected profile `partnered-5`; because
  conformance and producer matrices can false-green through silent seam gaps,
  while consolidation/rollback must preserve lineage. Robustness `full`; depth
  `high`; directed prep. The default high profile is retained despite score 4.

Recorded shorthand: `partnered-5/full/high +prep` for all milestones. Vendor is
`codex`; compiler extraction provider remains `direct`. High depth is justified
by target-revision inventory, schema/ownership reconciliation, and cross-system
ordering work—not by size alone.

## Decision gates

G1 package ownership, G2 journal/transaction authority, G3 neighboring
profile/fallback handoff, G4 privacy/retention, G5 backend capability floor, G6
compilation grouping, G7 promotion review tiers, and G8 per-seam retirement are
recorded in README and the architecture decision with owner, options, evidence,
and blocking effect. G1-G5 block affected L1 contract freeze; G6 blocks C1; G7
blocks C4; G8 blocks only production cutover/deletion, not implementation and
shadow readiness.

## Chain safety choices

- `base_branch` is the verified non-main resident target
  `consolidate/arnold-runtime-activation-20260714`, not inferred `main`.
- Top-level `anchors.north_star: NORTHSTAR.md` is declared.
- Failure and escalation stop the chain; milestones are never skipped or
  automatically retried from scratch.
- `driver.auto_approve: false`; planning does not grant execution approval.
- No seed plan: historical initialized plan
  `m1-durable-capture-cursors-20260713-2045` completed no implementation and is
  not a predecessor or resume source.

## Prep boundary

This prep record shapes future work only. No `megaplan init`, chain start,
model/agent launch, implementation, push, PR, deployment, restart, production
enablement, or retirement was performed.
