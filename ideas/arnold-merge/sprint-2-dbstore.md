# Sprint 2 — DBStore + Identity

**Authoritative source:** `docs/arnold-merge-design.md` (section "Sprint 2 — DBStore + Identity", lines ~720-736, plus Schema and Identity model sections).

**Predecessor:** Sprint 1 has shipped `Store` Protocol, `FileStore`, `PlanRepository`, all Pydantic models, and a `DBStore` skeleton.

**Required env at runtime:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (only for migrations), `MEGAPLAN_ACTOR_ID`.

## Scope

- `megaplan/store/db.py` full `DBStore` implementation against Arnold's Supabase tables (mirrored in Sprint 1's Pydantic models).
- New tables (Supabase migrations in **Arnold's repo** at `arnold-source/supabase/migrations/`, then committed back from arnold-source): `automation_actors`, `migration_runs`, `execution_leases`, `plan_artifacts`, `control_messages`, `progress_events`.
- Schema extensions: `epics.home_backend` (text, default `'db'`), `sprints.status` enum extension (`running`, `failed`, `blocked`, `cancelled`).
- RLS policies allowing actor-scoped writes; **no service-role usage in non-migration code paths**.
- `MEGAPLAN_ACTOR_ID` env or `--actor` CLI flag. CLI refuses DB writes without an actor.
- `megaplan run --from-arnold-epic <id>` reads (no writes back yet — that's Sprint 3).
- Same Sprint 1 fuzz harness passes against `DBStore`.

## Reference repos

- Arnold (clone read+write): https://github.com/peteromallet/arnold — DB migrations land here.

## Acceptance

- `pytest --backend db` green (using a test Supabase project or local Supabase).
- A plan against a DB-home epic completes end-to-end (read-only DB).
- No service-role usage in any non-migration path (assert via grep in CI).
- `automation_actors` row required for any DB write — verify with a negative test.

## Out of scope

- Writes back to DB (Sprint 3 enables those with `expected_revision`).
- Promote/demote between backends (Sprint 3).
- Editorial logic (Sprint 4-5).
- MultiStore routing (Sprint 3).

## Robustness

`standard` — schema migrations + RLS + identity gating need critique.
