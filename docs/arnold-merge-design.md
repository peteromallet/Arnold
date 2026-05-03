# Arnold ↔ Megaplan Merge Design

**Status:** Approved direction. Source of truth for Sprints 0–7.
**Audience:** Each chained megaplan reads this before planning. Don't redo the design — implement it.
**Revision:** v2 — incorporates findings from four codex audit agents (plan schema, store interface, adversarial edge cases, end-to-end journeys).

---

## Goal

Merge Arnold (Supabase-backed Discord planning bot) and megaplan (file-backed CLI plan-execution tool) into a single system where:

- Arnold's epic schema and editorial logic live inside megaplan as library code.
- Megaplan supports two interchangeable storage backends — `FileStore` and `DBStore` — as **first-class peers**.
- Each epic chooses its `home_backend` (file or db); both backends are full implementations of the same `Store` contract.
- Discord becomes a Discord-specific *adapter* layer on top of megaplan, not a parallel system.
- Existing megaplan plans (no parent epic) continue to work unchanged.
- The system survives concurrent edits, crash mid-transaction, mid-promote container death, and similar real-world failure modes — designed in, not retrofitted.

## Non-goals

- Don't invent new top-level abstractions (`WorkItem`, `RunGraph`, fresh `Epic` shape). Use Arnold's schema verbatim.
- Don't port Arnold's Discord runtime (`agent_kit/resident.py`). It stays Arnold-side.
- Don't build cross-project schedulers, isolation/merge-policy fields, or distributed orchestration beyond megaplan's existing `auto.py` chain.
- Don't promise feature parity for things that physically need multiple machines (real-time multi-user collab, cross-machine bot reactions). Those work on DB-home epics only — by physics.

---

## Current state

**Arnold** (`/Users/peteromalley/Documents/arnold-v2/`):
- Discord bot, multi-user, conversational.
- Storage: Supabase Postgres + Supabase Storage for blobs.
- Schema: 16 tables. See `supabase/migrations/`.
- Editorial logic: `agent_kit/{gating.py, tools/editorial.py, tools/editorial_reads.py, tools/images.py, store/supabase.py}`.
- Discord runtime: `agent_kit/resident.py` (NOT being ported).

**Megaplan** (`/Users/peteromalley/Documents/megaplan/`):
- CLI for plan execution: prep → plan → critique → gate → execute → review.
- Storage: filesystem at `<work-dir>/.megaplan/plans/<plan-id>/...`.
- Cloud worker on Railway (working today with `MEGAPLAN_TRUSTED_CONTAINER=1`).
- Today's plans are unparented (no epic).
- 335 filesystem touch points across 45 files; concentrated in `workers.py` (98), `_core/state.py` (51), `cli.py` (38). Some abstraction already exists in `_core/io.py` (`atomic_write_json`, `read_json`).

**Megaplan plans are filesystem trees, not single records.** Per plan: `state.json` (hot mutable), `plan_v{N}.md` + `.meta.json`, `critique_v{N}.json`, `gate_v{N}.json`, `gate_signals_v{N}.json`, `execution_batch_{N}.json`, `step_receipt_{phase}_v{N}.json`, `finalize.json`, `finalize_snapshot.json`, `final.md`, `execution_audit.json`, `execution_checkpoint.json`, `execution_trace.jsonl`, `faults.json`, `review.json`, `prep.json`, `research.json`, plus `.plan.lock`. ~32 distinct artifact types across 20 static names + 12 dynamic patterns. **Critically, `auto.py:197, 223, 685` reads several of these directly in tight loops to drive execute-phase decisions** — any "Plan as DB row, persisted at phase end" model breaks the auto-driver.

---

## Target architecture: sibling backends

### Per-epic `home_backend`

Every epic carries `home_backend ∈ {file, db}`. Exactly one backend is authoritative for an epic at any time. Both backends fully implement the `Store` contract.

- Local-only / scratch / single-user → `home_backend=file`.
- Collaborative / Discord-accessible / cloud-executable → `home_backend=db`.
- Move via explicit `migrate(epic, to=db|file)` — not implicit.

### Why per-epic ownership matters

- **Split-brain impossible:** only one backend authoritative per epic.
- **Cloud worker durability:** Railway operates exclusively on `db`-home epics. "FileStore on Railway" is not a supported pair, by design.
- **Cross-machine collaboration:** physically only works on `db`-home (a file on your laptop is invisible to a bot on Railway).
- **Worktree state:** lives at `~/.megaplan/<repo-id>/...`, not in cwd or worktree. Backend-stable.

### What runs identically on both

Editorial / planning / execution logic: epic CRUD, body editor, gating, lockdown scan, sprint queue, plan lifecycle (file-tree-shaped), revert, second opinions, image attach/render, search, code artifacts, feedback. All goes through `Store`.

### What's DB-only by physics, not by feature parity

Multi-user real-time collaboration; Discord bot live reactions; cross-machine read access; per-user RLS. None are file-backend gaps — they're features of having multiple machines.

---

## Schema: 1:1 mirror of Arnold + targeted extensions

Pydantic models in `megaplan/schemas/` mirror Arnold's Supabase tables exactly. Reference: `/Users/peteromalley/Documents/arnold-v2/supabase/migrations/`.

### Arnold tables to mirror (Pydantic + DB)

`epics`, `sprints`, `sprint_items`, `checklist_items`, `epic_events`, `images`, `feedback`, `code_artifacts`, `second_opinions`, `messages`, `bot_turns`, `tool_calls`, `system_logs`, `epic_locks`, `external_requests`, `codebases` — all per migration files.

### New fields on existing tables

**`epics.home_backend: Literal["file", "db"]`** — new column + Pydantic field. Defaults to current backend at creation.

**`sprints.status` enum extends to:** `proposed`, `queued`, `pending`, `running`, `done`, `failed`, `blocked`, `cancelled`. Arnold's existing 4 statuses are insufficient — real plan runs need `running/failed/blocked` (per audit D).

### New tables

**`migration_runs`** — durable state for promote/demote crash recovery (per audit C):

```
migration_runs {
  id: text (PK)
  epic_id: text (FK)
  source_backend: enum(file, db)
  target_backend: enum(file, db)
  phase: enum(planning, copying_meta, copying_blobs, verifying, cutting_over, tombstoning, complete, aborted)
  manifest: jsonb           # entities + checksums to copy
  copied_ids: jsonb         # {table: [ids]} of what's been copied
  blob_copy_progress: jsonb # {blob_id: state}
  started_at: timestamptz
  updated_at: timestamptz
  completed_at: timestamptz | null
  holder_id: text           # actor running the migration
  expires_at: timestamptz   # heartbeat-based; reclaimable
}
```

