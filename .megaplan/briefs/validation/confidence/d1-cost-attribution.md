## Verdict

**YES — this is a real gap. Severity: HIGH.**

### How cost is attributed today (plan-dir-scoped through and through)

Every cost write path and read path is keyed on a `plan_dir`:

1. **Cost emission** — The sole `COST_RECORDED` emitter is `megaplan/workers/hermes.py:1179-1189`. It calls `emit(EventKind.COST_RECORDED, plan_dir=plan_dir, ...)`, appending to `plan_dir/events.ndjson`.

2. **Cost accumulation** — `megaplan/_core/state.py:764-770` sums `entry["cost_usd"]` into `state["meta"]["total_cost_usd"]`, persisted to `plan_dir/state.json`. The pipeline executor writes state via `_merge_state_to_disk(artifact_root, state, ...)` (`_pipeline/executor.py:260`).

3. **Cost reading** — The `cost` CLI (`observability/cost.py:376-398`) calls `find_plan_dir(cwd, args.plan)` then reads `plan_dir/events.ndjson` + `plan_dir/state.json`. `CostTracker` (`_pipeline/runtime.py:70-71`) reads `state["meta"]["total_cost_usd"]`. `doctor.py:347-353` and `introspect.py:535-539` both sum `COST_RECORDED` events from `plan_dir/events.ndjson`.

4. **No cross-plan rollup exists.** The `insights.py` engine reads from `SessionDB` (SQLite, per-agent), not from plan directories. The `cost` CLI's `_load_state` (cost.py:55-63) reads exactly one `plan_dir/state.json`.

### What happens with a non-plan dispatch?

If Arnold's resident loop (no `plan_dir`) dispatches a model: the `emit()` call at `hermes.py:1179` **fails** — `plan_dir` is a required positional arg (`events.py:278`). Even if it were made optional, the emitted event would have no home; the `cost` CLI can only find events in `plan_dir/events.ndjson`. The cost **silently vanishes** from Megaplan's accounting.

### What must change

**Concrete fix** — milestone: **M5 (Dispatch as Shared Service)**:

1. **Introduce a `DispatchContext`** carrying `plan_dir: Path | None` + `tenant_id: str` + `dispatch_id: str`. Pass it alongside the model call.

2. **In `emit()` / `EventWriter`** (`events.py:150-237`): accept an optional `dispatch_ctx` parameter. When `plan_dir` is `None` but `dispatch_ctx` is present, write to a tenant-scoped journal (`~/.megaplan/dispatch_events/{tenant_id}/events.ndjson`) instead. Same seq/flock guarantees, different path.

3. **Add a `megaplan cost --dispatch`** flag to `handle_cost` (`cost.py:367-413`) that reads from the dispatch journal and maps costs to individual dispatch contexts. The reconciliation path (`_load_state`) falls back gracefully when no `plan_dir` exists.

4. **Extend `CostTracker`** (`runtime.py:67-72`) to query both `state["meta"]["total_cost_usd"]` and a dispatch-level accumulator so caps work across plan and non-plan calls.

This is not cosmetic — dispatch without cost tracking means untracked spend on every resident-loop model call. The fix is 2–3 files deep and touches the event journal, the CLI, and the runtime policy.