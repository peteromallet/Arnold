I have all the data. Here's the tight verdict:

---

## Verdict: YES — unpinned event schema is a real, medium-severity risk. Two parallel event systems exist; m4 makes emission a cross-tool contract.

### 1. Writers & readers of `events.ndjson`

**Writers** (all use `events.py:emit` or `EventWriter.emit`):
- `auto.py` (inferred — emits INIT, PHASE_START/END, STATE_TRANSITION, LLM_CALL_*, etc. from the driver loop)
- `handlers/override.py:159–881` — OVERRIDE_APPLIED, NOTE_ADDED (7 call sites)
- `handlers/gate.py:568–570` — FLAG_RAISED, FLAG_RESOLVED
- `events.py:369–415` — `spawned()` context manager (SUBPROCESS_SPAWNED/EXITED)
- CLI `_handle_record_tag` (`cli/__init__.py:997–1011`) — NOTE_ADDED

**Readers** (all via `events.py:read_events`):
- `trace.py:102–135` — `format_json/pretty/narrative`, all 25 event kinds parsed via `_kind_label()` and `format_narrative()` switch
- `cost.py:95–155` — reads COST_RECORDED + LLM_CALL_END, extracts `cost_usd`, `model`, `tokens_in/out` from payload
- `introspect.py:22` — reads events for liveness, drift, phase state
- `doctor.py:28` — reads events for stale-lock, timeout, cost trajectory checks
- `cloud/supervise.py` — remote status pipeline (reads status JSON which embeds event-derived data)

**Schema versioning**: **None.** The envelope (`seq`, `ts_utc`, `ts_rel_init_s`, `kind`, `phase`, `payload`) is defined only in `events.py:173–180` as an ad-hoc dict. The `docs/events.md:1` says "Status: Locked (2026-05-18)" but this is documentation convention, not a machine-enforced contract version field. No `schema_version` key exists in the event envelope unlike `status` JSON (which has `resolution_contract` module imports at `status_view.py:52`).

### 2. m4 shared-hook risk

If m4 makes event emission a shared hook (every tool emits into the same `events.ndjson`), the schema **becomes** a cross-tool contract. Currently, `trace.py`'s `format_narrative()` (`trace.py:176–282`) has per-kind switch branches that **hardcode payload field names** (`payload.get("model")`, `payload.get("cost_usd")`, etc.). `cost.py:100–128` similarly depends on `payload.model`, `payload.cost_usd`, `payload.tokens_in`, `payload.tokens_out`. If any new emitter changes a payload field name, **readers silently break** — there's no version guard, no schema validation, and `read_events()` silently skips JSON decode errors (`events.py:323–324`). This is the classic unpinned-contract failure mode that `status` JSON already protects against via `resolution_contract`.

### 3. Two parallel event systems: YES, they conflict

| System | Schema | Storage | Kind Taxonomy | Ownership |
|---|---|---|---|---|
| **events.ndjson** (`events.py`) | Ad-hoc dict, 25 string-literal kinds | File per plan dir | `init`, `phase_start`, `llm_call_end`, `cost_recorded`, etc. | Observability layer (m1) |
| **Store EpicEvent** (`store/base.py:443–474`) | Pydantic `EpicEvent`, `ProgressEvent`, `SystemLog` | Store backend (file/DB/multi) | `event_type: EpicEventType`, `kind: ProgressEventKind` | Arnold's event-sourcing model (m2) |

These are **independent, unconnected systems**:
- `events.ndjson` events have a `seq` counter, run-relative timestamps, no `epic_id` or `transaction_id`  
- Store `EpicEvent` has `epic_id`, `transaction_id`, pre/post state hashes, `idempotency_key` — full event-sourcing semantics  
- `ProgressEmitter` (`orchestration/progress.py:139–169`) writes `ProgressEvent` to the **Store**, not to `events.ndjson`  
- There is NO bridge: nothing reads `events.ndjson` and replays into the Store, or vice versa

A shared substrate would need to **reconcile** these: either unify on one envelope (likely Store-backed, with ndjson as a file-sidecar mirror) or define a formal bridge with translation rules. The naming collision alone is dangerous — both systems have a `phase_start` kind but with different payloads.

### 4. Concrete plan change

**What to pin**: The events.ndjson envelope + all 25 payload schemas must become a versioned, validated contract. Add a `"schema_version": 1` field to every event (`events.py:173`), add per-kind payload validation on emit, and add a `check_events_schema` to `doctor.py`.

**Milestone ownership**: **m4 (shared substrate)** — because that's when the contract becomes cross-tool. m1 already documents the 25 kinds (`docs/events.md`) but without machine enforcement. m4 should:
1. Extract event schemas into `schemas/observability.py` as Pydantic models (mirroring `schemas/arnold.py:239-253 EpicEvent`)
2. Make `EventWriter.emit()` validate payloads against kind-specific schemas
3. Define the bridge: `EpicEvent` ↔ ndjson event mapping rules (or decide to merge)
4. Add `schema_version` to the envelope so readers can version-gate

**Severity**: Medium. Current readers are fragile to payload drift but the blast radius is limited to 4 CLI commands. The bigger long-term risk is the **duplicate event system** creating maintenance debt and confusion for anyone adding new event sources in m4+.