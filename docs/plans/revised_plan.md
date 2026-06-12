# Implementation Plan: M0 — Tier 1: All 11 LOW-risk reorg units

## Overview

Land all 11 LOW-risk mechanical reorg units from the phase2 reorg plan. Each unit is a behavior-preserving mechanical move: folder bundles, barrel-`__init__` re-exports where they represent the canonical package API, dead-file deletes, and the `nodes/` shim elimination. No logic changes. Old file shims should be deleted after callers move to canonical paths, unless a hard external public contract makes a temporary shim unavoidable.

### Verified Current State (as of 2026-06-11)

| Unit | Status | What's actually in the working tree |
|------|--------|-------------------------------------|
| 1 | **DONE** | `testing/__init__.py:60-66` already imports from `.fixtures` — NO-OP |
| 2 | **Partial** | `_debug_resolver.py` already gone; `node_index.json` still at root (`[]`, zero refs) |
| 3 | **DONE** | `patches/resize_schema.py` deleted — confirmed orphan, zero references |
| 4 | **NOT done** | FOUR files at root: `node_packs.py` (465 LOC), `node_packs_lockfile.py` (334 LOC), `node_packs_install.py` (659 LOC), `node_packs_git.py` (123 LOC). `node_packs_git.py` has zero cross-refs with the other three; imported by `runtime/ensure_env.py:11` and `tests/test_node_packs_git.py:8`. |
| 5 | **DONE** | `router.py` deleted; `vibecomfy/router/` package exists with `__init__.py` barrel; `router_rules.py` is thin shim → `vibecomfy.router._rules` |
| 6 | **NOT done** | Two files at root: `fixtures.py` (288 LOC, zero Python importers, has `__main__` block for `python -m vibecomfy.fixtures`); `_agent_edit_debug.py` (504 LOC, 3 importers: `scripts/vibecomfy_debug.py:10`, `commands/debug.py:5`, `tests/test_cli_debug.py:143,181`) |
| 7 | **NOT done** | `wrapper_discovery.py` (616 LOC), `wrapper_codegen.py` (539 LOC) at `porting/`; internal cross-ref `wrapper_codegen.py:71` → `wrapper_discovery`; 6 external importers (3 files × 2 imports each) using `from vibecomfy.porting import wrapper_*` |
| 8 | **DONE** | Flat runtime eval files were deleted after moving test importers to canonical `vibecomfy.runtime.eval.*` paths. `from vibecomfy.runtime.eval import compile_eval_subgraph` remains supported by the package barrel. |
| 9 | **DONE** | Dead runtime helpers `discovery.py`, `policy.py`, `metadata.py`, `fingerprint.py`, and `watchdog_runtime.py` are gone; no live Python importers remain. |
| 10 | **DONE** | The 19 pack files remain as the documented public authoring API (`from vibecomfy.nodes.core import SaveImage`), which is the rare shim exception. `nodes/__init__.py` now computes root exports from `_generated.MODULES` instead of hardcoding 19 wildcard imports and a huge static `__all__`. |
| 11 | **Partial** | `registry.py` and `factory.py` already gone; `provider.py:22` already imports `InputSpec`/`OutputSpec` from `.types`; `format.py` (9 LOC) has 3 external importers (`doctor.py:31`, `validate.py:17`, `session.py:931`); `diagnostics/__init__.py` has types defined inline at lines 8-53 (needs extraction to `findings.py`) |

### Locked decisions

- **Every barrel `__init__.py` re-exports the identical names** — existing `from vibecomfy.<x> import Y` paths stay byte-for-byte valid.
- **Dead-code deletes** (Units 2, 3, 9) confirmed via grep for zero importers.
- **Unit 5 (router) and Unit 10 (nodes/)** are the two that touch surfaces real code depends on — verify identity explicitly post-move.
- **Each unit lands as its own commit**, gate-green between each.
- **Deletion-first compatibility policy:** update internal callers to canonical package paths and delete old file shims. Keep a shim only for an extreme case with a known public contract and a removal plan.

### Decisions on open questions