**`execution_leases`** — Store-level lease that cloud + local can both see (replaces local-only `fcntl` on `.plan.lock`):

```
execution_leases {
  plan_id: text (PK)
  epic_id: text | null (FK)
  holder_id: text
  phase: text
  worker_kind: enum(local_cli, cloud_worker, auto_driver)
  acquired_at: timestamptz
  heartbeat_at: timestamptz
  expires_at: timestamptz
}
```

**`plan_artifacts`** — see Plan + PlanArtifact section below. New table; supersedes filesystem-only plan trees in DB mode (file mode keeps the tree alongside).

**`control_messages`** + **`progress_events`** — see Discord Control Plane section.

**`automation_actors`** — see Identity Model section.

### Schema-level resolutions to known gremlins

- **`images.epic_id ON DELETE SET NULL`** preserved by storing blobs at `~/.megaplan/<repo-id>/blobs/` (file mode) or Supabase Storage (DB mode), with FK to epic. Deleting an epic dir does not cascade to blobs. Periodic GC sweeps orphans.
- **TIMESTAMPTZ:** always tz-aware, ISO-8601 UTC with `Z` suffix. Canonical JSON for any field that round-trips through JSONB.
- **JSONB defaults `[]`/`{}`:** Pydantic models normalize missing/null on serialization both ways.

---

## File layout (FileStore)

```
~/.megaplan/<repo-id>/
├── epics/
│   └── <epic-id>/
│       ├── epic.json              # Epic row + home_backend + revision
│       ├── body.md                # body content
│       ├── checklist.json         # array of ChecklistItem
│       ├── events.jsonl           # transaction-framed, append-only
│       ├── feedback.jsonl
│       ├── messages.jsonl
│       ├── second_opinions/
│       │   └── <id>.json
│       ├── code_artifacts/
│       │   └── <id>.json
│       ├── sprints/
│       │   └── <sprint-id>/
│       │       ├── sprint.json
│       │       ├── items.json
│       │       └── plans/
│       │           └── <plan-id>/    # plan tree per existing layout
│       │               ├── state.json, plan_v1.md, finalize.json, ...
│       │               └── .plan.lock
│       └── _journal/
│           ├── tx-<tx-id>.prepare.json   # active prepares
│           └── tx-<tx-id>.commit         # marker: prepare promoted to commit
├── blobs/
│   └── <blob-id>/
│       ├── meta.json
│       └── data.<ext>
├── orphan_plans/
│   └── <plan-id>/                # legacy plans without parent epic
├── migrations/
│   └── <migration-id>.json       # migration_runs equivalent
├── leases/
│   └── <plan-id>.json            # execution_leases equivalent
├── _index/
│   ├── queue.json                # derived: ready sprints across epics
│   └── schema_version
└── .lock                         # global advisory (rare uses)
```

---

## FileStore atomicity rules (rewritten — proper journal)

The previous "lock + temp-write + rename + append-event" design has a crash window between rename and event-append. Fixed via prepare/commit journal:

### Multi-entity transaction protocol

```
1. Acquire flock(epics/<id>/.lock) — TTL 60s with heartbeat.
2. Read current revisions of all entities being mutated.
3. Validate expected_revision matches each.
4. Write _journal/tx-<tx-id>.prepare.json — contains:
   - intended writes (path, new content, prior content hash)
   - intended event records
   - expected revisions
5. fsync the prepare file.
6. Write all temp files for entity changes.
7. fsync each.
8. Write _journal/tx-<tx-id>.commit (empty marker file).
9. fsync the directory containing the commit marker.
10. Atomic-rename temp files into place (in dependency order).
11. Append event records to events.jsonl with same tx-id.
12. Delete _journal/tx-<tx-id>.prepare.json and .commit.
13. Release flock.
```

### Recovery on FileStore open

```
For each epics/<id>/_journal/tx-*.commit found:
  - The transaction was committed. Replay any unfinished renames + event appends from prepare.json.
For each prepare.json without a matching commit marker:
  - The transaction was not committed. Discard temp files, delete prepare.json.
```

### JSONL event log (transaction-framed)

Per audit C: per-record framing isn't enough. Logical transactions are 1+ events — partial-write of N-of-M events corrupts logical state. Solution:

- Each event line is `<u32 length><json bytes>\n` with `tx_id` field.
- Logical transaction begins with `{tx_id, event_type: "_tx_begin"}` and ends with `{tx_id, event_type: "_tx_commit"}`.
- Tolerant scanner: events with `tx_id` lacking matching `_tx_commit` are ignored (treated as in-flight).
- Max event size: 1 MB. One write syscall per event. fsync after each `_tx_commit`.

### Blob writes

Stage to `blobs/<id>/data.staging`, fsync, write `meta.json`, fsync, atomic-rename staging → `data.<ext>`. Startup scrubber removes `*.staging` older than 1 hour.

### Queue position uniqueness

`set_sprint_queue(epic_id, ordered_sprint_ids, pending)` is the only method that mutates `queue_position`. Reads + rewrites all queued sprints under one epic lock, validates uniqueness, atomically applies. Individual `update_sprint(queue_position=...)` is forbidden.

### Cross-process safety

`flock` releases on process death — that's correct behavior. Crash recovery on the next open detects in-flight prepares and aborts them. Multiple readers OK; only one writer at a time per epic.

---

## Store interface (refined per audit B)

`megaplan/store/base.py` defines the contract. Both `FileStore` and `DBStore` implement it. `MultiStore` routes by `home_backend`.

