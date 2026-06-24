# M1 - Platform Contract

## Objective

Land the native-first platform transition without breaking unmigrated packages: add `Pipeline.native_program`, make executor and registry prefer it everywhere, keep `resource_bundles` execution compatibility during the migration window, and define the exact tests that prove the platform can support later package work.

## Files To Change And Instructions

- `arnold/pipeline/types.py`
  Add `Pipeline.native_program: NativeProgram | None` and update any helper types or serializers that assume projected pipelines are graph-only.
- `arnold/pipeline/__init__.py`
  Export the native-first public surface; if `arnold.pipeline.legacy` does not exist yet, create a compatibility namespace and re-export graph-era symbols through it instead of keeping them as the primary path.
- `arnold/pipeline/registry.py`
  Make native-backed packages first-class, accept projected shells with `native_program`, and keep legacy graph-only packages loading only as compatibility entries.
- `arnold/pipeline/validator.py`
  Require `driver`, `default_profile`, `supported_modes`, and native-backed `build_pipeline(...)`; permit execution-bearing `resource_bundles` only as a deprecated compatibility case and fail on placeholder strings.
- `arnold/pipeline/discovery/manifest.py`
  Make manifest discovery the default path, but keep `MEGAPLAN_M6_MANIFEST_DISCOVERY` as a no-op compatibility alias until M7 removes it.
- `arnold/pipeline/native/__init__.py`
  Export the compiler, projection, runtime, and resume helpers package authors will use after M1.
- `arnold/pipeline/native/compiler.py`
  Ensure compilation returns the `NativeProgram` attached by package `build_pipeline(...)`.
- `arnold/pipeline/native/graph_projection.py`
  Attach `native_program` to every projected compatibility shell produced from a native declaration.
- `arnold/pipeline/native/runtime.py`
  Make native runtime the default execution path without requiring `ARNOLD_NATIVE_RUNTIME=1`; keep env-flag handling as compatibility only.
- `arnold/pipeline/native/flags.py`
  Convert native-runtime and manifest flags into deprecation-compatible no-ops where possible; do not fully delete the symbols in M1.
- `arnold/pipeline/builder.py`
  Prefer `native_program` when constructing runnable pipelines and keep bundle-based execution fallback only for unmigrated packages.
- `arnold/pipeline/executor.py`
  Prefer `Pipeline.native_program` for executor selection and keep the old bundle-based execution lookup as an explicit transitional fallback.
- `arnold/pipeline/resume.py`
  Route resume through the native runtime contract and remove assumptions that continuation always means "build another graph."
- `arnold/pipelines/megaplan/cli/__init__.py`
  Point pipeline CLI entrypoints at the native-first contract and stop presenting graph runtime as canonical.
- `arnold/pipelines/megaplan/cli/arnold.py`
  Align `arnold pipelines check` and `arnold pipelines describe` with the new projected-shell-plus-`native_program` contract.
- `arnold/pipelines/megaplan/cli/parser.py`
  Keep CLI compatibility flags parseable for now, but mark them deprecated and route help text toward native-first usage.
- `tests/arnold/pipeline/test_executor_selection.py`
  Add coverage that executor selection prefers `native_program` and only falls back to bundle-based execution for explicit compatibility cases.
- `tests/arnold/pipeline/test_registry.py`
  Cover native-backed package registration, projected-shell loading, and compatibility handling for not-yet-migrated packages.
- `tests/arnold/pipeline/test_validator.py`
  Assert the new required metadata, `native_program` expectations, and transitional `resource_bundles` behavior.
- `tests/arnold/pipeline/test_topology_hash.py`
  Prove the new field does not silently destabilize topology-hash behavior.
- `tests/arnold/pipeline/test_resume.py`
  Verify resume works through the native-backed contract.
- `tests/arnold/pipeline/native/test_graph_projection.py`
  Assert projected shells now carry `native_program`.
- `tests/arnold/pipeline/native/test_runtime.py`
  Verify native runtime is the default path without env opt-in.
- `tests/arnold/pipeline/native/test_flags_context.py`
  Rework old flag tests so they validate compatibility aliases instead of runtime gating.
- `tests/_pipeline/test_discovery_manifest.py`
  Cover manifest-first discovery as the default path.
- `tests/_pipeline/test_registry_manifest_discovery.py`
  Verify registry and manifest discovery stay aligned after the M1 contract change.
- `tests/_pipeline/test_registry_python_discovery.py`
  Keep compatibility coverage for remaining Python-discovered packages until later milestones finish migration.
- `tests/resume/test_pre_m6_alias.py`
  Update the old manifest-flag alias tests so they assert compatibility behavior, not required gating.
- `tests/test_pipeline_run_cli.py`
  Verify `megaplan run <name> --describe` resolves through the same metadata used by `arnold pipelines describe`.
- `tests/test_pipelines_check_validator.py`
  Keep end-to-end `pipelines check` coverage aligned with the new validator contract.

## Verifiable Completion Criterion

- `Pipeline.native_program` exists and is populated on projected shells built from native packages.
- Executor-selection tests prove `native_program` wins and compatibility fallback still works.
- Registry, validator, manifest discovery, and CLI tests pass without requiring `ARNOLD_NATIVE_RUNTIME=1`.
- `resource_bundles` execution payloads are still supported only as a documented transitional fallback.

## Risks And Blockers

- `Pipeline.native_program` touches hashing, serialization, registry behavior, and executor selection all at once.
- Deleting compatibility too early would strand every package that still relies on bundle-based execution or old flags.
- CLI and discovery changes can expose stale assumptions in generated docs, templates, and older tests.

## Dependencies

- First milestone.
- M2 through M7 all depend on this contract being in place before package-level cleanup starts.
