# M0: Neutral Arnold Boundary Skeleton

## Outcome

Create the neutral Arnold package skeleton and primitive type surface without changing the current Megaplan runtime. This milestone proves the target shape and boundary gates before old code starts importing it.

## Scope

In:
- Add `arnold/` package skeleton.
- Add `arnold/pipeline/` with neutral primitive types and exports.
- Include only neutral names: `Pipeline`, `Stage`, `ParallelStage`, `Edge`, `Step`, `StepContext`, `StepResult`, `PipelineVerdict`, `StateDelta`, and `apply_delta`.
- Shape `StepContext` with neutral runtime names such as `artifact_root` or `run_root`, opaque state, and resource handles. Do not copy `plan_dir` or Megaplan `PlanState` assumptions.
- Add boundary tests for `arnold/pipeline/**`.

Out:
- Do not use the new package from current runtime code yet.
- Do not move stages, prompts, handlers, auto, resume, or control paths.
- Do not rename package metadata.

## Locked Decisions

- `PipelineVerdict.recommendation` and `PipelineVerdict.override` are `str | None`.
- No `GateRecommendation` or `OverrideAction` literals in generic Arnold.
- No `"planning"` literal in `arnold/pipeline/**`.
- No imports from `megaplan` in `arnold/pipeline/**`.

## Required Outputs

- Exact file layout inside `arnold/pipeline/`.
- Initial boundary test placement under `tests/arnold/` or the closest existing pipeline test root, with the choice documented in the test file name or module docstring.

## Constraints

- Existing Megaplan runtime behavior remains unchanged.
- This is additive. If a change requires old runtime code to import `arnold.pipeline`, defer it.
- Keep the diff small and reviewable.

## Done Criteria

- `arnold/__init__.py`, `arnold/py.typed`, `arnold/pipeline/__init__.py`, and neutral primitive modules exist.
- Boundary tests fail on `megaplan` imports, `"planning"`, and the Megaplan gate recommendation literals `"proceed"`, `"iterate"`, `"tiebreaker"`, and `"escalate"` in `arnold/pipeline/**`.
- Old runtime tests still pass.
- The next milestone can safely work on identity without depending on the new primitives.

## Touchpoints

- `arnold/`
- `tests/`
- `docs/arnold/package-disposition.md`
- `docs/arnold/package-disposition.yaml`

## Anti-Scope

- Do not edit `megaplan/auto.py`.
- Do not rename `megaplan/pipelines/planning/`.
- Do not copy `_phase_arg_overrides`, `Pipeline.run_phase()`, `_forward_m2_m3.py`, or `restore_and_diverge`.
- Do not implement `PipelineResourceBundle`, `PipelineResources`, `OperationSettings`, or `StageRuntimeSettings`; only neutral resource-handle slots may be shaped for later use.
