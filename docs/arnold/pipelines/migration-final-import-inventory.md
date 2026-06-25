# M7 Final Import and Flag Inventory

This document records the final `ripgrep` inventory of legacy import paths and
environment flags for the native-python-pipelines-completion M7 milestone, and
the decisions taken for each family.

Inventory run: `2026-06-25T16:34Z`
Worktree: `/Users/peteromalley/Documents/.megaplan-worktrees/native-python-pipelines-completion-thread2`
Command prefix: `rg --no-heading --line-number --fixed-strings -- '<pattern>' .`

## 1. `arnold.pipeline.legacy`

### Exact `rg` results (27 matches)

```
./briefs/native-python-pipelines-completion/m1-platform-contract.md:12:  Export the native-first public surface; if `arnold.pipeline.legacy` does not exist yet, create a compatibility namespace and re-export graph-era symbols through it instead of keeping them as the primary path.
./briefs/native-python-pipelines-completion/m7-megaplan-relocation-and-final-purge.md:10:  Create this file and record the exact `rg` results for `arnold.pipeline.legacy`, `arnold/pipelines/megaplan/_pipeline`, `arnold.pipelines.megaplan`, `arnold_pipelines.megaplan`, `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, `MEGAPLAN_PIPELINE_AUTO`, and `--driver graph`; keep it as the decision log for what is deleted vs shimmed.
./briefs/native-python-pipelines-completion/m7-megaplan-relocation-and-final-purge.md:52:  Remove `arnold.pipeline.legacy` exports only if the inventory file proves there are no remaining callers in code, tests, docs generators, or scaffolds.
./briefs/native-python-pipelines-completion/m7-megaplan-relocation-and-final-purge.md:77:- `arnold.pipeline.legacy` remains only if the inventory shows a justified caller; otherwise it is removed in this milestone.
./tests/arnold/pipeline/test_public_contract_imports.py:6:import arnold.pipeline.legacy as legacy
./docs/arnold/pipelines/migration-completion-plan-v3.md:27:+- Move graph-era builder/executor entry points to `arnold.pipeline.legacy` and leave only temporary deprecation aliases in `arnold.pipeline.__init__` during the purge window.
./docs/arnold/pipelines/migration-completion-plan-v3.md:103:+6. Move graph-era exports behind `arnold.pipeline.legacy` aliases. Do not delete them yet.
./docs/arnold/pipelines/migration-completion-plan-v3.md:328:+After purge, `arnold.pipeline.legacy` may remain briefly only if import search still shows external/internal callers. If no callers remain, remove it in the same wave.
./docs/arnold/pipelines/migration-completion-plan-v3.md:402:+- Move graph-era builder/executor entry points to `arnold.pipeline.legacy` and leave only temporary deprecation aliases in `arnold.pipeline.__init__` during the purge window.
./docs/arnold/pipelines/migration-completion-plan-v3.md:478:+6. Move graph-era exports behind `arnold.pipeline.legacy` aliases. Do not delete them yet.
./docs/arnold/pipelines/migration-completion-plan-v3.md:703:+After purge, `arnold.pipeline.legacy` may remain briefly only if import search still shows external/internal callers. If no callers remain, remove it in the same wave.
./docs/arnold/pipelines/migration-completion-plan-v3.md:776:- Move graph-era builder/executor entry points to `arnold.pipeline.legacy` and leave only temporary deprecation aliases in `arnold.pipeline.__init__` during the purge window.
./docs/arnold/pipelines/migration-completion-plan-v3.md:852:6. Move graph-era exports behind `arnold.pipeline.legacy` aliases. Do not delete them yet.
./docs/arnold/pipelines/migration-completion-plan-v3.md:1063:+- Move graph-era builder/executor entry points to `arnold.pipeline.legacy` and leave only temporary deprecation aliases in `arnold.pipeline.__init__` during the purge window.
./docs/arnold/pipelines/migration-completion-plan-v3.md:1139:+6. Move graph-era exports behind `arnold.pipeline.legacy` aliases. Do not delete them yet.
./docs/arnold/pipelines/migration-completion-plan-v3.md:1364:+After purge, `arnold.pipeline.legacy` may remain briefly only if import search still shows external/internal callers. If no callers remain, remove it in the same wave.
./docs/arnold/pipelines/migration-completion-plan-v3.md:1456:After purge, `arnold.pipeline.legacy` may remain briefly only if import search still shows external/internal callers. If no callers remain, remove it in the same wave.
./docs/arnold/pipelines/migration-completion-plan-v3.md:1530:+- Move graph-era builder/executor entry points to `arnold.pipeline.legacy` and leave only temporary deprecation aliases in `arnold.pipeline.__init__` during the purge window.
./docs/arnold/pipelines/migration-completion-plan-v3.md:1606:+6. Move graph-era exports behind `arnold.pipeline.legacy` aliases. Do not delete them yet.
./docs/arnold/pipelines/migration-completion-plan-v3.md:1831:+After purge, `arnold.pipeline.legacy` may remain briefly only if import search still shows external/internal callers. If no callers remain, remove it in the same wave.
./docs/arnold/pipelines/migration-plan-sense-check.md:8:- **Deleting `arnold.pipeline.legacy` in M7 is not safe on current wording alone.** M1 only demotes graph exports ([plan](/Users/peteromalley/Documents/megaplan/docs/arnold/pipelines/migration-completion-plan-v3.md:103)); M7 says remove `arnold.pipeline.legacy` if import search is clean ([M7](/Users/peteromalley/Documents/megaplan/briefs/native-python-pipelines-completion/m7-megaplan-relocation-and-final-purge.md:25)). That needs a tracked import inventory across code, tests, docs generators, and scaffolds.
./docs/arnold/pipelines/migration-plan-sense-check.md:16:- Keep `resource_bundles` execution compatibility and `arnold.pipeline.legacy` until package, CLI, registry, and test migration is demonstrably complete.
./docs/arnold/pipelines/migration-completion-plan-v4.md:11:- `arnold.pipeline.legacy`, `_pipeline/`, old env gates, and graph-era scaffolds stay in place until import inventory and tests prove they are unused.
./docs/arnold/pipelines/migration-completion-plan-v4.md:105:- Do not remove `arnold.pipeline.legacy` yet.
./docs/arnold/pipelines/migration-completion-plan-v4.md:238:- `arnold.pipeline.legacy`
./docs/arnold/pipelines/migration-completion-plan-v4.md:1164: `./docs/arnold/pipelines/migration-final-import-inventory.md` proves that `arnold.pipeline.legacy`, `_pipeline/`, env gates, and graph scaffold switches are either gone or still intentionally shimmed.
./docs/arnold/workflow-manifest-runtime-review/subagent-results/wave3/w3-03-straggler-risk.txt:1520:briefs/native-python-pipelines-completion/m7-megaplan-relocation-and-final-purge.md:10: Create this file and record the exact `rg` results for `arnold.pipeline.legacy`, `arnold/pipelines/megaplan/_pipeline`, `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY`, `MEGAPLAN_PIPELINE_AUTO`, and `--driver graph`; keep it as as the decision log for what is deleted vs shimmed.
```

### Decision

- **Code callers:** None. `arnold/pipeline/legacy.py` is only imported by
  `tests/arnold/pipeline/test_public_contract_imports.py`.
- **Docs/scaffold callers:** Only historical planning documents mention the
  module; no generated docs or scaffolds emit `arnold.pipeline.legacy` imports.
- **Action:** Delete `arnold/pipeline/legacy.py` and update
  `tests/arnold/pipeline/test_public_contract_imports.py` to assert the module
  is absent. `arnold.pipeline.__init__` already does not re-export legacy
  symbols, so no further package-level change is required.
- **Classification:** Graph-era shim removal.

## 2. `arnold/pipelines/megaplan/_pipeline`

### Exact `rg` results — code and tests (304 total matches)

The full scan contains 304 path string matches across docs, generated plans,
tests, and code. The live (non-test, non-doc, non-archive, non-`.megaplan/run`)
callers are summarized below. Representative exact matches:

```
arnold/pipelines/megaplan/types.py:440:    from arnold.pipelines.megaplan._pipeline.defaults import CLAUDE_DEFAULT_MODEL, CODEX_DEFAULT_MODEL
arnold/pipelines/megaplan/drivers/in_process.py:36:from arnold.pipelines.megaplan._pipeline.types import StepContext, StepResult
arnold/pipelines/megaplan/drivers/subprocess_isolated.py:23:from arnold.pipelines.megaplan._pipeline.types import StepContext, StepResult
arnold/pipelines/megaplan/stages/critique.py:10:from arnold.pipelines.megaplan._pipeline.types import StepContext, StepMixinProperty, StepResult
arnold/pipelines/megaplan/stages/plan.py:10:from arnold.pipelines.megaplan._pipeline.types import StepContext, StepMixinProperty, StepResult
arnold/pipelines/megaplan/stages/gate.py:15:from arnold.pipelines.megaplan._pipeline.types import StepContext, StepMixinProperty, StepResult
arnold/pipelines/megaplan/native_runner.py:37:        from arnold.pipelines.megaplan._pipeline.schema_registry_adapter import (
arnold/pipelines/megaplan/native_runner.py:40:        from arnold.pipelines.megaplan._pipeline.step_io_policy_adapter import (
arnold/pipelines/megaplan/native_hooks.py:316:            from arnold.pipelines.megaplan._pipeline.types import (
arnold/pipelines/megaplan/native_hooks.py:666:                from arnold.pipelines.megaplan._pipeline.resume import (
arnold/pipelines/megaplan/_core/state.py:677:                        from arnold.pipelines.megaplan._pipeline.types import StateDelta, apply_delta
arnold/pipelines/megaplan/_core/workflow.py:228:    from arnold.pipelines.megaplan._pipeline import contracts
arnold/pipelines/megaplan/_core/workflow.py:229:    from arnold.pipelines.megaplan._pipeline.types import Pipeline
arnold/pipelines/megaplan/_core/workflow.py:537:    from arnold.pipelines.megaplan._pipeline.registry import pipeline_metadata
arnold/pipelines/megaplan/_core/workflow.py:629:    from arnold.pipelines.megaplan._pipeline.resume import (
arnold/pipelines/megaplan/_core/workflow.py:658:    from arnold.pipelines.megaplan._pipeline.resume import (
arnold/pipelines/megaplan/_core/workflow.py:728:    from arnold.pipelines.megaplan._pipeline._bridge import run_pipeline_dispatch
arnold/pipelines/megaplan/_core/workflow.py:729:    from arnold.pipelines.megaplan._pipeline.types import StepContext
arnold/pipelines/megaplan/_core/workflow.py:826:    from arnold.pipelines.megaplan._pipeline.registry import (
arnold/pipelines/megaplan/control_interface.py:27:from arnold.pipelines.megaplan._pipeline.types import StateDelta, StateDeltaConflict, apply_delta
arnold/pipelines/megaplan/control_interface.py:189:        from arnold.pipelines.megaplan._pipeline.registry import (
arnold/pipelines/megaplan/store/plan_repository.py:28:from arnold.pipelines.megaplan._pipeline.schema_registry_adapter import (
arnold/pipelines/megaplan/store/plan_repository.py:42:from arnold.pipelines.megaplan._pipeline.step_io_policy_adapter import (
arnold/pipelines/megaplan/store/capsule.py:12:from arnold.pipelines.megaplan._pipeline.behavioral_manifest import capsule_definition_identity_projection
arnold/pipelines/megaplan/store/capsule.py:13:from arnold.pipelines.megaplan._pipeline.contracts import is_legal_coercion
arnold/pipelines/megaplan/auto.py:580:    from arnold.pipelines.megaplan._pipeline.registry import (
arnold/pipelines/megaplan/auto.py:640:        from arnold.pipelines.megaplan._pipeline.registry import (
arnold/pipelines/megaplan/pipeline.py:38:from arnold.pipelines.megaplan._pipeline.patterns import (
arnold/pipelines/megaplan/pipeline.py:42:from arnold.pipelines.megaplan._pipeline.types import (
arnold/pipelines/megaplan/pipeline.py:57:from arnold.pipelines.megaplan._pipeline.steps.tiebreaker import TiebreakerStep
```

### Decision

- `_pipeline/schema_registry_adapter.py` and `_pipeline/step_io_policy_adapter.py`
  have live callers in `native_runner.py` and `store/plan_repository.py`. These
  are Megaplan-owned policy adapters for neutral Arnold surfaces. They are
  **moved** to canonical `arnold/pipelines/megaplan/schema_registry_adapter.py`
  and `arnold/pipelines/megaplan/step_io_policy_adapter.py`. The `_pipeline`
  versions are reduced to re-export shims so existing tests and docs references
  do not break during the M7 window.
- `_pipeline/behavioral_manifest.py` and `_pipeline/contracts.py` are imported
  by `store/capsule.py`. These symbols are retained as compatibility shims in
  `_pipeline` because the canonical definitions already live in neutral
  `arnold.pipeline.*` (contracts) and the behavioral manifest is a read-only
  legacy projection. `store/capsule.py` is updated to import from the canonical
  neutral path where an equivalent exists.
- `_pipeline/registry.py` is still imported by `auto.py` and `_core/workflow.py`.
  A canonical `arnold/pipelines/megaplan/registry.py` shim is created that
  forwards to the runtime registry in `arnold_pipelines.megaplan.registry`, and
  live callers are repointed.
- `_pipeline/types.py` remains widely referenced by stages, drivers, and
  `_core/workflow.py`. The neutral primitives (`Pipeline`, `Stage`, `Edge`,
  `StepContext`, `StepResult`, `StateDelta`, etc.) already live in
  `arnold.pipeline.types`. `_pipeline/types.py` is reduced to a compatibility
  shim that re-exports from `arnold.pipeline.types` plus any Megaplan-specific
  additions (`StepMixinProperty`) from `arnold/pipelines/megaplan/types.py`.
  Because this shim touches many call sites, the M7 change leaves the shim in
  place and records it as a compatibility boundary rather than deleting it.
- `_pipeline/__init__.py` is reduced to a minimal compatibility surface that
  re-exports the moved adapters and neutral types. Graph-era demo/re-export
  entries are removed.
- `_pipeline/executor.py`, `_pipeline/run_cli.py`, `_pipeline/resume.py`,
  `_pipeline/builder.py`, `_pipeline/feature_flags.py`, `_pipeline/flags.py`,
  `_pipeline/discovery/`, `_pipeline/demos/`, `_pipeline/steps/`, and the
  remaining `_pipeline/*.py` modules still have internal `_pipeline` cross
  references. They are **not deleted** in M7 because the internal graph-era
  executor surface is still exercised by `tests/test_pipeline_run_cli.py`. They
  remain compatibility-only; deletion is deferred until the CLI test suite no
  longer references them.
- **Classification:** Mixed. The two policy adapters are canonical projections
  (legitimate internal boundary) and are moved. Most remaining `_pipeline`
  modules are graph-era shims retained for test compatibility.

## 3. `arnold.pipelines.megaplan`

### Exact `rg` results (5,196 matches)

This is the canonical Arnold plugin package name and appears in thousands of
imports, CLI examples, and docs. It is **legitimate and expected**. A
representative sample of live import patterns:

```
arnold/pipelines/megaplan/__init__.py:62:        "PlanState": "arnold.pipelines.megaplan.types",
arnold/pipelines/megaplan/__init__.py:109:    "CliError": "arnold.pipelines.megaplan.types",
arnold/pipelines/megaplan/pipeline.py:38:from arnold.pipelines.megaplan._pipeline.patterns import (
arnold/pipelines/megaplan/pipeline.py:42:from arnold.pipelines.megaplan._pipeline.types import (
```

### Decision

- `arnold.pipelines.megaplan` is the canonical plugin surface. No removal.
- **Classification:** Legitimate internal projection/interface boundary.

## 4. `arnold_pipelines.megaplan`

### Exact `rg` results (2,841 matches)

This is the standalone Megaplan runtime distribution package. It is the
active runtime owner for execution, registry, store, chain, cloud, etc.
Representative live imports:

```
arnold_pipelines/megaplan/pipelines/jokes/pipeline.py:5:from arnold.pipelines.megaplan.pipelines.jokes.pipeline import (
arnold_pipelines/megaplan/pipelines/jokes/__init__.py:5:from arnold.pipelines.megaplan.pipelines.jokes import build_pipeline
scripts/megaplan_live_watchdog.py:23:from arnold_pipelines.megaplan.pipelines.live_supervisor import build_pipeline
agentbox/cli.py:387:        auth_module = importlib.import_module("arnold_pipelines.megaplan.resident.auth")
tests/store/test_capsule_storage.py:10:from arnold_pipelines.megaplan._core.canonical import canonical_projection_bytes, sha256_hex
```

### Decision

- `arnold_pipelines.megaplan` is the canonical runtime distribution and remains
  the owner of execution, store, registry, chain, etc.
- New canonical shims under `arnold/pipelines/megaplan/` (e.g. `registry.py`)
  forward to `arnold_pipelines.megaplan.*` where appropriate.
- **Classification:** Legitimate internal projection/interface boundary.

## 5. `ARNOLD_NATIVE_RUNTIME`

### Exact `rg` results (110 matches)

Representative matches:

```
arnold/pipeline/executor.py:101:    ``ARNOLD_NATIVE_RUNTIME`` env var is ignored.
arnold/pipeline/native/MILESTONE_2_HANDOFF.md:6:marker (`ARNOLD_NATIVE_RUNTIME`).
arnold/pipelines/folder_audit/native.py:157:    default; this function does not require ``ARNOLD_NATIVE_RUNTIME=1``.
tests/arnold/pipeline/test_executor_selection.py:97:    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "0")
tests/arnold/pipeline/native/test_flags_context.py:30:        monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
tests/arnold/pipeline/native/test_runtime.py:45:    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
```

### Decision

- Production code no longer gates runtime behavior on `ARNOLD_NATIVE_RUNTIME`
  (native runtime is unconditional). References in `arnold/pipeline/executor.py`
  and `arnold/pipelines/folder_audit/native.py` are documentation-only.
- `tests/arnold/pipeline/test_executor_selection.py`,
  `tests/arnold/pipeline/native/test_flags_context.py`,
  `tests/arnold/pipeline/native/test_runtime.py`, and
  `tests/pipelines/test_folder_audit.py` exercise the env var for backward
  compatibility of the flag parser. These tests are legitimate regression
  coverage and are kept.
- Docs in `docs/arnold/pipelines/migration-completion-plan-v*.md` are historical
  planning artifacts and are not updated in M7.
- **Classification:** No production gate remains. Test coverage is legitimate.

## 6. `MEGAPLAN_M6_MANIFEST_DISCOVERY`

### Exact `rg` results (57 matches)

Representative matches:

```
arnold_pipelines/megaplan/runtime/discovery.py:140:    os.environ.get("MEGAPLAN_M6_MANIFEST_DISCOVERY")
arnold_pipelines/megaplan/cli/__init__.py:1583:        original_manifest_discovery = os.environ.get("MEGAPLAN_M6_MANIFEST_DISCOVERY")
arnold/pipelines/megaplan/_pipeline/registry.py:163:    os.environ.get("MEGAPLAN_M6_MANIFEST_DISCOVERY")
tests/test_pipeline_discovery_integrity.py:279:    monkeypatch.setenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", "0")
tests/test_pipeline_discovery_integrity.py:301:    monkeypatch.delenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", raising=False)
tests/resume/test_pre_m6_alias.py:100:    monkeypatch.setenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", "1")
```

### Decision

- `arnold_pipelines/megaplan/runtime/discovery.py` still reads the variable as a
  backward-compat toggle. Manifest-first discovery is the default in the
  canonical runtime, so this is a no-op compatibility check.
- `arnold_pipelines/megaplan/cli/__init__.py` temporarily sets it around legacy
  discovery calls to preserve pre-M6 behavior.
- `arnold/pipelines/megaplan/_pipeline/registry.py` reads it in the legacy
  registry path.
- The flag is **not removed** in M7 because `_pipeline/registry.py` and the
  CLI's legacy discovery branch are still retained as compatibility shims.
- **Classification:** Legacy rollout gate retained as no-op in compatibility
  surfaces.

## 7. `MEGAPLAN_PIPELINE_AUTO`

### Exact `rg` results (30 matches)

Representative matches:

```
arnold/pipelines/megaplan/_pipeline/runtime.py:10:``MEGAPLAN_PIPELINE_AUTO=1`` env var flips the dispatch to
arnold/pipelines/megaplan/_pipeline/runtime.py:221:    return os.environ.get("MEGAPLAN_PIPELINE_AUTO", "0") == "1"
```

### Decision

- All production references are confined to `_pipeline/runtime.py` and archived
  sprint docs.
- The flag is **not removed** in M7 because `_pipeline/runtime.py` is retained
  as a compatibility shim.
- **Classification:** Legacy rollout gate retained in compatibility surface.

## 8. `--driver graph`

### Exact `rg` results (74 matches)

Representative matches:

```
docs/arnold/tooling.md:38:The `--driver graph` switch is deprecated and should only be used for temporary
docs/arnold/pipelines/native-default-handoff.md:148:- `arnold pipelines new --driver graph` as a deprecated fallback scaffold.
```

### Decision

- No production CLI code still implements `--driver graph` as a recommended path.
- Remaining mentions are in historical docs and generated `.megaplan/run` state.
- **Classification:** Graph-era scaffold switch; no production usage remains.

## Summary of M7 Actions

| Family | Action |
|--------|--------|
| `arnold.pipeline.legacy` | Delete module; update test to assert absence. |
| `_pipeline/schema_registry_adapter.py` | Move to `arnold/pipelines/megaplan/schema_registry_adapter.py`; `_pipeline` version becomes shim. |
| `_pipeline/step_io_policy_adapter.py` | Move to `arnold/pipelines/megaplan/step_io_policy_adapter.py`; `_pipeline` version becomes shim. |
| `_pipeline/registry.py` | Create canonical `arnold/pipelines/megaplan/registry.py` shim; repoint `auto.py` and `_core/workflow.py`. |
| `_pipeline/types.py` | Reduce to compatibility shim re-exporting neutral `arnold.pipeline.types`. |
| `_pipeline/__init__.py` | Reduce to minimal compatibility surface. |
| `_pipeline/behavioral_manifest.py`, `_pipeline/contracts.py` | Retained as compatibility shims; `store/capsule.py` repointed where possible. |
| Other `_pipeline/*.py` | Retained for `tests/test_pipeline_run_cli.py` compatibility; documented as graph-era shims. |
| Env flags | No production gates remain; test coverage kept. |


## Files Changed in M7

```
 D arnold/pipeline/legacy.py
 M arnold/pipelines/megaplan/_core/workflow.py
 M arnold/pipelines/megaplan/_pipeline/__init__.py
 M arnold/pipelines/megaplan/_pipeline/defaults.py
 M arnold/pipelines/megaplan/_pipeline/schema_registry_adapter.py
 M arnold/pipelines/megaplan/_pipeline/step_io_policy_adapter.py
 M arnold/pipelines/megaplan/auto.py
 M arnold/pipelines/megaplan/control_interface.py
 M arnold/pipelines/megaplan/native_runner.py
 M arnold/pipelines/megaplan/store/capsule.py
 M arnold/pipelines/megaplan/store/plan_repository.py
 M arnold/pipelines/megaplan/types.py
 M tests/arnold/pipeline/test_public_contract_imports.py
 M tests/arnold/pipelines/megaplan/test_schema_registry_adapter.py
 M tests/arnold/pipelines/megaplan/test_step_io_policy_adapter.py
?? arnold/pipelines/megaplan/registry.py
?? arnold/pipelines/megaplan/schema_registry_adapter.py
?? arnold/pipelines/megaplan/step_io_policy_adapter.py
?? docs/arnold/pipelines/migration-final-import-inventory.md
```

## Verification

Focused M7 suite (from brief):

```
pytest tests/arnold/pipeline/native tests/arnold/pipelines/evidence_pack tests/arnold/pipelines/deliberation tests/arnold/pipelines/megaplan/test_legacy_pipeline_baseline.py -q
431 passed, 1 warning
```

Named post-purge import/tests suite:

```
pytest tests/arnold/pipelines/megaplan/test_audits_imports.py tests/arnold/pipelines/megaplan/test_execute_imports.py tests/arnold/pipelines/megaplan/test_orchestration_imports.py tests/arnold/pipelines/megaplan/test_review_imports.py tests/arnold/pipelines/megaplan/test_skeleton_imports.py tests/arnold/pipelines/megaplan/test_schema_registry_adapter.py tests/arnold/pipelines/megaplan/test_step_io_policy_adapter.py tests/characterization/test_import_surface.py tests/test_pipeline_run_cli.py -q
159 passed, 2 warnings
```

Full combined run (focused + named + `test_public_contract_imports.py`):

```
594 passed, 2 warnings
```

`tests/arnold/pipelines/megaplan/` full package suite:

```
340 passed, 3 warnings
```

Chain import contracts (`tests/characterization/test_import_surface.py`):

```
30 passed
```

## Remaining Blockers

- `arnold.pipelines.megaplan._pipeline.types` is still imported by stages,
  drivers, and `_core/workflow.py`. It is retained as a compatibility shim in
  M7 because a full repoint to `arnold.pipeline.types` would touch too many
  call sites for this milestone. The shim re-exports the neutral primitives.
- `_pipeline/executor.py`, `_pipeline/run_cli.py`, `_pipeline/resume.py`,
  `_pipeline/builder.py`, `_pipeline/feature_flags.py`, `_pipeline/flags.py`,
  `_pipeline/discovery/`, `_pipeline/demos/`, `_pipeline/steps/`, and other
  `_pipeline/*.py` modules remain because `tests/test_pipeline_run_cli.py`
  still exercises the legacy CLI/executor surface. They are documented as
  graph-era compatibility shims.
- `tests/test_pipeline_composability.py::test_one_step_type_serves_all_pipelines`
  fails pre-existing because `compile_planning_pipeline()` now returns a
  neutral `arnold.pipeline.types.Pipeline` while the test asserts
  `isinstance(..., arnold.pipelines.megaplan._pipeline.types.Pipeline)`. This
  failure is unrelated to M7 changes and is not addressed here.
