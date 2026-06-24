# Arnold Pipeline Migration Completion Plan V3
+
+## Decision
+
+This migration ends with **native as the only canonical authoring and runtime model**. The repository will not target a dual graph/native equilibrium.
+
+The concrete end-state contract is:
+
+- `build_pipeline(...)` returns a **projected `Pipeline` shell**.
+- That `Pipeline` shell must carry a **required `native_program` field** containing the compiled `NativeProgram`.
+- `resource_bundles` is reserved for prompt/resource bundles only. It must not carry execution bundles or placeholder strings.
+- The returned `Pipeline` exists only for compatibility with registry, topology hashing, manifest/describe UX, and temporary graph-baseline tests during the purge window.
+- Native declarations in `pipeline.py` are the source of truth. Hand-built graph builders are temporary private baselines only.
+- `driver` is standardized to `("native", "<kind>")`. No graph-first strings, no mixed forms.
+- `default_profile` and `supported_modes` are required package metadata. Missing values are validation errors.
+- Native runtime is unconditional. `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, `MEGAPLAN_PIPELINE_AUTO`, and graph scaffold switches are deleted.
+
+This is the final shape because it is the cleanest end-state that is still implementable in one migration wave. Returning a bare `NativeProgram` would force a larger cross-cutting registry/CLI/test contract rewrite than this effort needs. Keeping projected `Pipeline` plus a first-class `native_program` field preserves the stable external surface while making graph projection explicitly secondary.
+
+## Final End-State Contract
+
+### 1. Public API
+
+`arnold.pipeline` becomes native-first:
+
+- Keep/export: `Pipeline`, `PipelineResourceBundle`, `NativeProgram`, `phase`, `pipeline`, `decision`, `parallel`, `native_panel`, `compile_pipeline`, `project_graph`, `run_native_pipeline`.
+- Move graph-era builder/executor entry points to `arnold.pipeline.legacy` and leave only temporary deprecation aliases in `arnold.pipeline.__init__` during the purge window.
+- `run_pipeline()` and `run_pipeline_resume()` stop being promoted as the main execution surface. Native runtime is the canonical execution path.
+
+### 2. Package contract
+
+Every runtime package must converge on this structure:
+
+```text
+arnold/pipelines/<package>/
+├── __init__.py      # metadata + build_pipeline export
+├── pipeline.py      # native declaration only
+├── steps.py         # runtime-agnostic step logic
+├── prompts/         # package-owned prompt assets
+└── _legacy.py       # temporary graph baseline, deleted in final purge
+```
+
+Rules:
+
+- `build_pipeline(...)` lives in `__init__.py` and does only: compile native declaration, project graph, attach `native_program`, attach prompt/resource bundles, return `Pipeline`.
+- `_build_legacy_graph_pipeline()` is the only allowed legacy naming.
+- `writing_panel_strict.py` must become `arnold/pipelines/megaplan/pipelines/writing_panel_strict/`.
+- `select-tournament` must be renamed to `select_tournament`.
+- Centralized Megaplan prompt export registries are deleted. Prompt ownership is per package.
+
+### 3. Human gate and continuation
+
+- One shared primitive wins: `@decision(human_gate=True)`.
+- Add `arnold.pipeline.human_gate` as sugar if needed, but do not keep package-specific human-gate abstractions.
+- `evidence_pack`, `deliberation`, `writing_panel_strict`, and canonical Megaplan must all use the same suspension/resume contract.
+- Continuation is runtime behavior of `run_native_pipeline(..., resume=...)`, not a separate continuation builder.
+
+### 4. Discovery, registry, CLI
+
+- Manifest-first discovery is unconditional.
+- Registry accepts only native-authored packages as first-class packages.
+- `entrypoint` contract is a bare symbol name, not `module:name`.
+- Add/standardize `arnold pipelines describe <name>`.
+- Keep `megaplan run <name> --describe` only as a thin compatibility alias during cleanup, then reduce it to a wrapper around `arnold pipelines describe`.
+- `arnold pipelines new` emits only native-first scaffold. `--driver graph` and deprecated graph scaffold code are deleted.
+
+### 5. Testing contract
+
+- Native traces are the golden source.
+- Graph traces remain only as temporary compatibility baselines where explicitly needed during migration, then collapse into one legacy baseline suite.
+- No test may require `ARNOLD_NATIVE_RUNTIME=1` or force graph runtime as the normal path.
+
+## Execution Order
+
+Order matters. Do not start package-by-package cleanup before the platform contract lands.
+
+### Step 1. Land the platform contract
+
+Files:
+
+- `arnold/pipeline/types.py`
+- `arnold/pipeline/__init__.py`
+- `arnold/pipeline/registry.py`
+- `arnold/pipeline/validator.py`
+- `arnold/pipeline/discovery/manifest.py`
+- `arnold/pipeline/native/__init__.py`
+- `arnold/pipeline/native/compiler.py`
+- `arnold/pipeline/native/runtime.py`
+- `arnold/pipeline/native/routing.py`
+- `arnold/pipeline/native/graph_projection.py`
+- `arnold/pipeline/builder.py`
+- `arnold/pipeline/executor.py`
+- `arnold/pipeline/resume.py`
+- `arnold/pipelines/megaplan/cli/__init__.py`
+
+Actions:
+
+1. Add `Pipeline.native_program: NativeProgram | None` to the structural pipeline type and update all projection/build helpers to populate it.
+2. Stop treating `resource_bundles` as an execution-bundle escape hatch.
+3. Make validator require `driver`, `default_profile`, `supported_modes`, and a native-backed `build_pipeline`.
+4. Delete `MEGAPLAN_M6_MANIFEST_DISCOVERY` logic and the eager `exec_module` discovery branch.
+5. Remove `ARNOLD_NATIVE_RUNTIME` requirement/error posture from native runtime and CLI help.
+6. Move graph-era exports behind `arnold.pipeline.legacy` aliases. Do not delete them yet.
+7. Delete `_MEGAPLAN_NATIVE_STAGE_ORDER` heuristics from `arnold/pipeline/native/routing.py`; canonical Megaplan must carry enough native structure to route itself.
+8. Move CLI pipeline subcommands out of `arnold/pipelines/megaplan/cli/__init__.py` into a dedicated `cli/pipelines.py` module as part of the cleanup.
+
+Exit criteria:
+
+- Registry loads native-backed packages without feature flags.
+- `arnold pipelines check` validates against the new contract.
+- `Pipeline.native_program` is the only sanctioned execution hook on projected pipelines.
+
+### Step 2. Normalize package layout and naming before behavior changes
+
+Files:
+
+- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py`
+- `arnold/pipelines/megaplan/pipelines/select-tournament/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/select-tournament/steps.py`
+- package `__init__.py` files across all migrated packages
+
+Actions:
+
+1. Convert `writing_panel_strict.py` into package form:
+   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/__init__.py`
+   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/pipeline.py`
+   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/steps.py`
+   - optional `_legacy.py`
+2. Rename `arnold/pipelines/megaplan/pipelines/select-tournament/` to `select_tournament/` and update imports, docs, manifests, and tests.
+3. Standardize package internals so each migrated package has `pipeline.py`, `steps.py`, and temporary `_legacy.py` if needed.
+
+Exit criteria:
+
+- No migrated package still uses one-off file layout when package layout is expected.
+- No hyphenated Python package names remain.
+
+### Step 3. Convert all already-close packages to the final contract
+
+Packages:
+
+- `arnold/pipelines/megaplan/pipelines/creative/`
+- `arnold/pipelines/megaplan/pipelines/doc/`
+- `arnold/pipelines/megaplan/pipelines/jokes/`
+- `arnold/pipelines/megaplan/pipelines/live_supervisor/`
+- `arnold/pipelines/megaplan/pipelines/writing_panel_strict/`
+- `arnold/pipelines/megaplan/pipelines/epic_blitz.py` or package if split
+- `arnold/pipelines/megaplan/pipelines/select_tournament/`
+- `arnold/pipelines/folder_audit/`
+- `arnold/pipelines/deliberation/`
+
+Actions for every package:
+
+1. Move native declaration into `pipeline.py`.
+2. Make `build_pipeline(...)` compile the native declaration, project it, attach `native_program`, attach prompt/resource bundles, and return the projected shell.
+3. Set `driver = ("native", "<kind>")`.
+4. Require real bundle objects in `resource_bundles`; remove empty tuples and placeholder strings.
+5. Rename any remaining graph-default builder to `_build_legacy_graph_pipeline()`.
+
+Package-specific requirements:
+
+- `creative`
+  - Delete `_CREATIVE_PROMPT_EXPORTS`.
+  - Remove graph-era docstrings/metadata.
+- `doc`
+  - Preserve fanout behavior, but make tests validate output/trace/describe contract instead of top-level `SubloopStep` shape.
+- `jokes`
+  - Preserve `_JokesNativeAdapter` semantics only if still required for parameter-to-state wiring.
+  - Update generated docs after migration.
+- `live_supervisor`
+  - Remove tests and code paths that force graph runtime.
+- `writing_panel_strict`
+  - Preserve `continue` and `stop` gate semantics exactly under native suspension/resume.
+- `epic_blitz`
+  - Attach a real native program and fix Megaplan runtime context injection so native execution is real, not a graph fallback.
+- `select_tournament`
+  - Replace hardcoded candidate assumptions with argument-driven native state/config wiring.
+- `folder_audit`
+  - Make native adapters work with runtime state injection rather than graph flattening assumptions.
+- `deliberation`
+  - Separate discovery metadata from runtime construction.
+  - Remove `build_pipeline()` overload behavior where no-arg means discovery and args mean graph runtime.
+
+Exit criteria:
+
+- Every package above is native-backed and validator-clean under the final contract.
+- Legacy graph builders are private baselines only.
+
+### Step 4. Migrate `evidence_pack` last among packages, but before purge
+
+Files:
+
+- `arnold/pipelines/evidence_pack/__init__.py`
+- `arnold/pipelines/evidence_pack/pipeline.py` or create it
+- `arnold/pipelines/evidence_pack/steps.py`
+- `arnold/pipelines/evidence_pack/pipelines.py`
+- `arnold/pipelines/evidence_pack/hooks.py`
+- `arnold/pipelines/evidence_pack/resume.py`
+- `arnold/pipelines/_deliberation_example/` consumers
+
+Actions:
+
+1. Create native declaration phases for ingest, validator fanout, reduce, human review, and attestation emission.
+2. Replace package-specific continuation flow with shared native suspension/resume.
+3. Remove `build_continuation_pipeline()` as a public concept.
+4. Replace `EvidencePackHooks` and `resume.py` graph-executor coupling with neutral runtime hooks or delete them outright.
+5. Update any example or downstream code still importing `HumanReviewStep`.
+
+Exit criteria:
+
+- `evidence_pack` runs natively with the same human review lifecycle as the other gated pipelines.
+- No graph-only continuation path remains in the package.
+
+### Step 5. Move still-live Megaplan runtime helpers out of `_pipeline/`
+
+Files to move or replace:
+
+- `arnold/pipelines/megaplan/_pipeline/types.py`
+- `arnold/pipelines/megaplan/_pipeline/registry.py`
+- any schema/step-IO/envelope helpers still under `_pipeline/`
+
+Target homes:
+
+- `arnold/pipelines/megaplan/types.py`
+- `arnold/pipelines/megaplan/registry.py`
+- `arnold/pipelines/megaplan/runtime/`
+- `arnold/pipelines/megaplan/discovery/` or `judge_manifests/` where appropriate
+
+Actions:
+
+1. Move the still-load-bearing non-graph helpers to first-class module homes.
+2. Update all imports to the new homes.
+3. Leave only a tiny temporary `arnold/pipelines/megaplan/_legacy.py` shim for import compatibility if strictly necessary.
+
+Exit criteria:
+
+- `_pipeline/` no longer contains active runtime ownership.
+- Remaining compatibility surface is explicit and small.
+
+### Step 6. Rewrite tests around native truth, then delete obsolete suites
+
+Files and directories:
+
+- `tests/arnold/pipelines/megaplan/parity_harness.py`
+- `tests/arnold/pipeline/native/parity_trace.py`
+- `tests/arnold/pipelines/megaplan/data/native_parity/`
+- `tests/arnold/pipelines/megaplan/test_native_parity_golden_traces.py`
+- `tests/arnold/pipelines/megaplan/test_graph_baseline.py`
+- `tests/arnold/pipelines/megaplan/test_legacy_pipeline_baseline.py`
+- `tests/parity/`
+- `tests/test_pipeline_parity.py`
+- `tests/test_pipeline_planning_parity.py`
+- package-specific pipeline tests called out in Wave 1
+
+Actions:
+
+1. Replace parity harness with a shared native-trace assertion helper.
+2. Rename golden trace storage to `golden_traces/` and regenerate them from native runtime.
+3. Rewrite package tests that assert graph topology details into behavior/trace/describe assertions.
+4. Collapse remaining graph-baseline assertions into one explicit legacy suite.
+5. Remove all env fixtures or helpers that force `ARNOLD_NATIVE_RUNTIME=1` or graph runtime as default.
+
+Exit criteria:
+
+- Native traces are canonical.
+- Only one deliberately-scoped legacy graph baseline suite remains before final purge.
+
+### Step 7. Docs and scaffold cleanup
+
+Files:
+
+- `docs/arnold/package-authoring-contract.md`
+- `docs/arnold/package-contract.md`
+- `docs/arnold/authoring-guide.md`
+- `docs/arnold/creating-a-new-pipeline.md`
+- `docs/arnold/examples/jokes.md`
+- `docs/arnold/examples/select-tournament.md`
+- `scripts/generate_arnold_docs.py`
+- template/scaffold files used by `arnold pipelines new`
+
+Actions:
+
+1. Rewrite docs to describe `build_pipeline()` returning a projected `Pipeline` with required `native_program`.
+2. Document `driver = ("native", "<kind>")` as the only accepted runtime posture.
+3. Regenerate examples and reference docs from native declarations.
+4. Replace template/scaffold output with native-first runnable examples only.
+
+Exit criteria:
+
+- No doc instructs users to opt into native runtime or create graph pipelines.
+
+### Step 8. Final purge
+
+Do this only after all prior exit criteria are met.
+
+## Purge List
+
+Delete outright:
+
+- `arnold/pipelines/megaplan/_pipeline/builder.py`
+- `arnold/pipelines/megaplan/_pipeline/executor.py`
+- `arnold/pipelines/megaplan/_pipeline/patterns.py`
+- `arnold/pipelines/megaplan/_pipeline/pattern_dynamic.py`
+- `arnold/pipelines/megaplan/_pipeline/subloop.py`
+- `arnold/pipelines/megaplan/_pipeline/resume.py`
+- `arnold/pipelines/megaplan/_pipeline/_bridge.py`
+- `arnold/pipelines/megaplan/_pipeline/_forward_m2_m3.py`
+- `arnold/pipelines/megaplan/_pipeline/_BRIDGE_CALLERS.md`
+- `arnold/pipelines/megaplan/_pipeline/runtime.py`
+- `arnold/pipelines/megaplan/operations.py` if import search confirms it is dead
+- `arnold/pipelines/megaplan/prompts/__init__.py`
+- duplicate test `tests/test_execute_merge_creative.py`
+- temporary legacy graph builders in migrated packages (`_legacy.py`) once the final compatibility suite is removed
+- any remaining graph scaffold helper such as `_deprecated_graph_scaffold_module_content()`
+
+Delete feature flags and compatibility env gates:
+
+- `MEGAPLAN_M6_MANIFEST_DISCOVERY`
+- `ARNOLD_NATIVE_RUNTIME`
+- `MEGAPLAN_PIPELINE_AUTO`
+
+Delete old tests/fixtures:
+
+- `tests/parity/`
+- `tests/test_pipeline_parity.py`
+- `tests/test_pipeline_planning_parity.py`
+- graph-generated golden trace fixtures superseded by native `golden_traces/`
+
+After purge, `arnold.pipeline.legacy` may remain briefly only if import search still shows external/internal callers. If no callers remain, remove it in the same wave.
+
+## Test And Docs Cleanup Checklist
+
+- Rewrite tests that assert graph metadata, graph-only drivers, or graph step classes.
+- Remove any tests calling graph builders directly as the primary path.
+- Update topology-hash tests to compare projected shells derived from native declarations.
+- Ensure doc generators inspect native declarations and `build_pipeline()` contract, not graph builder internals.
+- Remove stale SKILL/doc references to graph runtime switches or manifest discovery flags.
+
+## Validation Checklist
+
+The migration is complete only when all of these are true:
+
+1. `arnold pipelines check` passes for every registered package with no feature flags.
+2. `arnold pipelines describe <name>` works for every registered package.
+3. `megaplan run <name> --describe` resolves through the same native-backed contract.
+4. Every runtime package’s `build_pipeline()` returns a projected `Pipeline` shell with a non-null `native_program`.
+5. No package uses placeholder strings or execution objects in `resource_bundles`.
+6. Native execution succeeds for `creative`, `doc`, `jokes`, `live_supervisor`, `writing_panel_strict`, `epic_blitz`, `select_tournament`, `folder_audit`, `deliberation`, `evidence_pack`, and canonical Megaplan.
+7. Human-gated flows suspend and resume through the shared native runtime contract.
+8. Native traces are the canonical golden fixtures.
+9. Import search shows no production callers of deleted `_pipeline/` graph modules.
+10. Import search shows no references to `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, or graph scaffold switches.
+11. Docs and scaffolds describe only native-first authoring.
+
+## Risks
+
+- `evidence_pack` is the highest-risk migration because it combines fanout, reduction, human review, and continuation semantics.
+- `deliberation` is risky because discovery/runtime overload has already blurred the package contract; that split must be corrected cleanly.
+- `doc` and `select_tournament` are risky because parameterized fanout behavior can silently drift even when topology still projects cleanly.
+- `writing_panel_strict` and canonical Megaplan are risky because human-gate semantics must stay exact across suspend/resume.
+- Adding `Pipeline.native_program` is a structural change that touches type definitions, validators, registry, projection, and tests; it must land first or package migrations will fork the contract again.
+
+## Non-Negotiables
+
+- Do not adopt bare `NativeProgram` return values in this wave.
+- Do not keep execution payloads in `resource_bundles`.
+- Do not preserve graph-first package metadata for compatibility.
+- Do not let `_pipeline/` become a permanent compatibility graveyard.
+- Do not start deleting graph modules before registry, package contracts, and tests have all been moved to native truth.

