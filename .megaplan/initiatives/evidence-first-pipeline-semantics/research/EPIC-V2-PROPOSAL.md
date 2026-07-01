# Evidence-First Pipeline Semantics — v2 proposal (for approval before brief rewrites)

Status: PROPOSAL. Does not modify the live m0–m10 briefs or chain.yaml. Product of
review by 4 per-milestone reviewers (GPT-5.5), 4 adversarial/cost/contrarian/slice
lenses (DeepSeek), and 2 frontier direction + cost-of-simplification reviews
(GPT-5.5 + Opus, run independently). Two cross-checks converged on the same verdict.

## What changed from v1 and why (one page)

**Reframe (the organizing idea).** Not "compute more evidence" but an **authority
kernel**: define *who is allowed to make each kind of truth* (dispatch, transition,
config-resolution, workspace-mutation, reset), and let evidence *support* those
boundaries. Success metric = **convert every silent proceed into a loud, named,
operator-visible halt-or-waive**, on the surface of *all authority increases* (not
all reads — status may be eventually consistent; transitions may not). The four
dogfood failures were *unsurfaced* signals, not *uncomputed* ones.

**Prevent at the source before verifying after the fact.** Two subtractive moves
from the contrarian, adopted because they remove failure classes instead of
detecting them:
- **Engine/Target Isolation becomes the FIRST milestone** (pulled from deferred
  ticket `01KS3DCH9Y…`). Both frontier reviewers' #1 change. Prevents the entire
  contamination class m10 only detected, and removes the dogfood-shadow trap.
- **Routing is recomputed from pinned inputs, never frozen** (the m9 thesis),
  folded into the transition validator.

**Shrink the over-built; keep the invariant.** m7's grand all-readers *projection*
is dropped (it was "a sixth store by another name"), but its load-bearing
*invariant* is restored as a first-class early milestone: a corroborated-`done`
predicate every authority-increasing reader must consult. This is the ONE
non-negotiable add-back both cost-reviews demanded.

**Touch m0–m6 surgically** (locked ≠ frozen-into-contradiction): m6 gains an
unattended-deadlock fallback (the "enforcement-killer" guardrail); m5 gains
reset/reconcile + config-reroute coverage and routing-recompute; objective gates
go async/per-milestone and robustness-gated (cost). Concurrency/TOCTOU discipline
(lease/lock + compare-and-swap-on-inputs + record-the-checked-SHA) applies to every
authority-increasing path.

**Validate against itself.** A post-merge re-baseline deliverable rebuilds the
driver engine from the merged result, so the epic is tested against the very
failure class that motivated it.

Net: ~same milestone count as v1, reshaped prevention-first, smaller per-milestone,
and validated. No new stores; every add-back is a predicate / record / assertion.

## v1 → v2 milestone map

| v2 | source | change |
|----|--------|--------|
| m0 engine/target isolation | deferred ticket | NEW, first; prevention |
| m1 evidence contract + corroborated-`done` predicate | v1 m0 | + `is_task_satisfied(...)` |
| m2 authority-reader migration | v1 m7 (invariant only) | the mandatory add-back, pulled early |
| m3 execute→review→done slice | v1 m1 | unchanged |
| m4 review evidence service | v1 m2 | unchanged |
| m5 objective gates | v1 m3 | + async/per-milestone + robustness-gated |
| m6 provenance + workspace assertions | v1 m4 + reduced m10 | cheap HEAD+dirty-set+checked-SHA at authority transitions (no per-boundary tree hash) |
| m7 transition validator + routing recompute | v1 m5 + folded m9 | + reset/reconcile/config-reroute + recompute-from-pinned + `routing_resolution_decision` + TOCTOU |
| m8 capability dispatch gate | v1 m8 | kept; tighten: actual-vs-adjudicated-tier, auth-proven availability, batch-level |
| m9 atomic reset + reconcile | v1 m7 (reset half) | recovery ops through m7's writer; fenced/archived |
| m10 rollout to enforcement | v1 m6 | + unattended-deadlock fallback + protect all-authority-increases + robustness-gating |
| m11 post-merge re-baseline | NEW | validate epic against its own failure class |

## Proposed chain.yaml

