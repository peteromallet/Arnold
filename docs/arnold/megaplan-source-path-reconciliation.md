# Megaplan Source-Path Reconciliation — M1 Launch-Gate Authority

**Milestone:** M1 — Megaplan Compositional Migration
**Status:** Launch-gate authority (pre-implementation reconciliation)
**Date:** 2026-07-03

---

## 1. Purpose

This document is the **M1 launch-gate authority** for source-path reconciliation. Before any M1 workflow edits land, it proves that package registration, CLI, auto-drive, and tests inspect the same live canonical workflow source. It identifies the live canonical source files, package/CLI/auto-drive entrypoints, native compiler/runtime/projection paths, explicitly marks `native_runner.py` / `native_hooks.py` as nonexistent, and classifies every stale `arnold/pipelines/...` reference as migration target, compatibility alias, or dead path.

**Key ruling (SD2):** All implementation edits target live `arnold_pipelines/megaplan/` paths. The stale `arnold/pipelines/megaplan/` paths are documented here — not edited. No stale paths will be created for runtime behavior.

This document supersedes the M1 entries in `docs/arnold/m3-5-canonical-megaplan-source-path-reconciliation.md` for M1 launch gating.

---

## 2. Core Path Mapping — M1 Live Canonical Paths

### 2.1 Workflow Source Files

The canonical Megaplan workflow for M1 is authored as a composition of native workflows with explicit subworkflows, stable IDs, and declared inputs/outputs.

| # | Live Path | Role | Status |
|---|----------|------|--------|
| W1 | `arnold_pipelines/megaplan/workflows/workflow.py` | Canonical authored workflow source (93 lines) | **Live** — Declares `planning_workflow` using `@workflow` and `loop` decorators. Compositional source: prep→plan→(critique→gate→revise loop)→finalize→execute→review, with tiebreaker and override branches. |
| W2 | `arnold_pipelines/megaplan/workflows/planning.py` | DSL pipeline builder (249 lines) | **Live** — `build_pipeline()` returns the DSL `Pipeline`; defines `AUTHOR_REVISE` and `AUTHOR_TIEBREAKER_DECIDE` variant components. |
| W3 | `arnold_pipelines/megaplan/workflows/components.py` | StepComponent definitions | **Live** — 12 `StepComponent` definitions with handler_ref strings and route_bindings (`SOURCE_PREP`, `SOURCE_PLAN`, `SOURCE_CRITIQUE`, `SOURCE_GATE`, `SOURCE_REVISE`, `SOURCE_TIEBREAKER_RUN`, `SOURCE_FINALIZE`, `SOURCE_EXECUTE`, `SOURCE_REVIEW`, `SOURCE_OVERRIDE`, `SOURCE_HALT`, `TIEBREAKER_DECIDE`). |
| W4 | `arnold_pipelines/megaplan/workflows/__init__.py` | Workflows package init | **Live** — Package marker. |

### 2.2 Package Facade and Compatibility Shell

| # | Live Path | Role | Status |
|---|----------|------|--------|
| P1 | `arnold_pipelines/megaplan/pipeline.py` | Thin facade (28 lines) | **Live** — Re-exports `build_pipeline` from `workflows.planning`; provides `build_and_compile_pipeline()` wrapping `_compatibility.build_compatibility_shell()`. |
| P2 | `arnold_pipelines/megaplan/__init__.py` | Plugin root (99 lines) | **Live** — Package metadata (`name`, `entrypoint`, `capabilities`), content-type registration, model-seam adapter. |
| P3 | `arnold_pipelines/megaplan/_compatibility.py` | Compatibility projection helper | **Live** — `build_compatibility_shell()` projects authored workflow to native-backed shell. |

### 2.3 CLI and Auto-Drive Entrypoints

| # | Live Path | Role | Status |
|---|----------|------|--------|
| C1 | `arnold_pipelines/megaplan/cli/__init__.py` | Monolithic CLI (2987 lines) | **Live** — All CLI surface: `describe`, `run`, `auto`, phase commands. |
| C2 | `arnold_pipelines/megaplan/cli/run.py` | Run subcommand handler | **Live** — `cli_run()`. |
| C3 | `arnold_pipelines/megaplan/cli/parser.py` | CLI argument parser | **Live** — Parser for megaplan commands. |
| C4 | `arnold_pipelines/megaplan/cli/projection.py` | CLI projection module | **Live** — Projection helpers. |
| C5 | `arnold_pipelines/megaplan/auto.py` | Auto-drive (4670 lines) | **Live** — In-process auto-drive, resume, recovery. |
| C6 | `arnold_pipelines/megaplan/registry.py` | Operation registry | **Live** — `dispatch_operation_for()`, `_builtin_megaplan_builder()`. |
| C7 | `arnold_pipelines/megaplan/routing.py` | Megaplan routing | **Live** — Megaplan-specific routing module. |
| C8 | `arnold_pipelines/megaplan/__main__.py` | Module entrypoint | **Live** — `python -m arnold_pipelines.megaplan`. |

