# BoundaryTurn Load-Bearing Questions

## Context

This note records the load-bearing questions for
`docs/arnold/megaplan-boundary-turn-design.md`. Each question has a reviewed
answer based on an independent DeepSeek Pro subagent check, so implementation
planning should use this file rather than conversation memory.

## Questions And Reviewed Answers

### 1. What exactly is the scope of BoundaryTurn?

**Question:** Does BoundaryTurn govern only model-output capture and plan-dir
artifact promotion, or does it also promise atomicity for external workspace
mutations?

**Answer:** BoundaryTurn governs model-output capture and plan-dir canonical
promotion. It must not promise rollback for target-repository edits, test runs,
provider calls, subprocesses, or other external effects. Execute must record
external side effects with evidence and resumable checkpoints.

**DeepSeek check:** Sound, but the doc must say why rollback is not the goal.
The safe invariant is that BoundaryTurn prevents phantom canonical claims and
state advancement without evidence; it does not undo real workspace mutation.

### 2. How should plan and revise fit?

**Question:** Should plan and revise become Markdown draft boundaries, or must
they remain structured payload boundaries first?

**Answer:** They must remain structured payload boundaries first. Current
plan/revise outputs contain Markdown plus metadata, and promotion writes both
`plan_vN.md` and `plan_vN.meta.json`. Markdown-only drafts are a later option
only if metadata parity is proven.

**DeepSeek check:** This is load-bearing. The metadata at risk includes
questions, assumptions, success criteria, imported decision criteria, changed
surfaces, test blast radius, plan-version deltas, note-consumption receipts,
cache-hit guards, carried blast radius, flag updates, and validation summaries.

### 3. What happens to worker recovery paths?

**Question:** Can strict expected-path capture replace Hermes/model-seam
recovery immediately?

**Answer:** No. Existing phases should start under a `legacy_recovery` policy:
expected draft path wins, but known worker/model-seam fallbacks remain available
until tests prove a stricter policy is safe. BoundaryTurn needs explicit
fallback policies: `strict_file_fill`, `legacy_recovery`, `inline_when_missing`,
and `inline_only`.

**DeepSeek check:** The recovery cascade must run before boundary
classification under `legacy_recovery`. Hermes tool-markup extraction,
empty-response retry, execute/gate payload reconstruction, model-seam recovery,
phase normalizers, compatibility projection, and current `promote_scratch`
semantics are all load-bearing. Missing and unmodified drafts must remain
distinct diagnostics.

### 4. Who owns routing and state transitions?

**Question:** Can BoundaryTurn reduce next routing to a generic string or state
delta?

**Answer:** No. BoundaryTurn may return a validated workflow transition result,
but routing must remain policy-aware. Gate, review, and execute depend on
robustness settings, blocking classes, phase results, auto-driver behavior,
operator overrides, and recovery policies.

**DeepSeek check:** `workflow_transition` is a proposal, not a command. The
auto-driver re-derives routes from state, and transition policy can deny a
handler's intended move. BoundaryTurn must not absorb `_apply_gate_outcome`,
`_resolve_review_outcome`, or review-done evidence gating.

### 5. What must gate preserve?

**Question:** Can gate be reduced to `gate_output.json` -> `gate.json`?

**Answer:** No. BoundaryTurn can standardize gate capture/promotion, but gate
must preserve `gate_signals_vN.json`, `gate_carry.json`, `last_gate`, invalid
recommendation fallback, full-replacement reprompts, no-progress and
max-iteration termination, debt writes, flag events, tiebreaker validation, and
blocked/gated state distinctions.

**DeepSeek check:** Gate's reprompt loop is the risky edge. Intermediate
attempts should validate but not promote. `gate.json` and `gate_carry.json`
should be written once after the final attempt and any PROCEED-to-ITERATE
auto-downgrade.

### 6. What must finalize preserve?

**Question:** Is finalize just `finalize_output.json` -> `finalize.json`?

**Answer:** No. Finalize also produces `final.md`, `contract.json`,
`user_actions.md`, `finalize_snapshot.json`, capability claims, baseline/cache
behavior, scoped baseline selection, execution baseline, and sometimes
finalize-to-revise feedback artifacts. The model-fill draft must not own
harness-computed `validation`.

**DeepSeek check:** Finalize needs explicit multi-artifact mapping. Baseline
capture is a heavyweight harness side effect and must be recorded as such.
Baseline-selection failure is a route-to-revise path that writes gate/feedback
artifacts rather than a normal promotion.

### 7. What is the execute shape?

