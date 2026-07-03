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

---

## 10. M1 Compositional Migration — Source-Path Entries

**Milestone:** M1 — Megaplan Compositional Migration
**Status:** Launch-gate authority (pre-implementation reconciliation)
**Date:** 2026-07-03

### 10.1 Purpose

The M1 milestone migrates canonical Megaplan into the compositional workflow format. This section provides the pre-implementation source-path reconciliation required by the M1 launch gate. It identifies the live canonical source files, package/CLI/auto-drive entrypoints, native compiler/runtime/projection paths, and explicitly marks `native_runner.py` / `native_hooks.py` as nonexistent before implementation starts.

### 10.2 Live M1 Workflow Source Files

The canonical Megaplan workflow for M1 is authored as a composition of native workflows. The following live files are the authoritative source:

| # | Live Path | Role | Notes |
|---|----------|------|-------|
| W1 | `arnold_pipelines/megaplan/workflows/workflow.py` | Canonical authored workflow source | Declares `planning_workflow` using `@workflow` and `loop` decorators from `arnold.workflow.authoring`. This is the compositional source — not a flat stage list. |
| W2 | `arnold_pipelines/megaplan/workflows/planning.py` | DSL pipeline builder | `build_pipeline()` returns the DSL `Pipeline`; also defines `AUTHOR_REVISE` and `AUTHOR_TIEBREAKER_DECIDE` variant components used by `workflow.py`. |
| W3 | `arnold_pipelines/megaplan/workflows/components.py` | StepComponent definitions | 12 `StepComponent` definitions (`SOURCE_PREP`, `SOURCE_PLAN`, `SOURCE_CRITIQUE`, `SOURCE_GATE`, `SOURCE_REVISE`, `SOURCE_TIEBREAKER_RUN`, `SOURCE_FINALIZE`, `SOURCE_EXECUTE`, `SOURCE_REVIEW`, `SOURCE_OVERRIDE`, `SOURCE_HALT`, `TIEBREAKER_DECIDE`) with handler_ref strings and route_bindings. |
| W4 | `arnold_pipelines/megaplan/workflows/__init__.py` | Workflows package init | Package marker. |

### 10.3 Package Facade and Compatibility Shell

| # | Live Path | Role | Notes |
|---|----------|------|-------|
| P1 | `arnold_pipelines/megaplan/pipeline.py` | Thin facade | Re-exports `build_pipeline` from `workflows.planning`; provides `build_and_compile_pipeline()` wrapping `_compatibility.build_compatibility_shell()`. |
| P2 | `arnold_pipelines/megaplan/__init__.py` | Plugin root | Package metadata (`name`, `entrypoint`, `capabilities`), content-type registration, model-seam adapter installation. |
| P3 | `arnold_pipelines/megaplan/_compatibility.py` | Compatibility projection helper | `build_compatibility_shell()` — projects the authored workflow to a native-backed shell. Created per M3.5 T3; live as of 2026-07-01. |

### 10.4 CLI and Auto-Drive Entrypoints

| # | Live Path | Role | Notes |
|---|----------|------|-------|
| C1 | `arnold_pipelines/megaplan/cli/__init__.py` | Monolithic CLI (2987 lines) | All CLI surface: `describe`, `run`, `auto`, phase commands. Standalone entrypoint via `python -m arnold_pipelines.megaplan`. |
| C2 | `arnold_pipelines/megaplan/cli/run.py` | Run subcommand handler | `cli_run()` — subprocess CL entry. |
| C3 | `arnold_pipelines/megaplan/cli/parser.py` | CLI argument parser | Parser for megaplan commands. |
| C4 | `arnold_pipelines/megaplan/cli/projection.py` | CLI projection module | Projection helpers for CLI output. |
| C5 | `arnold_pipelines/megaplan/auto.py` | Auto-drive (4670 lines) | In-process auto-drive, resume, recovery. Dispatches via `registry.dispatch_operation_for()`. |
| C6 | `arnold_pipelines/megaplan/registry.py` | Operation registry | `dispatch_operation_for()` and `_builtin_megaplan_builder()`. |
| C7 | `arnold_pipelines/megaplan/routing.py` | Megaplan routing | Megaplan-specific routing module. |
| C8 | `arnold_pipelines/megaplan/__main__.py` | Module entrypoint | `python -m arnold_pipelines.megaplan` entry. |

### 10.5 Native Compiler, Runtime, and Projection Paths

These are the neutral (non-megaplan-specific) native substrate files that M1 depends on. Per SD2, a non-Megaplan fixture must pass through these paths before Megaplan workflow edits proceed.