```yaml
base_branch: arnold-epic

milestones:
  - label: m0-engine-target-isolation
    profile: premium
    robustness: thorough
    depth: high
    notes: "PREVENTION-FIRST. Driver runs from an isolated frozen worktree/container; engine is never target-writable; engine==target overlap refused before any mutating phase (explicit recorded waiver for local dev). Retires most of contamination detection and removes the dogfood-shadow trap."

  - label: m1-evidence-contract
    profile: apex
    robustness: thorough
    depth: high
    notes: "EvidenceRef, TransitionDecision, trust classes (claim/evidence/judgment/routing), provenance + schema/version, telemetry skeleton. PLUS the corroborated-done predicate is_task_satisfied(task, nucleus, head/code_hash). No enforcement."

  - label: m2-authority-reader-migration
    profile: premium
    robustness: thorough
    depth: high
    notes: "MANDATORY ADD-BACK (m7 invariant, not architecture). Every authority-increasing reader — task selection, dependency scheduling, resume, chain advance — consults the corroborated-done predicate and resolves divergence DOWN before treating work as done. No projection store. Closes the phantom-dependency class early, before enforce."

  - label: m3-first-slice
    profile: premium
    robustness: thorough
    depth: high
    notes: "Vertical proof for execute->review->done: review-start evidence, evidence-backed review findings, TransitionDecision for review->done."

  - label: m4-review-evidence-service
    profile: partnered
    robustness: full
    depth: medium
    notes: "Generalize review-time evidence across all review paths; migrate review payloads toward evidence refs."

  - label: m5-objective-gates
    profile: premium
    robustness: thorough
    depth: high
    notes: "Machine-verifiable criteria -> engine-owned checks + command evidence. Run ASYNC at milestone-start (not per-phase-boundary); robustness-gate (light skips, full warn, thorough enforce)."

  - label: m6-provenance-and-workspace-assertions
    profile: directed
    robustness: full
    depth: medium
    notes: "Artifact provenance + freshness helpers. PLUS cheap target HEAD + dirty-set + checked-SHA assertions at authority transitions only (execute-start, review-start, done/advance, reset) — replaces v1 m10's per-boundary tree hashing and supplies the TOCTOU checked-SHA."

  - label: m7-transition-validator-routing
    profile: premium
    robustness: thorough
    depth: high
    notes: "Full TransitionWriter over authority-increasing routes INCLUDING reset/reconcile + config-reroute. Chain/CI SHA-pinning, override waivers. Routing recomputed from pinned inputs (adjudicated tier/task id/policy/profile pinned; tier->model map recomputed), never frozen; emit routing_resolution_decision; carry the frozen-tier_models regression test. Concurrency/TOCTOU: lease/lock + compare-and-swap on inputs + stale-decision rejection."

  - label: m8-capability-dispatch-gate
    profile: partnered
    robustness: thorough
    depth: high
    notes: "Per-dispatch capability evidence; gate ACTUAL model vs ADJUDICATED tier (not resolved spec); availability AUTH-PROVEN (not env/binary proxy); batch-level task evidence. Closes the silent premium->DeepSeek degrade."

  - label: m9-atomic-reset-reconcile
    profile: partnered
    robustness: full
    depth: high
    notes: "Atomic reset + reconcile as RECOVERY operations routed through m7's TransitionWriter; fenced under locks; archive never delete; refuse if head/worktree changed since preflight. The operational core of v1 m7, minus the projection."

  - label: m10-rollout-enforcement
    profile: partnered
    robustness: thorough
    depth: medium
    notes: "shadow->warn->enforce. PLUS mandatory unattended-context fallback: blocked gate with no human -> timeout -> auto-waive-and-record (warn) / fail-with-diagnostics (enforce); NEVER hang. Protect surface = all authority increases. Robustness-gated; legacy/prose/human-deferred defaults."

  - label: m11-post-merge-rebaseline
    profile: directed
    robustness: full
    depth: low
    notes: "Rebuild the frozen driver engine from the merged result and re-run the motivating failure scenarios (silent degrade, contamination, phantom-dep, frozen-config) as regression proof. Validates the epic against its own failure class."

on_failure:
  abort: stop_chain
on_escalate:
  abort: stop_chain
merge_policy: manual

driver:
  robustness: thorough
  auto_approve: true
  max_iterations: 80
  poll_sleep: 8.0
```

## Open decisions for the operator
1. Approve the renumber/reorder (isolation first; authority-readers before enforce), or keep v1 numbering and accept the noted contradictions?
2. m0 isolation: in-repo worktree separation vs container — and the local-dev waiver policy.
3. Is m11 re-baseline a milestone, or a release-gate checklist item outside the chain?
