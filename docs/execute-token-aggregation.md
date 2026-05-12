# Execute Phase Token Aggregation Bug

## Symptom

In `step_receipt_execute_v*.json`, `prompt_tokens` and `completion_tokens` are
always `0`, even when the execute phase consumed substantial inference (e.g.
10+ minutes of DeepSeek inference per batch). `cost_usd` is also `0.0`.

Other phases sharing the same hermes/deepseek worker (e.g. finalize) capture
tokens correctly. The defect is specific to **how the execute receipt is
assembled in the multi-batch auto-loop**, not the hermes worker.

Example evidence from `.megaplan/plans/tickets-mvp/`:

| receipt | prompt_tokens | completion_tokens | cost_usd | duration_ms |
| ------- | ------------- | ----------------- | -------- | ----------- |
| `step_receipt_finalize_v4.json` | 787,185 | 12,608 | 0.0 | 461,620 |
| `step_receipt_execute_v4.json`  | **0**   | **0**  | 0.0 | 646,024 |

(`cost_usd` is 0 in both rows because fireworks/deepseek pricing isn't wired
into the cost path — separate issue, out of scope here.)

## Root cause

`megaplan/execute/core.py::dispatch_execute_auto_loop` (the multi-batch entry
point that runs ≥1 batches and then aggregates into a single
`execution.json` + `step_receipt_execute_v<iter>.json`) builds its
`receipt_worker` like this around line 1473:

```python
receipt_worker = WorkerResult(
    payload=aggregate_payload,
    raw_output="",
    duration_ms=total_duration_ms,
    cost_usd=total_cost_usd,
    session_id=latest_session_id,
    trace_output="".join(trace_chunks) if trace_chunks else None,
)
```

`WorkerResult.prompt_tokens` / `completion_tokens` / `total_tokens` default to
`0` (see `megaplan/workers.py:104-106`), and they are never set here. Per-batch
`result.worker.prompt_tokens` is populated correctly by the hermes worker
(`megaplan/hermes_worker.py:624-635`), but the aggregation loop only sums
`duration_ms` and `cost_usd`, dropping every batch's token counts on the floor.

`receipts/__init__.py:93-94` then reads `worker.prompt_tokens`
(`getattr(worker, "prompt_tokens", 0)`) and faithfully writes 0 into the
receipt.

By contrast, the single-batch path at `core.py:887-898`
(`dispatch_execute_one_batch`) *does* forward `prompt_tokens`,
`completion_tokens`, and `total_tokens` from `result.worker`. So single-batch
executes would record real tokens — the bug only manifests in the auto-loop.

## Recommended fix

Aggregate tokens in the same loop that already aggregates duration and cost,
then forward them into `receipt_worker`. ~10 LOC.

### Files to change

- `megaplan/execute/core.py`
  - Add `total_prompt_tokens`, `total_completion_tokens`,
    `total_total_tokens` accumulators next to `total_duration_ms` /
    `total_cost_usd` (search for the latter near the top of the auto-loop;
    they're initialized before the batch loop).
  - Increment each accumulator inside the loop alongside `total_duration_ms`
    (around line 1289-1290).
  - Pass them to the `WorkerResult(...)` constructor at line 1473.

### Risk / blast radius

- Pure addition; no behavior change for any existing call path.
- `single-batch` path is unaffected (it already does the right thing).
- Receipt schema already accepts these fields — no schema migration needed.
- Audit log consumers that previously saw `0` will start seeing real numbers.
  This is the desired outcome and shouldn't break any existing analytics
  (sum-of-zero is still a valid input).

## Out of scope (deferred)

These are visible in the same receipt but are unrelated to token aggregation:

1. **`cost_usd = 0.0` for hermes/deepseek.** Pricing isn't wired for
   fireworks-hosted models; `result.get("estimated_cost_usd", 0.0)` in
   `hermes_worker.py:623` returns 0. Fix requires per-provider pricing table.
2. **`model_actual: null` and `prompt_hash_*: null` in the auto-loop receipt.**
   `receipt_worker` in the auto-loop also omits `rendered_prompt` and
   `model_actual`. Multi-batch aggregation has no single "rendered prompt"
   semantically, but we could pull `model_actual` from the last batch.
3. **`session_id`** uses `latest_session_id` (last batch); fine as a coarse
   anchor, but the audit log loses earlier batches' session ids. Existing
   `apply_session_update` already records each per batch in plan state.
