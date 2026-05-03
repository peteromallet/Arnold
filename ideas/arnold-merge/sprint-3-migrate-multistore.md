# Sprint 3 — Promote/Demote + MultiStore

**Authoritative source:** `docs/arnold-merge-design.md` (section "Sprint 3 — Promote/Demote + MultiStore", lines ~740-756, plus the `migration_runs` 7-phase state machine, MultiStore federation, and execution-leases sections).

**Predecessor:** Sprint 2 has shipped `DBStore` (read-only writes), identity model, RLS, and the new tables.

## Scope

- DBStore writes enabled — every mutation requires `expected_revision` and an idempotency key, runs inside a transaction.
- `MultiStore` in `megaplan/store/multi.py` — routes by `epics.home_backend`. A single `MultiStore` instance owns both a `FileStore` and a `DBStore`; reads/writes dispatch by epic.
- `migrate_epic` with all 7 phases (planning → tombstoning → complete), durable `migration_runs` rows, resumable on holder death (recovery on next CLI start).
- Pre-migrate checks: no active execution lease on the epic, no collision with another running migration, holds the epic lock for the duration.
- `~/.megaplan/<repo-id>/...` becomes the canonical FileStore root (formalize the path).
- `megaplan epic snapshot <id>` for offline reads of DB-home epics.

## Acceptance

- `migrate_epic` round-trips a complete epic (including blobs, all related rows: checklist items, sprints, second opinions, images, etc.) with byte-equal blob hashes verified.
- Mid-migration kill (kill -9) + resume produces identical final state — no half-migrated rows.
- Concurrent `migrate_epic` attempts: second one fails cleanly with a lease-busy error.
- Fuzz harness from Sprint 1 passes on `MultiStore` with epics in both backends simultaneously.

## Out of scope

- Editorial logic transplant (Sprint 4-5).
- Discord control plane (Sprint 6).

## Robustness

`standard` — durability + crash-recovery + concurrent migration are the highest-risk parts of the whole project.