```python
class Store(Protocol):

    # ---------- Transaction ----------
    @contextmanager
    def transaction(self, epic_id: str | None = None) -> Iterator[Transaction]: ...
    # epic_id may be None — create_epic starts a transaction before the epic exists.

    # ---------- Epic ----------
    def create_epic(self, *, title: str, goal: str, body: str,
                    state: str = "shaping",
                    home_backend: Backend = "file") -> Epic: ...
    def load_epic(self, epic_id: str) -> Epic | None: ...
    def update_epic(self, epic_id: str, *,
                    expected_revision: int | None = None,
                    **changes: Any) -> Epic: ...
    def list_epics(self, *, active_only: bool = True, limit: int = 50,
                   home_backend: Backend | None = None) -> list[EpicSummary]: ...
    def search_epics(self, *, query: str, active_only: bool = True,
                     limit: int = 20) -> list[EpicSummary]: ...

    # ---------- Body ----------
    # body lives on Epic in DB mode (text col) or body.md in file mode.
    def load_body(self, epic_id: str) -> str: ...
    def update_body(self, epic_id: str, body: str, *,
                    expected_revision: int) -> Epic: ...

    # ---------- Checklist ----------
    def list_checklist_items(self, epic_id: str, *,
                             status: str | None = None) -> list[ChecklistItem]: ...
    def add_checklist_items(self, epic_id: str,
                            items: Sequence[ChecklistItemInput]) -> list[ChecklistItem]: ...
    def update_checklist_item(self, item_id: str, **changes: Any) -> ChecklistItem: ...
    def delete_checklist_items(self, item_ids: Sequence[str]) -> None: ...
    def replace_checklist(self, epic_id: str,
                          items: Sequence[ChecklistItemInput]) -> list[ChecklistItem]: ...

    # ---------- Sprints ----------
    def create_sprint(self, *, epic_id: str, sprint_number: int,
                      name: str, goal: str, **fields: Any) -> Sprint: ...
    def load_sprint(self, sprint_id: str) -> Sprint | None: ...
    def list_sprints(self, epic_id: str, *,
                     status: str | None = None) -> list[Sprint]: ...
    def list_sprints_with_items(self, epic_id: str) -> list[SprintWithItems]: ...
    def update_sprint(self, sprint_id: str, *,
                      expected_revision: int | None = None,
                      **changes: Any) -> Sprint: ...
    def delete_sprint(self, sprint_id: str) -> None: ...
    def replace_sprint_items(self, sprint_id: str,
                             items: Sequence[SprintItemInput]) -> list[SprintItem]: ...
    def set_sprint_queue(self, epic_id: str,
                         ordered_sprint_ids: Sequence[str],
                         pending: Mapping[str, str]) -> list[Sprint]: ...

    # ---------- Events ----------
    def record_epic_event(self, *, epic_id: str, transaction_id: str,
                          event_type: str, summary: str,
                          prior_state: dict | None,
                          turn_id: str | None) -> EpicEvent: ...
    def list_epic_events(self, epic_id: str, *,
                         since: str | None = None, until: str | None = None,
                         kinds: Sequence[str] | None = None,
                         limit: int | None = None) -> list[EpicEvent]: ...
    def latest_transaction_id(self, epic_id: str) -> str | None: ...
    def events_by_transaction(self, transaction_id: str) -> list[EpicEvent]: ...

    # ---------- Messages / turns ----------
    def create_message(self, **fields: Any) -> Message: ...
    def update_message(self, message_id: str, **changes: Any) -> Message: ...
    def create_turn(self, **fields: Any) -> BotTurn: ...
    def update_turn(self, turn_id: str, **changes: Any) -> BotTurn: ...
    def list_recent_turns(self, *, n: int = 10,
                          epic_id: str | None = None) -> list[BotTurn]: ...
    def search_messages(self, *, query: str, epic_id: str | None = None,
                        limit: int = 20) -> list[MessageSearchHit]: ...
    def search_tool_calls_by(self, **filters: Any) -> list[ToolCall]: ...

    # ---------- Hot context (joined read for editorial) ----------
    def load_hot_context(self, epic_id: str | None) -> HotContext: ...
    # Returns: epic + recent messages + recent tool calls + feedback + sprints +
    # codebases + code_artifacts + images + second_opinions. One round trip in DB,
    # bundled reads in file mode.

    # ---------- Images ----------
    def create_image(self, **fields: Any) -> Image: ...
    def load_image(self, image_id: str) -> Image | None: ...
    def list_images(self, *, epic_id: str, source: str | None = None,
                    active: bool | None = True) -> list[Image]: ...
    def update_image(self, image_id: str, **changes: Any) -> Image: ...
    def load_active_image_by_reference(self, epic_id: str,
                                       reference_key: str) -> Image | None: ...
    def active_image_reference_exists(self, epic_id: str,
                                      reference_key: str) -> bool: ...
    def deactivate_active_image_reference(self, epic_id: str,
                                          reference_key: str) -> list[Image]: ...

    # ---------- Plan + PlanArtifact ----------
    def create_plan(self, *, sprint_id: str | None, epic_id: str | None,
                    name: str, idea: str, **fields: Any) -> Plan: ...
    def load_plan(self, plan_id: str) -> Plan | None: ...
    def update_plan(self, plan_id: str, *,
                    expected_revision: int | None = None,
                    **changes: Any) -> Plan: ...
    def list_plans(self, *, sprint_id: str | None = None,
                   epic_id: str | None = None,
                   include_orphans: bool = False) -> list[Plan]: ...
    def read_plan_artifact(self, plan_id: str, name: str) -> bytes | None: ...
    def write_plan_artifact(self, plan_id: str, name: str, data: bytes,
                            *, expected_revision: int | None = None) -> ArtifactRef: ...
    def list_plan_artifacts(self, plan_id: str) -> list[ArtifactRef]: ...
    def stat_plan_artifact(self, plan_id: str,
                           name: str) -> ArtifactStat | None: ...

    # ---------- Execution leases ----------
    def acquire_execution_lease(self, plan_id: str, holder_id: str,
                                worker_kind: str, ttl_seconds: int) -> Lease: ...
    def heartbeat_lease(self, plan_id: str, holder_id: str) -> Lease: ...
    def release_lease(self, plan_id: str, holder_id: str) -> None: ...
    def get_active_lease(self, plan_id: str) -> Lease | None: ...

    # ---------- Locks (epic-level, separate from execution leases) ----------
    def acquire_lock(self, epic_id: str, holder_id: str,
                     ttl_seconds: int) -> EpicLock: ...
    def release_lock(self, epic_id: str, holder_id: str) -> None: ...

    # ---------- Control plane (Discord ↔ megaplan) ----------
    def put_control_message(self, msg: ControlMessageInput) -> ControlMessage: ...
    def claim_pending_control_messages(self, *, processor_id: str,
                                       max: int = 10) -> list[ControlMessage]: ...
    def mark_control_message_processed(self, msg_id: str,
                                       result: dict) -> None: ...
    def append_progress_event(self, event: ProgressEventInput) -> ProgressEvent: ...
    def list_progress_events(self, *, plan_id: str | None = None,
                             epic_id: str | None = None,
                             since: datetime | None = None) -> list[ProgressEvent]: ...

    # ---------- Migration (promote/demote) ----------
    # NOT a per-backend method. Lives on MultiStore.

class MultiStore:
    def migrate_epic(self, epic_id: str, *, to: Backend,
                     holder_id: str) -> MigrationRun: ...
    def get_migration_run(self, migration_id: str) -> MigrationRun | None: ...
    def resume_migration(self, migration_id: str) -> MigrationRun: ...
```