diff --git a/docs/arnold/pipelines/migration-completion-plan-v3.md b/docs/arnold/pipelines/migration-completion-plan-v3.md
new file mode 100644
index 0000000000000000000000000000000000000000..123d830a105811886550143ed3ce70f9ccb88965
--- /dev/null
+++ b/docs/arnold/pipelines/migration-completion-plan-v3.md
@@ -0,0 +1,368 @@
+# Arnold Pipeline Migration Completion Plan V3
+
+## Decision
+
+This migration ends with **native as the only canonical authoring and runtime model**. The repository will not target a dual graph/native equilibrium.
+
+The concrete end-state contract is:
+
+- `build_pipeline(...)` returns a **projected `Pipeline` shell**.
+- That `Pipeline` shell must carry a **required `native_program` field** containing the compiled `NativeProgram`.
+- `resource_bundles` is reserved for prompt/resource bundles only. It must not carry execution bundles or placeholder strings.
+- The returned `Pipeline` exists only for compatibility with registry, topology hashing, manifest/describe UX, and temporary graph-baseline tests during the purge window.
+- Native declarations in `pipeline.py` are the source of truth. Hand-built graph builders are temporary private baselines only.
+- `driver` is standardized to `("native", "<kind>")`. No graph-first strings, no mixed forms.
+- `default_profile` and `supported_modes` are required package metadata. Missing values are validation errors.
+- Native runtime is unconditional. `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, `MEGAPLAN_PIPELINE_AUTO`, and graph scaffold switches are deleted.
+
+This is the final shape because it is the cleanest end-state that is still implementable in one migration wave. Returning a bare `NativeProgram` would force a larger cross-cutting registry/CLI/test contract rewrite than this effort needs. Keeping projected `Pipeline` plus a first-class `native_program` field preserves the stable external surface while making graph projection explicitly secondary.
+
+## Final End-State Contract
+
+### 1. Public API
+
+`arnold.pipeline` becomes native-first:
+
+- Keep/export: `Pipeline`, `PipelineResourceBundle`, `NativeProgram`, `phase`, `pipeline`, `decision`, `parallel`, `native_panel`, `compile_pipeline`, `project_graph`, `run_native_pipeline`.
+- Move graph-era builder/executor entry points to `arnold.pipeline.legacy` and leave only temporary deprecation aliases in `arnold.pipeline.__init__` during the purge window.
+- `run_pipeline()` and `run_pipeline_resume()` stop being promoted as the main execution surface. Native runtime is the canonical execution path.
+
+### 2. Package contract
+
+Every runtime package must converge on this structure:
+
+```text
+arnold/pipelines/<package>/
+├── __init__.py      # metadata + build_pipeline export
+├── pipeline.py      # native declaration only
+├── steps.py         # runtime-agnostic step logic
+├── prompts/         # package-owned prompt assets
+└── _legacy.py       # temporary graph baseline, deleted in final purge
+```
+
+Rules:
+
+- `build_pipeline(...)` lives in `__init__.py` and does only: compile native declaration, project graph, attach `native_program`, attach prompt/resource bundles, return `Pipeline`.
+- `_build_legacy_graph_pipeline()` is the only allowed legacy naming.
+- `writing_panel_strict.py` must become `arnold/pipelines/megaplan/pipelines/writing_panel_strict/`.
+- `select-tournament` must be renamed to `select_tournament`.
+- Centralized Megaplan prompt export registries are deleted. Prompt ownership is per package.
+
+### 3. Human gate and continuation
+
+- One shared primitive wins: `@decision(human_gate=True)`.
+- Add `arnold.pipeline.human_gate` as sugar if needed, but do not keep package-specific human-gate abstractions.
+- `evidence_pack`, `deliberation`, `writing_panel_strict`, and canonical Megaplan must all use the same suspension/resume contract.
+- Continuation is runtime behavior of `run_native_pipeline(..., resume=...)`, not a separate continuation builder.
+
+### 4. Discovery, registry, CLI
+
+- Manifest-first discovery is unconditional.
+- Registry accepts only native-authored packages as first-class packages.
+- `entrypoint` contract is a bare symbol name, not `module:name`.
+- Add/standardize `arnold pipelines describe <name>`.
+- Keep `megaplan run <name> --describe` only as a thin compatibility alias during cleanup, then reduce it to a wrapper around `arnold pipelines describe`.
+- `arnold pipelines new` emits only native-first scaffold. `--driver graph` and deprecated graph scaffold code are deleted.
+
+### 5. Testing contract
+
+- Native traces are the golden source.
+- Graph traces remain only as temporary compatibility baselines where explicitly needed during migration, then collapse into one legacy baseline suite.
+- No test may require `ARNOLD_NATIVE_RUNTIME=1` or force graph runtime as the normal path.
+
+## Execution Order
+
+Order matters. Do not start package-by-package cleanup before the platform contract lands.
+
+### Step 1. Land the platform contract
+
+Files:
+
+- `arnold/pipeline/types.py`
+- `arnold/pipeline/__init__.py`
+- `arnold/pipeline/registry.py`
+- `arnold/pipeline/validator.py`
+- `arnold/pipeline/discovery/manifest.py`
+- `arnold/pipeline/native/__init__.py`
+- `arnold/pipeline/native/compiler.py`
+- `arnold/pipeline/native/runtime.py`
+- `arnold/pipeline/native/routing.py`
+- `arnold/pipeline/native/graph_projection.py`
+- `arnold/pipeline/builder.py`
+- `arnold/pipeline/executor.py`
+- `arnold/pipeline/resume.py`
+- `arnold/pipelines/megaplan/cli/__init__.py`
+
+Actions:
+
+1. Add `Pipeline.native_program: NativeProgram | None` to the structural pipeline type and update all projection/build helpers to populate it.
+2. Stop treating `resource_bundles` as an execution-bundle escape hatch.
+3. Make validator require `driver`, `default_profile`, `supported_modes`, and a native-backed `build_pipeline`.
+4. Delete `MEGAPLAN_M6_MANIFEST_DISCOVERY` logic and the eager `exec_module` discovery branch.
+5. Remove `ARNOLD_NATIVE_RUNTIME` requirement/error posture from native runtime and CLI help.
+6. Move graph-era exports behind `arnold.pipeline.legacy` aliases. Do not delete them yet.
+7. Delete `_MEGAPLAN_NATIVE_STAGE_ORDER` heuristics from `arnold/pipeline/native/routing.py`; canonical Megaplan must carry enough native structure to route itself.
+8. Move CLI pipeline subcommands out of `arnold/pipelines/megaplan/cli/__init__.py` into a dedicated `cli/pipelines.py` module as part of the cleanup.
+
+Exit criteria:
+
+- Registry loads native-backed packages without feature flags.
+- `arnold pipelines check` validates against the new contract.
+- `Pipeline.native_program` is the only sanctioned execution hook on projected pipelines.
+
+### Step 2. Normalize package layout and naming before behavior changes
+
+Files:
+
+- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py`
+- `arnold/pipelines/megaplan/pipelines/select-tournament/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/select-tournament/steps.py`
+- package `__init__.py` files across all migrated packages
+
+Actions:
+
+1. Convert `writing_panel_strict.py` into package form:
+   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/__init__.py`
+   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/pipeline.py`
+   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/steps.py`
+   - optional `_legacy.py`
+2. Rename `arnold/pipelines/megaplan/pipelines/select-tournament/` to `select_tournament/` and update imports, docs, manifests, and tests.
+3. Standardize package internals so each migrated package has `pipeline.py`, `steps.py`, and temporary `_legacy.py` if needed.
+
+Exit criteria:
+
+- No migrated package still uses one-off file layout when package layout is expected.
+- No hyphenated Python package names remain.
+
+### Step 3. Convert all already-close packages to the final contract
+
+Packages:
+
+- `arnold/pipelines/megaplan/pipelines/creative/`
+- `arnold/pipelines/megaplan/pipelines/doc/`
+- `arnold/pipelines/megaplan/pipelines/jokes/`
+- `arnold/pipelines/megaplan/pipelines/live_supervisor/`
+- `arnold/pipelines/megaplan/pipelines/writing_panel_strict/`
+- `arnold/pipelines/megaplan/pipelines/epic_blitz.py` or package if split
+- `arnold/pipelines/megaplan/pipelines/select_tournament/`
+- `arnold/pipelines/folder_audit/`
+- `arnold/pipelines/deliberation/`
+
+Actions for every package:
+
+1. Move native declaration into `pipeline.py`.
+2. Make `build_pipeline(...)` compile the native declaration, project it, attach `native_program`, attach prompt/resource bundles, and return the projected shell.
+3. Set `driver = ("native", "<kind>")`.
+4. Require real bundle objects in `resource_bundles`; remove empty tuples and placeholder strings.
+5. Rename any remaining graph-default builder to `_build_legacy_graph_pipeline()`.
+
+Package-specific requirements:
+
+- `creative`
+  - Delete `_CREATIVE_PROMPT_EXPORTS`.
+  - Remove graph-era docstrings/metadata.
+- `doc`
+  - Preserve fanout behavior, but make tests validate output/trace/describe contract instead of top-level `SubloopStep` shape.
+- `jokes`
+  - Preserve `_JokesNativeAdapter` semantics only if still required for parameter-to-state wiring.
+  - Update generated docs after migration.
+- `live_supervisor`
+  - Remove tests and code paths that force graph runtime.
+- `writing_panel_strict`
+  - Preserve `continue` and `stop` gate semantics exactly under native suspension/resume.
+- `epic_blitz`
+  - Attach a real native program and fix Megaplan runtime context injection so native execution is real, not a graph fallback.
+- `select_tournament`
+  - Replace hardcoded candidate assumptions with argument-driven native state/config wiring.
+- `folder_audit`
+  - Make native adapters work with runtime state injection rather than graph flattening assumptions.
+- `deliberation`
+  - Separate discovery metadata from runtime construction.
+  - Remove `build_pipeline()` overload behavior where no-arg means discovery and args mean graph runtime.
+
+Exit criteria:
+
+- Every package above is native-backed and validator-clean under the final contract.
+- Legacy graph builders are private baselines only.
+
+### Step 4. Migrate `evidence_pack` last among packages, but before purge
+
+Files:
+
+- `arnold/pipelines/evidence_pack/__init__.py`
+- `arnold/pipelines/evidence_pack/pipeline.py` or create it
+- `arnold/pipelines/evidence_pack/steps.py`
+- `arnold/pipelines/evidence_pack/pipelines.py`
+- `arnold/pipelines/evidence_pack/hooks.py`
+- `arnold/pipelines/evidence_pack/resume.py`
+- `arnold/pipelines/_deliberation_example/` consumers
+
+Actions:
+
+1. Create native declaration phases for ingest, validator fanout, reduce, human review, and attestation emission.
+2. Replace package-specific continuation flow with shared native suspension/resume.
+3. Remove `build_continuation_pipeline()` as a public concept.
+4. Replace `EvidencePackHooks` and `resume.py` graph-executor coupling with neutral runtime hooks or delete them outright.
+5. Update any example or downstream code still importing `HumanReviewStep`.
+
+Exit criteria:
+
+- `evidence_pack` runs natively with the same human review lifecycle as the other gated pipelines.
+- No graph-only continuation path remains in the package.
+
+### Step 5. Move still-live Megaplan runtime helpers out of `_pipeline/`
+
+Files to move or replace:
+
+- `arnold/pipelines/megaplan/_pipeline/types.py`
+- `arnold/pipelines/megaplan/_pipeline/registry.py`
+- any schema/step-IO/envelope helpers still under `_pipeline/`
+
+Target homes:
+
+- `arnold/pipelines/megaplan/types.py`
+- `arnold/pipelines/megaplan/registry.py`
+- `arnold/pipelines/megaplan/runtime/`
+- `arnold/pipelines/megaplan/discovery/` or `judge_manifests/` where appropriate
+
+Actions:
+
+1. Move the still-load-bearing non-graph helpers to first-class module homes.
+2. Update all imports to the new homes.
+3. Leave only a tiny temporary `arnold/pipelines/megaplan/_legacy.py` shim for import compatibility if strictly necessary.
+
+Exit criteria:
+
+- `_pipeline/` no longer contains active runtime ownership.
+- Remaining compatibility surface is explicit and small.
+
+### Step 6. Rewrite tests around native truth, then delete obsolete suites
+
+Files and directories:
+
+- `tests/arnold/pipelines/megaplan/parity_harness.py`
+- `tests/arnold/pipeline/native/parity_trace.py`
+- `tests/arnold/pipelines/megaplan/data/native_parity/`
+- `tests/arnold/pipelines/megaplan/test_native_parity_golden_traces.py`
+- `tests/arnold/pipelines/megaplan/test_graph_baseline.py`
+- `tests/arnold/pipelines/megaplan/test_legacy_pipeline_baseline.py`
+- `tests/parity/`
+- `tests/test_pipeline_parity.py`
+- `tests/test_pipeline_planning_parity.py`
+- package-specific pipeline tests called out in Wave 1
+
+Actions:
+
+1. Replace parity harness with a shared native-trace assertion helper.
+2. Rename golden trace storage to `golden_traces/` and regenerate them from native runtime.
+3. Rewrite package tests that assert graph topology details into behavior/trace/describe assertions.
+4. Collapse remaining graph-baseline assertions into one explicit legacy suite.
+5. Remove all env fixtures or helpers that force `ARNOLD_NATIVE_RUNTIME=1` or graph runtime as default.
+
+Exit criteria:
+
+- Native traces are canonical.
+- Only one deliberately-scoped legacy graph baseline suite remains before final purge.
+
+### Step 7. Docs and scaffold cleanup
+
+Files:
+
+- `docs/arnold/package-authoring-contract.md`
+- `docs/arnold/package-contract.md`
+- `docs/arnold/authoring-guide.md`
+- `docs/arnold/creating-a-new-pipeline.md`
+- `docs/arnold/examples/jokes.md`
+- `docs/arnold/examples/select-tournament.md`
+- `scripts/generate_arnold_docs.py`
+- template/scaffold files used by `arnold pipelines new`
+
+Actions:
+
+1. Rewrite docs to describe `build_pipeline()` returning a projected `Pipeline` with required `native_program`.
+2. Document `driver = ("native", "<kind>")` as the only accepted runtime posture.
+3. Regenerate examples and reference docs from native declarations.
+4. Replace template/scaffold output with native-first runnable examples only.
+
+Exit criteria:
+
+- No doc instructs users to opt into native runtime or create graph pipelines.
+
+### Step 8. Final purge
+
+Do this only after all prior exit criteria are met.
+
+## Purge List
+
+Delete outright:
+
+- `arnold/pipelines/megaplan/_pipeline/builder.py`
+- `arnold/pipelines/megaplan/_pipeline/executor.py`
+- `arnold/pipelines/megaplan/_pipeline/patterns.py`
+- `arnold/pipelines/megaplan/_pipeline/pattern_dynamic.py`
+- `arnold/pipelines/megaplan/_pipeline/subloop.py`
+- `arnold/pipelines/megaplan/_pipeline/resume.py`
+- `arnold/pipelines/megaplan/_pipeline/_bridge.py`
+- `arnold/pipelines/megaplan/_pipeline/_forward_m2_m3.py`
+- `arnold/pipelines/megaplan/_pipeline/_BRIDGE_CALLERS.md`
+- `arnold/pipelines/megaplan/_pipeline/runtime.py`
+- `arnold/pipelines/megaplan/operations.py` if import search confirms it is dead
+- `arnold/pipelines/megaplan/prompts/__init__.py`
+- duplicate test `tests/test_execute_merge_creative.py`
+- temporary legacy graph builders in migrated packages (`_legacy.py`) once the final compatibility suite is removed
+- any remaining graph scaffold helper such as `_deprecated_graph_scaffold_module_content()`
+
+Delete feature flags and compatibility env gates:
+
+- `MEGAPLAN_M6_MANIFEST_DISCOVERY`
+- `ARNOLD_NATIVE_RUNTIME`
+- `MEGAPLAN_PIPELINE_AUTO`
+
+Delete old tests/fixtures:
+
+- `tests/parity/`
+- `tests/test_pipeline_parity.py`
+- `tests/test_pipeline_planning_parity.py`
+- graph-generated golden trace fixtures superseded by native `golden_traces/`
+
+After purge, `arnold.pipeline.legacy` may remain briefly only if import search still shows external/internal callers. If no callers remain, remove it in the same wave.
+
+## Test And Docs Cleanup Checklist
+
+- Rewrite tests that assert graph metadata, graph-only drivers, or graph step classes.
+- Remove any tests calling graph builders directly as the primary path.
+- Update topology-hash tests to compare projected shells derived from native declarations.
+- Ensure doc generators inspect native declarations and `build_pipeline()` contract, not graph builder internals.
+- Remove stale SKILL/doc references to graph runtime switches or manifest discovery flags.
+
+## Validation Checklist
+
+The migration is complete only when all of these are true:
+
+1. `arnold pipelines check` passes for every registered package with no feature flags.
+2. `arnold pipelines describe <name>` works for every registered package.
+3. `megaplan run <name> --describe` resolves through the same native-backed contract.
+4. Every runtime package’s `build_pipeline()` returns a projected `Pipeline` shell with a non-null `native_program`.
+5. No package uses placeholder strings or execution objects in `resource_bundles`.
+6. Native execution succeeds for `creative`, `doc`, `jokes`, `live_supervisor`, `writing_panel_strict`, `epic_blitz`, `select_tournament`, `folder_audit`, `deliberation`, `evidence_pack`, and canonical Megaplan.
+7. Human-gated flows suspend and resume through the shared native runtime contract.
+8. Native traces are the canonical golden fixtures.
+9. Import search shows no production callers of deleted `_pipeline/` graph modules.
+10. Import search shows no references to `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, or graph scaffold switches.
+11. Docs and scaffolds describe only native-first authoring.
+
+## Risks
+
+- `evidence_pack` is the highest-risk migration because it combines fanout, reduction, human review, and continuation semantics.
+- `deliberation` is risky because discovery/runtime overload has already blurred the package contract; that split must be corrected cleanly.
+- `doc` and `select_tournament` are risky because parameterized fanout behavior can silently drift even when topology still projects cleanly.
+- `writing_panel_strict` and canonical Megaplan are risky because human-gate semantics must stay exact across suspend/resume.
+- Adding `Pipeline.native_program` is a structural change that touches type definitions, validators, registry, projection, and tests; it must land first or package migrations will fork the contract again.
+
+## Non-Negotiables
+
+- Do not adopt bare `NativeProgram` return values in this wave.
+- Do not keep execution payloads in `resource_bundles`.
+- Do not preserve graph-first package metadata for compatibility.
+- Do not let `_pipeline/` become a permanent compatibility graveyard.
+- Do not start deleting graph modules before registry, package contracts, and tests have all been moved to native truth.

