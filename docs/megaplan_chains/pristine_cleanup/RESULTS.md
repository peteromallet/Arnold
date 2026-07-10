# Pristine Cleanup Results

Date: 2026-05-24

This file reconciles the original 10-lens audit against the current
`megaplan/pristine-cleanup` worktree. It is evidence-only: statuses below are
backed by existing audit files, chain artifacts, current source inspection, and
the green publish precheck recorded by batch T2.

Status meanings:

- `fixed` - the current tree contains a concrete code, test, or docs change that
  resolves the audit finding.
- `deferred` - the finding remains, is intentionally outside this cleanup pass,
  or needs a later design decision.
- `won't-fix` - the finding was a false positive, no longer applies to this
  checkout, or is explicitly accepted.

## Summary Evidence

- Green pre-bookkeeping gate from T2: `python -m pytest` passed with `543 passed,
  11 skipped, 5 deselected, 1 xfailed`; the four required CLI smoke commands
  also exited 0, including `python -m vibecomfy.cli port check image/z_image
  --json`.
- M1 safety evidence: `docs/audits/m1-safety-gate.md`.
- M1 duplicate inventory: `docs/megaplan_chains/pristine_cleanup/artifacts/m1-duplication-inventory.md`.
- M2 helper consolidation map: `docs/audits/m2-symbol-map.md`.
- M2 dirty-worktree classification: `docs/audits/m2-diff-hygiene.md`.
- M6 public API contract: `docs/api/m6-public-api.md`.
- M7 documentation reconciliation is present in the working tree via
  `README.md`, `CLAUDE.md`, `AGENTS.md`, `docs/historical/`,
  `docs/release_notes.md`, and deleted stale docs.

## God-File LOC

| Original audit target | Baseline LOC | Current equivalent file(s) | Current LOC | Result |
| --- | ---: | --- | ---: | --- |
| `emitter.py` | 3304 | `vibecomfy/porting/emitter.py` | 171 | fixed |
| `session.py` | 1379 | `vibecomfy/runtime/session.py` | 439 | fixed |
| `provider.py` | 984 | `vibecomfy/schema/provider.py` | 42 | fixed |

Supporting current count command:

```text
wc -l vibecomfy/porting/emitter.py vibecomfy/runtime/session.py vibecomfy/schema/provider.py
```

Observed current output: `171`, `439`, and `42` lines respectively.

## Duplicate-Removal Count

The M1 duplicate inventory recorded 32 search matches across the target helper
families. Re-running the same search against the current tree returns 24
matches. More importantly, the duplicated local helper definitions called out by
the inventory are gone:

- `_is_link`: 5 local definitions in M1 -> 0 old local definitions now; callers
  use `vibecomfy._graph_utils.is_api_link(...)`.
- `_id_sort_key` / `_node_sort_key`: 2 local definitions in M1 -> 0 old local
  definitions now; callers use `vibecomfy._graph_utils.node_id_sort_key(...)`.
- `_git_head`: 3 local definitions in M1 -> 0 old local definitions now; callers
  use `vibecomfy._git_utils.git_head(...)`.
- `UI_ONLY_CLASS_TYPES`: tool-local constant moved to
  `vibecomfy._graph_utils.UI_ONLY_CLASS_TYPES`.

Backed count: 8 inventory search matches removed (`32 -> 24`) and 10 duplicated
local helper definitions collapsed into canonical helpers, with one UI-only
constant relocated. Evidence: M1 inventory, `docs/audits/m2-symbol-map.md`, and
current `rg` inspection.

## Lens 1 - CLI Commands

- `fixed` - Corrupted `port.py:611` / missing `port doctor-all` path: current
  `vibecomfy/commands/port.py` is a small registered command module with
  `validate-call` and `check`; the T2 `port check image/z_image --json` smoke
  passed.
- `fixed` - `validate.py` ignored `--json`: current
  `vibecomfy/commands/validate.py` registers `--json` and emits structured
  report/error payloads through `commands._output.emit`.
- `fixed` - Dead `--backend` argument in `validate.py`: current validate parser
  has `path`, `--json`, and `--no-schema`; no unused `--backend` remains.
- `deferred` - `nodes spec` always prints JSON: not part of the current publish
  evidence and not fixed by the cleanup branch.
- `won't-fix` - `commands/test.py` local `_emit`: no current `vibecomfy/commands/test.py`
  exists in this checkout.
- `deferred` - `analyze.py` parallel output system: current source still has a
  separate analyze command surface; no evidence of full output unification.
