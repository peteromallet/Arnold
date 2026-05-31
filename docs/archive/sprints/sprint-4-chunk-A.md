# Sprint 4 Chunk A — Typed verdicts + typed edges

The full Sprint-4 plan is at `.megaplan/briefs/sprint-4-elegance.md`. This file is
the Chunk-A subset.

## Problem

Today `Edge.label` is a string like `"gate_iterate:revise"` that packs
two fields (condition + next_step). `Verdict.recommendation` doesn't
exist — the gate stores its decision in a JSON file and the matching
edge is found by string compare.

## What ships in Chunk A

1. Extend `megaplan/_pipeline/types.py`:
   - `GateRecommendation = Literal["proceed", "iterate", "tiebreaker", "escalate"]`
   - `OverrideAction = Literal["force_proceed", "abort", "replan", "add_note"]`
   - Add `recommendation: GateRecommendation | None = None` and
     `override: OverrideAction | None = None` to `Verdict`.
   - Add `EdgeKind = Literal["normal", "gate", "override"]`
   - Add `Edge.kind: EdgeKind = "normal"` defaulted; for `kind="gate"`,
     edges match on `Verdict.recommendation` instead of label-string.
2. Update `megaplan/_pipeline/executor.py`: when a Step returns a
   `StepResult` whose `verdict.recommendation` is set, prefer matching
   on that over the label-string. Keep label-string matching for
   `kind="normal"` edges.
3. Update `megaplan/_pipeline/planning.py::_edges_from_transitions` to
   emit typed gate edges. The legacy WORKFLOW-derived edges with
   condition `gate_iterate`/`gate_proceed`/`gate_tiebreaker`/`gate_escalate`
   become `Edge(kind="gate", recommendation=...)`. Non-gate transitions
   stay `Edge(kind="normal", label="<step>")`.
4. Update doc-critique demo + composability tests to use the typed
   shape where they touch gate semantics.

## Out of scope for Chunk A

- Porting any handler into a Step (Chunk B).
- Modifying `auto.py` (Chunk C).
- Subloop / override executor branches (Chunk D).
- Deleting WORKFLOW (Chunk E).

## Constraints

- All Sprint 1–3 tests must still pass.
- Live `megaplan` (system shebang) must keep working — verify after
  every commit with the smoke check.
- All commits on `decomp/main`.

## Acceptance

- New `tests/test_pipeline_typed_edges.py` asserts:
  - `Verdict` has the new typed fields.
  - The compiled planning Pipeline emits `Edge(kind="gate", ...)`
    for gate transitions; `Edge(kind="normal", label=...)` for the
    rest.
  - `git grep -E "gate_iterate:|gate_proceed:|gate_tiebreaker:|gate_escalate:" megaplan/` returns no hits in production code.
  - Edge dispatch by typed verdict works end-to-end on a tiny
    pipeline test.
- All 90+ existing pipeline tests still pass.
- Full `pytest tests/` stays green (except the pre-existing
  test_profile_smoke and test_run_shannon_step flakes).

## Operating principles

- No human review or approval gates.
- Self-validating tests are the only gate.
- Blockers via fallback paths; >2 attempts → `BLOCKER-<n>.md`.
- Live megaplan invariant verified after every commit.
- Same worktree, same branch (`decomp/main`).