### 2.4 Native Compiler, Runtime, and Projection Paths

These are the neutral native substrate files that M1 depends on. Per SD2, a non-Megaplan fixture must pass through these paths before Megaplan workflow edits proceed.

| # | Live Path | Role | Status |
|---|----------|------|--------|
| N1 | `arnold/pipeline/native/compiler.py` | AST-to-NativeProgram lowering (1204 lines) | **Live** — Parses `@pipeline`-decorated functions; emits `NativeProgram`. |
| N2 | `arnold/pipeline/native/runtime.py` | Native runtime executor | **Live** — Executes `NativeProgram` against neutral runtime. |
| N3 | `arnold/pipeline/native/graph_projection.py` | NativeProgram→Pipeline projection (911 lines) | **Live** — Builds `Pipeline` with stage/edge metadata. |
| N4 | `arnold/pipeline/native/ir.py` | Native IR definitions | **Live** — `NativeProgram`, `NativeInstruction`, `NativeDecision`, etc. |
| N5 | `arnold/pipeline/native/decorators.py` | `@phase` / `@decision` / `@pipeline` decorators | **Live** — Runtime metadata. |
| N6 | `arnold/pipeline/native/hooks.py` | Native hook dispatch | **Live** — Neutral hook system. |
| N7 | `arnold/pipeline/native/routing.py` | Native routing (176 lines) | **Live** — Generic native/graph dispatch; verified clean of megaplan references. |
| N8 | `arnold/pipeline/native/checkpoint.py` | Checkpoint/resume support | **Live** |
| N9 | `arnold/pipeline/native/context.py` | Execution context | **Live** |
| N10 | `arnold/pipeline/native/trace.py` | Execution tracing | **Live** |
| N11 | `arnold/pipeline/native/flags.py` | Feature flags | **Live** |
| N12 | `arnold/pipeline/native/__init__.py` | Package init | **Live** |
| N13 | `arnold/pipeline/types.py` | Pipeline type definitions | **Live** — `Pipeline.native_program: NativeProgram \| None`. |
| N14 | `arnold/workflow/source_compiler.py` | Workflow source compiler | **Live** — `lower_workflow_file()`. |
| N15 | `arnold/workflow/compiler.py` | Workflow compiler | **Live** — General compilation support. |

---

## 3. Non-Existent Files — Explicitly Marked

These paths are referenced in the M1 brief but do **not** exist on the filesystem. They must not be created unless a concrete import contract forces it.

| # | Non-Existent Path | Live Equivalent | Resolution |
|---|------------------|-----------------|------------|
| NX1 | `arnold_pipelines/megaplan/native_runner.py` | `arnold_pipelines/megaplan/auto.py` (in-process auto-drive) + `arnold_pipelines/megaplan/cli/run.py` (subprocess entry) | **Does not exist.** The live runtime equivalent is `auto.py` for in-process auto-drive and `cli/run.py` for subprocess entry. Do **not** create `native_runner.py` unless a concrete import contract forces it. |
| NX2 | `arnold_pipelines/megaplan/native_hooks.py` | `arnold/pipeline/native/hooks.py` (neutral native hooks) + `arnold_pipelines/megaplan/handlers/` (megaplan-specific handler bridge modules: `init.py`, `gate.py`, `finalize.py`, `critique.py`, `review.py`, `execute.py`, `tiebreaker.py`, `override.py`, `plan.py`, `shared.py`, `tickets.py`, `anchors.py`, `verifiability.py`, `structured_output.py`) | **Does not exist.** Megaplan-specific hook behavior lives in the handler bridge modules. Neutral hook dispatch lives at `arnold/pipeline/native/hooks.py`. Do **not** create `native_hooks.py` unless a concrete import contract forces it. |

---

## 4. Stale `arnold/pipelines/...` Reference Classification

The dot-separated `arnold/pipelines/` prefix is the stale package root (excluded from wheel per `pyproject.toml` lines 76, 97). All live megaplan source lives under underscore-separated `arnold_pipelines/`. Every stale reference in the codebase is classified below.

