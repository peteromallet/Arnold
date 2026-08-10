# Milestone 4 — Main Megaplan Pipeline Conversion Handoff

## Outcome

`arnold/pipelines/megaplan/pipeline.py` now contains a canonical native `@pipeline("megaplan")` declaration that compiles, projects to a graph, and runs side-by-side with the existing graph executor behind a per-run opt-in flag. The graph executor remains the production default.

## Topology baseline

- Legacy hand-built graph hash: `sha256:f11cd2e61fdb8fcb8aac558db6ceb5aef2a936cd2a58c0277a7e45523512ba30`
- `build_pipeline()` validates the native-derived graph against this hash and falls back to the hand-built graph if parity is not yet proven.
- `validate_control_flow()` reports no defects on the hand-built fallback.

## Parity fixture matrix

Fixtures live under `tests/arnold/pipelines/megaplan/data/native_parity/` and are exercised by `tests/arnold/pipelines/megaplan/test_native_execution_parity_fixtures.py`.

| Scenario | Status | Golden trace |
|----------|--------|--------------|
| happy_finalize (straight-through) | **passing** | `happy_finalize_golden_graph_trace.json` |
| revise_loop | **passing** | `revise_loop_golden_graph_trace.json` |
| tiebreaker (proceed path) | **passing** | `tiebreaker_golden_graph_trace.json` |
| gate escalate-to-finalize | **passing** | `escalate_golden_graph_trace.json` |
| tiebreaker escalate | **passing** | `tiebreaker_golden_graph_trace.json` |
| execute/review artifact parity | **passing** | `execute_review_artifact_golden_graph_trace.json` |
| override force-proceed | **known limitation** | `override_force_proceed_golden_graph_trace.json` |
| override abort | **known limitation** | `override_abort_golden_graph_trace.json` |
| suspension/resume cursor persistence | **known limitation** | `suspension_resume_golden_graph_trace.json` |

Known limitations are blocked on M4 compiler/runtime gaps, not on the Megaplan wrapper itself.

## Execution-mode selection

- Default (no marker): graph executor.
- Native opt-in: set `state["_native_execution"] = True` before dispatch; `run_pipeline_dispatch` in `arnold/pipelines/megaplan/_pipeline/_bridge.py` routes to `NativeMegaplanRunner`.

## Resume routing

Implemented in `arnold/pipeline/native/checkpoint.py::classify_resume_cursor()` and wired in `_bridge.py`:

- Graph-born cursor (no top-level `native` key or `native: null`) → graph executor.
- Native-born cursor (`native` dict with integer `pc` and `version`) → native executor.
- Corrupt/ambiguous native cursor → raises `NativeCursorCorruptError` (fail-closed).

## Escape-hatch behavior

- `build_pipeline()` falls back to the hand-built legacy graph with a `UserWarning` when native-derived topology hash does not match the baseline.
- Override routing and suspension/resume are explicit known limitations for M4; production default remains graph execution.

## M5A / M5B target order

1. **M5A — Parallel and panel pipelines**: add native `parallel(...)`, panel composition, and derived-graph/projection support for bounded fan-out/fan-in. Convert `select-tournament` and `epic-blitz`. Keep human-gate suspend/resume out of scope.
2. **M5B — Human gates**: add human-gate suspend/resume parity and convert `writing-panel-strict`; `deliberation` enters only by explicit kickoff if a second real human-gate pipeline is needed.

## Remaining runtime API gaps

- `parallel(...)` primitive for bounded fan-out/fan-in.
- Human-gate suspension/resume full parity (cursor persistence under test conditions).
- Override routing in native compiler grammar (`override_vocabulary` on decision stages).
- Native-derived topology hash parity with hand-built graph once compiler supports multi-way decision stages with extra edges and loop back-edges.

## Committed artifacts

- `arnold/pipelines/megaplan/pipeline.py` — native `@pipeline("megaplan")` declaration + legacy fallback.
- `arnold/pipelines/megaplan/_pipeline/_bridge.py` — execution-mode dispatch and resume routing.
- `arnold/pipeline/native/checkpoint.py` — `classify_resume_cursor()`.
- `tests/arnold/pipelines/megaplan/parity_harness.py` — shared parity comparison harness.
- `tests/arnold/pipelines/megaplan/data/native_parity/` — golden traces and scenario descriptors.
- `tests/arnold/pipelines/megaplan/test_native_execution_parity_fixtures.py` — parity fixture tests.
- `tests/arnold/pipelines/megaplan/test_native_port_declarations.py` — port/metadata parity tests.
- `tests/arnold/pipeline/native/test_resume_routing.py` — cursor routing tests.
