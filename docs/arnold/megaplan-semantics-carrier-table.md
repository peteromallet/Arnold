# Megaplan Semantics Carrier Table

**Milestone:** M1 — Megaplan Compositional Workflow Migration  
**Status:** Phase 1 launch-gate artifact — handler inventory and carrier classification  
**Date:** 2026-07-02  
**Doctrine Reference:** `docs/arnold/megaplan-composition-doctrine-proof.md`  
**Path Reference:** `docs/arnold/megaplan-source-path-reconciliation.md`  

---

## 1. Purpose

This document is the **semantics carrier table** for M1. It inventories every
exported Megaplan handler, maps each handler to the report-owned semantics it
currently carries, and classifies every semantic into exactly one carrier
category:

| Carrier | Meaning |
|---------|---------|
| `canonical_source` | Semantics visible in compositional Python source or declared policy in the live `arnold_pipelines/megaplan/` package. |
| `declared_policy` | Semantics owned by explicit policy declarations (stable IDs, decision vocabulary, schemas, merge rules), authored in source. |
| `audited_pure_phase_body` | Semantics that naturally belong in a handler body because the handler performs pure computation without owning routing, state transitions, fanout, or override dispatch. |
| `pending` | Semantics currently hidden inside handler bodies that must be decomposed into visible compositional structure before they can claim `canonical_source` or `declared_policy` status. A `pending` classification is a **handler-ref false-pass guard** — it prevents any test or alignment row from claiming implementation when the semantic carrier is still an opaque handler. |

**MUST:** No alignment-plan row may be marked `implemented` if its semantic
carrier is `pending`. Pending rows are bridge debt, not migration completion.

**MUST:** The carrier classification in this table is binding for all M1
conformance claims. Any implementation that asserts a semantic is source-owned
when this table classifies it as `pending` is non-conformant per
`megaplan-composition-doctrine-proof.md` §5.3.

---

## 2. Exported Handler Inventory

The live handler export surface is defined in
`arnold_pipelines/megaplan/handlers/__init__.py` (lines 75–90).

| # | Handler | Source File | Lines | Signature |
|---|---------|-------------|-------|-----------|
| 1 | `handle_init` | `handlers/init.py` | 630 | `(root: Path, args: Namespace) -> StepResponse` |
| 2 | `handle_plan` | `handlers/plan.py` | 325 | `(root: Path, args: Namespace) -> StepResponse` |
| 3 | `handle_prep` | `handlers/plan.py` | 325 | `(root: Path, args: Namespace) -> StepResponse` |
| 4 | `handle_critique` | `handlers/critique.py` | 1295 | `(root: Path, args: Namespace) -> StepResponse` |
| 5 | `handle_revise` | `handlers/critique.py` | 1295 | `(root: Path, args: Namespace) -> StepResponse` |
| 6 | `handle_gate` | `handlers/gate.py` | 1047 | `(root: Path, args: Namespace) -> StepResponse` |
| 7 | `handle_finalize` | `handlers/finalize.py` | 1747 | `(root: Path, args: Namespace) -> StepResponse` |
| 8 | `handle_execute` | `handlers/execute.py` | 369 | `(root: Path, args: Namespace) -> StepResponse` |
| 9 | `handle_review` | `handlers/review.py` | 1538 | `(root: Path, args: Namespace) -> StepResponse` |
| 10 | `handle_override` | `handlers/override.py` | 1852 | `(root: Path, args: Namespace) -> StepResponse` |
| 11 | `handle_audit_verifiability` | `handlers/verifiability.py` | 337 | `(root: Path, args: Namespace) -> StepResponse` |
| 12 | `handle_verify_human` | `handlers/verifiability.py` | 337 | `(root: Path, args: Namespace) -> StepResponse` |
| 13 | `handle_tiebreaker_run` | `handlers/_tiebreaker_impl.py` | ~120 | `(root: Path, args: Namespace) -> StepResponse` |
| 14 | `handle_tiebreaker_decide` | `handlers/_tiebreaker_impl.py` | ~120 | `(root: Path, args: Namespace) -> StepResponse` |

**Total: 14 exported handlers across 8 source modules.**

---

## 3. Handler Semantics Classification

### 3.1 handle_init

