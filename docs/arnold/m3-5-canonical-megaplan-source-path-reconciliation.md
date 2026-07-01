# M3.5 Canonical Megaplan — Source-Path Reconciliation

**Milestone:** M3.5 — Canonical Megaplan Native-First Contract Migration
**Status:** Substrate proof only — not final native representation report conformance.
**Date:** 2026-07-01

---

## 1. Purpose

The original M3.5 plan and task descriptions reference paths under the stale `arnold/pipelines/megaplan/` prefix (dot-separated directory name). The live package root is `arnold_pipelines/megaplan/` (underscore-separated, the plugin root included in the wheel build). Several referenced files do not exist at any path. This artifact:

1. Maps every stale plan-listed source path to its live `arnold_pipelines/megaplan/` equivalent.
2. Documents which test files exist, which are missing, and the relocation convention.
3. Explicitly labels M3.5 as **substrate proof only** per the North Star doctrine gate.

**Key ruling (SD2):** All implementation edits target live `arnold_pipelines/megaplan/` paths. The stale `arnold/pipelines/megaplan/` paths are documented here — not edited. No stale paths will be created for runtime behavior.

---

## 2. Core Path Mapping

All plan-referenced source paths use the stale dot-separated prefix. The live package root is `arnold_pipelines/megaplan/`.

| # | Stale Plan Path | Live Equivalent | Status | Notes |
|---|----------------|-----------------|--------|-------|
| 1 | `arnold/pipelines/megaplan/__init__.py` | `arnold_pipelines/megaplan/__init__.py` | Live | Package metadata and `build_pipeline` entrypoint. |
| 2 | `arnold/pipelines/megaplan/pipeline.py` | `arnold_pipelines/megaplan/pipeline.py` | Live | Thin facade re-exporting `build_pipeline` from `workflows.planning`. |
| 3 | `arnold/pipelines/megaplan/workflows/planning.py` | `arnold_pipelines/megaplan/workflows/planning.py` | Live | Canonical `build_pipeline()` — returns DSL Pipeline without `native_program`. |
| 4 | `arnold/pipelines/megaplan/workflows/components.py` | `arnold_pipelines/megaplan/workflows/components.py` | Live | 12 StepComponents with handler_ref strings and route_bindings. |
| 5 | `arnold/pipelines/megaplan/auto.py` | `arnold_pipelines/megaplan/auto.py` | Live | Auto-drive, resume, recovery (4670 lines). Dispatches via `registry.dispatch_operation_for()`. |
| 6 | `arnold/pipelines/megaplan/registry.py` | `arnold_pipelines/megaplan/registry.py` | Live | Megaplan operation registry with `dispatch_operation_for()` and `_builtin_megaplan_builder()`. |
| 7 | `arnold/pipelines/megaplan/cli/__init__.py` | `arnold_pipelines/megaplan/cli/__init__.py` | Live | Monolithic CLI (2987 lines) — the live CLI surface for `run`, `describe`, `auto`, etc. |
| 8 | `arnold/pipelines/megaplan/cli/parser.py` | `arnold_pipelines/megaplan/cli/parser.py` | Live | CLI argument parser for megaplan commands. |
| 9 | `arnold/pipelines/megaplan/cli/run.py` | `arnold_pipelines/megaplan/cli/run.py` | Live | Run subcommand handler (`cli_run`). |
| 10 | `arnold/pipelines/megaplan/routing.py` | `arnold_pipelines/megaplan/routing.py` | Live | Megaplan-specific routing module. |
| 11 | `arnold/pipelines/megaplan/runtime/bridge.py` | `arnold_pipelines/megaplan/runtime/bridge.py` | Live | Bridge adapter for megaplan→neutral executor; already reads `native_program` via `getattr`. |
| 12 | `arnold/pipelines/megaplan/runtime/discovery.py` | `arnold_pipelines/megaplan/runtime/discovery.py` | Live | Runtime discovery module. |
| 13 | `arnold/pipelines/megaplan/planning/operations.py` | `arnold_pipelines/megaplan/planning/operations.py` | Live | PlanningOperationRegistry with subprocess-spawning dispatch. |
| 14 | `arnold/pipeline/native/routing.py` | `arnold/pipeline/native/routing.py` | Live | Generic native/graph dispatch — already clean of megaplan references (verification-only). |
| 15 | `arnold/pipeline/executor.py` | `arnold/pipeline/executor.py` | Live | Generic executor — already clean of megaplan fallback logic (verification-only). |
| 16 | `arnold/pipeline/types.py` | `arnold/pipeline/types.py` | Live | Defines `Pipeline.native_program: NativeProgram \| None`. |

---

## 3. Non-Existent Files — Live Equivalents

These paths appear in plan task references but do not exist on the filesystem. Live equivalents are named below.

