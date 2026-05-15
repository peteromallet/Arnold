# Sprint 4 Chunk D — `subloop` + `override` executor branches

Full Sprint-4 plan at `briefs/sprint-4-elegance.md`. Chunk D follows
Chunks A (typed edges), B (handler ports), C (auto-pipeline runtime).

## Problem

`subloop` and `override` are declared on the Step.kind Literal but the
executor has no branch for them. Tiebreaker is still two regular
stages (`tiebreaker_pending` → `tiebreaker_ready`) and override is
still a CLI escape hatch outside the state machine.

## What ships in Chunk D

1. **Subloop executor branch.**
   - Add an optional `child_pipeline: Pipeline | None = None` to the
     Step protocol (or carry it on the Stage). When
     `step.kind == "subloop"`, the executor builds a child
     StepContext (inherits parent's plan_dir, profile, mode but with
     a child artifact_root), recursively calls `run_pipeline`, and
     promotes the child's final state into a Verdict on the parent.
   - Document the contract: subloop stages always produce a Verdict;
     the child's StepResult outputs are NOT merged into the parent's
     artifact set (they live under the subloop's artifact_root).

2. **`TiebreakerSubloop` Step.** Replace the legacy
   `tiebreaker_pending` / `tiebreaker_ready` state machine pair with a
   single `Subloop` Step whose child Pipeline has
   `researcher → challenger → synthesis` stages. The child outputs
   the synthesis decision; the parent's Verdict captures it.

3. **State name migration.** The legacy `tiebreaker_pending` /
   `tiebreaker_ready` state names disappear. Existing plans with
   persisted state.json carrying those names need migration. Ship a
   `megaplan/_pipeline/migrate.py` helper that auto-detects + remaps
   on plan load.

4. **Override executor branch.**
   - Add `override_edges: tuple[Edge, ...] = ()` to `Stage` (and
     `ParallelStage`). When a Step returns a `StepResult` whose
     `verdict.override` is set, the executor matches against
     `override_edges` first (before the normal edges).
   - Refactor `override force-proceed`, `override abort`,
     `override replan`, `override add-note` from CLI escape
     subcommands into edges on the relevant Stage. The CLI subcommand
     still exists (back-compat shim) but it constructs a Verdict
     with the matching `override` action and submits it through the
     executor.

5. **Update planning.py compilation** to emit `override_edges` on
   the relevant stages (today's WORKFLOW table encodes them as
   regular Transitions with `condition="gate_escalate"`).

## Out of scope

- Deleting WORKFLOW (Chunk E).
- Polish + docs (Chunk F).

## Constraints

- Existing tiebreaker tests
  (`tests/test_tiebreaker_*`) must pass unchanged in behaviour.
- Existing override tests
  (`tests/test_override_strict_notes.py`, etc.) must pass.
- Live `megaplan` must keep working.
- All commits on `decomp/main`.

## Acceptance

- New `tests/test_pipeline_subloop.py` exercises a hermetic
  parent→child subloop pipeline.
- New `tests/test_pipeline_override.py` exercises override-edge
  routing on a hermetic pipeline.
- `tests/test_tiebreaker_*` tests still pass.
- The state names `tiebreaker_pending` / `tiebreaker_ready` are gone
  from production code paths (legacy migration helper retains them
  as recognised input names).
- Full `pytest tests/` stays green.

## Operating principles

Same as Chunks A + B + C.
