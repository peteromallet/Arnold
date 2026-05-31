# `megaplan cost` — per-vendor / per-model cost & token breakdown

Spec shorthand: `directed/light` (default depth). Read-only reporting command + one source-fix to make token attribution exact.

## Outcome

Add a read-only `megaplan cost --plan <name>` subcommand that prints a per-vendor and per-model breakdown of a finished (or in-flight) plan's spend: dollar cost, cost %, token count, token %. Cost is authoritative (summed from `cost_recorded` events, reconciled against `state.meta.total_cost_usd`); tokens are attributed **exactly** by model — which requires a small source fix to stamp the model onto `llm_call_end` events, which today omit it.

A reviewer checks: `megaplan cost --plan X` on an existing plan prints a vendor table (claude / deepseek / codex) and a model table, the cost total reconciles to `total_cost_usd`, and on a freshly-run plan the token attribution is exact (no "unknown"/heuristic bucket needed).

## Background

A breakdown is currently only obtainable by hand-parsing `events.ndjson`: `cost_recorded` events carry `{request_id, cost_usd, provider, model}` (cost is cleanly attributable), but `llm_call_end` events carry only `{tokens_in, tokens_out, request_id}` — **no model** — so tokens can only be attributed by joining on `request_id` to `cost_recorded`, and cheap-worker calls whose `cost_recorded` has a null `request_id` fall through to a guess. The fix is to stamp `model` onto `llm_call_end` at emission (the model is already in scope there), then have the command attribute tokens directly.

## Scope (IN)

1. **Stamp model onto `llm_call_end`.** In `_emit_llm_end()` (`megaplan/workers/hermes.py:170`), add a `model` parameter and include it in the payload, exactly as `_emit_llm_start()` already does with `resolved_model`. Update the call site (~`hermes.py:1015`) to pass `resolved_model` (in scope there). Audit for **any other `llm_call_end` emission sites** (e.g. `megaplan/workers/shannon.py`, `workers/_impl.py`) and thread model through them too — every emitter must stamp it. Payload addition is backward-compatible (consumers tolerate absence).

2. **New `megaplan cost` subcommand.**
   - Register in `megaplan/cli.py` mirroring the `introspect`/`trace` pattern (subparser ~line 4142, `--plan` required; add a `_handle_cost()` wrapper; add `"cost": _handle_cost` to the dispatch dict ~line 4526).
   - Implement the handler in a new module `megaplan/observability/cost.py` (alongside `trace.py` / `introspect.py` / `doctor.py`), signature `handle_cost(root, args) -> int`, resolving the plan dir via `find_plan_dir` like `introspect` does.
   - Read events with the existing `read_events(plan_dir, kinds=[...])` from `megaplan/observability/events.py` — do not re-implement an ndjson parser.

3. **Aggregation logic.**
   - **Cost:** sum `cost_recorded.payload.cost_usd` grouped by model and by vendor. Reconcile the grand total against `state.meta.total_cost_usd` the same way `introspect` does (take the max of events-sum vs meta to avoid undercount); surface the reconciled total and note the source.
   - **Tokens:** sum `llm_call_end` `tokens_in + tokens_out` grouped by the new `model` field. **Backward-compat fallback** for plans run before the source fix (no `model` on `llm_call_end`): join on `request_id` to the `cost_recorded` model map, and bucket any still-unmatched tokens as `deepseek` (the documented heuristic — every premium call carries a request_id, cheap workers don't). Indicate in output when the fallback was used so the number is honestly labelled as an estimate vs exact.
   - **Vendor classification** helper: model string containing opus/sonnet/claude → `claude`; gpt/codex → `codex`; deepseek/flash/hermes/shannon → `deepseek`; else `other`.

4. **Output.** Default human-readable table: a by-vendor table (cost, cost%, tokens, tok%) and a by-model table. Add `--format json` for machine consumption (emit a dict with totals, by_vendor, by_model, reconciliation source, and an `exact_tokens: bool`). Optional `--by-phase` flag that adds a per-phase cost/token rollup (events carry `phase`). Keep `--by-phase` minimal; the vendor/model tables are the core deliverable.

5. **Tests** (`tests/` — new `test_cost.py` or extend an observability test): synthesize a small `events.ndjson` and assert the vendor/model rollups, the reconciliation-against-meta behavior, the exact-token path (model present), and the fallback path (model absent → request_id join → deepseek bucket, `exact_tokens=False`). Plus a test that `_emit_llm_end` now writes `model`.

## Scope (OUT) / anti-scope

- **Do not** change how cost itself is computed or recorded; `cost_recorded` and `total_cost_usd` (`_core/state.py:564`) stay as-is — this command only *reads* them.
- **Do not** add live polling/`--follow` (that's `trace`'s job).
- **Do not** build cross-plan aggregation (single plan only for now).
- **Do not** alter `llm_call_start`, `cost_recorded`, or heartbeat payloads beyond what's needed; only `llm_call_end` gains a field.
- **Do not** introduce a new events reader — reuse `read_events`.

## Locked decisions

- New module `megaplan/observability/cost.py`; mirror the existing reporting-command pattern, no new architecture.
- Cost = exact (reconciled to `total_cost_usd`); tokens = exact once `model` is stamped, with a labelled request_id→deepseek fallback for legacy plans.
- Vendor buckets: claude / codex / deepseek / other.

## Open questions for the planner

- Exact column layout / whether to show in-vs-out token split — planner's call; keep it readable.
- Whether `--by-phase` is worth including now or deferred — include if cheap, else note as follow-up.

## Constraints

- Read-only: the command must never mutate plan state or events.
- Backward-compatible on **existing** plans (no `model` on old `llm_call_end`) — must still produce a sensible, honestly-labelled breakdown via fallback.
- Adding the `model` field must not break existing event consumers (`trace`, `introspect`) or their tests.

## Done criteria

- `megaplan cost --plan <name>` prints vendor + model tables; total reconciles to `state.meta.total_cost_usd`.
- `--format json` emits a structured payload incl. `exact_tokens` bool.
- New plans: tokens attributed exactly from the stamped `model` (no fallback bucket).
- `_emit_llm_end` stamps `model`; all `llm_call_end` emitters updated.
- Tests cover exact path, fallback path, reconciliation, and the new event field.
- Existing observability test suites still pass.

## Touchpoints (file:line, current tree)

- `megaplan/workers/hermes.py` — `_emit_llm_end` def (170) + call site (~1015); `_emit_llm_start` (~ above, the model-stamping template); `cost_recorded` emit (~1174, reference for model/vendor). *(file has uncommitted WIP — build on it.)*
- `megaplan/workers/shannon.py`, `megaplan/workers/_impl.py` — audit for other `llm_call_end` emitters; thread model through. *(uncommitted WIP — build on it.)*
- `megaplan/observability/events.py` — `read_events()` (~301), `EventKind`, `emit()` (~157). *(uncommitted WIP — build on it.)*
- `megaplan/observability/introspect.py` — cost reconciliation pattern (~540–560) to mirror.
- `megaplan/observability/cost.py` — NEW handler module.
- `megaplan/cli.py` — subparser registration (~4142), wrapper + dispatch dict (~4526).
- `megaplan/_core/state.py` — `total_cost_usd` ledger (~564), read-only reference.
- `tests/` — new `test_cost.py`.
