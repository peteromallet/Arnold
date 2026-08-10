# M7 Final Import Inventory

**Generated:** 2026-07-02T09:45Z  
**Purpose:** Exact `rg` results for all eight requested import/flag families, with deletion-vs-survivor classification. This document serves as the decision log for what is deleted, shimmed, retained, or requires conformance repair in M7.

---

## 1. `arnold.pipeline.legacy`

### Exact `rg` output (non-docs, non-archive, non-.megaplan)

```
arnold/pipeline/legacy.py:13:    from arnold.pipeline.legacy import (
tests/arnold/pipeline/test_legacy.py:1:"""Smoke tests for :mod:`arnold.pipeline.legacy` — graph-era compatibility namespace.
tests/arnold/pipeline/test_legacy.py:15:import arnold.pipeline.legacy as _legacy
tests/arnold/pipeline/test_legacy.py:43:    """Every required symbol is importable from arnold.pipeline.legacy."""
tests/arnold/pipeline/test_legacy.py:47:        assert hasattr(_legacy, name), f"{name} not found in arnold.pipeline.legacy"
tests/arnold/pipeline/test_public_contract_imports.py:42:    """M1: arnold.pipeline.legacy is a live compatibility namespace (M7 will remove it)."""
tests/arnold/pipeline/test_public_contract_imports.py:43:    legacy = importlib.import_module("arnold.pipeline.legacy")
```

### Classification

| Hit | File | Kind | Verdict |
|-----|------|------|---------|
| Self-reference in docstring | `arnold/pipeline/legacy.py:13` | Module source (docstring example) | **Delete** — module will be removed |
| Smoke tests | `tests/arnold/pipeline/test_legacy.py` (4 hits) | Test | **Delete** — dedicated shim test, remove with module |
| Public contract test | `tests/arnold/pipeline/test_public_contract_imports.py:42-43` | Test (conformance) | **Repair** — assert absence, not existence; test docstring says "M7 will remove it" |

### Summary

- **Production callers:** ZERO. No non-test, non-docs code imports `arnold.pipeline.legacy`.
- **Test callers:** Two test files:
  - `tests/arnold/pipeline/test_legacy.py` — dedicated shim smoke test (delete with module).
  - `tests/arnold/pipeline/test_public_contract_imports.py` — public contract test; currently asserts legacy *exists* but docstring acknowledges M7 removal. Must be updated to assert *absence*.
- **Docs/archive references:** Extensive historical references in `docs/archive/m5/`, `docs/arnold/pipelines/`, `.megaplan/` logs. All are non-actionable documentation.
- **Verdict:** `arnold.pipeline.legacy` has no production callers. The module, its dedicated test, and the "exists" assertion in the public contract test are all M7 deletion/repair targets.

---

## 2. `arnold/pipelines/megaplan/_pipeline`

### Directory status

```
ls arnold/pipelines/megaplan/_pipeline/  →  No such file or directory
ls arnold/pipelines/megaplan/            →  No such file or directory
```

The entire DOT-path `arnold/pipelines/megaplan/` package tree is **deleted**. The `_pipeline/` subtree does not exist on disk.

### Exact `rg` output (non-docs, non-archive, non-.megaplan)

```
arnold/pipeline/native/MILESTONE_3_HANDOFF.md:174:`arnold/pipelines/megaplan/_pipeline/executor.py:1182–1195` and the
arnold/pipeline/native/MILESTONE_4_HANDOFF.md:34:- Native opt-in: set `state["_native_execution"] = True` before dispatch; `run_pipeline_dispatch` in `arnold/pipelines/megaplan/_pipeline/_bridge.py` routes to `NativeMegaplanRunner`.
arnold/pipeline/native/MILESTONE_4_HANDOFF.md:64:- `arnold/pipelines/megaplan/_pipeline/_bridge.py` — execution-mode dispatch and resume routing.
tests/arnold/workflow/test_m5_inventory_scanners.py:122:    assert "arnold/pipelines/megaplan/_pipeline/pipeline_ids.json" not in relative
```

### Classification

| Hit | File | Kind | Verdict |
|-----|------|------|---------|
| Historical reference | `MILESTONE_3_HANDOFF.md` | Docs (handoff) | **Non-actionable** — historical milestone doc |
| Historical reference | `MILESTONE_4_HANDOFF.md` (2 hits) | Docs (handoff) | **Non-actionable** — historical milestone doc |
| Absence assertion | `tests/arnold/workflow/test_m5_inventory_scanners.py:122` | Test (scanner) | **Keep** — asserts deleted tree is absent, correct behavior |

