# Megaplan Semantics Carrier Table — M1 Launch Gate

**Milestone:** M1 — Megaplan Compositional Migration
**Status:** Launch-gate artifact (pre-implementation classification)
**Date:** 2026-07-03

---

## 1. Purpose

This document is the **M1 semantics carrier table**. It covers all 11 Megaplan
handler refs defined in `arnold_pipelines/megaplan/workflows/components.py`,
classifying each as either a **retained pure phase body** (computes outputs
without owning routing) or a **report-semantic owner** (handler body owns or
participates in routing, loop-exit, fanout, retry, suspension, override dispatch,
or implicit transition decisions).

This table is the launch-gate authority for the SD3 doctrine: *"Handler routing
ownership must be split into pure signal outputs plus explicit workflow
decisions."* Any handler classified as a report-semantic owner below carries
routing semantics that must be migrated into visible workflow structure or
declared policy before the M1 composition milestone can claim source-ownership
conformance.

Tests in `tests/arnold_pipelines/megaplan/test_semantics_carrier.py`
mechanically enforce the classifications in this table.

---

## 2. Handler Classification Table

Each handler ref is identified by its canonical `module:function` qualifier
as used in `StepComponent.metadata.handler_ref` entries in
`arnold_pipelines/megaplan/workflows/components.py`.

### 2.1 Report-Semantic Owners

These handlers own routing, transition, or closed-loop decisions. The routing
semantics they carry must ultimately live in visible workflow structure or
declared policy, not buried inside handler bodies.

| # | Handler Ref | Module | Routing Ownership | Notes |
|---|------------|--------|-------------------|-------|
| 1 | `arnold_pipelines.megaplan.handlers:handle_prep` | `handlers/plan.py` | **Yes** — `_apply_prep_clarify_gate` branches between `STATE_AWAITING_HUMAN` (human clarification needed) and `STATE_PREPPED` (proceed to plan). Owns the prep→plan vs prep→await-human routing decision. | The prep research payload is a pure output, but the clarify-gate branch embeds routing inside the handler body. |
| 2 | `arnold_pipelines.megaplan.handlers:handle_critique` | `handlers/critique.py` | **Yes** — Owns tiebreaker routing (reject-on-disabled, reject-on-budget, reject-on-blocklist, reject-on-no-signal, reject-on-missing-fields), gate outcome synthesis with branching to `STATE_GATED` / `STATE_CRITIQUED` / `STATE_TIEBREAKER_PENDING`. | The critique payload is a pure output, but the tiebreaker routing and gate-outcome synthesis embed routing decisions in the handler body. |
| 3 | `arnold_pipelines.megaplan.handlers:handle_gate` | `handlers/gate.py` | **Yes** — `_apply_gate_outcome` determines proceed / iterate / tiebreaker / escalate / abort / suspend / force_proceed / blocked_preflight. `_next_progress_step` synthesizes the next step. Owns the full gate routing decision tree. | Gate signals artifact is a pure output, but the routing decision logic in `_apply_gate_outcome` and `_next_progress_step` makes this a report-semantic owner. |
| 4 | `arnold_pipelines.megaplan.handlers:handle_revise` | `handlers/critique.py` | **Yes** — `_resolve_revise_transition` calls `workflow_transition(state, "revise")` and the result determines `state["current_state"]`. Owns the revise→next transition. | The revised plan payload is a pure output, but the transition logic calls `workflow_transition` inside the handler. |
| 5 | `arnold_pipelines.megaplan.handlers:handle_tiebreaker_decide` | `handlers/tiebreaker.py` (via `_tiebreaker_impl.py`) | **Yes** — Owns pick / escalate / replan routing. Calls `workflow_transition` and directly sets `state["current_state"]` for escalate and replan paths. | The tiebreaker decision record is a pure output, but the handler body owns the transition to critique, finalize, or override based on the decision action. |
| 6 | `arnold_pipelines.megaplan.handlers:handle_finalize` | `handlers/finalize.py` | **Yes** (conditional) — `_route_finalize_baseline_selection_failure_to_revise` synthesizes gate feedback recommending ITERATE and routes back to revise when baseline test selection fails. Also assigns `state["current_state"]` to `STATE_FINALIZED` on the happy path. | The happy path is pure computation, but the baseline-selection failure path embeds a routing decision inside the handler. |
| 7 | `arnold_pipelines.megaplan.handlers:handle_execute` | `handlers/execute.py` | **Yes** — Assigns `state["current_state"]` to `next_state` (variable from execute result) which can be `STATE_EXECUTED`, `STATE_BLOCKED`, `STATE_FAILED`, or `STATE_DONE`. Owns the execute outcome routing. | The execute payload is a pure output, but the outcome-to-state mapping embeds routing in the handler body. |
| 8 | `arnold_pipelines.megaplan.handlers:handle_review` | `handlers/review.py` | **Yes** — `_resolve_review_outcome` determines pass → done vs rework → back to execute, caps rework cycles, and force-proceeds on exhaustion. Owns the review routing decision tree. | The review verdict is a pure output, but routing (next_state, next_step selection) and rework-cycle capping are embedded in the handler body via `_resolve_review_outcome`. |
| 9 | `arnold_pipelines.megaplan.handlers:handle_override` | `handlers/override.py` | **Yes** — Owns abort (`_override_abort`), force_proceed (`_override_force_proceed`), replan (`_override_replan`), set-robustness (`_override_set_robustness`), and add-note (`_override_add_note`) routing decisions. Calls `workflow_transition` and directly mutates state to control transitions. | Override is the escalation dispatch point; every branch determines a distinct next workflow step. |