- `fixed` - `fetch.py` / `doctor.py` duplicate model-entry helpers: shared model
  logic now lives in `vibecomfy/commands/_model_entries.py`.
- `fixed` - `doctor.py` / `nodes.py` duplicate `_git_head`: both use
  `vibecomfy._git_utils.git_head(...)`; see `docs/audits/m2-symbol-map.md`.
- `deferred` - `schemas.py` mixed raw prints and `emit`: no current
  `vibecomfy/commands/schemas.py` command module is registered; no active fix was
  needed for publish.
- `deferred` - `commands/session.py` dual CLI/daemon role: current command still
  exists and session lifecycle split work focused on runtime internals.

## Lens 2 - Porting / Codemod

- `fixed` - `emitter.py` god-module: reduced from 3304 LOC to 171 LOC, with
  supporting modules under `vibecomfy/porting/{formatting,loader,naming,node_kwargs,templates,widget_schema}.py`.
- `won't-fix` - `_sort_key` duplicated in older `widget_aliases.py` /
  `workbench.py`: those older files and helper names are absent from this
  checkout; M2 recorded them as absent older-tree targets.
- `won't-fix` - `OPAQUE_COMPONENT_CLASS_RE` duplicated: no current matches in
  the M1/M2 search roots.
- `fixed` - `UI_ONLY_CLASS_TYPES` duplicated: centralized in
  `vibecomfy._graph_utils.UI_ONLY_CLASS_TYPES`.
- `fixed` - Widget-key translation duplication: current porting split routes
  node kwargs through `vibecomfy/porting/node_kwargs.py` and widget schema
  resolution through `vibecomfy/porting/widget_schema.py`.
- `won't-fix` - `_readability_diagnostics` reimplemented alias analysis: older
  `workbench.py` target is absent.
- `won't-fix` - Private `_looks_like_model_value` cross-import: older
  `convert.py` / `workbench.py` target is absent.
- `fixed` - Parallel porting diagnostic dataclasses: current port command maps
  workflow `ValidationIssue` through `vibecomfy.diagnostics.DiagnosticFinding`;
  no old `EmissionDiagnostic` / `PortIssue` / `LintDiagnostic` trio remains.
- `won't-fix` - Competing strict template linters: older `workbench.py` /
  `lint.py` targets are absent.
- `deferred` - `WIDGET_SCHEMA` / `WIDGET_SEMANTIC_NAMES` precedence: current
  `vibecomfy/porting/widget_schema.py` remains a focused schema module; no
  further consolidation was required for publish.
- `fixed` - Local emitter topological sort: current topological naming/order
  logic lives in `vibecomfy/porting/naming.py`.

## Lens 3 - Public API Surface & Naming

- `fixed` - Missing `workflow_from_template` / `load_template`: both are exported
  from `vibecomfy.__all__`; see current `vibecomfy/__init__.py` and
  `docs/api/m6-public-api.md`.
- `fixed` - `run_embedded` / `run_embedded_sync` omitted from `__all__`: both are
  now exported and documented in M6.
- `fixed` - `load_workflow_json` not top-level: exported from `vibecomfy` and
  listed in M6.
- `deferred` - `VibeInput.media_semantics` / `media` dual naming: not addressed
  by the current publish branch.
- `won't-fix` - Public `export_to_json` duplicate of `compile("api")`: M6 records
  `compile("api")` as the sole documented export path and explicitly declines a
  separate public export method.
- `deferred` - `blocks.__all__` re-exporting `Handle`: not changed by the current
  branch.
- `deferred` - `Handle` vs `Handles` naming ambiguity: no current cleanup evidence.
- `deferred` - `set_input` mutating widgets as fallback: no current cleanup evidence.
- `deferred` - `router.pick` terse naming: no current cleanup evidence.

## Lens 4 - Layer 2 Architecture

- `deferred` - `ltx_lowvram` patch hardcoded template node IDs: current
  `vibecomfy/patches/ltx_lowvram.py` remains in the patch layer.
- `deferred` - `gguf_unet` patch changes loader class types: current
  `vibecomfy/patches/gguf_unet.py` remains in the patch layer.
- `deferred` - `controlnet` patch adds nodes and splices conditioning: current
  `vibecomfy/patches/controlnet.py` remains in the patch layer.
- `deferred` - Patch docstring permits broad graph mutation: current patch
  architecture still allows broad patch behavior.
- `won't-fix` - `resize_schema.py` orphan patch: no current
  `vibecomfy/patches/resize_schema.py` exists.
