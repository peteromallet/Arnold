# Arnold Pipeline Migration Completion Plan V2
+
+## Final audit summary
+
+The original completion plan got the direction right but under-scoped the work. The repo is not blocked only on five Megaplan subpipelines. The real blockers are:
+
+1. Several packages are still graph-default or graph-only.
+2. Registry, manifest discovery, validator, and CLI scaffolding still encode graph-first assumptions.
+3. The parity and regression suite still treats graph execution as canonical in many places.
+4. A large compatibility surface under `arnold/pipelines/megaplan/_pipeline/` is still load-bearing and cannot be purged until its callers are removed or moved.
+
+The correct end-state is:
+
+- Every registered pipeline builds as native-first.
+- Every runtime pipeline can execute via native runtime without `ARNOLD_NATIVE_RUNTIME=1` escape-hatch semantics.
+- Registry and `pipelines check` accept native-authored packages as the normal case.
+- `arnold pipelines check` passes for every registered pipeline.
+- `megaplan run <pipeline> --describe` works for every registered pipeline.
+- Graph-era builders, bridges, env gates, stale scaffolds, stale docs, and graph-only tests are deleted once no longer needed.
+
+## What stays, what changes, what gets cut
+
+Keep:
+
+- Native compiler/runtime/projection stack in `arnold/pipeline/native/`.
+- Canonical native-authored packages already close to target: `megaplan`, `epic_blitz`, `select-tournament`, `creative`, `doc`, `jokes`, `live_supervisor`, `writing_panel_strict`, `folder_audit`, `deliberation`.
+- Legacy graph builders only as temporary parity baselines during migration.
+
+Cut:
+
+- Manifest-discovery feature-flag rollout posture.
+- Native-runtime opt-in posture.
+- Deprecated graph scaffolding path in CLI.
+- Graph-first package metadata and graph-first tests as the source of truth.
+- Dead bridges marked for deletion in prior milestones.
+
+Reorder:
+
+1. Fix platform/discovery/validator/CLI assumptions first.
+2. Then flip package entrypoints and attach real native bundles.
+3. Then migrate `evidence_pack`.
+4. Then repair tests/docs/fixtures.
+5. Then purge graph-era code.
+
+## Prioritized execution plan
+
+### 1. Make native-first the platform default
+
+This must land before package cleanup. Otherwise `pipelines check`, registry discovery, and CLI scaffolding will keep reintroducing graph-era behavior.
+
+Files to change:
+
+- `arnold/pipeline/__init__.py`
+- `arnold/pipeline/registry.py`
+- `arnold/pipeline/discovery/manifest.py`
+- `arnold/pipeline/validator.py`
+- `arnold/pipeline/native/__init__.py`
+- `arnold/pipeline/native/routing.py`
+- `arnold/pipeline/native/compiler.py`
+- `arnold/pipeline/native/runtime.py`
+- `arnold/pipeline/native/graph_projection.py`
+- `arnold/pipelines/megaplan/cli/__init__.py`
+- `docs/arnold/package-authoring-contract.md`
+- `docs/arnold/authoring-guide.md`
+
+Required changes:
+
+- Make the authoring contract accept native-first packages as the normal case, not a projected graph special case.
+- Remove `MEGAPLAN_M6_MANIFEST_DISCOVERY` as a rollout gate and make manifest-first discovery unconditional.
+- Update registry storage and validator assumptions so package entrypoints returning projected native pipelines are first-class.
+- Export native authoring symbols from `arnold.pipeline` public surface.
+- Remove stale native-runtime errors and docs that tell users to set `ARNOLD_NATIVE_RUNTIME=1`.
+- Remove the deprecated graph scaffold path from `arnold pipelines new`; native scaffold becomes the only scaffold.
+- Remove Megaplan-specific stage-order heuristics from `arnold/pipeline/native/routing.py`.
+- Keep projection adapters only until the final purge stage; do not expand them further.
+
+### 2. Normalize package metadata and entrypoint semantics
+
+Before touching per-pipeline behavior, standardize package metadata across all registered pipelines.
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/creative/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/doc/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/jokes/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/live_supervisor/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/live_supervisor/pipelines.py`
+- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py`
+- `arnold/pipelines/megaplan/pipelines/epic_blitz.py`
+- `arnold/pipelines/megaplan/pipelines/select-tournament/__init__.py`
+- `arnold/pipelines/folder_audit/__init__.py`
+- `arnold/pipelines/folder_audit/native.py`
+- `arnold/pipelines/deliberation/__init__.py`
+- `arnold/pipelines/deliberation/pipelines.py`
+- `arnold/pipelines/evidence_pack/__init__.py`
+- `arnold/pipelines/evidence_pack/pipelines.py`
+
+Required changes:
+
+- `build_pipeline()` must return the canonical native-first pipeline in every runtime package.
+- `driver` metadata must stop advertising graph-first execution.
+- Every package must expose valid `default_profile` and `supported_modes` constants so manifest discovery does not need special-case tolerance.
+- Every native-first pipeline must carry a real native execution bundle in `resource_bundles`, not empty tuples or placeholder strings.
+- Legacy graph builders may remain only as `_build_legacy_graph_pipeline()` or equivalent temporary helpers for parity baselines.
+
+### 3. Finish the remaining Megaplan subpipelines
+
+These are smaller than `evidence_pack` and should be cleared first.
+
+#### 3.1 creative
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/creative/__init__.py`
+- `arnold/pipelines/megaplan/prompts/__init__.py`
+- `tests/arnold/pipelines/megaplan/test_creative_native_parity.py`
+- `tests/test_execute_merge_creative.py`
+- `tests/pipelines/megaplan/execute/test_merge_creative.py`
+
+Actions:
+
+- Make native projection the only default return path.
+- Remove graph-era docstring and driver metadata.
+- Delete `_CREATIVE_PROMPT_EXPORTS` shim from `arnold/pipelines/megaplan/prompts/__init__.py`.
+- Delete the duplicate `tests/test_execute_merge_creative.py`; keep the canonical execute test under `tests/pipelines/megaplan/execute/`.
+
+#### 3.2 doc
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/doc/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/doc/steps.py`
+- `tests/arnold/pipelines/megaplan/test_doc_native_parity.py`
+- `tests/pipelines/test_doc_pipeline.py`
+
+Actions:
+
+- Make native projection the default return path.
+- Keep fanout semantics stable, but stop treating top-level `SubloopStep` shape as the contract.
+- Rewrite `tests/pipelines/test_doc_pipeline.py` to validate behavior and manifest/describe output, not legacy graph topology.
+
+#### 3.3 jokes
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/jokes/__init__.py`
+- `tests/arnold/pipelines/megaplan/test_jokes_native_parity.py`
+- `tests/pipelines/test_jokes_pipeline.py`
+- `scripts/generate_arnold_docs.py`
+- `docs/arnold/examples/jokes.md`
+
+Actions:
+
+- Make native projection the default return path.
+- Preserve topic-seeding behavior through `_JokesNativeAdapter`.
+- Rewrite graph-only metadata assertions in `tests/pipelines/test_jokes_pipeline.py`.
+- Update generated docs and the docs generator to describe jokes as native-first.
+
+#### 3.4 live_supervisor
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/live_supervisor/pipelines.py`
+- `arnold/pipelines/megaplan/pipelines/live_supervisor/__init__.py`
+- `tests/arnold/pipelines/megaplan/test_live_supervisor_native_parity.py`
+- `tests/pipelines/test_live_supervisor_pipeline.py`
+
+Actions:
+
+- Make native projection the default return path.
+- Remove test dependence on `ARNOLD_PIPELINE_RUNTIME=graph`.
+- Keep timestamp normalization and envelope assertions only where they validate behavior rather than executor identity.
+
+#### 3.5 writing_panel_strict
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py`
+- `tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py`
+- `tests/_pipeline/test_writing_panel_e2e.py`
+
+Actions:
+
+- Make native projection the default return path.
+- Keep human gate behavior identical: `continue` loops, `stop` halts.
+- Rewrite `tests/_pipeline/test_writing_panel_e2e.py` to validate suspension/resume semantics, not direct patching of `HumanDecisionStep` internals.
+
+### 4. Fix the packages that are already “native-default” but not actually native-runnable
+
+The original plan treated these as done. They are not done.
+
+#### 4.1 epic_blitz
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/epic_blitz.py`
+- `tests/arnold/pipelines/megaplan/test_epic_blitz_native_parity.py`
+
+Actions:
+
+- Attach a real native execution bundle.
+- Stop advertising graph-first driver metadata.
+- Ensure Megaplan-specific runtime context injection works in native runtime instead of silently falling back to graph execution.
+
+#### 4.2 select_tournament
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/select-tournament/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/select-tournament/steps.py`
+- `tests/arnold/pipelines/megaplan/test_select_tournament_native_parity.py`
+- `docs/arnold/examples/select-tournament.md`
+
+Actions:
+
+- Replace placeholder `resource_bundles` entries with a real native bundle.
+- Keep candidate-count parameterization working through projection.
+- Update docs to match real runtime behavior.
+
+### 5. Finish root-level converted packages
+
+#### 5.1 folder_audit
+
+Files to change:
+
+- `arnold/pipelines/folder_audit/__init__.py`
+- `arnold/pipelines/folder_audit/native.py`
+- `tests/pipelines/test_folder_audit.py`
+- `tests/arnold/pipeline/test_executor_selection.py`
+- `tests/arnold/pipeline/test_topology_hash.py`
+
+Actions:
+
+- Make `build_pipeline()` native-first.
+- Remove `ARNOLD_NATIVE_RUNTIME=1` opt-in wording and expectations.
+- Fix native adapters in `native.py` so runtime state injection does not depend on graph-executor flattening behavior.
+- Rewrite `tests/pipelines/test_folder_audit.py` away from graph-default metadata expectations.
+
+#### 5.2 deliberation
+
+Files to change:
+
+- `arnold/pipelines/deliberation/__init__.py`
+- `arnold/pipelines/deliberation/pipelines.py`
+- `tests/arnold/pipelines/deliberation/test_native_parity.py`
+- `tests/arnold/pipelines/deliberation/test_e2e.py`
+- `tests/arnold/pipelines/deliberation/test_skeleton.py`
+- `tests/boundary/test_deliberation_import_leak.py`
+
+Actions:
+
+- Separate discovery from runtime completely.
+- `build_pipeline()` must be a native-first runtime entrypoint.
+- Introduce an explicit manifest-introspection path for discovery-only callers instead of overloading `build_pipeline()`.
+- Move tests off direct `build_initial_pipeline()` dependence unless they are explicitly testing the legacy baseline.
+
+### 6. Migrate `evidence_pack` completely
+
+This is the largest remaining migration and the last package-level blocker before purge.
+
+Files to change:
+
+- `arnold/pipelines/evidence_pack/__init__.py`
+- `arnold/pipelines/evidence_pack/pipelines.py`
+- `arnold/pipelines/evidence_pack/steps.py`
+- `arnold/pipelines/evidence_pack/hooks.py`
+- `arnold/pipelines/evidence_pack/resume.py`
+- `arnold/pipelines/_deliberation_example/__init__.py`
+- `arnold/pipelines/_deliberation_example/pipelines.py`
+- `arnold/pipelines/_deliberation_example/_hooks.py`
+- `tests/arnold/pipelines/evidence_pack/test_pipelines.py`
+- `tests/arnold/pipelines/evidence_pack/test_end_to_end.py`
+- `tests/arnold/pipelines/evidence_pack/test_resume.py`
+- `tests/arnold/pipelines/evidence_pack/test_hooks.py`
+- `tests/arnold/pipelines/evidence_pack/test_steps.py`
+- `tests/arnold/conformance/test_evidence_pack_conformance.py`
+- `tests/arnold/pipeline/test_evidence_pack_expressibility.py`
+- `tests/arnold/pipeline/test_c4_authored_end_to_end.py`
+
+Actions:
+
+- Add a native declaration for the initial pipeline and a native declaration for the continuation pipeline.
+- Preserve the current human review semantics by wrapping the existing `HumanReviewStep` behavior, not by inventing a different suspension contract.
+- Keep `resume.py` and `EvidencePackHooks` working against the native runtime.
+- Update `_deliberation_example` to import the canonical human-review path that survives the migration.
+
+### 7. Convert registry, check, describe, and docs from graph-baseline to native-baseline
+
+Files to change:
+
+- `arnold/pipelines/megaplan/cli/__init__.py`
+- `scripts/generate_arnold_docs.py`
+- `tests/test_pipelines_check_validator.py`
+- `tests/test_pipeline_run_cli.py`
+- `tests/test_generate_arnold_docs.py`
+- `tests/arnold/pipelines/test_package_authoring_contract.py`
+- `tests/arnold/pipelines/test_authoring.py`
+- `tests/_pipeline/test_registry_python_discovery.py`
+- `tests/arnold/pipeline/test_registry.py`
+- `tests/test_pipeline_registry.py`
+
+Actions:
+
+- Make `arnold pipelines check` validate the actual native-first packages without temporary env mutation.
+- Make `megaplan run <pipeline> --describe` work from manifest-discovered, native-first package metadata.
+- Stop generating docs that describe graph pipelines as canonical.
+- Update authoring/registry tests so native-first packages are the contract.
+
+### 8. Replace graph-first parity harness and stale fixtures
+
+Files to change:
+
+- `tests/arnold/pipelines/megaplan/parity_harness.py`
+- `tests/arnold/pipelines/megaplan/test_native_parity.py`
+- `tests/arnold/pipelines/megaplan/test_native_parity_golden_traces.py`
+- `tests/arnold/pipelines/megaplan/test_graph_baseline.py`
+- `tests/arnold/pipelines/megaplan/test_legacy_pipeline_baseline.py`
+- `tests/test_pipeline_parity.py`
+- `tests/test_pipeline_planning_parity.py`
+- `tests/parity/test_graph_projection_parity.py`
+- `tests/arnold/pipeline/native/parity_trace.py`
+- `tests/arnold/pipelines/megaplan/data/native_parity/*.json`
+
+Actions:
+
+- Stop treating graph-executor traces as golden source of truth.
+- Regenerate parity fixtures from native execution where parity is still required.
+- Keep one explicit legacy-baseline suite until purge is complete; after purge, delete it.
+- Remove native tests that still force `ARNOLD_NATIVE_RUNTIME=1`.
+
+### 9. Purge graph-era Megaplan internals after all callers are gone
+
+Do not start this step early. It is intentionally last.
+
+Files and modules to remove or reduce sharply:
+
+- `arnold/pipelines/megaplan/_pipeline/_forward_m2_m3.py`
+- `arnold/pipelines/megaplan/_pipeline/_bridge.py`
+- `arnold/pipelines/megaplan/_pipeline/_BRIDGE_CALLERS.md`
+- `arnold/pipelines/megaplan/_pipeline/runtime.py`
+- `arnold/pipelines/megaplan/_pipeline/executor.py`
+- `arnold/pipelines/megaplan/_pipeline/builder.py`
+- `arnold/pipelines/megaplan/_pipeline/patterns.py`
+- `arnold/pipelines/megaplan/_pipeline/pattern_dynamic.py`
+- `arnold/pipelines/megaplan/_pipeline/subloop.py`
+- `arnold/pipelines/megaplan/_pipeline/resume.py`
+- `arnold/pipelines/megaplan/_pipeline/registry.py`
+- `arnold/pipelines/megaplan/operations.py`
+- `arnold/pipelines/megaplan/auto.py`
+- Inline legacy builder in `arnold/pipelines/megaplan/pipeline.py`
+
+Actions:
+
+- Move any remaining required compatibility helpers into one explicit compatibility module.
+- Delete env-gated policy runtime and graph fallback selection code.
+- Remove import-by-string or bridge callers before deleting modules.
+- Shrink `arnold/pipelines/megaplan/pipeline.py` to native composition plus temporary compatibility wrapper only if still needed.
+
+### 10. Final cleanup and dead-file purge
+
+Purge list:
+
+- `tests/test_execute_merge_creative.py`
+- Any untracked `_tmp_compute_hash.py`
+- Deprecated graph scaffold generator branch in `arnold/pipelines/megaplan/cli/__init__.py`
+- Stale graph-era wording in:
+  - `docs/arnold/examples/jokes.md`
+  - `docs/arnold/examples/select-tournament.md`
+  - `docs/arnold/package-authoring-contract.md`
+  - `docs/arnold/authoring-guide.md`
+- Any remaining docs or tests that require `ARNOLD_NATIVE_RUNTIME=1`
+- Any remaining docs or tests that force `ARNOLD_PIPELINE_RUNTIME=graph`
+
+## Validation checklist
+
+### Package-level validation
+
+- `pytest tests/arnold/pipelines/megaplan/test_creative_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_doc_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_jokes_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_live_supervisor_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_epic_blitz_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_select_tournament_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_native_parity.py`
+- `pytest tests/arnold/pipelines/deliberation/test_native_parity.py`
+- `pytest tests/arnold/pipelines/evidence_pack`
+- `pytest tests/pipelines/test_folder_audit.py`
+
+### Platform validation
+
+- `pytest tests/arnold/pipeline/test_registry.py`
+- `pytest tests/arnold/pipeline/test_executor_selection.py`
+- `pytest tests/test_pipeline_registry.py`
+- `pytest tests/test_pipelines_check_validator.py`
+- `pytest tests/test_pipeline_run_cli.py`
+- `pytest tests/test_generate_arnold_docs.py`
+- `pytest tests/arnold/pipelines/test_package_authoring_contract.py`
+- `pytest tests/arnold/pipelines/test_authoring.py`
+
+### Regression validation
+
+- `pytest tests/arnold/pipeline tests/arnold/pipelines tests/_pipeline tests/pipelines`
+
+### CLI validation
+
+- `arnold pipelines check`
+- `megaplan run megaplan --describe`
+- `megaplan run creative --describe`
+- `megaplan run doc --describe`
+- `megaplan run epic-blitz --describe`
+- `megaplan run jokes --describe`
+- `megaplan run live-supervisor --describe`
+- `megaplan run select-tournament --describe`
+- `megaplan run writing-panel-strict --describe`
+- `megaplan run folder-audit --describe`
+- `megaplan run deliberation --describe`
+- `megaplan run evidence-pack --describe`
+
+All of the above must work without setting `ARNOLD_NATIVE_RUNTIME`, `ARNOLD_PIPELINE_RUNTIME`, or `MEGAPLAN_M6_MANIFEST_DISCOVERY`.
+
+## Risks
+
+- Human-gate behavior is the highest-risk migration surface. `writing_panel_strict`, `deliberation`, `evidence_pack`, and `megaplan` must preserve suspension and resume semantics exactly.
+- `evidence_pack` is the only remaining graph-only runtime package and is the largest implementation task.
+- `doc` fanout semantics can regress if native parallelism changes artifact shape; behavior-level assertions must replace graph-shape assertions.
+- Some parity infrastructure is graph-executor-shaped by design. Replacing it too early will hide regressions; replacing it too late will block purge.
+- `megaplan/_pipeline/*` is still load-bearing. Purge must be driven by import elimination, not by milestone labels.
+
+## Definition of done
+
+This migration is complete only when:
+
+- Every registered pipeline is native-first.
+- Every registered pipeline describes successfully through CLI.
+- `arnold pipelines check` passes without env flags.
+- `evidence_pack` no longer depends on graph-only builder/executor semantics.
+- Graph-era bridges and deprecated graph scaffolding are deleted.
+- The remaining tests and docs treat native execution as canonical.

diff --git a/docs/arnold/pipelines/migration-completion-plan-v2.md b/docs/arnold/pipelines/migration-completion-plan-v2.md
new file mode 100644
index 0000000000000000000000000000000000000000..2c9c235d89eee8e8e7eb56959a6c41a385b79fc7
--- /dev/null
+++ b/docs/arnold/pipelines/migration-completion-plan-v2.md
@@ -0,0 +1,439 @@
+# Arnold Pipeline Migration Completion Plan V2
+
+## Final audit summary
+
+The original completion plan got the direction right but under-scoped the work. The repo is not blocked only on five Megaplan subpipelines. The real blockers are:
+
+1. Several packages are still graph-default or graph-only.
+2. Registry, manifest discovery, validator, and CLI scaffolding still encode graph-first assumptions.
+3. The parity and regression suite still treats graph execution as canonical in many places.
+4. A large compatibility surface under `arnold/pipelines/megaplan/_pipeline/` is still load-bearing and cannot be purged until its callers are removed or moved.
+
+The correct end-state is:
+
+- Every registered pipeline builds as native-first.
+- Every runtime pipeline can execute via native runtime without `ARNOLD_NATIVE_RUNTIME=1` escape-hatch semantics.
+- Registry and `pipelines check` accept native-authored packages as the normal case.
+- `arnold pipelines check` passes for every registered pipeline.
+- `megaplan run <pipeline> --describe` works for every registered pipeline.
+- Graph-era builders, bridges, env gates, stale scaffolds, stale docs, and graph-only tests are deleted once no longer needed.
+
+## What stays, what changes, what gets cut
+
+Keep:
+
+- Native compiler/runtime/projection stack in `arnold/pipeline/native/`.
+- Canonical native-authored packages already close to target: `megaplan`, `epic_blitz`, `select-tournament`, `creative`, `doc`, `jokes`, `live_supervisor`, `writing_panel_strict`, `folder_audit`, `deliberation`.
+- Legacy graph builders only as temporary parity baselines during migration.
+
+Cut:
+
+- Manifest-discovery feature-flag rollout posture.
+- Native-runtime opt-in posture.
+- Deprecated graph scaffolding path in CLI.
+- Graph-first package metadata and graph-first tests as the source of truth.
+- Dead bridges marked for deletion in prior milestones.
+
+Reorder:
+
+1. Fix platform/discovery/validator/CLI assumptions first.
+2. Then flip package entrypoints and attach real native bundles.
+3. Then migrate `evidence_pack`.
+4. Then repair tests/docs/fixtures.
+5. Then purge graph-era code.
+
+## Prioritized execution plan
+
+### 1. Make native-first the platform default
+
+This must land before package cleanup. Otherwise `pipelines check`, registry discovery, and CLI scaffolding will keep reintroducing graph-era behavior.
+
+Files to change:
+
+- `arnold/pipeline/__init__.py`
+- `arnold/pipeline/registry.py`
+- `arnold/pipeline/discovery/manifest.py`
+- `arnold/pipeline/validator.py`
+- `arnold/pipeline/native/__init__.py`
+- `arnold/pipeline/native/routing.py`
+- `arnold/pipeline/native/compiler.py`
+- `arnold/pipeline/native/runtime.py`
+- `arnold/pipeline/native/graph_projection.py`
+- `arnold/pipelines/megaplan/cli/__init__.py`
+- `docs/arnold/package-authoring-contract.md`
+- `docs/arnold/authoring-guide.md`
+
+Required changes:
+
+- Make the authoring contract accept native-first packages as the normal case, not a projected graph special case.
+- Remove `MEGAPLAN_M6_MANIFEST_DISCOVERY` as a rollout gate and make manifest-first discovery unconditional.
+- Update registry storage and validator assumptions so package entrypoints returning projected native pipelines are first-class.
+- Export native authoring symbols from `arnold.pipeline` public surface.
+- Remove stale native-runtime errors and docs that tell users to set `ARNOLD_NATIVE_RUNTIME=1`.
+- Remove the deprecated graph scaffold path from `arnold pipelines new`; native scaffold becomes the only scaffold.
+- Remove Megaplan-specific stage-order heuristics from `arnold/pipeline/native/routing.py`.
+- Keep projection adapters only until the final purge stage; do not expand them further.
+
+### 2. Normalize package metadata and entrypoint semantics
+
+Before touching per-pipeline behavior, standardize package metadata across all registered pipelines.
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/creative/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/doc/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/jokes/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/live_supervisor/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/live_supervisor/pipelines.py`
+- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py`
+- `arnold/pipelines/megaplan/pipelines/epic_blitz.py`
+- `arnold/pipelines/megaplan/pipelines/select-tournament/__init__.py`
+- `arnold/pipelines/folder_audit/__init__.py`
+- `arnold/pipelines/folder_audit/native.py`
+- `arnold/pipelines/deliberation/__init__.py`
+- `arnold/pipelines/deliberation/pipelines.py`
+- `arnold/pipelines/evidence_pack/__init__.py`
+- `arnold/pipelines/evidence_pack/pipelines.py`
+
+Required changes:
+
+- `build_pipeline()` must return the canonical native-first pipeline in every runtime package.
+- `driver` metadata must stop advertising graph-first execution.
+- Every package must expose valid `default_profile` and `supported_modes` constants so manifest discovery does not need special-case tolerance.
+- Every native-first pipeline must carry a real native execution bundle in `resource_bundles`, not empty tuples or placeholder strings.
+- Legacy graph builders may remain only as `_build_legacy_graph_pipeline()` or equivalent temporary helpers for parity baselines.
+
+### 3. Finish the remaining Megaplan subpipelines
+
+These are smaller than `evidence_pack` and should be cleared first.
+
+#### 3.1 creative
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/creative/__init__.py`
+- `arnold/pipelines/megaplan/prompts/__init__.py`
+- `tests/arnold/pipelines/megaplan/test_creative_native_parity.py`
+- `tests/test_execute_merge_creative.py`
+- `tests/pipelines/megaplan/execute/test_merge_creative.py`
+
+Actions:
+
+- Make native projection the only default return path.
+- Remove graph-era docstring and driver metadata.
+- Delete `_CREATIVE_PROMPT_EXPORTS` shim from `arnold/pipelines/megaplan/prompts/__init__.py`.
+- Delete the duplicate `tests/test_execute_merge_creative.py`; keep the canonical execute test under `tests/pipelines/megaplan/execute/`.
+
+#### 3.2 doc
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/doc/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/doc/steps.py`
+- `tests/arnold/pipelines/megaplan/test_doc_native_parity.py`
+- `tests/pipelines/test_doc_pipeline.py`
+
+Actions:
+
+- Make native projection the default return path.
+- Keep fanout semantics stable, but stop treating top-level `SubloopStep` shape as the contract.
+- Rewrite `tests/pipelines/test_doc_pipeline.py` to validate behavior and manifest/describe output, not legacy graph topology.
+
+#### 3.3 jokes
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/jokes/__init__.py`
+- `tests/arnold/pipelines/megaplan/test_jokes_native_parity.py`
+- `tests/pipelines/test_jokes_pipeline.py`
+- `scripts/generate_arnold_docs.py`
+- `docs/arnold/examples/jokes.md`
+
+Actions:
+
+- Make native projection the default return path.
+- Preserve topic-seeding behavior through `_JokesNativeAdapter`.
+- Rewrite graph-only metadata assertions in `tests/pipelines/test_jokes_pipeline.py`.
+- Update generated docs and the docs generator to describe jokes as native-first.
+
+#### 3.4 live_supervisor
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/live_supervisor/pipelines.py`
+- `arnold/pipelines/megaplan/pipelines/live_supervisor/__init__.py`
+- `tests/arnold/pipelines/megaplan/test_live_supervisor_native_parity.py`
+- `tests/pipelines/test_live_supervisor_pipeline.py`
+
+Actions:
+
+- Make native projection the default return path.
+- Remove test dependence on `ARNOLD_PIPELINE_RUNTIME=graph`.
+- Keep timestamp normalization and envelope assertions only where they validate behavior rather than executor identity.
+
+#### 3.5 writing_panel_strict
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py`
+- `tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py`
+- `tests/_pipeline/test_writing_panel_e2e.py`
+
+Actions:
+
+- Make native projection the default return path.
+- Keep human gate behavior identical: `continue` loops, `stop` halts.
+- Rewrite `tests/_pipeline/test_writing_panel_e2e.py` to validate suspension/resume semantics, not direct patching of `HumanDecisionStep` internals.
+
+### 4. Fix the packages that are already “native-default” but not actually native-runnable
+
+The original plan treated these as done. They are not done.
+
+#### 4.1 epic_blitz
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/epic_blitz.py`
+- `tests/arnold/pipelines/megaplan/test_epic_blitz_native_parity.py`
+
+Actions:
+
+- Attach a real native execution bundle.
+- Stop advertising graph-first driver metadata.
+- Ensure Megaplan-specific runtime context injection works in native runtime instead of silently falling back to graph execution.
+
+#### 4.2 select_tournament
+
+Files to change:
+
+- `arnold/pipelines/megaplan/pipelines/select-tournament/__init__.py`
+- `arnold/pipelines/megaplan/pipelines/select-tournament/steps.py`
+- `tests/arnold/pipelines/megaplan/test_select_tournament_native_parity.py`
+- `docs/arnold/examples/select-tournament.md`
+
+Actions:
+
+- Replace placeholder `resource_bundles` entries with a real native bundle.
+- Keep candidate-count parameterization working through projection.
+- Update docs to match real runtime behavior.
+
+### 5. Finish root-level converted packages
+
+#### 5.1 folder_audit
+
+Files to change:
+
+- `arnold/pipelines/folder_audit/__init__.py`
+- `arnold/pipelines/folder_audit/native.py`
+- `tests/pipelines/test_folder_audit.py`
+- `tests/arnold/pipeline/test_executor_selection.py`
+- `tests/arnold/pipeline/test_topology_hash.py`
+
+Actions:
+
+- Make `build_pipeline()` native-first.
+- Remove `ARNOLD_NATIVE_RUNTIME=1` opt-in wording and expectations.
+- Fix native adapters in `native.py` so runtime state injection does not depend on graph-executor flattening behavior.
+- Rewrite `tests/pipelines/test_folder_audit.py` away from graph-default metadata expectations.
+
+#### 5.2 deliberation
+
+Files to change:
+
+- `arnold/pipelines/deliberation/__init__.py`
+- `arnold/pipelines/deliberation/pipelines.py`
+- `tests/arnold/pipelines/deliberation/test_native_parity.py`
+- `tests/arnold/pipelines/deliberation/test_e2e.py`
+- `tests/arnold/pipelines/deliberation/test_skeleton.py`
+- `tests/boundary/test_deliberation_import_leak.py`
+
+Actions:
+
+- Separate discovery from runtime completely.
+- `build_pipeline()` must be a native-first runtime entrypoint.
+- Introduce an explicit manifest-introspection path for discovery-only callers instead of overloading `build_pipeline()`.
+- Move tests off direct `build_initial_pipeline()` dependence unless they are explicitly testing the legacy baseline.
+
+### 6. Migrate `evidence_pack` completely
+
+This is the largest remaining migration and the last package-level blocker before purge.
+
+Files to change:
+
+- `arnold/pipelines/evidence_pack/__init__.py`
+- `arnold/pipelines/evidence_pack/pipelines.py`
+- `arnold/pipelines/evidence_pack/steps.py`
+- `arnold/pipelines/evidence_pack/hooks.py`
+- `arnold/pipelines/evidence_pack/resume.py`
+- `arnold/pipelines/_deliberation_example/__init__.py`
+- `arnold/pipelines/_deliberation_example/pipelines.py`
+- `arnold/pipelines/_deliberation_example/_hooks.py`
+- `tests/arnold/pipelines/evidence_pack/test_pipelines.py`
+- `tests/arnold/pipelines/evidence_pack/test_end_to_end.py`
+- `tests/arnold/pipelines/evidence_pack/test_resume.py`
+- `tests/arnold/pipelines/evidence_pack/test_hooks.py`
+- `tests/arnold/pipelines/evidence_pack/test_steps.py`
+- `tests/arnold/conformance/test_evidence_pack_conformance.py`
+- `tests/arnold/pipeline/test_evidence_pack_expressibility.py`
+- `tests/arnold/pipeline/test_c4_authored_end_to_end.py`
+
+Actions:
+
+- Add a native declaration for the initial pipeline and a native declaration for the continuation pipeline.
+- Preserve the current human review semantics by wrapping the existing `HumanReviewStep` behavior, not by inventing a different suspension contract.
+- Keep `resume.py` and `EvidencePackHooks` working against the native runtime.
+- Update `_deliberation_example` to import the canonical human-review path that survives the migration.
+
+### 7. Convert registry, check, describe, and docs from graph-baseline to native-baseline
+
+Files to change:
+
+- `arnold/pipelines/megaplan/cli/__init__.py`
+- `scripts/generate_arnold_docs.py`
+- `tests/test_pipelines_check_validator.py`
+- `tests/test_pipeline_run_cli.py`
+- `tests/test_generate_arnold_docs.py`
+- `tests/arnold/pipelines/test_package_authoring_contract.py`
+- `tests/arnold/pipelines/test_authoring.py`
+- `tests/_pipeline/test_registry_python_discovery.py`
+- `tests/arnold/pipeline/test_registry.py`
+- `tests/test_pipeline_registry.py`
+
+Actions:
+
+- Make `arnold pipelines check` validate the actual native-first packages without temporary env mutation.
+- Make `megaplan run <pipeline> --describe` work from manifest-discovered, native-first package metadata.
+- Stop generating docs that describe graph pipelines as canonical.
+- Update authoring/registry tests so native-first packages are the contract.
+
+### 8. Replace graph-first parity harness and stale fixtures
+
+Files to change:
+
+- `tests/arnold/pipelines/megaplan/parity_harness.py`
+- `tests/arnold/pipelines/megaplan/test_native_parity.py`
+- `tests/arnold/pipelines/megaplan/test_native_parity_golden_traces.py`
+- `tests/arnold/pipelines/megaplan/test_graph_baseline.py`
+- `tests/arnold/pipelines/megaplan/test_legacy_pipeline_baseline.py`
+- `tests/test_pipeline_parity.py`
+- `tests/test_pipeline_planning_parity.py`
+- `tests/parity/test_graph_projection_parity.py`
+- `tests/arnold/pipeline/native/parity_trace.py`
+- `tests/arnold/pipelines/megaplan/data/native_parity/*.json`
+
+Actions:
+
+- Stop treating graph-executor traces as golden source of truth.
+- Regenerate parity fixtures from native execution where parity is still required.
+- Keep one explicit legacy-baseline suite until purge is complete; after purge, delete it.
+- Remove native tests that still force `ARNOLD_NATIVE_RUNTIME=1`.
+
+### 9. Purge graph-era Megaplan internals after all callers are gone
+
+Do not start this step early. It is intentionally last.
+
+Files and modules to remove or reduce sharply:
+
+- `arnold/pipelines/megaplan/_pipeline/_forward_m2_m3.py`
+- `arnold/pipelines/megaplan/_pipeline/_bridge.py`
+- `arnold/pipelines/megaplan/_pipeline/_BRIDGE_CALLERS.md`
+- `arnold/pipelines/megaplan/_pipeline/runtime.py`
+- `arnold/pipelines/megaplan/_pipeline/executor.py`
+- `arnold/pipelines/megaplan/_pipeline/builder.py`
+- `arnold/pipelines/megaplan/_pipeline/patterns.py`
+- `arnold/pipelines/megaplan/_pipeline/pattern_dynamic.py`
+- `arnold/pipelines/megaplan/_pipeline/subloop.py`
+- `arnold/pipelines/megaplan/_pipeline/resume.py`
+- `arnold/pipelines/megaplan/_pipeline/registry.py`
+- `arnold/pipelines/megaplan/operations.py`
+- `arnold/pipelines/megaplan/auto.py`
+- Inline legacy builder in `arnold/pipelines/megaplan/pipeline.py`
+
+Actions:
+
+- Move any remaining required compatibility helpers into one explicit compatibility module.
+- Delete env-gated policy runtime and graph fallback selection code.
+- Remove import-by-string or bridge callers before deleting modules.
+- Shrink `arnold/pipelines/megaplan/pipeline.py` to native composition plus temporary compatibility wrapper only if still needed.
+
+### 10. Final cleanup and dead-file purge
+
+Purge list:
+
+- `tests/test_execute_merge_creative.py`
+- Any untracked `_tmp_compute_hash.py`
+- Deprecated graph scaffold generator branch in `arnold/pipelines/megaplan/cli/__init__.py`
+- Stale graph-era wording in:
+  - `docs/arnold/examples/jokes.md`
+  - `docs/arnold/examples/select-tournament.md`
+  - `docs/arnold/package-authoring-contract.md`
+  - `docs/arnold/authoring-guide.md`
+- Any remaining docs or tests that require `ARNOLD_NATIVE_RUNTIME=1`
+- Any remaining docs or tests that force `ARNOLD_PIPELINE_RUNTIME=graph`
+
+## Validation checklist
+
+### Package-level validation
+
+- `pytest tests/arnold/pipelines/megaplan/test_creative_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_doc_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_jokes_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_live_supervisor_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_epic_blitz_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_select_tournament_native_parity.py`
+- `pytest tests/arnold/pipelines/megaplan/test_native_parity.py`
+- `pytest tests/arnold/pipelines/deliberation/test_native_parity.py`
+- `pytest tests/arnold/pipelines/evidence_pack`
+- `pytest tests/pipelines/test_folder_audit.py`
+
+### Platform validation
+
+- `pytest tests/arnold/pipeline/test_registry.py`
+- `pytest tests/arnold/pipeline/test_executor_selection.py`
+- `pytest tests/test_pipeline_registry.py`
+- `pytest tests/test_pipelines_check_validator.py`
+- `pytest tests/test_pipeline_run_cli.py`
+- `pytest tests/test_generate_arnold_docs.py`
+- `pytest tests/arnold/pipelines/test_package_authoring_contract.py`
+- `pytest tests/arnold/pipelines/test_authoring.py`
+
+### Regression validation
+
+- `pytest tests/arnold/pipeline tests/arnold/pipelines tests/_pipeline tests/pipelines`
+
+### CLI validation
+
+- `arnold pipelines check`
+- `megaplan run megaplan --describe`
+- `megaplan run creative --describe`
+- `megaplan run doc --describe`
+- `megaplan run epic-blitz --describe`
+- `megaplan run jokes --describe`
+- `megaplan run live-supervisor --describe`
+- `megaplan run select-tournament --describe`
+- `megaplan run writing-panel-strict --describe`
+- `megaplan run folder-audit --describe`
+- `megaplan run deliberation --describe`
+- `megaplan run evidence-pack --describe`
+
+All of the above must work without setting `ARNOLD_NATIVE_RUNTIME`, `ARNOLD_PIPELINE_RUNTIME`, or `MEGAPLAN_M6_MANIFEST_DISCOVERY`.
+
+## Risks
+
+- Human-gate behavior is the highest-risk migration surface. `writing_panel_strict`, `deliberation`, `evidence_pack`, and `megaplan` must preserve suspension and resume semantics exactly.
+- `evidence_pack` is the only remaining graph-only runtime package and is the largest implementation task.
+- `doc` fanout semantics can regress if native parallelism changes artifact shape; behavior-level assertions must replace graph-shape assertions.
+- Some parity infrastructure is graph-executor-shaped by design. Replacing it too early will hide regressions; replacing it too late will block purge.
+- `megaplan/_pipeline/*` is still load-bearing. Purge must be driven by import elimination, not by milestone labels.
+
+## Definition of done
+
+This migration is complete only when:
+
+- Every registered pipeline is native-first.
+- Every registered pipeline describes successfully through CLI.
+- `arnold pipelines check` passes without env flags.
+- `evidence_pack` no longer depends on graph-only builder/executor semantics.
+- Graph-era bridges and deprecated graph scaffolding are deleted.
+- The remaining tests and docs treat native execution as canonical.

codex