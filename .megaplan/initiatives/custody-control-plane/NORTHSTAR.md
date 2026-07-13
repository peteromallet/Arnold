---
type: anchor
anchor_type: north_star
slug: custody-control-plane
title: 'North Star: Custody Control Plane'
created_at: '2026-07-07T19:24:43.691296+00:00'
---

# North Star: Custody Control Plane

## End State

The "derived-state-drift" failure class is mechanically impossible: custody layers (watchdog, L1 repair, L2 meta-repair, L3 auditor, status-custody) never trust cached/derived state over ground truth. ONE custody control plane — a canonical ground-truth resolver `resolve_run_state() -> CanonicalRunState` (reads 6 sources in ground-truth order: live process, plan state.json, execute/finalize artifacts, chain state, repair-data, PR/CI), an event-sourced incident ledger (projection, not authority), a repair custody contract, and trustworthiness criteria (liveness ≠ success, mandatory `verify_retrigger_success`) — is consumed at every custody decision. Six validated gaps are closed: read-coherence, profile-pin-vs-tier residual, audit-the-auditor, DRIFT_DETECTED observability, enforcement-as-gate, external coverage (red-main CI + engine-tree consistency). Supersedes canonical-run-state-control-plane + incident-control-plane + superfixer-repair-custody + tiered-repair-hardening.

## Non-Negotiables

- The resolver is the single classification authority at every custody decision point (status, dispatch, watchdog, chain guards, L2, L3). Dispatch REJECTS inputs not from `resolve_run_state()` (enforcement-as-gate).
- Live beats stale; evidence beats labels; liveness ≠ success; `verify_retrigger_success()` is the only writer of terminal success (fail-closed).
- The resolver gathers a READ-COHERENT snapshot (atomic/version-token), not 6 independent reads.
- Drift is EMITTED (`DRIFT_DETECTED`), never silently suppressed.
- The resolver + L2 are themselves audited by L3 (audit-the-auditor: L3 recursion guard + `auditor_escalate_to_human`).
- `manual_review` is never a dispatch policy; unknown fails safe.

## Explicit Non-Goals

- Profile/model routing beyond closing the profile-pin-vs-tier residual (#2) — mostly fixed via `2f15007a`.
- Workspace restoration for deleted sessions (DETECT via `BROKEN_STATE_MACHINE`, don't recreate).
- Fixing main CI (DETECT red-main as base-health, don't fix).
- Real code/planner bugs (AWF242, test-selection) — the resolver reports, doesn't fix.
- Merging workflow-boundary-contracts (stays separate; consumed as resolver evidence).

## Allowed Temporary Bridges

- `ARNOLD_RESOLVER_OBSERVE=1` / `ENFORCEMENT=0` feature flags during rollout (observe before enforce).
- Legacy derived-state fields kept during migration, with `stale_sources` surfacing disagreement.
- Bridge retirement completed on 2026-07-08: the 3 duplicate initiatives are superseded, merge-disabled, and retirement-logged.

## Drift Signals

- The resolver is bypassed at a call site (dispatch consumes raw labels).
- A known July-2026 incident shape isn't caught by a fixture.
- Drift is suppressed (not emitted) — operators lose visibility.
- L3 can't audit the resolver/L2 (no backstop for the backstop).
- The 3 duplicate initiatives get re-launched as separate chains.

## Definitive migration extension

The resolver and custody work are necessary substrate, not the final authority
model. The deepest practical end state is one append-only causal history for
workflow attempts, effects, transitions, custody, and decisions. Every record
is bound to an exact workflow/contract version, run and attempt identity,
coordinator fence, idempotency key, coherent evidence snapshot, and causal
parents. Mutable JSON, markers, process probes, logs, receipts, status files,
and provider facts are evidence or rebuildable projections only.

All supported writers must append through the fenced history API before an
effect or transition is considered accepted. All authority-increasing readers
must consume a version-matched reducer view, return `UNKNOWN` for incomplete or
incoherent evidence, and reread after mutation. Recovery closes only after an
independent verifier proves both blocker clearance and resumed authoritative
progress. Legacy bypasses fail closed, then are deleted behind machine-readable
conformance and zero-reader gates.

## Initiative lineage and bounded follow-up

M1-M4 are completed historical foundation: resolver/read coherence, status and
dispatch integration, watchdog/repair verification, and auditor coverage. Their
briefs remain under `briefs/` as lineage and acceptance context; they are not
pending executable milestones.

Workflow Boundary Contracts owns the shared boundary declarations and durable
attempt/effect evidence needed by the next custody step. The only pending
initiative milestone is a bounded post-WBC convergence of the Megaplan
cloud-chain custody read and decision path. It consumes WBC and Run Authority by
exact version, preserves the North Star above, and must not recreate their
ledgers, decisions, lifecycle, or conformance programs.