**Question:** Can execute use the same single-draft pattern as JSON phases?

**Answer:** No. Execute needs child turns for `execution_batch_N.json` and a
reducer turn for `execution.json`. It must preserve stable batch numbering,
resume mapping, target-repo mutations, approval/preflight, tier routing,
timeout recovery, quality gates, blocked-task reset, prerequisite blocks,
`finalize.json` updates, audit/trace outputs, and skipped-review stubs.

**DeepSeek check:** Confirmed. The important nuance is that child batch turns
can mutate the target repo and update `finalize.json` before aggregate
`execution.json` exists. Per-batch tier routing and active-step session keys
are child-turn harness behavior, not model output.

### 8. What is the review shape?

**Question:** Does BoundaryTurn cover review if it wraps `review_output.json`?

**Answer:** Only for the simple path. Review also has parallel/extreme review
merges, infrastructure-failure detection, empty-approved backfill, verdict
merge into finalize projection, maker stop, transition-policy denial artifacts,
rework caps, receipts, flag updates, and `final.md` rewrites.

**DeepSeek check:** The parallel/extreme path is not a single scratch file. It
needs child per-check turns and a reducer turn before the shared
`_finalize_review_outcome` flow. The reducer must preserve deterministic-check
evidence, task IDs, flag IDs, infra-failure signals, transition-policy denial,
and conditional `review.json` re-promotion.

### 9. How do tiebreakers and subpipelines fit?

**Question:** Is parent/child BoundaryTurn enough for tiebreaker?

**Answer:** Directionally yes, but only if child outputs are treated as
evidence and parent state advances solely through a reducer decision. The
tiebreaker path must preserve `gate.json` input, researcher/challenger outputs,
`tiebreaker_decisions.json`, audits, flag registry mutation, and
human/replan/revise state choices.

**DeepSeek check:** The design was under-specified. Child researcher/challenger
runs need real draft/capture/validate/promote boundaries, not direct canonical
writes. The reducer must receive `gate.json` as an evidence ref, validate child
artifacts, checkpoint flag-registry mutation, and model versioned runs via
iteration metadata.

### 10. Is this a recipe other pipeline authors can follow?

**Question:** Does BoundaryTurn standardize enough to be reusable without
flattening stage semantics?

**Answer:** Yes if the recipe standardizes boundary mechanics, not stage
meaning. Authors should define a spec, build drafts, prompt expected paths,
capture, validate, semantically check, promote, emit state/history/receipts,
and test wrong-path, invalid, unmodified, and resume behavior.

**DeepSeek check:** As originally written, no: it was too Megaplan-specific to
be an Arnold-wide recipe. The design now needs a generalization boundary:
generic `BoundarySpec`/validator/promoter protocols, no dependency on
Megaplan's template registry, canonical targets declared by the spec, runtime
event/journal mapping, and at least one non-Megaplan example.

## Subagent Review Synthesis

All ten DeepSeek subagents completed. The strongest conclusion is that
BoundaryTurn is robust only if it is a promotion-time abstraction, not a
replacement for worker parsing, phase validators, route policy, or recovery
logic.

The implementation plan should therefore start conservative:

1. Wrap existing JSON scratch behavior with `legacy_recovery`.
2. Prove byte-for-byte or behavior-for-behavior parity for each migrated phase.
3. Tighten individual phases only after provider-path tests show strict capture
   is safe.
4. Treat execute, parallel review, and tiebreaker as child-turn/reducer
   structures, not as single-draft phases.
5. Keep Megaplan-specific policy in handlers and transition policy while
   making the draft/capture/validate/promote recipe reusable.

## Cross-Cutting Acceptance Tests

- Direct canonical writes do not count as valid model output.
- Missing or unmodified drafts fall back only under an explicit policy.
- Modified invalid drafts fail under strict/file-fill policy.
- Worker/model-seam recovery runs before `legacy_recovery` boundary
  classification.
- Unknown JSON keys are stripped or rejected according to phase policy.
- Plan/revise preserve metadata and `plan_vN.meta.json`.
- Execute records external side effects instead of pretending they are atomic.
- Gate reprompts retain complete-replacement semantics and promote canonical
  gate artifacts once.
- Parallel review uses child turns plus reducer behavior.
- Tiebreaker reducer validates child evidence and checkpointed flag mutation.
- Promotion never advances Megaplan state without the required canonical
  artifacts and recorded side effects.
- A non-Megaplan pipeline can use BoundaryTurn without importing Megaplan
  registries or artifact names.
