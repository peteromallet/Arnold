# M1: Canonical Authority And Extraction

## Outcome

`arnold_pipelines.megaplan` is the real authority for import-time behavior, public supported surfaces, and runtime implementation responsibilities on `main`. The authority inversion, side-effect migration, and legacy-root deletion landed in commit `1052ef091a`; this brief is a post-hoc verification of that result without recreating `_pipeline` as a final namespace.

## Scope

In:

- Verify the landed load-bearing import side effects in canonical modules: content-type registration, model adapter installation, normalizer registration, and registry setup.
- Verify import-order subprocess tests for canonical-only, legacy-only if still present, canonical-then-legacy, and legacy-then-canonical.
- Verify public exports: supported symbols are on canonical APIs or deliberately removed with tests/docs.
- Verify the landed responsibility homes for executor, builder, resume, preflight, registry, dispatch, subloop, pattern, hook, validator, artifact, planning, receipt, fault, taint, and step behavior.
- The actual canonical homes are: executor -> `arnold_pipelines/megaplan/execute/batch.py` + `arnold_pipelines/megaplan/execute/core.py`; preflight -> `arnold_pipelines/megaplan/preflight.py` + `arnold_pipelines/megaplan/execute/preflight.py`; dispatch -> `arnold_pipelines/megaplan/_core/dispatch.py`; patterns -> `arnold_pipelines/megaplan/pattern_dynamic.py` + `arnold_pipelines/megaplan/runtime/pattern_topology.py`; registry -> `arnold_pipelines/megaplan/registry.py` (rehomed from `_pipeline.registry`); resume -> `arnold_pipelines/megaplan/runtime/resume.py`; process isolation -> `arnold_pipelines/megaplan/runtime/process.py`.
- `runtime/executor.py`, `runtime/preflight.py`, `runtime/dispatch.py`, and `runtime/patterns.py` do not exist and should not be created merely to match the old preferred names.
- Verify the landed process-isolation behavior: process root detection, execution environment, engine isolation, worker env builders, and Hermes runtime import resolution.
- Verify tests and callers target canonical modules after each responsibility move.

Out:

- Do not preserve `_pipeline` as a final API.
- Do not repeat the legacy-root deletion; it already landed on `main` in `1052ef091a`.
- Do not change checkout/workspace isolation semantics without characterization proof.

## Done Criteria

- `[Verified on current main, 1052ef091a]` `arnold_pipelines.megaplan` no longer needs `arnold.pipelines.megaplan` for initialization side effects.
- `[Verified on current main]` Import-order matrix tests pass.
- `[Verified on current main, 1052ef091a]` No canonical module imports implementation code from `arnold.pipelines.megaplan._pipeline`.
- `[Verified on current main]` Core CLI/execute/resume/runtime tests target canonical modules.
- `[Verified on current main]` Engine-root, execution-environment, and worker subprocess parity gates pass.