| # | Live Path | Role | Notes |
|---|----------|------|-------|
| N1 | `arnold/pipeline/native/compiler.py` | AST-to-NativeProgram lowering (1204 lines) | Parses `@pipeline`-decorated functions; emits `NativeProgram` with program counters and branch labels. M1 may add narrow Megaplan-specific support marked `TEMPORARY_MEGAPLAN_ONLY`. |
| N2 | `arnold/pipeline/native/runtime.py` | Native runtime executor | Executes `NativeProgram` against the neutral runtime substrate. M1 must support Megaplan composition shape without changing unrelated runtime behavior. |
| N3 | `arnold/pipeline/native/graph_projection.py` | NativeProgram→Pipeline graph projection (911 lines) | Walks compiled `NativeProgram`, builds `Pipeline` with stage/edge metadata, guarded-loop conditions, and typed-port binding. |
| N4 | `arnold/pipeline/native/ir.py` | Native IR definitions | `NativeProgram`, `NativeInstruction`, `NativeDecision`, `NativeLoopGuard`, `ParallelInstruction` types. |
| N5 | `arnold/pipeline/native/decorators.py` | `@phase` / `@decision` / `@pipeline` decorators | Runtime metadata for native pipeline authoring. |
| N6 | `arnold/pipeline/native/hooks.py` | Native hook dispatch | Neutral hook system for native pipeline lifecycle. |
| N7 | `arnold/pipeline/native/routing.py` | Native routing (176 lines) | Generic native/graph dispatch. Verified clean of megaplan references (M3.5 verification-only). |
| N8 | `arnold/pipeline/native/checkpoint.py` | Checkpoint/resume support | Checkpointing for native pipeline execution. |
| N9 | `arnold/pipeline/native/context.py` | Execution context | Native pipeline execution context. |
| N10 | `arnold/pipeline/native/trace.py` | Execution tracing | Trace support for native pipeline runs. |
| N11 | `arnold/pipeline/native/flags.py` | Feature flags | Native pipeline feature flags. |
| N12 | `arnold/pipeline/native/__init__.py` | Package init | Native pipeline package. |
| N13 | `arnold/pipeline/types.py` | Pipeline type definitions | Defines `Pipeline.native_program: NativeProgram \| None`. |
| N14 | `arnold/workflow/source_compiler.py` | Workflow source compiler | `lower_workflow_file()` — compiles workflow source files. |
| N15 | `arnold/workflow/compiler.py` | Workflow compiler | General workflow compilation support. |

### 10.6 Non-Existent Files — Explicitly Marked

These paths are referenced in the M1 brief but do **not** exist on the filesystem. They must not be created unless a concrete import contract forces it, and the live equivalents are named below.

| # | Non-Existent Path | Live Equivalent | Resolution |
|---|------------------|-----------------|------------|
| NX1 | `arnold_pipelines/megaplan/native_runner.py` | `arnold_pipelines/megaplan/auto.py` (in-process auto-drive) + `arnold_pipelines/megaplan/cli/run.py` (subprocess entry) | **Does not exist.** The live runtime equivalent is `auto.py` for in-process auto-drive and `cli/run.py` for subprocess entry. Do **not** create `native_runner.py` unless a concrete import contract forces it. |
| NX2 | `arnold_pipelines/megaplan/native_hooks.py` | `arnold/pipeline/native/hooks.py` (neutral native hooks) + `arnold_pipelines/megaplan/handlers/` (megaplan-specific handler bridge modules) | **Does not exist.** Megaplan-specific hook behavior lives in the handler bridge modules (`handlers/init.py`, `handlers/gate.py`, `handlers/finalize.py`, `handlers/critique.py`, `handlers/review.py`, `handlers/execute.py`, `handlers/tiebreaker.py`, `handlers/override.py`, `handlers/plan.py`, `handlers/shared.py`, `handlers/tickets.py`, `handlers/anchors.py`, `handlers/verifiability.py`, `handlers/structured_output.py`). The neutral hook dispatch lives at `arnold/pipeline/native/hooks.py`. Do **not** create `native_hooks.py` unless a concrete import contract forces it. |

### 10.7 Stale `arnold/pipelines/...` Reference Classification

The dot-separated `arnold/pipelines/` prefix is the stale package root (excluded from wheel per `pyproject.toml`). All live megaplan source lives under underscore-separated `arnold_pipelines/`. The following classification covers every stale reference discovered in the codebase:

#### 10.7.1 Dead Paths

Directories or files referenced under `arnold/pipelines/` that do not exist on the filesystem and will never be recreated. These are listed in the M6 deletion inventory (`arnold/conformance/deleted_surfaces.py`).

