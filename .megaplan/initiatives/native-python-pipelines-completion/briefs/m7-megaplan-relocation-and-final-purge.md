# M7 - Megaplan Relocation And Final Purge

## Objective

Finish the migration by inventorying every remaining legacy import and flag, moving any still-live Megaplan runtime ownership out of `_pipeline/`, and deleting compatibility surfaces only after the inventory and the named tests prove the tree is clean.

## Files To Change And Instructions

- `docs/arnold/pipelines/migration-final-import-inventory.md`
  Create this file and record the exact `rg` results for `arnold.pipeline.legacy`, `arnold/pipelines/megaplan/_pipeline`, `arnold.pipelines.megaplan`, `arnold_pipelines.megaplan`, `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, `MEGAPLAN_PIPELINE_AUTO`, and `--driver graph`; keep it as the decision log for what is deleted vs removed from the authoring/runtime surface. The inventory must distinguish graph-era compatibility shims from legitimate internal projection/interface boundaries.
- `arnold/pipelines/megaplan/_pipeline/__init__.py`
  Reduce to a minimal compatibility surface or delete it if the import inventory proves nothing still needs it.
- `arnold/pipelines/megaplan/_pipeline/types.py`
  Move any still-live runtime types to `arnold/pipelines/megaplan/types.py`; keep only a compatibility shim if the inventory says callers still exist.
- `arnold/pipelines/megaplan/_pipeline/registry.py`
  Move live registry behavior to `arnold/pipelines/megaplan/registry.py` and keep this module only as a shim if the inventory demands it.
- `arnold/pipelines/megaplan/_pipeline/runtime.py`
  Move live runtime behavior into `arnold/pipelines/megaplan/runtime/` and leave only a shim if required.
- `arnold/pipelines/megaplan/_pipeline/run_cli.py`
  Delete or shim only after CLI callers have been migrated.
- `arnold/pipelines/megaplan/_pipeline/resume.py`
  Delete or shim only after shared native resume has replaced all call sites.
- `arnold/pipelines/megaplan/_pipeline/builder.py`
  Delete or shim only after no builder call sites remain in the inventory.
- `arnold/pipelines/megaplan/_pipeline/executor.py`
  Delete or shim only after executor callers are gone.
- `arnold/pipelines/megaplan/_pipeline/feature_flags.py`
  Remove only after the inventory proves all legacy env gates are gone.
- `arnold/pipelines/megaplan/_pipeline/flags.py`
  Remove only after the inventory proves all legacy flag references are gone.
- `arnold/pipelines/megaplan/_pipeline/schema_registry_adapter.py`
  Move live behavior to the canonical package location or delete if dead.
- `arnold/pipelines/megaplan/_pipeline/step_io_policy_adapter.py`
  Move live behavior to the canonical package location or delete if dead.
- `arnold/pipelines/megaplan/_pipeline/artifact_adapter.py`
  Move live behavior to the canonical package location or delete if dead.
- `arnold/pipelines/megaplan/_pipeline/discovery/__init__.py`
  Delete or shim only after discovery imports are migrated.
- `arnold/pipelines/megaplan/_pipeline/discovery/trust.py`
  Delete or shim only after trust-gate imports are migrated.
- `arnold/pipelines/megaplan/types.py`
  Receive active runtime types moved out of `_pipeline/types.py`.
- `arnold/pipelines/megaplan/registry.py`
  Create or expand as the canonical home for active registry behavior formerly under `_pipeline/registry.py`.
- `arnold/pipelines/megaplan/runtime/__init__.py`
  Create or expand the canonical runtime home for behavior moved out of `_pipeline/runtime.py`.
- `arnold/pipelines/megaplan/discovery/__init__.py`
  Create or expand the canonical discovery home for behavior moved out of `_pipeline/discovery/`.
- `arnold/pipelines/megaplan/_compatibility.py`
  Keep only the compatibility shims that survive the import inventory; delete the rest.
- `arnold/pipeline/__init__.py`
  Remove `arnold.pipeline.legacy` exports only if the inventory file proves there are no remaining callers in code, tests, docs generators, or scaffolds.
- `tests/arnold/pipelines/megaplan/test_audits_imports.py`
  Update import-surface assertions to the final post-purge locations.
- `tests/arnold/pipelines/megaplan/test_execute_imports.py`
  Update import coverage after `_pipeline` execution helpers move or disappear.
- `tests/arnold/pipelines/megaplan/test_orchestration_imports.py`
  Update import coverage after runtime relocation.
- `tests/arnold/pipelines/megaplan/test_review_imports.py`
  Update import coverage after runtime relocation.
- `tests/arnold/pipelines/megaplan/test_skeleton_imports.py`
  Update import coverage after scaffold and compatibility cleanup.
- `tests/arnold/pipelines/megaplan/test_schema_registry_adapter.py`
  Repoint the suite to the final canonical module locations.
- `tests/arnold/pipelines/megaplan/test_step_io_policy_adapter.py`
  Repoint the suite to the final canonical module locations.
- `tests/characterization/test_import_surface.py`
  Update or narrow the public import-surface contract to the final intended
  survivors. This suite is a hard gate for de-facto public Megaplan surfaces,
  including `arnold_pipelines.megaplan` store, workers, cli, chain, execute,
  agent runtime, cloud modules, and private-but-used chain helpers.
- `tests/test_pipeline_run_cli.py`
  The full suite must pass or each intentional compatibility break must be
  recorded in the inventory with migration guidance. Do not limit this to CLI
  describe: preserve run behavior for runtime/executor flags, vendor/profile
  options, manifest/runtime identity, registered non-Megaplan pipelines, and
  creative-only argument validation.

## Verifiable Completion Criterion

- `docs/arnold/pipelines/migration-final-import-inventory.md` exists and shows the final status of every legacy import and flag family.
- The inventory covers both `arnold.pipelines.megaplan.*` and
  `arnold_pipelines.megaplan.*` import surfaces, not only `_pipeline`.
- No file named above is deleted unless the inventory proves it has no remaining callers or can safely be reduced to a shim.
- `_pipeline/` no longer owns active runtime behavior; anything that remains is explicitly documented as compatibility only.
- `arnold.pipeline.legacy` remains only if the inventory shows a justified caller; otherwise it is removed in this milestone.
- `_pipeline/resume.py` is not deleted until existing Megaplan resume file
  surfaces pass through `arnold.pipeline.resume` or have explicit migration
  diagnostics covered by tests.
- Chain import contracts and PR helper behavior remain covered by
  `tests/characterization/test_import_surface.py`; destructive relocation must
  not break `ChainState`, `save_chain_state`, `load_chain_state`,
  `_capture_sync_state`, `_ensure_milestone_pr`, `_commit_and_push_phase`, or
  `_enable_auto_merge` without a deliberate compatibility decision.
- The purge does not delete legitimate internal projection/interface boundaries
  that implement the native contract. "No shims" means no graph-era fallback,
  `_legacy.py`, `_pipeline`, opt-in flag, or compatibility authoring pattern;
  it does not forbid an internal facade/projection layer when that layer is the
  canonical way to expose the native interface.

## Native Representation Alignment

- Matrix rows affected: Canonical source path reconciliation; Behavior parity with existing Megaplan; Source readability.
- Expected status change: substrate `enabled` by proving reviewers and runtime call sites agree on the canonical source/import surface.
- Proof artifacts: final import inventory, `rg` results for legacy flags/imports, import-surface characterization tests, and CLI/run smoke tests.
- Completion-manifest gate: before this chain can hand off to composition,
  implement and produce
  `.megaplan/initiatives/native-python-pipelines-completion/completion-manifest.json`
  with schema `arnold.megaplan.chain_completion_manifest.v1`. The manifest must
  bind the current chain spec, `NORTHSTAR.md`, ordered milestone labels, every
  completion milestone brief path and SHA-256, completed plan names, merged PR
  numbers/states/merge SHAs, final `done` statuses, and declared proof artifact
  paths plus SHA-256 hashes. `native-composition-followup` must keep
  `require_manifest: true` on its prerequisite and fail launch if this manifest
  is absent or stale.
- False-pass guard: deleting `_pipeline` or compatibility modules without proving callers moved can break resume/chain behavior while appearing clean.
- Doctrine guard: `Source readability` remains substrate/source-path proof in
  this completion milestone. It is not report conformance unless composition M6
  structural conformance, handler-purity, mutation tests, rendered policy view,
  and source-authority proof pass.
- Deferrals: if any compatibility path survives, it must be marked internal/deprecated and must not hide product routing or handler-owned semantics.
- Canonical paths/imports: this milestone owns the authoritative reconciliation table for `arnold.*`, `arnold_pipelines.*`, CLI, chain, resume, and PR helper surfaces.

## Risks And Blockers

- This milestone is destructive and must not start from assumption.
- Import inventory can uncover test, docs-generator, or scaffold references long after runtime code is clean.
- Over-deleting here can strand external or internal callers that were hidden behind generated docs or template code.

## Dependencies

- Depends on M6.
- Final milestone only.
- Legacy code, flags, and shims must stay in place until the import inventory and named tests prove the tree is clean.