1. **Unit 10 public shim exception**: Keep ALL 19 pack files because they are the documented public authoring API. The 19 wildcard lines become a loop over `_generated.MODULES`. Public pack imports stay — `from vibecomfy.nodes.core import SaveImage` paths survive.

2. **Unit 4 includes node_packs_git.py**: Bundle it as `node_packs/_git.py`, move callers to `vibecomfy.node_packs`, then delete `node_packs_git.py`. This completes the "bundle ALL node_packs_* files into a package" intent without retaining a root shim.

3. **Unit 6 includes _agent_edit_debug.py**: The file EXISTS (verified). Move to `commands/_agent_edit_debug.py` with a thin shim at the old root location. This completes Unit 6's intended scope.

4. **Unit 7 uses deletion-first migration**: Move callers to `vibecomfy.porting.wrappers.*`, then delete `porting/wrapper_discovery.py` and `porting/wrapper_codegen.py`.

5. **Unit 8 uses deletion-first migration**: Move test importers to `runtime/eval/` modules, then delete `runtime/eval_prompt.py`, `runtime/eval_plan.py`, `runtime/preview_types.py`, and the shadowed `runtime/eval.py`. The `runtime/eval/__init__.py` barrel preserves the canonical package import `from vibecomfy.runtime.eval import compile_eval_subgraph`.

6. **Unit 9 is complete**: Dead runtime files (`discovery.py`, `policy.py`, `metadata.py`, `fingerprint.py`, and `watchdog_runtime.py`) are physically deleted.

7. **`queue_eval_subgraph` omitted from barrel**: Doesn't exist in any file (confirmed via grep). Not included.

8. **Unit 8 `preview_types.py`**: Exists at `runtime/preview_types.py` (confirmed). Move to `runtime/eval/preview_types.py`.

---

## Phase 0 — Land already-done units as NO-OP commits

### Step 1: Confirm and commit Unit 1 (testing fixtures)
**Complexity:** 1

1. **Verify** `vibecomfy/testing/__init__.py:60-66` already imports from `.fixtures` (confirmed — 5 names: `dry_runtime`, `make_handle_factory`, `make_workflow_factory`, `vibecomfy_handle_factory`, `vibecomfy_workflow_factory`).
2. **Gate**: `PYTHONHASHSEED=0 pytest tests/characterization -x -q`
3. **Commit** as NO-OP confirmation: `"Unit 1: testing fixture stubs — confirmed already wired (NO-OP)"`

### Step 2: Confirm and commit Unit 2 (_debug_resolver.py already gone)
**Complexity:** 1

1. **Verify** `_debug_resolver.py` absent from repo (confirmed — no file found, zero content references).
2. **Gate**: `python -c "import vibecomfy"` succeeds.
3. **Commit** as NO-OP: `"Unit 2: _debug_resolver.py removal — confirmed already gone (NO-OP)"`

---

## Phase 1 — Deletes (straightforward, lowest risk)

### Step 3: Delete node_index.json (Unit 2 remainder)
**Complexity:** 1

1. **Confirm** `node_index.json` contains `[]` and has zero references.
2. **Delete** `node_index.json`.
3. **Gate**: `python -c "import vibecomfy"` + characterization gate.
4. **Commit**.

### Step 4: Delete patches/resize_schema.py (Unit 3) ✅ DONE
**Complexity:** 1

1. ✅ **Confirmed** `vibecomfy/patches/resize_schema.py` was NOT in `patches/__init__.py`.
2. ✅ **Confirmed** zero importers.
3. ✅ **Deleted** `vibecomfy/patches/resize_schema.py`.
4. ✅ **Gate passed**: `python -c "import vibecomfy"` + characterization gate.
5. ✅ **Committed**.

### Step 5: Delete dead runtime files (Unit 9) ✅ DONE
**Complexity:** 1

1. ✅ **Confirmed** zero Python importers for:
   - `vibecomfy/runtime/discovery.py`
   - `vibecomfy/runtime/policy.py`
   - `vibecomfy/runtime/metadata.py`
   - `vibecomfy/runtime/fingerprint.py`
   - `vibecomfy/runtime/watchdog_runtime.py`