| # | Stale Path | Classification | Evidence |
|---|-----------|---------------|----------|
| D1 | `arnold/pipelines/megaplan/` | **Dead path** | Directory does not exist. M6 deletion target (`deleted_surfaces.py` line 38). Conformance allowlists reference it for legacy-gate purposes only. |
| D2 | `arnold/pipelines/megaplan/data/` | **Dead path** | Directory does not exist. M6 deletion target (`deleted_surfaces.py` line 66). |
| D3 | `arnold/pipelines/jokes/` | **Dead path** | M6 deletion target (`deleted_surfaces.py` line 39). |
| D4 | `arnold/pipelines/creative/` | **Dead path** | M6 deletion target (`deleted_surfaces.py` line 40). |
| D5 | `arnold/pipelines/doc/` | **Dead path** | M6 deletion target (`deleted_surfaces.py` line 41). |
| D6 | `arnold/pipelines/live_supervisor/` | **Dead path** | M6 deletion target (`deleted_surfaces.py` line 42). |
| D7 | `arnold/pipelines/select_tournament/` | **Dead path** | M6 deletion target (`deleted_surfaces.py` line 43). |
| D8 | `arnold/pipelines/simplify_writing/` | **Dead path** | M6 archive target (`deleted_surfaces.py` line 44). |
| D9 | `arnold/pipelines/vibecomfy_executor/` | **Dead path** | M6 archive target (`deleted_surfaces.py` line 45). |
| D10 | `arnold/pipelines/writing_panel_strict.py` | **Dead path** | M6 deletion target (`deleted_surfaces.py` line 46). |
| D11 | `arnold/pipelines/epic_blitz/` | **Dead path** | M6 archive target (`deleted_surfaces.py` line 47). |
| D12 | `arnold/pipelines/briefs/` | **Dead path** | M6 archive target (`deleted_surfaces.py` line 51). |
| D13 | `arnold/pipelines/_template/` | **Dead path** | Does not exist; only referenced in `discovery.py` as legacy mapping. |

#### 10.7.2 Compatibility Aliases

Stale `arnold/pipelines/` paths that still resolve to live `arnold_pipelines/` equivalents through discovery/registry compatibility mappings. These are NOT dead — they serve as aliases for backward compatibility in discovery.

| # | Stale Path | Live Equivalent | Classification | Notes |
|---|-----------|----------------|---------------|-------|
| A1 | `arnold/pipelines/megaplan/pipelines/doc` | `arnold_pipelines/megaplan/pipelines/doc/` | **Compatibility alias** | Discovery alias in `arnold_pipelines/discovery.py` line 155. |
| A2 | `arnold/pipelines/megaplan/pipelines/creative` | `arnold_pipelines/megaplan/pipelines/creative/` | **Compatibility alias** | Discovery alias in `discovery.py` line 163. |
| A3 | `arnold/pipelines/megaplan/pipelines/jokes` | `arnold_pipelines/megaplan/pipelines/jokes/` | **Compatibility alias** | Discovery alias in `discovery.py` line 171. |
| A4 | `arnold/pipelines/megaplan/pipelines/live_supervisor` | `arnold_pipelines/megaplan/pipelines/live_supervisor/` | **Compatibility alias** | Discovery alias in `discovery.py` line 179. |
| A5 | `arnold/pipelines/megaplan/pipelines/epic_blitz.py` | `arnold_pipelines/megaplan/pipelines/epic_blitz.py` | **Compatibility alias** | Discovery alias in `discovery.py` line 187. |
| A6 | `arnold/pipelines/megaplan/pipelines/select_tournament` | `arnold_pipelines/megaplan/pipelines/select_tournament/` | **Compatibility alias** | Discovery alias in `discovery.py` line 196. |
| A7 | `arnold/pipelines/megaplan/pipelines/writing_panel_strict` | `arnold_pipelines/megaplan/pipelines/writing_panel_strict/` | **Compatibility alias** | Discovery alias in `discovery.py` line 204. |
| A8 | `arnold/pipelines/folder_audit` | `arnold/pipelines/folder_audit/` (live dot-separated) | **Compatibility alias** | Discovery alias in `discovery.py` line 212. Live under `arnold/pipelines/` still. |
| A9 | `arnold/pipelines/deliberation` | `arnold/pipelines/deliberation/` (live dot-separated) | **Compatibility alias** | Discovery alias in `discovery.py` line 222. Live under `arnold/pipelines/` still. |
| A10 | `arnold/pipelines/_deliberation_example` | `arnold/pipelines/_deliberation_example/` (live dot-separated) | **Compatibility alias** | Discovery alias in `discovery.py` line 380. Live under `arnold/pipelines/` still. |

#### 10.7.3 Migration Targets

Paths that exist under the live `arnold_pipelines/` prefix but are also referenced under stale `arnold/pipelines/` in code or docs. These are the target of M1 migration — the stale reference must be updated or removed.