`BlobStore` is a separate contract:

```python
class BlobStore(Protocol):
    def put(self, blob_id: str, content: bytes, *,
            content_type: str) -> BlobRef: ...
    def get(self, blob_id: str) -> bytes: ...
    def url(self, blob_id: str, *, signed: bool = False,
            ttl: int = 3600) -> str: ...
    def delete(self, blob_id: str) -> None: ...
    def stat(self, blob_id: str) -> BlobStat | None: ...
```

`LocalDirBlobStore` (file mode) and `SupabaseStorageBlobStore` (db mode).

### `expected_revision` semantics with idempotency

Per audit C: blind retry on `RevisionConflict` can duplicate operations. Resolution:

- Every `Epic`, `Sprint`, `Plan`, etc. carries a monotonic `revision`.
- `update_*` accepts `expected_revision`; mismatch raises `RevisionConflict`.
- Mutating operations carry an `idempotency_key` (op-level UUID). Duplicate keys return the prior result, not a new write.
- Retries are operation-level commands, not blind reload-and-rewrite.

---

## Plan + PlanArtifact (per audit A)

The doc previously said "Plan model" without defining it. Megaplan plans are filesystem trees — many artifact files per plan, mutated mid-lifecycle. **`auto.py:197, 223, 685` reads `state.json` and `execution_batch_*.json` directly in tight loops.** A pure DB-row Plan that only persists at phase end breaks the auto-driver.

### Hybrid model

Plan has typed hot fields (state machine, history, current phase) and a list of artifacts (cold storage of phase outputs).

```python
class PlanArtifact(BaseModel):
    name: str                    # e.g. "plan_v3.md", "execution_batch_2.json"
    kind: Literal["markdown", "json", "jsonl", "raw_text", "lock", "derived"]
    role: Literal[
        "plan_version", "plan_meta", "critique", "gate", "gate_signals",
        "finalize", "finalize_snapshot", "execution_batch", "execution",
        "execution_audit", "execution_checkpoint", "execution_trace",
        "faults", "receipt", "review", "raw_worker_output",
        "template", "derived_final", "prep", "research", "directors_notes",
        "human_verifications", "tiebreaker_decisions", "tiebreaker_payload",
    ]
    version: int | None = None
    batch: int | None = None
    phase: str | None = None
    content_text: str | None = None      # for markdown/text kinds
    content_json: dict | list | None = None  # for json/jsonl
    sha256: str
    created_at: datetime
    updated_at: datetime

class Plan(BaseModel):
    id: str
    name: str
    epic_id: str | None = None       # None = orphan plan (legacy megaplan use)
    sprint_id: str | None = None
    revision: int

    # Hot mutable state — read by auto.py mid-loop.
    idea: str
    current_state: str               # plan state machine
    iteration: int
    config: dict[str, Any]
    sessions: dict[str, dict[str, Any]]
    plan_versions: list[dict[str, Any]]
    history: list[dict[str, Any]]
    meta: dict[str, Any]
    last_gate: dict[str, Any]
    active_step: dict[str, Any] | None = None
    latest_finalize: dict[str, Any] | None = None
    latest_review: dict[str, Any] | None = None
    latest_execution: dict[str, Any] | None = None

    # Cold artifacts.
    artifacts: list[PlanArtifact] = []

    created_at: datetime
    updated_at: datetime
```

### PlanRepository adapter

Don't replace 335 file-touch points with `Store` calls directly — too invasive. Instead, introduce `PlanRepository` as a layer between megaplan internals and `Store`:

- File mode: PlanRepository reads/writes the existing tree under `~/.megaplan/<repo-id>/.../plans/<plan-id>/`. Hot fields live in `state.json`. Artifacts are still individual files. Same layout as today.
- DB mode: PlanRepository materializes the file tree into a temp working dir on demand (e.g. `/tmp/megaplan-work/<plan-id>/`), exposes the same paths to workers, syncs back to `Plan` row + `plan_artifacts` table on each phase boundary. Workers never know.

This preserves byte-exact compatibility with the current cloud worker, which writes a real filesystem tree today.

### Hot-state writes

Hot fields on `Plan` (`current_state`, `iteration`, `history`, `last_gate`, etc.) update through typed methods, not artifact writes. `auto.py`'s tight-loop reads of `state.json` become tight-loop reads of `Plan.current_state` + `Plan.latest_execution` (or, in file mode, the same `state.json` it reads today).

---

## DBStore notes

- Wraps Arnold's existing Supabase queries; reuse patterns from `arnold-v2/agent_kit/store/supabase.py` rather than reinventing.
- `expected_revision` enforced via `UPDATE ... WHERE id = ? AND revision = ? RETURNING revision+1`.
- `acquire_lock` and `acquire_execution_lease` use the new tables with TTL + heartbeat.
- `transaction()` maps to a Postgres transaction; `epic_id=None` is a no-op scope (transaction still atomic).
- All writes carry `actor_id` for RLS (see Identity Model).

---

## MultiStore federation

`megaplan/store/multi.py`:

- Routes Store calls by `epic_id → home_backend` lookup. Cache the routing in memory; invalidate on `update_epic(home_backend=...)`.
- `list_epics` queries both backends and merges.
- `migrate_epic(epic_id, to=db|file)` is the public promote/demote API. Internally records a `migration_runs` row, executes the phases below, and is **idempotent + resumable**.
- All clients (CLI, bot, cloud worker) talk to MultiStore, not directly to a backend.

### Migration phases (durable, recoverable)

```
1. planning      — write migration_runs row, build manifest of entities/blobs
2. copying_meta  — copy epic + sprints + checklist + events + feedback + opinions to target
3. copying_blobs — copy each blob; update progress in migration_runs.blob_copy_progress
4. verifying     — re-read source + target; checksum compare; row counts match
5. cutting_over  — set source.home_backend = "<target>" (now target authoritative; source has migrating_to flag)
6. tombstoning   — mark source rows with migrated_to=<migration_id>; remove from list_epics
7. complete      — clear migration_runs.expires_at; mark complete
```