2. ✅ **Deleted** all five files.
3. ✅ **Confirmed** no live code imports the removed runtime helper paths.
4. **Gate**: runtime-focused verification is recorded in
   `docs/structure_cleanup/status.md`.

---

## Phase 2 — Units with package moves

### Step 6: Bundle router rules into router/ package (Unit 5) ✅ DONE
**Complexity:** 2

1. ✅ **Created** `vibecomfy/router/` directory.
2. ✅ **Moved** `vibecomfy/router.py` → `vibecomfy/router/_core.py`; `vibecomfy/router_rules.py` → `vibecomfy/router/_rules.py`.
3. ✅ **Updated internal cross-ref** at `router/_core.py:8` to use the package-local `_rules` module.
4. ✅ **Created** `vibecomfy/router/__init__.py` barrel re-exporting `RouterResult`, `pick`, `Rule`, `register_route`, `rules`.
5. ✅ **Removed** the temporary `vibecomfy/router_rules.py` shim after internal callers moved to `vibecomfy.router`.
6. ✅ **Verified** `vibecomfy/__init__.py:15` (`from . import router`) still works — Python imports the `router/` package's `__init__.py`.
7. ✅ **Verified identity**: `python -c "from vibecomfy.router import pick, RouterResult, register_route, rules; print('OK')"`.
8. ✅ **Gate passed**: characterization gate.
9. ✅ **Committed**.

### Step 7: Move fixtures.py → testing/_fixtures_smoke.py (Unit 6 — part A)
**Complexity:** 2

1. **Move** `vibecomfy/fixtures.py` → `vibecomfy/testing/_fixtures_smoke.py`.
2. **Keep only the public CLI wrapper** `vibecomfy/fixtures.py`, re-exporting from `vibecomfy.testing._fixtures_smoke` and preserving the `__main__` block so `python -m vibecomfy.fixtures list` continues to work. This is the one justified compatibility exception in this unit. The wrapper should include:
   ```python
   from vibecomfy.testing._fixtures_smoke import *
   from vibecomfy.testing._fixtures_smoke import __all__
   if __name__ == "__main__":
       from vibecomfy.testing._fixtures_smoke import main
       main()
   ```
3. **Verify** `python -m vibecomfy.fixtures list` still works.
4. **Gate**: characterization gate.
5. **Commit**.

### Step 8: Move _agent_edit_debug.py → commands/_agent_edit_debug.py (Unit 6 — part B)
**Complexity:** 2

1. **Move** `vibecomfy/_agent_edit_debug.py` → `vibecomfy/commands/_agent_edit_debug.py`.
2. **Update all internal importers** (`scripts/vibecomfy_debug.py`, `commands/debug.py`, `tests/test_cli_debug.py`) to import `vibecomfy.commands._agent_edit_debug`.
3. **Delete** `vibecomfy/_agent_edit_debug.py`; do not keep a private root shim.
4. **Gate**: characterization gate.
5. **Commit**.

### Step 9: Move wrappers into porting/wrappers/ package (Unit 7)
**Complexity:** 2

1. **Create** `vibecomfy/porting/wrappers/` directory.
2. **Move** `vibecomfy/porting/wrapper_discovery.py` → `vibecomfy/porting/wrappers/discovery.py`.
3. **Move** `vibecomfy/porting/wrapper_codegen.py` → `vibecomfy/porting/wrappers/codegen.py`.
4. **Update internal cross-ref** at `wrappers/codegen.py:71` to import `ClassSpec` and `InputFieldSpec` from the package-local discovery module.
5. **Create** `vibecomfy/porting/wrappers/__init__.py` barrel re-exporting `ClassSpec`, `InputFieldSpec`, `DiscoveryError`, `Source`, `DEFAULT_PRECEDENCE`, `discover_all`, `discover_pack`, `known_pack_slug`, `sha256_of_path` from discovery.py and `GENERATOR_VERSION`, `RenderResult`, `parse_generated_header`, `render_pack`, `render_widget_schema` from codegen.py.
6. **Create thin shims** at old locations:
   - `vibecomfy/porting/wrapper_discovery.py`: `from vibecomfy.porting.wrappers.discovery import *`
   - `vibecomfy/porting/wrapper_codegen.py`: `from vibecomfy.porting.wrappers.codegen import *`
   This preserves ALL 6 external importers without touching any of them:
   - `commands/nodes.py:24-25`
   - `tests/test_wrapper_codegen.py:18`
   - `tests/test_wrapper_discovery.py:16`
   - `scripts/demo_wrapper_codegen.py:27-28`
