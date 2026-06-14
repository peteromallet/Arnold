# Agent Runtime Integration

How internal Megaplan callers dispatch one agent request, fan out many, use
generic process fanout, and keep the vendorable runtime surface clean.

## Single dispatch: `run_step_with_worker`

For one-shot agent execution (a single critique, a triage call, a distillation
step) the idiomatic internal path is **`run_step_with_worker`** from
`megaplan.workers`.  It drives Claude (via Shannon interactive tmux), Codex, and
Hermes through a single worker dispatch function:

```python
from megaplan.workers import run_step_with_worker

worker, agent, mode, refreshed = run_step_with_worker(
    step="critique",
    state=state,
    plan_dir=plan_dir,
    args=args,
    root=root,
    resolved=resolved_mode,
    prompt_override=prompt,
    read_only=True,
    output_path=output_path,
)
# worker is a WorkerResult with .payload, .cost_usd, .session_id, etc.
```

This is the compatibility primitive.  It is not being replaced — fanout callers
converge *onto* it, not away from it.  Callers that only need one agent dispatch
(`loop/engine.py`, `handlers/shared.py`, `execute/batch.py`, sequential
tiebreakers) keep using `run_step_with_worker` directly.

A thin `AgentDispatcher` wrapper exists in the public runtime contracts
(`megaplan.agent_runtime.adapters.AgentDispatcher`) for callers that want to
inject a dispatcher through the contract boundary, but the canonical internal
entry point is `run_step_with_worker`.

## Worker-backed fanout: `WorkerUnit` + `scatter_worker_units`

When the caller needs to dispatch **multiple** agent calls concurrently (prep
research areas, parallel review checks), use the worker fanout path in
`megaplan._core.worker_fanout`:

```python
from megaplan._core import WorkerUnit, scatter_worker_units

units = [
    WorkerUnit(
        step="prep-research",
        resolved=model,
        prompt=built_prompt,
        output_path=output_path,
        read_only=True,
        extra={"index": i, "area": area_dict},
    )
    for i, area in enumerate(areas)
]

result = scatter_worker_units(
    units=units,
    state=state,
    plan_dir=plan_dir,
    root=root,
    args=args,
    parse_result=my_parse_hook,       # (index, WorkerUnitResult, WorkerUnit) -> parsed
    on_unit_error=my_error_handler,   # (index, Exception) -> (payload, cost, pt, ct, tt)
    max_concurrent=4,
    timeout_seconds=900.0,
)
# result.ordered_results   — parsed hook outputs in input order
# result.total_cost        — aggregated across all units
# result.total_tokens      — aggregated token count
```

### Why this design

- **Prompt/template/path construction happens in the parent process** (the
  caller).  Each `WorkerUnit` carries only simple strings, paths, and a resolved
  `AgentMode` — all trivially picklable.  This avoids the process-boundary
  headaches of shipping model objects or file handles through `pickle`.

- **Parse/reduce hooks run in the parent process** after `WorkerUnitResult`
  objects come back.  `WorkerUnitResult` is a rich, picklable dataclass carrying
  `payload`, `raw_output`, `duration_ms`, `cost_usd`, `session_id`,
  `trace_output`, `rendered_prompt`, `model_actual`, `shannon_plan`, per-unit
  token counts, and unit metadata (`step`, `output_path`, `read_only`, `extra`,
  `agent`, `mode`, `model`, `resolved_model`, `effort`).  Hooks consume this
  directly — no lossy `payload`-only unwrapping unless the caller opts into
  legacy behaviour by omitting `parse_result`.

- **No raw Hermes/thread fanout in production callers.**  `scatter_worker_units`
  delegates to `scatter_gather_processes` (process-based concurrency) under the
  hood via a picklable module-level adapter (`_scatter_worker_unit_from_packed`).
  The caller never imports or calls `scatter_gather_processes`,
  `scatter_gather_checks`, or raw Hermes runtime symbols directly.

### Side units

`scatter_worker_units` accepts optional `side_units` and `parse_side_result`.
Main and side units are flattened into a single ordered process-fanout batch
(packed with `role` and `original_index` metadata), then split deterministically
in the parent.  This is how parallel review dispatches review checks (main
units) and a criteria verdict (side unit) in one fanout call:

```python
result = scatter_worker_units(
    units=review_check_units,
    side_units=[criteria_verdict_unit],
    parse_result=parse_review_result,
    parse_side_result=parse_criteria_result,
    ...
)
# result.ordered_results  — parsed review checks
# result.side_results     — parsed criteria verdict
```

Zero-main side-only calls and zero-side calls are both supported.  Aggregate
cost/token totals span both roles.

### Production callers

| Caller | Module | Pattern |
|--------|--------|---------|
| Prep research fanout | `megaplan.orchestration.prep_research` | `WorkerUnit` per area, `parse_result` normalizes findings, `on_unit_error` produces timeout/error sentinels |
| Parallel review | `megaplan.review.parallel` | `WorkerUnit` per check + one side criteria unit, `parse_result` enforces exactly-one-check, `parse_side_result` extracts criteria payload |

## Generic process fanout: `megaplan.agent_runtime.process_fanout`

