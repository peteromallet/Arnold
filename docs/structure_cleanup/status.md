# Structure Cleanup Status

Last updated: 2026-06-12.

## Completed This Pass

### Root Layer

Ran a 10-brief DeepSeek/Hermes root audit swarm. Results are in
`docs/structure_cleanup/results/`.

Applied root cleanup:

- moved root audits to `docs/audits/`
- moved root plans/manifests to `docs/plans/`
- moved one-off root scripts to `scripts/maintenance/`
- removed ignored local junk: `.DS_Store`, `_debug_*.py`, `install.log`, empty
  local `input/`, and safe cache dirs
- updated `.gitignore` for root caches, local input, root one-off scripts, and
  `finalize.json`
- kept repo-owned indexes/lockfiles at root because code/docs still treat them
  as contracts: `template_index.json`, `workflow_index.json`,
  `external_workflow_index.json`, `version_matrix.json`, `custom_nodes.lock`

### Docs Layer

Ran a 10-brief DeepSeek/Hermes docs audit swarm. Results are in
`docs/structure_cleanup/docs_results/`.

Applied docs cleanup:

- added `docs/README.md`
- added indexes for `docs/audits/`, `docs/historical/`, and `docs/plans/`
- moved stale historical docs:
  - `docs/frontier-hardening-runbook.md` -> `docs/historical/frontier-hardening-runbook.md`
  - `docs/sprint5_followups.md` -> `docs/historical/sprint5_followups.md`
  - `docs/template_cleanup_followups.md` -> `docs/historical/template_cleanup_followups.md`
- moved active loose-work plan:
  - `docs/loose-work-consolidation-plan.md` -> `docs/plans/loose-work-consolidation-plan.md`
- created `docs/agent-edit/` and moved the agent-edit contracts, plans, and
  failure evidence there with link updates
- created `docs/text-to-graph/` and moved the three tracked core text-to-graph
  design docs there with link updates
- created `docs/runtime/`, `docs/runpod/`, `docs/testing/`, and
  `docs/migration/`, with index READMEs and path updates
- created `docs/templates/` for porting/readiness/generated-template docs and
  `docs/workflow-coverage/` for corpus/family coverage maps, with tests and
  strict-ready loader paths updated
- created `docs/architecture/` for architecture/design proposals

### Agentic / Agent Config Layer

Ran a 10-brief DeepSeek/Hermes audit swarm. Results are in
`docs/structure_cleanup/agentic_results/`.

Applied safe cleanup:

- removed stale tracked sample evidence from `agentic/evidence/`; generated
  evidence belongs under `out/agentic/reports/<tag>/`
- cleaned ignored Python bytecode caches under `agentic/`
- updated `agentic/__init__.py` and `agentic/README.md` so the actor modules and
  evidence-pack location match the actual harness
- added `agents/README.md` to distinguish visible agent interface declarations
  from the `agentic/` test harness and hidden local agent config
- added a root `README.md` repository-layout table for the similarly named agent
  and planning surfaces

Deferred:

- renaming `agentic/actors_m4/`, `agentic/actors_m5/`, `agentic/briefs/`, or
  `agentic/scenarios/`; tests and imports use those paths as contracts
- deleting `.claude/`, `.agents/`, or `.megaplan/` local state without explicit
  user approval
- moving tracked `.megaplan` planning artifacts; that deserves a dedicated
  planning-artifacts pass

## Verification

Passed:

- `python -m vibecomfy.cli workflows list --ready --json`
- `python -m vibecomfy.cli nodes list --json`
- `python -m py_compile vibecomfy/comfy_nodes/agent/edit.py`
- old-path `rg` checks for moved root, agent-edit, and text-to-graph paths
- old-path `rg` checks for moved runtime, RunPod, testing, migration,
  templates, workflow-coverage, and architecture paths
- `./.venv/bin/pytest tests/test_strict_ready.py -q` passed
- `./.venv/bin/pytest tests/test_gold_template_alignment.py tests/test_ui_emitter_parity.py::test_allowlist_documents_widget_shape_taxonomy -q`
  exited 0 with three known baseline gold-template failures and no regressions
- `./.venv/bin/pytest tests/test_agentic_contract.py tests/test_agentic_runner.py tests/test_agentic_adapter.py tests/test_agentic_structural.py tests/test_agentic_golden_m4.py tests/test_agentic_golden_m5.py -q`
  passed after the agentic cleanup

Focused ready-template test command:

- `pytest tests/test_comfy_backend.py tests/test_ready_templates.py -q`
- exited 0 with the repo's known-failure reporting: 12 ready-template failures
  were reported as known/baseline, not regressions.

Full test attempts:

- bare `pytest -q` used system Python 3.14 and stopped at collection because
  `sisypy` and `hypothesis` were unavailable in that interpreter.
- `uv run pytest -q` failed dependency resolution for Python 3.14 markers and
  never ran tests.
- installed sibling `../sisypy` editable into `.venv` with
  `uv pip install --python ./.venv/bin/python -e ../sisypy`.
- `.venv/bin/pytest -q` completed but was not green:
  `310 failed, 3466 passed, 127 skipped, 16 deselected, 4 xfailed, 39 errors`.
  The 39 errors are characterization tests requiring `PYTHONHASHSEED=0`. The
  broad failure set appears dominated by existing corpus/template parity issues,
  but this pass did not prove the full suite is regression-free.

### Artifacts Layer

Moved active/public-facing docs out of `artifacts/`:

