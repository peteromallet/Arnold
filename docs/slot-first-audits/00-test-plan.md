# Slot-First Test Plan

Generated: 2026-05-20T10:51:32Z.

This is the shared test plan for M1-M4. M0 installed audit-mode infrastructure only; DB-backed checks become enforcing gates when a real database target and the slot-first schema exist. The central rule is that pgTAP is DB coverage and health diagnostics are not.

## Executable Surface Installed In M0

| Layer | Command | Current M0 behavior | Enforcement owner |
| --- | --- | --- | --- |
| Frontend/unit | `npm run test:slot:unit` / `make slot-first-unit` | Runs focused Vitest coverage for the disabled-trigger stale promotion cleanup. | M1-M4 expand this to slot-first frontend units. |
| Edge/unit | `npm run test:slot:edge` / `make slot-first-edge` | Runs the existing edge smoke suite because broader edge units currently include unrelated failures. | M3 replaces smoke-only scope with slot-first edge contract tests. |
| DB pgTAP | `npm run test:slot:db -- --audit` / `make slot-first-db` | Runs `scripts/quality/run-slot-pgtap.mjs`; exits successfully if pgTAP files, `psql`, or DB credentials are unavailable in M0 audit mode. | M1 adds pgTAP files; M4 flips enforcement. |
| E2E | `npm run test:slot:e2e` / `make slot-first-e2e` | Runs Playwright with the Vite dev server and safe dummy public Supabase env vars. | M2-M4 add authenticated/seeded workflows. |
| Schema drift | `npm run quality:schema-drift -- --audit` / `make slot-first-schema-drift` | Parses tracked migrations and, if a schema dump or DB URL exists, compares live objects to tracked evidence. Does not fail in M0 audit mode. | M4 flips enforcement. |
| Fixture rot | `npm run quality:test-fixture-legacy -- --audit` / `make slot-first-test-fixture-legacy` | Greps active test/spec files for legacy terms and reports offenders without failing. | M4 flips enforcement. |
| Health/readiness | `npm run slot:first:health -- --audit` / `make slot-first-health` | Reports env keys, DB tooling, and local Supabase/Postgres ports. This is diagnostics only. | Never counted as DB coverage. |
| Composed audit | `npm run quality:slot-first:audit` / `make slot-first-audit` | Runs unit, edge, pgTAP audit, schema-drift audit, fixture-rot audit, health diagnostics, and Playwright. | CI runs this on slot-first path PRs. |

CI wiring is `.github/workflows/slot-first-quality.yml`. It is separate from the existing Dockerfile workflow and runs `make slot-first-audit` on PRs touching slot-first docs, scripts, source, Supabase, Playwright config, or the quality workflow itself.

## Test Pyramid

Unit tests are the first line for deterministic contract behavior. M2 owns frontend unit tests for slot selection, duplicate/share-copy/drag-reorder behaviors, generated Supabase type consumers, and stale-trigger caller cleanup. M3 owns edge and agent unit tests for claim/complete/task-count/data-fetch contracts, Astrid tool schemas, and worker-facing payload validation.

DB tests are pgTAP, not port checks. M1 must create `supabase/tests/slot-first/` or `supabase/tests/slot_first/` SQL files for schema invariants, RLS, RPC behavior, lifecycle transitions, and row-lock behavior. The runner also picks up `supabase/tests/*slot*.sql`, but new slot-first DB coverage should live in a dedicated directory so M4 can require it.