7. **Verify** `python -c "from vibecomfy.porting.wrappers import discovery as wd, codegen as wc; print('OK')"`.
8. **Gate**: characterization gate.
9. **Commit**.

### Step 10: Move eval files into runtime/eval/ package (Unit 8) ✅ DONE
**Complexity:** 2

1. ✅ **Created** `vibecomfy/runtime/eval/` directory.
2. ✅ **Moved files**:
   - `vibecomfy/runtime/eval.py` → `vibecomfy/runtime/eval/core.py`
   - `vibecomfy/runtime/eval_plan.py` → `vibecomfy/runtime/eval/plan.py`
   - `vibecomfy/runtime/eval_prompt.py` → `vibecomfy/runtime/eval/prompt.py`
   - `vibecomfy/runtime/preview_types.py` → `vibecomfy/runtime/eval/preview_types.py`
3. ✅ **Updated internal imports**:
   - `plan.py:8` → `from .preview_types import preview_plan_for_type`
   - `prompt.py:11` → `from .plan import EvalNodePlan, plan_eval_node`
4. ✅ **Created** `vibecomfy/runtime/eval/__init__.py` barrel re-exporting
   `compile_eval_subgraph`, `EvalNodePlan`, `plan_eval_node`,
   `EvalNodeResult`, `eval_node`, `eval_node_sync`, `queue_api_for_plan`,
   `PreviewInjection`, `PreviewPlan`, and `preview_plan_for_type`.
5. ✅ **Migrated callers** from old flat eval modules to canonical
   `vibecomfy.runtime.eval.*` package paths.
6. ✅ **Deleted** old flat eval files instead of keeping shims:
   `runtime/eval.py`, `runtime/eval_plan.py`, `runtime/eval_prompt.py`, and
   `runtime/preview_types.py`.
7. ✅ **Added guard coverage** in `tests/test_runtime_eval_absence.py` to
   prevent live code from importing removed flat runtime modules again.
8. **Gate**: runtime-focused verification is recorded in
   `docs/structure_cleanup/status.md`.

---

## Phase 3 — Unit 4: Bundle ALL node_packs_* files (highest complexity)

### Step 11: Bundle all 4 node_packs_* files into node_packs/ package (Unit 4)
**Complexity:** 3

1. **Create** `vibecomfy/node_packs/` directory **if it doesn't already exist**. Note: after this step, `node_packs/` is the directory package and the root `node_packs*.py` files should not remain.
   - To avoid a transient name collision during the move, do the moves before creating the package `__init__.py`.
2. **Move files**:
   - `vibecomfy/node_packs.py` → `vibecomfy/node_packs/_defs.py`
   - `vibecomfy/node_packs_lockfile.py` → `vibecomfy/node_packs/_lockfile.py`
   - `vibecomfy/node_packs_install.py` → `vibecomfy/node_packs/_install.py`
   - `vibecomfy/node_packs_git.py` → `vibecomfy/node_packs/_git.py`
3. **Update internal cross-references** to relative imports:
   - `_defs.py:7`: `from vibecomfy.node_packs import LockEntry, read_lockfile` → `from ._lockfile import LockEntry, read_lockfile`
   - `_install.py:7`: `from vibecomfy.node_packs import CustomNodePack, get_known_node_packs, resolve_node_packs, unresolved_class_types` → `from ._defs import CustomNodePack, get_known_node_packs, resolve_node_packs, unresolved_class_types`
   - `_install.py:8`: `from vibecomfy.node_packs import LockEntry, upsert_lockfile_entry` → `from ._lockfile import LockEntry, upsert_lockfile_entry`
   - `_git.py` has no cross-refs to the other three (confirmed) — no updates needed.