### 4.1 Dead Paths

Directories or files referenced under `arnold/pipelines/` that do not exist on the filesystem and will never be recreated. Listed in the M6 deletion inventory (`arnold/conformance/deleted_surfaces.py`).

| # | Stale Path | Classification | Evidence |
|---|-----------|---------------|----------|
| D1 | `arnold/pipelines/megaplan/` | **Dead path** | Directory does not exist. M6 deletion target (`deleted_surfaces.py` line 38). Conformance allowlists reference it for legacy-gate purposes only. |
| D2 | `arnold/pipelines/megaplan/data/` | **Dead path** | Does not exist. M6 deletion target (`deleted_surfaces.py` line 66). |
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
| D13 | `arnold/pipelines/_template/` | **Dead path** | Does not exist; legacy mapping in `discovery.py`. |

### 4.2 Compatibility Aliases

Stale `arnold/pipelines/` paths that still resolve to live equivalents through discovery/registry compatibility mappings. These are NOT dead — they serve as backward-compatibility aliases.

| # | Stale Path | Live Equivalent | Classification | Notes |
|---|-----------|----------------|---------------|-------|
| A1 | `arnold/pipelines/megaplan/pipelines/doc` | `arnold_pipelines/megaplan/pipelines/doc/` | **Compatibility alias** | `discovery.py:155` |
| A2 | `arnold/pipelines/megaplan/pipelines/creative` | `arnold_pipelines/megaplan/pipelines/creative/` | **Compatibility alias** | `discovery.py:163` |
| A3 | `arnold/pipelines/megaplan/pipelines/jokes` | `arnold_pipelines/megaplan/pipelines/jokes/` | **Compatibility alias** | `discovery.py:171` |
| A4 | `arnold/pipelines/megaplan/pipelines/live_supervisor` | `arnold_pipelines/megaplan/pipelines/live_supervisor/` | **Compatibility alias** | `discovery.py:179` |
| A5 | `arnold/pipelines/megaplan/pipelines/epic_blitz.py` | `arnold_pipelines/megaplan/pipelines/epic_blitz.py` | **Compatibility alias** | `discovery.py:187` |
| A6 | `arnold/pipelines/megaplan/pipelines/select_tournament` | `arnold_pipelines/megaplan/pipelines/select_tournament/` | **Compatibility alias** | `discovery.py:196` |
| A7 | `arnold/pipelines/megaplan/pipelines/writing_panel_strict` | `arnold_pipelines/megaplan/pipelines/writing_panel_strict/` | **Compatibility alias** | `discovery.py:204` |
| A8 | `arnold/pipelines/folder_audit` | `arnold/pipelines/folder_audit/` | **Compatibility alias** | `discovery.py:212`; live under dot-separated path. |
| A9 | `arnold/pipelines/deliberation` | `arnold/pipelines/deliberation/` | **Compatibility alias** | `discovery.py:222`; live under dot-separated path. |
| A10 | `arnold/pipelines/_deliberation_example` | `arnold/pipelines/_deliberation_example/` | **Compatibility alias** | `discovery.py:380`; live under dot-separated path. |
| A11 | `arnold/pipelines/jokes` | `arnold_pipelines/megaplan/pipelines/jokes/` | **Compatibility alias** | `discovery.py:279`; maps to live megaplan sub-pipeline. |
| A12 | `arnold/pipelines/creative` | `arnold_pipelines/megaplan/pipelines/creative/` | **Compatibility alias** | `discovery.py:287`; maps to live megaplan sub-pipeline. |
| A13 | `arnold/pipelines/doc` | `arnold_pipelines/megaplan/pipelines/doc/` | **Compatibility alias** | `discovery.py:295`; maps to live megaplan sub-pipeline. |
| A14 | `arnold/pipelines/live_supervisor` | `arnold_pipelines/megaplan/pipelines/live_supervisor/` | **Compatibility alias** | `discovery.py:303`; maps to live megaplan sub-pipeline. |
| A15 | `arnold/pipelines/select_tournament` | `arnold_pipelines/megaplan/pipelines/select_tournament/` | **Compatibility alias** | `discovery.py:311`; maps to live megaplan sub-pipeline. |
| A16 | `arnold/pipelines/writing_panel_strict.py` | `arnold_pipelines/megaplan/pipelines/writing_panel_strict/pipeline.py` | **Compatibility alias** | `discovery.py:319`; maps to live megaplan sub-pipeline. |
| A17 | `arnold/pipelines/writing_panel_strict` | `arnold_pipelines/megaplan/pipelines/writing_panel_strict/` | **Compatibility alias** | `discovery.py:327`; maps to live megaplan sub-pipeline. |
| A18 | `arnold/pipelines/__init__.py` | `arnold/pipelines/__init__.py` | **Compatibility alias** | `discovery.py:335`; self-referential discovery entry. |
| A19 | `arnold/pipelines/_authoring.py` | `arnold/pipelines/_authoring.py` | **Compatibility alias** | `discovery.py:343`; self-referential discovery entry. |
| A20 | `arnold/pipelines/simplify_writing` | (dead path) | **Compatibility alias** | `discovery.py:355`; maps to M6 archive target. |
| A21 | `arnold/pipelines/vibecomfy_executor` | (dead path) | **Compatibility alias** | `discovery.py:363`; maps to M6 archive target. |
| A22 | `arnold/pipelines/epic_blitz` | (dead path) | **Compatibility alias** | `discovery.py:371`; maps to M6 archive target. |
| A23 | `arnold/pipelines/briefs` | (dead path) | **Compatibility alias** | `discovery.py:388`; maps to M6 archive target. |

