# M3.5 - Canonical Megaplan Migration

## Objective

Migrate the canonical `megaplan` pipeline, native runner, and auto-drive path onto the native-first contract before test cleanup so the repo no longer depends on stage-order heuristics, bundle-carried execution metadata, or legacy topology-hash assumptions for the flagship workflow.

## Files To Change And Instructions

- `arnold/pipelines/megaplan/__init__.py`
  Make canonical Megaplan metadata and package exports resolve through the native-first contract.
- `arnold/pipelines/megaplan/pipeline.py`
  Rewrite canonical `build_pipeline(...)` so it compiles the native declaration, projects the compatibility shell, attaches `native_program`, and stops encoding execution state through `resource_bundles` strings or `_LEGACY_STAGE_ORDER`-style shortcuts.
- `arnold/pipelines/megaplan/native_runner.py`
  Make the runner consume `Pipeline.native_program` first and keep old bundle-based execution only as a fallback for explicit compatibility cases.
- `arnold/pipelines/megaplan/auto.py`
  Route auto-drive, resume, and recovery through the canonical native-backed pipeline instead of graph-era runner assumptions.
- `arnold/pipelines/megaplan/_compatibility.py`
  Keep only compatibility shims that are still required after the canonical migration; remove stage-order or topology assumptions that are no longer needed.
- `arnold/pipelines/megaplan/cli/arnold.py`
  Make `arnold pipelines describe megaplan` and related CLI paths use the canonical metadata from the migrated package.
- `arnold/pipelines/megaplan/cli/parser.py`
  Keep describe and auto subcommands aligned with the canonical native-backed runtime path.
- `arnold/pipeline/native/routing.py`
  Remove Megaplan-specific stage-order routing heuristics only after `arnold/pipelines/megaplan/pipeline.py` declares enough native structure to route itself correctly.
- `arnold/pipeline/executor.py`
  Delete any canonical-Megaplan-specific executor fallback that became unnecessary once the flagship package carries `native_program`.
- `tests/test_auto.py`
  Update auto-drive coverage to the migrated canonical runtime path.
- `tests/test_auto_driver_lock.py`
  Keep driver-lock behavior stable after the runtime contract change.
- `tests/test_auto_escalation.py`
  Keep escalation flow stable under the native-backed auto path.
- `tests/test_auto_phase_timeout_retryable.py`
  Keep retryable phase-timeout behavior stable.
- `tests/test_auto_pipeline_runtime.py`
  Assert the canonical auto path now runs against the native-backed contract.
- `tests/test_pipeline_run_cli.py`
  Verify `megaplan run megaplan --describe` resolves through the same migrated metadata as `arnold pipelines describe megaplan`.
- `tests/characterization/test_auto_drive.py`
  Re-baseline characterization coverage for the migrated canonical runtime.
- `tests/characterization/test_pipeline_golden.py`
  Re-baseline golden behavior that still depends on canonical Megaplan runtime flow.
- `tests/arnold/conformance/test_megaplan_coupling_gate.py`
  Keep the coupling gate aligned with the migrated canonical contract.
- `tests/arnold/pipeline/native/test_resume_routing.py`
  Assert native resume routing no longer depends on Megaplan-specific stage-order heuristics.
- `tests/arnold/pipelines/megaplan/test_bridged_executor.py`
  Remove assumptions that canonical Megaplan still needs a graph-bridge executor.
- `tests/arnold/pipelines/megaplan/test_native_execution_parity_fixtures.py`
  Update fixtures and assertions to the migrated canonical runtime behavior.
- `tests/arnold/pipelines/megaplan/test_native_parity.py`
  Convert the suite to native-truth coverage for the canonical pipeline.
- `tests/arnold/pipelines/megaplan/test_native_parity_golden_traces.py`
  Keep golden traces aligned with the migrated canonical runtime path.
- `tests/arnold/pipelines/megaplan/test_pipeline_contracts.py`
  Assert canonical Megaplan now satisfies the same `native_program` contract as the subpipelines.

## Verifiable Completion Criterion

- `arnold/pipelines/megaplan/pipeline.py` returns a projected shell with non-null `native_program`.
- `native_runner.py` and `auto.py` execute canonical Megaplan through `native_program` rather than stage-order strings or graph-first bundle payloads.
- Megaplan-specific routing heuristics are removed from `arnold/pipeline/native/routing.py` without breaking the named tests.

## Risks And Blockers

- This is the highest-risk migration outside `evidence_pack` because it touches the flagship runtime, CLI, auto drive, resume, and characterization goldens together.
- Removing heuristics too early will break routing; leaving them in place too long will keep M5 and M7 ambiguous.
- Characterization fixtures can produce large diffs once the canonical runtime stops using the old bridge behavior.

## Dependencies

- Depends on M1, M2, and M3.
- Must finish before M4 shares the final resume contract broadly and before M5 rewrites test truth around native execution.
