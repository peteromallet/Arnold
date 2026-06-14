# Bridge Deletion Checklist — `_pipeline/executor.py` Callers

This file lists every caller of the legacy standalone `run_pipeline` /
`run_pipeline_with_policy` from `arnold.pipelines.megaplan._pipeline.executor`
(aliased as `megaplan._pipeline.executor` in the compatibility layer).

**Deletion gate:** every entry in §"Intentionally left on legacy" below must
move to §"Repointed" before the legacy `executor.py` can be deleted.

---

## Repointed in M1

| Caller | Module | Line | Notes |
|--------|--------|------|-------|
| `run_pipeline` | `megaplan/_pipeline/run_cli.py` | 171 | CLI `megaplan run` entry — repointed to `run_pipeline_dispatch` |

---

## Intentionally left on legacy for M1

### `run_pipeline` callers

| Caller | Module | Line | Notes |
|--------|--------|------|-------|
| `run_pipeline` | `megaplan/_pipeline/demo_judges.py` | 35 | Standalone demo entry — callers go through dispatcher; this file stays on legacy until demo entry is also repointed |
| `run_pipeline` | `megaplan/_pipeline/subloop.py` | 72 | `SubloopStep.run()` — child-pipeline execution, not yet bridge-compatible |
| `run_pipeline` | `megaplan/_pipeline/demos/doc_critique.py` | 37 | Standalone demo — not bridged in M1 |
| `run_pipeline` | `megaplan/cli/__init__.py` | 1070 | Resume subcommand (`_resume_human_gate`) — intentionally left on legacy (anti-scope: no resume redesign in M1) |
| `run_pipeline` | `megaplan/_pipeline/registry.py` | 252 | `run_pipeline()` helper — delegates to bare executor when no profile selected; also imports `run_pipeline_with_policy` |

### `run_pipeline_with_policy` callers

| Caller | Module | Line | Notes |
|--------|--------|------|-------|
| `run_pipeline_with_policy` | `megaplan/_pipeline/registry.py` | 254 | `run_pipeline()` helper — profile path calls this |
| `run_pipeline_with_policy` | `tests/test_pipeline_runnable_e2e.py` | 23 | E2E test |
| `run_pipeline_with_policy` | `tests/characterization/test_pipeline_golden.py` | 33 | Characterization test |
| `run_pipeline_with_policy` | `tests/test_pipeline_planning_parity.py` | 34 | Planning parity test |
| `run_pipeline_with_policy` | `tests/test_pipeline_composability.py` | 314 | Composability test |
| `run_pipeline_with_policy` | `tests/test_pipeline_runtime_e2e.py` | 30 | Runtime E2E test |
| `run_pipeline_with_policy` | `tests/test_auto_pipeline_runtime.py` | 24 | Auto pipeline runtime test |
| `run_pipeline_with_policy` | `tests/test_mechanical_gate_e2e.py` | 38 | Mechanical gate E2E test |
| `run_pipeline_with_policy` | (additional test callers) | — | ~11 more test modules import via `megaplan/_pipeline/executor` transitively |

Additional test modules (via `megaplan._pipeline.executor` transitive imports):
- `tests/_pipeline/test_epic_blitz_e2e.py`
- `tests/_pipeline/test_human_gate.py`
- `tests/_pipeline/test_writing_panel_e2e.py`
- `tests/pipelines/test_doc_pipeline.py`
- `tests/test_pipeline_compose.py`
- `tests/test_pipeline_mode_e2e.py`
- `tests/test_pipeline_override.py`
- `tests/test_pipeline_scoped_prompts.py`
- `tests/test_pipeline_subloop.py`
- `tests/test_pipeline_typed_edges.py`
- `tests/test_plan_state_writer.py`

---

## Not bridge-compatible in M1 (blockers)

Pipelines that depend on `_materialize_stage_step` (StepInvocation injection at
`executor.py:709-721`) are NOT M1-bridgeable and must stay on the legacy path
via the dispatcher allowlist:

- `creative` — uses stage-level invocation metadata
- `epic_blitz` — uses stage-level invocation metadata
- Any pipeline with `invocation` set on `Stage`

These pipelines cannot be dispatched through the bridge until `_BridgeStep`
learns to honor `_materialize_stage_step`.

---

## Deletion gate

Before `arnold/pipelines/megaplan/_pipeline/executor.py` can be deleted:

1. Every caller in §"Intentionally left on legacy" must be moved to §"Repointed".
   This means writing bridge-compatible paths for:
   - `SubloopStep` (child-pipeline execution)
   - Resume path (`cli/__init__.py:1339`)
   - `run_pipeline_with_policy` and its 19+ callers
   - All demo entries (`demo_judges.py`, `demos/doc_critique.py`, etc.)
2. `_materialize_stage_step` must be supported in `_BridgeStep` so that
   `creative`, `epic_blitz`, and similar pipelines can pass through the bridge.
3. The dispatcher allowlist `_BRIDGED_PIPELINES` must be broadened to include
   the newly supported pipelines, or removed entirely after all pipelines
   are bridge-compatible.
4. All test modules that import from `megaplan._pipeline.executor` must be
   updated to target the bridge surface.