- `deferred` - Separate patches/ops registries: current
  `vibecomfy/patches/registry.py` and `vibecomfy/ops/registry.py` remain.
- `deferred` - Mixed patch factory/singleton convention: current `patches`
  package still includes both styles.
- `deferred` - Thin one-patch recipes: current `recipes/wan_i2v_lowres.py` and
  `recipes/wan_t2v_long.py` remain.

## Lens 5 - Runtime & Execution

- `fixed` - Three overlapping eval modules: current tree has no
  `vibecomfy/runtime/eval.py`, `eval_plan.py`, or `eval_prompt.py`; absence is
  covered by `tests/test_runtime_eval_absence.py` and M1 safety evidence.
- `won't-fix` - Broken `test_agentic_affordances.py` import: that test file is
  absent in the current checkout.
- `fixed` - Dead `queue_eval_subgraph`: removed with the old eval modules.
- `fixed` - Queue/wait/output logic triplication: shared queue logic is in
  `vibecomfy/runtime/execution.py`; runtime prompt preparation is in
  `vibecomfy/runtime/prompt.py`.
- `fixed` - `session.py` god-class: reduced from 1379 LOC to 439 LOC, with
  runtime support split into `config.py`, `discovery.py`, `execution.py`,
  `fingerprint.py`, `metadata.py`, `policy.py`, `prompt.py`, `server.py`, and
  `server_process.py`.
- `fixed` - Duplicated `_on_schema_unavailable`: current schema-unavailable
  handling is shared through `runtime.prompt.emit_schema_unavailable_once`.
- `deferred` - Asymmetric `ensure_packs` parameter: no current publish evidence
  of API unification.
- `deferred` - `watchdog.py:write_report` uses broad `Any`: `runtime/watchdog.py`
  remains outside the session split.

## Lens 6 - Errors, Diagnostics, Next Action

- `fixed` - `_prepare_prompt` wrappers dropped `next_action`: current
  `vibecomfy/runtime/prompt.py` wraps build failures in `WorkflowBuildError`
  with `next_action`.
- `fixed` - Raw session lifecycle `RuntimeError`s: current
  `vibecomfy/runtime/session.py` raises `SessionBusyError`,
  `SessionLifecycleError`, and `NodePackInstallError` for the audited lifecycle
  paths.
- `fixed` - Duplicate diagnostics logic: current CLI-facing structured findings
  use `vibecomfy.diagnostics.DiagnosticFinding`; `port.py` and doctor diagnostic
  tests use that shared shape.
- `deferred` - `SyntaxError` caught naked in `commands/run.py`: no current
  evidence that CLI scratchpad syntax errors were normalized.
- `fixed` - Generic queue `next_action`: current `runtime/execution.py` uses
  separate embedded/server queue helpers with different remediation strings.
- `won't-fix` - `EnvironmentError` catch concern: audit already downgraded this
  as not a Python 3 bug.
- `fixed` - `next_action` formatting: current `VibeComfyError.__str__` prints a
  newline plus `Next action: ...`.
- `deferred` - `_session_url_healthy` Boolean failure shape: no current cleanup
  evidence.

## Lens 7 - Testing Infrastructure

- `fixed` - Public testing API stubs: current `vibecomfy/testing/__init__.py`
  imports real fixture helpers, and `docs/audits/m1-safety-gate.md` records a
  passing `from vibecomfy.testing import *` check.
- `fixed` - `_is_link` duplicated in testing/helpers: M2 removed the targeted
  local helper definitions and routes callers through `vibecomfy._graph_utils`.
- `won't-fix` - Misnamed `test_agentic_affordances.py`: file is absent.
- `won't-fix` - Bare `test_sisypy_integration.py` import: file is absent.
- `won't-fix` - Duplicated private workflow helpers in older testing files:
  current testing surface is `vibecomfy/testing/fixtures.py` plus
  `tests/test_testing_api.py`; older files are absent.
- `won't-fix` - `_runtime_session_helpers.py` fixture discovery pattern: older
  file is absent.
- `fixed` - Parity registry coverage gap: M1 safety evidence records 10 parity
  anchors covering all 9 `tests/snapshots/*.api.json` stems plus the preserved
  audio anchor.
- `fixed` - `_pytest_plugin.py` missing factory exports: current plugin exports
  `dry_runtime`, `vibecomfy_handle_factory`, `vibecomfy_workflow_factory`,
  `make_workflow_factory`, and `make_handle_factory`.

## Lens 8 - Schema & Node Specs