**Phase:** Initialization — creates runtime layout, seeds plan state, routes
deprecated `--mode` flags to pipeline names.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| Runtime layout creation | Handler body | `audited_pure_phase_body` | Pure filesystem setup; no routing, no state-machine transitions visible to composition. |
| Mode-to-pipeline routing | Handler body (`_PIPELINE_ROUTING`) | `declared_policy` | The mapping table (`doc→doc`, `metaplan→doc`, `creative→creative`, `joke→creative`) is explicit, stable, and could be declared as policy. Currently inlined but trivially extractable. |
| State initialization (`STATE_INITIALIZED`) | Handler body | `audited_pure_phase_body` | Single deterministic state seed; no branching. |
| Anchor document validation | Handler body → `anchors.validate_anchor_source` | `audited_pure_phase_body` | Pure validation with no routing decisions. |
| Deprecated mode deprecation warning | Handler body | `audited_pure_phase_body` | Informational side effect; no product semantics. |

**Overall classification:** `declared_policy` (mode routing is the only product
semantic, and it is already explicit). The rest is pure phase body.

**False-pass guard:** None — `handle_init` does not own hidden routing or state
transitions that would trigger a false pass if wrapped in a native node.

---

### 3.2 handle_plan

**Phase:** Planning — invokes planner worker, writes plan artifacts, merges
imported decision criteria.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| Planner worker invocation | Handler body → `_run_worker` | `pending` | Worker dispatch is handler-owned; composition should declare the plan step with explicit input/output contracts. |
| Plan artifact writing | Handler body → `_write_plan_version`, `_write_json_artifact` | `audited_pure_phase_body` | Pure artifact persistence; no routing decisions. |
| Imported decision criteria merge | Handler body → `_merge_imported_decision_criteria` | `pending` | Criteria merge affects downstream gate/critique semantics; should be declared at the workflow boundary. |
| Next-step transition | Handler body → `_finish_step` | `pending` | Transition to `STATE_PLANNED` is handler-owned; should be a visible workflow transition. |

**Mapped traceability rows:** `plan-artifact-version-metadata`

**Overall classification:** `pending` — The planner invocation, criteria merge,
and state transition are handler-owned and must be decomposed before claiming
source conformance.

**False-pass guard:** A test that passes because `handle_plan` emits artifacts
without verifying that input/output contracts and the planner invocation are
visible at the composition boundary is a false pass.

---

### 3.3 handle_prep

**Phase:** Preparation — runs prep worker, applies clarification gate,
builds verifiability flags.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| Prep worker invocation | Handler body → `_run_worker` | `pending` | Worker dispatch is handler-owned. |
| Clarification gate (`_apply_prep_clarify_gate`) | Handler body — mutates `state['clarification']`, returns `STATE_AWAITING_HUMAN` | `pending` | The branch decision (suspend vs proceed) is handler-owned; should be a visible workflow branch. |
| Verifiability flag building (`_build_verifiability_flags`) | Handler body | `pending` | Flag construction affects downstream gate behavior; should be declared policy or visible composition. |
| Next-step transition | Handler body → `_finish_step` | `pending` | Transition to `STATE_PREPPED` is handler-owned. |

**Mapped traceability rows:** `prep-clarification-gate`, `human-decision-suspension`

**Overall classification:** `pending` — The clarification gate is the canonical
example of handler-owned routing that must become a visible suspension branch.
`_apply_prep_clarify_gate` mutates state and returns a routing decision from
inside the handler body.

**False-pass guard:** A test that passes because the handler sets a waiting
state while topology still shows a single prep node is a false pass (per
`megaplan-composition-doctrine-proof.md` §4.2).

---

### 3.4 handle_critique

**Phase:** Critique — runs parallel critique lenses, adaptive evaluator retry,
robustness skip, fallback behavior.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| Robustness skip (bare mode) | Handler body — `configured_robustness` check | `pending` | The skip decision is handler-owned; should be visible workflow policy or branch. |
| Adaptive evaluator retry loop | Handler body — retry logic in `_recover_evaluator_payload_from_raw` and retry helpers | `pending` | Retry is invisible to topology/policy inspection. |
| Parallel critique lens dispatch | Handler body → `run_parallel_critique` | `pending` | Fanout over selected checks is handler-owned; should be visible `parallel_map`. |
| Fan-in / reducer | Handler body — aggregating parallel results | `pending` | Reducer is handler-owned; should be visible composition. |
| Fallback to sequential critique | Handler body | `pending` | Fallback behavior is handler-owned. |
| Unverifiable check annotation | Handler body → `annotate_unverifiable_checks` | `audited_pure_phase_body` | Pure annotation; no routing. |
| Tiebreaker validation (`_validate_tiebreaker`) | Handler body | `pending` | Validation affects downstream routing. |
| Next-step transition | Handler body → `_finish_step` | `pending` | Transition to `STATE_CRITIQUED` / `STATE_GATED` is handler-owned. |