### 2.2 Retained Pure Phase Bodies

These handlers compute outputs (payloads, artifacts, reports) without owning
routing, loop-exit, fanout, retry, suspension, override dispatch, or implicit
transition decisions beyond a mechanical single-state advancement. They are
**retained** in the compositional migration: their bodies remain as subworkflow
contents, but they never decide what happens next.

| # | Handler Ref | Module | Pure Outputs | Notes |
|---|------------|--------|-------------|-------|
| 10 | `arnold_pipelines.megaplan.handlers:handle_plan` | `handlers/plan.py` | Plan payload, plan version artifacts | Pure computation. Assigns `state["current_state"] = STATE_PLANNED` (mechanical constant, not a branching decision). No routing calls. |
| 11 | `arnold_pipelines.megaplan.handlers:handle_tiebreaker_run` | `handlers/tiebreaker.py` (via `_tiebreaker_impl.py`) | Tiebreaker researcher/challenger outputs, tiebreaker analysis | Pure computation. Calls `workflow_transition(state, "tiebreaker-run")` which is a single deterministic step (run→decide), not a branched routing decision. |

---

## 3. Purity Inventory

### 3.1 What "Pure Phase Body" Means

A handler is a **pure phase body** if and only if:

1. **No routing:** The handler does not decide which step comes next. It may
   produce outputs that influence a routing decision, but the decision itself
   is owned by workflow structure or declared policy.
2. **No loop-exit:** The handler does not break out of or terminate a loop.
3. **No fanout:** The handler does not spawn or orchestrate parallel work.
4. **No retry:** The handler does not implement retry logic that changes the
   workflow path.
5. **No suspension:** The handler does not suspend the workflow or await human
   intervention.
6. **No override dispatch:** The handler does not dispatch to escalation or
   override paths.
7. **No implicit transitions:** The handler does not set `next_step`,
   `current_state`, or equivalent transition fields except through a mechanical
   one-step advance (e.g., run → decide with a single fixed successor).

### 3.2 Purity Counts

| Classification | Count | Handlers |
|---------------|-------|----------|
| Report-semantic owners | 9 | prep, critique, gate, revise, tiebreaker_decide, finalize, execute, review, override |
| Pure phase bodies | 2 | plan, tiebreaker_run |
| **Total** | **11** | |

### 3.3 What the Migration Requires

For the M1 composition milestone to claim source-ownership conformance:

- **Report-semantic owners** (prep, critique, gate, revise, tiebreaker_decide,
  finalize, execute, review, override — 9 handlers) must have their routing
  semantics represented in visible workflow structure (branches, loops,
  suspension points, escalation edges) or declared policy (control transitions,
  suspension routes, rework-cycle caps). The handler bodies may remain as
  subworkflow contents, but the routing decisions must be visible without
  reading handler bodies.

- **Pure phase bodies** (plan, tiebreaker_run — 2 handlers) are retained.
  Their bodies remain as subworkflow contents. The migration wraps them as
  invoked subworkflows but does not need to decompose their internal
  computation.

---

## 4. No-Hidden-Routing Claims

The following claims are mechanically enforceable and are verified by
`tests/arnold_pipelines/megaplan/test_semantics_carrier.py`:

### 4.1 Pure-Handler Invariants

For every handler classified as a **pure phase body** (§2.2), the following
must hold (tested by AST scan of the handler function body):

| # | Invariant | Enforcement |
|---|-----------|-------------|
| P1 | The handler function body does not contain calls to routing functions (`workflow_transition`, `workflow_next`, `_next_progress_step`, `_apply_gate_outcome`, `_resolve_revise_transition`, `_apply_prep_clarify_gate`, `_resolve_review_outcome`, `_route_*`, `_override_*`). | AST call-site scan for routing call markers |
| P2 | Exception: `handle_tiebreaker_run` may call `workflow_transition` for its single deterministic step (run→decide). | Allowed via `MECHANICAL_TRANSITION_HANDLERS` allowlist |

### 4.2 Report-Semantic-Owner Invariants

For every handler classified as a **report-semantic owner** (§2.1), the
following must hold:

| # | Invariant | Enforcement |
|---|-----------|-------------|
| R1 | Any handler whose function body contains routing call markers must be classified as a report-semantic owner. | AST call-site scan cross-referenced against `REPORT_SEMANTIC_OWNERS` |
| R2 | The classification is reviewed manually for correctness: a handler that contains branching routing logic but delegates it to helpers must still be listed here. The test cannot detect routing hidden in called helpers, so manual review of the classification table is the authoritative check. | Manual review of §2.1 table entries |

### 4.3 Handler Ref Completeness

| # | Invariant | Enforcement |
|---|-----------|-------------|
| C1 | Every `handler_ref` string in `ALL_STEP_COMPONENTS` from `arnold_pipelines.megaplan.workflows.components` must appear in this table. | Import-time scan of `ALL_STEP_COMPONENTS` |
| C2 | Every handler in this table must have a matching `handler_ref` in `ALL_STEP_COMPONENTS`. | Cross-reference validation |
| C3 | No handler_ref in `ALL_STEP_COMPONENTS` may be `None` or empty (HALT and SUSPEND are terminal steps with no handler and are excluded from the handler count). | Import-time validation |

---

## 5. Handler Ref Index

Complete index of all 11 handler refs with file locations:

| # | Handler Ref | File | Line | Classification |
|---|------------|------|------|---------------|
| 1 | `HANDLER_MODULE:handle_prep` | `handlers/plan.py` | 209 | Report-semantic owner |
| 2 | `HANDLER_MODULE:handle_plan` | `handlers/plan.py` | 140 | Pure phase body |
| 3 | `HANDLER_MODULE:handle_critique` | `handlers/critique.py` | 279 | Report-semantic owner |
| 4 | `HANDLER_MODULE:handle_gate` | `handlers/gate.py` | 791 | Report-semantic owner |
| 5 | `HANDLER_MODULE:handle_revise` | `handlers/critique.py` | 1055 | Report-semantic owner |
| 6 | `HANDLER_MODULE:handle_tiebreaker_run` | `handlers/tiebreaker.py` (→ `_tiebreaker_impl.py`) | 37 | Pure phase body |
| 7 | `HANDLER_MODULE:handle_tiebreaker_decide` | `handlers/tiebreaker.py` (→ `_tiebreaker_impl.py`) | 76 | Report-semantic owner |
| 8 | `HANDLER_MODULE:handle_finalize` | `handlers/finalize.py` | 1677 | Report-semantic owner |
| 9 | `HANDLER_MODULE:handle_execute` | `handlers/execute.py` | 134 | Report-semantic owner |
| 10 | `HANDLER_MODULE:handle_review` | `handlers/review.py` | ~900 | Report-semantic owner |
| 11 | `HANDLER_MODULE:handle_override` | `handlers/override.py` | ~1837 | Report-semantic owner |

Where `HANDLER_MODULE = "arnold_pipelines.megaplan.handlers"` (defined in
`arnold_pipelines/megaplan/workflows/components.py` line 19).

---

## 6. Relationship to Other Artifacts

| Artifact | Relationship |
|----------|-------------|
| `docs/arnold/megaplan-composition-handoff.md` | This table is the handler classification referenced by the handoff's source-authority doctrine (§2.1). |
| `docs/arnold/megaplan-source-path-reconciliation.md` | Live path inventory — this table's handler refs correspond to StepComponent entries in `workflows/components.py` (entry W3). |
| `docs/arnold/native-composition-contract.md` | M0 bridge contract — this table enforces the SD3 doctrine. |
| `arnold_pipelines/megaplan/workflows/components.py` | Source of truth for `ALL_STEP_COMPONENTS` handler_ref entries. |
| `tests/arnold_pipelines/megaplan/test_semantics_carrier.py` | Mechanical enforcement tests for this table. |

---

## 7. Classification Methodology

Each handler was classified by:

1. **AST inspection** of the handler function body for routing markers:
   - `workflow_transition(` calls
   - `workflow_next(` calls
   - `_next_progress_step(` calls
   - `state["current_state"]` direct assignments
   - `_route_*` function calls
   - `_resolve_review_outcome(` calls

2. **Semantic analysis** of any routing marker found:
   - Is it a mechanical one-step advance (run → decide) or a branched decision?
   - Does the handler choose between multiple distinct next steps?
   - Does the handler set `next_step` to a value that depends on handler-internal
     logic rather than a fixed successor?

3. **Cross-reference** with the SD3 doctrine: if the routing decision would need
   to be visible in workflow structure to satisfy source-authority requirements,
   the handler is a report-semantic owner.

---

## 8. Gate Marker

**M1 semantics carrier gate label:** SEMANTICS-CARRIER AUTHORITY.

This document is the pre-implementation handler classification required by the
M1 launch gate (T3). No Megaplan workflow edit shall land before the handler
purity inventory is acknowledged and mechanically enforced by
`test_semantics_carrier.py`.
