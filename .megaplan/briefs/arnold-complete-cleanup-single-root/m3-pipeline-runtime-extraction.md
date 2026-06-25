# M3: Pipeline And Runtime Extraction

## Outcome

The remaining legacy `_pipeline` and runtime implementation responsibilities have canonical homes under `arnold_pipelines.megaplan`, and callers/tests move to those homes. The final design does not recreate `_pipeline` as a permanent namespace.

## Scope

In:

- Extract executor, builder, resume, preflight, registry, dispatch, subloop, pattern, hook, validator, artifact, planning, receipt, fault, taint, and step responsibilities from `arnold/pipelines/megaplan/_pipeline`.
- Prefer responsibility-named canonical modules such as `runtime/executor.py`, `runtime/resume.py`, `runtime/preflight.py`, `registry.py`, `cli/run.py`, `runtime/dispatch.py`, and `runtime/patterns.py`.
- Migrate `tests/test_pipeline_run_cli.py` and related tests off legacy imports as each canonical responsibility lands.
- Repoint canonical bridges and callers away from legacy executor/runtime modules.
- Batch runtime process isolation changes: `process.py`, `execution_environment.py`, `engine_isolation.py`, worker env builders, and Hermes runtime import resolution.

Out:

- Do not preserve `_pipeline` as a final API for convenience.
- Do not move unrelated pipeline-authoring substrate work into this milestone.
- Do not change checkout/workspace isolation semantics unless a characterization test proves the current behavior and the change is required for root consolidation.

## Locked Decisions

- `arnold_pipelines.megaplan` is the implementation authority.
- Legacy implementation files must downgrade from `implementation` to `shim` to deleted, never the reverse.
- Worker subprocesses must resolve the same engine root as the parent.

## Done Criteria

- No canonical module imports implementation code from `arnold.pipelines.megaplan._pipeline`.
- Core CLI/run/resume tests target canonical modules.
- Engine-root, execution-environment, and worker subprocess parity gates pass.
- The legacy registry count and implementation-file count shrink from M1.