**Mapped traceability rows:** `critique-bare-skip`, `critique-evaluator-retry`,
`critique-parallel-lenses`, `dynamic-parallel-map`

**Overall classification:** `pending` — `handle_critique` is the most
handler-owned phase. It contains a retry loop, parallel dispatch, robustness
skip, and fallback that are all invisible to the composition compiler. Per
`megaplan-composition-doctrine-proof.md` §4.2, this is the primary
decomposition target.

**False-pass guard:** A single native node calling `handle_critique` is a
wrapper graph false pass. Native trace listing child calls is insufficient —
the source must show visible parallel map, retry policy, and robustness branch.

---

### 3.5 handle_revise

**Phase:** Revise — bounded critique/gate/revise loop iteration.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| Revise worker invocation | Handler body → `_run_worker` | `pending` | Worker dispatch is handler-owned. |
| Loop termination decision | Handler body — state inspection, flag resolution | `pending` | Loop exit conditions (cap, no-progress, severity termination) are handler-owned. |
| Typed outcome emission | Handler body — implicit via state transitions | `pending` | Outcomes (proceed, iterate, blocked, escalate) are not declared at the workflow level. |
| Next-step transition | Handler body → `_finish_step` | `pending` | Transition back to critique or forward to gate is handler-owned. |

**Mapped traceability rows:** `critique-gate-revise-loop`, `typed-loop-outcomes`

**Overall classification:** `pending` — The revise loop is partly expressed as
graph policy but termination decisions and typed outcomes are hidden in the
handler. Per `megaplan-composition-doctrine-proof.md` §4.2, the bounded loop
must be visible with declared outcome enum.

**False-pass guard:** A state field jumping back to critique without visible
typed outcomes is a false pass.

---

### 3.6 handle_gate

**Phase:** Gate — builds signals, runs gate checks, resolves flags, handles
reprompt, records debt, applies gate outcomes.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| Signal building (`_build_gate_signals_artifact`) | Handler body → `build_gate_signals` | `pending` | Signal construction is handler-owned but affects routing. |
| Gate checks (`run_gate_checks`) | Handler body | `pending` | Check execution and result interpretation are handler-owned. |
| Preflight / payload normalization | Handler body — malformed payload recovery | `pending` | Recovery logic is handler-owned; should be declared preflight policy. |
| Agent availability check | Handler body → `only_agent_availability_preflight_failed` | `pending` | Availability decision is handler-owned. |
| Flag resolution | Handler body — `_remaining_significant_flags`, `_resolve_revise_transition` | `pending` | Flag-based routing is handler-owned. |
| Reprompt routing | Handler body — `_build_gate_prompt_override` | `pending` | Reprompt decision is handler-owned. |
| Debt recording (`_record_gate_debt_entries`) | Handler body | `pending` | Debt recording is a product semantic; should be a declared effect. |
| High-complexity downgrade | Handler body | `pending` | Downgrade route is handler-owned. |
| Rubber-stamp fast path | Handler body → `is_rubber_stamp` | `pending` | Fast-path decision is handler-owned. |
| Gate carry / outcome application | Handler body → `_write_gate_carry`, `_apply_gate_outcome` | `pending` | Outcome application mutates state; should be visible. |
| Next-step transition | Handler body → `_finish_step`, `workflow_transition` | `pending` | Transition to revise/tiebreaker/finalize is handler-owned. |

**Mapped traceability rows:** `gate-preflight-normalization`,
`gate-signal-reprompt`, `gate-flag-debt-fallback`,
`critique-gate-revise-loop`

**Overall classification:** `pending` — `handle_gate` owns extensive routing:
preflight, reprompt, flag resolution, debt, downgrade, rubber-stamp, and
next-step transition. Per `megaplan-composition-doctrine-proof.md` §4.2, all
of these must be decomposed into visible gate decision vocabulary.

**False-pass guard:** Gate looking native while reprompt/downgrade lives in
handler is a false pass. Debt flag written without an explicit product route
is a false pass.

---

### 3.7 handle_finalize