| # | Stale Reference | Live Migration Target | Classification | Notes |
|---|----------------|----------------------|---------------|-------|
| M1 | `arnold/pipelines/megaplan/__init__.py` | `arnold_pipelines/megaplan/__init__.py` | **Migration target** | Package root. Live at underscore path. |
| M2 | `arnold/pipelines/megaplan/pipeline.py` | `arnold_pipelines/megaplan/pipeline.py` | **Migration target** | Facade. Live at underscore path. |
| M3 | `arnold/pipelines/megaplan/workflows/planning.py` | `arnold_pipelines/megaplan/workflows/planning.py` | **Migration target** | DSL builder. Live at underscore path. |
| M4 | `arnold/pipelines/megaplan/workflows/workflow.py` | `arnold_pipelines/megaplan/workflows/workflow.py` | **Migration target** | Canonical authored source. Live at underscore path. |
| M5 | `arnold/pipelines/megaplan/workflows/components.py` | `arnold_pipelines/megaplan/workflows/components.py` | **Migration target** | StepComponents. Live at underscore path. |
| M6 | `arnold/pipelines/megaplan/auto.py` | `arnold_pipelines/megaplan/auto.py` | **Migration target** | Auto-drive. Live at underscore path. |
| M7 | `arnold/pipelines/megaplan/registry.py` | `arnold_pipelines/megaplan/registry.py` | **Migration target** | Registry. Live at underscore path. |
| M8 | `arnold/pipelines/megaplan/cli/__init__.py` | `arnold_pipelines/megaplan/cli/__init__.py` | **Migration target** | CLI. Live at underscore path. |
| M9 | `arnold/pipelines/megaplan/cli/parser.py` | `arnold_pipelines/megaplan/cli/parser.py` | **Migration target** | CLI parser. Live at underscore path. |
| M10 | `arnold/pipelines/megaplan/cli/run.py` | `arnold_pipelines/megaplan/cli/run.py` | **Migration target** | CLI run. Live at underscore path. |
| M11 | `arnold/pipelines/megaplan/routing.py` | `arnold_pipelines/megaplan/routing.py` | **Migration target** | Routing. Live at underscore path. |
| M12 | `arnold/pipelines/megaplan/runtime/bridge.py` | `arnold_pipelines/megaplan/runtime/bridge.py` | **Migration target** | Bridge. Live at underscore path. |
| M13 | `arnold/pipelines/megaplan/runtime/discovery.py` | `arnold_pipelines/megaplan/runtime/discovery.py` | **Migration target** | Runtime discovery. Live at underscore path. |
| M14 | `arnold/pipelines/megaplan/planning/operations.py` | `arnold_pipelines/megaplan/planning/operations.py` | **Migration target** | Operations. Live at underscore path. |

### 10.8 Conformance Allowlist References

The `arnold/conformance/legacy_reference_allowlist.json` and `arnold/conformance/checks.py` contain numerous references to `arnold/pipelines/megaplan` as **legacy allowlist entries**. These are intentional — the conformance system tracks legacy references to ensure they are not reintroduced as live code paths. These are classified as **dead path gate entries** — they exist only to detect regressions where new code references the stale path. They are not migration targets and do not require updates during M1.

### 10.9 Summary — M1 Source-Path Reconciliation

| Category | Count | Resolution |
|----------|-------|------------|
| Live workflow source files | 4 | `workflow.py`, `planning.py`, `components.py`, `__init__.py` |
| Package facade / compatibility | 3 | `pipeline.py`, `__init__.py`, `_compatibility.py` |
| CLI / auto-drive entrypoints | 8 | `cli/__init__.py`, `cli/run.py`, `cli/parser.py`, `cli/projection.py`, `auto.py`, `registry.py`, `routing.py`, `__main__.py` |
| Native compiler/runtime/projection | 15 | `compiler.py`, `runtime.py`, `graph_projection.py`, `ir.py`, `decorators.py`, `hooks.py`, `routing.py`, `checkpoint.py`, `context.py`, `trace.py`, `flags.py`, `__init__.py`, `types.py`, `source_compiler.py`, `compiler.py` (workflow) |
| Nonexistent files | 2 | `native_runner.py`, `native_hooks.py` — explicitly marked nonexistent |
| Dead paths | 13 | Stale `arnold/pipelines/` paths that do not exist and will not be recreated |
| Compatibility aliases | 10 | Discovery aliases mapping stale→live paths |
| Migration targets | 14 | Stale `arnold/pipelines/megaplan/...` references mapped to live `arnold_pipelines/megaplan/...` |

**M1 doctrine gate label:** The source-path reconciliation table exists before workflow edits land and proves that package registration, CLI, auto-drive, and tests inspect the same live canonical workflow source. No stale path will be created or edited for runtime behavior.
