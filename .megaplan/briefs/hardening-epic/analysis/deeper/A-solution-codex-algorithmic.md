# Algorithmic Design: Make Plan Critique a Contraction

The plan-critique loop should stop behaving like repeated whole-plan rediscovery. Split critique into two modes with persisted state: an initial exhaustive discovery pass that must close enumerable sets, followed by anchored differential re-critique that invalidates prior pass verdicts only when the plan delta touches their dependency footprint. The hard cap remains, but only as a failure detector.

## Data Model

Add a per-plan artifact, `critique_anchors.json`, maintained by `handle_critique` after writing `critique_vN.json` at `megaplan/handlers/critique.py:424`:

```json
{
  "schema_version": 1,
  "iteration": 3,
  "closed_sets": {
    "CS-json-writers": {
      "lens": "all_locations",
      "query": "state.json writer sites",
      "evidence": ["rg 'write_text\\(|atomic_write_json|json.dump' megaplan"],
      "locations": [
        {"path": "megaplan/foo.py", "symbol": "save_x", "line": 42, "role": "writer"}
      ],
      "negative_evidence": ["rg found no FileStore JSON writers outside megaplan/storage"],
      "plan_coverage": ["Phase 2 / Step 3", "Phase 2 / Step 4"],
      "hash": "stable hash over query+locations+coverage"
    }
  },
  "pass_anchors": {
    "A-scope-001": {
      "lens": "scope",
      "claim": "All state.json writer sites are enumerated and assigned.",
      "plan_spans": [{"heading": "Phase 2", "start_line": 77, "end_line": 118}],
      "code_footprint": [{"path": "megaplan/storage.py"}, {"path": "megaplan/handlers"}],
      "depends_on_closed_sets": ["CS-json-writers"],
      "created_iteration": 1,
      "last_validated_iteration": 2,
      "status": "valid"
    }
  }
}
```

This is not a second flag registry. Flags remain in the existing registry. Anchors record negative work: what was checked and why it remains passed. Closed sets record finite enumerations future rounds can reuse.

## 1. Front-Loaded Completeness

The first critique pass for discovery-shaped lenses must be a closure pass. In `megaplan/audits/robustness.py:47-78`, mark `scope`, `all_locations`, and `callers` with `requires_closed_set: true` and a `closure_kind` such as `related_locations`, `pattern_instances`, or `call_graph`. The prompt builder in `megaplan/prompts/critique.py:441-486` should add a mandatory closure contract whenever one of these checks runs:

1. State the enumerable universe.
2. List the exact search commands or AST/query tools used.
3. Emit every location found, grouped by role.
4. Explain exclusions.
5. Map each location to either an existing plan step, a new blocking flag, or a justified non-requirement.
6. Return `closed_set_evidence[]` in the critique JSON.

"Closed" means the critic provides positive evidence, negative evidence, and coverage mapping. For M2, a valid set would include every state JSON writer with command evidence like `rg` patterns, a location list, and plan coverage for each writer. A finding that says "checked writer X" without an exhaustive set fails validation.

Hook this in two places. First, extend the critique schema to accept `closed_set_evidence`. Second, strengthen `validate_critique_checks` after `megaplan/handlers/critique.py:394`: if an active check has `requires_closed_set`, reject outputs that lack a closed set, have an empty command list, have no locations, or contain locations with no coverage/disposition. In parallel mode, `_run_check` in `megaplan/orchestration/parallel_critique.py:49-123` should apply the same closure validation.

This turns discovery from "find one more thing" into "prove the finite set now." If a critic cannot close the set, it must raise one blocking meta-flag: "closed set not proven for X."

## 2. Diff-Aware Re-Critique with Anchored Verdicts

Today the critic sees the full latest plan at `megaplan/prompts/critique.py:298-299`, gets only supplementary diff context at `megaplan/handlers/critique.py:336-357`, and the evaluator reselects lenses fresh at `megaplan/handlers/critique.py:207-218`. Replace that with an invalidation step before evaluator dispatch.

Add `megaplan/orchestration/critique_anchors.py`:

- `load_anchors(plan_dir)`
- `derive_plan_spans(plan_text)`
- `compute_anchor_invalidations(previous_plan, current_plan, anchors, flag_resolutions)`
- `build_anchor_context(valid, invalidated)`
- `merge_critique_anchors(critique_payload, old_anchors, current_plan)`