- `fixed` - Three overlapping validation schemas: current tree has one primary
  schema validation path in `vibecomfy/schema/validate.py`; tests assert
  `vibecomfy/porting/validate_call.py` is absent and no `NodeCallValidation` /
  `CallValidation` symbols remain.
- `fixed` - `provider.py` god module / misleading precedence comments: reduced
  from 984 LOC to 42 LOC, with implementation split across
  `schema/{factory,local,object_info,parsing,registry,runtime,types}.py`.
- `fixed` - Fictional handwritten nodes split: current `vibecomfy/nodes/`
  contains `__init__.py` and `index.py`, not 14 boilerplate re-export modules.
- `fixed` - Duplicate `.pyi` node stubs: no duplicate node-family `.pyi` stubs
  are present in the current `vibecomfy/nodes/` tree.
- `fixed` - Inconsistent schema attribute access across validation layers:
  current validation uses `getattr(schema, "inputs", {})`; old porting
  validation layer is absent.
- `won't-fix` - Dead `_generated/__init__.py`: no current `vibecomfy/nodes/_generated/`
  package exists.

## Lens 9 - Docs vs Reality

- `fixed` - `CLAUDE.md` / `AGENTS.md` byte-identical duplicate: current
  `AGENTS.md` is a short bootstrap and `CLAUDE.md` is the long-form source of
  truth.
- `fixed` - README dead bundled-skill path: current `README.md` points agents to
  `AGENTS.md` -> `CLAUDE.md` and states the old bundled-skill path is absent in
  this checkout.
- `fixed` - README v2.6 vs CLAUDE v2.7 API drift: README now documents the
  current `load -> edit -> patch/block -> validate -> run` flow and cites
  `docs/api/m6-public-api.md`.
- `fixed` - Historical docs marked active: stale docs are now under
  `docs/historical/`.
- `fixed` - Ephemeral sprint artifact docs: stale docs were moved/trimmed as
  part of M7 docs reconciliation.
- `fixed` - `docs/release_notes.md` stub shadows real notes: current tree has
  `docs/release_notes.md` plus `docs/release_notes/`; this reconciliation is
  present in the working tree.
- `fixed` - Sprint 5 copy-paste header: covered by the stale-doc reconciliation;
  no current follow-up file was found by name inspection.
- `deferred` - Missing v2.4 -> v2.5 migration guide: no evidence this migration
  gap was filled in the current branch.

## Lens 10 - Repo Hygiene

- `fixed` - Dead `vibecomfy/source_map.py`: absent; M1 safety evidence records
  no source references outside chain artifacts.
- `fixed` - `_literal_value` duplication: no live definitions under `vibecomfy`,
  `tests`, `tools`, or `scripts`; see M2 symbol map.
- `fixed` - `_call_name` duplication: no live definitions under `vibecomfy`,
  `tests`, `tools`, or `scripts`; see M2 symbol map.
- `fixed` - `_regen_templates.py` abandoned migration script: absent; M1 safety
  evidence records no source references outside chain artifacts.
- `won't-fix` - `template_index.json` generated/tracked claim: reviewers
  corrected this as repo-owned and intentionally tracked; `node_index.json` is
  not tracked.
- `fixed` - `this.env` credential risk: file is ignored and not tracked; M1
  safety evidence checks ignore rules without printing secrets.
- `fixed` - Tracked `__pycache__` / `.pyc`: current `git ls-files` check reports
  no tracked cache files.
- `fixed` - Tracked `.DS_Store`: current `git ls-files` check reports no tracked
  `.DS_Store`.
- `deferred` - Root clutter (`CUSTOM_NODES_AUDIT.md`, `custom_nodes.lock`, etc.):
  not part of the publish cleanup branch evidence.

## Late Follow-Ups / Deferred Items

- Layer-2 patch taxonomy remains the largest intentional deferral:
  `ltx_lowvram`, `gguf_unet`, `controlnet`, patch registry shape, and thin
  recipes still need a separate architecture decision.
- Runtime API polish remains partially deferred: `ensure_packs` asymmetry,
  watchdog typing, `commands/run.py` syntax-error handling, and session URL
  health diagnostics were not finished in this branch.
- Public API naming cleanup remains partially deferred: `VibeInput.media`, block
  `Handle` re-export ownership, `Handle` vs `Handles`, `set_input` widget
  fallback semantics, and `router.pick` naming were not changed.
- Documentation migration coverage remains incomplete for the v2.4 -> v2.5
  migration path.
- CLI output unification remains partial for `nodes spec`, `analyze`, and
  command/session daemon ergonomics.
