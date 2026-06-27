# Arnold Pipeline Migration Completion Plan V4

## Decision

The end-state is still native-first, but V4 fixes the rollout sequence:

- `build_pipeline(...)` returns a projected `Pipeline` compatibility shell.
- That shell must carry a first-class `native_program` field once a package is migrated.
- During the migration window, executor and runner code must prefer `Pipeline.native_program` but continue to honor the old `resource_bundles` execution payload when an unmigrated package still depends on it.
- Canonical Megaplan gets its own migration milestone before test cleanup.
- `arnold.pipeline.legacy`, `_pipeline/`, old env gates, and graph-era scaffolds stay in place until import inventory and tests prove they are unused.

V3 was directionally right but too aggressive in M1. The platform contract, canonical Megaplan migration, test cleanup, and destructive purge need to be sequenced explicitly.

## Sense-Check Fixes Baked Into V4

1. M1 is now a transition milestone, not a purge milestone.
   `native_program` lands early; bundle-based execution fallback remains until later milestones remove package dependencies on it.
2. Canonical Megaplan is scheduled explicitly as M3.5.
   `arnold/pipelines/megaplan/pipeline.py`, `native_runner.py`, and `auto.py` are no longer assumed to "come along for free" inside package cleanup.
3. Every milestone is executable from-doc.
   The briefs now name exact code files, tests, and generated-doc artifacts.
4. M5 names the old-contract suites directly.
   Parity, graph-baseline, native-parity, and golden-trace suites are enumerated instead of referenced loosely.
5. M7 requires a tracked import inventory before legacy deletion.
   No late-stage "if grep is clean" hand-wave. The inventory itself is a deliverable.

## End-State Contract

### 1. Public API

- `arnold.pipeline` is native-first.
- `Pipeline.native_program` is the canonical execution artifact on projected shells.
- Graph-era exports remain available only through explicit compatibility surfaces until M7.

### 2. Package Contract

Each migrated package converges on:

```text
arnold/pipelines/<package>/
├── __init__.py
├── pipeline.py
├── steps.py
└── _legacy.py   # only when a temporary baseline suite still needs it
```

Rules:

- `build_pipeline(...)` compiles the native declaration, projects the graph shell, attaches `native_program`, and returns the projected `Pipeline`.
- `driver` is `("native", "<kind>")`.
- `default_profile` and `supported_modes` are required package metadata.
- `resource_bundles` holds prompt/resource bundles only once the migration is complete. Until then, compatibility payloads are tolerated but must be treated as deprecated.

### 3. Discovery, Registry, and CLI

- Manifest-first discovery is the default path in M1 and the only path after M7.
- `arnold pipelines describe <name>` and `megaplan run <name> --describe` resolve through the same metadata contract.
- `arnold pipelines new` becomes native-first in M6; graph scaffold compatibility is deleted in M7 after docs and tests are clean.

### 4. Runtime and Resume

- Shared native suspension and resume are the long-term contract.
- Canonical Megaplan, `writing_panel_strict`, `deliberation`, and `evidence_pack` must all converge on the same runtime resume semantics.

### 5. Testing

- Native traces become the golden source only after package migrations and canonical Megaplan migration are complete.
- One explicit legacy baseline suite may survive through M5 and M6.
- Final legacy test removal happens in M7 after import inventory and docs are clean.

## Execution Order

### M1. Platform contract transition

Goal:

- Add `Pipeline.native_program`.
- Teach executor, registry, validator, discovery, and CLI to prefer the native-first contract.
- Keep `resource_bundles` execution compatibility and env-flag compatibility as temporary shims.

Key files:

- `arnold/pipeline/types.py`
- `arnold/pipeline/__init__.py`
- `arnold/pipeline/registry.py`
- `arnold/pipeline/validator.py`
- `arnold/pipeline/discovery/manifest.py`
- `arnold/pipeline/native/__init__.py`
- `arnold/pipeline/native/compiler.py`
- `arnold/pipeline/native/runtime.py`
- `arnold/pipeline/native/flags.py`
- `arnold/pipeline/native/graph_projection.py`
- `arnold/pipeline/builder.py`
- `arnold/pipeline/executor.py`
- `arnold/pipeline/resume.py`
- `arnold/pipelines/megaplan/cli/__init__.py`
- `arnold/pipelines/megaplan/cli/arnold.py`
- `arnold/pipelines/megaplan/cli/parser.py`

