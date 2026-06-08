---
id: 01KTH8484QJQZM16VVQN1654AC
title: Resume Evidence-First M4-M11 after post-M3 pipeline generalization
status: open
source: human
tags:
- evidence-first
- post-m3
- generalization
- epic
codebase_id: null
created_at: '2026-06-07T14:34:57.559724+00:00'
last_edited_at: '2026-06-07T14:34:57.559724+00:00'
epics: []
---

The Evidence-First chain has been intentionally shortened to stop after M3 (`m3-first-slice`) instead of automatically continuing through M4-M11.

Reason: the current architectural decision is to finish Evidence-First M0-M3 first, prove the execute -> review -> done authority/evidence slice, then pause before M4 and run the aggressive generalized-pipeline migration tranche. After that migration, resume/recreate the later Evidence-First work on top of the generalized substrate instead of baking more Megaplan-specific behavior into the old package shape.

Removed from automatic continuation, but still important:

- M4 review evidence service: generalize review-time evidence across all review paths and migrate review payloads toward evidence refs.
- M5 objective gates: machine-verifiable criteria backed by engine-owned checks and command evidence, robustness-gated from skip/warn/enforce.
- M6 provenance and workspace assertions: artifact provenance, freshness helpers, target HEAD/dirty-set/checked-SHA assertions at authority transitions.
- M7 transition validator routing: TransitionWriter over authority-increasing routes including reset/reconcile/config reroute, SHA-pinning, override waivers, routing_resolution_decision, CAS/lease stale-decision rejection.
- M8 capability dispatch gate: per-dispatch capability evidence, gate actual model against adjudicated tier, auth-proven availability, batch-level task evidence.
- M9 atomic reset reconcile: atomic reset/reconcile as recovery operations through TransitionWriter, fenced under locks, archive-not-delete, refuse changed head/worktree.
- M10 rollout enforcement: shadow -> warn -> enforce for all authority increases, including unattended-context fallback that records/fails instead of hanging.
- M11 post-merge rebaseline: rebuild frozen driver engine from merged result and rerun motivating failure scenarios as regression proof.

Important brief details to preserve when this is replanned:

- M4's review service must ground bulk-change verdicts in live file state, not serialized deviation claims, so global mechanical failures route to real owners.
- M5 should support author-declared objective checks, not only engine-inferred checks, so mechanical/cross-cutting milestones can be deterministic by construction.
- M6 includes the worker sweep ownership manifest: commit only phase-created/modified files, exclude `.megaplan/`, respect `.gitignore`, and never adopt ambient junk.
- M7 includes GitHub merge verification: after merge, verify the merge commit contains the branch tip and surface mismatches loudly.
- M9 includes recoverable merge failure handling: failed PR merge parks the milestone in a recoverable blocked state and retries without worktree-unsafe `--delete-branch` when needed.
- M10's unattended fallback is mandatory: blocked gates with no human must time out into warn-mode auto-waiver or enforce-mode diagnostics, never hang.
- M11 should stay focused on the four motivating regressions: silent model degrade, engine/target contamination, phantom dependency, and frozen config.

The intended follow-up sequence is:

1. Complete M0-M3 in the shortened Evidence-First chain.
2. Run the aggressive generalized-pipeline migration: boundary lock, RunOutcome/control extraction, StepContract authority, executor convergence, supervisor extraction, oracle-gated strangler, second proof pipeline, Megaplan as flagship pipeline.
3. Reintroduce M4-M11 as a new chain/epic slice adapted to the generalized pipeline substrate.

Source briefs remain under `.megaplan/briefs/evidence-first-pipeline-semantics/`; this ticket exists so the removed milestones are not lost and can be folded into the post-generalization epic.
