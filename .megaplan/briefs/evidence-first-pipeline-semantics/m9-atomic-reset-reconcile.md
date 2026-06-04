# M9: Atomic Reset Reconcile

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Provide atomic reset and reconcile as recovery operations routed through M7's `TransitionWriter`, fenced under locks, and grounded in the evidence nucleus without reintroducing the dropped projection-store architecture.

This keeps the operational core of old M7: when stores drift, reconcile reports the divergence and reset rewinds all affected stores together to a verified consistent point. It closes the recovery side of the phantom-dependency class while leaving the all-readers invariant in M2.

## Scope

IN:

- `reconcile(milestone)`: compare live stores against the evidence nucleus and current target head/code hash, classify each claim as fresh/stale/missing/divergent, and emit a structured reconciliation report.
- Atomic `reset-milestone-to-consistent-point`: a single recovery operation that rewinds all affected stores together (working tree to checkpoint where applicable, task ledger, execute artifacts, chain-state pointer, resolved routing/capability state) to a verified consistent point.
- Route reset and reconcile through M7's `TransitionWriter` with durable `TransitionDecision` records.
- Fence reset/reconcile under locks/leases so concurrent driver/cloud operations cannot interleave.
- Archive replaced artifacts/state; never delete silently.
- Preflight target head/worktree state and refuse if head or dirty-set changed before mutation since the checked preflight.
- Validate chain-state pointer / plan selection during recovery so a desynced `current_plan_name` is detected and corrected only through an explicit recovery decision.

OUT:

- No grand all-readers projection store.
- No new authority-reader invariant; M2 owns reader behavior.
- No new evidence collection; use the evidence nucleus, M6 provenance/freshness helpers, and existing objective gate facts.
- No partial reset path.
- No silent deletion of artifacts or state.

## Locked Decisions

- Reset and reconcile are recovery operations, not ordinary readers.
- Reset is atomic across all affected stores or it does not happen.
- Divergence resolves DOWN to unknown/unsatisfied, never up to success.
- Recovery state changes go through M7's `TransitionWriter`.
- Archive, never delete.
- Refuse recovery mutation if head/worktree changed since preflight.

## Open Questions

- Checkpoint granularity: per-phase vs per-milestone.
- How reset interacts with committed work (target HEAD) vs uncommitted execute output.
- Exact archive location and retention policy.
- Migration: how an existing in-flight plan acquires an initial recovery checkpoint.

## Constraints

- Reuse M1 `EvidenceRef` / M6 freshness / M5 gates — no second verifier.
- Reset must be safe under the concurrent driver and `.megaplan/.state-locks`.
- Backwards-compatible: legacy plans without full evidence reconcile as unknown, not as success.
- Recovery operations must be retryable or explicitly non-retryable with diagnostics.

## Done Criteria

1. `reconcile` produces a structured divergence report and never upgrades divergent claims.
2. `reset-milestone-to-consistent-point` rewinds all affected stores together with a durable `TransitionDecision`; partial reset is impossible.
3. Reset/reconcile route through M7's `TransitionWriter`.
4. Recovery operations are fenced under locks/leases and reject stale checked inputs.
5. Replaced artifacts/state are archived, not deleted.
6. Chain-state pointer / plan selection is validated during recovery and repaired only through an explicit decision.
7. Tests cover phantom dependency recovery, config/ledger/worktree divergence, atomic-reset rollback, archive-never-delete, stale head/worktree refusal, concurrent recovery refusal, and legacy-as-unknown.

## Touchpoints

- `completion_contract` / evidence nucleus (M1)
- `megaplan/_core/state.py`, `megaplan/_core/workflow.py`
- chain state (`.megaplan/plans/.chains/chain-*.json`) + `megaplan/chain/__init__.py`
- `megaplan/_core` state-locks
- execute artifacts / task ledger
- a `reconcile` / `reset-milestone` CLI command
- transition writer and recovery route tests
- reconcile, atomic-reset, archive, and stale-preflight tests

## Rubric

- Profile: `partnered`
- Robustness: `full`
- Depth: `high`

Rationale: the projection-store ambition is gone, but recovery still mutates multiple authority-bearing stores. Depth stays high for the atomicity and TOCTOU judgment; robustness can be full because the reader invariant is already handled in M2.