| # | Non-Existent Path | Live Equivalent | Resolution |
|---|------------------|-----------------|------------|
| N1 | `native_runner.py` | `arnold_pipelines/megaplan/auto.py` + `arnold_pipelines/megaplan/cli/run.py` | No `native_runner.py` exists. The live runtime equivalent is `auto.py` (in-process auto-drive) and `cli/run.py` (subprocess entry). Do **not** create `native_runner.py` unless a concrete import contract forces it. |
| N2 | `_compatibility.py` (root) | **Must be created** at `arnold_pipelines/megaplan/_compatibility.py` | Does not exist. T3 will create this as a narrowly scoped DSL-to-native projection helper. |
| N3 | `cli/arnold.py` | `arnold_pipelines/megaplan/cli/__init__.py` | No separate `cli/arnold.py` exists. The monolithic `cli/__init__.py` handles all CLI surface including `describe`, `run`, `auto`, and phase commands. |
| N4 | `cli/parser.py` (bare) | `arnold_pipelines/megaplan/cli/parser.py` | The bare path is a plan truncation; the live file is under the `arnold_pipelines/megaplan/cli/` package. |
| N5 | `cli/run.py` (bare) | `arnold_pipelines/megaplan/cli/run.py` | Same as N4 — live file is within the `cli/` subpackage. |
| N6 | `pipelines/writing_panel_strict/pipeline.py` (bare) | `arnold_pipelines/megaplan/pipelines/writing_panel_strict/pipeline.py` | The bare path is a plan truncation of the live subpackage path. |
| N7 | `planning/operations.py` (bare) | `arnold_pipelines/megaplan/planning/operations.py` | Same pattern — plan truncation. |
| N8 | `auto.py` (bare) | `arnold_pipelines/megaplan/auto.py` | Plan truncation of the live auto-drive module. |

---

## 4. Test Path Reconciliation

The plan references 15 test paths. Only 4 exist at their listed paths. 10 are missing and must be created. 1 is archived and must be resurrected or replaced.

### 4.1 Existing Tests (at listed paths)

| # | Test Path | Lines | Status |
|---|----------|-------|--------|
| E1 | `tests/characterization/test_auto_drive.py` | 2602 | Live — comprehensive auto-drive characterization. |
| E2 | `tests/characterization/test_pipeline_golden.py` | 123 | Live — golden step-order baseline (12 expected steps). |
| E3 | `tests/arnold/conformance/test_megaplan_coupling_gate.py` | — | Live — coupling gate with allowlist. |
| E4 | `tests/test_pipeline_run_cli.py` | 1437 | Live — megaplan run CLI describe and list. |

### 4.2 Missing Tests (must be created)

| # | Missing Path | Planned Location (per SD3) | Purpose |
|---|-------------|---------------------------|---------|
| M1 | `tests/test_auto.py` | `tests/arnold_pipelines/megaplan/test_auto.py` | Auto-drive coverage for canonical native-backed runtime. |
| M2 | `tests/test_auto_driver_lock.py` | `tests/arnold_pipelines/megaplan/test_auto_driver_lock.py` | Driver-lock behavior stability under native-backed auto path. |
| M3 | `tests/test_auto_escalation.py` | `tests/arnold_pipelines/megaplan/test_auto_escalation.py` | Escalation flow stability under native-backed auto path. |
| M4 | `tests/test_auto_phase_timeout_retryable.py` | `tests/arnold_pipelines/megaplan/test_auto_phase_timeout_retryable.py` | Phase-timeout retryable behavior stability. |
| M5 | `tests/test_auto_pipeline_runtime.py` | `tests/arnold_pipelines/megaplan/test_auto_pipeline_runtime.py` | Canonical auto path runs against native-backed contract. |
| M6 | `tests/arnold/pipelines/megaplan/test_bridged_executor.py` | `tests/arnold_pipelines/megaplan/test_bridged_executor.py` | Remove assumptions that canonical Megaplan needs graph-bridge executor. |
| M7 | `tests/arnold/pipelines/megaplan/test_native_execution_parity_fixtures.py` | `tests/arnold_pipelines/megaplan/test_native_execution_parity_fixtures.py` | Fixtures and assertions for migrated canonical runtime. |
| M8 | `tests/arnold/pipelines/megaplan/test_native_parity.py` | `tests/arnold_pipelines/megaplan/test_native_parity.py` | Native-truth coverage for canonical pipeline. |
| M9 | `tests/arnold/pipelines/megaplan/test_native_parity_golden_traces.py` | `tests/arnold_pipelines/megaplan/test_native_parity_golden_traces.py` | Golden traces aligned with migrated canonical runtime. |
| M10 | `tests/arnold/pipelines/megaplan/test_pipeline_contracts.py` | `tests/arnold_pipelines/megaplan/test_pipeline_contracts.py` | Canonical Megaplan satisfies same `native_program` contract as subpipelines. |

### 4.3 Archived Test

