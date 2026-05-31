# Manifest Contract — M6 Discovery Trust Boundary

**Status:** Specification (T1 audit). Authoritative for the manifest-first, non-executing discovery surface that replaces the eager `exec_module` seam in `megaplan/_pipeline/registry.py`.

---

## 1. Current-state audit (`registry.py` as of M5b)

### 1.1 `_load_module_from_path` (lines 333–372)

The current discovery import seam **executes arbitrary top-level module code** on every `megaplan` command that triggers discovery (list, status, profile resolution, run). The function:

- For in-tree sibling files (`.py`, not `__init__.py`): calls `importlib.import_module(dotted)` which **executes the module**.
- For in-tree packages (`__init__.py`): calls `importlib.import_module(dotted)` which **executes the package**.
- For out-of-tree/user modules (`~/.megaplan/pipelines/`): uses `importlib.util.spec_from_file_location` + `spec.loader.exec_module(module)` which **executes arbitrary user code** (the ACE — Arbitrary Code Execution — surface, line 368).

On any import failure the function returns `None` **silently** (line 369: `except Exception: return None`). A typo'd entrypoint, a missing `SKILL.md`, or any runtime error in the module's top-level code vanishes without a trace.

### 1.2 `_module_metadata` (lines 375–389)

Reads module-level constants via `getattr` **after import** — requires the module to already be loaded (i.e., after `exec_module` has run). Current keys: `description`, `default_profile`, `supported_modes`, `recommended_profiles`. No `arnold_api_version`, no `driver`, no `capabilities`, no `name` (name is derived from the file stem, not declared).

### 1.3 `_BUILTIN_NAMES` (line 85)

`frozenset({"planning"})` — the sole hardcoded built-in. Discovery skips any CLI name that collides with a built-in (line 442 in `scan_python_pipelines`, line 566 in `discover_python_pipelines`). The built-in registration happens at import time via `_planning_builder` (lines 586–595).

### 1.4 `_planning_builder` (lines 586–595)

A deferred-import callable that wraps `compile_planning_pipeline()` from `megaplan._pipeline.planning`. Registered programmatically at module import time — planning is **not** discovered; it's hardcoded.

### 1.5 `discover_python_pipelines` (lines 507–578)

The primary discovery entry point. Delegates to `scan_python_pipelines` for the full scan, then:

1. Warns on builtin-name collisions (lines 527–534).
2. Collects rejected in-tree modules for an aggregate `RuntimeError` (line 537).
3. Warns on rejected user modules (lines 540–546).
4. **Secondary loop** (lines 562–576): re-walks every scan root and **re-imports** every module via `_load_module_from_path` (line 568) — this is a second execution pass over already-scanned modules. Returns `(cli_name, build_callable, metadata, source_path)` quads.

### 1.6 `scan_python_pipelines` (lines 401–504)

The full-scan function that returns a `Disposition` for every encountered path. Uses `_scan_dir_for_pipeline_modules` (lines 291–330) to enumerate candidate modules, then attempts `_load_module_from_path` for each. Produces dispositions with status `"discovered"`, `"rejected"`, or `"skipped"`.

### 1.7 `Disposition` dataclass (lines 53–81)

```python
@dataclass
class Disposition:
    path: Path
    origin: str          # "in_tree" | "user"
    status: str          # "discovered" | "rejected" | "skipped"
    reason: str
    traceback: Optional[str] = None
    cli_name: Optional[str] = None
```

### 1.8 Path-derived origins

- `"in_tree"` — `package_prefix == "megaplan.pipelines"` (line 431)
- `"user"` — `package_prefix is None` (`~/.megaplan/pipelines/`, line 431)

No trust tier currently exists — `origin` is informational only and carries no execution gate.

---

## 2. Manifest-first contract (target state)

### 2.1 Static manifest file

Every pipeline package **MUST** ship a `MANIFEST.json` (or `manifest.json`) in its root alongside `build_pipeline()` / `__init__.py`. The manifest is read via **`ast.parse` + `ast.literal_eval`** (or a `json.loads` equivalent for pure-JSON manifests) **without importing the module**. This means the manifest MUST be valid Python literal syntax or valid JSON — no expressions, no imports, no f-strings.

**Required fields:**

| Field | Type | Description |
|---|---|---|
| `name` | `str` | CLI-visible name (hyphenated). Must match the file-stem / directory name derived name. |
| `driver` | `str` | The driver substrate identifier (e.g., `"subprocess_isolated"`, `"graph"`, `"loop"`). |
| `entrypoint` | `str` | The dotted Python path to `build_pipeline` (e.g., `"megaplan.pipelines.planning:build_pipeline"`). |
| `capabilities` | `list[str]` | Declared capability kinds (e.g., `["execute", "review", "gate"]`). New/unknown kinds → DENY by default. |
| `arnold_api_version` | `str` | Semver major.minor (e.g., `"1.0"`). Checked at discovery with **no import**. |
| `default_profile` | `str \| null` | Default profile name, or `null`. |
| `supported_modes` | `list[str]` | List of supported mode strings (empty list if none). |