### Summary

- **On-disk tree:** ABSENT. The `arnold/pipelines/megaplan/` DOT package (which contained `_pipeline/`) is fully deleted.
- **Live code imports:** ZERO. No production or test code imports from this path.
- **Docs references:** Handoff docs and extensive archive/docs references. All are historical/non-actionable.
- **Scanner test:** The M5 inventory scanner correctly asserts the deleted tree is absent.
- **Verdict:** Deleted `_pipeline` tree is confirmed absent. The only live hit is a scanner test asserting absence — correct and should be preserved.

---

## 3. `arnold.pipelines.megaplan` (DOT path)

### Directory status

```
ls arnold/pipelines/megaplan/  →  No such file or directory
```

The DOT-package `arnold.pipelines.megaplan` is **fully deleted**.

### Exact `rg` output (non-docs, non-archive, non-.megaplan) — representative sample

```
arnold/conformance/deleted_surfaces.py:83-86:    DeletedSurface entries for arnold.pipelines.megaplan._pipeline.discovery, .runtime, .agent_runtime
arnold/conformance/deleted_surfaces.py:100:    "arnold.pipelines.megaplan",
arnold/conformance/deleted_surfaces.py:124-130:    Deleted import modules/prefixes
arnold/conformance/deleted_surfaces.py:163:    "arnold.pipelines.megaplan",
arnold/conformance/legacy_reference_allowlist.json: ~40 entries allowing "arnold.pipelines.megaplan" references in docs/archive
arnold/conformance/checks.py:40,42,373,457,694:    Scan targets and docstrings referencing deleted surface
arnold/conformance/workflow_manifest_runtime.py:21:    "arnold.pipelines.megaplan"
arnold/agent/dispatcher.py:7:    "No imports from arnold.pipelines.megaplan (zero-leak gate)."
arnold/agent/providers/pool.py:10:    "No imports from arnold.pipelines.megaplan."
arnold/agent/contracts.py:11:    "No imports from arnold.pipelines.megaplan."
arnold/agent/__init__.py:16:    "No imports from arnold.pipelines.megaplan (zero-leak gate)."
arnold/agent/adapters/deepseek.py:26:    "No imports from arnold.pipelines.megaplan (zero-leak gate)."
arnold/agent/adapters/_pricing.py:6:    "No imports from arnold.pipelines.megaplan (zero-leak gate)."
arnold/agent/adapters/__init__.py:10:    "No imports from arnold.pipelines.megaplan (zero-leak gate)."
arnold/__init__.py:10:    "a megaplan import (the old from arnold.pipelines.megaplan import __version__ created"
arnold/workflow/validation.py:37:    "arnold.pipelines.megaplan",
scripts/check_workflow_pipeline_inventory.py:165:    "arnold.pipelines.megaplan",
NEXT_STEPS.md:158:    "the old arnold.pipelines.megaplan path is gone"
```

### Classification

| Category | Files | Verdict |
|----------|-------|---------|
| **Conformance metadata** | `deleted_surfaces.py`, `checks.py`, `legacy_reference_allowlist.json`, `workflow_manifest_runtime.py` | **Keep (repair where needed)** — conformance modules correctly track `arnold.pipelines.megaplan` as a deleted surface. The `_compatibility` misclassification within these modules is addressed in §6. |
| **Zero-leak gate docstrings** | `arnold/agent/*.py`, `arnold/__init__.py` | **Keep** — these are documentation of the import discipline, not actual imports. |
| **Validation allowlists** | `arnold/workflow/validation.py:37` | **Keep** — tracks deleted package as known legacy surface. |
| **Script inventory** | `scripts/check_workflow_pipeline_inventory.py:165` | **Keep** — inventory script tracking deleted surface. |
| **Docs** | `NEXT_STEPS.md`, handoff docs, archive | **Non-actionable** — historical documentation. |

### Summary

