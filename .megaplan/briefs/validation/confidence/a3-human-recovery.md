# A3 — Human-Recovery Surface vs. m3 Routing Collapse

**Verdict: HIGH coupling. m3's "collapse the 3 next-step encodings onto graph
edges" plan will break the recovery surface IF `workflow_next` is deleted. It is
SAFE if `workflow_next` is retained as a thin, state-derived *projection* over
the edges. Recommended plan change: keep `workflow_next` as the projection layer;
do not let edges become the only next-step source.**

Files read: `megaplan/handlers/override.py`, `megaplan/handlers/verifiability.py`
(`handle_verify_human`), `megaplan/user_actions.py`,
`megaplan/_core/workflow.py` (`workflow_next`, `resume_plan`,
`_RESUME_ACTIVE_STATES`), `megaplan/_core/workflow_data.py` (`WORKFLOW`,
`_ROBUSTNESS_OVERRIDES`), `megaplan/_pipeline/planning.py` (the compiled graph),
`megaplan/_pipeline/executor.py`/`runtime.py`/`builder.py` (no robustness
handling), `megaplan/observability/doctor.py` + `introspect.py` (recoverable_via),
`megaplan/cli/status_view.py` (next_step).

---

## 1. Planning-vocabulary assumptions in the recovery surface

These commands are NOT routing-agnostic. They are written in the planning state
machine's private vocabulary:

### State-name vocabulary (string-literal coupling)
- **`override force-proceed`** hardcodes `STATE_EXECUTED → STATE_DONE` (review
  bypass), `STATE_CRITIQUED`/`STATE_BLOCKED` as the only legal entry states, and
  `STATE_GATED` as the forced exit. It then *manufactures a gate artifact*
  (`build_gate_artifact` with `recommendation="PROCEED"`), writes `gate.json`,
  clears `state.last_gate`, and pushes a literal `next_step="finalize"`. This is
  pure planning-pipeline knowledge baked into a recovery command.
- **`override replan`** allows `{GATED, FINALIZED, CRITIQUED, FAILED}` → forces
  `STATE_PLANNED`, clears `last_gate`. Re-enters the *planning loop* specifically.
- **`override resume-clarify`** requires `STATE_AWAITING_HUMAN`,
  `clarification.source == "prep"`, → `STATE_PREPPED`. Hardwired to the prep phase.
- **`override recover-blocked`** owns `_BLOCKED_RECOVERY_STATES`, a private
  **phase→recovered-state map** (`prep/plan→initialized, critique→planned,
  gate/revise→critiqued, finalize→gated, execute→finalized, review→executed,
  feedback→reviewed`). This is a *second, hand-maintained copy* of the workflow's
  reverse edges. `resume_plan` carries a near-identical `_RESUME_ACTIVE_STATES`
  map — a third copy.
- **`verify-human`** requires `STATE_AWAITING_HUMAN_VERIFY` → `STATE_DONE`; reads
  `success_criteria` from `plan_v1.meta.json` (planning artifact).

### Gate/verdict-vocabulary coupling
- `force-proceed` reads `last_gate.recommendation == "ESCALATE"` (strict-notes),
  and depends on `_last_gate_is_agent_availability_preflight_block` — the exact
  `gate_proceed_agent_availability_blocked` predicate.
- `workflow_next` itself encodes the verdict vocabulary as edge *conditions*:
  `gate_unset / gate_iterate / gate_escalate / gate_tiebreaker /
  gate_proceed / gate_proceed_blocked / gate_proceed_agent_availability_blocked`.

### Robustness/feature-flag coupling
- `workflow_next` is robustness-conditional: it merges `_ROBUSTNESS_OVERRIDES`
  (bare/light/full) and `with_prep`/`with_feedback` *at call time* from
  `state.config`. The set of valid next steps for `STATE_CRITIQUED` differs by
  robustness (light collapses `revise→GATED`; bare collapses `plan→finalize`).
- The `"step"` pseudo-target: for `_STEP_CONTEXT_STATES = {PLANNED, CRITIQUED,
  GATED, FINALIZED}`, `workflow_next` *appends a synthetic `"step"`* that exists
  in no graph edge at all. `workflow_includes_step` special-cases it
  (`if step == "step": return True`).

## 2. What BREAKS when the 3 encodings collapse to static edges

The compiled pipeline graph (`planning.py`) is a **single, full-fidelity,
robustness-blind** topology. The executor (`executor.py`/`runtime.py`/`builder.py`)
contains **zero** references to `robustness`, `with_prep`, or `with_feedback`.
So if recovery commands switch from `workflow_next(state)` to "read the edges off
the current stage," the following break concretely:

1. **Robustness projection is lost.** Static edges always say `CRITIQUED →
   {critique, gate, revise, tiebreaker, …}`. On a `light` plan, `revise` should
   land in `GATED` not `PLANNED`; on `bare`, `PLANNED → finalize` directly. Every
   `valid_next=infer_next_steps(state)` error hint (force-proceed line 263/269,
   replan 361, recover-blocked 438, resume-clarify 855/862, gate.py 154/157,
   step_edit 117, shared.py 476/531/571) would print **wrong recovery commands** —
   the maximally painful failure: telling a stuck operator to run a step the
   harness will reject.