**Optional fields:**

| Field | Type | Description |
|---|---|---|
| `description` | `str` | Human-readable pipeline description. |
| `recommended_profiles` | `list[str]` | Recommended profile names. |
| `schema_version` | `int` | Manifest schema version (default `1`). |

### 2.2 Reading the manifest without import

The manifest reader MUST:

1. Locate `MANIFEST.json` (or `manifest.json`) adjacent to the discovered module file (sibling for `.py` files, same directory for `__init__.py` packages).
2. Read the raw bytes.
3. Parse with `json.loads()` (preferred) or `ast.literal_eval()`.
4. Validate all required fields are present and correctly typed.
5. Reject loudly on parse failure, missing fields, or type errors — `Disposition(status="rejected", reason="...")`.

**No `importlib`, no `exec_module`, no `getattr`.** The manifest is the **only** source of metadata during discovery.

### 2.3 SKILL.md by-convention sibling file rule

- `SKILL.md` is **required** for every pipeline package.
- Location: sibling to the manifest — same directory as the module file.
  - Sibling-file modules (`writing_panel_strict.py`) → `SKILL.md` lives in the hyphenated resource directory (`writing-panel-strict/SKILL.md`), matching the existing `read_skill_md` layout at `registry.py:191-195`.
  - Package modules (`__init__.py`) → `SKILL.md` lives alongside `__init__.py`.
- Discovery MUST check for `SKILL.md` existence at scan time. **Missing `SKILL.md` → loud rejection** (`Disposition(status="rejected", reason="missing required SKILL.md")`). No silent vanish.
- The existing `PipelineRegistry.read_skill_md()` method (lines 169–199) already implements this layout — the M6 change makes the **existence check mandatory at discovery** rather than a graceful `None` return at read time.

### 2.4 `exec_module` deferral seam

The current `_load_module_from_path` eagerly executes `spec.loader.exec_module(module)` (line 368) for every discovered module. Under the manifest-first contract:

1. **Discovery phase:** Read `MANIFEST.json` only. Do NOT import the module. Do NOT call `exec_module`. The `_load_module_from_path` function is replaced with a manifest reader — the old `exec_module` path is gated behind trust-tier selection.

2. **Selection phase:** When a pipeline is selected to run (`registry.get(name)` / `get_pipeline(name)`), the module is imported via `importlib.import_module()` **only if** the trust tier permits it:
   - `in-tree` → auto-exec on selection (trusted, same as today but deferred from discovery to selection).
   - `out-of-tree` / `user` → quarantined by default; runs only if explicitly allowed or promoted to `blessed`.
   - `blessed` → explicit allowlist, auto-exec on selection.
   - Unknown/unspecified tier → DENY (no execution).

3. The existing `_module_metadata` function (lines 375–389) is **replaced** by manifest reading during discovery. After import (at selection time), module-level constants can still be read for backward compatibility, but the manifest is authoritative.

### 2.5 `arnold_api_version` range check

- Supported range: `[1.0, current-major)` where `current-major` is the SDK's major version.
- The check is performed at discovery time from the manifest field — **no import required**.
- Out-of-range → `Disposition(status="rejected", reason="arnold_api_version X.Y is outside supported range [1.0, N.0)")`.
- Missing field → `Disposition(status="rejected", reason="missing required field 'arnold_api_version'")`.
- Malformed version string → `Disposition(status="rejected", reason="arnold_api_version '...' is not a valid semver major.minor")`.

### 2.6 Path-derived trust tiers

Three tiers, computed from the scan root `origin` (already available at `registry.py:431`):

| Tier | Origin | Behavior |
|---|---|---|
| `in-tree` | `package_prefix == "megaplan.pipelines"` | Trusted. Manifest validated, `SKILL.md` required. Auto-exec on selection. |
| `out-of-tree` | `package_prefix is None` (user home) | Untrusted. Manifest validated, `SKILL.md` required. Quarantined — manifest-only at discovery; execution requires explicit allow or promotion to `blessed`. SDK-assigned `tenant_id = hash(name + install_path)`. |
| `blessed` | Either origin, promoted via allowlist | Trusted. Explicit allowlist entry (default empty). Auto-exec on selection. Promotion gated on graph-abuse oracle pass. |

The trust tier is **path-derived** (computed from `origin` and an allowlist), never from a prompt or a module-level constant. It is **not** stored in the manifest — it's a runtime property of the discovery surface.

### 2.7 Disposition failure modes

All failures produce a `Disposition` with `status="rejected"`. The existing `scan_python_pipelines` contract (lines 401–504) already returns a `Disposition` for every path. The manifest-first contract extends the rejection reasons:

| Failure | `reason` field | `traceback` |
|---|---|---|
| Manifest file missing | `"missing required MANIFEST.json"` | `None` |
| Manifest parse error | `"MANIFEST.json is not valid JSON: <error>"` | parse error string |
| Missing required field | `"missing required field '<field>' in MANIFEST.json"` | `None` |
| Wrong field type | `"field '<field>' in MANIFEST.json: expected <type>, got <actual>"` | `None` |
| `arnold_api_version` out of range | `"arnold_api_version <ver> is outside supported range [1.0, <current-major>)"` | `None` |
| `arnold_api_version` malformed | `"arnold_api_version '<ver>' is not a valid semver major.minor"` | `None` |
| `SKILL.md` missing | `"missing required SKILL.md"` | `None` |
| Capability DENY (new unknown kind) | `"capability '<kind>' is not recognized; package quarantined"` | `None` |
| Module import failure (at selection time) | `"module could not be imported: <error>"` | full traceback |

The `discover_python_pipelines` function's existing aggregate-raise behavior (lines 549–554) is preserved: rejected in-tree modules cause a collective `RuntimeError`; rejected user modules emit `UserWarning`.

### 2.8 Rejected dispositions are **loud**

- Every rejected disposition is catalogued and surfaced in `doctor`/`check` output.
- In-tree rejections raise `RuntimeError` (aggregate, after full scan — preserving the existing collect-then-raise pattern at lines 549–554).
- User rejections emit `UserWarning` (preserving lines 540–546).
- Rejected packages are **excluded from the runnable set** — `registry.names()` does not include them.
- The system proceeds with remaining valid packages (never fails-fast on a single bad package).

---

## 3. Migration from current state

### 3.1 What changes

1. **`_load_module_from_path`** (lines 333–372) → replaced with a manifest reader that does zero imports. The `exec_module` call moves to a new `_import_module_for_run` function gated on trust tier.

2. **`_module_metadata`** (lines 375–389) → replaced with manifest-field extraction. The `getattr`-based reading is retired for discovery; it may survive as a fallback at selection time for backward compat.

3. **`_scan_dir_for_pipeline_modules`** (lines 291–330) → extended to also locate `MANIFEST.json` and `SKILL.md` alongside each candidate module file.

4. **`scan_python_pipelines`** (lines 401–504) → the `_load_module_from_path` call at line 467 is replaced with manifest reading. The `getattr(module, "build_pipeline", None)` check at line 484 moves to selection time.

5. **`discover_python_pipelines`** (lines 507–578) → the secondary loop at lines 562–576 (which re-imports modules) is **eliminated**. The quad construction `(cli_name, build, metadata, module_file)` becomes `(cli_name, manifest, module_file)` — the builder callable is resolved at selection time, not discovery time.

6. **`_BUILTIN_NAMES`** (line 85) → removed. Planning becomes a discovered package with its own `MANIFEST.json` and `SKILL.md`.

7. **`_planning_builder`** (lines 586–595) → the programmatic registration is removed. Planning is discovered like any other pipeline.

### 3.2 What stays

- `PipelineRegistry` class and its lazy `_ensure_discovered` pattern.
- `_GLOBAL_REGISTRY` singleton.
- `register_pipeline`, `get_pipeline`, `registered_pipelines`, `describe_pipeline`, `pipeline_metadata`, `read_pipeline_skill_md`, `run_pipeline_by_name` public API.
- `Disposition` dataclass (extended with trust-tier information as needed).
- `_scan_dir_for_pipeline_modules` directory-walking logic.
- `_get_scan_roots` and `_SCAN_ROOTS`.
- `_cli_name` helper.
- The aggregate-raise pattern for in-tree rejections.
- The `UserWarning` pattern for user rejections.

---

## 4. Validation checklist

- [ ] `MANIFEST.json` is read via `json.loads()` or `ast.literal_eval()` — no `importlib`, no `exec_module`, no `getattr` during discovery.
- [ ] All required fields (`name`, `driver`, `entrypoint`, `capabilities`, `arnold_api_version`, `default_profile`, `supported_modes`) are validated.
- [ ] `arnold_api_version` is range-checked `[1.0, current-major)`.
- [ ] Missing `SKILL.md` produces `Disposition(status="rejected")`.
- [ ] Manifest parse failures produce `Disposition(status="rejected")` with descriptive `reason`.
- [ ] Unknown capability kinds produce DENY + quarantine (not silent skip).
- [ ] Trust tier is path-derived (`in-tree` / `out-of-tree` / `blessed`), never from module code.
- [ ] `exec_module` is deferred to selection time, gated on trust tier.
- [ ] `_BUILTIN_NAMES` is removed.
- [ ] `_planning_builder` programmatic registration is removed.
- [ ] The secondary import loop in `discover_python_pipelines` (line ~568) is eliminated.
- [ ] Rejected in-tree modules still raise aggregate `RuntimeError` (collect-then-raise).
- [ ] Rejected user modules still emit `UserWarning`.
- [ ] Rejected packages are excluded from `registry.names()`.
- [ ] `PipelineRegistry._ensure_discovered` still gates on `_discovered` flag to prevent recursive discovery.