- `artifacts/m6-public-api.md` → `docs/api/m6-public-api.md` (public API surface)
- `artifacts/m1-step1-audit.md` → `docs/audits/m1-step1-audit.md` (M1 audit baseline)
- `artifacts/m2-diff-hygiene.md` → `docs/audits/m2-diff-hygiene.md` (M2 diff classification)

Created `docs/api/README.md` and `artifacts/README.md` to explain each directory's
purpose. Updated all cross-references in `README.md`, `CLAUDE.md`,
`docs/historical/*.md`, and `docs/megaplan_chains/**/*.md` to the new paths.
Updated `docs/README.md` and `docs/audits/README.md` for navigation.

Initially kept in `artifacts/`: `m1-safety-gate.md`, `m2-symbol-map.md`, `m4/`,
`m5_*`, and `m5a-*`. A later deletion-first pass removed the generated `m4/`,
`m5_*`, and `m5a-*` baselines, leaving durable docs in `docs/` and the
`artifacts/README.md` boundary note.

Verification:

- `python -m vibecomfy.cli workflows list --ready --json`
- `python -m vibecomfy.cli nodes list --json`
- `git diff --check`
- stale-path `rg` for the moved artifact paths; remaining matches are limited to
  `docs/structure_cleanup/` audit logs/briefs that intentionally describe the
  source paths

### Scripts / Tools Layer

Ran a 10-brief DeepSeek/Hermes audit swarm. Results are in
`docs/structure_cleanup/scripts_results/`.

Applied safe cleanup:

- added `scripts/README.md` to define direct-run operational scripts, RunPod
  harnesses, agent/editor helpers, and local maintenance scripts
- added `tools/README.md` to define importable developer tools run as
  `python -m tools.<name>`
- updated the root `README.md` repository-layout table with `scripts/` and
  `tools/`
- removed ignored local junk under this layer: `.DS_Store`, `__pycache__/`, and
  orphaned ignored `tools/_legacy/`

Deferred:

- moving `scripts/regenerate_snapshots.py` to `tools/`; it is tool-shaped, but
  CI, tests, and docs reference the current path, so that should be its own
  explicit refactor
- moving RunPod scripts into subdirectories; their current paths are referenced
  by tests, CI, docs, and sibling imports
- deleting tracked private/spike scripts without user approval

Verification:

- import smoke for load-bearing `scripts` modules
- import smoke for load-bearing `tools` modules
- `python -m vibecomfy.cli workflows list --ready --json`
- `python -m vibecomfy.cli nodes list --json`
- `git diff --check`

### Megaplan Layer

Ran a 10-brief DeepSeek/Hermes audit swarm. Results are in
`docs/structure_cleanup/megaplan_results/`.

Applied safe cleanup:

- added `docs/megaplan_chains/README.md` to define durable authored megaplan
  planning material versus generated `.megaplan/` runtime state
- updated the root `README.md` repository-layout table with
  `docs/megaplan_chains/`, `.megaplan/`, `agentic/`, `agents/`, `scripts/`,
  `tools/`, and `artifacts/`
- updated `docs/README.md` with the `.megaplan` versus
  `docs/megaplan_chains/` boundary
- removed transient untracked helper scripts created by subagents during the
  audit: `__run_task.sh`, `tmp_audit.sh`, `tmp_audit_output.sh`, and
  `tmp_run.sh`

Deferred:

- bulk-moving tracked `.megaplan/briefs`, `.megaplan/chains`,
  `.megaplan/ideas`, `.megaplan/tickets`, or `.megaplan/schemas`; the audit
  found live or historical path contracts, and symlink/path-bridge work should
  be its own explicit pass
- deleting ignored `.megaplan` runtime state such as `plans/`, `logs/`,
  `telemetry/`, `wakeup/`, `.state-locks/`, and nested `.megaplan/` trees
  without explicit user approval
- moving `.megaplan/debt.json`; agents classified it as mixed authored and
  auto-updated state

Verification:

- `python -m vibecomfy.cli workflows list --ready --json`
- `python -m vibecomfy.cli nodes list --json`
- `git diff --check`

### Compatibility / Small Shim Layer

Ran a 10-brief DeepSeek/Hermes compatibility audit swarm. Results are in
`docs/structure_cleanup/compat_results/`.

Applied deletion-first cleanup:

- kept `vibecomfy/fixtures.py` only as the public CLI exception for
  `python -m vibecomfy.fixtures`; moved the implementation to
  `vibecomfy/testing/_fixtures_smoke.py`
- deleted `vibecomfy/testing/_fixtures.py`, the stale byte-for-byte duplicate
- moved agent-edit debug implementation to
  `vibecomfy/commands/_agent_edit_debug.py`, updated all internal importers,
  and deleted the root `vibecomfy/_agent_edit_debug.py` compatibility path
- moved `format_issue` into `vibecomfy/schema/validate.py`, updated all
  internal importers, and deleted `vibecomfy/schema/format.py`
- deleted dead schema modules `vibecomfy/schema/factory.py` and
  `vibecomfy/schema/registry.py`; `schema/__init__.py` already re-exports the
  provider-backed implementations
- deleted the orphaned duplicate `vibecomfy/cli/_debug.py`
- kept `vibecomfy/diagnostics/__init__.py` as a pure barrel over
  `diagnostics.findings` and `diagnostics.health`

Verification:

- `PYTHONDONTWRITEBYTECODE=1 python -m vibecomfy.fixtures list`
- `PYTHONDONTWRITEBYTECODE=1 python -m vibecomfy.cli debug --help`
- `PYTHONDONTWRITEBYTECODE=1 python -m vibecomfy.cli validate --help`
- `PYTHONDONTWRITEBYTECODE=1 python -m vibecomfy.cli doctor --help`
- canonical import smoke for `vibecomfy.schema.validate.format_issue`,
  `vibecomfy.commands._agent_edit_debug`, and `vibecomfy.fixtures`
- deleted-path import smoke confirmed no specs for
  `vibecomfy._agent_edit_debug` or `vibecomfy.schema.format`
- `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_fixtures.py tests/test_cli_debug.py tests/test_diagnostics.py tests/test_cli_doctor_contract_validate.py tests/test_doctor_diagnostics.py -q`
  reported 44 passing tests and 2 known baseline failures from
  `tests/known_failures.txt`

### Vendor Compatibility Shim Layer

Applied the deletion-first recommendation from
`docs/structure_cleanup/compat_results/09-delete-first-risk.txt` after
re-checking the local checkout:

- deleted `vendor/ComfyUI/comfy/transformers_compat.py`
- migrated all 16 vendored tokenizer import sites to direct `transformers`
  imports
- relied on `vendor/ComfyUI/pyproject.toml` requiring `transformers>=4.57.3`;
  the local environment has all previously shimmed tokenizer names available
- kept `vendor/ComfyUI/comfy/torchvision_compat.py`,
  `vendor/ComfyUI/comfy_extras/nodes/nodes_template_compatibility.py`, and
  `vendor/ComfyUI/comfy/tracing_compatibility.py` because they are active
  runtime patches or template-conversion node stubs, not dead import aliases

Verification:

- no remaining `transformers_compat` references under `vendor/ComfyUI/comfy`
  or `vendor/ComfyUI/tests`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/ComfyUI:$PYTHONPATH" python - <<'PY' ...`
  imported every touched tokenizer module and `comfy.sd1_clip`
- `git -C vendor/ComfyUI diff --check`

### Remaining Docs Root Layer

Ran a 10-brief DeepSeek/Hermes audit swarm. Results are in
`docs/structure_cleanup/docsroot_results/`.

Applied safe cleanup:

- moved `docs/m4_resolution_context.md` to
  `docs/architecture/m4-resolution-context.md`
- updated `docs/architecture/README.md` to index the moved design document

Kept at `docs/` root:

- core entry/reference docs with broad links or cross-cutting scope:
  `authoring.md`, `vibeworkflow.md`, `api_stability.md`, `custom_nodes.md`,
  `errors_and_doctor.md`, `node_pack_reconciliation.md`,
  `roadmap_agentic_comfyui.md`, and `release_notes.md`
- `local_agent_text_to_graph_blockers.md` as a bridge doc between
  `agent-edit/` and `text-to-graph/`

Deferred:

- moving `structural_audit_2026-05.md`, `structural_issues.md`,
  `comfy_version_support.md`, or `local_agent_text_to_graph_e2e.md`; the audit
  found enough cross-references that those should be batched with explicit link
  repair, not hidden inside this pass
- converting `docs/release_notes.md` to `docs/release_notes/README.md`; useful
  but cosmetic and not worth extra link churn here

Verification:

- no non-cleanup references to `m4_resolution_context` remain
- `python -m vibecomfy.cli workflows list --ready --json`
- `python -m vibecomfy.cli nodes list --json`
- `git diff --check`

### Template / Corpus / Recipe Layer

Ran a 10-brief DeepSeek/Hermes audit swarm. Results are in
`docs/structure_cleanup/template_surface_results/`.

Applied safe cleanup:

- added `workflow_corpus/README.md` to document source JSON workflow layout,
  fixture/media boundaries, manifests, and path/index contracts
- updated `ready_templates/README.md` for the current 64-template count,
  `audio/` and `smoke/` categories, and generated/manual marker policy
- expanded `recipes/README.md` with a recipe catalog, loader guidance, snapshot
  boundary, and links to authoring/testing/template docs
- added a `Recipes` entry to `docs/README.md`
- cross-linked `docs/templates/README.md` to workflow coverage and
  `workflow_corpus/README.md`
- removed ignored local junk under this surface: `.DS_Store`, `__pycache__/`,
  and `.pyc` files in `ready_templates/`, `recipes/`, and `workflow_corpus/`

Deferred:

- moving or renaming any `ready_templates/**/*.py`; those paths define ready
  IDs and are referenced by generated indexes and coverage/regeneration
  manifests
- moving `workflow_corpus/**/*.json`, `workflow_corpus/input/`, or
  `workflow_corpus/manifests/`; those are path-sensitive source/index surfaces
- moving recipe snapshot fixtures; the current sibling snapshot is part of the
  documented user-code testing flow
- changing root index/manifest tracking policy for `template_index.json`,
  `workflow_index.json`, `external_workflow_index.json`, `node_index.json`,
  `version_matrix.json`, `asset_manifest.json`, or `custom_nodes.lock`

Verification:

- `python -m vibecomfy.cli workflows list --ready --json`
- `python -m vibecomfy.cli nodes list --json`
- `git diff --check`

### Config / Ops / Root Metadata Layer

Ran a 10-brief DeepSeek/Hermes audit swarm. Results are in
`docs/structure_cleanup/config_ops_results/`.

Applied safe cleanup:

- added `vendor/README.md` to define the mixed vendor boundary:
  `vendor/ComfyUI/` as a git submodule, `vendor/direct_templates/` as checked-in
  source JSON, and `vendor/workflow_templates/` / `vendor/external_workflows/`
  as ignored local checkout areas
- updated the root `README.md` repository-layout table to point readers to
  `vendor/README.md`
