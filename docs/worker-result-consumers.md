# WorkerResult consumer audit

This is the durable audit artifact for M1, "the invocation seam."  The milestone
adds `rate_limit: dict[str, Any] | None = None` to `WorkerResult`, `AgentResult`,
and `WorkerUnitResult` without making it part of routing, retry admission,
vendor selection, or the persisted top-level receipt schema.

## Contract notes

- `rate_limit` is optional, opaque metadata.  Current engines may leave it
  `None`; future engines can populate a dictionary without changing consumer
  contracts.
- One-to-one rebuilds copy `rate_limit` exactly from their source result.
- Retry merges prefer the retry attempt when it supplies non-`None`
  `rate_limit`; otherwise they keep the base attempt.
- Aggregate wrappers preserve every non-`None` value as `{"values": [...]}` via
  `aggregate_rate_limits`.
- `shannon_plan` remains opaque compatibility metadata.  It is serialized by the
  Shannon worker and written to receipts, but it is not an engine discriminator.
- `_classify_vendor` is cost-reporting logic only.  It buckets model strings for
  `megaplan cost`; worker dispatch and result transforms do not consult it.
- M1 preserves the receipt constraint that absent rate-limit data is not emitted
  as a new top-level `rate_limit: null` field in step receipts.

## Consumer table