**Phase:** Finalize — generates tasks, selects baseline tests, captures
uncommitted baseline, writes artifacts, applies calibration.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| Task generation | Handler body — `render_final_md`, task extraction | `pending` | Task generation logic is handler-owned. |
| Baseline test selection (`compute_test_blast_radius`, `resolve_baseline_test_selection`) | Handler body | `pending` | Test selection policy is handler-owned; should be declared policy. |
| Scoped baseline fallback | Handler body | `pending` | Fallback route when scoped baseline is missing is handler-owned. |
| Uncommitted baseline capture (`capture_uncommitted_baseline`) | Handler body | `audited_pure_phase_body` | Pure git/filesystem snapshot; no routing. |
| Calibration claim writing | Handler body → `write_capability_claim` | `audited_pure_phase_body` | Pure evidence recording. |
| Artifact writing | Handler body → `_write_finalize_artifacts` | `audited_pure_phase_body` | Pure artifact persistence. |
| Validation (`_validate_finalize_payload`) | Handler body | `audited_pure_phase_body` | Pure validation. |
| Verification task creation (`_ensure_verification_task`) | Handler body | `pending` | Verification task creation affects downstream routing. |
| Next-step transition | Handler body → `_finish_step` | `pending` | Transition to execute/review is handler-owned. |
| Failure/finalize_error routing | Handler body — swallowed into artifacts | `pending` | Failure routes are not visible in topology. |

**Mapped traceability rows:** `finalize-fallback-routes`,
`plan-artifact-version-metadata`, `golden-trace-regeneration`

**Overall classification:** `pending` — Task generation, baseline selection,
and fallback routing are handler-owned. Per
`megaplan-composition-doctrine-proof.md` §4.2, finalize failures must not be
swallowed into artifact flags; failure routes must be visible.

**False-pass guard:** Finalize errors swallowed into artifact flags without
visible topology routes is a false pass.

---

### 3.8 handle_execute

**Phase:** Execute — DAG batching, approval gates, task execution, rework
re-execution detection.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| DAG batching (`handle_execute_auto_loop`, `handle_execute_one_batch`) | Handler body → `execute/batch.py` | `pending` | Batching and dependency ordering are handler-owned; should be visible subworkflow or DAG primitive. |
| Approval gate routing | Handler body — `user_approved`, `confirm_destructive` checks | `pending` | Approval decisions are handler-owned; should be declared gates. |
| No-review fast path | Handler body — `_is_rework_reexecution` check | `pending` | No-review decision is handler-owned. |
| Deferred human verify routing | Handler body | `pending` | Human suspension routing is handler-owned. |
| Task execution dispatch | Handler body → `worker_module` | `pending` | Worker dispatch is handler-owned. |
| Partial failure / resume | Handler body — `BlockedTask`, `Deviation` handling | `pending` | Resume coordinates are handler-owned. |
| Model routing by task complexity | Handler body → `apply_profile_expansion`, `audit_step_payload` | `pending` | Model selection policy is handler-owned. |
| Phase preflight | Handler body → `preflight_mutating_phase` | `audited_pure_phase_body` | Pure environment setup. |
| Next-step transition | Handler body — `save_state_merge_meta`, `set_active_step` | `pending` | Transition to review/done is handler-owned. |

**Mapped traceability rows:** `execute-dependency-batches`,
`execute-approval-gates`, `model-routing-policy`, `path-addressed-checkpoints`

**Overall classification:** `pending` — `handle_execute` delegates to
`execute/batch.py` for DAG logic but the composition boundary is still a single
handler-backed stage. Per `megaplan-composition-doctrine-proof.md` §4.2,
execute must not remain one opaque handler.

**False-pass guard:** Execute remaining one node with richer internal logging
is a false pass. Approval working through side effects without visible topology
is a false pass.

---

### 3.9 handle_review

**Phase:** Review — parallel check dispatch, verdict merge, rework loop,
infrastructure retry, cap outcomes.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| Parallel review check dispatch | Handler body → `run_parallel_review`, `review/parallel.py` | `pending` | Fanout over checks is handler-owned; should be visible parallel map. |
| Reviewer verdict merge (`_merge_review_verdicts`) | Handler body | `pending` | Reducer is handler-owned. |
| Review outcome resolution (`_resolve_review_outcome`) | Handler body | `pending` | Outcome classification (approve/rework/block/force-proceed/escalate) is handler-owned. |
| Rework loop routing | Handler body — mutates `next_step` to execute | `pending` | Rework route is handler-owned state mutation. |
| Infrastructure retry | Handler body | `pending` | Retry logic is handler-owned. |
| Repeated failure cap | Handler body | `pending` | Cap threshold is handler-owned; no visible branch. |
| Blocked message building | Handler body → `_build_review_blocked_message` | `audited_pure_phase_body` | Pure message construction. |
| Prompt override building | Handler body → `_build_review_prompt_override` | `pending` | Prompt override affects worker behavior; should be declared policy. |
| Rework item synthesis (`_synthesize_review_rework_items`) | Handler body | `pending` | Rework item generation is handler-owned. |
| Done task evidence check | Handler body → `_check_done_task_evidence` | `audited_pure_phase_body` | Pure evidence verification. |
| Rubber-stamp detection | Handler body → `is_rubber_stamp` | `pending` | Fast-path decision is handler-owned. |
| Merge validation (`_validate_and_merge_batch`) | Handler body | `audited_pure_phase_body` | Pure merge/validation. |
| Transition policy writing | Handler body → `TransitionWriter` | `pending` | Transition decision is handler-owned. |
| Next-step transition | Handler body | `pending` | Transition to execute/done/blocked is handler-owned. |