- added `.env.example` with placeholder local/runtime env var names and added
  `.env` to `.gitignore`; the existing `this.env` local credential file remains
  untouched and ignored
- added `docs/cloud.md` to resolve the existing `docs/cloud.md` reference and
  point cloud readers to root `cloud.yaml` and the megaplan chain operator notes
- removed ignored local junk outside `.venv/`, `.git/`, and the ComfyUI
  submodule: `.DS_Store` files and `__pycache__/` directories

Deferred:

- moving root config files such as `pyproject.toml`, `uv.lock`,
  `.pre-commit-config.yaml`, `.gitignore`, `.gitmodules`, `.importlinter`,
  `cloud.yaml`, `version_matrix.json`, `custom_nodes.lock`, or
  `asset_manifest.json`; the audit found path contracts or standard tool
  conventions for each
- moving or deleting `CLAUDE.md` / `AGENTS.md`; agent discovery expects root
  paths
- deleting or relocating `this.env` without an explicit credential migration
  decision; it contains live local credentials and is already ignored
- deleting `.venv/`, `.claude/`, `.agents/`, `.desloppify/`, `.pytest_cache/`,
  or ComfyUI submodule internals without explicit approval or a dedicated tool
  owner pass
- changing tracked `vibecomfy/porting/cache/` snapshots; they are already
  tracked source/cache fixtures, so adding a gitignore rule would not change
  current behavior

Verification:

- no ignored `.DS_Store` or `__pycache__/` files remain in the parent tree
  outside `.venv/`, `.git/`, and `vendor/ComfyUI/`
- `python -m vibecomfy.cli workflows list --ready --json`
- `python -m vibecomfy.cli nodes list --json`
- `git diff --check`

### Tests Layer

Ran a 10-brief DeepSeek/Hermes audit swarm. Results are in
`docs/structure_cleanup/tests_results/`.

Applied safe cleanup:

- added `tests/README.md` to document test layout, stable fixture/baseline
  boundaries, focused run commands, known-failures handling, and ignored e2e
  outputs
- deleted stale committed fixture
  `tests/fixtures/porting/opaque_component.json`; the audit found no references
  from tests, docs, or tools
- removed ignored local Playwright artifacts and dependencies:
  `tests/e2e/test-results/`, `tests/e2e/playwright-report/`, and
  `tests/e2e/node_modules/`

Deferred:

- moving root-level `tests/test_*.py` files into subdirectories; many paths are
  anchored in `tests/known_failures.txt`, direct imports, and file-relative
  fixture resolution
- moving `tests/_cli_helpers.py`, `tests/_runtime_session_helpers.py`,
  `tests/conftest.py`, or `tests/smoke/_runpod_helpers.py`; these are active
  support/import surfaces
- moving or pruning committed generated baselines under `tests/snapshots/`,
  `tests/characterization/goldens/`, and
  `tests/fixtures/canonical_parity_baseline.json`; those are regenerated
  in-place and intentionally committed
- renaming `tests/edgecases/`, moving property tests, or consolidating
  duplicate-looking tests; those are behavior/test-identity refactors, not safe
  structure cleanup

Verification:

- stale fixture path no longer exists
- ignored e2e local output/dependency directories no longer exist
- `PYTHONDONTWRITEBYTECODE=1 python -m vibecomfy.cli workflows list --ready --json`
- `PYTHONDONTWRITEBYTECODE=1 python -m vibecomfy.cli nodes list --json`
- `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_workflow_core.py tests/test_contracts_reexport.py -q`
- `git diff --check`

### Package Internals Layer

Ran a 10-brief DeepSeek/Hermes audit swarm. Results are in
`docs/structure_cleanup/package_results/`.

Applied safe cleanup:

- added subsystem boundary READMEs:
  `vibecomfy/ir/README.md`, `vibecomfy/_compile/README.md`,
  `vibecomfy/schema/README.md`, `vibecomfy/contracts/README.md`,
  `vibecomfy/porting/README.md`, `vibecomfy/commands/README.md`,
  `vibecomfy/runtime/README.md`, `vibecomfy/testing/README.md`, and
  `vibecomfy/router/README.md`
- removed recreated `__pycache__/` directories under `vibecomfy/` and `tests/`
- reviewed and corrected the subagent's `.gitignore` patch: kept the approved
  `.env` rule, but did not ignore tracked/significant `asset_manifest.json` or
  apply a blanket `*.env` rule

Deferred:

- deleting `vibecomfy/_graph_utils.py`; code no longer imports it, but current
  docs/artifacts still document it as a foundation utility path, so removing it
  should be bundled with doc/reference cleanup or a deprecation note
- deleting shims `_workflow_helpers.py`, `_helper_resolve.py`, and
  `_widget_aliases.py`; active tests, `workflow.py`, and `.importlinter` still
  reference those compatibility paths
- deleting `vibecomfy/commands/port.py`, `vibecomfy/router.py`, or
  `vibecomfy/patches/resize_schema.py`; these were deferred here, then handled
  in the later package dead-module verification layer. `vibecomfy/router/_rules.py`
  remains live as the canonical router rule module.
- changing `vibecomfy/runtime` structure; the runtime audit found duplicate-ish
  private helpers but those are behavior refactors, not structure-only cleanup
- changing tracked object-info/cache snapshots under `vibecomfy/porting/`; their
  lifecycle needs its own generated-snapshot policy decision

Verification:

- `PYTHONDONTWRITEBYTECODE=1 python -m vibecomfy.cli workflows list --ready --json`
- `PYTHONDONTWRITEBYTECODE=1 python -m vibecomfy.cli nodes list --json`
- `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_workflow_helpers.py tests/test_contracts_reexport.py -q`
- `git diff --check`

### Package Dead-Module Verification Layer

Ran a 10-brief DeepSeek/Hermes audit swarm. Results are in
`docs/structure_cleanup/dead_module_results/`.

Applied safe cleanup:

- deleted `vibecomfy/commands/port.py`; Python resolves
  `vibecomfy.commands.port` to the package directory, and the old file was a
  shadowed legacy copy of the split command implementation
- deleted `vibecomfy/commands/_analyze_names.py`; the public
  `vibecomfy/commands/analyze_names.py` is the live implementation and no code
  imports the private duplicate
- deleted `vibecomfy/router.py`; `vibecomfy.router` resolves to the package
  directory, not the top-level file
- deleted `vibecomfy/patches/resize_schema.py`; it was not exported, not a
  `Patch`, and had no live imports
- later removed the temporary `vibecomfy/router_rules.py` shim after migrating
  internal callers to `vibecomfy.router`

Deferred:

- runtime files flagged by the synthesis (`runtime/config.py`,
  `runtime/server_process.py`, `runtime/watchdog_runtime.py`,
  `runtime/_local_library_yaml.py`); the dedicated runtime audit found active
  internal consumers or behavioral drift, so these are refactors, not safe
  dead-code deletions
- schema files flagged only by the broad synthesis; no candidate-specific audit
  covered them, so they need a separate schema pass before deletion
- `vibecomfy/_graph_utils.py`; code no longer imports it, but docs and artifact
  references still describe that compatibility path, so deletion needs bundled
  reference repair
- legacy object-info JSON snapshots under `vibecomfy/porting/object_info/`;
  primary consumers use `cache/object_info`, but
  `scripts/demo_wrapper_codegen.py` still relies on the legacy snapshot source
- testing fixture/stub cleanup; `vibecomfy/testing/__init__.py` export fixes
  would change public behavior and should be handled as a test-tooling fix

Verification:

- no live code imports the deleted module paths
- `PYTHONDONTWRITEBYTECODE=1 python -m vibecomfy.cli --help`
- `PYTHONDONTWRITEBYTECODE=1 python -m vibecomfy.cli port --help`
- `PYTHONDONTWRITEBYTECODE=1 python -m vibecomfy.cli analyze names image/z_image --json`
- `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_analysis.py::test_analyze_names_cli_reports_role_based_preview tests/test_router.py -q`
- targeted ready-template resize-schema tests were run as a sanity check; they
  still fail with existing `known_failures.txt` baseline KeyErrors, not with
  import/deleted-module errors
- `git diff --check`

### Docs Reference Audit Layer

Ran a 10-brief DeepSeek/Hermes audit swarm. Results are in
`docs/structure_cleanup/docs_reference_results/`.

Applied safe cleanup:

- updated active RunPod docs to refer to the live `vibecomfy/router/` package
  instead of deleted top-level router files
- updated `CLAUDE.md` so agent guidance points at `vibecomfy/router/` directly
- kept the docs index additions for `errors_and_doctor.md`,
  `comfy_version_support.md`, `tests/README.md`,
  `ready_templates/README.md`, and `workflow_corpus/README.md`
- kept two narrow safe-reference fixes from the agent pass:
  `docs/authoring.md` no longer recommends the removed materializer script for
  new template work, and `docs/historical/sprint5_followups.md` no longer has a
  stale Sprint 4 heading
- updated `docs/structure_cleanup/README.md` to index the layer audit
  directories

Rejected/deferred:

- moving more docs-root files; the audit found useful candidates, but those are
  moves with link churn and should be their own explicit pass
- broad plan/history rewrites under `docs/plans/` and
  `docs/megaplan_chains/`; those remain provenance records unless promoted in a
  dedicated historical-docs pass
- treating `docs/structure_cleanup/*_results` references as stale; they are
  audit evidence for the cleanup process
- creating or expanding migration/release content beyond relocating existing
  index text; content-writing is outside this reference cleanup layer

Verification:

- active RunPod and agent guidance references now point at `vibecomfy/router/`
- focused CLI smoke and `git diff --check` run after this layer

### Historical Docs Boundary Layer

Ran a 10-brief DeepSeek/Hermes audit swarm. Results are in
`docs/structure_cleanup/historical_docs_results/`.

Applied safe cleanup:

- moved the active `agent_readable_templates_v2.md` plan from
  `docs/historical/` to `docs/plans/`, matching its `**Status:** active`
  header and the historical directory contract
- updated `docs/plans/README.md`, `docs/historical/README.md`, and
  `docs/README.md` to describe the active-plan versus historical-record
  boundary
- kept historical status headers added by the audit on completed follow-up and
  runbook documents
- updated `vibecomfy/contracts/RUNTIME_CONTRACT.md` to point runtime-contract
  readers at the runtime docs instead of the unrelated M3 corpus plan
- removed the stale `docs/plans/plan_v2.md` pointer from
  `vibecomfy/porting/lowering.py`; the lowering decisions are listed inline

Rejected/deferred:

- bulk-moving `docs/plans/plan_v2.md`, `docs/plans/revised_plan.md`,
  `docs/plans/finalize.json`, or
  `docs/plans/loose-work-consolidation-plan.md`; the audits conflicted, and
  current evidence shows these still serve as active, queued, or partial
  planning context
- archiving `docs/structure_cleanup/`; the overall cleanup goal is still
  active, and the status/evidence tree should remain easy to find until
  deferred items are resolved or explicitly closed
