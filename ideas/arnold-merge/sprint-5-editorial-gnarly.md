# Sprint 5 — Editorial transplant: gnarly bits

**Authoritative source:** `docs/arnold-merge-design.md` (section "Sprint 5 — Editorial transplant: gnarly bits", lines ~777-792).

**Predecessor:** Sprint 4 has shipped pure editorial logic against `Store`. Sprint 5 tackles the parts that involve canonical-form determinism, multi-row atomicity, blob-backed media, and search-index dual-backend semantics.

## Scope

- `revert(epic_id, to_transaction_id)` with `expected_revision`, **canonical JSON serialization** (deterministic key ordering, no whitespace drift), full prior-state restoration including dependent rows.
- `get_epic_at_time(epic_id, when)` — point-in-time epic reconstruction from event log.
- Second-opinion runner: invokes a model, persists `second_opinions` rows, atomically updates `checklist_items` based on findings.
- Image management: `reference_key` uniqueness, inline body refs (`![alt](mp://image/<key>)`), blob backend abstraction so file-mode images on disk and DB-mode images in Supabase storage both work and survive migrate.
- Full-text search: PG `tsvector` + GIN index for DB backend; SQLite FTS5 for file backend. Both wired through a `search_epics` Store method.

## Reference repos

- Arnold source (read-only): https://github.com/peteromallet/arnold — see `agent_kit/tools/editorial.py` revert logic, `agent_kit/tools/images.py`, second-opinion code paths.

## Acceptance

- Revert round-trips correctly: revert-to-T then re-applying ops produces same state hash; subsequent edits work; `revision` advances monotonically.
- Second opinion is atomic across `second_opinions` insert + `checklist_items` updates (kill-9 mid-second-opinion leaves no half-state).
- Image attached in file-mode survives `migrate_epic` to DB and renders identically (byte-equal blob hash).
- Search returns ranked results in **both** backends; top-3 results stable across re-indexing.

## Out of scope

- Discord control plane (Sprint 6).
- Arnold gutting (Sprint 6).

## Robustness

`standard` — canonical-form determinism + multi-row atomicity + dual-backend search are subtle and need critique.