codex
The v3 plan is written. I’m doing one quick pass on the saved document to make sure the file-level steps, purge list, and validation gates are internally consistent and decisive.
exec
/bin/zsh -lc "sed -n '1,280p' docs/arnold/pipelines/migration-completion-plan-v3.md" in /Users/peteromalley/Documents/megaplan
 succeeded in 0ms:
# Arnold Pipeline Migration Completion Plan V3

## Decision

This migration ends with **native as the only canonical authoring and runtime model**. The repository will not target a dual graph/native equilibrium.

The concrete end-state contract is:

- `build_pipeline(...)` returns a **projected `Pipeline` shell**.
- That `Pipeline` shell must carry a **required `native_program` field** containing the compiled `NativeProgram`.
- `resource_bundles` is reserved for prompt/resource bundles only. It must not carry execution bundles or placeholder strings.
- The returned `Pipeline` exists only for compatibility with registry, topology hashing, manifest/describe UX, and temporary graph-baseline tests during the purge window.
- Native declarations in `pipeline.py` are the source of truth. Hand-built graph builders are temporary private baselines only.
- `driver` is standardized to `("native", "<kind>")`. No graph-first strings, no mixed forms.
- `default_profile` and `supported_modes` are required package metadata. Missing values are validation errors.
- Native runtime is unconditional. `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, `MEGAPLAN_PIPELINE_AUTO`, and graph scaffold switches are deleted.

This is the final shape because it is the cleanest end-state that is still implementable in one migration wave. Returning a bare `NativeProgram` would force a larger cross-cutting registry/CLI/test contract rewrite than this effort needs. Keeping projected `Pipeline` plus a first-class `native_program` field preserves the stable external surface while making graph projection explicitly secondary.

## Final End-State Contract

### 1. Public API

`arnold.pipeline` becomes native-first:

- Keep/export: `Pipeline`, `PipelineResourceBundle`, `NativeProgram`, `phase`, `pipeline`, `decision`, `parallel`, `native_panel`, `compile_pipeline`, `project_graph`, `run_native_pipeline`.
- Move graph-era builder/executor entry points to `arnold.pipeline.legacy` and leave only temporary deprecation aliases in `arnold.pipeline.__init__` during the purge window.
- `run_pipeline()` and `run_pipeline_resume()` stop being promoted as the main execution surface. Native runtime is the canonical execution path.

### 2. Package contract

Every runtime package must converge on this structure:

```text
arnold/pipelines/<package>/
├── __init__.py      # metadata + build_pipeline export
├── pipeline.py      # native declaration only
├── steps.py         # runtime-agnostic step logic
├── prompts/         # package-owned prompt assets
└── _legacy.py       # temporary graph baseline, deleted in final purge
```

Rules:

- `build_pipeline(...)` lives in `__init__.py` and does only: compile native declaration, project graph, attach `native_program`, attach prompt/resource bundles, return `Pipeline`.
- `_build_legacy_graph_pipeline()` is the only allowed legacy naming.
- `writing_panel_strict.py` must become `arnold/pipelines/megaplan/pipelines/writing_panel_strict/`.
- `select-tournament` must be renamed to `select_tournament`.
- Centralized Megaplan prompt export registries are deleted. Prompt ownership is per package.

### 3. Human gate and continuation

- One shared primitive wins: `@decision(human_gate=True)`.
- Add `arnold.pipeline.human_gate` as sugar if needed, but do not keep package-specific human-gate abstractions.
- `evidence_pack`, `deliberation`, `writing_panel_strict`, and canonical Megaplan must all use the same suspension/resume contract.
- Continuation is runtime behavior of `run_native_pipeline(..., resume=...)`, not a separate continuation builder.

### 4. Discovery, registry, CLI

- Manifest-first discovery is unconditional.
- Registry accepts only native-authored packages as first-class packages.
- `entrypoint` contract is a bare symbol name, not `module:name`.
- Add/standardize `arnold pipelines describe <name>`.
- Keep `megaplan run <name> --describe` only as a thin compatibility alias during cleanup, then reduce it to a wrapper around `arnold pipelines describe`.
- `arnold pipelines new` emits only native-first scaffold. `--driver graph` and deprecated graph scaffold code are deleted.

### 5. Testing contract

- Native traces are the golden source.
- Graph traces remain only as temporary compatibility baselines where explicitly needed during migration, then collapse into one legacy baseline suite.
- No test may require `ARNOLD_NATIVE_RUNTIME=1` or force graph runtime as the normal path.

## Execution Order

Order matters. Do not start package-by-package cleanup before the platform contract lands.

### Step 1. Land the platform contract

Files:

- `arnold/pipeline/types.py`
- `arnold/pipeline/__init__.py`
- `arnold/pipeline/registry.py`
- `arnold/pipeline/validator.py`
- `arnold/pipeline/discovery/manifest.py`
- `arnold/pipeline/native/__init__.py`
- `arnold/pipeline/native/compiler.py`
- `arnold/pipeline/native/runtime.py`
- `arnold/pipeline/native/routing.py`
- `arnold/pipeline/native/graph_projection.py`
- `arnold/pipeline/builder.py`
- `arnold/pipeline/executor.py`
- `arnold/pipeline/resume.py`
- `arnold/pipelines/megaplan/cli/__init__.py`

Actions:

1. Add `Pipeline.native_program: NativeProgram | None` to the structural pipeline type and update all projection/build helpers to populate it.
2. Stop treating `resource_bundles` as an execution-bundle escape hatch.
3. Make validator require `driver`, `default_profile`, `supported_modes`, and a native-backed `build_pipeline`.
4. Delete `MEGAPLAN_M6_MANIFEST_DISCOVERY` logic and the eager `exec_module` discovery branch.
5. Remove `ARNOLD_NATIVE_RUNTIME` requirement/error posture from native runtime and CLI help.
6. Move graph-era exports behind `arnold.pipeline.legacy` aliases. Do not delete them yet.
7. Delete `_MEGAPLAN_NATIVE_STAGE_ORDER` heuristics from `arnold/pipeline/native/routing.py`; canonical Megaplan must carry enough native structure to route itself.
8. Move CLI pipeline subcommands out of `arnold/pipelines/megaplan/cli/__init__.py` into a dedicated `cli/pipelines.py` module as part of the cleanup.

Exit criteria:

- Registry loads native-backed packages without feature flags.
- `arnold pipelines check` validates against the new contract.
- `Pipeline.native_program` is the only sanctioned execution hook on projected pipelines.

### Step 2. Normalize package layout and naming before behavior changes

Files:

- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py`
- `arnold/pipelines/megaplan/pipelines/select-tournament/__init__.py`
- `arnold/pipelines/megaplan/pipelines/select-tournament/steps.py`
- package `__init__.py` files across all migrated packages