- splitting `template_cleanup_followups.md`; that is content restructuring, not
  a file-structure boundary fix

Verification:

- no non-cleanup references to the old
  `docs/historical/agent_readable_templates_v2.md` path remain
- focused CLI smoke and `git diff --check` run after this layer

### Deletion-First Current Tree Audit

Ran a 10-brief DeepSeek/Hermes deletion-first audit swarm. Results are in
`docs/structure_cleanup/deletion_first_results/`.

Applied safe cleanup:

- migrated internal agent-edit callers from old `vibecomfy.porting.edit_*`
  shim modules to canonical `vibecomfy.porting.edit.*` imports
- deleted old edit shim modules:
  `edit_ops.py`, `edit_apply.py`, `edit_lint.py`, `edit_projection.py`,
  `edit_ledger.py`, `edit_types.py`, and `edit_session.py`
- deleted dead porting modules with no live imports:
  `helpers.py`, `templates.py`, `handle_index.py`, `naming.py`,
  `formatting.py`, and `node_kwargs.py`
- migrated plugin route registration to `vibecomfy.router.register_route` and
  deleted `vibecomfy/router_rules.py`
- migrated callers from root-level duplicate porting modules to canonical
  package paths and deleted `uid.py`, `scope.py`, `slot_codec.py`,
  `widget_aliases.py`, `widget_schema.py`, `wrapper_codegen.py`, and
  `wrapper_discovery.py`
- deleted orphaned/generated root state: `node_index.json` and
  `asset_manifest.json`
- deleted ignored/generated local state: `out/`, `.pytest_cache/`,
  `ready_templates/image/__pycache__/`, stale `.desloppify` run artifacts, and
  stale `.megaplan` backup JSON files
- deleted generated artifact baselines under `artifacts/m4/`, `artifacts/m5_*`,
  and `artifacts/m5a-*`
- deleted ComfyUI submodule local bytecode/runtime junk without touching tracked
  submodule content

Kept / deferred:

- did not touch `this.env`, despite one agent recommending deletion, because it
  is a local secret file and outside this cleanup's safe edit boundary
- kept `.claude/`, broad `.megaplan/` authored/planning state, `.venv/`, and
  tracked docs with mixed active/historical value
- the next porting-deep pass deleted the byte-identical UI emitter duplicate;
  the Python template emitter remains at the porting root because focused tests
  showed the split emitter does not yet preserve all formatting/signature
  behavior

Verification:

- no live code imports the deleted shim/dead module paths
- focused CLI and pytest checks are run after this layer
- `git diff --check` is run after this layer

### Porting Deep Cleanup Layer

Ran a 10-brief DeepSeek/Hermes porting-layer audit swarm. Results are in
`docs/structure_cleanup/porting_deep_results/`.

Applied cleanup:

- moved private edit-session mixin modules from the `vibecomfy/porting/` root
  into `vibecomfy/porting/edit/` as `_session_types.py`, `_parse.py`,
  `_ir_utils.py`, `_diff.py`, `_resolve.py`, `_describe.py`, `_gates.py`,
  `_render.py`, and `_parse_execute.py`
- updated their imports to the new canonical `vibecomfy.porting.edit._*` paths
- migrated UI emitter callers from `vibecomfy.porting.ui_emitter` to
  `vibecomfy.porting.emit.ui` and deleted the byte-identical root duplicate
  `ui_emitter.py`
- attempted to migrate Python emitter callers to
  `vibecomfy.porting.emit.emitter`, but restored
  `vibecomfy.porting.emitter` after focused tests showed behavior divergence
  in ready-template formatting and available-node signature rendering
- deleted stale duplicate RunPod snapshot JSON files from
  `vibecomfy/porting/object_info/`; the active snapshots are under
  `vibecomfy/porting/cache/object_info/`
- updated `vibecomfy/porting/README.md` so the package boundary reflects the
  new canonical homes

Kept / deferred:

- kept `layout_store.py` at the porting root; agents found it is a sidecar I/O
  boundary used by CLI and agent code, not a layout-engine internal
- kept root `emit_*` helper modules because they are still active shared
  implementations used by the canonical emitter package
- kept root `emitter.py` as the current Python template emitter behavior
  boundary; deleting it is deferred until the split `emit/` implementation is
  demonstrably parity-equivalent
- kept object-info cache snapshots under `porting/cache/` because tests and
  offline schema/wrapper workflows still use them

Verification:

- focused edit-session and UI emitter tests passed after this layer
- targeted ready-template emitter checks are still at the existing
  `known_failures.txt` baseline; they were used to confirm `emitter.py` is not
  yet deletable
- CLI smoke passed after this layer
- stale import scans confirm the removed UI emitter, deleted compatibility
  modules, and old edit-session paths are no longer used by live code
- `git diff --check` passed after this layer

### Package Root Module Cleanup Layer

Ran a 10-brief DeepSeek/Hermes audit swarm over top-level `vibecomfy/*.py`.
Results are in `docs/structure_cleanup/vibe_root_results/`.

Applied cleanup:

- deleted pure compile/helper root shims:
  `vibecomfy/_graph_utils.py`, `vibecomfy/_helper_resolve.py`,
  `vibecomfy/_widget_aliases.py`, and `vibecomfy/_workflow_helpers.py`
- updated `vibecomfy/workflow.py` to import canonical helpers from
  `vibecomfy._compile._resolve`, `vibecomfy._compile._widgets`, and
  `vibecomfy._compile._helpers`