4. **Create** `vibecomfy/node_packs/__init__.py` barrel re-exporting all public names from all four sub-modules:
   - From `_defs`: `CustomNodePack`, `get_known_node_packs`, `resolve_node_packs`, `unresolved_class_types`
   - From `_lockfile`: `LockEntry`, `read_lockfile`, `write_lockfile`, `upsert_lockfile_entry`
   - From `_install`: install-related public names (check `__all__` if present, otherwise all public functions/classes)
   - From `_git`: `InstalledPackGitRef`, `find_installed_pack_ref`
5. **Migrate callers** from the old root modules to `vibecomfy.node_packs` or the private package modules where tests intentionally exercise internals, then delete the old root files:
   - `vibecomfy/node_packs.py`
   - `vibecomfy/node_packs_lockfile.py`
   - `vibecomfy/node_packs_install.py`
   - `vibecomfy/node_packs_git.py`
6. **Verify edge case**: `commands/nodes.py:22` should import the canonical package and still access the install helpers it needs. Verify: `python -c "import vibecomfy.node_packs as npi; print(dir(npi)[:10])"`.
7. **Verify** key import paths:
   - `python -c "from vibecomfy.node_packs import resolve_node_packs, CustomNodePack; print('OK')"`
   - `python -c "from vibecomfy.node_packs import LockEntry; print('OK')"`
   - `python -c "from vibecomfy.node_packs import find_installed_pack_ref; print('OK')"`
8. **Gate**: characterization gate.
9. **Commit**.

**Note on move order**: Python cannot have both a `node_packs.py` file and a `node_packs/` directory in the same parent package. The move sequence must be:
1. Rename `node_packs.py` → `node_packs/_defs.py` (via git mv or OS move into the newly-created `node_packs/` dir)
2. Create `node_packs/__init__.py`
3. Delete the old root `node_packs*.py` files after callers use the package.
The directory `node_packs/` must be created before the file moves into it. Use
`mkdir -p vibecomfy/node_packs` first, then move all four files in, create
`__init__.py`, migrate importers, and delete the old root files.

---

## Phase 4 — Unit 10: Programmatic nodes/__init__.py

### Step 12: Rewrite nodes/__init__.py with programmatic wildcard imports (Unit 10) ✅ DONE
**Complexity:** 2

1. ✅ **Read** `vibecomfy/nodes/_generated/__init__.py:1` — confirmed: `MODULES = ['core', 'kjnodes', 'ltxvideo', 'videohelpersuite', 'controlnet_aux', 'depthanythingv2', 'wanvideowrapper', 'qwentts', 'qwen3tts', 'gguf', 'rgthree', 'sam2', 'wananimatepreprocess', 'ailab_audioduration', 'custom_scripts', 'florence2', 'gimm_vfi', 'melbandroformer', 'vibecomfy_internal']` (19 entries).
2. ✅ **Rewrote** `vibecomfy/nodes/__init__.py`: replaced the 19 hardcoded `from vibecomfy.nodes.<pack> import *` lines and huge static `__all__` with a loop over `_generated.MODULES` that imports each public pack module, collects `__all__`, and merges exports into globals. The programmatic import pattern:
   ```python
   from __future__ import annotations
   from vibecomfy.nodes._generated import MODULES

   __all__: list[str] = []
   for _module_name in MODULES:
       _mod = __import__(f"vibecomfy.nodes.{_module_name}", fromlist=["*"])
       _mod_all = getattr(_mod, "__all__", None)
       if _mod_all is not None:
           __all__.extend(_mod_all)
           for _name in _mod_all:
               globals()[_name] = getattr(_mod, _name)
   ```