| File / function | Fields read | Mutates or rebuilds `WorkerResult` | Aggregates results | Engine-aware logic |
| --- | --- | --- | --- | --- |
| `megaplan/workers/_impl.py` / `WorkerResult` | Native storage for `payload`, raw output, timing, cost, session, trace, rendered prompt, model, token counts, `shannon_plan`, `rate_limit` | Defines the compatibility dataclass | No | No |
| `megaplan/agent_runtime/contracts.py` / `AgentResult` | Same worker-visible fields plus runtime provenance and metadata | Native runtime dataclass | No | No |
| `megaplan/_core/worker_fanout.py` / `WorkerUnitResult` | Worker fields plus unit metadata (`step`, output path, routing details) | Native fan-out dataclass | No | No |
| `megaplan/workers/_impl.py` / `WorkerResult.from_agent_result` | All `AgentResult` worker-compatible fields including `rate_limit` | Rebuilds `WorkerResult` one-to-one | No | No |
| `megaplan/workers/_impl.py` / `WorkerResult.to_agent_result` | All `WorkerResult` fields including `rate_limit` | Projects to `AgentResult` one-to-one | No | No |
| `megaplan/_core/worker_fanout.py` / `WorkerUnitResult.from_worker_result` | All worker-visible fields including `rate_limit` | Projects to `WorkerUnitResult` one-to-one | No | No |
| `megaplan/_core/worker_fanout.py` / `run_worker_unit` | Worker payload, raw output, metrics, trace, model, `shannon_plan`, `rate_limit` through `from_worker_result` | Rebuilds a unit result from a worker result | No | No |
| `megaplan/workers/_impl.py` / `_mock_result` | Payload and optional trace | Constructs mock `WorkerResult` with defaults | No | No |
| `megaplan/workers/hermes.py` / worker return | Payload, raw output, duration, cost, session, trace, rendered prompt, model, token counts | Constructs native Hermes `WorkerResult`; `rate_limit` defaults to `None` | No | No |
| `megaplan/workers/shannon.py` / worker return | Payload, raw output, duration, cost, session, trace, rendered prompt, model, token counts, serialized `shannon_plan` | Constructs native Shannon `WorkerResult`; `rate_limit` defaults to `None` | No | Shannon serializes `shannon_plan`, but consumers treat it as opaque metadata |
| `megaplan/workers/_impl.py` / `run_step_with_worker` dispatch and retry | Agent, mode, model, session, output, cost and token fields | Constructs worker results from engine output and timeout recovery | No | Yes, deliberately contained: Shannon self-cleans with a fresh retry; Codex records stale session state before retry |
| `megaplan/handlers/shared.py` / `_run_worker` | Worker result plus agent, mode, refreshed routing tuple | Pass-through only | No | Resolves agent/mode before invocation; does not inspect `shannon_plan` or `rate_limit` |
| `megaplan/handlers/plan.py` / `handle_plan` | `worker.payload` and receipt/history fields via `_finish_step` | Consumer-only | No | No |
| `megaplan/handlers/plan.py` / `handle_prep` | `worker.payload` and receipt/history fields via `_finish_step` | Consumer-only | No | No |
| `megaplan/handlers/critique.py` / `_rebuild_recovered_critique_worker` | Raw output, timing, cost, session, trace, prompt, model, token counts, `rate_limit` | Rebuilds `WorkerResult` one-to-one with recovered payload | No | No |
| `megaplan/handlers/critique.py` / `handle_critique` | Payload, validation output, receipt/history fields | May use recovery rebuild above | No | No |
| `megaplan/handlers/critique.py` / `handle_revise` | Payload plus receipt metrics | Consumer-only | No | No |
| `megaplan/handlers/review.py` / `_wrap_parallel_review_worker` | Raw output, timing, cost, tokens, `rate_limit` | Rebuilds `WorkerResult` around merged review payload | No; aggregate already done in parallel review | No |
| `megaplan/handlers/review.py` / `handle_review` | Payload, review evidence, receipt/history fields | May use wrapper above | No | No |
| `megaplan/handlers/gate.py` / `_merge_gate_worker_attempt` | Payload, raw/trace output, timing, cost, session, tokens, `rate_limit` | Mutates base `WorkerResult` with retry data | Retry merge semantics only | No |
| `megaplan/handlers/gate.py` / `handle_gate` | Payload, gate recommendation, receipt/history fields | May use retry merge above | No | No |
| `megaplan/handlers/finalize.py` / `_validate_finalize_payload`, `handle_finalize` | `worker.payload` and receipt/history fields | Consumer-only | No | No |
| `megaplan/handlers/execute.py` / `handle_execute` | Execute response and worker metrics indirectly through batch execution | Consumer-only wrapper around execute batch flow | No | No |
| `megaplan/execute/batch.py` / `handle_execute_one_batch` receipt wrapper | Execute worker timing, cost, session, trace, tokens, `rate_limit` | Rebuilds receipt `WorkerResult` one-to-one for aggregate execution receipt | No | No |
| `megaplan/execute/batch.py` / `handle_execute_auto_loop` aggregate receipt worker | Per-batch worker timing, cost, session, trace, tokens, `rate_limit` | Builds aggregate receipt `WorkerResult` | Yes, sums metrics and preserves all non-`None` `rate_limit` values | No |
| `megaplan/execute/timeout.py` / timeout receipt worker | Timeout recovery payload and synthetic timing/cost fields | Constructs timeout `WorkerResult`; `rate_limit` defaults to `None` | No | No |
| `megaplan/orchestration/prep_research.py` / fan-out parse | `WorkerUnitResult` payload, duration, `rate_limit` | Stores `rate_limit` in side-result metrics | Per-unit side-result collection | No |
| `megaplan/orchestration/prep_research.py` / no-areas triage skip | Triage worker raw output, timing, cost, session, trace, prompt, model, tokens, `rate_limit` | Rebuilds `WorkerResult` one-to-one | No | No |
| `megaplan/orchestration/prep_research.py` / final triage/fan-out/distill worker | Triage, fan-out, and distill timing, cost, tokens, session, trace, prompt, model, `rate_limit` | Builds aggregate `WorkerResult` | Yes, preserves triage, fan-out side-result, and distill non-`None` values | No |
| `megaplan/orchestration/parallel_critique.py` / parallel critique aggregate | Per-unit payloads, timing, cost, tokens, `rate_limit` | Builds aggregate `WorkerResult` | Yes, preserves all non-`None` unit values | No |
| `megaplan/review/parallel.py` / parallel review aggregate | Per-check/per-criterion payloads, timing, cost, tokens, `rate_limit` | Builds aggregate `WorkerResult` | Yes, preserves all non-`None` unit values | No |
| `megaplan/receipts/__init__.py` / receipt rendering | Worker cost, duration, tokens, session, model, `shannon_plan` | Consumer-only | No | Persists `shannon_plan` as opaque metadata; does not persist top-level `rate_limit` |
| `megaplan/observability/cost.py` / `_classify_vendor`, `_aggregate` | Event model strings, cost, request IDs, token counts | Consumer-only | Aggregates cost/tokens, not worker results | Vendor-aware for reporting only |
| `megaplan/agent/environments/agent_loop.py` / agent loop returns | Messages and loop state | Returns runtime-loop `AgentResult`, not worker contract `AgentResult` | No | No |
| `megaplan/handlers/tiebreaker.py` / tiebreaker run/decide | Gate artifact fields and tiebreaker response state | Consumer-only; no `WorkerResult` rebuild | No | No |

## Audit closure

The fields that can be silently lost are covered at the transform boundaries:
dataclass projections, critique recovery, review wrapping, gate retry merge,
execute receipt rebuilds, prep research rebuilds, parallel critique, and parallel
review.  The remaining sites either construct native worker results with
`rate_limit=None`, read `worker.payload` for phase logic, or render existing
receipt/cost metadata without changing the `WorkerResult` contract.
