# Sprint 7 — Hardening + migration tooling

**Authoritative source:** `docs/arnold-merge-design.md` (section "Sprint 7 — Hardening + migration tooling", lines ~814-825).

**Predecessor:** Sprint 6 completed the Discord control plane and Arnold gutting. The merged system is functional. Sprint 7 polishes the rough edges and ensures existing megaplan users have a clean upgrade path.

**Note:** marked optional in the design doc, but recommended.

## Scope

- Migration script for **existing megaplan local plans** under `~/.megaplan/<project>/plans/<plan-id>/` → orphan plans (`epic_id=None`) in the new schema, OR attached to a new "legacy" epic. User picks via flag.
- Backup tooling for FileStore: `megaplan epic export <id>` produces a tar of the epic's full state (rows + blobs) suitable for re-import or DR.
- Operational docs in `docs/ops/`: how to recover from each known failure mode (stuck transaction journal, abandoned migration_run, orphaned execution_lease, corrupt blob, etc.).
- Cloud worker rebuild + smoke-test against the new megaplan: confirm `megaplan cloud chain` still works end-to-end on a fresh image with the new code.

## Acceptance

- All existing megaplan plan dirs found under `~/.megaplan/` migrate cleanly with the script (verify against a snapshot of pre-migration state).
- One full chain (an epic with 3 sprints) runs end-to-end in cloud on the new system, using `megaplan cloud chain`.
- Failure-mode docs exist for each scenario and have been validated by deliberately reproducing each failure.

## Out of scope

- New features. Sprint 7 is exclusively hardening.

## Robustness

`light` — discrete tooling tasks with concrete acceptance.