**Mapped traceability rows:** `execute-review-rework-loop`,
`review-parallel-fanin`, `review-retry-cap-outcomes`

**Overall classification:** `pending` — `handle_review` has the most extensive
handler-owned routing of any single handler: parallel dispatch, verdict merge,
outcome resolution, rework loop, retry, and cap. Per
`megaplan-composition-doctrine-proof.md` §4.2, all must be decomposed.

**False-pass guard:** Review handler mutating `next_step` to execute (hiding
rework route) must fail conformance. Parallel checks running inside handler
with topology showing one review node is a false pass.

---

### 3.10 handle_override

**Phase:** Override — action route matrix: abort, replan, force-proceed,
add-note, resume-clarify, recover-blocked, set-robustness, set-profile,
set-model, set-vendor.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| Action route matrix | Handler body — `_override_abort`, `_override_force_proceed`, `_override_replan`, `_override_set_robustness`, `_override_add_note` | `pending` | Each action is a handler-owned branch with product semantics. |
| State mutation per action | Handler body — each `_override_*` mutates `state` | `pending` | State transitions are handler-owned. |
| Profile/model/vendor changes | Handler body → `_override_set_robustness` + profile helpers | `pending` | Policy changes are handler-owned. |
| Resume-clarify routing | Handler body | `pending` | Resume routing is handler-owned. |
| Recover-blocked routing | Handler body | `pending` | Recovery routing is handler-owned. |
| Control interface routing | Handler body → `control_interface_routing_on` | `pending` | Feature-flag-gated routing is handler-owned. |
| Premium vendor resolution | Handler body → `effective_premium_vendor`, `resolve_premium_placeholder_spec` | `pending` | Vendor routing is handler-owned; should be declared policy. |
| Next-step transition | Handler body — `workflow_next`, `infer_next_steps` | `pending` | Transition is handler-owned. |

**Mapped traceability rows:** `override-action-surface`,
`human-decision-suspension`, `model-routing-policy`

**Overall classification:** `pending` — `handle_override` is the canonical
example of handler-owned routing that must become declared decision vocabulary.
The full action surface (abort, replan, force-proceed, add-note,
resume-clarify, recover-blocked, set-robustness/profile/model/vendor) is
dispatched inside one handler body. Per
`megaplan-composition-doctrine-proof.md` §4.2, this is a primary decomposition
target.

**False-pass guard:** Only abort/replan being visible while other actions
mutate config/state through handler-internal branches is a false pass. No
generic Megaplan literal scan plus action-by-action route tests are required
to close this row.

---

### 3.11 handle_audit_verifiability

**Phase:** Audit — classifies success criteria against worker capabilities,
identifies human-deferred criteria.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| Criteria classification (`classify_criteria`) | Handler body → `orchestration/verifiability.py` | `audited_pure_phase_body` | Pure classification; no routing decisions. Output is informational. |
| Deferred-must identification | Handler body | `audited_pure_phase_body` | Pure set computation. |
| State transition (`STATE_DONE`) | Handler body | `audited_pure_phase_body` | Single deterministic transition. |

**Mapped traceability rows:** None directly — this is an audit/observability
handler, not a product-semantic owner.

**Overall classification:** `audited_pure_phase_body` — `handle_audit_verifiability`
performs pure classification with no routing, fanout, state-machine decisions,
or product semantics. It is the least problematic handler from a composition
standpoint.

**False-pass guard:** None — this handler does not own hidden routing.

---

### 3.12 handle_verify_human

**Phase:** Human verification — loads verification records, applies
latest-verdict semantics, marks criteria as verified.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| Verification record loading | Handler body → `get_human_verification_status` | `audited_pure_phase_body` | Pure data loading. |
| Latest-verdict semantics | Handler body | `audited_pure_phase_body` | Pure deterministic algorithm; no routing. |
| Verification status update | Handler body | `audited_pure_phase_body` | Pure state recording. |
| State transition (`STATE_DONE`) | Handler body | `audited_pure_phase_body` | Single deterministic transition. |

