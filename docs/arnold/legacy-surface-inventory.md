# Legacy Megaplan Surface Inventory (M4 Phase 1)

> **Scope:** Active legacy surfaces that reference `arnold.pipelines.megaplan` or its historical aliases (`megaplan`, `arnold.pipeline`, `arnold.runtime`).
> **Owner:** `m4-megaplan-product-migration`
> **Base:** `origin/main` at `cede284f65dfdbb3511f9c9e9f7f8d296fc48960`
> **Plan:** `.megaplan/plans/m4-megaplan-product-migration/plan_v1.md`

## Classification legend

| Class | Meaning | Expiry convention |
| --- | --- | --- |
| `move` | Relocate to `arnold_pipelines.megaplan` in M4 Phase 2; behavior unchanged. | M4 |
| `temporary M4 parity shim` | Kept in legacy location to preserve CLI/tests/adapters during M4; forwards to new package or retains legacy behavior. | M6 |
| `read-only migration input` | Read by migration tooling in M4 Phase 4/5; never mutated by new runtime. | M6 archive |
| `M6 delete` | Deletion target after parity is proven and in-flight runs are drained. | M6 |
| `non-legacy neutral surface` | Owned by neutral Arnold (`arnold.execution`, `arnold.workflow`, `arnold.kernel`, `arnold.agent`, `arnold.conformance`); must not import product package. | permanent |

## 1. `arnold/pipelines/megaplan/` top-level product surface

| Path / group | Class | Owner | Blocker | Expiry |
| --- | --- | --- | --- | --- |
| `arnold/pipelines/megaplan/__init__.py` | `temporary M4 parity shim` | megaplan | plugin registry still scans `arnold/pipelines` first; must keep alias until M6 | M6 |
| `arnold/pipelines/megaplan/__main__.py` | `temporary M4 parity shim` | megaplan | CLI entry `python -m arnold.pipelines.megaplan` used in docs/scripts | M6 |
| `arnold/pipelines/megaplan/_compatibility.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/pipeline.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/routing.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/types.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/flags.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/control.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/control_interface.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/model_seam.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/run_outcome.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/step_contracts.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/policy_settings.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/artifacts.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/auto.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/auto_escalation.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/blocker_recovery.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/briefs.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/judge_manifest.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/operations.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/pipeline_contracts.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/quality_resolutions.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/resolution_contract.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/resolutions.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/schema_seeds.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/template_registry.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/user_actions.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/SKILL.md` | `M6 delete` | megaplan | skill metadata duplicated in `.agents/skills/megaplan` | M6 |

## 2. Core engine (`arnold/pipelines/megaplan/_core/`)

| Path / group | Class | Owner | Blocker | Expiry |
| --- | --- | --- | --- | --- |
| `arnold/pipelines/megaplan/_core/__init__.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/activation.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/canonical.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/config_resolver.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/dispatch.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/hermes_fanout.py` | `move` | megaplan | imports vendored `agent/` runtime | M4 |
| `arnold/pipelines/megaplan/_core/io.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/modes.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/phase_runtime.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/process_fanout.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/registries.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/scheduler/` | `move` | megaplan | generic scheduler; disposition already `arnold-core` in `package-disposition.md`, but still physically moved in M4 | M4 |
| `arnold/pipelines/megaplan/_core/state.py` | `temporary M4 parity shim` | megaplan | legacy `state.json` writes/read; new runtime uses journal projection | M6 |
| `arnold/pipelines/megaplan/_core/state_store.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/topology.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/user_config.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/worker_fanout.py` | `move` | megaplan | imports `agent/` runtime; keep parity adapter | M4 |
| `arnold/pipelines/megaplan/_core/workflow.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_core/workflow_data.py` | `move` | megaplan | none | M4 |

## 3. Legacy pipeline runtime (`arnold/pipelines/megaplan/_pipeline/`)

