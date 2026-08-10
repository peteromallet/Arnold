# M1: Unify the graph-pipeline type surface

## Outcome
Graph-pipeline authors use a single, stable, documented import surface (`arnold.pipeline` / `arnold.pipeline.types`), while Megaplan-specific runtime concepts (`plan_dir`, `profile`, `budget`, Megaplan envelope, `Pipeline.builder()`, `run_phase()`) stay on a Megaplan facade/adapter without polluting the neutral Arnold API.

## Scope

IN:
- Audit `arnold/pipeline/types.py` vs `arnold/pipelines/megaplan/_pipeline/types.py`.
- Promote `arnold.pipeline.types` as the canonical neutral surface for `Stage`, `Pipeline`, `Edge`, `Step`, `StepContext`, `StepResult`.
- Keep `_pipeline/types.py` as a compatibility facade that re-exports/extends the neutral types and maps Megaplan-specific fields onto neutral execution (e.g. adapter from neutral `StepContext` to Megaplan `StepContext`).
- Add generic neutral aliases only where truly universal (e.g. `artifact_root`). Do NOT add `plan_dir`, `profile`, `budget`, or Megaplan envelope semantics to `arnold.pipeline.types.StepContext`.
- Keep `Pipeline.builder()` and `run_phase()` on a Megaplan authoring facade, not on the core `Pipeline` dataclass.
- Fix `arnold/pipelines/_template/skills/new-arnold-pipeline/SKILL.md` to import from `arnold.pipeline`.
- Add an executor startup type-origin check that rejects non-canonical families with a clear `TypeError`.
- Update examples to import from the public surface (via the shim where necessary).
- Add regression tests.

OUT:
- Do not move Megaplan-specific runtime fields into neutral types.
- Do not redesign the neutral executor.
- Do not delete `_pipeline/types.py`; keep it as a compatibility/adapter layer.

## Locked decisions
- Neutral surface: `arnold.pipeline` / `arnold.pipeline.types`.
- Megaplan runtime surface: `arnold.pipelines.megaplan._pipeline.types` as an adapter/facade, not a fork.
- Deprecation warnings point authors to the public neutral surface.

## Open questions
- How exactly does `_pipeline.types.StepContext` adapt neutral `StepContext`? Does it subclass, wrap, or map at executor entry?
- Which existing megaplan pipelines need import changes vs. working through the shim?

## Constraints
- All existing megaplan pipelines pass `arnold pipelines check` and a smoke run.
- No change to on-disk plan artifact schema.

## Done criteria
- `arnold pipelines check creative` passes after the refactor.
- A newly scaffolded graph pipeline imports only from `arnold.pipeline`.
- Wrong-type pipeline fails at check/run with a clear `TypeError`.
- `pytest` for touched modules passes.

## Touchpoints
- `arnold/pipeline/types.py`
- `arnold/pipelines/megaplan/_pipeline/types.py`
- `arnold/pipelines/megaplan/_pipeline/executor.py`
- `arnold/pipelines/_template/skills/new-arnold-pipeline/SKILL.md`
- Example pipeline imports
- New regression tests

## Anti-scope
- Do not unify the two executors.
- Do not add Megaplan-specific fields to neutral types.
- Do not refactor `PipelineBuilder` worker injection; that is M3.
