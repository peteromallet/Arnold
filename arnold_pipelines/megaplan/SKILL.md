---
name: megaplan
description: Run the canonical Megaplan planning pipeline from its Arnold plugin home.
---

# Megaplan

Use this pipeline for high-rigor planning workflows that need prep, plan,
critique, gate, revise, finalize, execute, review, and tiebreaker stages.

For epic-sized, migration, public-contract, or otherwise drift-sensitive work,
capture durable end-state intent with a North Star anchor: pass
`--north-star PATH` to `megaplan init` for a standalone plan, or declare
`anchors.north_star` in `chain.yaml` for epics.

---

## North Star Actions (v1)

### Where questions come from

North Star questions are **explicitly authored** — they are not extracted from
code, diffs, or execution traces. In v1 the pipeline reads them from a
`NORTHSTAR.md` file in the plan directory (standalone plans) and/or from
sprint-brief anchors declared in `chain.yaml` (epic chains).  There is no
semantic-parity extraction step: if a question is not written in one of those
sources it does not exist from the pipeline's point of view.

### How actions flow through the pipeline

1. **Gate (structured carry).**  When a gate or reviewer evaluator raises a
   concern tied to a North Star question, it emits a `north_star_actions[]`
   entry — an action with a concrete `action_type` (`change_plan`,
   `add_gate`, `add_scenario`, `add_checker`, `dead_delete`, or
   `add_human_halt`), a `severity` (blocking/advisory), supporting evidence,
   and optional plan references.  Actions in the *dangerous* categories
   (`route_authority`, `baselines`, `row_carrier_exemptions`,
   `target_narrowing`, `generated_conformance_authority`,
   `live_plan_topology_resume_risk`) are **blocking by schema rule** regardless
   of what the evaluator labels them.  All actions are normalized at gate time
   and carried forward through `gate_carry.json` (with `gate.json` as a
   fallback).

2. **Revise (change the plan or halt).**  The revise worker prompt receives
   the carried `north_star_actions[]` with per-action-type instructions:
   - `change_plan` — make a concrete, traceable plan change.
   - `add_gate` — add an explicit gate requirement.
   - `add_scenario` — add a concrete scenario / test case.
   - `add_checker` — add an automated checker.
   - `dead_delete` — remove dead plan steps.
   - `add_human_halt` — halt; the action cannot be mapped to a plan change.

   Before the revise worker runs, a pre-worker guard halts through the
   existing `CliError`/step-failure path when any carried blocking action is
   `add_human_halt`, has an unrecognized `action_type`, or is a
   dangerous-category blocker with no concrete target (`plan_refs` or
   `required_change`).  **Revise must change the plan or halt** — it cannot
   silently ignore a blocking action.

   After the revise worker completes, the pipeline validates that every
   carried blocking action has a corresponding `north_star_actions_addressed[]`
   entry with concrete `plan_refs` and the matching `action_type` marker.
   Prose-only resolutions, mismatched action types, and omitted actions are
   rejected (fail-closed).

3. **Finalize / Review → done (closeout blocking).**  Finalize refuses to
   produce executable tasks if any carried blocking North Star action is
   unresolved in the latest revise metadata.  The review→done transition
   runs a separate pre-check before `TransitionPolicy.evaluate_review_done()`;
   unresolved blocking actions deny the transition through the existing
   denial path.  Absent or malformed `north_star_actions_addressed[]` is
   treated as all-carried-blocking-unresolved (fail-closed).

### `north_star_critical` and robustness

Chain and milestone specs support an optional `north_star_critical: bool`
(default `false`).  When `true`, the milestone (or chain) declares that
North Star enforcement is mandatory for that work unit and cannot be
skipped.

`north_star_critical: true` is **incompatible** with `bare` and `light`
robustness.  The chain-spec validator rejects these combinations with a
`CliError` — it never silently upgrades the robustness level.  Acceptable
robustness levels are `full`, `thorough`, and `extreme`.  Milestone-level
robustness takes precedence over driver-level robustness when both are
present; `north_star_critical` is OR'd across the chain-level and
milestone-level settings.

### Missing packaged skill paths

Some North Star action types conceptually suggest packaged skills (e.g. a
`dead_delete` action could map to a dead-code-removal skill), but no such
skills ship with the pipeline today.  These are **packaging follow-up
items** — the pipeline enforces the structured action contract regardless,
and any future skill packaging would consume the existing
`north_star_actions[]` / `north_star_actions_addressed[]` metadata without a
contract change.