Invalidation is conservative. A pass anchor remains valid only if all of these hold: its plan spans are byte-equivalent or only line-number shifted; every dependent closed set hash is unchanged; no new or revised flag names the same subsystem, symbol, or path; and the current plan diff does not touch headings or bullets in the anchor span. If any condition fails, the anchor becomes `invalidated` with a reason and its lens is eligible to run. If a changed section imports, deletes, renames, or broadens a dependency that intersects the anchor's `code_footprint`, invalidate it even if the text span did not change.

The evaluator prompt in `megaplan/prompts/critique_evaluator.py` should receive valid and invalidated anchor blocks. It must not select lenses whose only rationale is already covered by a valid anchor, and must select lenses for invalidated anchors and newly changed regions. The critique prompt in `megaplan/prompts/critique.py:268-325` should show valid anchors as carried-forward PASS verdicts: do not rescan anchored regions unless invalidated; do check whether changed regions break them.

This preserves safety because anchors are cached proofs with dependencies. Any relevant delta invalidates them.

## 3. Bounded Revise Churn

The revise prompt at `megaplan/prompts/critique.py:101-131` currently asks for a complete revised plan and gives no edit budget. Keep the full-plan output requirement for compatibility, but add a delta contract:

- Touch only sections referenced by open blocking flags, invalidated anchors, or required structural metadata.
- Preserve all valid anchor spans exactly.
- Default delta budget: max 15% changed lines or 40 lines, whichever is larger.
- If a root-cause correction truly requires larger churn, return `delta_budget_override` with affected flags and rationale; the gate treats unjustified override as blocking.

Enforcement should be code, not just prompt. After revise writes a new plan, compute line delta using `compute_plan_delta_percent` from `megaplan/orchestration/gate_signals.py:55-59` plus changed-line count. Add `revise_delta.json` with changed headings, changed lines, percent delta, touched anchors, and budget status. If budget is exceeded without an override tied to open blocking flags, create a blocking completeness flag before the next critique or force "churn audit" mode.

The bound is intentionally tight: 15% allows localized repair while making 53% churn impossible unless the reviser declares a new approach. Valid anchor spans must be text-preserved.

## 4. Convergence Metric and Backstop

Define the loop variant:

```text
V = (
  open_blocking_flag_count,
  invalidated_anchor_count,
  unclosed_required_set_count,
  churn_violation_count
)
```

Order it lexicographically, with the first component dominant. A normal revise must decrease `open_blocking_flag_count` and must not increase the other three except where a declared root-cause override invalidates anchors. New flags are allowed only from a newly closed set or changed-region critique, not blind rescans of valid anchors.

Extend `build_gate_signals` at `megaplan/orchestration/gate_signals.py:91-220` to include `convergence`: previous and current `V`, resolved prior blocking count, new blocking count, closed set count, invalidated anchors, churn budget status, and `no_net_progress`. Then change `_apply_gate_outcome` at `megaplan/handlers/gate.py:360-361`: on `ITERATE`, return `revise` only if `V` decreased or the gate explicitly records a root-cause override. If `V` is unchanged for one round, route to `tiebreaker` or `override add-note` with a diagnostic. If `V` worsens without justified override, route to `revise` once in constrained repair mode; a second worsening escalates.

Set the hard cap to four plan-critique iterations for normal robustness and six for apex. This cap is not the convergence mechanism. It catches invalid closure evidence, prompt noncompliance, ambiguity, or root-cause drift.

## Why M2 Becomes 2-3 Rounds

Round 1 would have forced `all_locations` and `scope` to close the two finite universes: every state.json writer and every FileStore/DBStore parity location. The two concern threads would produce two closed sets and up to 17 flags immediately, instead of one adjacent location per pass. The reviser would then be constrained to touch only the sections mapping those flags, preserving unrelated anchors.

Round 2 critique would verify revised sections against the two closed sets, carry forward anchored PASS verdicts, and invalidate only spans touched by the repair. If the reviser missed one location from the already-closed set, the critic would raise it in the same thread. Round 3 is cleanup for residual misses or justified larger churn.

Non-convergence can still happen if the closed set is wrong, the codebase search surface is dynamic or too large for the critic, the user changes scope mid-loop, or the reviser repeatedly exceeds the delta budget. In those cases the backstop produces a meaningful stop condition: "cannot prove closure," "variant not decreasing," or "churn budget violated," with artifacts showing which invariant failed. That is a debuggable loop-control failure, not an arbitrary cutoff after nine rounds.
