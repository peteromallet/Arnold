# Structural Smell Swarm Findings - 2026-07-09

DeepSeek swarm run:

- Model: `deepseek:deepseek-v4-pro`
- Lanes: 30
- Result: 30 succeeded, 0 failed
- Raw output: `/tmp/vibecomfy-structural-smell-swarm-results`
- Report index: `/tmp/vibecomfy-structural-smell-swarm-results/_report.json`

This report intentionally ignores the accidental Desloppify output from this session. The findings below are synthesized from the DeepSeek lane outputs only.

## Executive Summary

The dominant smell is not file size by itself. It is dual authority: old compatibility fields, mirrors, source-generation shims, and permissive fallbacks remained live after newer canonical systems were added. That means bugs can survive because two paths both look valid, tests often check one path, and production can exercise another.

The top remediation theme is to pick canonical owners and make compatibility paths fail closed behind explicit tests or feature flags.

## Highest Priority Findings

### 1. Frontend state still has compatibility mirrors as live data

Evidence:

- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
- `vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js`
- `vibecomfy/comfy_nodes/web/agent_edit_response_contract.js`
- `vibecomfy/comfy_nodes/web/diagnostics_reporting.js`

The swarm repeatedly flagged `chatMessages` vs. `transcriptMessages`, `executionEvents` vs. `turns`, and candidate/baseline aliases as live dual-authority state. These are not just backwards-compatible readers. They are still written, snapshotted, restored, and consulted by separate paths.

Recommended fix:

1. Make one canonical transcript source.
2. Make one canonical execution-event source.
3. Remove direct legacy writes from lifecycle transitions.
4. Keep legacy readers only at process boundaries, with tests proving canonical output.
5. Add a lifecycle invariant test that runs every transition and asserts mirrors are absent or derived.

### 2. Agent-edit backend uses runtime source assembly

Evidence:

- `vibecomfy/comfy_nodes/agent/edit.py`
- `vibecomfy/comfy_nodes/agent/edit_*.py`

The agent-edit implementation is split into many modules that hold `SOURCE = r'''...'''` blocks, then `edit.py` concatenates and `exec(compile(...))`s them into one namespace. This defeats import contracts, static analysis, independent tests, and normal refactoring.

Recommended fix:

1. Convert each `SOURCE` body into a real Python module.
2. Replace the installer with explicit imports and a re-export facade.
3. Add a test that each module is independently importable.
4. Add a test that the facade exports exactly the intended public API.

### 3. Import boundaries are inverted in several core layers

Evidence:

- `vibecomfy/porting/edit/ops.py` imports error classes from `vibecomfy/comfy_nodes/agent/provider.py`.
- `vibecomfy/comfy_nodes/agent/provider.py` runtime-imports back from `vibecomfy/porting/edit/ops.py`.
- `vibecomfy/porting/workbench.py` imports `vibecomfy.cli_loader` and `vibecomfy.commands._workflow_path`.
- `vibecomfy/contracts/surface.py` imports from `vibecomfy.porting`.

These are layer inversions. Core edit/contract libraries should not depend on agent runtime or CLI modules.

Recommended fix:

1. Move shared errors out of `provider.py` into a neutral contract/error module.
2. Move workflow path and ready-id helpers out of CLI modules into a shared library module.
3. Either move `contracts.surface` out of the contracts package or invert its dependency via protocol/data input.
4. Add importlinter-style tests for these boundaries.

### 4. Error taxonomy is not actually central

Evidence:

- `vibecomfy/errors.py`
- Many `*Error` classes in `porting`, `executor`, `search`, `agent`, `comfy_nodes`.

The codebase has a central `VibeComfyError` contract, but many domain errors inherit directly from `Exception`, `RuntimeError`, or `ValueError`. That means structured fields such as remediation hints, severity, and serialized diagnostics are inconsistent.

Recommended fix:

1. Rebase domain errors onto `VibeComfyError` unless explicitly allowlisted.
2. Add default `next_action` values for agent-facing failures.
3. Add an AST-based test that every first-party `*Error` inherits from `VibeComfyError` or appears in a tiny allowlist.

### 5. Browser test coverage is largely non-gating

Evidence:

- `tests/test_comfy_nodes_browser.py`
- `tests/browser/*.test.mjs`

Only `roundtrip_smoke.test.mjs` is wired through the Python test runner. The rest of the browser test suite can rot unless manually invoked. Several ownership tests are source-regex checks rather than runtime behavior checks.

Recommended fix:

1. Add a gated target that runs `node --test tests/browser/`.
2. At minimum, wire critical contract files: `agent_edit_response_contract.test.mjs`, `agent_edit_lifecycle.test.mjs`, `canonical_delta.test.mjs`, and `payload_contracts.test.mjs`.
3. Keep static ownership checks as secondary lint, not primary behavioral proof.

### 6. Preview overlay still has stale test/probe and geometry contracts

Evidence:

- `tests/e2e/helpers/canvas-debug-probes.mjs`
- `vibecomfy/comfy_nodes/web/comfy_adapter.js`
- `vibecomfy/comfy_nodes/web/panel_overlay.js`
- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`

The e2e probe reads `app.__vibecomfyAgentPreviewOverlayDraw`, while the adapter writes `app.__vibecomfyPreviewForegroundDraw`. There is also an unused `canvasRect()` helper that suggests HiDPI/CSS-pixel geometry was recognized but not integrated.

Recommended fix:

1. Update the probe to the current sentinel and assert installer strategy too.
2. Either wire `canvasRect()` into the draw transform with a pixel test, or delete it and document the current coordinate constraint.
3. Export a single `clearPreviewDomOverlayForApp(app)` path instead of hardcoding `app?.canvas?.canvas?.ownerDocument` in the shell.

### 7. Credential handling exposes more than it needs to

Evidence:

- `vibecomfy/comfy_nodes/web/agent_status_poller.js`
- `vibecomfy/comfy_nodes/agent/provider.py`
- `scripts/run_local_agent_comfy.sh`

The browser stores the raw OpenRouter key in `panel.state.lastAutoSavedOpenRouterKey` as a dedup marker. Credential save responses include absolute filesystem paths. Shell and Python `.env` readers parse differently.

Recommended fix:

1. Store a hash/nonce instead of the raw key in browser panel state.
2. Remove `path` from credential-save JSON responses.
3. Create one canonical `.env` parsing helper and use it in Python entry points; make shell scripts source the env file instead of grepping.

### 8. Packaging and install recipes diverge

Evidence:

- `Makefile`
- `pyproject.toml`
- CI workflow files
- `uv.lock`

The swarm found ghost packages installed in CI, divergent install recipes, duplicate optional dependency groups, and `custom_nodes.lock` entries with `version = "unknown"`.

Recommended fix:

1. Make `pyproject.toml` the install authority.
2. Make CI install through one shared target.
3. Add a dependency freshness check for generated/lock artifacts.

### 9. Reorganise and session modules have too much authority in one place

Evidence:

- `vibecomfy/porting/reorganise/compile.py`
- `vibecomfy/porting/reorganise/orchestrate.py`
- `vibecomfy/comfy_nodes/agent/session.py`

These modules combine parsing, planning, validation, persistence, lifecycle state mutation, CAS checks, and rendering/response details. The risk is not merely line count; it is that invariants have no narrow owner.

Recommended fix:

1. Split session into `_paths`, `_locking`, `_state`, `_lifecycle`, and `_rebaseline` modules.
2. Split reorganise compilation by phase and add phase input/output contracts.
3. Add consistency validators at state transition boundaries.

### 10. Documentation and stale artifacts can contradict current code

Evidence:

- `docs/plans/*`
- tracked megaplan/worktree artifacts
- migration docs

Several plan documents describe superseded architectures. This is not a runtime bug, but it can mislead agents and humans into reviving old paths.

Recommended fix:

1. Add status headers to plan docs: active, superseded, historical.
2. Move stale operational notes under an archive path.
3. Add a doc freshness check for known plan categories.

## Suggested Cleanup Order

1. Fix preview overlay probe and DOM-clear path. Small, directly related to the visible preview bug class.
2. Wire the browser contract tests into CI/local `make` targets so frontend cleanup has a real safety net.
3. Remove frontend compatibility dual writes for transcript/turn mirrors.
4. Break the `porting.edit.ops` / `provider.py` circular dependency.
5. Convert agent-edit `SOURCE` modules into real modules.
6. Centralize first-party errors under `VibeComfyError`.
7. Split session/reorganise authority after the above gates exist.
8. Clean packaging/install drift and stale docs.

## Raw Lane Index

Raw outputs are in `/tmp/vibecomfy-structural-smell-swarm-results`:

- `01_frontend_shell_boundaries.txt`
- `02_frontend_lifecycle_contract.txt`
- `03_frontend_preview_replay_demo.txt`
- `04_frontend_overlay_canvas.txt`
- `05_frontend_thread_rendering.txt`
- `06_frontend_composer_status.txt`
- `07_frontend_runtime_scope.txt`
- `08_frontend_contract_normalizers.txt`
- `09_frontend_tests_strategy.txt`
- `10_e2e_browser_specs.txt`
- `11_agent_server_routes.txt`
- `12_agent_edit_backend.txt`
- `13_porting_edit_apply.txt`
- `14_porting_reorganise.txt`
- `15_porting_emit_codegen.txt`
- `16_porting_object_info_widgets.txt`
- `17_porting_layout.txt`
- `18_workflow_ir_runtime.txt`
- `19_cli_commands.txt`
- `20_scripts_operational_runpod.txt`
- `21_scripts_data_ingest_upload.txt`
- `22_docs_plans_staleness.txt`
- `23_ready_templates_workflows.txt`
- `24_packaging_dependencies.txt`
- `25_security_keys_paths.txt`
- `26_error_taxonomy_logging.txt`
- `27_state_mirror_compat.txt`
- `28_import_cycles_boundaries.txt`
- `29_dead_code_stale_artifacts.txt`
- `30_cross_cutting_synthesis.txt`