| # | Original Path | Archived Path | Resolution |
|---|--------------|---------------|------------|
| A1 | `tests/arnold/pipeline/native/test_resume_routing.py` | `tests/archive/m6_deleted_legacy_runtime/arnold/pipeline/native/test_resume_routing.py` | Must be resurrected as a structural assertion that native resume routing no longer depends on megaplan-specific stage-order heuristics. |

### 4.4 Test Relocation Convention (SD3)

Per the approved plan decision SD3, all new and reconciled auto-drive tests are placed under `tests/arnold_pipelines/megaplan/` — **not** flat `tests/test_auto*.py` files. This matches the existing convention where live megaplan tests (`test_auto_engine_isolation_default.py`, `test_auto_recover_blocked.py`, and 40+ others) already live under `tests/arnold_pipelines/megaplan/`.

---

## 5. CLI Surface Mapping

The plan references `arnold pipelines describe megaplan` and `cli/arnold.py` — neither exists.

| Plan Reference | Live Command / Module | Notes |
|---------------|----------------------|-------|
| `arnold pipelines describe megaplan` | `megaplan describe` → `cli/__init__.py:handle_describe()` | The `arnold` top-level CLI routes `workflow` and operator commands only, not `pipelines describe`. |
| `arnold pipelines run megaplan --describe` | `megaplan run megaplan --describe` → `cli/run.py:cli_run()` | The live megaplan CLI is a standalone entrypoint (`python -m arnold_pipelines.megaplan`). |
| `cli/arnold.py` | `arnold_pipelines/megaplan/cli/__init__.py` | Monolithic CLI handling all commands (2987 lines). |

---

## 6. Substrate-Proof-Only Declaration

Per the North Star doctrine gate and the approved plan's success criterion #8:

> **This milestone (M3.5) is substrate proof only.** It does **not** claim final native representation report conformance.

Specifically:

- The canonical pipeline's handlers remain opaque string references (`'arnold_pipelines.megaplan.handlers:handle_prep'`) to handler-backed nodes.
- Visible critique, gate, tiebreaker, execute, and review structure remains deferred to composition milestones M1 and M6.
- `native_program` on the compiled pipeline shell serves as **compatibility dispatch proof** — the system can route through the native execution substrate rather than legacy stage-order heuristics.
- Full semantic visibility (critique/gate/tiebreaker bodies as `@phase`/`@decision` callables with inspectable product semantics) is **out of scope** for M3.5.

The substrate changes in M3.5 establish:
1. The canonical pipeline compiles to an `arnold.pipeline.types.Pipeline` shell.
2. That shell carries a non-null `native_program`.
3. Auto-drive, CLI, and operation dispatch routes through the native-backed path.
4. Megaplan-specific stage-order heuristics are verified absent from shared routing/executor substrate.

---

## 7. Routing/Executor Substrate Status

The plan targets `arnold/pipeline/native/routing.py` and `arnold/pipeline/executor.py` for heuristic removal. Confirmed by codebase audit:

| File | Megaplan References | Stage-Order Heuristics | Action |
|------|-------------------|----------------------|--------|
| `arnold/pipeline/native/routing.py` (176 lines) | Zero | Zero | **Verification-only** — already generic. No code removal needed. |
| `arnold/pipeline/executor.py` (1257 lines) | Zero | Zero | **Verification-only** — already clean. No code removal needed. |

The plan's T7 (substrate verification) is a confirmation step, not a code-removal step. The actual megaplan-specific routing logic lives in `arnold_pipelines/megaplan/routing.py` and the planning workflow's `_CANONICAL_ROUTE_SPECS`.

---

## 8. Package Build Verification

Per `pyproject.toml`:

- `arnold/pipelines/` (dot-separated): **excluded from wheel** (pyproject.toml line 76, 97). Contains only `deliberation` and `folder_audit` — no megaplan.
- `arnold_pipelines/` (underscore-separated): **included in wheel** (pyproject.toml line 84). This is the plugin root and the live package for all megaplan source.

This confirms SD2: editing stale `arnold/pipelines/megaplan/` paths would create ghost code excluded from the built wheel.

---

## 9. Summary

| Category | Count | Resolution |
|----------|-------|------------|
| Stale paths (dot-separated) | 16 | All mapped to live `arnold_pipelines/megaplan/` equivalents |
| Non-existent files | 8 | Live equivalents named; `_compatibility.py` designated for creation |
| Missing tests | 10 | All relocated to `tests/arnold_pipelines/megaplan/` per SD3 |
| Archived tests | 1 | Resurrection candidate (`test_resume_routing.py`) |
| Existing tests | 4 | No relocation needed |
| Substrate files (verification-only) | 2 | `routing.py` and `executor.py` — already clean |

**Doctrine gate label:** M3.5 = SUBSTRATE PROOF ONLY. Do not claim final native representation report conformance while handler-backed product semantics remain opaque.
