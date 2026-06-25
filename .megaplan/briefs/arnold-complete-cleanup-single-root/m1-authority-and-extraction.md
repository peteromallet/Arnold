# M1: Canonical Authority And Extraction

## Outcome

`arnold_pipelines.megaplan` becomes the real authority for import-time behavior, public supported surfaces, and runtime implementation responsibilities. Legacy `_pipeline` and runtime code is extracted into named canonical modules without recreating `_pipeline` as a final namespace.

## Scope

In:

- Migrate load-bearing import side effects to canonical modules: content-type registration, model adapter installation, normalizer registration, and registry setup.
- Add import-order subprocess tests for canonical-only, legacy-only if still present, canonical-then-legacy, and legacy-then-canonical.
- Reconcile public exports: move supported symbols to canonical APIs or deliberately remove them with tests/docs.
- Extract executor, builder, resume, preflight, registry, dispatch, subloop, pattern, hook, validator, artifact, planning, receipt, fault, taint, and step responsibilities from legacy `_pipeline`.
- Prefer responsibility-named canonical modules such as `runtime/executor.py`, `runtime/resume.py`, `runtime/preflight.py`, `registry.py`, `cli/run.py`, `runtime/dispatch.py`, and `runtime/patterns.py`.
- Batch runtime process isolation changes: process root detection, execution environment, engine isolation, worker env builders, and Hermes runtime import resolution.
- Migrate tests and callers to canonical modules as each responsibility moves.

Out:

- Do not preserve `_pipeline` as a final API.
- Do not delete the legacy root yet.
- Do not change checkout/workspace isolation semantics without characterization proof.

## Done Criteria

- `arnold_pipelines.megaplan` no longer needs `arnold.pipelines.megaplan` for initialization side effects.
- Import-order matrix tests pass.
- No canonical module imports implementation code from `arnold.pipelines.megaplan._pipeline`.
- Core CLI/run/resume/runtime tests target canonical modules.
- Engine-root, execution-environment, and worker subprocess parity gates pass.