**Mapped traceability rows:** `human-decision-suspension` (indirectly — this
handler resolves the suspension, but the suspension decision itself is in
`handle_prep` and `handle_override`)

**Overall classification:** `audited_pure_phase_body` — `handle_verify_human`
performs pure verification with deterministic latest-verdict semantics. It
does not own routing, fanout, or product-level decisions. The suspension
semantics it resolves are owned by `handle_prep` and `handle_override`.

**False-pass guard:** None — this handler does not own hidden routing, but
tests must verify that the suspension coordinate it resolves was created by
a visible workflow branch, not a handler-internal state mutation.

---

### 3.13 handle_tiebreaker_run

**Phase:** Tiebreaker (research) — invokes researcher worker, collects
proposals.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| Researcher worker invocation | Handler body → `_run_worker` | `pending` | Worker dispatch is handler-owned. |
| Researcher prompt construction | Handler body → `_build_tiebreaker_reprompt` | `pending` | Prompt policy is handler-owned. |
| Proposal collection | Handler body | `pending` | Proposal aggregation is handler-owned. |

**Mapped traceability rows:** `tiebreaker-subworkflow`

**Overall classification:** `pending` — `handle_tiebreaker_run` and
`handle_tiebreaker_decide` together form a researcher/challenger subworkflow
that is currently split across two handler-backed stages. Per
`megaplan-composition-doctrine-proof.md` §4.2, tiebreaker must be a visible
subworkflow with researcher, challenger, decision, and parent promotion.

**False-pass guard:** One native node calling the old tiebreaker handler
(pair) is a false pass. Structural conformance must fail for single
handler-backed tiebreaker stages.

---

### 3.14 handle_tiebreaker_decide

**Phase:** Tiebreaker (decision) — invokes challenger/decider worker, selects
winning proposal, promotes to parent.

| Semantic | Current Carrier | Classification | Reason |
|----------|----------------|----------------|--------|
| Challenger worker invocation | Handler body → `_run_worker` | `pending` | Worker dispatch is handler-owned. |
| Decision / winner selection | Handler body | `pending` | Winner selection is handler-owned. |
| Escalation routing | Handler body | `pending` | Escalation to human is handler-owned. |
| Replan routing | Handler body | `pending` | Replan decision is handler-owned. |
| Parent promotion | Handler body | `pending` | Promotion logic is handler-owned. |
| Next-step transition | Handler body | `pending` | Transition to finalize/blocked/human is handler-owned. |

**Mapped traceability rows:** `tiebreaker-subworkflow`,
`human-decision-suspension`, `path-addressed-checkpoints`

**Overall classification:** `pending` — See §3.13. The run/decide pair must
become a single visible subworkflow with declared decision vocabulary.

**False-pass guard:** Same as §3.13.

---

## 4. Carrier Summary

| Handler | Classification | Decomposition Priority | Primary Traceability Rows |
|---------|---------------|----------------------|---------------------------|
| `handle_init` | `declared_policy` / `audited_pure_phase_body` | Low — mode routing already explicit | — |
| `handle_plan` | `pending` | Medium — planner invocation, criteria merge | `plan-artifact-version-metadata` |
| `handle_prep` | `pending` | **High** — clarification gate is canonical suspension | `prep-clarification-gate`, `human-decision-suspension` |
| `handle_critique` | `pending` | **Highest** — retry, parallel, skip, fallback | `critique-bare-skip`, `critique-evaluator-retry`, `critique-parallel-lenses`, `dynamic-parallel-map` |
| `handle_revise` | `pending` | High — loop termination, typed outcomes | `critique-gate-revise-loop`, `typed-loop-outcomes` |
| `handle_gate` | `pending` | **Highest** — preflight, reprompt, flag, debt, downgrade | `gate-preflight-normalization`, `gate-signal-reprompt`, `gate-flag-debt-fallback` |
| `handle_finalize` | `pending` | Medium — task gen, baseline selection, fallback routes | `finalize-fallback-routes`, `golden-trace-regeneration` |
| `handle_execute` | `pending` | **High** — DAG, approval, model routing, partial resume | `execute-dependency-batches`, `execute-approval-gates`, `model-routing-policy` |
| `handle_review` | `pending` | **Highest** — parallel, merge, rework, retry, cap | `execute-review-rework-loop`, `review-parallel-fanin`, `review-retry-cap-outcomes` |
| `handle_override` | `pending` | **Highest** — full action matrix, 10+ product routes | `override-action-surface`, `human-decision-suspension` |
| `handle_audit_verifiability` | `audited_pure_phase_body` | None — no decomposition needed | — |
| `handle_verify_human` | `audited_pure_phase_body` | None — no decomposition needed | — |
| `handle_tiebreaker_run` | `pending` | **High** — subworkflow split | `tiebreaker-subworkflow`, `path-addressed-checkpoints` |
| `handle_tiebreaker_decide` | `pending` | **High** — subworkflow split, decision vocabulary | `tiebreaker-subworkflow`, `human-decision-suspension` |