- deleted dead root `vibecomfy/source_map.py`; only historical/audit docs
  referenced it
- deleted shadowed `vibecomfy/node_packs.py`; imports resolve to the
  `vibecomfy/node_packs/` package
- migrated node-pack root shim callers to `vibecomfy.node_packs` and deleted
  `vibecomfy/node_packs_git.py`, `vibecomfy/node_packs_install.py`, and
  `vibecomfy/node_packs_lockfile.py`
- kept private install-helper tests on `vibecomfy.node_packs._install` rather
  than re-exposing private helpers from the package
- updated active docs and comments to point at canonical `_compile` and
  `node_packs/` package paths

Kept / deferred:

- kept public root API modules such as `workflow.py`, `templates.py`,
  `handles.py`, `artifacts.py`, `errors.py`, `cli.py`, `cli_loader.py`,
  `utils.py`, and `extras.py`
- kept real implementation modules such as `comfy_backend.py`,
  `scratchpad_loader.py`, `local_library.py`, `model_assets.py`, `fetch.py`,
  and `checks.py`; moving those is a behavior/public-boundary refactor, not a
  deletion-first shim cleanup

Verification:

- import smoke for `vibecomfy.node_packs`, `resolve_pack`, `install_pack`,
  lockfile helpers, and `VibeWorkflow` passed
- focused root/node-pack suite passed:
  `tests/test_workflow_helpers.py`, `tests/test_widget_aliases.py`,
  `tests/test_node_packs_compat.py`, `tests/test_node_packs_git.py`,
  `tests/test_nodes_lock.py`, `tests/test_nodes_install.py`,
  `tests/test_runtime_ensure_env.py`, `tests/security/test_install_pack_gate.py`,
  and `tests/test_cli_sources_workflows_nodes.py` (`135 passed`)
- additional lockfile/import consumer tests passed:
  selected drift tests plus `tests/test_pack_provenance.py`,
  `tests/test_custom_node_refs.py`, `tests/test_template_traceability.py`,
  `tests/test_doctor_lockfile.py`, `tests/test_doctor_diagnostics.py`, and
  `tests/test_porting_object_info.py` (`70 passed`)
- CLI smoke passed for `python -m vibecomfy.cli --help` and
  `python -m vibecomfy.cli workflows list --ready --json` (`64` ready rows)
- `python -m vibecomfy.cli nodes list --json` currently requires
  `node_index.json`; that generated index was intentionally removed in an
  earlier cleanup layer, so the command reports `node_index.json not found; run
  vibecomfy sources sync`
- live-code stale import scans found no references to the deleted root shim
  modules
- `git diff --check` is run after this layer

### Runtime Cleanup Layer

Ran a 10-brief DeepSeek/Hermes audit swarm over `vibecomfy/runtime/`. Results
are in `docs/structure_cleanup/runtime_results/`.

Applied cleanup:

- migrated eval tests from old flat modules to canonical package imports:
  `vibecomfy.runtime.eval.prompt` and `vibecomfy.runtime.eval.plan`
- deleted the shadowed flat eval module and duplicate flat eval helpers:
  `vibecomfy/runtime/eval.py`, `eval_plan.py`, `eval_prompt.py`, and
  `preview_types.py`
- kept the canonical eval package surface under `vibecomfy/runtime/eval/`,
  including `from vibecomfy.runtime.eval import compile_eval_subgraph`
- deleted zero-import runtime helper modules:
  `watchdog_runtime.py`, `fingerprint.py`, `discovery.py`, `policy.py`, and
  `metadata.py`
- extended `tests/test_runtime_eval_absence.py` so live code cannot reintroduce
  imports from the removed flat runtime modules
- updated `docs/plans/revised_plan.md` to remove the stale thin-shim strategy
  for runtime eval and node-pack cleanup; the current policy is to migrate
  callers and delete old files unless a hard public contract requires a
  temporary shim

Kept / deferred:

- kept `server_process.py`; it is still imported by `runtime/server.py` and
  `runtime/config.py`
- kept `config.py`, `server.py`, `session.py`, `execution.py`, `attempt.py`,
  `run.py`, `watchdog.py`, `drift.py`, `ensure_env.py`, `model_policy.py`,
  `_local_library_yaml.py`, and `prompt.py`; these are live runtime surfaces or
  behavior-bearing modules, not safe shim deletes
- deferred the larger `session.py` process/config/output decomposition; that is
  a behavior refactor, not a deletion-first structure cleanup

Verification:

- import smoke passed for canonical eval imports, and `importlib.util.find_spec`
  returned `None` for deleted flat modules:
  `runtime.eval_plan`, `runtime.eval_prompt`, `runtime.preview_types`,
  `runtime.metadata`, `runtime.watchdog_runtime`, `runtime.fingerprint`,
  `runtime.discovery`, and `runtime.policy`
- runtime-only focused tests passed:
  `tests/test_runtime_eval_absence.py`, selected eval-subgraph tests from
  `tests/test_runtime_run.py`, `tests/test_runtime_session_config.py`, and
  `tests/test_runtime_execution.py` (`56 passed`)
- broader `tests/test_agentic_affordances.py` was also run with the runtime
  subset; it exited under the repo's known-failure plugin with `57 passed` and
  `9` known baseline failures, not new import/deletion failures
- CLI smoke passed:
  `python -m vibecomfy.cli --help`,
  `python -m vibecomfy.cli runtime --help`, and
  `python -m vibecomfy.cli workflows list --ready --json` (`64` ready rows)