| Path / group | Class | Owner | Blocker | Expiry |
| --- | --- | --- | --- | --- |
| `arnold/pipelines/megaplan/_pipeline/__init__.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/_bridge.py` | `temporary M4 parity shim` | megaplan | bridge between legacy `Pipeline` and M3 `WorkflowManifest`; referenced by `_BRIDGE_CALLERS.md` | M6 |
| `arnold/pipelines/megaplan/_pipeline/_forward_m2_m3.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/adapter.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/artifact_adapter.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/artifacts.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/behavioral_manifest.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/builder.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/contracts.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/defaults.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/dispatch*.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/envelope.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/eval_judge_wrapper.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/executor.py` | `temporary M4 parity shim` | megaplan | 19+ legacy callers still import `run_pipeline` / `run_pipeline_with_policy` (see Bridge Callers) | M6 |
| `arnold/pipelines/megaplan/_pipeline/faults.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/feature_flags.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/flags.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/hooks.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/judge_manifest*.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/loop_node.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/override.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/pattern*.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/planning*.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/preflight.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/profile.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/prompts.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/receipt.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/registry.py` | `temporary M4 parity shim` | megaplan | legacy dispatcher allowlist `_BRIDGED_PIPELINES` | M6 |
| `arnold/pipelines/megaplan/_pipeline/resume.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/run_cli.py` | `temporary M4 parity shim` | megaplan | legacy `megaplan run` CLI path | M6 |
| `arnold/pipelines/megaplan/_pipeline/runtime.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/schema_registry_adapter.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/step_helpers.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/step_io_policy_adapter.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/subloop.py` | `temporary M4 parity shim` | megaplan | child-pipeline execution not yet bridge-compatible | M6 |
| `arnold/pipelines/megaplan/_pipeline/taint.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/types.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/validator.py` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/_pipeline/demos/` | `M6 delete` | megaplan | demo entries not bridged; `demo_judges.py`, `demos/doc_critique.py`, `demos/tournament.py` | M6 |
| `arnold/pipelines/megaplan/_pipeline/discovery/` | `move` | megaplan | `trust.py` is `arnold-core` disposition but moved physically in M4 | M4 |
| `arnold/pipelines/megaplan/_pipeline/steps/` | `move` | megaplan | legacy step implementations | M4 |
| `arnold/pipelines/megaplan/_pipeline/m5-wrapper-eval.judge.json` | `M6 delete` | megaplan | generated judge fixture | M6 |
| `arnold/pipelines/megaplan/_pipeline/pipeline_ids.json` | `read-only migration input` | megaplan | legacy pipeline ID registry used for alias mapping | M6 archive |

### 3.1 Bridge caller list

The canonical bridge path is `arnold/pipelines/megaplan/_pipeline/_bridge.py` (not `arnold/pipeline/_bridge.py`).
The bridge caller inventory is maintained in `arnold/pipelines/megaplan/_pipeline/_BRIDGE_CALLERS.md`.  Key callers:

| Symbol | Caller module | Status | Blocker |
| --- | --- | --- | --- |
| `run_pipeline` | `megaplan/_pipeline/run_cli.py` | repointed in M1 | none |
| `run_pipeline` | `megaplan/_pipeline/demo_judges.py` | legacy | demo entry not bridged |
| `run_pipeline` | `megaplan/_pipeline/subloop.py` | legacy | child-pipeline execution |
| `run_pipeline` | `megaplan/_pipeline/demos/doc_critique.py` | legacy | demo entry |
| `run_pipeline` | `megaplan/cli/__init__.py` (`_resume_human_gate`) | legacy | resume redesign deferred |
| `run_pipeline` | `megaplan/_pipeline/registry.py` | legacy | bare dispatcher path |
| `run_pipeline_with_policy` | `megaplan/_pipeline/registry.py` | legacy | profile path |
| `run_pipeline_with_policy` | `tests/test_pipeline_runnable_e2e.py` | legacy | test migration |
| `run_pipeline_with_policy` | `tests/characterization/test_pipeline_golden.py` | legacy | golden test migration |
| `run_pipeline_with_policy` | `tests/test_pipeline_planning_parity.py` | legacy | parity test migration |
| `run_pipeline_with_policy` | `tests/test_pipeline_composability.py` | legacy | composability migration |
| `run_pipeline_with_policy` | `tests/test_pipeline_runtime_e2e.py` | legacy | runtime E2E migration |
| `run_pipeline_with_policy` | `tests/test_auto_pipeline_runtime.py` | legacy | auto runtime migration |
| `run_pipeline_with_policy` | `tests/test_mechanical_gate_e2e.py` | legacy | gate E2E migration |
| `run_pipeline_with_policy` | `tests/_pipeline/*`, `tests/pipelines/*`, additional test modules | legacy | broad test migration |

## 4. Product subsystems

| Path / group | Class | Owner | Blocker | Expiry |
| --- | --- | --- | --- | --- |
| `arnold/pipelines/megaplan/handlers/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/stages/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/execute/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/review/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/orchestration/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/planning/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/prompts/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/forms/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/routing/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/profiles/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/workers/` | `move` | megaplan | imports `agent/` runtime; parity adapter | M4 |
| `arnold/pipelines/megaplan/drivers/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/audits/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/receipts/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/tickets/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/editorial/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/store/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/schemas/` | `move` | megaplan | `arnold-core` disposition per `package-disposition.md`; moved physically in M4 | M4 |
| `arnold/pipelines/megaplan/bakeoff/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/calibration/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/chain/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/cli/` | `move` | megaplan | old CLI surface; new projections added in M4 Phase 4 | M4 |
| `arnold/pipelines/megaplan/cloud/` (except `_reference`) | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/cloud/_reference/` | `M6 delete` | megaplan | generated reference debris; already excluded from wheel/sdist | M6 |
| `arnold/pipelines/megaplan/data/` (except `_codex_skills`) | `move` | megaplan | product data fixtures/templates | M4 |
| `arnold/pipelines/megaplan/data/_codex_skills/` | `M6 delete` | megaplan | generated skill cache | M6 |
| `arnold/pipelines/megaplan/observability/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/pricing/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/resident/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/runtime/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/supervisor/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/watchdog/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/loop/` | `move` | megaplan | none | M4 |
| `arnold/pipelines/megaplan/pipelines/` | `move` | megaplan | none | M4 |

## 5. Vendored / generated debris

| Path / group | Class | Owner | Blocker | Expiry |
| --- | --- | --- | --- | --- |
| `arnold/pipelines/megaplan/agent/` | `M6 delete` (vendored) | megaplan | full Hermes/agent runtime vendored under product tree; neutral `arnold/agent/` now owns equivalent surfaces | M6 |
| `arnold/pipelines/megaplan/agent/.github/` | `M6 delete` | megaplan | upstream issue/CI templates | M6 |
| `arnold/pipelines/megaplan/agent/tests/` | `M6 delete` | megaplan | vendored agent tests | M6 |
| `arnold/pipelines/megaplan/agent/pyproject.toml` | `M6 delete` | megaplan | nested package metadata; already excluded from wheel/sdist | M6 |
| `arnold/pipelines/megaplan/agent/scripts/whatsapp-bridge/package-lock.json` | `M6 delete` | megaplan | vendored node lockfile | M6 |
| `arnold/pipelines/megaplan/vendor/shannon/` | `M6 delete` (vendored) | megaplan | vendored Shannon runtime | M6 |
| `arnold/pipelines/megaplan/skills/` | `move` | megaplan | Megaplan-specific skills (`babysit`, `megaplan*`) are product-owned; generic skills belong in neutral skill registry post-M6 | M4 |
| `arnold/pipelines/megaplan/agent_runtime/` | `move` | megaplan | product-owned adapter to vendored `agent/`; will become a parity shim if `agent/` is removed before M6 | M4 |
| `arnold/pipelines/megaplan/agent_adapters/` | `move` | megaplan | product-owned codex/shannon/oneshot adapters | M4 |
| `arnold/pipelines/megaplan/__pycache__/` | `delete` (cache) | — | rebuild artifact | immediate |
| `arnold/pipelines/megaplan/**/__pycache__/` | `delete` (cache) | — | rebuild artifact | immediate |

## 6. Neutral Arnold surfaces that interact with Megaplan

| Path / group | Class | Owner | Blocker | Expiry |
| --- | --- | --- | --- | --- |
| `arnold/pipeline/__init__.py` | `non-legacy neutral surface` | arnold | none | permanent |
| `arnold/pipeline/builder.py` | `non-legacy neutral surface` | arnold | none | permanent |
| `arnold/pipeline/executor.py` | `non-legacy neutral surface` | arnold | none | permanent |
| `arnold/pipeline/state.py` | `temporary M4 parity shim` | arnold | legacy state authority; journal projection replaces writes in M4 Phase 4 | M6 |
| `arnold/pipeline/resume.py` | `temporary M4 parity shim` | arnold | legacy resume tokens | M6 |
| `arnold/pipeline/registry.py` | `non-legacy neutral surface` | arnold | discovers `arnold.pipelines.megaplan` plugin; allowlist updated in M4 | permanent |
| `arnold/pipeline/discovery/` | `non-legacy neutral surface` | arnold | none | permanent |
| `arnold/pipeline/steps/` | `non-legacy neutral surface` | arnold | none | permanent |
| `arnold/runtime/__init__.py` | `non-legacy neutral surface` | arnold | none | permanent |
| `arnold/runtime/driver.py` | `non-legacy neutral surface` | arnold | none | permanent |
| `arnold/runtime/state_persistence.py` | `temporary M4 parity shim` | arnold | legacy state persistence | M6 |
| `arnold/runtime/event_journal.py` | `non-legacy neutral surface` | arnold | journal becomes authority | permanent |
| `arnold/runtime/resume.py` | `non-legacy neutral surface` | arnold | converts legacy tokens to `ManifestCursor` | permanent |
| `arnold/cli/__init__.py` | `temporary M4 parity shim` | arnold | legacy `megaplan` subcommands; projections move to `arnold_pipelines.megaplan.cli` | M6 |
| `arnold/cli/execution.py` | `non-legacy neutral surface` | arnold | none | permanent |
| `arnold/agent/` | `non-legacy neutral surface` | arnold | neutral agent runtime; must not import `arnold_pipelines.megaplan` | permanent |
| `arnold/execution/` | `non-legacy neutral surface` | arnold | manifest execution backend | permanent |
| `arnold/workflow/` | `non-legacy neutral surface` | arnold | DSL/compiler/manifest | permanent |
| `arnold/kernel/` | `non-legacy neutral surface` | arnold | replay, content types, registries | permanent |
| `arnold/conformance/` | `non-legacy neutral surface` | arnold | import-boundary scanning | permanent |

## 7. Tests

| Path / group | Class | Owner | Blocker | Expiry |
| --- | --- | --- | --- | --- |
| `tests/arnold/pipelines/megaplan/` | `move` | megaplan | migrate to `tests/arnold_pipelines/megaplan/` as parity tests land | M4 |
| `tests/pipelines/megaplan/` | `move` | megaplan | migrate to `tests/arnold_pipelines/megaplan/` | M4 |
| `tests/test_pipeline_*.py` | `read-only migration input` | megaplan | golden/parity references; kept until new tests lock parity | M6 archive |
| `tests/characterization/test_pipeline_golden.py` | `read-only migration input` | megaplan | golden characterization | M6 archive |
| `tests/_pipeline/` | `read-only migration input` | megaplan | legacy pipeline tests | M6 archive |
| `tests/arnold/conformance/test_conformance_gates.py` | `non-legacy neutral surface` | arnold | include `arnold_pipelines.megaplan` in active package scans | permanent |
| `tests/arnold/workflow/test_import_boundaries.py` | `non-legacy neutral surface` | arnold | none | permanent |
| `tests/arnold/execution/test_import_boundaries.py` | `non-legacy neutral surface` | arnold | none | permanent |
| `tests/arnold_pipelines/megaplan/test_package.py` | `move` (new) | megaplan | added in M4 Phase 2 | permanent |
| `tests/arnold_pipelines/megaplan/test_import_boundaries.py` | `move` (new) | megaplan | added in M4 Phase 2 | permanent |

## 8. Command strings and generated references

| Command / reference | Class | Owner | Blocker | Expiry |
| --- | --- | --- | --- | --- |
| `python -m arnold.pipelines.megaplan` | `temporary M4 parity shim` | megaplan | CLI docs/scripts | M6 |
| `python -m arnold.pipelines.megaplan run` | `temporary M4 parity shim` | megaplan | operator habit, scripts | M6 |
| `arnold megaplan run` / `arnold megaplan resume` | `temporary M4 parity shim` | arnold | `arnold/cli/__init__.py` subcommands | M6 |
| `arnold_pipelines.megaplan` wheel package | `move` | megaplan | `pyproject.toml` package inclusion | M4 |
| `docs/arnold/legacy-surface-inventory.md` | `move` (this doc) | megaplan | M4 Phase 1 deliverable | M4 |
| `docs/arnold/state-authority-migration.md` | `non-legacy neutral surface` | arnold | extended in M4 Phase 1 | permanent |
| `docs/arnold/package-disposition.md` | `non-legacy neutral surface` | arnold | generated from YAML; authoritative disposition | permanent |
| `docs/arnold/workflow-manifest-amendments.md` | `non-legacy neutral surface` | arnold | updated when Megaplan topology changes | permanent |
| Generated docs under `arnold/pipelines/megaplan/agent/docs/` | `M6 delete` | megaplan | vendored agent docs | M6 |
| `arnold/pipelines/megaplan/agent/skills/index-cache/*.json` | `M6 delete` | megaplan | generated skill index cache | M6 |

## 9. M4 parity adapter inventory

Temporary aliases and shims that bridge old imports to the new package during M4.

| Adapter | Location | Old symbol | New target | Expiry |
| --- | --- | --- | --- | --- |
| Top-level package alias | `arnold/pipelines/megaplan/__init__.py` | `arnold.pipelines.megaplan.*` | forwarded lazily to new package modules in M4 | M6 |
| CLI alias | `arnold/pipelines/megaplan/__main__.py` | `python -m arnold.pipelines.megaplan` | delegates to `arnold_pipelines.megaplan.cli` | M6 |
| Registry plugin alias | `arnold/pipeline/registry.py` | `arnold.pipelines.megaplan` discovery | also scans `arnold_pipelines.megaplan` | M6 |
| Worker agent parity | `arnold_pipelines/megaplan/workers/hermes.py`, `workers/_impl.py` | imports `arnold.pipelines.megaplan.agent` | allowed M4 parity adapter; vendored `agent/` stays in legacy tree | M6 |

## 10. Notes

* The bridge path is `arnold/pipelines/megaplan/_pipeline/_bridge.py`.  The brief `arnold-post-extraction-next/m1-megaplan-canonical-executor-bridge.md` incorrectly referenced `arnold/pipeline/_bridge.py`; this inventory corrects that path.
* `arnold/pipelines/megaplan/agent/` is classified as vendored debris for M4 because neutral `arnold/agent/` now hosts the equivalent runtime.  It remains physically present for parity only.
* `arnold/pipelines/megaplan/_core/state.py` and `arnold/pipeline/state.py` are *read-only migration inputs* for the new journal-backed runtime; no M4 code may treat them as authority.
* All `__pycache__` directories are excluded from the inventory because they are rebuild artifacts.