3. ✅ **Kept** `vibecomfy/nodes/__init__.pyi` static because type checkers resolve wildcard stub imports statically; dynamic stubs would lose useful IDE/type-checker behavior.
4. ✅ **Kept all 19 public pack files** — do not delete any. `from vibecomfy.nodes.core import SaveImage` paths survive.
5. ✅ **Also removed** the generic `write_json` helper from `vibecomfy/nodes/index.py` by using the ingest-layer `write_index` helper at the only call site.
6. ✅ **Updated** `tools/generate_node_shims.py` so future generation preserves the compact dynamic `nodes/__init__.py`.
7. ✅ **Verified identity**:
   - `python -c "from vibecomfy.nodes import *; print(len(__all__))"` — record the count before and after; must be identical.
   - `python -c "from vibecomfy.nodes.core import SaveImage; print('OK')"`
   - `python -c "from vibecomfy.nodes import SaveImage; print('OK')"`
8. ✅ **Gate passed**: focused nodes/import tests and CLI smoke are recorded in
   `docs/structure_cleanup/status.md`.

---

## Phase 5 — Unit 11: Schema/diagnostics tidy

### Step 13: Merge format.py into validate.py; extract diagnostics to findings.py (Unit 11)
**Complexity:** 2

1. **Merge** `vibecomfy/schema/format.py` (9 LOC — `format_issue` function) into `vibecomfy/schema/validate.py`. Append the function to validate.py.
2. **Create thin shim** `vibecomfy/schema/format.py`: `from vibecomfy.schema.validate import format_issue`. Preserves 3 external importers (`doctor.py:31`, `validate.py:17`, `session.py:931`).
3. **Extract diagnostics types** from `vibecomfy/diagnostics/__init__.py` (lines 8-53: `Severity` type alias, `DiagnosticFinding` dataclass, `PatchSuggestion` dataclass, `finding_messages`, `findings_payload`, `patch_suggestions_payload`) to new `vibecomfy/diagnostics/findings.py`.
4. **Rewrite** `vibecomfy/diagnostics/__init__.py` as pure re-export barrel:
   ```python
   from __future__ import annotations
   from vibecomfy.diagnostics.findings import (
       DiagnosticFinding, PatchSuggestion, Severity,
       finding_messages, findings_payload, patch_suggestions_payload,
   )
   from vibecomfy.diagnostics.health import HealthReport, SubcheckFinding, SubcheckResult

   __all__ = [
       "DiagnosticFinding",
       "HealthReport",
       "PatchSuggestion",
       "Severity",
       "SubcheckFinding",
       "SubcheckResult",
       "finding_messages",
       "findings_payload",
       "patch_suggestions_payload",
   ]
   ```
5. **Verify** `provider.py:22` already imports `InputSpec`/`OutputSpec` from `.types` (confirmed — no dedup needed). No changes to `provider.py`.
6. **Delete** obsolete `registry.py` and `factory.py` from `vibecomfy/schema/`; provider-backed implementations are already exported by `schema/__init__.py`.
7. **Move** `format_issue` into `vibecomfy.schema.validate`, update internal imports, and delete `vibecomfy/schema/format.py`.
8. **Verify** `python -c "from vibecomfy.diagnostics import DiagnosticFinding, HealthReport; print('OK')"`.
9. **Gate**: characterization gate.
10. **Commit**.

---

## Execution Order

1. **Phase 0**: Steps 1–2 (NO-OP commits for Units 1 and 2 partial)
2. **Phase 1**: Steps 3–5 (deletes: node_index.json, resize_schema.py, dead runtime files)
3. **Phase 2**: Steps 6–10 (package moves; migrate callers and delete old files unless a hard public contract requires a temporary shim)
4. **Phase 3**: Step 11 (node_packs bundle — all 4 files)
5. **Phase 4**: Step 12 (nodes/__init__.py programmatic rewrite)
6. **Phase 5**: Step 13 (schema/diagnostics tidy)

Gate green between each commit.

## Validation Order

1. After each step: `PYTHONHASHSEED=0 pytest tests/characterization -x -q`
2. After each phase: `python -c "import vibecomfy"` + spot-check key import paths
3. After final step: full `pytest` against `tests/known_failures.txt` baseline
4. Final: `python -c "import vibecomfy; print([n for n in vibecomfy.__all__])"` — verify all names importable