Actions:

1. Convert `writing_panel_strict.py` into package form:
   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/__init__.py`
   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/pipeline.py`
   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/steps.py`
   - optional `_legacy.py`
2. Rename `arnold/pipelines/megaplan/pipelines/select-tournament/` to `select_tournament/` and update imports, docs, manifests, and tests.
3. Standardize package internals so each migrated package has `pipeline.py`, `steps.py`, and temporary `_legacy.py` if needed.

Exit criteria:

- No migrated package still uses one-off file layout when package layout is expected.
- No hyphenated Python package names remain.

### Step 3. Convert all already-close packages to the final contract

Packages:

- `arnold/pipelines/megaplan/pipelines/creative/`
- `arnold/pipelines/megaplan/pipelines/doc/`
- `arnold/pipelines/megaplan/pipelines/jokes/`
- `arnold/pipelines/megaplan/pipelines/live_supervisor/`
- `arnold/pipelines/megaplan/pipelines/writing_panel_strict/`
- `arnold/pipelines/megaplan/pipelines/epic_blitz.py` or package if split
- `arnold/pipelines/megaplan/pipelines/select_tournament/`
- `arnold/pipelines/folder_audit/`
- `arnold/pipelines/deliberation/`

Actions for every package:

1. Move native declaration into `pipeline.py`.
2. Make `build_pipeline(...)` compile the native declaration, project it, attach `native_program`, attach prompt/resource bundles, and return the projected shell.
3. Set `driver = ("native", "<kind>")`.
4. Require real bundle objects in `resource_bundles`; remove empty tuples and placeholder strings.
5. Rename any remaining graph-default builder to `_build_legacy_graph_pipeline()`.

Package-specific requirements:

- `creative`
  - Delete `_CREATIVE_PROMPT_EXPORTS`.
  - Remove graph-era docstrings/metadata.
- `doc`
  - Preserve fanout behavior, but make tests validate output/trace/describe contract instead of top-level `SubloopStep` shape.
- `jokes`
  - Preserve `_JokesNativeAdapter` semantics only if still required for parameter-to-state wiring.
  - Update generated docs after migration.
- `live_supervisor`
  - Remove tests and code paths that force graph runtime.
- `writing_panel_strict`
  - Preserve `continue` and `stop` gate semantics exactly under native suspension/resume.
- `epic_blitz`
  - Attach a real native program and fix Megaplan runtime context injection so native execution is real, not a graph fallback.
- `select_tournament`
  - Replace hardcoded candidate assumptions with argument-driven native state/config wiring.
- `folder_audit`
  - Make native adapters work with runtime state injection rather than graph flattening assumptions.
- `deliberation`
  - Separate discovery metadata from runtime construction.
  - Remove `build_pipeline()` overload behavior where no-arg means discovery and args mean graph runtime.

Exit criteria:

- Every package above is native-backed and validator-clean under the final contract.
- Legacy graph builders are private baselines only.

### Step 4. Migrate `evidence_pack` last among packages, but before purge

Files:

- `arnold/pipelines/evidence_pack/__init__.py`
- `arnold/pipelines/evidence_pack/pipeline.py` or create it
- `arnold/pipelines/evidence_pack/steps.py`
- `arnold/pipelines/evidence_pack/pipelines.py`
- `arnold/pipelines/evidence_pack/hooks.py`
- `arnold/pipelines/evidence_pack/resume.py`
- `arnold/pipelines/_deliberation_example/` consumers

Actions:

1. Create native declaration phases for ingest, validator fanout, reduce, human review, and attestation emission.
2. Replace package-specific continuation flow with shared native suspension/resume.
3. Remove `build_continuation_pipeline()` as a public concept.
4. Replace `EvidencePackHooks` and `resume.py` graph-executor coupling with neutral runtime hooks or delete them outright.
5. Update any example or downstream code still importing `HumanReviewStep`.

Exit criteria:

- `evidence_pack` runs natively with the same human review lifecycle as the other gated pipelines.
- No graph-only continuation path remains in the package.

### Step 5. Move still-live Megaplan runtime helpers out of `_pipeline/`

Files to move or replace:

- `arnold/pipelines/megaplan/_pipeline/types.py`
- `arnold/pipelines/megaplan/_pipeline/registry.py`
- any schema/step-IO/envelope helpers still under `_pipeline/`

Target homes:

- `arnold/pipelines/megaplan/types.py`
- `arnold/pipelines/megaplan/registry.py`
- `arnold/pipelines/megaplan/runtime/`
- `arnold/pipelines/megaplan/discovery/` or `judge_manifests/` where appropriate

Actions:

1. Move the still-load-bearing non-graph helpers to first-class module homes.
2. Update all imports to the new homes.
3. Leave only a tiny temporary `arnold/pipelines/megaplan/_legacy.py` shim for import compatibility if strictly necessary.

Exit criteria:

- `_pipeline/` no longer contains active runtime ownership.
- Remaining compatibility surface is explicit and small.

### Step 6. Rewrite tests around native truth, then delete obsolete suites

Files and directories:

- `tests/arnold/pipelines/megaplan/parity_harness.py`
- `tests/arnold/pipeline/native/parity_trace.py`
- `tests/arnold/pipelines/megaplan/data/native_parity/`
- `tests/arnold/pipelines/megaplan/test_native_parity_golden_traces.py`
- `tests/arnold/pipelines/megaplan/test_graph_baseline.py`
- `tests/arnold/pipelines/megaplan/test_legacy_pipeline_baseline.py`
- `tests/parity/`
- `tests/test_pipeline_parity.py`
- `tests/test_pipeline_planning_parity.py`
- package-specific pipeline tests called out in Wave 1

Actions:

1. Replace parity harness with a shared native-trace assertion helper.
2. Rename golden trace storage to `golden_traces/` and regenerate them from native runtime.
3. Rewrite package tests that assert graph topology details into behavior/trace/describe assertions.
4. Collapse remaining graph-baseline assertions into one explicit legacy suite.
5. Remove all env fixtures or helpers that force `ARNOLD_NATIVE_RUNTIME=1` or graph runtime as default.

Exit criteria:

- Native traces are canonical.
- Only one deliberately-scoped legacy graph baseline suite remains before final purge.

### Step 7. Docs and scaffold cleanup

Files:

- `docs/arnold/package-authoring-contract.md`
- `docs/arnold/package-contract.md`
- `docs/arnold/authoring-guide.md`
- `docs/arnold/creating-a-new-pipeline.md`
- `docs/arnold/examples/jokes.md`
- `docs/arnold/examples/select-tournament.md`
- `scripts/generate_arnold_docs.py`
- template/scaffold files used by `arnold pipelines new`

Actions:

diff --git a/docs/arnold/pipelines/migration-completion-plan-v3.md b/docs/arnold/pipelines/migration-completion-plan-v3.md
new file mode 100644
index 0000000000000000000000000000000000000000..123d830a105811886550143ed3ce70f9ccb88965
--- /dev/null
+++ b/docs/arnold/pipelines/migration-completion-plan-v3.md
@@ -0,0 +1,368 @@
+# Arnold Pipeline Migration Completion Plan V3
+
+## Decision
+
+This migration ends with **native as the only canonical authoring and runtime model**. The repository will not target a dual graph/native equilibrium.
+
+The concrete end-state contract is:
+
+- `build_pipeline(...)` returns a **projected `Pipeline` shell**.
+- That `Pipeline` shell must carry a **required `native_program` field** containing the compiled `NativeProgram`.
+- `resource_bundles` is reserved for prompt/resource bundles only. It must not carry execution bundles or placeholder strings.
+- The returned `Pipeline` exists only for compatibility with registry, topology hashing, manifest/describe UX, and temporary graph-baseline tests during the purge window.
+- Native declarations in `pipeline.py` are the source of truth. Hand-built graph builders are temporary private baselines only.
+- `driver` is standardized to `("native", "<kind>")`. No graph-first strings, no mixed forms.
+- `default_profile` and `supported_modes` are required package metadata. Missing values are validation errors.
+- Native runtime is unconditional. `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, `MEGAPLAN_PIPELINE_AUTO`, and graph scaffold switches are deleted.
+
+This is the final shape because it is the cleanest end-state that is still implementable in one migration wave. Returning a bare `NativeProgram` would force a larger cross-cutting registry/CLI/test contract rewrite than this effort needs. Keeping projected `Pipeline` plus a first-class `native_program` field preserves the stable external surface while making graph projection explicitly secondary.
+
+## Final End-State Contract
+
+### 1. Public API
+
+`arnold.pipeline` becomes native-first:
+
+- Keep/export: `Pipeline`, `PipelineResourceBundle`, `NativeProgram`, `phase`, `pipeline`, `decision`, `parallel`, `native_panel`, `compile_pipeline`, `project_graph`, `run_native_pipeline`.
+- Move graph-era builder/executor entry points to `arnold.pipeline.legacy` and leave only temporary deprecation aliases in `arnold.pipeline.__init__` during the purge window.
+- `run_pipeline()` and `run_pipeline_resume()` stop being promoted as the main execution surface. Native runtime is the canonical execution path.
+
+### 2. Package contract
+
+Every runtime package must converge on this structure:
+
+```text
+arnold/pipelines/<package>/
+├── __init__.py      # metadata + build_pipeline export
+├── pipeline.py      # native declaration only
+├── steps.py         # runtime-agnostic step logic
+├── prompts/         # package-owned prompt assets
+└── _legacy.py       # temporary graph baseline, deleted in final purge
+```
+
+Rules:
+
+- `build_pipeline(...)` lives in `__init__.py` and does only: compile native declaration, project graph, attach `native_program`, attach prompt/resource bundles, return `Pipeline`.
+- `_build_legacy_graph_pipeline()` is the only allowed legacy naming.
+- `writing_panel_strict.py` must become `arnold/pipelines/megaplan/pipelines/writing_panel_strict/`.
+- `select-tournament` must be renamed to `select_tournament`.
+- Centralized Megaplan prompt export registries are deleted. Prompt ownership is per package.
+
+### 3. Human gate and continuation
+
+- One shared primitive wins: `@decision(human_gate=True)`.
+- Add `arnold.pipeline.human_gate` as sugar if needed, but do not keep package-specific human-gate abstractions.
+- `evidence_pack`, `deliberation`, `writing_panel_strict`, and canonical Megaplan must all use the same suspension/resume contract.
+- Continuation is runtime behavior of `run_native_pipeline(..., resume=...)`, not a separate continuation builder.
+
+### 4. Discovery, registry, CLI
+
+- Manifest-first discovery is unconditional.
+- Registry accepts only native-authored packages as first-class packages.
+- `entrypoint` contract is a bare symbol name, not `module:name`.
+- Add/standardize `arnold pipelines describe <name>`.
+- Keep `megaplan run <name> --describe` only as a thin compatibility alias during cleanup, then reduce it to a wrapper around `arnold pipelines describe`.
+- `arnold pipelines new` emits only native-first scaffold. `--driver graph` and deprecated graph scaffold code are deleted.
+
+### 5. Testing contract
+
+- Native traces are the golden source.
+- Graph traces remain only as temporary compatibility baselines where explicitly needed during migration, then collapse into one legacy baseline suite.
+- No test may require `ARNOLD_NATIVE_RUNTIME=1` or force graph runtime as the normal path.
+
+## Execution Order
+
+Order matters. Do not start package-by-package cleanup before the platform contract lands.
+
+### Step 1. Land the platform contract
+
+Files:
+
+- `arnold/pipeline/types.py`
+- `arnold/pipeline/__init__.py`
+- `arnold/pipeline/registry.py`
+- `arnold/pipeline/validator.py`
+- `arnold/pipeline/discovery/manifest.py`
+- `arnold/pipeline/native/__init__.py`
+- `arnold/pipeline/native/compiler.py`
+- `arnold/pipeline/native/runtime.py`
+- `arnold/pipeline/native/routing.py`
+- `arnold/pipeline/native/graph_projection.py`
+- `arnold/pipeline/builder.py`
+- `arnold/pipeline/executor.py`
+- `arnold/pipeline/resume.py`
+- `arnold/pipelines/megaplan/cli/__init__.py`
+
+Actions:
+
+1. Add `Pipeline.native_program: NativeProgram | None` to the structural pipeline type and update all projection/build helpers to populate it.
+2. Stop treating `resource_bundles` as an execution-bundle escape hatch.
+3. Make validator require `driver`, `default_profile`, `supported_modes`, and a native-backed `build_pipeline`.
+4. Delete `MEGAPLAN_M6_MANIFEST_DISCOVERY` logic and the eager `exec_module` discovery branch.
+5. Remove `ARNOLD_NATIVE_RUNTIME` requirement/error posture from native runtime and CLI help.
+6. Move graph-era exports behind `arnold.pipeline.legacy` aliases. Do not delete them yet.
+7. Delete `_MEGAPLAN_NATIVE_STAGE_ORDER` heuristics from `arnold/pipeline/native/routing.py`; canonical Megaplan must carry enough native structure to route itself.
+8. Move CLI pipeline subcommands out of `arnold/pipelines/megaplan/cli/__init__.py` into a dedicated `cli/pipelines.py` module as part of the cleanup.
+
+Exit criteria:
+
+- Registry loads native-backed packages without feature flags.
+- `arnold pipelines check` validates against the new contract.
+- `Pipeline.native_program` is the only sanctioned execution hook on projected pipelines.
+
+### Step 2. Normalize package layout and naming before behavior changes
+
+Files:
+
+- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py`
+- `arnold/pipelines/megaplan/pipelines/select-tournament/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/select-tournament/steps.py`
+- package `__init__.py` files across all migrated packages
+
+Actions:
+
+1. Convert `writing_panel_strict.py` into package form:
+   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/__init__.py`
+   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/pipeline.py`
+   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/steps.py`
+   - optional `_legacy.py`
+2. Rename `arnold/pipelines/megaplan/pipelines/select-tournament/` to `select_tournament/` and update imports, docs, manifests, and tests.
+3. Standardize package internals so each migrated package has `pipeline.py`, `steps.py`, and temporary `_legacy.py` if needed.
+
+Exit criteria:
+
+- No migrated package still uses one-off file layout when package layout is expected.
+- No hyphenated Python package names remain.
+
+### Step 3. Convert all already-close packages to the final contract
+
+Packages:
+
+- `arnold/pipelines/megaplan/pipelines/creative/`
+- `arnold/pipelines/megaplan/pipelines/doc/`
+- `arnold/pipelines/megaplan/pipelines/jokes/`
+- `arnold/pipelines/megaplan/pipelines/live_supervisor/`
+- `arnold/pipelines/megaplan/pipelines/writing_panel_strict/`
+- `arnold/pipelines/megaplan/pipelines/epic_blitz.py` or package if split
+- `arnold/pipelines/megaplan/pipelines/select_tournament/`
+- `arnold/pipelines/folder_audit/`
+- `arnold/pipelines/deliberation/`
+
+Actions for every package:
+
+1. Move native declaration into `pipeline.py`.
+2. Make `build_pipeline(...)` compile the native declaration, project it, attach `native_program`, attach prompt/resource bundles, and return the projected shell.
+3. Set `driver = ("native", "<kind>")`.
+4. Require real bundle objects in `resource_bundles`; remove empty tuples and placeholder strings.
+5. Rename any remaining graph-default builder to `_build_legacy_graph_pipeline()`.
+
+Package-specific requirements:
+
+- `creative`
+  - Delete `_CREATIVE_PROMPT_EXPORTS`.
+  - Remove graph-era docstrings/metadata.
+- `doc`
+  - Preserve fanout behavior, but make tests validate output/trace/describe contract instead of top-level `SubloopStep` shape.
+- `jokes`
+  - Preserve `_JokesNativeAdapter` semantics only if still required for parameter-to-state wiring.
+  - Update generated docs after migration.
+- `live_supervisor`
+  - Remove tests and code paths that force graph runtime.
+- `writing_panel_strict`
+  - Preserve `continue` and `stop` gate semantics exactly under native suspension/resume.
+- `epic_blitz`
+  - Attach a real native program and fix Megaplan runtime context injection so native execution is real, not a graph fallback.
+- `select_tournament`
+  - Replace hardcoded candidate assumptions with argument-driven native state/config wiring.
+- `folder_audit`
+  - Make native adapters work with runtime state injection rather than graph flattening assumptions.
+- `deliberation`
+  - Separate discovery metadata from runtime construction.
+  - Remove `build_pipeline()` overload behavior where no-arg means discovery and args mean graph runtime.
+
+Exit criteria:
+
+- Every package above is native-backed and validator-clean under the final contract.
+- Legacy graph builders are private baselines only.
+
+### Step 4. Migrate `evidence_pack` last among packages, but before purge
+
+Files:
+
+- `arnold/pipelines/evidence_pack/__init__.py`
+- `arnold/pipelines/evidence_pack/pipeline.py` or create it
+- `arnold/pipelines/evidence_pack/steps.py`
+- `arnold/pipelines/evidence_pack/pipelines.py`
+- `arnold/pipelines/evidence_pack/hooks.py`
+- `arnold/pipelines/evidence_pack/resume.py`
+- `arnold/pipelines/_deliberation_example/` consumers
+
+Actions:
+
+1. Create native declaration phases for ingest, validator fanout, reduce, human review, and attestation emission.
+2. Replace package-specific continuation flow with shared native suspension/resume.
+3. Remove `build_continuation_pipeline()` as a public concept.
+4. Replace `EvidencePackHooks` and `resume.py` graph-executor coupling with neutral runtime hooks or delete them outright.
+5. Update any example or downstream code still importing `HumanReviewStep`.
+
+Exit criteria:
+
+- `evidence_pack` runs natively with the same human review lifecycle as the other gated pipelines.
+- No graph-only continuation path remains in the package.
+
+### Step 5. Move still-live Megaplan runtime helpers out of `_pipeline/`
+
+Files to move or replace:
+
+- `arnold/pipelines/megaplan/_pipeline/types.py`
+- `arnold/pipelines/megaplan/_pipeline/registry.py`
+- any schema/step-IO/envelope helpers still under `_pipeline/`
+
+Target homes:
+
+- `arnold/pipelines/megaplan/types.py`
+- `arnold/pipelines/megaplan/registry.py`
+- `arnold/pipelines/megaplan/runtime/`
+- `arnold/pipelines/megaplan/discovery/` or `judge_manifests/` where appropriate
+
+Actions:
+
+1. Move the still-load-bearing non-graph helpers to first-class module homes.
+2. Update all imports to the new homes.
+3. Leave only a tiny temporary `arnold/pipelines/megaplan/_legacy.py` shim for import compatibility if strictly necessary.
+
+Exit criteria:
+
+- `_pipeline/` no longer contains active runtime ownership.
+- Remaining compatibility surface is explicit and small.
+
+### Step 6. Rewrite tests around native truth, then delete obsolete suites
+
+Files and directories:
+
+- `tests/arnold/pipelines/megaplan/parity_harness.py`
+- `tests/arnold/pipeline/native/parity_trace.py`
+- `tests/arnold/pipelines/megaplan/data/native_parity/`
+- `tests/arnold/pipelines/megaplan/test_native_parity_golden_traces.py`
+- `tests/arnold/pipelines/megaplan/test_graph_baseline.py`
+- `tests/arnold/pipelines/megaplan/test_legacy_pipeline_baseline.py`
+- `tests/parity/`
+- `tests/test_pipeline_parity.py`
+- `tests/test_pipeline_planning_parity.py`
+- package-specific pipeline tests called out in Wave 1
+
+Actions:
+
+1. Replace parity harness with a shared native-trace assertion helper.
+2. Rename golden trace storage to `golden_traces/` and regenerate them from native runtime.
+3. Rewrite package tests that assert graph topology details into behavior/trace/describe assertions.
+4. Collapse remaining graph-baseline assertions into one explicit legacy suite.
+5. Remove all env fixtures or helpers that force `ARNOLD_NATIVE_RUNTIME=1` or graph runtime as default.
+
+Exit criteria:
+
+- Native traces are canonical.
+- Only one deliberately-scoped legacy graph baseline suite remains before final purge.
+
+### Step 7. Docs and scaffold cleanup
+
+Files:
+
+- `docs/arnold/package-authoring-contract.md`
+- `docs/arnold/package-contract.md`
+- `docs/arnold/authoring-guide.md`
+- `docs/arnold/creating-a-new-pipeline.md`
+- `docs/arnold/examples/jokes.md`
+- `docs/arnold/examples/select-tournament.md`
+- `scripts/generate_arnold_docs.py`
+- template/scaffold files used by `arnold pipelines new`
+
+Actions:
+
+1. Rewrite docs to describe `build_pipeline()` returning a projected `Pipeline` with required `native_program`.
+2. Document `driver = ("native", "<kind>")` as the only accepted runtime posture.
+3. Regenerate examples and reference docs from native declarations.
+4. Replace template/scaffold output with native-first runnable examples only.
+
+Exit criteria:
+
+- No doc instructs users to opt into native runtime or create graph pipelines.
+
+### Step 8. Final purge
+
+Do this only after all prior exit criteria are met.
+
+## Purge List
+
+Delete outright:
+
+- `arnold/pipelines/megaplan/_pipeline/builder.py`
+- `arnold/pipelines/megaplan/_pipeline/executor.py`
+- `arnold/pipelines/megaplan/_pipeline/patterns.py`
+- `arnold/pipelines/megaplan/_pipeline/pattern_dynamic.py`
+- `arnold/pipelines/megaplan/_pipeline/subloop.py`
+- `arnold/pipelines/megaplan/_pipeline/resume.py`
+- `arnold/pipelines/megaplan/_pipeline/_bridge.py`
+- `arnold/pipelines/megaplan/_pipeline/_forward_m2_m3.py`
+- `arnold/pipelines/megaplan/_pipeline/_BRIDGE_CALLERS.md`
+- `arnold/pipelines/megaplan/_pipeline/runtime.py`
+- `arnold/pipelines/megaplan/operations.py` if import search confirms it is dead
+- `arnold/pipelines/megaplan/prompts/__init__.py`
+- duplicate test `tests/test_execute_merge_creative.py`
+- temporary legacy graph builders in migrated packages (`_legacy.py`) once the final compatibility suite is removed
+- any remaining graph scaffold helper such as `_deprecated_graph_scaffold_module_content()`
+
+Delete feature flags and compatibility env gates:
+
+- `MEGAPLAN_M6_MANIFEST_DISCOVERY`
+- `ARNOLD_NATIVE_RUNTIME`
+- `MEGAPLAN_PIPELINE_AUTO`
+
+Delete old tests/fixtures:
+
+- `tests/parity/`
+- `tests/test_pipeline_parity.py`
+- `tests/test_pipeline_planning_parity.py`
+- graph-generated golden trace fixtures superseded by native `golden_traces/`
+
+After purge, `arnold.pipeline.legacy` may remain briefly only if import search still shows external/internal callers. If no callers remain, remove it in the same wave.
+
+## Test And Docs Cleanup Checklist
+
+- Rewrite tests that assert graph metadata, graph-only drivers, or graph step classes.
+- Remove any tests calling graph builders directly as the primary path.
+- Update topology-hash tests to compare projected shells derived from native declarations.
+- Ensure doc generators inspect native declarations and `build_pipeline()` contract, not graph builder internals.
+- Remove stale SKILL/doc references to graph runtime switches or manifest discovery flags.
+
+## Validation Checklist
+
+The migration is complete only when all of these are true:
+
+1. `arnold pipelines check` passes for every registered package with no feature flags.
+2. `arnold pipelines describe <name>` works for every registered package.
+3. `megaplan run <name> --describe` resolves through the same native-backed contract.
+4. Every runtime package’s `build_pipeline()` returns a projected `Pipeline` shell with a non-null `native_program`.
+5. No package uses placeholder strings or execution objects in `resource_bundles`.
+6. Native execution succeeds for `creative`, `doc`, `jokes`, `live_supervisor`, `writing_panel_strict`, `epic_blitz`, `select_tournament`, `folder_audit`, `deliberation`, `evidence_pack`, and canonical Megaplan.
+7. Human-gated flows suspend and resume through the shared native runtime contract.
+8. Native traces are the canonical golden fixtures.
+9. Import search shows no production callers of deleted `_pipeline/` graph modules.
+10. Import search shows no references to `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, or graph scaffold switches.
+11. Docs and scaffolds describe only native-first authoring.
+
+## Risks
+
+- `evidence_pack` is the highest-risk migration because it combines fanout, reduction, human review, and continuation semantics.
+- `deliberation` is risky because discovery/runtime overload has already blurred the package contract; that split must be corrected cleanly.
+- `doc` and `select_tournament` are risky because parameterized fanout behavior can silently drift even when topology still projects cleanly.
+- `writing_panel_strict` and canonical Megaplan are risky because human-gate semantics must stay exact across suspend/resume.
+- Adding `Pipeline.native_program` is a structural change that touches type definitions, validators, registry, projection, and tests; it must land first or package migrations will fork the contract again.
+
+## Non-Negotiables
+
+- Do not adopt bare `NativeProgram` return values in this wave.
+- Do not keep execution payloads in `resource_bundles`.
+- Do not preserve graph-first package metadata for compatibility.
+- Do not let `_pipeline/` become a permanent compatibility graveyard.
+- Do not start deleting graph modules before registry, package contracts, and tests have all been moved to native truth.

exec
/bin/zsh -lc "sed -n '281,520p' docs/arnold/pipelines/migration-completion-plan-v3.md" in /Users/peteromalley/Documents/megaplan
 succeeded in 0ms:

1. Rewrite docs to describe `build_pipeline()` returning a projected `Pipeline` with required `native_program`.
2. Document `driver = ("native", "<kind>")` as the only accepted runtime posture.
3. Regenerate examples and reference docs from native declarations.
4. Replace template/scaffold output with native-first runnable examples only.

Exit criteria:

- No doc instructs users to opt into native runtime or create graph pipelines.

### Step 8. Final purge

Do this only after all prior exit criteria are met.

## Purge List

Delete outright:

- `arnold/pipelines/megaplan/_pipeline/builder.py`
- `arnold/pipelines/megaplan/_pipeline/executor.py`
- `arnold/pipelines/megaplan/_pipeline/patterns.py`
- `arnold/pipelines/megaplan/_pipeline/pattern_dynamic.py`
- `arnold/pipelines/megaplan/_pipeline/subloop.py`
- `arnold/pipelines/megaplan/_pipeline/resume.py`
- `arnold/pipelines/megaplan/_pipeline/_bridge.py`
- `arnold/pipelines/megaplan/_pipeline/_forward_m2_m3.py`
- `arnold/pipelines/megaplan/_pipeline/_BRIDGE_CALLERS.md`
- `arnold/pipelines/megaplan/_pipeline/runtime.py`
- `arnold/pipelines/megaplan/operations.py` if import search confirms it is dead
- `arnold/pipelines/megaplan/prompts/__init__.py`
- duplicate test `tests/test_execute_merge_creative.py`
- temporary legacy graph builders in migrated packages (`_legacy.py`) once the final compatibility suite is removed
- any remaining graph scaffold helper such as `_deprecated_graph_scaffold_module_content()`

Delete feature flags and compatibility env gates:

- `MEGAPLAN_M6_MANIFEST_DISCOVERY`
- `ARNOLD_NATIVE_RUNTIME`
- `MEGAPLAN_PIPELINE_AUTO`

Delete old tests/fixtures:

- `tests/parity/`
- `tests/test_pipeline_parity.py`
- `tests/test_pipeline_planning_parity.py`
- graph-generated golden trace fixtures superseded by native `golden_traces/`

After purge, `arnold.pipeline.legacy` may remain briefly only if import search still shows external/internal callers. If no callers remain, remove it in the same wave.

## Test And Docs Cleanup Checklist

- Rewrite tests that assert graph metadata, graph-only drivers, or graph step classes.
- Remove any tests calling graph builders directly as the primary path.
- Update topology-hash tests to compare projected shells derived from native declarations.
- Ensure doc generators inspect native declarations and `build_pipeline()` contract, not graph builder internals.
- Remove stale SKILL/doc references to graph runtime switches or manifest discovery flags.

## Validation Checklist

The migration is complete only when all of these are true:

1. `arnold pipelines check` passes for every registered package with no feature flags.
2. `arnold pipelines describe <name>` works for every registered package.
3. `megaplan run <name> --describe` resolves through the same native-backed contract.
4. Every runtime package’s `build_pipeline()` returns a projected `Pipeline` shell with a non-null `native_program`.
5. No package uses placeholder strings or execution objects in `resource_bundles`.
6. Native execution succeeds for `creative`, `doc`, `jokes`, `live_supervisor`, `writing_panel_strict`, `epic_blitz`, `select_tournament`, `folder_audit`, `deliberation`, `evidence_pack`, and canonical Megaplan.
7. Human-gated flows suspend and resume through the shared native runtime contract.
8. Native traces are the canonical golden fixtures.
9. Import search shows no production callers of deleted `_pipeline/` graph modules.
10. Import search shows no references to `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, or graph scaffold switches.
11. Docs and scaffolds describe only native-first authoring.