Resume: `resume_migration(migration_id)` reads phase, replays from there. Safe to call repeatedly. Lease expires if holder dies; another actor can claim and continue.

### Pre-migrate checks

Reject migration if:
- An `execution_lease` is active for any plan under the epic (cloud/local plan running).
- The target backend already has an epic with the same id (collision).
- Caller doesn't hold the epic lock (acquired with reasonable TTL).

---

## Identity model

DBStore reads/writes need an actor. CLI and cloud workers don't have a Discord user. Sprint 2 designs:

- New table `automation_actors` `{id, name, granted_epic_ids: jsonb | "*", actor_kind: enum(cli, cloud_worker, ci, admin), created_at, last_active_at}`.
- CLI/cloud workers pass `actor_id` via env/flag (`MEGAPLAN_ACTOR_ID`, `--actor`).
- RLS policies: write allowed if (a) Discord user owns the epic OR (b) `actor.granted_epic_ids` includes the epic id (or is `"*"`).
- Service role exists only for migrations and admin tooling. No code path may use it as default.
- File mode: actor identity is OS-level (whoever runs the CLI). No row-level enforcement.

---

## Editorial logic transplant

### Sprint 4 (pure logic — extended scope per audit B)

Move from `arnold-v2/` to `megaplan/editorial/`, swapping `supabase` calls for `Store` calls:

- `agent_kit/gating.py` → `megaplan/editorial/gating.py` (state machine + transitions)
- `agent_kit/tools/editorial.py`: body editing, section operations → `megaplan/editorial/body.py`
- `agent_kit/tools/editorial.py`: lockdown scan (lines 13–16, 49–79) → `megaplan/editorial/lockdown.py`
- `agent_kit/tools/editorial.py`: checklist operations → `megaplan/editorial/checklist.py`
- `agent_kit/tools/editorial.py`: sprint editing + queue normalization → `megaplan/editorial/sprints.py`
- `agent_kit/tools/editorial_reads.py`: hot-context loader → `megaplan/editorial/reads.py`

These all operate on `Store` (`MultiStore` in practice) and an `actor_id`.

### Sprint 5 (gnarly bits)

- **Revert / get_epic_at_time** (`editorial.py:337`, `editorial_reads.py:319`). Reconstructs from `prior_state` JSONB across grouped events. **Requires `expected_revision`** — can't blindly overwrite a newer state. Canonical JSON serialization (sorted keys, ISO-Z UTC, explicit nulls, stable numeric formatting).
- **Second-opinion runner** (LLM call → score → resulting checklist items, all in one transaction).
- **Image management** (`agent_kit/tools/images.py`): attach, `reference_key` partial uniqueness, inline body refs `![[reference_key]]`, render with both blob backends.
- **Full-text search**: PG `to_tsvector` (DB mode); SQLite FTS5 (file mode); same `Store.search_messages` API. Ranking may differ but top-3 stable.

### Explicitly NOT being ported

- `agent_kit/resident.py` — Discord runtime, message bursts, channel state, mid-turn checks, status edits.
- Bot turn lifecycle wiring (`bot_turns` table is read-only on megaplan side; only Arnold-the-adapter writes).
- Voice transcription, attachment handling, Discord message ID tracking.

---

## Discord control plane

Per audit D: previously the doc had `ControlMessage` + `ProgressEvent` schemas but no Store API to write/read them. Fixed in the refined Store Protocol above.

### ControlMessage

```python
class ControlMessage(BaseModel):
    id: str
    epic_id: str
    actor_id: str                # Discord user or automation actor
    intent: Literal["run_sprint", "pause_plan", "resume_plan",
                    "approve_gate", "reject_gate", "cancel_run",
                    "manual_fix", "request_inspect"]
    target_id: str               # sprint_id, plan_id, gate_id depending on intent
    payload: dict
    idempotency_key: str
    created_at: datetime
    processor_id: str | None     # claimed-by, null if unclaimed
    claimed_at: datetime | None
    processed_at: datetime | None
    result: dict | None
```

### ProgressEvent

```python
class ProgressEvent(BaseModel):
    id: str
    epic_id: str
    plan_id: str | None
    sprint_id: str | None
    kind: Literal["phase_start", "phase_end", "batch_complete",
                  "gate_pending", "gate_resolved", "plan_done", "plan_failed",
                  "execution_blocked", "manual_fix_attached"]
    summary: str
    details: dict                # for plan_failed: blocker info, file:line, etc.
    occurred_at: datetime
```

### Subscription

- DB mode: Arnold subscribes to `progress_events` via Supabase realtime; control_messages via NOTIFY or polling.
- File mode: file watcher on `progress_events.jsonl`. Not exposed to Discord (file-home epics are not Discord-collaborative by design).

---

## Run lifecycle contract (new — per audit D)

Storage parity ≠ workflow continuity. The system needs explicit semantics for failure inspection, manual fixes, and resume.

### Plan states (extended)