### 4.3 Migration Targets

Paths that exist under the live `arnold_pipelines/` prefix but are referenced under stale `arnold/pipelines/` in code or docs. These are the target of M1 migration — stale references must be updated.

| # | Stale Reference | Live Migration Target | Classification |
|---|----------------|----------------------|---------------|
| M1 | `arnold/pipelines/megaplan/__init__.py` | `arnold_pipelines/megaplan/__init__.py` | **Migration target** |
| M2 | `arnold/pipelines/megaplan/pipeline.py` | `arnold_pipelines/megaplan/pipeline.py` | **Migration target** |
| M3 | `arnold/pipelines/megaplan/workflows/planning.py` | `arnold_pipelines/megaplan/workflows/planning.py` | **Migration target** |
| M4 | `arnold/pipelines/megaplan/workflows/workflow.py` | `arnold_pipelines/megaplan/workflows/workflow.py` | **Migration target** |
| M5 | `arnold/pipelines/megaplan/workflows/components.py` | `arnold_pipelines/megaplan/workflows/components.py` | **Migration target** |
| M6 | `arnold/pipelines/megaplan/auto.py` | `arnold_pipelines/megaplan/auto.py` | **Migration target** |
| M7 | `arnold/pipelines/megaplan/registry.py` | `arnold_pipelines/megaplan/registry.py` | **Migration target** |
| M8 | `arnold/pipelines/megaplan/cli/__init__.py` | `arnold_pipelines/megaplan/cli/__init__.py` | **Migration target** |
| M9 | `arnold/pipelines/megaplan/cli/parser.py` | `arnold_pipelines/megaplan/cli/parser.py` | **Migration target** |
| M10 | `arnold/pipelines/megaplan/cli/run.py` | `arnold_pipelines/megaplan/cli/run.py` | **Migration target** |
| M11 | `arnold/pipelines/megaplan/routing.py` | `arnold_pipelines/megaplan/routing.py` | **Migration target** |
| M12 | `arnold/pipelines/megaplan/runtime/bridge.py` | `arnold_pipelines/megaplan/runtime/bridge.py` | **Migration target** |
| M13 | `arnold/pipelines/megaplan/runtime/discovery.py` | `arnold_pipelines/megaplan/runtime/discovery.py` | **Migration target** |
| M14 | `arnold/pipelines/megaplan/planning/operations.py` | `arnold_pipelines/megaplan/planning/operations.py` | **Migration target** |

### 4.4 Conformance Allowlist Entries (Not Migration Targets)

The `arnold/conformance/legacy_reference_allowlist.json` and `arnold/conformance/checks.py` contain references to `arnold/pipelines/megaplan` as **legacy allowlist entries**. These are intentional — the conformance system tracks legacy references to ensure they are not reintroduced as live code paths. They are **dead path gate entries**: they exist only to detect regressions. They are not migration targets and do not require updates during M1.

---

## 5. CLI Surface Mapping