### 4.1 Classification Counts

| Classification | Count | Handlers |
|---------------|-------|----------|
| `canonical_source` | 0 | None — Phase 3 migration not yet executed |
| `declared_policy` | 1 | `handle_init` (mode routing) |
| `audited_pure_phase_body` | 2 | `handle_audit_verifiability`, `handle_verify_human` |
| `pending` | 11 | `handle_plan`, `handle_prep`, `handle_critique`, `handle_revise`, `handle_gate`, `handle_finalize`, `handle_execute`, `handle_review`, `handle_override`, `handle_tiebreaker_run`, `handle_tiebreaker_decide` |

### 4.2 Traceability Row Coverage

Every traceability matrix row is owned by at least one `pending` handler,
confirming that no row can claim `implemented` before Phase 3 decomposition.

| Row ID | Owning Handler(s) | Carrier Status |
|--------|-------------------|----------------|
| `prep-clarification-gate` | `handle_prep` | `pending` |
| `plan-artifact-version-metadata` | `handle_plan`, `handle_finalize` | `pending` |
| `critique-bare-skip` | `handle_critique` | `pending` |
| `critique-evaluator-retry` | `handle_critique` | `pending` |
| `critique-parallel-lenses` | `handle_critique` | `pending` |
| `critique-gate-revise-loop` | `handle_revise`, `handle_gate` | `pending` |
| `gate-preflight-normalization` | `handle_gate` | `pending` |
| `gate-signal-reprompt` | `handle_gate` | `pending` |
| `gate-flag-debt-fallback` | `handle_gate` | `pending` |
| `tiebreaker-subworkflow` | `handle_tiebreaker_run`, `handle_tiebreaker_decide` | `pending` |
| `human-decision-suspension` | `handle_prep`, `handle_override`, `handle_tiebreaker_decide` | `pending` |
| `finalize-fallback-routes` | `handle_finalize` | `pending` |
| `execute-dependency-batches` | `handle_execute` | `pending` |
| `execute-approval-gates` | `handle_execute` | `pending` |
| `execute-review-rework-loop` | `handle_review` | `pending` |
| `review-parallel-fanin` | `handle_review` | `pending` |
| `review-retry-cap-outcomes` | `handle_review` | `pending` |
| `override-action-surface` | `handle_override` | `pending` |
| `timeout-deadline-policy` | (distributed — runtime helpers, not a single handler) | `pending` |
| `model-routing-policy` | `handle_execute`, `handle_override` | `pending` |
| `runtime-list-iteration` | (compiler — not handler-owned) | `pending` (compiler) |
| `dynamic-parallel-map` | `handle_critique`, `handle_review`, `handle_execute` | `pending` |
| `typed-loop-outcomes` | `handle_revise` | `pending` |
| `autodrive-event-liveness` | (distributed — control transitions, not a single handler) | `pending` |
| `path-addressed-checkpoints` | `handle_execute`, `handle_tiebreaker_run`, `handle_tiebreaker_decide` | `pending` |
| `shadow-topology` | (not handler-owned — planning artifact) | `pending` |
| `handler-purity-audit` | (meta — this table is the inventory) | `pending` |
| `golden-trace-regeneration` | `handle_finalize` | `pending` |
| `source-path-reconciliation` | (docs task — completed in T1) | `declared_policy` |
| `behavior-parity` | (cross-cutting — all handlers) | `pending` |
| `source-readability` | (cross-cutting — all handlers) | `pending` |

---

## 5. Handler-Ref False-Pass Guards

The following patterns appear across multiple handlers and constitute
**handler-ref false passes** if any test or alignment row claims them as
conformance evidence:

### 5.1 State Mutation Routing

Handlers that mutate `state['next_step']`, `state['current_step']`, or call
`workflow_transition()` / `workflow_next()` / `infer_next_steps()` are
performing **handler-owned routing**. Affected handlers:

- `handle_prep` — `_apply_prep_clarify_gate` mutates state for suspension
- `handle_gate` — `workflow_transition`, `_resolve_revise_transition`
- `handle_review` — mutates `next_step` to execute for rework
- `handle_override` — `workflow_next`, `infer_next_steps`
- `handle_tiebreaker_decide` — escalation/replan routing

### 5.2 Worker Dispatch

Handlers that call `_run_worker()` or `worker_module` to invoke AI workers
are performing **handler-owned dispatch**. Affected handlers:

- `handle_plan`, `handle_prep`, `handle_critique`, `handle_revise`,
  `handle_gate`, `handle_execute`, `handle_review`, `handle_tiebreaker_run`,
  `handle_tiebreaker_decide`

### 5.3 Parallel Dispatch

Handlers that call `run_parallel_critique()`, `run_parallel_review()`, or
equivalent fanout primitives are performing **handler-owned fanout**.
Affected handlers:

- `handle_critique` — `run_parallel_critique`
- `handle_review` — `run_parallel_review`

### 5.4 Loop / Retry

Handlers that contain retry loops or loop termination logic are performing
**handler-owned iteration**. Affected handlers:

- `handle_critique` — adaptive evaluator retry
- `handle_revise` — bounded critique/gate/revise loop
- `handle_review` — infrastructure retry, rework loop

### 5.5 Override Action Dispatch

Handlers that contain a matrix of action routes (`_override_abort`,
`_override_force_proceed`, etc.) are performing **handler-owned product
decision routing**. Affected handlers:

- `handle_override` — 10+ action routes in one handler

---

## 6. Phase-Dependent Carrier Status

### 6.1 Phase 1 (Current — This Document)

All 11 `pending` handlers remain `pending`. No carrier reclassification occurs
in Phase 1. This table is a **launch-gate inventory**, not a migration claim.

### 6.2 Phase 2

Neutral native child-workflow compiler/runtime support is additive. No handler
semantics change. Carrier classifications remain unchanged.

### 6.3 Phase 3 (Blocked — Gated on M7)

When the M7 prerequisite is satisfied or waived, Phase 3 decomposes each
`pending` handler. After decomposition:

- `handle_critique` → `canonical_source` (visible parallel map + retry policy + robustness branch)
- `handle_gate` → `canonical_source` (visible decision vocabulary + preflight policy)
- `handle_review` → `canonical_source` (visible parallel map + rework loop + cap outcomes)
- `handle_override` → `canonical_source` (visible action route matrix)
- `handle_execute` → `canonical_source` (visible DAG subworkflow + approval gates)
- `handle_tiebreaker_run` + `handle_tiebreaker_decide` → `canonical_source` (visible subworkflow)
- `handle_prep` → `canonical_source` (visible suspension branch)
- `handle_revise` → `canonical_source` (visible bounded loop with typed outcomes)
- `handle_finalize` → `canonical_source` (visible task gen + baseline policy + failure routes)
- `handle_plan` → `canonical_source` (visible planner invocation + declared artifact contracts)

After decomposition, retained handler bodies (if any) would be reclassified as
`audited_pure_phase_body` — pure computation with no routing, state transitions,
fanout, or product decisions.

---

## 7. Acceptance

This carrier table conforms to the requirements of
`megaplan-composition-doctrine-proof.md` and the H6 Semantics Carrier Review
wave in `megaplan-native-representation-alignment-plan.md`:

1. ✅ Every exported handler (14) is inventoried with source file and line counts.
2. ✅ Every report-owned semantic is classified as `canonical_source`,
   `declared_policy`, `audited_pure_phase_body`, or `pending`.
3. ✅ No handler-ref false pass: zero handlers are classified as
   `canonical_source` before Phase 3 decomposition.
4. ✅ Every traceability matrix row is mapped to its owning handler(s).
5. ✅ Handler-owned routing patterns (state mutation, worker dispatch, parallel
   dispatch, loop/retry, override action dispatch) are explicitly enumerated
   as false-pass guards.
6. ✅ Phase-dependent carrier status clearly gates all `pending` → `canonical_source`
   transitions on Phase 3 + M7 completion.
7. ✅ Two handlers (`handle_audit_verifiability`, `handle_verify_human`) are
   audited and confirmed as pure phase bodies with no hidden routing.
8. ✅ One handler (`handle_init`) is confirmed as having explicit, extractable
   `declared_policy` for mode routing, with the remainder as pure phase body.
