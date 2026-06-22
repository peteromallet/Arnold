# State Authority Migration

The M3 runtime replaces overwrite-only state authorities with a journal-first,
manifest-coordinate model.  This document explains the new coordinate system,
legacy-alias quarantine, authority-gated resume, and the migration path for old
state authorities.

## Manifest-coordinate cursors

Runtime identity is `(alias, manifest_hash)`:

```python
from arnold.manifest import manifest_coordinate, NodeRef

coord = manifest_coordinate("my-workflow", "sha256:...")
cursor = coord.cursor(node=NodeRef("gate"), reentry_id="resume")
```

`ManifestCursor` (in `arnold.manifest.refs`) is the only cursor accepted by
`arnold.execution.run`.  It pairs a human alias with a cryptographic manifest
hash, so old aliases cannot accidentally resume against a changed workflow
definition.

The kernel's `ReplayCursor` (`arnold.kernel.replay`) is bridged to a
`ManifestCursor` by `arnold.execution.resume.build_resume_manifest_cursor` and
`prepare_resume`.

## Legacy alias quarantine

`prepare_resume` resolves cursors with native-first semantics:

1. If the cursor's `manifest_hash` matches the loaded manifest, use it.
2. Otherwise, consult `legacy_aliases` (a mapping from old hash to
   `LegacyAliasRecord`).
3. If neither resolves cleanly, the outcome is quarantined with a reason such
   as `manifest_hash mismatch`.

Quarantine produces `ResumeOutcome(ok=False, replay_resolution=..., quarantine_reason=...)`
rather than mutating state.  This prevents stale aliases from resuming against
the wrong topology.

## Authority-gated resume

A manifest may declare `AuthorityRequirement` items in its `WorkflowPolicy`:

```python
WorkflowPolicy(
    authority=(
        AuthorityRequirement(authority_id="resume-auth", action="resume"),
    ),
)
```

Before accepting a resume cursor, `LocalJournalBackend._check_authority` asks
`ExecutionRegistries.authorities` to verify the action.  Denied authority
short-circuits to `ExecutionState.QUARANTINED` and emits a `resume_rejected`
event with code `authority_denied`.

Authority is checked before any node executes, so a denied resume cannot mutate
the journal beyond the rejection event.

## Migration path for old state authorities

Old authorities live in modules such as `arnold.pipeline.state`,
`arnold.runtime.state_persistence`, and product-specific resume stores.  The
migration path is:

1. **Read-only reconciliation**: continue writing old state, but do not use it
   as the source of truth.  Reconstruct runnable state from `events.ndjson`.
2. **Cursor conversion**: convert old resume tokens to `ReplayCursor` or
   `ManifestCursor` using `build_resume_manifest_cursor`.
3. **Alias registration**: map old manifest hashes to current hashes via
   `legacy_aliases` in `prepare_resume`.
4. **Authority registration**: port old auth checks to
   `ExecutionRegistries.authorities` handlers.
5. **Deletion**: once all in-flight runs have converted, remove old state
   writes.  See `runtime-salvage-deletion-map.md` for the disposal schedule.

## Files involved

- `arnold/manifest/refs.py` — `ManifestCoordinate`, `ManifestCursor`, `NodeRef`.
- `arnold/kernel/replay.py` — `ReplayCursor`, `resolve_cursor`.
- `arnold/execution/resume.py` — `prepare_resume`, `build_resume_manifest_cursor`.
- `arnold/execution/backend.py` — `_check_authority`, `run_manifest`.
- `arnold/execution/registries.py` — `AuthorityRegistry`, `ExecutionRegistries`.

---

## Megaplan nested-state ledger

This ledger was produced by an explicit scan of `.megaplan/` in the engine root
(`MEGAPLAN_ENGINE_ROOT=/Users/peteromalley/Documents/megaplan`).  It applies to
all Megaplan plans and runs that pre-date the M4 manifest runtime.

### Disposition legend

| Disposition | Meaning |
| --- | --- |
| `migrate` | Convert into manifest event-journal coordinates / artifact bindings in M4 Phase 4. |
| `project read-only with sunset` | Kept as a read-only projection for operators; writes stop once migration is complete; deleted at sunset. |
| `archive outside active tree` | Moved to `.megaplan/_archived/` or equivalent; not loaded by active code. |
| `delete` | Safe to delete once no in-flight run references it. |
| `quarantine with operator-visible rationale` | Cannot be auto-migrated; operator must decide per instance. |

### Ledger