| Plan/Brief Reference | Live Command / Module | Notes |
|---------------------|----------------------|-------|
| Retired top-level pipeline-describe form for Megaplan | `megaplan describe` → `cli/__init__.py:handle_describe()` | The `arnold` top-level CLI routes `workflow` and operator commands only. |
| `arnold pipelines run megaplan --describe` | `megaplan run megaplan --describe` → `cli/run.py:cli_run()` | The live megaplan CLI is a standalone entrypoint. |
| `cli/arnold.py` | `arnold_pipelines/megaplan/cli/__init__.py` | Monolithic CLI (2987 lines). Also `cli/arnold.py` exists as a legacy top-level dispatch (M6 deletion target per `deleted_surfaces.py` line 53). |

---

## 6. Package Build Verification

Per `pyproject.toml`:

- `arnold/pipelines/` (dot-separated): **excluded from wheel** (lines 76, 97). Contains only `deliberation`, `folder_audit`, `evidence_pack`, and `_deliberation_example` — no megaplan.
- `arnold_pipelines/` (underscore-separated): **included in wheel** (line 84). This is the plugin root and the live package for all megaplan source.

This confirms SD2: editing stale `arnold/pipelines/megaplan/` paths would create ghost code excluded from the built wheel.

---

## 7. Doctrine Gate

Per the M1 brief's verifiable completion criterion:

> The source-path reconciliation table exists before workflow edits land and proves that package registration, CLI, auto-drive, and tests inspect the same live canonical workflow source. Any stale `arnold/pipelines/...` reference must be classified as migration target, compatibility alias, or dead path before implementation starts.

This document satisfies that gate. Key proofs:

1. **Live workflow source:** `arnold_pipelines/megaplan/workflows/workflow.py` is the canonical authored source (verified live, 93 lines, `@workflow`/`loop` decorators).
2. **Package registration:** `arnold_pipelines/megaplan/__init__.py` declares `entrypoint: str = "build_pipeline"`, routing through `pipeline.py` facade → `workflows/planning.py`.
3. **CLI:** `arnold_pipelines/megaplan/cli/__init__.py` (2987 lines) handles all CLI surface.
4. **Auto-drive:** `arnold_pipelines/megaplan/auto.py` (4670 lines) provides in-process auto-drive.
5. **Nonexistent files:** `native_runner.py` and `native_hooks.py` confirmed absent; live equivalents documented.
6. **Stale path classification:** 13 dead paths, 23 compatibility aliases, 14 migration targets — all classified before implementation starts.

**M1 doctrine gate label:** LAUNCH-GATE AUTHORITY. This document is the pre-implementation source-path reconciliation required by the M1 launch gate. No workflow edits shall land before this reconciliation is acknowledged.

---

## 8. Relationship to Other Artifacts

- **`docs/arnold/m3-5-canonical-megaplan-source-path-reconciliation.md`** — M3.5 substrate-proof reconciliation (Section 10 contains the M1 entries replicated here). This document is the M1-specific authority.
- **`arnold/conformance/deleted_surfaces.py`** — M6 deletion inventory; source of truth for dead path classifications.
- **`arnold/conformance/legacy_reference_allowlist.json`** — Conformance allowlist; tracks legacy `arnold/pipelines/megaplan` references for regression detection.
- **`arnold_pipelines/discovery.py`** — Registry discovery; contains the compatibility alias mappings documented in §4.2.

---

## 9. Summary

| Category | Count | Resolution |
|----------|-------|------------|
| Live workflow source files | 4 | `workflow.py`, `planning.py`, `components.py`, `__init__.py` |
| Package facade / compatibility | 3 | `pipeline.py`, `__init__.py`, `_compatibility.py` |
| CLI / auto-drive entrypoints | 8 | `cli/__init__.py`, `cli/run.py`, `cli/parser.py`, `cli/projection.py`, `auto.py`, `registry.py`, `routing.py`, `__main__.py` |
| Native compiler/runtime/projection | 15 | `compiler.py`, `runtime.py`, `graph_projection.py`, `ir.py`, `decorators.py`, `hooks.py`, `routing.py`, `checkpoint.py`, `context.py`, `trace.py`, `flags.py`, `__init__.py`, `types.py`, `source_compiler.py`, `compiler.py` (workflow) |
| Nonexistent files | 2 | `native_runner.py`, `native_hooks.py` — explicitly marked nonexistent |
| Dead paths | 13 | Stale `arnold/pipelines/` paths that do not exist |
| Compatibility aliases | 23 | Discovery aliases mapping stale→live paths |
| Migration targets | 14 | Stale `arnold/pipelines/megaplan/...` → live `arnold_pipelines/megaplan/...` |

**Ready for M1 implementation.** No stale path will be created or edited for runtime behavior. All live canonical source paths identified. `native_runner.py` and `native_hooks.py` confirmed nonexistent.
