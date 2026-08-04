# Architecture-fit and minimality gate — 2026-08-04

Gate ID: `architecture-fit-minimality-gate.v1`

This is a cross-cutting acceptance gate, not a new control plane or an extra
milestone. The critique epic must fit the existing Custody Control Plane:
[`../custody-control-plane/NORTHSTAR.md`](../custody-control-plane/NORTHSTAR.md)
and its M6A–M11 ownership/adoption work.

## Canonical ownership

| Concern | Existing owner | Critique responsibility |
| --- | --- | --- |
| Grants, fences, accepted claims/decisions, quarantine | Run Authority | Consume and validate; never duplicate |
| Attempt/effect evidence, provenance, receipts, payload policy | WBC | Use the canonical store/outbox and schemas |
| Occurrence identity, lease/epoch, transfer, recovery, reconciliation | Custody | Request/verify custody; never create a second ledger |
| Status, liveness, diagnostics and operator views | Rebuildable projections/observers | Read only; never authorize action |
| Critique semantics and product workflow | Megaplan/Critique Ledger | Remain domain-owned; do not move into generic authority |

## Required minimality proof

Every F1–F8 handoff must include an architecture-fit receipt proving:

- every new state field and mutation has exactly one existing owner;
- no new authority ledger, event bus, snapshot authority, fixer framework,
  daemon, or persistence service was introduced without an explicit reviewed
  exception;
- each compatibility writer/reader is either retired, fenced read-only, or has
  an owner, expiry, and removal proof;
- at least one complete crash, response-loss, restart, or stale-evidence slice
  is proven end-to-end through WBC + Run Authority + Custody before broadening
  inventory;
- implementation, review, and evidence work are separated from replay,
  queue, compaction, and orchestration overhead in the work ledger; and
- the bounded T6.2/current relaunch remains independently runnable and is not
  held hostage by later platform-wide hardening.

## Sprint placement

- **F1:** produce the ownership matrix, no-new-store decision, and one exact
  occurrence/lease recovery proof before expanding storage or retirement scope.
- **F2:** inventory every launch/resume/override/replay entry point, retire or
  fence bypasses, and prove one admission path rather than adding wrappers.
- **F3:** prove one thin ordinary CL2 path end-to-end before accepting broad
  feature execution.
- **F7:** run the deletion/retirement and complexity audit; unresolved duplicate
  authority is a failed closeout, not documentation debt.
- **Custody M9/M10 alignment:** consume their canonical projection/liveness and
  retry/effect contracts; do not reimplement those systems inside Critique.

## Stop conditions

Stop and obtain an architecture decision if a proposal introduces a competing
writer, positive authority from a projection/process fact, a second recovery
queue, an unbounded watcher/fixer loop, or a new persistence substrate solely
to avoid adopting the existing owner API.
