# Event Journal Specification

The manifest runtime is event-sourced.  Every state change is appended to an
append-only NDJSON journal maintained by `arnold.kernel.journal.NDJsonEventJournal`.
The journal is the authoritative runtime state; mutable runner state is derived
from it on every loop iteration via `arnold.execution.routing.project_routing_state`.

## File layout

```
<artifact_root>/
  events.ndjson      # canonical event lines
  .events.seq        # monotonic sequence counter (fcntl-locked)
  .events.init_ts    # first-write timestamp
  .quarantine/
    journal.ndjson   # malformed or mismatched lines
```

Lines are appended atomically with an assigned `sequence` and `occurred_at`
timestamp.  Reads return only valid, consistently-ordered events; divergent
lines are quarantined rather than dropped.

## Line format

Each line is the canonical JSON form of an `arnold.kernel.events.EventEnvelope`:

```json
{"artifact_root":"/path/to/root","event_id":"run:...:kind:N","family":"node-lifecycle","kind":"node_completed","manifest":{"alias":"...","manifest_hash":"sha256:...","uri":null},"occurred_at":"2026-06-22T00:00:00+00:00","payload":{"node_ref":"...","attempt":1,"iteration":1,"outputs":{}},"payload_schema_hash":"sha256:...","replay":{"cursor":null,"journal_uri":"/path/to/root/events.ndjson","sequence":42},"reentry_id":null,"scope_stack":[],"sequence":42}
```

Canonical JSON rules (see `canonical_json`):

- UTF-8, no trailing newline in the encoded object.
- Keys sorted lexicographically.
- No insignificant whitespace (`separators=(",", ":")`).
- Tuples become JSON arrays.
- `StrEnum` values use their string value.

## Required envelope fields

| Field | Source | Purpose |
|-------|--------|---------|
| `event_id` | `LocalJournalBackend._append` | Unique per run: `run:<run_id>:<kind>:<counter>` |
| `family` | `EventFamily` | Grouping: `control-transition`, `effect`, `suspension`, `artifact`, `node-lifecycle` |
| `kind` | backend/executor | Specific event type (see below) |
| `manifest.alias` | `WorkflowManifest.id` | Human workflow alias |
| `manifest.manifest_hash` | `WorkflowManifest.manifest_hash` | Runtime discriminator for replay/quarantine |
| `run_id` | backend | Unique run identifier |
| `payload_schema_hash` | manifest hash | Schema contract for payload validation |
| `sequence` | journal | Monotonic, gap-free integer assigned at append |
| `scope_stack` | backend | Subpipeline scope hash chain |
| `reentry_id` | cursor / backend | Resume/suspension correlation |
| `artifact_root` | backend | Filesystem root for artifacts and journal |
| `idempotency_key` | effect/budget | Idempotency boundary for effects and reservations |
| `replay` | journal | `ReplayReference(journal_uri, sequence)` for lineage |

## Required event types

### Lifecycle

- `manifest_loaded` — emitted at start of `run_manifest`.
- `manifest_validated` — emitted after lineage checks.
- `node_started` — before a `RouteCoordinate` executes.
- `node_completed` — when a coordinate finishes successfully.
- `node_failed` — when a coordinate fails.
- `node_suspended` — when a coordinate returns `NodeState.SUSPENDED`.
- `node_resumed` — when a run resumes from a cursor.
- `node_cancelled` — when a coordinate returns `NodeState.CANCELLED`.
- `node_timeout` — when elapsed time exceeds `TimingPolicy.timeout_seconds`.
- `branch_selected` — records the chosen edge after a branch node.
- `loop_iteration` — records each loop controller iteration.
- `reducer_completed` — fanout reducer finished.
- `subpipeline_entered` / `subpipeline_exited` — child scope boundaries.

### Budget

- `budget_reserved` — reservation before node execution.
- `budget_settled` — actual cost after successful execution.
- `budget_released` — reservation released on failure/suspension/cancellation.

### Effects

- `effect_intent` — idempotent intent recorded before execution.
- `effect_fulfillment` — successful effect result.
- `effect_failure` — effect raised an exception.
- `effect_rejected` — idempotency policy violation.

### Control transitions

- `control_transition` — generic transition event; `payload.kind` distinguishes
  `override`, `fallback`, `escalation`, `supervisor_promotion`, and `overlay`.
- `escalation_routed` — retry/escalation path taken.

### Compensation

- `compensation_started`
- `compensation_step_completed`
- `compensation_step_failed`
- `compensation_completed`

### Suspension / resume gates

- `resume_rejected` — authority-gated resume denied.

### Terminal

- `run_completed`
- `run_failed`
- `run_suspended`
- `run_cancelled`

### Deadline / TTL

- `ttl_expired` — manifest-level `TimingPolicy.ttl_seconds` exceeded.
- `manifest_deadline` — manifest-level `TimingPolicy.deadline_ref` exceeded.

## Replay and quarantine

`validate_event_envelope` enforces required fields.  Reads additionally reject:

- Malformed JSON or missing fields.
- `manifest_hash` or `artifact_root` diverging from the first valid event.
- Non-monotonic `sequence` values.

Mismatched lines are wrapped in `JournalQuarantineRecord` and persisted to
`.quarantine/journal.ndjson` by `NDJsonEventJournal.quarantine`.