Do not do in M1:

- Do not ban bundle-based execution payloads outright.
- Do not delete `_MEGAPLAN_NATIVE_STAGE_ORDER` or other canonical-Megaplan heuristics yet.
- Do not remove `arnold.pipeline.legacy` yet.
- Do not delete `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, or `MEGAPLAN_PIPELINE_AUTO` references until M7 inventory proves they are gone.

### M2. Megaplan subpipeline layout normalization

Goal:

- Normalize `writing_panel_strict` and `select_tournament` into stable package paths before behavior-heavy migrations.

Key files:

- `arnold/pipelines/megaplan/pipelines/writing_panel_strict.py`
- `arnold/pipelines/megaplan/pipelines/writing-panel-strict/**`
- `arnold/pipelines/megaplan/pipelines/select-tournament/**`
- new `arnold/pipelines/megaplan/pipelines/writing_panel_strict/**`
- new `arnold/pipelines/megaplan/pipelines/select_tournament/**`

### M3. Shared and root package migrations

Goal:

- Migrate the package set that is already close to the final contract:
  `creative`, `doc`, `jokes`, `live_supervisor`, `writing_panel_strict`, `epic_blitz`, `select_tournament`, `folder_audit`, `deliberation`.

Key rule:

- Every migrated package returns a projected shell with `native_program`.
- Legacy graph builders become private baselines only.

### M3.5. Canonical Megaplan migration

Goal:

- Migrate canonical `megaplan` itself before test cleanup.

Key files:

- `arnold/pipelines/megaplan/pipeline.py`
- `arnold/pipelines/megaplan/native_runner.py`
- `arnold/pipelines/megaplan/auto.py`
- `arnold/pipelines/megaplan/__init__.py`
- `arnold/pipelines/megaplan/_compatibility.py`
- `arnold/pipelines/megaplan/cli/arnold.py`
- `arnold/pipelines/megaplan/cli/parser.py`
- `arnold/pipeline/native/routing.py`

This is the milestone that removes canonical Megaplan's stage-order strings, legacy topology-hash pinning assumptions, and runner dependence on bundle-carried execution metadata.

### M4. Evidence pack native migration

Goal:

- Migrate `evidence_pack` onto the same native execution and resume contract used everywhere else.

Key files:

- `arnold/pipelines/evidence_pack/__init__.py`
- new `arnold/pipelines/evidence_pack/pipeline.py`
- `arnold/pipelines/evidence_pack/steps.py`
- `arnold/pipelines/evidence_pack/pipelines.py`
- `arnold/pipelines/evidence_pack/hooks.py`
- `arnold/pipelines/evidence_pack/resume.py`
- `arnold/pipelines/evidence_pack/verifier.py`
- `arnold/pipelines/_deliberation_example/**`

### M5. Native test and golden-trace cleanup

Goal:

- Rewrite old-contract test suites so native truth becomes canonical.
- Keep only one explicit legacy baseline suite until M7.

Named old-contract suites:

- `tests/parity/test_graph_projection_parity.py`
- `tests/parity/test_no_state_carry.py`
- `tests/test_pipeline_parity.py`
- `tests/test_pipeline_planning_parity.py`
- `tests/test_workflow_topology_parity.py`
- `tests/test_workflow_topology_parity_gate.py`
- `tests/editorial_parity.py`
- `tests/_pipeline/test_planning_discovered_parity.py`
- `tests/_pipeline/test_receipt_planning_parity.py`
- `tests/arnold/pipeline/native/test_graph_parity.py`
- `tests/arnold/pipeline/native/test_runtime_parity.py`
- `tests/arnold/pipeline/test_model_seam_parity.py`
- `tests/arnold/pipelines/deliberation/test_native_parity.py`
- `tests/arnold/pipelines/megaplan/test_creative_native_parity.py`
- `tests/arnold/pipelines/megaplan/test_doc_native_parity.py`
- `tests/arnold/pipelines/megaplan/test_epic_blitz_native_parity.py`
- `tests/arnold/pipelines/megaplan/test_jokes_native_parity.py`
- `tests/arnold/pipelines/megaplan/test_live_supervisor_native_parity.py`
- `tests/arnold/pipelines/megaplan/test_select_tournament_native_parity.py`
- `tests/arnold/pipelines/megaplan/test_writing_panel_strict_native_parity.py`
- `tests/arnold/pipelines/megaplan/test_native_execution_parity_fixtures.py`
- `tests/arnold/pipelines/megaplan/test_native_parity.py`
- `tests/arnold/pipelines/megaplan/test_native_parity_golden_traces.py`
- `tests/arnold/pipelines/megaplan/test_graph_baseline.py`
- `tests/arnold/pipelines/megaplan/test_legacy_pipeline_baseline.py`
- `tests/arnold/pipelines/megaplan/test_parity_harness.py`
- `tests/arnold/pipelines/megaplan/test_step_contracts_parity.py`

### M6. Docs and scaffolds native-first

Goal:

- Make authored docs, generated docs, and scaffolds teach only the native-first contract.

Key files:

- `docs/arnold/package-authoring-contract.md`
- `docs/arnold/package-contract.md`
- `docs/arnold/authoring-guide.md`
- `docs/arnold/creating-a-new-pipeline.md`
- `docs/arnold/examples/jokes.md`
- `docs/arnold/examples/select-tournament.md`
- `docs/reference/arnold-projections.md`
- `scripts/generate_arnold_docs.py`
- `arnold/pipelines/_authoring.py`
- `arnold/pipelines/_template/__init__.py`
- `arnold/pipelines/_template/pipelines.py`
- `arnold/pipelines/_template/SKILL.md`

### M7. Megaplan relocation and final purge

Goal:

- Move remaining live Megaplan runtime helpers out of `_pipeline/`.
- Produce a final import inventory.
- Delete legacy surfaces only after that inventory is clean.

Required inventory:

- `arnold.pipeline.legacy`
- `arnold/pipelines/megaplan/_pipeline/*`
- `ARNOLD_NATIVE_RUNTIME`
- `MEGAPLAN_M6_MANIFEST_DISCOVERY`
- `MEGAPLAN_PIPELINE_AUTO`
- `--driver graph`

Required artifact:

- `docs/arnold/pipelines/migration-final-import-inventory.md`

Destructive deletion rule:

- If the inventory is not clean, convert the remaining surface to an explicit shim and keep it for another pass. Do not delete first and investigate later.

## Milestone Dependencies

- M1 has no dependencies.
- M2 depends on M1.
- M3 depends on M1 and M2.
- M3.5 depends on M1, M2, and M3.
- M4 depends on M1 and M3.5.
- M5 depends on M3, M3.5, and M4.
- M6 depends on M5.
- M7 depends on M6 and the M7 import inventory being clean.

## Final Verification Checklist

1. Every migrated package returns a projected `Pipeline` with non-null `native_program`.
2. Executor and runners prefer `native_program`; bundle-based execution is either gone or isolated to documented compatibility shims.
3. `arnold pipelines describe <name>` works for canonical Megaplan and every migrated package.
4. `megaplan run <name> --describe` works through the same metadata and native-backed contract.
5. Canonical Megaplan native runtime, auto drive, and resume flows work without stage-order heuristics.
6. `evidence_pack` uses shared native suspension and resume.
7. Native traces are the canonical goldens; only one intentional legacy suite survives before M7.
8. Docs and scaffolds no longer instruct users to set `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, or `--driver graph`.
9. `docs/arnold/pipelines/migration-final-import-inventory.md` proves that `arnold.pipeline.legacy`, `_pipeline/`, env gates, and graph scaffold switches are either gone or still intentionally shimmed.
10. Final purge happens only after items 1 through 9 are satisfied.
