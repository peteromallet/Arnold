# Custody Control Plane — Holistic Run Authority Runtime Migration

This is the canonical durable epic for completing pipeline-wide adoption of the
Run Authority contract/runtime. It reuses the existing Custody Control Plane
initiative because that initiative already owns the authority-lineage audit,
migration matrix, canonical run-state/custody foundation, and the original
residual migration design.

## What already exists

- Custody M1-M4 delivered the canonical run-state resolver, coherent evidence
  model, custody integrations, repair verification, and auditor coverage. Their
  briefs remain historical lineage and are not pending chain milestones.
- `runauthority-epic` landed grants, accepted attempts/decisions, fences,
  quarantine, and operational views. Its three current milestone completion
  receipts are nevertheless rejected, and canonical verification reports three
  divergences. Nominal `done`, merged PRs, and manifest presence are not enough.
- Workflow Boundary Contracts (WBC) owns boundary declarations, the durable
  execution-attempt/effect ledger, payload/reference policy, semantic findings,
  and supported-runtime conformance. This epic consumes those outputs by exact
  version and must not recreate them.

## Unified residual prevention epic

The executable chain now contains eight ordered milestones:

1. M5 reconciles all three Run Authority receipts, proves zero divergence, then
   writes and attests the metadata-only retirement marker for the exact
   `.megaplan/initiatives/runauthority-epic/` initiative.
2. M6 pins the reconciled Run Authority and WBC evidence and freezes the
   residual zero-exemption map.
3. M7 consolidates remaining authoritative writers behind the existing Run
   Authority/WBC contracts and controlled writer boundary.
4. M8 migrates residual runtime, chain, resident, and cloud adopters.
5. M8A adds Megaplan-owned DAG feasibility, complexity, deterministic
   validation, launcher bounds, repair-adoption, and executor circuit controls
   without moving those policies into Run Authority.
6. M9 makes status, liveness, and operator surfaces rebuildable projections of
   one reducer and joins productive-versus-replayed latency/cost evidence.
7. M10 makes retry, event-driven recovery, replay, and external effects safe,
   exact-signature-bound, and independently verifiable with p95 unblock under
   five minutes plus the six-hour reconciliation backstop.
8. M11 proves conformance through captured replay, idle and worker/repair
   canaries, controlled installed-runtime deployment, a genuine blocked-run
   recovery, and evidence-gated bypass retirement.

`briefs/m5-post-wbc-custody-convergence.md` is retained as an earlier bounded
follow-up proposal. The eight-milestone chain supersedes it as executable scope;
its useful cloud-custody constraints are absorbed into M8-M11 and M8A.

The authoritative relationship, ownership matrix, F01-F17 prevention mapping,
rollout gates, unknowns, and completion contract are in
`research/unified-authority-efficiency-prevention-20260714.md`.

## Launch posture

The chain is deliberately unlaunched and fail-closed. M5 does not require
already-accepted Run Authority receipts, WBC completion, or the later migration
approval: producing genuine Run Authority completion/retirement evidence is its
purpose. Its only chain-entry checks preserve the three-milestone source lineage
and manifest claim as inputs to reconcile; they do not assert acceptance. The
serial chain and manual milestone merge gate block M6 until M5 has
three accepted receipts, zero canonical verification divergences, a regenerated
manifest, the canonical `runauthority-epic/.retired` marker, and its
content-addressed retirement attestation. M6 must then validate current WBC
evidence, and M7 cannot begin implementation until M6's ownership handoff and
the approval record are accepted. Planning completion grants no authority to
start, resume, execute, merge, deploy, or delete anything.