2. **The `"step"` pseudo-target vanishes.** `step-add/-remove/-move` and the
   "edit the plan then continue" affordance are advertised *only* by
   `workflow_next`'s synthetic append. Static edges never contain `"step"`, so
   `status`, `doctor` recoverable_via, `introspect` recoverable_via, and every
   `valid_next` hint silently drop the structural-edit escape hatch.

3. **Fine-grained gate predicates flatten.** The graph encodes gate verdicts as
   3 `kind="gate"` edges (iterate/proceed/escalate) — it does NOT distinguish
   `gate_proceed` vs `gate_proceed_blocked` vs
   `gate_proceed_agent_availability_blocked`. `force-proceed`-from-blocked relies
   on exactly that last predicate; `status_view` (line 749+) branches on it.
   Collapsing to graph edges erases the distinction that decides whether
   force-proceed-from-blocked is even legal.

4. **doctor / introspect `recoverable_via` go stale or empty.** Both call
   `workflow_next(state)` directly. Against static edges they'd over-report
   (offer skipped phases) on reduced-robustness plans — exactly when an operator
   is debugging and trusts the tool most.

5. **`override` no-ops in BLOCKED state.** Graph edges have no `blocked` node;
   `workflow_next` returns `[]` for blocked. recover-blocked's whole reason to
   exist is that the *graph cannot route out of blocked* — recovery is the
   reverse-edge map (`_BLOCKED_RECOVERY_STATES`), not a forward edge.

## 3. Can the override actions be expressed against graph edges?

**Partially, and only the forward-progress half.**
- `force-proceed` (critiqued/executed path), `replan`, `resume-clarify` describe
  *transitions* that DO correspond to existing edges/states — but they need the
  **robustness-resolved** target, which the raw graph doesn't give. They could
  read edges *if* the graph were first projected through robustness — which is
  precisely what `workflow_next` does.
- `recover-blocked` and `resume_plan` are **reverse projections** (blocked/failed
  → the phase's active state). No forward edge expresses this; they need a
  reverse map. m3 must not assume edges subsume them.
- The `"step"` affordance has **no edge** and must remain a synthetic projection.

Conclusion: override actions need `workflow_next`'s **dynamic, state-derived
projection**, not the static edge list. The edges are necessary input but
insufficient output.

## 4. Safe way to collapse routing WITHOUT breaking escape hatches

**Keep `workflow_next` (and `infer_next_steps`, its alias) as the single
projection function — re-implement its body over the graph, keep its signature.**

Concretely for m3:
1. **Treat the pipeline graph as the data source, `workflow_next` as the view.**
   Make `workflow_next(state)` compute: (a) resolve the robustness/feature-flag
   subgraph (the existing `_workflow_for_robustness` projection logic moves to
   operate on graph edges instead of the `WORKFLOW` dict), (b) filter edges by
   the gate-predicate conditions against `state.last_gate`, (c) re-append the
   synthetic `"step"` for `_STEP_CONTEXT_STATES`. Same return type, same ~15
   callers unchanged.
2. **Do NOT delete the condition vocabulary.** The 7 `_transition_matches`
   predicates must survive as edge metadata; the 3 `kind="gate"` edges in
   `planning.py` are too coarse for force-proceed/status. Either enrich edge
   conditions to the full predicate set or keep `_transition_matches` as the
   resolver invoked by the projection.
3. **Unify the 3 phase↔state maps, don't collapse them away.**
   `_BLOCKED_RECOVERY_STATES`, `_RESUME_ACTIVE_STATES`, and the implicit forward
   transitions are three copies of one relation. Derive all three from the graph
   edges (forward = edge target-state; reverse-recovery = predecessor-state of
   the phase's stage). This is a *correctness win* m3 can bank — but the derived
   maps must still exist as a queryable API for the recovery handlers.
4. **Add a parity test** asserting `workflow_next(state)` over the new graph-backed
   impl equals the legacy dict-backed impl across the cross-product of
   {5 robustness levels} × {with_prep, with_feedback} × {all states} × {all gate
   recommendations}. This is the regression gate that proves recovery hints didn't
   silently drift.

## Residual uncertainty
- I did not read `_pipeline/patterns.py::critique_revise_gate_loop` or
  `builder.py::_escalate_if` in full, so I can't confirm whether the gate-predicate
  granularity *already* exists as edge metadata somewhere (it may, partially). If
  it does, item 2 is cheaper than stated.
- Whether m3 intends to keep `state.current_state` (state-name vocabulary) at all,
  or re-key everything to stage names. If state names are also collapsed, the
  string-literal coupling in override.py (every `STATE_*` comparison) is a second,
  larger breakage axis not fully scoped here.
- The `kind="gate"` typed-edge executor dispatch path was not traced end-to-end;
  it may already centralize verdict→target resolution in a way that helps.