E2E tests are Playwright. M0 added `@playwright/test`, `playwright.config.ts`, and `tests/e2e/home-load.spec.ts`. The config starts Vite with dummy `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and `VITE_APP_ENV=web`, then loads the unauthenticated `/home` route. Later milestones add seeded authenticated flows instead of replacing this smoke test.

Migration rehearsal is a human-controlled staging restore from a recent dev/prod-like snapshot. It is not replaced by schema-drift parsing, pgTAP, or Playwright because the cutover needs real data distributions, legacy bad rows, and long-tail migration inputs.

## pgTAP Coverage Targets

M1 pgTAP coverage must verify schema shape and invariants:

- `shot_slots` is the sole successor to `shot_generations`, with `slot_id` primary identity and required `project_id`/`shot_id` ownership agreement.
- Positioned slots are unique within a shot by the chosen ordering coordinate.
- Attempts and optional clips attach to slots without reintroducing `generation_id` aliases.
- RLS keeps `user_id` as auth ownership and `project_id` as project ownership, without treating either as a legacy domain ID.
- New functions and triggers encode invariants as constraints or transactional logic, not comments.

M2 pgTAP coverage must verify frontend-facing RPCs and generated type expectations:

- Same source attempt/media can occupy multiple slots without uniqueness violations on the output identity.
- Share-copy creates new slot identities and does not preserve legacy generation IDs as aliases.
- Drag/drop reorder mutates slot position only and leaves attempt/clip identity stable.

M3 pgTAP coverage must verify service-contract behavior:

- `claim-next-task` and `task-counts` keep `worker_backend` and `selector_namespace` behavior while replacing legacy generation-shaped selectors.
- `complete_task`, `reigh-data-fetch`, and `update-shot-pair-prompts` no longer expose `parent_generation_id`, `pair_shot_generation_id`, `child_generation_id`, or equivalent compatibility fields.
- Task lifecycle transitions cannot produce orphan attempts, orphan slots, or cross-project references.

M4 pgTAP coverage must verify cutover and deletion:

- Legacy tables/functions/triggers/views slated for deletion are absent.
- Slot-first constraints still pass after migrated data is loaded.
- Concurrent `slot_first_complete_attempt` or equivalent completion RPCs serialize safely when competing for the same `shot_slots` row.
- No RLS policy still depends on `generation_variants`, `shot_generations`, or `generations` as live domain tables.

## Health Is Separate

`scripts/quality/check-slot-first-health.mjs` is intentionally a readiness command. It reports whether secrets, DB tooling, and local ports are present. It must remain useful for diagnosing why pgTAP or schema-drift cannot run, but it must never be cited as DB test coverage.

Acceptable uses:

- Confirm whether `psql`, `pg_dump`, or `supabase` are available.
- Confirm whether `SLOT_FIRST_DATABASE_URL`, `DATABASE_URL`, `SUPABASE_DB_URL`, `POSTGRES_URL`, or `PG*` env vars are set.
- Confirm whether local Supabase/Postgres ports are open.

Unacceptable uses:

- Treating a green health command as proof that schema constraints, RPCs, RLS, triggers, or migration data are correct.
- Replacing `test:slot:db` with `slot:first:health` in CI or release notes.
- Calling health output a staging rehearsal.

## Playwright Wiring And Growth Path

M0 wiring:

- Dependency: `@playwright/test` in `devDependencies`.
- Config: `playwright.config.ts`.
- Smoke: `tests/e2e/home-load.spec.ts`.
- Script: `npm run test:slot:e2e`.
- Make target: `make slot-first-e2e`.
- CI: `.github/workflows/slot-first-quality.yml` installs Chromium and runs `make slot-first-audit`.

M2 must add a seeded frontend slot workflow once M1 schema exists. Minimum flow: create/open a project fixture, render a shot with multiple slots, reorder slots, duplicate or share-copy a source item, and assert the UI does not expose legacy generation vocabulary.

M3 must add an agent/edge-facing workflow only after the service contracts are slot-first. Minimum flow: create an attempt through the edge pathway used by workers/Astrid, complete it, and observe the slot/attempt/clip result in the frontend or data-fetch payload.

M4 must add a cutover smoke that starts from migrated fixture data and proves the app boots without `generations`, `generation_variants`, or `shot_generations` being available as active tables.

## Existing Legacy Test And Spec Handling

The existing test surface is legacy-heavy. A fresh repository count found 1,203 active test/spec files outside `node_modules`, and the M0 fixture-rot grep found 145 active test/spec files with legacy terms. Earlier D4 notes called this roughly 138 files; the M0 gate is the current executable source and should be re-run by each milestone.

Current inventory command:

```sh
rg -l "generations|generation_variants|shot_generations|parent_generation_id|pair_shot_generation_id|child_generation_id|primary_variant_id|generation_id|variant_id" \
  --glob '*.{test,spec}.{ts,tsx,js,jsx,mjs,cjs,sql}' \
  --glob 'test_*.py' \
  --glob '*_test.py' \
  --glob '!node_modules/**' \
  --glob '!**/_archived_*/**'