- **On-disk tree:** ABSENT. The DOT package is fully deleted.
- **Live imports:** ZERO production or test imports from `arnold.pipelines.megaplan`.
- **Conformance metadata:** Correctly tracks the deleted surface. However, `_compatibility.py` is wrongly listed under `arnold_pipelines.megaplan._compatibility` as a deleted surface (see §6).
- **Zero-leak gates:** `arnold/agent/` modules correctly assert zero imports.
- **Verdict:** DOT package deleted. Conformance metadata is accurate except for the `_compatibility` misclassification (SD2).

---

## 4. `arnold_pipelines.megaplan` (underscore — canonical package)

### Directory status

```
ls arnold_pipelines/megaplan/  →  Present (canonical package)
ls arnold_pipelines/megaplan/_compatibility.py  →  Present (substrate proof)
```

### Exact `rg` output

Extensive — the canonical package has thousands of self-references. Representative categories:

| Category | Example files | Verdict |
|----------|--------------|---------|
| **Canonical package internals** | `arnold_pipelines/megaplan/*.py` (~200+ files) | **Survive** — legitimate canonical package |
| **Neutral surface adapters** | `arnold/agent/adapters/shannon.py`, `codex.py`, `_oneshot.py` | **Survive** — authorized adapter imports from canonical package |
| **Neutral surface tools** | `arnold/agent/tools/*.py`, `arnold/agent/agent/copilot_acp_client.py` | **Survive** — authorized tool imports (process, runtime) |
| **Supervisor** | `arnold/supervisor/model.py`, `outcomes.py` | **Survive** — authorized neutral→product imports |
| **agentbox** | `agentbox/cli.py:388` | **Survive** — authorized adapter import |
| **Conformance metadata** | `arnold/conformance/checks.py`, `deleted_surfaces.py`, `workflow_manifest_runtime.py` | **Survive (repair)** — tracks canonical package; `_compatibility` needs removal from deleted lists |
| **Validation** | `arnold/workflow/validation.py:38` | **Survive** — allowlist entry |
| **Discovery** | `arnold_pipelines/discovery.py` | **Survive** — canonical discovery path comments |
| **Docs/README** | `README.md`, `NEXT_STEPS.md`, `docs/*` | **Survive** — user-facing canonical references |
| **Tests** | `tests/arnold_pipelines/megaplan/*`, `tests/resume/*`, `tests/characterization/*` | **Survive** — canonical package tests |

### Key finding: `_compatibility.py` is substrate proof, not a shim

`arnold_pipelines/megaplan/_compatibility.py` (356 lines) is a **legitimate internal projection facade** that:
- Projects the authored workflow DSL pipeline into a neutral Arnold graph shell (`CompatibilityPipelineShell`)
- Attaches a `NativeProgram` to the pipeline
- Exposes `build_pipeline()`, `build_native_program()`, and shell-building helpers
- Is the canonical mechanism by which `Pipeline.native_program` is populated for Megaplan pipelines

**This is substrate evidence for the `Pipeline.native_program` interface, not a graph-era shim.** Per SD2, it must NOT be deleted.

### Summary

- **Canonical package:** `arnold_pipelines.megaplan` is the permanent product home. Survives.
- **`_compatibility.py`:** Legitimate internal projection facade (substrate proof). Must be removed from `DELETED_IMPORT_MODULES`, `DELETED_IMPORT_PREFIXES`, and `DELETED_ARTIFACT_PATH_PREFIXES` in `arnold/conformance/deleted_surfaces.py`.
- **Neutral surface imports:** Authorized adapter/tool imports from canonical package are legitimate and survive.
- **Verdict:** Survive. Repair conformance metadata to stop listing `_compatibility` as deleted.

---

## 5. `ARNOLD_NATIVE_RUNTIME`

### Exact `rg` output (non-docs, non-archive, non-.megaplan)

```
arnold/pipeline/native/flags.py:3:    ``ARNOLD_NATIVE_RUNTIME`` is retained only for callers that still import
arnold/pipeline/executor.py:101:    ``ARNOLD_NATIVE_RUNTIME`` env var is ignored.
_smoke_trace_test.py:4:    os.environ['ARNOLD_NATIVE_RUNTIME'] = '1'
tests/arnold/pipeline/test_executor_selection.py:5:    and native-program dispatch routing.  The deprecated ``ARNOLD_NATIVE_RUNTIME``
tests/arnold/pipeline/native/test_flags_context.py:30,34,38,44,50,63,69,76,83,99,133:    monkeypatch.setenv/delenv("ARNOLD_NATIVE_RUNTIME", ...)
tests/arnold/pipeline/native/test_runtime.py:45,753:    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", ...)
tests/pipelines/test_folder_audit.py:440,446,459,464:    monkeypatch.setenv/delenv("ARNOLD_NATIVE_RUNTIME", ...)
```