| Class | Example paths | Disposition | Owner | Notes / blocker |
| --- | --- | --- | --- | --- |
| `state.json` (plan) | `.megaplan/plans/<plan>/state.json` | `project read-only with sunset` | megaplan | Old mutable authority; new runtime reconstructs from `events.ndjson`. |
| `state.json` (run) | `.megaplan/runs/<alias>/<timestamp>/state.json` | `project read-only with sunset` | megaplan | Same as plan state; sunset after journal parity. |
| Receipts | `.megaplan/plans/<plan>/step_receipt_*.json` | `migrate` | megaplan | Convert to checkpoint events with artifact bindings. |
| Phase artifacts | `.megaplan/plans/<plan>/phase_result.json`, `prep.json`, `research.json`, `routing_ledger.jsonl` | `migrate` | megaplan | Map to explicit node outputs / branch choices. |
| Plan locks | `.megaplan/plans/<plan>/.plan.lock`, `.routing_ledger.lock` | `quarantine with operator-visible rationale` | megaplan | Lock owner/PID/TTL must be inspected before migration. |
| Run locks | `.megaplan/runs/<alias>/.state-locks/<timestamp>.lock` | `quarantine with operator-visible rationale` | megaplan | Stale locks may indicate crashed runs. |
| `.hermes_state` | `.megaplan/plans/<plan>/.hermes_state/*.db*` | `archive outside active tree` | megaplan | Agent conversation cache; not reproducible from journal. |
| Nested `.megaplan` dirs | `.megaplan/runs/<alias>/.megaplan-event-store/` | `migrate` | megaplan | Event-store used by sub-epics; fold into parent journal. |
| Telemetry | `.megaplan/telemetry/` | `archive outside active tree` | megaplan | Cost/usage telemetry; not runtime authority. |
| Watchdog logs | `.megaplan/watchdog-run-logs/` | `archive outside active tree` | megaplan | Operational observability only. |
| Briefs | `.megaplan/briefs/**` | `project read-only with sunset` | megaplan | Authoring input; immutable after adoption. |
| Schemas | `.megaplan/schemas/` | `project read-only with sunset` | arnold | Runtime schema authority now lives in `arnold/kernel` content-type registry. |
| Tickets | `.megaplan/tickets/` | `migrate` | megaplan | Convert to `Ticket` storage model events if linked to a run. |
| Drafts | `.megaplan/plan_v4_draft.md`, `plan_v2_revised.json` | `archive outside active tree` | megaplan | Superseded drafts. |
| Empty roots | `.megaplan/blobs/`, empty plan dirs | `delete` | megaplan | Safe once confirmed unused. |
| Epic event journals | `.megaplan/epics/<epic>/events.jsonl` | `migrate` | megaplan | Already event-shaped; normalize to manifest event schema. |
| Plan event journal | `.megaplan/plans/<plan>/events.ndjson` | `migrate` | megaplan | Becomes the canonical authority; verify sequence integrity. |
| Run event journal | `.megaplan/runs/<alias>/<timestamp>/events.ndjson` | `migrate` | megaplan | Becomes the canonical authority. |
| `.events.seq` | `.megaplan/plans/<plan>/.events.seq`, run `.events.seq` | `migrate` | arnold | Sequence counter; migrate to journal sequence coordinate. |
| Idea snapshot | `.megaplan/plans/<plan>/idea_snapshot.md` | `archive outside active tree` | megaplan | Authoring artifact. |
| Current / revised docs | `.megaplan/runs/<alias>/<timestamp>/current.md`, `revised.md`, `revise_prompt.md` | `migrate` | megaplan | Bind as artifacts on `revise` node. |

### Lock owner / PID / TTL / stale-lock handling

Megaplan uses filesystem locks for plan and run exclusivity.

| Lock path pattern | Scope | Owner field | TTL convention | Stale handling |
| --- | --- | --- | --- | --- |
| `.megaplan/.state-locks/<plan>.lock` | Plan/epic | `owner` (PID + hostname) | 24h | If mtime > TTL and PID not alive, treat as stale; emit `lock_stale` quarantine event. |
| `.megaplan/plans/<plan>/.plan.lock` | Plan write | `owner` | 24h | Stale locks may be broken after operator confirmation; new runtime never mutates. |
| `.megaplan/plans/<plan>/.routing_ledger.lock` | Routing ledger | `owner` | 1h | Short-lived; stale implies crashed router. |
| `.megaplan/runs/<alias>/.state-locks/<timestamp>.lock` | Run | `owner` | 24h | Stale locks block resume until quarantined or cleared. |

Rules:

1. **Never overwrite an alive lock.** Migration tooling checks PID liveness with `psutil.pid_exists()` before declaring stale.
2. **Stale locks are quarantined, not silently broken.** The operator sees a `quarantine_reason` such as `stale_lock_owner_dead`.
3. **New runtime locks are advisory only.** Authority is the event journal; locks prevent concurrent writers but are not the source of truth.

### Old resume fields → manifest event-journal coordinates

| Legacy field (in `state.json` / resume token) | Meaning | Manifest coordinate |
| --- | --- | --- |
| `plan_id` / `run_id` | Human alias for the run | `ManifestCursor.alias` |
| `pipeline_id` / `pipeline_hash` | Old pipeline identity | `ManifestCursor.manifest_hash` (after alias registration) |
| `phase` | Current phase name (`prep`, `plan`, `critique`, `gate`, `revise`, `finalize`, `execute`, `review`, `tiebreaker`) | `NodeRef(node_id=...)` in the explicit-node manifest |
| `iteration` | Gate / critique loop counter | `reentry_id` on the resume cursor, plus event sequence offset |
| `last_completed_step` | Last successful step | `ReplayCursor.position` → `NodeRef` + sequence |
| `suspended_at` | Human-gate suspension timestamp | `suspend` control-transition event with `suspended_at` metadata |
| `override` | Operator override catalog action | `ControlTransition` event emitted into the journal |
| `flags` | Significant flags | Artifact binding on `gate` / `critique` node outcome |
| `artifacts` | Output file paths | `ArtifactBinding` entries in node outcome |
| `resume_token` | Opaque legacy token | `LegacyAliasRecord` mapping old hash → current manifest hash |

### Migration sequencing

1. **Inventorize** all `.megaplan` roots (plans, runs, epics) and their locks.
2. **Quarantine** anything with stale locks, mismatched hashes, or unsupported phase names.
3. **Convert** surviving `state.json` + receipts + event journals into manifest checkpoints.
4. **Archive** `.hermes_state`, telemetry, watchdog logs, and drafts outside the active tree.
5. **Validate** that status / trace / resume projections from the new journal match the old `state.json` read-only view.
6. **Sunset** old state writes once parity tests pass.