- live-code stale import scan found no references to the deleted runtime module
  paths outside the intentional absence guard test
- `git diff --check` passed
- removed local `.pytest_cache` and `__pycache__/` directories outside `.venv`
  and `vendor/ComfyUI`

### Nodes Layer

Ran a 10-brief DeepSeek/Hermes audit swarm over `vibecomfy/nodes/`. Results are
in `docs/structure_cleanup/nodes_results/`.

Applied cleanup:

- rewrote `vibecomfy/nodes/__init__.py` from 19 hardcoded wildcard imports plus
  a huge static `__all__` into a compact dynamic barrel over
  `vibecomfy.nodes._generated.MODULES`
- updated `tools/generate_node_shims.py` so future node-wrapper generation keeps
  the compact dynamic `nodes/__init__.py`
- removed the generic `write_json` helper from `vibecomfy/nodes/index.py`; the
  only caller now uses the ingest-layer `write_index` helper directly
- ran `python -m tools.generate_node_shims` as a determinism check, then removed
  unintended local-cache generated output (`custom_nodes_offline`) and restored
  tracked generated wrapper churn; no generated wrapper content is part of this
  layer's final diff

Kept / deferred:

- kept all 19 `vibecomfy/nodes/<pack>.py` and `.pyi` files despite their
  re-export shape, because the swarm found this is the documented public
  authoring API (`from vibecomfy.nodes.core import SaveImage`) used by README,
  authoring docs, ready templates, generated goldens, and tests
- kept `vibecomfy/nodes/__init__.pyi` static because type checkers can resolve
  the explicit wildcard stub imports; a dynamic stub would be less useful
- kept `vibecomfy/nodes/index.py` as the live node-indexing boundary after
  removing the unrelated generic JSON writer
- deferred any migration to `vibecomfy.nodes._generated.<pack>` imports; that
  would leak an internal generated path into user-facing templates and would
  require rewriting ready templates, emitter output, and characterization
  goldens for little structural gain

Verification:

- import smoke passed:
  `from vibecomfy.nodes import KSampler, EmptyImage, WanVideoSampler`,
  `from vibecomfy.nodes.core import SaveImage`, and
  `from vibecomfy.nodes.index import index_custom_node_examples, index_runtime_nodes`
  (`1399` root node exports)
- focused nodes suite passed with the known-red test deselected:
  `tests/test_node_shims.py`, `tests/test_generated_node_wrappers.py`,
  `tests/test_nodes_index.py`, and `tests/test_cli_sources_workflows_nodes.py`
  (`45 passed, 1 deselected`)
- the same focused suite was also run without deselection; it exited under the
  repo's known-failure plugin with `45 passed` and one known baseline failure
  in `test_generated_wrapper_rejects_multiple_positional_workflows`, not a
  nodes-structure regression
- CLI smoke passed:
  `python -m vibecomfy.cli workflows list --ready --json` (`64` ready rows)
- stale scan found no remaining imports of `write_json` from
  `vibecomfy.nodes.index` and no `custom_nodes_offline` module references
- `git diff --check` passed
- removed local `.pytest_cache` after verification

### Comfy Nodes Layer

Ran a 10-brief DeepSeek/Hermes audit swarm over `vibecomfy/comfy_nodes/`.
Results are in `docs/structure_cleanup/comfy_nodes_results/`.

Applied deletion-first cleanup:

- deleted the dead `vibecomfy/comfy_nodes/stages/` package; its imports pointed
  at long-removed `agent_*` modules, and no live code imported it
- deleted `vibecomfy/comfy_nodes/session_io.py`; its only internal dependency
  was the dead `stages` package and no live code imported it
- deleted unused `vibecomfy/comfy_nodes/_time_utils.py`
- deleted web debris from `vibecomfy/comfy_nodes/web/`:
  `.gitkeep`, `package.json`, `panel_thread.js.bak`, and
  `vibecomfy_roundtrip.js.bak`

Kept / deferred:

- kept `vibecomfy/comfy_nodes/agent/` despite large modules because it is the
  live backend surface covered by the agent edit tests
- kept `exec_node.py` and `exec_examples.py`; `exec_examples.py` is live data
  for the exec node rather than standalone documentation
- kept the live web JS files, `astrid_logo.png`, and
  `agent_edit_response_contract_generated.js`; the generated contract file is
  intentionally tracked and drift-guarded by `tests/test_agent_contract_codegen.py`
- deferred smaller agent-module deduplication (`_now`, route recovery helpers)
  because this layer was deletion-first and those are live-code refactors

Verification:

- stale-reference scan found no remaining references to deleted stages,
  `session_io`, `_time_utils`, or web `.bak` files outside
  `docs/structure_cleanup/`
- import smoke passed for `vibecomfy.comfy_nodes.agent`, `exec_node`,
  top-level `NODE_CLASS_MAPPINGS`, and `WEB_DIRECTORY`
- focused tests passed:
  `tests/test_comfy_exec_node.py`, `tests/test_agent_contract_codegen.py`, and
  `tests/test_comfy_nodes_entrypoint.py` (`15 passed`)
- CLI smoke passed:
  `python -m vibecomfy.cli workflows list --ready --json` (`64` ready rows)
- `git diff --check` passed

## Next Recommended Layer

Continue with one of the remaining top-level surfaces:

1. Run the next focused package pass over `vibecomfy/intent`, `contracts`, and
   `security` boundaries; those are small but highly connected, so deletion
   should be conservative and import-topology-backed.
2. Run a docs-root follow-up for the remaining active root docs if the next
   code package pass does not surface a higher-value deletion.