`shaping → planning → critiquing → gating → revising → executing → reviewing → done` with off-ramps:
- `failed` — terminal until manual intervention
- `blocked` — auto-driver determined cannot progress without human input (today's `worker_blocked` outcome)
- `paused` — explicitly paused by user
- `cancelled` — terminal, user cancelled

### Failure inspection

When a plan transitions to `failed` or `blocked`:
- `progress_event { kind: "plan_failed" | "execution_blocked", details: { blocker_kind, blocker_message, last_artifact, suggested_action } }`
- Failure record persisted on Plan (`latest_failure: { ... }`) + as a `progress_event`.
- Discord posts the summary with a link to the latest plan version + execution batch.

### Manual fix attachment

User attaches a fix via:
- File mode: drops a file in `epics/<id>/sprints/<id>/plans/<id>/manual_fix.json` and runs `megaplan plan resume <id>`.
- DB mode: `put_control_message(intent="manual_fix", target_id=plan_id, payload={ files: [...], notes: "..." })`. The control processor materializes the fix to the plan's working dir before resume.

### Resume cursor

Plan carries `resume_cursor: { phase, batch_index | null, retry_strategy }`. `resume_plan` intent or CLI `megaplan plan resume <id>` re-enters at the cursor:
- `executing/batch=4` → re-run batch 4 with manual fix incorporated.
- `gating` → re-prompt gate.
- `failed` (no specific cursor) → re-enter from last completed phase.

### Conflict UX (RevisionConflict)

When CLI or bot encounters `RevisionConflict`:
- Reload current state.
- Surface to user: "Your edit was based on revision N; current is M. [reapply | discard | merge interactively]."
- For automation: log as `progress_event { kind: "execution_blocked", details: { reason: "stale_revision" } }`; pause until user resolves.

---

## Offline DB-home epics (new — per audit D Journey 2)

Audit D found: bot user offline cannot read his own DB-home epic. Doc was silent. Stance:

**DB-home epics are online-only by default.** No automatic sync to disk. To work offline:

- `megaplan epic snapshot <id>` writes a read-only snapshot to `~/.megaplan/snapshots/<epic-id>-<timestamp>/`.
- Snapshots are explicitly read-only; cannot be edited and re-uploaded.
- For offline edit-and-resync: use `migrate_epic(<id>, to=file)` to demote, work locally, `migrate_epic(<id>, to=db)` to re-promote when back online. Migration handles conflicts via `RevisionConflict` if the bot edited in the meantime.

This is intentionally unforgiving: full bidirectional offline sync is a CRDT-shaped problem, out of scope.

---

## Per-sprint scope (revised — Sprint 0 added, Sprints 1/4/5 grew to 3 weeks)

### Sprint 0 — Spike (3 days, light)

**Purpose:** validate the refined `Store` Protocol and transaction journal against real call sites before committing to Sprint 1.

**Scope:**
- Implement `Store` Protocol stubs in a throwaway branch.
- Implement transaction journal prepare/commit/recover in `FileStore` (minimal).
- Wire 5 representative `editorial.py` call sites to call the new Store: `create_epic`, `update_body`, `set_sprint_queue`, `add_checklist_items`, `record_epic_event` inside one transaction.
- Inject a crash mid-transaction; verify recover-on-open.
- Round-trip a real `auto.py` plan through `PlanRepository` (file mode), confirm tight-loop reads still work.
- Throw away the branch. Output: a 1-page report of Protocol issues found and changes to fold into Sprint 1.

**Acceptance:** report lands in `docs/sprint-0-spike-report.md`. No production code changes.

---

### Sprint 1 — Foundation: Schema + Store + FileStore + PlanRepository (3 weeks, standard)

**Scope:**
- All Pydantic models per Schema section (16 mirrored Arnold tables + new tables).
- Full `Store` Protocol per the refined definition above.
- `FileStore` with proper transaction journal (prepare/commit/recover), length-prefixed JSONL with `_tx_begin`/`_tx_commit` framing, blob staging.
- `BlobStore` Protocol + `LocalDirBlobStore`.
- `Plan` + `PlanArtifact` Pydantic models.
- `PlanRepository` adapter — file mode reads/writes existing plan tree under `~/.megaplan/<repo-id>/.../plans/<plan-id>/`.
- Refactor megaplan internals (335 touch points across 45 files) to go through `PlanRepository` for plan-tree access and `Store` for everything else. Heaviest in `workers.py`, `_core/state.py`, `cli.py`. **Existing `_core/io.py` already factors atomic writes — extend, don't replace.**
- Existing megaplan plans become orphan plans (`epic_id=None`); `list_plans(include_orphans=True)` returns them.
- `DBStore` skeleton (Protocol satisfied with `NotImplementedError` raises).
- Test fuzz harness in `megaplan/tests/store_contract.py` exercising any `Store`; passes against `FileStore`.

**Acceptance:**
- `pytest --backend file` green.
- `megaplan auto --plan <name>` runs against new code with no behavior change (orphan plan).
- Crash mid-transaction (kill -9 between prepare and commit) recovers cleanly on next open.
- Spike report's findings folded in.

**Out of scope:** DBStore implementation, editorial logic, promote/demote, MultiStore, control plane.

---

### Sprint 2 — DBStore + Identity (2 weeks, standard)

**Scope:**
- `megaplan/store/db.py` full `DBStore` implementation against Arnold's Supabase tables.
- New tables: `automation_actors`, `migration_runs`, `execution_leases`, `plan_artifacts`, `control_messages`, `progress_events`. Migrations in `arnold-v2/supabase/migrations/`.
- Schema extensions: `epics.home_backend`, `sprints.status` enum extension.
- RLS policies allowing actor-scoped writes.
- `MEGAPLAN_ACTOR_ID` env / `--actor` flag. CLI refuses DB writes without an actor.
- `megaplan run --from-arnold-epic <id>` reads (no writes).
- Same fuzz harness passes against `DBStore`.

**Acceptance:**
- `pytest --backend db` green.
- A plan against a DB-home epic completes end-to-end (read-only DB).
- No service-role usage in any non-migration path.

**Out of scope:** writes back to DB, promote/demote, editorial logic, control plane.

---

### Sprint 3 — Promote/Demote + MultiStore (2 weeks, standard)

**Scope:**
- DBStore writes enabled (with `expected_revision`, transactions).
- `MultiStore` in `megaplan/store/multi.py` — routing by `home_backend`.
- `migrate_epic` with all 7 phases (planning → tombstoning → complete), durable `migration_runs`, resumable on holder death.
- Pre-migrate checks (no active execution lease, no collision, holds epic lock).
- `~/.megaplan/<repo-id>/...` becomes canonical FileStore root.
- `megaplan epic snapshot <id>` for offline reads.

**Acceptance:**
- `migrate_epic` round-trips a complete epic (including blobs, all related rows) with byte-equal blob hashes.
- Mid-migration kill + resume produces identical final state.
- Concurrent migrate attempts: second one fails cleanly (lease).
- Fuzz harness on MultiStore with epics in both backends.

**Out of scope:** editorial logic, control plane.

---

### Sprint 4 — Editorial transplant: pure logic (3 weeks, light)

**Scope:**
- Port editorial code per the Editorial Logic Transplant section. All operate on `Store`.
- Includes: gating, body editor, lockdown, checklist (full CRUD), sprints (full CRUD + queue normalization), hot-context loader.
- Run lifecycle contract: plan state machine extension, failure record, resume cursor on Plan.
- Tests cover both backends.

**Acceptance:**
- An epic can be created, body edited, transitioned through full lifecycle, with all gates Arnold enforces today.
- Plan failure records are queryable; `resume_plan` re-enters at cursor.
- `pytest tests/editorial_*.py --backend file` and `--backend db` green.

**Out of scope:** revert, second opinions, images, FTS, control plane.

---

### Sprint 5 — Editorial transplant: gnarly bits (3 weeks, standard)

**Scope:**
- `revert(epic_id, to_transaction_id)` with `expected_revision`, canonical JSON, full prior-state restoration.
- `get_epic_at_time(epic_id, when)`.
- Second-opinion runner.
- Image management with `reference_key` uniqueness, inline body refs, blob backend abstraction.
- Full-text search: PG `tsvector` (DB) + SQLite FTS5 (file).

**Acceptance:**
- Revert round-trips correctly; subsequent edits work; revisions advance.
- Second opinion atomic across `second_opinions` + `checklist_items`.
- Image attached file-mode survives migrate-to-DB and renders identically.
- Search returns ranked results in both backends; top-3 stable.

**Out of scope:** Discord control plane, Arnold gutting.

---

### Sprint 6 — Discord control plane + Arnold gutting (2 weeks, standard)

**Scope:**
- `megaplan/control.py`: control message processor (claims, dispatches, marks processed).
- `megaplan/progress.py`: emitter publishing `progress_events` from plan phase transitions, batch completions, gate-needed signals.
- Arnold gutting: `agent_kit/resident.py` keeps Discord I/O, message bursts, status edits, voice transcription. All editorial calls replaced with `megaplan.editorial.*` imports. Bot polls `control_messages` and subscribes to `progress_events`.
- Arnold's Discord-specific tables (`bot_turns`, `messages.discord_message_id`, `tool_calls`, `system_logs`) stay Arnold-side.

**Acceptance:**
- Discord user can `@arnold run sprint 2` and watch live progress.
- Discord gate approval (reaction or button) writes a `ControlMessage`; plan continues.
- `grep -r "supabase" arnold-v2/agent_kit/tools/editorial*.py` returns nothing.
- Existing Discord conversations on `shaping` epics work end-to-end.

**Out of scope:** anything not listed.

---

### Sprint 7 — Hardening + migration tooling (2 weeks, light, optional)

**Scope:**
- Migration script for existing megaplan local plans → orphan plans in new schema (or attach to a "legacy" epic).
- Backup tooling for FileStore (`megaplan epic export <id>` → tar).
- Operational docs: how to recover from each known failure mode.
- Cloud worker rebuild + smoke-test against new megaplan.

**Acceptance:**
- All existing megaplan plan dirs migrate cleanly.
- One full chain (epic → 3 sprints in cloud) runs end-to-end on the new system.

---

## Sprint sizing summary

| Sprint | Mode | Original | Revised | Reason |
|---|---|---|---|---|
| 0 — Spike | light | — | 3 days | New; derisks Sprint 1. |
| 1 — Foundation | standard | 2 weeks | **3 weeks** | Store Protocol is 3× wider; PlanRepository is genuinely new. |
| 2 — DBStore + Identity | standard | 2 weeks | 2 weeks | Unchanged. |
| 3 — Migrate + MultiStore | standard | 2 weeks | 2 weeks | Mostly unchanged; migration durability adds rigor not scope. |
| 4 — Editorial pure | light | 2 weeks | **3 weeks** | More methods than initially named (joins, sprint CRUD, hot context). |
| 5 — Editorial gnarly | standard | 2 weeks | **3 weeks** | Revert + canonical JSON + image semantics + FTS in both backends. |
| 6 — Discord adapter | light | 2 weeks | 2 weeks | Unchanged. |
| 7 — Hardening | light | — | 2 weeks | Optional; recommended. |

**Total: 17 weeks** (vs original 12). Includes Sprint 0 spike + Sprint 7 hardening.

---

## Gremlins / known landmines

Compiled from prior audits. Each megaplan should be aware of these.

### Concurrency / atomicity

1. **Multi-file transactions need a journal.** Use `Store.transaction()`. The protocol is prepare → stage → commit-marker → atomic-rename → event-append → cleanup. Recovery on next open detects in-flight prepares and aborts them.
2. **JSONL events need transaction framing**, not just per-record framing. Logical transactions begin with `_tx_begin` and end with `_tx_commit`. Tolerant scanner ignores in-flight tx_ids.
3. **Queue reordering** uses `set_sprint_queue` only. Individual `update_sprint(queue_position=...)` is forbidden.
4. **Blob/metadata two-phase failure:** stage blob, fsync, write metadata, atomic-rename. Startup scrubber sweeps `*.staging` >1h old.
5. **`expected_revision` + idempotency keys** on every mutating op. Blind retry duplicates state.
6. **Execution leases span backends** (Store-level), not just `fcntl`. Local CLI must see cloud worker's lease and vice versa.

### Schema fidelity

1. **Image colocation:** blobs at `~/.megaplan/<repo-id>/blobs/`, not under `epics/<id>/`. Matches `ON DELETE SET NULL` semantics.
2. **Canonical JSON** for `prior_state` JSONB and any round-trip field — sorted keys, ISO-Z timestamps, explicit nulls, stable numerics.
3. **JSONB defaults `[]`/`{}`:** Pydantic normalizes missing/null on serialization both ways.
4. **Partial unique indexes** enforced in code in file mode: active image `reference_key`, queued sprint `queue_position`, `idempotency_key`, Discord message id, lowercase codebase owner/name.
5. **TIMESTAMPTZ** always tz-aware, ISO-8601 UTC with `Z` suffix.

### Editorial transplant

1. **Multi-entity edits at `editorial.py:95, 196`** become `Store.transaction()`.
2. **Revert needs `expected_revision`** — bot/CLI race during revert is a real failure mode.
3. **`load_hot_context`** is a first-class Store method (joined read), not composed primitive reads.
4. **`transaction(epic_id=None)` allowed** because `create_epic` runs before the epic exists.
5. **Don't port `resident.py`.** Period.

### Operational

1. **Cloud worker + FileStore = unsupported pair.** Cloud only operates on `db`-home epics.
2. **Identity model can't be deferred.** Sprint 2 designs the automation-actor; no service-role-as-default.
3. **Worktree state at `~/.megaplan/<repo-id>/`**, not in worktree. Backend-stable.
4. **Concurrent edits use `expected_revision` everywhere.** Both backends.
5. **Hybrid backups defer.** Don't try cross-backend consistency in v1.
6. **Mid-promote crash recovery** via `migration_runs` durable phase tracking. Resumable.
7. **Plan failure UX requires the run lifecycle contract.** Without it, failures are inscrutable.

---

## Out of scope for the merge (do not "while we're at it")

- New top-level abstractions beyond Arnold's schema (`WorkItem`, `RunGraph`).
- Cross-project distributed scheduler.
- Isolation/merge_policy fields on plans.
- Sub-attempt tracking beyond plan iterations.
- Visual UI / web dashboard.
- Migrating Discord-specific tables (`bot_turns`, `tool_calls`, `system_logs`) into megaplan-side ownership.
- Voice / image generation pipelines beyond what Arnold has today.
- Full bidirectional offline sync (CRDT territory).
- Backwards-compat shims for Arnold's old API surface — Arnold is gutted, not preserved.
- Real-time multi-user behavior in file mode (physically impossible).

---

## Recommended order of operations

1. **Sprint 0 spike (3 days).** Validate refined Store Protocol + transaction journal against real call sites. Update this doc with findings.
2. **Sprint 1 standalone.** Don't chain. Verify foundation lands clean.
3. **Confirm `arnold-merge-design.md` still matches reality.** Update if not.
4. **Then chain Sprints 2–6 in cloud** with the existing `megaplan auto`/`cloud chain` machinery.
5. **Sprint 7 (hardening) optional but recommended** before declaring the merge complete.

---

## Reference: file paths used in this doc

- Arnold root: `/Users/peteromalley/Documents/arnold-v2/`
- Arnold migrations: `/Users/peteromalley/Documents/arnold-v2/supabase/migrations/`
- Arnold editorial source: `/Users/peteromalley/Documents/arnold-v2/agent_kit/{gating.py, tools/editorial.py, tools/editorial_reads.py, tools/images.py, store/supabase.py, sprints.py}`
- Arnold runtime (NOT porting): `/Users/peteromalley/Documents/arnold-v2/agent_kit/resident.py`
- Megaplan root: `/Users/peteromalley/Documents/megaplan/`
- Megaplan core: `/Users/peteromalley/Documents/megaplan/megaplan/{auto.py, workers.py, types.py, schemas.py, cli.py, _core/io.py, _core/state.py}`
- New in megaplan post-merge: `megaplan/{schemas/, store/, editorial/, control.py, progress.py, plan_repository.py}`

---

## Current execution status (snapshot)

Cloud chain is in flight against an earlier baseline:

- **Sprint 1 (canonical data model):** in progress, on `origin/main`. `plan + critique + gate` completed; gate routed into `revise`. Active step is healthy and recently started.
- **Sprints 2–8:** pending.

Worktree posture today:

- `bakeoff` mode uses separate worktrees per branch.
- `chain` mode does **not** — it runs serially in one checkout.
- This is fine for a strict linear sprint chain. It is **not** good enough for the "run all unblocked plans across projects" model this doc is moving toward.

---

## Future work: queue, worktrees, merge state machine

The architecture below is *not* part of Sprints 0–7. It's the natural next layer once the Store + schema land — the piece that turns "chain serial driver over one checkout" into a real concurrent scheduler. Captured here so we don't forget it.

### Recommended abstraction

Five concrete moves:

**1. Every runnable plan gets its own worktree.**
- Branch name derived from epic/plan id: `megaplan/<epic-id>/<plan-id>`
- Base SHA recorded at start.
- Runtime files live outside the app repo or in ignored `.megaplan/runtime/`.

**2. Dependencies are graph edges, not list order.**
- The queue finds all open plans where dependencies are satisfied.
- Those plans can run concurrently — even across projects.
- Epics are containers that create or group plans; they're not the execution primitive.

**3. Merge is a first-class state machine.**
- `running → completed_unmerged → merge_pending → merged`
- Or off-ramps: `merge_conflict`, `review_failed`, `discarded`.
- Nothing is "done" until merged or explicitly discarded.

**4. Merging is patch/branch based.**
- For each completed worktree, capture:
  - base SHA
  - head SHA
  - full patch
  - changed files
  - tests run
  - megaplan plan/review artifacts
- Apply onto current integration branch with `git apply --check` or `git merge --no-ff`.
- If conflicts happen, create a merge-resolution plan instead of silently failing.

**5. Make data loss impossible by default.**
- Never delete a worktree until its patch and branch are archived.
- Never overwrite a shared checkout with active work.
- Never continue after failed fetch/checkout/pull.
- Always expose: base ref, worktree path, branch, dirty status, merge status.

### Mechanical vs agent-guided split

Most of this should be mechanical infrastructure. Agents only where judgment is genuinely needed.

**Mechanical (no agent reasoning):**
- Worktree creation per runnable plan.
- Branch naming, base SHA capture, dirty-state checks.
- Dependency scheduling: "run all unblocked plans."
- Runtime state tracking: `queued / running / blocked / completed / merge_pending / merged / conflicted`.
- Patch capture and artifact archival.
- Merge preflight: `git apply --check`, changed-file overlap detection, test command routing.
- Refusing unsafe operations: dirty shared checkout, failed refresh, missing base, untracked runtime file collisions.
- Status output showing exactly where work lives and what needs attention.

**Agent-guided (explicit contracts):**
- Deciding whether two completed plans are semantically compatible.
- Resolving merge conflicts.
- Choosing whether a failed review needs rework or can be accepted.
- Summarizing risk between concurrently produced changes.
- Creating follow-up plans when merge/review reveals a deeper architectural issue.

Phase contracts:

- **Executor:** "You own only this worktree and this plan. Do not modify runtime state. Produce implementation + evidence."
- **Reviewer:** "Judge against success criteria and changed files. Do not merge."
- **Merger:** "Resolve only integration conflicts between these branches. Preserve both sides unless explicitly obsolete."
- **Scheduler:** not an agent. Pure code.

### Data model sketch

```
Epic
  owns many Plans

Plan
  has dependencies (other plans)
  has target project
  has execution branch/worktree
  produces artifacts + patch

Run
  one attempt to execute a Plan
  records base SHA, head SHA, status, logs, review

Merge
  promotes a completed Run into an integration branch
  can be automatic, conflicted, or agent-assisted
```

### Queue rule

```
Find all Plans where:
  - state ∈ {open, ready}
  - all dependencies are merged or waived
  - no conflicting active lock exists

Start each in its own worktree.
When done, review.
If review passes, move to merge_pending.
Attempt merge.
If merge succeeds, mark merged and unblock dependents.
If merge fails, create a merge-resolution plan.
```

### Why this matters

The mistake would be making "chaining" a prompt convention. It should be a real scheduler / runner / merge state machine, with agents plugged into the specific points where reasoning is needed. The current chain mode (serial over one checkout) is fine while we're shipping Sprints 0–7 — but once those land, the scheduler/worktree/merge layer becomes the obvious next thing to build, and it should sit on top of `MultiStore` cleanly.

This is *not* a Sprint 8. It's a separate initiative that builds on the merged system.