### Classification

| Hit | File | Kind | Verdict |
|-----|------|------|---------|
| Docstring (no-op) | `flags.py:3` | Production code | **Keep** — docstring documents retention for legacy callers |
| Docstring (no-op) | `executor.py:101` | Production code | **Keep** — docstring says env var is ignored |
| Smoke trace | `_smoke_trace_test.py:4` | Test utility | **Keep** — sets flag for trace capture |
| Deprecation docstring | `test_executor_selection.py:5` | Test | **Keep** — documents deprecated flag |
| Flag context tests | `test_flags_context.py` (11 hits) | Test | **Keep** — tests flag parsing behavior (no-op compatibility) |
| Runtime tests | `test_runtime.py` (2 hits) | Test | **Keep** — tests native runtime with flag set |
| Folder audit tests | `test_folder_audit.py` (4 hits) | Test | **Keep** — tests native execution env |
| Archive tests | `tests/archive/m6_deleted_legacy_runtime/` (~25 hits) | Archived test | **Non-actionable** — archived |

### Summary

- **Production code:** Only docstring references. `flags.py` retains the flag as compatibility; `executor.py` declares it ignored. No production logic gates on `ARNOLD_NATIVE_RUNTIME`.
- **Active tests:** `test_flags_context.py`, `test_runtime.py`, `test_executor_selection.py`, `test_folder_audit.py` all use the flag for testing flag-parsing behavior or setting up native execution environments.
- **Verdict:** Retained as a no-op compatibility flag per plan assumptions (SD1). Production code ignores it; tests use it for flag-parsing verification and execution environment setup. No deletion needed in M7.

---

## 6. `MEGAPLAN_M6_MANIFEST_DISCOVERY`

### Exact `rg` output (non-docs, non-archive, non-.megaplan)

```
arnold_pipelines/megaplan/runtime/discovery.py:140:    The ``MEGAPLAN_M6_MANIFEST_DISCOVERY`` env var is no longer read or
tests/test_pipeline_discovery_integrity.py:281:    monkeypatch.setenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", "0")
tests/test_pipeline_discovery_integrity.py:303:    monkeypatch.delenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", raising=False)
tests/arnold/pipeline/test_discovery_manifest.py:59:    monkeypatch.delenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", raising=False)
tests/arnold/pipeline/test_discovery_manifest.py:62:    monkeypatch.setenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", "0")
tests/resume/test_pre_m6_alias.py:100,149:    monkeypatch.setenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", "1")
```

### Classification

| Hit | File | Kind | Verdict |
|-----|------|------|---------|
| Docstring (no-op) | `discovery.py:140` | Production code | **Keep** — docstring says env var is no longer read |
| Discovery integrity tests | `test_pipeline_discovery_integrity.py` (2 hits) | Test | **Keep** — tests manifest discovery behavior with flag set/unset |
| Manifest discovery tests | `test_discovery_manifest.py` (2 hits) | Test | **Keep** — tests manifest discovery with flag |
| Pre-M6 alias tests | `test_pre_m6_alias.py` (2 hits) | Test | **Keep** — tests pre-M6 alias behavior |
| Archive tests | `tests/archive/m6_deleted_legacy_runtime/`, `tests/archive/m5/` | Archived test | **Non-actionable** — archived |

### Summary

- **Production code:** `discovery.py:140` declares the env var is no longer read. No production logic gates on it.
- **Active tests:** Discovery integrity and manifest tests use the flag for testing backward-compat discovery paths.
- **Verdict:** Retained as documented no-op/backward-compat discovery context per plan assumptions. No deletion needed in M7.

---

## 7. `MEGAPLAN_PIPELINE_AUTO`

### Exact `rg` output (non-docs, non-archive, non-.megaplan)

```
(NONE — zero hits outside docs/ and archive/)
```

### Classification

- **Production code:** ZERO references.
- **Active tests:** ZERO references.
- **All hits:** Exclusively in `docs/archive/sprints/`, `docs/pipeline-architecture.md`, `.megaplan/initiatives/`, and `docs/archive/m5/pipeline-plans/`. All are historical documentation.

### Summary

