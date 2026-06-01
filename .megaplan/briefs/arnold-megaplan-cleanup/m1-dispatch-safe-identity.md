# M1: Dispatch-Safe Megaplan Identity

## Outcome

Make `megaplan` the canonical discovered built-in plugin identity without physically moving the production pipeline outside the current discovery root. Legacy `planning` references should route through an explicit migration alias, not generic defaults.

## Scope

In:
- Rename the discovered built-in pipeline identity from `planning` to `megaplan`. Register `megaplan` as the canonical name. Do not keep `planning` as a co-equal identity.
- Keep implementation under the current discovery root until M2 capability dispatch can support physical relocation.
- Add explicit legacy alias behavior for `planning -> megaplan`.
- Update registry listing, CLI dispatch, status/control lookup, and resume routing enough that `megaplan` works as canonical identity.
- Test legacy `planning` plan resume routing to `megaplan`.

Out:
- Do not physically move to `arnold/pipelines/megaplan/`.
- Do not move stages/prompts/handlers.
- Do not remove old `planning` code paths except where replaced by explicit alias logic.

## Locked Decisions

- Public plugin identity is `megaplan`.
- `planning` is legacy migration identity only.
- `PipelineRegistry().get("megaplan")` must work.
- `PipelineRegistry().get("planning")` may work only through explicit legacy aliasing.
- Set plugin metadata to `name = "megaplan"` and `entrypoint = "build_pipeline"`.
- Set `capabilities = ("plan", "execute", "review")` or the richer capability object chosen by the existing manifest contract.

## Required Outputs

- Implementation choice for temporary file placement: either rename `megaplan/pipelines/planning/` to `megaplan/pipelines/megaplan/` safely or keep files in place while registering `megaplan` as the only canonical identity.
- How to report/record alias migration intent for legacy runs.

## Constraints

- Do not strand the current engine: auto/resume/control still have old call paths in this milestone.
- Do not silently default missing plugin identity to `planning` in auto dispatch, resume routing, control/status lookup, `read_valid_targets()`, or similar control APIs.
- Keep physical movement gated by M2 capability dispatch readiness.

## Done Criteria

- Pipeline listing shows `megaplan`, not `planning`, as the built-in plugin.
- `arnold auto megaplan` does not fail only because the CLI still hardcodes `planning`.
- A captured legacy `planning` plan routes to canonical `megaplan`.
- Tests expecting the built-in identity are updated to `megaplan`.
- The physical plugin move remains blocked until registry scans `arnold.pipelines`, resources resolve there, profiles load there, and legacy aliases route through the run envelope/migration path.

## Touchpoints

- `megaplan/pipelines/planning/`
- `megaplan/_pipeline/registry.py`
- `megaplan/auto.py`
- `megaplan/control_interface.py`
- `megaplan/cli/arnold.py`
- `megaplan/_core/workflow.py`
- profile and registry tests

## Anti-Scope

- Do not delete `_pipeline/planning.py`.
- Do not remove `GateRecommendation`.
- Do not perform package-wide import rename.