```

Handling categories:

- Rewrite to slot-first: tests that assert behavior that survives the migration, such as placement ordering, duplicate/share-copy semantics, task completion, RLS ownership, and agent/worker contracts.
- Delete as legacy-only: tests whose only assertion is that old tables/triggers/RPC overloads behave a certain way and whose behavior is superseded by new slot-first tests.
- Keep temporarily as migration-period regression: tests needed during M1-M3 to prove legacy read paths still work until M4 cutover. Every kept test needs an owner milestone and an explicit deletion or rewrite note.

Ownership:

- M2 handles frontend tests, including generated Supabase type consumers and video-editor/gallery tests that currently assert `generation_id`, `shot_generations`, or variant identity.
- M3 handles edge-function and Astrid tests, including `supabase/functions/_tests/harness/snapshot.ts` and every `supabase/functions/ai-timeline-agent/*.test.ts` or `tools/*.test.ts` listed in `04-astrid-current-state.md`.
- M3 also handles sibling-repo worker/orchestrator/Astrid tests surfaced in `05-worker-contract.md`.
- M4 turns `quality:test-fixture-legacy` from audit mode to enforce mode and verifies no active test/spec file outside `_archived_*` paths references legacy domain IDs or tables.

## Schema Drift And Fixture Rot Gates

`scripts/quality/check-schema-drift.mjs` and `scripts/quality/check-test-fixture-legacy.mjs` are installed and wired in M0. They are deliberately inactive in M0 because the cutover has not happened and this harness lacks DB credentials.

M1-M3 must keep these scripts running in audit mode on PRs. Net new offenders are not acceptable even while existing offenders remain. M4 flips enforcement through `--enforce`, `SLOT_FIRST_SCHEMA_DRIFT_ENFORCE=1`, `SLOT_FIRST_FIXTURE_LEGACY_ENFORCE=1`, or `CI_SLOT_FIRST_ENFORCE=1`.

Schema drift input options:

- `SLOT_FIRST_SCHEMA_DUMP` or `SCHEMA_DUMP_PATH` for a committed-or-artifact schema-only dump.
- `SLOT_FIRST_DATABASE_URL`, `DATABASE_URL`, `SUPABASE_DB_URL`, or `POSTGRES_URL` plus `pg_dump`.

Fixture rot enforcement excludes `_archived_*` paths by design. Archiving a legacy fixture is acceptable only when the owning milestone documents why it is no longer active coverage.

## Per-Milestone Expectations

| Milestone | Required test work | Required gate behavior |
| --- | --- | --- |
| M1 schema foundation | Add pgTAP for `shot_slots`, attempt/clip relations, RLS ownership, uniqueness, lifecycle constraints, and catalog dependency verification from `01-migration-ledger.md`. Add migration rehearsal notes for all legacy objects M1 creates or rewrites. | `test:slot:db -- --audit` should find real SQL files. Health remains separate. Schema drift remains audit mode but should be runnable against staging if credentials exist. |
| M2 frontend migration | Rewrite frontend tests from `01-grep-ledger.md`; add unit tests for same output in multiple slots, share-copy, drag reorder, generated type usage, and no compatibility aliases. Add first seeded Playwright slot workflow. | `test:slot:unit` must expand beyond M0 stale-trigger tests. `quality:test-fixture-legacy -- --audit` should show reduced frontend offenders. |
| M3 service contracts | Rewrite edge/Astrid/worker/orchestrator tests from `04-astrid-current-state.md` and `05-worker-contract.md`. Add contract tests for Zod/shared schemas at worker-edge and edge-agent boundaries. Add pgTAP for `claim-next-task`, `task-counts`, completion, and data-fetch slot-first contracts. | `test:slot:edge` must stop being smoke-only for slot-first paths. Fixture-rot audit should show no active edge/Astrid worker-contract legacy tests except explicitly kept migration-period tests. |
| M4 cutover/drop | Delete or rewrite all remaining active legacy test fixtures; add post-cutover pgTAP absence checks for old tables/functions/triggers/views; run zero-ref grep across this repo and sibling worktrees; add migrated-data Playwright smoke. | Flip schema drift and fixture rot to enforcement. `make slot-first-audit` should fail on legacy references, untracked live schema, missing pgTAP, or cutover smoke failure. |

## Staging Restore Rehearsal

The cutover needs a human-run rehearsal against staging restored from a recent dev/prod-like snapshot. The operator should record the date, source snapshot, migration range, row counts, failures, and post-check evidence in the M4 PR.

Required rehearsal steps:

1. Restore staging from a recent snapshot that includes legacy `generations`, `generation_variants`, `shot_generations`, route backend tables, task history, Astrid sessions, and worker-produced payloads.
2. Capture preflight counts for legacy tables, route backend tables, task statuses, shots with multiple timeline positions, shared/copied shots, and rows touched by `_applied_20260225000000_backfill_pair_shot_generation_id.sql`.
3. Run all M1-M4 migrations through cutover on staging.
4. Run pgTAP in enforcement mode against staging with `test:slot:db`.
5. Run schema drift in enforcement mode with a live `pg_dump` or schema dump.
6. Run fixture rot in enforcement mode.
7. Run Playwright against the staging frontend/API target with seeded migrated data.
8. Run representative worker/orchestrator/Astrid contract checks from `05-worker-contract.md`.
9. Record postflight counts proving old objects are gone, new slot/attempt/clip rows are populated, no orphan/cross-project references exist, and no compatibility aliases remain.

This rehearsal is required even if all CI checks pass. CI proves the code path; staging restore proves the data path.

## Audit References

- Whole-repo legacy burn-down ledger: `docs/slot-first-audits/01-grep-ledger.md`.
- Migration object/dependency ledger: `docs/slot-first-audits/01-migration-ledger.md`.
- Slot model decision: `docs/slot-first-audits/02-second-slot-question.md`.
- Stale caller cleanup: `docs/slot-first-audits/03-stale-callers.md`.
- Astrid M3 work list: `docs/slot-first-audits/04-astrid-current-state.md`.
- Worker/orchestrator/Astrid contract surface: `docs/slot-first-audits/05-worker-contract.md`.
- Prior-art and sibling worktree handling: `docs/slot-first-audits/06-prior-art-reconciliation.md`.
- Identity glossary: `docs/slot-first-id-glossary.md`.