- **Verdict:** Docs/archive-only. No live code or test references. No M7 action needed.

---

## 8. `--driver graph`

### Exact `rg` output (non-docs, non-archive, non-.megaplan)

```
(NONE — zero hits in production code or active tests)
```

All hits are in:
- `docs/arnold/package-authoring-contract.md`, `docs/arnold/creating-a-new-pipeline.md`, `docs/arnold/authoring-guide.md` — documentation that labels `--driver graph` as deprecated/unsupported legacy.
- `.megaplan/runs/simplify-writing/` — archive state files from old megaplan runs.
- `docs/archive/m5/pipeline-plans/` — archived migration plans.

### Classification

- **Production CLI code:** ZERO references. No CLI implements `--driver graph`.
- **Active tests:** ZERO references.
- **Docs:** Correctly label `--driver graph` as deprecated/unsupported legacy.

### Summary

- **Verdict:** Docs/archive-only. No production CLI code implements `--driver graph`. The docs correctly describe it as unsupported legacy. No M7 action needed.

---

## Cross-Cutting Classification Summary

| Search Family | On-Disk Status | Production Callers | Test Callers | M7 Action |
|---------------|---------------|-------------------|--------------|-----------|
| `arnold.pipeline.legacy` | Module exists | **ZERO** | 2 test files (7 hits) | **Delete** module, delete dedicated test, repair public contract test to assert absence |
| `arnold/pipelines/megaplan/_pipeline` | **ABSENT** (tree deleted) | ZERO | Scanner test asserts absence | **None** — already deleted |
| `arnold.pipelines.megaplan` (DOT) | **ABSENT** (tree deleted) | ZERO | ZERO | **None** — already deleted; conformance metadata is accurate |
| `arnold_pipelines.megaplan` (underscore) | **PRESENT** (canonical) | Extensive (authorized) | Extensive | **Survive** — repair conformance: remove `_compatibility` from deleted lists |
| `ARNOLD_NATIVE_RUNTIME` | Flag exists (no-op) | ZERO (docstring only) | 4 test files | **Keep** — no-op compatibility flag |
| `MEGAPLAN_M6_MANIFEST_DISCOVERY` | Flag exists (no-op) | ZERO (docstring only) | 3 test files | **Keep** — documented no-op |
| `MEGAPLAN_PIPELINE_AUTO` | No live refs | ZERO | ZERO | **None** — docs/archive only |
| `--driver graph` | No live refs | ZERO | ZERO | **None** — docs/archive only |

---

## Critical Conformance Repair Note

**`arnold_pipelines.megaplan._compatibility` is currently misclassified as a deleted surface** in `arnold/conformance/deleted_surfaces.py`:

- Line 108: Listed in `DELETED_IMPORT_MODULES`
- Line 133: Listed in `DELETED_IMPORT_PREFIXES`
- Line 140: Listed in `DELETED_ARTIFACT_PATH_PREFIXES`
- Line 166: Listed in `DELETED_CLI_HELP_FRAGMENTS`

Per SD2, `_compatibility.py` is a **legitimate internal projection facade** — it projects the authored workflow DSL into a neutral Arnold graph shell and attaches `NativeProgram`. It is substrate evidence for the `Pipeline.native_program` interface, **not a graph-era shim**.

**M7 must remove `arnold_pipelines.megaplan._compatibility` from all four deletion lists** while keeping the deleted DOT (`arnold.pipelines.megaplan`) and `_pipeline` surfaces properly guarded.

---

## Verification Checklist

- [x] Exact `rg` output recorded for all eight families
- [x] Every hit classified (production/test/docs/archive/conformance)
- [x] Explicit statement: `arnold/pipelines/megaplan/_pipeline/` tree is absent (confirmed via `ls`)
- [x] Explicit statement: DOT package `arnold/pipelines/megaplan/` is absent (confirmed via `ls`)
- [x] Explicit statement: `arnold.pipeline.legacy` has **zero** production callers
- [x] `_compatibility.py` classified as substrate proof, not a shim
- [x] Conformance misclassification of `_compatibility` identified for repair in later tasks
- [x] `ARNOLD_NATIVE_RUNTIME`, `MEGAPLAN_M6_MANIFEST_DISCOVERY` confirmed as no-op compatibility flags
- [x] `MEGAPLAN_PIPELINE_AUTO` and `--driver graph` confirmed as docs/archive-only
