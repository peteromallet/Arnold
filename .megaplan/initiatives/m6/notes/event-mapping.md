# M6 T15 — EventKind → Store routing

Status: implemented for T15. T16 will replace the temporary legacy
`events.ndjson` telemetry mirror with a projection layer.

## Scope

Map every `EventKind` (megaplan/observability/events.py:100, currently 30 kinds
— note: T15's brief says "27", but the live enum is 30 after M5-cal additions
[`CAPABILITY_CLAIM`, `CALIBRATION_EXPERIMENT`] and the `STATE_CACHE_DRIFT` /
`ACTIVATION_TRANSITIONED` additions; we map all 30) to:

1. Which `Store` method it routes through:
   - `record_epic_event`  — durable, replayable, attributable plan-level events
   - `append_progress_event` — narrative/UI progress fan-out
   - `log_system_event`   — diagnostic, low-stakes
   - `append_telemetry_event` (NEW, see "Protocol extension")
     — fast-rate, non-attributable telemetry that does not fit the above
2. Required envelope fields beyond the base (`kind`, `ts`, `plan_id`, `seq`).
3. How `transaction_id` is derived for subprocess-emitted events
   (provenance hash of `plan_id + phase + seq`).

## Routing table

| EventKind | Method | Required payload fields | Notes |
| --- | --- | --- | --- |
| INIT | record_epic_event | plan_name, idea, config | once per plan |
| PHASE_START | record_epic_event | phase, robustness | one per phase entry |
| PHASE_END | record_epic_event | phase, status, duration_ms | one per phase exit |
| PHASE_RETRY | record_epic_event | phase, attempt, reason | |
| STATE_TRANSITION | record_epic_event | from, to, condition | drives WAL fold |
| STATE_WRITTEN | record_epic_event | snapshot_hash | mtime-debounced |
| LOCK_ACQUIRED | log_system_event | lock_name, holder | |
| LOCK_RELEASED | log_system_event | lock_name | |
| PLAN_ABORTED | record_epic_event | reason | terminal |
| PLAN_FINISHED | record_epic_event | status | terminal |
| SUBPROCESS_SPAWNED | append_telemetry_event | argv, pid, phase | high-rate |
| SUBPROCESS_EXITED | append_telemetry_event | pid, exit_code, duration_ms | |
| SUBPROCESS_SIGNALED | append_telemetry_event | pid, signal | |
| LLM_CALL_START | append_telemetry_event | model, prompt_hash | high-rate |
| LLM_TOKEN_HEARTBEAT | append_telemetry_event | model, tokens, elapsed | heartbeat |
| LLM_CALL_END | append_telemetry_event | model, tokens_in/out, cost | |
| LLM_CALL_ERROR | append_telemetry_event | model, error_class | |
| ARTIFACT_WRITTEN | record_epic_event | path, hash, role | provenance |
| ARTIFACT_INVALIDATED | record_epic_event | path, reason | |
| OVERRIDE_APPLIED | record_epic_event | override, scope, actor | |
| FLAG_RAISED | record_epic_event | flag, reason | |
| FLAG_RESOLVED | record_epic_event | flag, resolution | |
| NOTE_ADDED | record_epic_event | note, actor | |
| TIER_ESCALATED | record_epic_event | from_tier, to_tier, reason | |
| COST_RECORDED | append_telemetry_event | model, usd, tokens | |
| EVALUAND_RECORDED | record_epic_event | attribution_key, score | M5-eval load-bearing |
| HEALTH_CHECK_FAILED | log_system_event | check, error | |
| DRIFT_DETECTED | log_system_event | what, expected, actual | |
| ACTIVATION_TRANSITIONED | record_epic_event | from, to | M5b |
| STATE_CACHE_DRIFT | record_epic_event | wal_seq, cache_hash | R1 authority |
| CAPABILITY_CLAIM | record_epic_event | claim (full CapabilityClaim) | M5-cal |
| CALIBRATION_EXPERIMENT | record_epic_event | finding (CalibrationExperimentFinding) | M5-cal |

## transaction_id derivation (subprocess-emitted events)

For any event emitted from a subprocess (planning worker, hermes worker,
codex worker), `transaction_id` MUST be set to:

```
transaction_id = sha256(f"{plan_id}::{phase}::{seq}").hexdigest()[:16]
```

`seq` is the per-(plan,phase) monotonic counter the worker already owns
(see EventWriter._next_seq). This is deterministic across restarts as long
as `(plan_id, phase, seq)` is preserved by the WAL — which it is, because
seq is part of the envelope.

In-process emits (main loop, gateway) reuse the same scheme with phase set
to the current PlanState.current_state. Out-of-band emits (CLI tooling,
ad-hoc readers) use `phase="cli"`.

## Protocol extension — `append_telemetry_event`

Add to the `Store` Protocol:

```python
def append_telemetry_event(
    self,
    kind: str,
    payload: Mapping[str, Any],
    *,
    scope: str | None = None,
) -> None: ...
```

Backend obligations:

- File backend (NDJSON): write to `telemetry.ndjson` next to `events.ndjson`,
  fcntl.flock-equivalent per-plan-dir locking, identical envelope shape
  (kind, ts, plan_id, seq, payload, scope) but `attribution_key` MAY be omitted.
- DB backend: same row schema as `epic_events` but with `is_telemetry=true`
  flag and a partial index on `(plan_id, ts)`; serialization via existing
  row-level lock.
- Concurrency: ordering MUST be preserved per-(plan_id, kind). Regression
  test asserts that two writers emitting 100 events each interleave with
  strictly-monotonic seq per writer and no payload tearing.

## Emit-site migration inventory

All sites must route through Store; direct file writes are removed.

1. `megaplan/observability/events.py:294` — `EventWriter.emit()` body;
   route into `record_epic_event` / `append_progress_event` /
   `log_system_event` / `append_telemetry_event` per the table above.
2. `megaplan/observability/events.py:377` — module-level `_get_writer(plan_dir).emit()`
   helper; thin shim, becomes `_get_store(plan_dir).<method>()`.
3. `megaplan/observability/events.py:398, :456` — module-level
   `emit(plan_dir, kind, ...)` and `record_state_written(plan_dir, payload)`;
   re-route via Store.
4. `megaplan/orchestration/progress.py:108` — `ProgressEmitter.emit()` and
   its 9 convenience wrappers (`phase_start` :175, `phase_end` :178,
   `batch_complete` :181, `gate_pending` :184, `gate_resolved` :187,
   `plan_done` :190, `plan_failed` :193, `execution_blocked` :196,
   `manual_fix_attached` :199); all route to `append_progress_event`.
5. Gateway emit sites — enumerate in PR description from
   `grep -rn '\.emit\b' megaplan/_gateway/ megaplan/_pipeline/runtime.py`
   at implementation time; route per the table.

## Concurrency invariant

Per-plan-dir lock (current `EventWriter._lock` via `fcntl.flock`) is preserved
by routing every method through a single `Store` instance that owns the lock.
The DB backend preserves ordering via row-level serialization on
`(plan_id, seq)`.

Regression test (`tests/observability/test_concurrent_telemetry_ordering.py`,
to be authored at implementation time):

- Two worker threads each emit 100 telemetry events with distinct payloads.
- Reader reads back; asserts (a) every event present, (b) per-writer seq
  monotonic, (c) no torn payloads (json.loads succeeds on every line).

## Landed implementation

The contract above is settled and T15 landed the first implementation slice:

1. Added `append_telemetry_event` to the canonical `Store` Protocol in
   `megaplan/store/base.py`, plus FileStore, DBStore, and MultiStore
   implementations.
2. Routed `EventWriter.emit()` through the Store-method routing table by
   stamping each envelope with `store_method`.
3. Wrote telemetry kinds to `telemetry.ndjson` under the existing per-plan-dir
   flock and seq counter. For compatibility, telemetry is mirrored to
   `events.ndjson` until T16 replaces readers with a Store projection.
4. Added deterministic `transaction_id =
   sha256(f"{plan_id}::{phase}::{seq}").hexdigest()[:16]` for emitted events.
5. Added `tests/observability/test_concurrent_telemetry_ordering.py`.

SC11 verify (T11) confirms the M3 topology substrate is sound, so T15's
upstream dependency (topology-projected phase ordering used by transaction_id)
is satisfied by the existing `megaplan/_core/topology.py:Graph` +
`workflow_next`.

## T16 projection contract

`megaplan/observability/events_projection.py` materializes the legacy
`events.ndjson` view from Store reads. The Store Protocol now exposes:

```python
def events_for_plan(plan_id: str) -> Iterator[StoredEvent]: ...
```

`StoredEvent` is the store-neutral read shape for the projection:
`kind`, `phase`, `payload`, optional `occurred_at`, optional backend `id`,
optional `seq`, and optional `source` / store method.

Schema-equivalent projection means the projected `events.ndjson` and the
recorded reference stream have the same ordered `(kind, phase, payload)`
triples. `seq`, DB-generated ids, `transaction_id`, and ISO timestamps may
differ across backends, but the projection must be deterministic for the same
input Store event stream. Field ordering is normalized with the single
`_canonical_dumps` helper in `events_projection.py`; parity tests import that
helper instead of defining a second serializer.

Lazy materialization rule: on plan-dir load, `PlanRepository.from_plan_dir()`
calls `ensure_events_projection()` when a Store is supplied and no
`events.ndjson` exists. The legacy readers in `observability/events.py` and
`observability/fold.py` also call the same helper before reading, so
`fold.py`, `cost.py`, `trace.py`, and `events.py` keep consuming the
traditional file path while the canonical source moves behind Store reads.