For callers that need **process-isolated fanout without the worker dispatch
layer** (i.e., running arbitrary Python functions in subprocesses, not driving
CLI backends through `run_step_with_worker`), use the vendorable alias:

```python
from megaplan.agent_runtime.process_fanout import (
    GenericScatterResult,
    scatter_gather_processes,
)
```

This re-exports the generic (non-review) primitives from
`megaplan._core.hermes_fanout`.  It deliberately **excludes** review-specific
names like `ScatterResult` and `scatter_gather_checks`.  Callers that need those
should import from `megaplan._core.hermes_fanout` directly.

`megaplan._core.process_fanout` is a parallel alias for internal callers that
already import from `_core`.  Both resolve to the same implementation.

## Public/vendorable versus worker-compatibility split

### `megaplan.agent_runtime` — vendorable public surface

The `megaplan.agent_runtime` package is the **vendorable contract**.  It is
designed to be extracted into a standalone package with no dependency on
`megaplan.workers` or `megaplan._core`.  Importing it in a fresh Python process
does not pull either module into `sys.modules`.

Public exports:

| Symbol | Source | Purpose |
|--------|--------|---------|
| `AgentRequest` | `agent_runtime.contracts` | One agent dispatch request |
| `AgentResult` | `agent_runtime.contracts` | One agent dispatch result (no worker conversion methods — those live on `WorkerResult` in `megaplan.workers`) |
| `TokenUsage` | `agent_runtime.contracts` | Token accounting dataclass |
| `CostUsage` | `agent_runtime.contracts` | Cost accounting dataclass |
| `ResultProvenance` | `agent_runtime.contracts` | Agent/model/session provenance |
| `FanoutUnit` | `agent_runtime.contracts` | One unit for `scatter_agent_units` |
| `FanoutResult` | `agent_runtime.contracts` | Aggregated fanout result |
| `scatter_agent_units` | `agent_runtime.contracts` | Thread-based fanout with injected `AgentDispatcher` |
| `AgentSpec` | transitional re-export from `megaplan.types` | Parsed agent spec |
| `AgentMode` | transitional re-export from `megaplan.types` | Resolved agent mode |
| `parse_agent_spec` | transitional re-export from `megaplan.types` | Parse spec string |
| `format_agent_spec` | transitional re-export from `megaplan.types` | Format spec to string |
| `AgentDispatcher` | `agent_runtime.adapters` | Dispatch protocol |
| `PromptProvider` | `agent_runtime.adapters` | Prompt resolution protocol |
| `SessionStore` | `agent_runtime.adapters` | Session persistence protocol |
| `EventEmitter` | `agent_runtime.adapters` | Event emission protocol |
| `LivenessTouch` | `agent_runtime.adapters` | Liveness heartbeat protocol |
| `KeySource` | `agent_runtime.adapters` | API key resolution protocol |

`AgentSpec`, `AgentMode`, `parse_agent_spec`, and `format_agent_spec` are
**identity-preserving transitional re-exports** from `megaplan.types`.  A
downstream vendor importing `megaplan.agent_runtime.AgentSpec` gets the exact
same object as `megaplan.types.AgentSpec`.  Full decoupling (copying the
definitions into `agent_runtime`) is deferred — the current split keeps the
authoritative definitions in `megaplan.types` and re-exports them.

### Worker compatibility: `megaplan.workers` + `megaplan._core.worker_fanout`

These modules own the **Megaplan adapter layer** — the bridge between the public
runtime contracts and the concrete CLI backends (Claude/Shannon, Codex, Hermes):

- **`megaplan.workers`** — `run_step_with_worker`, `WorkerResult`,
  `resolve_agent_mode`, and the full Claude/Codex/Hermes dispatch
  implementation.  `WorkerResult` owns the `to_agent_result()` /
  `from_agent_result()` boundary conversions — not `AgentResult` in
  `agent_runtime`.

- **`megaplan._core.worker_fanout`** — `WorkerUnit`, `WorkerUnitResult`,
  `scatter_worker_unit`, `scatter_worker_units`.  This is the reusable
  worker-fanout primitive that production prep and review fanout callers depend
  on.  It also contains `_worker_unit_to_agent_request` (the
  `WorkerUnit`→`AgentRequest` adapter) and `_scatter_worker_unit_from_packed`
  (the picklable process-fanout entry point).

Callers that need worker fanout import from `megaplan._core` and depend on the
`workers` package.  Callers that only need the vendorable contracts import from
`megaplan.agent_runtime` and stay decoupled.

## Quick reference

| Goal | Import from | Use |
|------|-------------|-----|
| Dispatch one agent | `megaplan.workers` | `run_step_with_worker(...)` |
| Fan out many workers | `megaplan._core` | `WorkerUnit` + `scatter_worker_units(...)` |
| Generic process fanout | `megaplan.agent_runtime.process_fanout` | `scatter_gather_processes(...)` |
| Thread-based injected fanout | `megaplan.agent_runtime` | `scatter_agent_units(...)` with an `AgentDispatcher` |
| Runtime contracts only | `megaplan.agent_runtime` | `AgentRequest`, `AgentResult`, protocols |
| Worker result conversion | `megaplan.workers` | `WorkerResult.to_agent_result()` / `.from_agent_result()` |