## Risks

- `evidence_pack` is the highest-risk migration because it combines fanout, reduction, human review, and continuation semantics.
- `deliberation` is risky because discovery/runtime overload has already blurred the package contract; that split must be corrected cleanly.
- `doc` and `select_tournament` are risky because parameterized fanout behavior can silently drift even when topology still projects cleanly.
- `writing_panel_strict` and canonical Megaplan are risky because human-gate semantics must stay exact across suspend/resume.
- Adding `Pipeline.native_program` is a structural change that touches type definitions, validators, registry, projection, and tests; it must land first or package migrations will fork the contract again.

## Non-Negotiables

- Do not adopt bare `NativeProgram` return values in this wave.
- Do not keep execution payloads in `resource_bundles`.
- Do not preserve graph-first package metadata for compatibility.
- Do not let `_pipeline/` become a permanent compatibility graveyard.
- Do not start deleting graph modules before registry, package contracts, and tests have all been moved to native truth.

diff --git a/docs/arnold/pipelines/migration-completion-plan-v3.md b/docs/arnold/pipelines/migration-completion-plan-v3.md
new file mode 100644
index 0000000000000000000000000000000000000000..123d830a105811886550143ed3ce70f9ccb88965
--- /dev/null
+++ b/docs/arnold/pipelines/migration-completion-plan-v3.md
@@ -0,0 +1,368 @@
+# Arnold Pipeline Migration Completion Plan V3
+
+## Decision
+
+This migration ends with **native as the only canonical authoring and runtime model**. The repository will not target a dual graph/native equilibrium.
+
+The concrete end-state contract is:
+
+- `build_pipeline(...)` returns a **projected `Pipeline` shell**.
+- That `Pipeline` shell must carry a **required `native_program` field** containing the compiled `NativeProgram`.
+- `resource_bundles` is reserved for prompt/resource bundles only. It must not carry execution bundles or placeholder strings.
+- The returned `Pipeline` exists only for compatibility with registry, topology hashing, manifest/describe UX, and temporary graph-baseline tests during the purge window.
+- Native declarations in `pipeline.py` are the source of truth. Hand-built graph builders are temporary private baselines only.
+- `driver` is standardized to `("native", "<kind>")`. No graph-first strings, no mixed forms.
+- `default_profile` and `supported_modes` are required package metadata. Missing values are validation errors.
+- Native runtime is unconditional. `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, `MEGAPLAN_PIPELINE_AUTO`, and graph scaffold switches are deleted.
+
+This is the final shape because it is the cleanest end-state that is still implementable in one migration wave. Returning a bare `NativeProgram` would force a larger cross-cutting registry/CLI/test contract rewrite than this effort needs. Keeping projected `Pipeline` plus a first-class `native_program` field preserves the stable external surface while making graph projection explicitly secondary.
+
+## Final End-State Contract
+
+### 1. Public API
+
+`arnold.pipeline` becomes native-first:
+
+- Keep/export: `Pipeline`, `PipelineResourceBundle`, `NativeProgram`, `phase`, `pipeline`, `decision`, `parallel`, `native_panel`, `compile_pipeline`, `project_graph`, `run_native_pipeline`.
+- Move graph-era builder/executor entry points to `arnold.pipeline.legacy` and leave only temporary deprecation aliases in `arnold.pipeline.__init__` during the purge window.
+- `run_pipeline()` and `run_pipeline_resume()` stop being promoted as the main execution surface. Native runtime is the canonical execution path.
+
+### 2. Package contract
+
+Every runtime package must converge on this structure:
+
+```text
+arnold/pipelines/<package>/
+├── __init__.py      # metadata + build_pipeline export
+├── pipeline.py      # native declaration only
+├── steps.py         # runtime-agnostic step logic
+├── prompts/         # package-owned prompt assets
+└── _legacy.py       # temporary graph baseline, deleted in final purge
+```
+
+Rules:
+
+- `build_pipeline(...)` lives in `__init__.py` and does only: compile native declaration, project graph, attach `native_program`, attach prompt/resource bundles, return `Pipeline`.
+- `_build_legacy_graph_pipeline()` is the only allowed legacy naming.
+- `writing_panel_strict.py` must become `arnold/pipelines/megaplan/pipelines/writing_panel_strict/`.
+- `select-tournament` must be renamed to `select_tournament`.
+- Centralized Megaplan prompt export registries are deleted. Prompt ownership is per package.
+
+### 3. Human gate and continuation
+
+- One shared primitive wins: `@decision(human_gate=True)`.
+- Add `arnold.pipeline.human_gate` as sugar if needed, but do not keep package-specific human-gate abstractions.
+- `evidence_pack`, `deliberation`, `writing_panel_strict`, and canonical Megaplan must all use the same suspension/resume contract.
+- Continuation is runtime behavior of `run_native_pipeline(..., resume=...)`, not a separate continuation builder.
+
+### 4. Discovery, registry, CLI
+
+- Manifest-first discovery is unconditional.
+- Registry accepts only native-authored packages as first-class packages.
+- `entrypoint` contract is a bare symbol name, not `module:name`.
+- Add/standardize `arnold pipelines describe <name>`.
+- Keep `megaplan run <name> --describe` only as a thin compatibility alias during cleanup, then reduce it to a wrapper around `arnold pipelines describe`.
+- `arnold pipelines new` emits only native-first scaffold. `--driver graph` and deprecated graph scaffold code are deleted.
+
+### 5. Testing contract
+
+- Native traces are the golden source.
+- Graph traces remain only as temporary compatibility baselines where explicitly needed during migration, then collapse into one legacy baseline suite.
+- No test may require `ARNOLD_NATIVE_RUNTIME=1` or force graph runtime as the normal path.
+
+## Execution Order
+
+Order matters. Do not start package-by-package cleanup before the platform contract lands.
+
+### Step 1. Land the platform contract
+
+Files:
+
+- `arnold/pipeline/types.py`
+- `arnold/pipeline/__init__.py`
+- `arnold/pipeline/registry.py`
+- `arnold/pipeline/validator.py`
+- `arnold/pipeline/discovery/manifest.py`
+- `arnold/pipeline/native/__init__.py`
+- `arnold/pipeline/native/compiler.py`
+- `arnold/pipeline/native/runtime.py`
+- `arnold/pipeline/native/routing.py`
+- `arnold/pipeline/native/graph_projection.py`
+- `arnold/pipeline/builder.py`
+- `arnold/pipeline/executor.py`
+- `arnold/pipeline/resume.py`
+- `arnold/pipelines/megaplan/cli/__init__.py`
+
+Actions:
+
+1. Add `Pipeline.native_program: NativeProgram | None` to the structural pipeline type and update all projection/build helpers to populate it.
+2. Stop treating `resource_bundles` as an execution-bundle escape hatch.
+3. Make validator require `driver`, `default_profile`, `supported_modes`, and a native-backed `build_pipeline`.
+4. Delete `MEGAPLAN_M6_MANIFEST_DISCOVERY` logic and the eager `exec_module` discovery branch.
+5. Remove `ARNOLD_NATIVE_RUNTIME` requirement/error posture from native runtime and CLI help.
+6. Move graph-era exports behind `arnold.pipeline.legacy` aliases. Do not delete them yet.
+7. Delete `_MEGAPLAN_NATIVE_STAGE_ORDER` heuristics from `arnold/pipeline/native/routing.py`; canonical Megaplan must carry enough native structure to route itself.
+8. Move CLI pipeline subcommands out of `arnold/pipelines/megaplan/cli/__init__.py` into a dedicated `cli/pipelines.py` module as part of the cleanup.
+
+Exit criteria:
+
+- Registry loads native-backed packages without feature flags.
+- `arnold pipelines check` validates against the new contract.
+- `Pipeline.native_program` is the only sanctioned execution hook on projected pipelines.
+
+### Step 2. Normalize package layout and naming before behavior changes
+
+Files:
+
+- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py`
+- `arnold/pipelines/megaplan/pipelines/select-tournament/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/select-tournament/steps.py`
+- package `__init__.py` files across all migrated packages
+
+Actions:
+
+1. Convert `writing_panel_strict.py` into package form:
+   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/__init__.py`
+   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/pipeline.py`
+   - `arnold/pipelines/megaplan/pipelines/writing_panel_strict/steps.py`
+   - optional `_legacy.py`
+2. Rename `arnold/pipelines/megaplan/pipelines/select-tournament/` to `select_tournament/` and update imports, docs, manifests, and tests.
+3. Standardize package internals so each migrated package has `pipeline.py`, `steps.py`, and temporary `_legacy.py` if needed.
+
+Exit criteria:
+
+- No migrated package still uses one-off file layout when package layout is expected.
+- No hyphenated Python package names remain.
+
+### Step 3. Convert all already-close packages to the final contract
+
+Packages:
+
+- `arnold/pipelines/megaplan/pipelines/creative/`
+- `arnold/pipelines/megaplan/pipelines/doc/`
+- `arnold/pipelines/megaplan/pipelines/jokes/`
+- `arnold/pipelines/megaplan/pipelines/live_supervisor/`
+- `arnold/pipelines/megaplan/pipelines/writing_panel_strict/`
+- `arnold/pipelines/megaplan/pipelines/epic_blitz.py` or package if split
+- `arnold/pipelines/megaplan/pipelines/select_tournament/`
+- `arnold/pipelines/folder_audit/`
+- `arnold/pipelines/deliberation/`
+
+Actions for every package:
+
+1. Move native declaration into `pipeline.py`.
+2. Make `build_pipeline(...)` compile the native declaration, project it, attach `native_program`, attach prompt/resource bundles, and return the projected shell.
+3. Set `driver = ("native", "<kind>")`.
+4. Require real bundle objects in `resource_bundles`; remove empty tuples and placeholder strings.
+5. Rename any remaining graph-default builder to `_build_legacy_graph_pipeline()`.
+
+Package-specific requirements:
+
+- `creative`
+  - Delete `_CREATIVE_PROMPT_EXPORTS`.
+  - Remove graph-era docstrings/metadata.
+- `doc`
+  - Preserve fanout behavior, but make tests validate output/trace/describe contract instead of top-level `SubloopStep` shape.
+- `jokes`
+  - Preserve `_JokesNativeAdapter` semantics only if still required for parameter-to-state wiring.
+  - Update generated docs after migration.
+- `live_supervisor`
+  - Remove tests and code paths that force graph runtime.
+- `writing_panel_strict`
+  - Preserve `continue` and `stop` gate semantics exactly under native suspension/resume.
+- `epic_blitz`
+  - Attach a real native program and fix Megaplan runtime context injection so native execution is real, not a graph fallback.
+- `select_tournament`
+  - Replace hardcoded candidate assumptions with argument-driven native state/config wiring.
+- `folder_audit`
+  - Make native adapters work with runtime state injection rather than graph flattening assumptions.
+- `deliberation`
+  - Separate discovery metadata from runtime construction.
+  - Remove `build_pipeline()` overload behavior where no-arg means discovery and args mean graph runtime.
+
+Exit criteria:
+
+- Every package above is native-backed and validator-clean under the final contract.
+- Legacy graph builders are private baselines only.
+
+### Step 4. Migrate `evidence_pack` last among packages, but before purge
+
+Files:
+
+- `arnold/pipelines/evidence_pack/__init__.py`
+- `arnold/pipelines/evidence_pack/pipeline.py` or create it
+- `arnold/pipelines/evidence_pack/steps.py`
+- `arnold/pipelines/evidence_pack/pipelines.py`
+- `arnold/pipelines/evidence_pack/hooks.py`
+- `arnold/pipelines/evidence_pack/resume.py`
+- `arnold/pipelines/_deliberation_example/` consumers
+
+Actions:
+
+1. Create native declaration phases for ingest, validator fanout, reduce, human review, and attestation emission.
+2. Replace package-specific continuation flow with shared native suspension/resume.
+3. Remove `build_continuation_pipeline()` as a public concept.
+4. Replace `EvidencePackHooks` and `resume.py` graph-executor coupling with neutral runtime hooks or delete them outright.
+5. Update any example or downstream code still importing `HumanReviewStep`.
+
+Exit criteria:
+
+- `evidence_pack` runs natively with the same human review lifecycle as the other gated pipelines.
+- No graph-only continuation path remains in the package.
+
+### Step 5. Move still-live Megaplan runtime helpers out of `_pipeline/`
+
+Files to move or replace:
+
+- `arnold/pipelines/megaplan/_pipeline/types.py`
+- `arnold/pipelines/megaplan/_pipeline/registry.py`
+- any schema/step-IO/envelope helpers still under `_pipeline/`
+
+Target homes:
+
+- `arnold/pipelines/megaplan/types.py`
+- `arnold/pipelines/megaplan/registry.py`
+- `arnold/pipelines/megaplan/runtime/`
+- `arnold/pipelines/megaplan/discovery/` or `judge_manifests/` where appropriate
+
+Actions:
+
+1. Move the still-load-bearing non-graph helpers to first-class module homes.
+2. Update all imports to the new homes.
+3. Leave only a tiny temporary `arnold/pipelines/megaplan/_legacy.py` shim for import compatibility if strictly necessary.
+
+Exit criteria:
+
+- `_pipeline/` no longer contains active runtime ownership.
+- Remaining compatibility surface is explicit and small.
+
+### Step 6. Rewrite tests around native truth, then delete obsolete suites
+
+Files and directories:
+
+- `tests/arnold/pipelines/megaplan/parity_harness.py`
+- `tests/arnold/pipeline/native/parity_trace.py`
+- `tests/arnold/pipelines/megaplan/data/native_parity/`
+- `tests/arnold/pipelines/megaplan/test_native_parity_golden_traces.py`
+- `tests/arnold/pipelines/megaplan/test_graph_baseline.py`
+- `tests/arnold/pipelines/megaplan/test_legacy_pipeline_baseline.py`
+- `tests/parity/`
+- `tests/test_pipeline_parity.py`
+- `tests/test_pipeline_planning_parity.py`
+- package-specific pipeline tests called out in Wave 1
+
+Actions:
+
+1. Replace parity harness with a shared native-trace assertion helper.
+2. Rename golden trace storage to `golden_traces/` and regenerate them from native runtime.
+3. Rewrite package tests that assert graph topology details into behavior/trace/describe assertions.
+4. Collapse remaining graph-baseline assertions into one explicit legacy suite.
+5. Remove all env fixtures or helpers that force `ARNOLD_NATIVE_RUNTIME=1` or graph runtime as default.
+
+Exit criteria:
+
+- Native traces are canonical.
+- Only one deliberately-scoped legacy graph baseline suite remains before final purge.
+
+### Step 7. Docs and scaffold cleanup
+
+Files:
+
+- `docs/arnold/package-authoring-contract.md`
+- `docs/arnold/package-contract.md`
+- `docs/arnold/authoring-guide.md`
+- `docs/arnold/creating-a-new-pipeline.md`
+- `docs/arnold/examples/jokes.md`
+- `docs/arnold/examples/select-tournament.md`
+- `scripts/generate_arnold_docs.py`
+- template/scaffold files used by `arnold pipelines new`
+
+Actions:
+
+1. Rewrite docs to describe `build_pipeline()` returning a projected `Pipeline` with required `native_program`.
+2. Document `driver = ("native", "<kind>")` as the only accepted runtime posture.
+3. Regenerate examples and reference docs from native declarations.
+4. Replace template/scaffold output with native-first runnable examples only.
+
+Exit criteria:
+
+- No doc instructs users to opt into native runtime or create graph pipelines.
+
+### Step 8. Final purge
+
+Do this only after all prior exit criteria are met.
+
+## Purge List
+
+Delete outright:
+
+- `arnold/pipelines/megaplan/_pipeline/builder.py`
+- `arnold/pipelines/megaplan/_pipeline/executor.py`
+- `arnold/pipelines/megaplan/_pipeline/patterns.py`
+- `arnold/pipelines/megaplan/_pipeline/pattern_dynamic.py`
+- `arnold/pipelines/megaplan/_pipeline/subloop.py`
+- `arnold/pipelines/megaplan/_pipeline/resume.py`
+- `arnold/pipelines/megaplan/_pipeline/_bridge.py`
+- `arnold/pipelines/megaplan/_pipeline/_forward_m2_m3.py`
+- `arnold/pipelines/megaplan/_pipeline/_BRIDGE_CALLERS.md`
+- `arnold/pipelines/megaplan/_pipeline/runtime.py`
+- `arnold/pipelines/megaplan/operations.py` if import search confirms it is dead
+- `arnold/pipelines/megaplan/prompts/__init__.py`
+- duplicate test `tests/test_execute_merge_creative.py`
+- temporary legacy graph builders in migrated packages (`_legacy.py`) once the final compatibility suite is removed
+- any remaining graph scaffold helper such as `_deprecated_graph_scaffold_module_content()`
+
+Delete feature flags and compatibility env gates:
+
+- `MEGAPLAN_M6_MANIFEST_DISCOVERY`
+- `ARNOLD_NATIVE_RUNTIME`
+- `MEGAPLAN_PIPELINE_AUTO`
+
+Delete old tests/fixtures:
+
+- `tests/parity/`
+- `tests/test_pipeline_parity.py`
+- `tests/test_pipeline_planning_parity.py`
+- graph-generated golden trace fixtures superseded by native `golden_traces/`
+
+After purge, `arnold.pipeline.legacy` may remain briefly only if import search still shows external/internal callers. If no callers remain, remove it in the same wave.
+
+## Test And Docs Cleanup Checklist
+
+- Rewrite tests that assert graph metadata, graph-only drivers, or graph step classes.
+- Remove any tests calling graph builders directly as the primary path.
+- Update topology-hash tests to compare projected shells derived from native declarations.
+- Ensure doc generators inspect native declarations and `build_pipeline()` contract, not graph builder internals.
+- Remove stale SKILL/doc references to graph runtime switches or manifest discovery flags.
+
+## Validation Checklist
+
+The migration is complete only when all of these are true:
+
+1. `arnold pipelines check` passes for every registered package with no feature flags.
+2. `arnold pipelines describe <name>` works for every registered package.
+3. `megaplan run <name> --describe` resolves through the same native-backed contract.
+4. Every runtime package’s `build_pipeline()` returns a projected `Pipeline` shell with a non-null `native_program`.
+5. No package uses placeholder strings or execution objects in `resource_bundles`.
+6. Native execution succeeds for `creative`, `doc`, `jokes`, `live_supervisor`, `writing_panel_strict`, `epic_blitz`, `select_tournament`, `folder_audit`, `deliberation`, `evidence_pack`, and canonical Megaplan.
+7. Human-gated flows suspend and resume through the shared native runtime contract.
+8. Native traces are the canonical golden fixtures.
+9. Import search shows no production callers of deleted `_pipeline/` graph modules.
+10. Import search shows no references to `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, or graph scaffold switches.
+11. Docs and scaffolds describe only native-first authoring.
+
+## Risks
+
+- `evidence_pack` is the highest-risk migration because it combines fanout, reduction, human review, and continuation semantics.
+- `deliberation` is risky because discovery/runtime overload has already blurred the package contract; that split must be corrected cleanly.
+- `doc` and `select_tournament` are risky because parameterized fanout behavior can silently drift even when topology still projects cleanly.
+- `writing_panel_strict` and canonical Megaplan are risky because human-gate semantics must stay exact across suspend/resume.
+- Adding `Pipeline.native_program` is a structural change that touches type definitions, validators, registry, projection, and tests; it must land first or package migrations will fork the contract again.
+
+## Non-Negotiables
+
+- Do not adopt bare `NativeProgram` return values in this wave.
+- Do not keep execution payloads in `resource_bundles`.
+- Do not preserve graph-first package metadata for compatibility.
+- Do not let `_pipeline/` become a permanent compatibility graveyard.
+- Do not start deleting graph modules before registry, package contracts, and tests have all been moved to native truth.

codex