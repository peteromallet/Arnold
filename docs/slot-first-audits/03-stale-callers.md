# Stale Caller Cleanup Audit

Generated: 2026-05-20T10:01:19Z

Scope: M0 records the remaining stale callers after the frontend disabled-trigger cleanup. T5 changed the live promotion callers to fail closed before a `generations` insert. T6 added the single allowed M0 migration that drops the disabled `trg_auto_create_variant_after_generation` trigger and `auto_create_variant_after_generation_insert()` function. This audit covers the still-active script surfaces that can survive outside the app bundle.

## Commands Run

```bash
nl -ba scripts/debug/commands/context.py | sed -n '1,380p'
nl -ba scripts/debug/client.py | sed -n '1,470p'
nl -ba scripts/quality/check-supabase-rls.mjs | sed -n '1,260p'
rg -n "generation_id|generation_variants|shot_generations|pair_shot_generation_id|parent_generation_id|child_generation_id|primary_variant_id|generations|createClient|create_client|SUPABASE|supabase|from\(|readFileSync|readdirSync|client\.supabase|\.table\(|\.rpc\(" scripts/debug scripts/quality/check-supabase-rls.mjs -S
find scripts/debug -maxdepth 3 -type f | sort
git status --short
```

## Classification Rules

- **Live DB client:** creates or receives a Supabase client and can query production/staging data at runtime.
- **Static parser:** reads tracked repository files only. It can still encode stale schema assumptions, but it is not a live data client.
- **Formatter/support code:** does not query Supabase directly, but renders or prioritizes legacy fields returned by live clients.

## Primary Stale Surfaces

| Surface | Type | Evidence | Legacy dependency | M4 action |
| --- | --- | --- | --- | --- |
| `scripts/debug/commands/context.py:75-89` | Live DB client via `DebugClient` | Reads task params `parent_generation_id`, `child_generation_id`, `pair_shot_generation_id`. | Worker/task payload legacy generation contract. | **Disable until rewritten.** At M4, block the command before cutover unless it has been rewritten to `task_id`, `attempt_id`, `slot_id`, and optional `clip_id`. |
| `scripts/debug/commands/context.py:111-113` | Live DB client | Queries `generations` and selects `parent_generation_id`, `is_child`, `child_order`, `pair_shot_generation_id`. | Legacy generation tree identity. | **Disable until rewritten.** Replace with attempt/task lookup and explicit parentage from slot-first attempt relationships, not generation parent columns. |
| `scripts/debug/commands/context.py:128-141` | Live DB client | Queries `shot_generations` by `generation_id` to infer `shot_id`. | `shot_generations` as shot placement. | **Disable until rewritten.** Replace with `shot_slots` lookup keyed by `slot_id` or attempt output placement. |
| `scripts/debug/commands/context.py:210-227` | Live DB client | Looks up a generation by task membership and then queries `generation_variants` by `generation_id`. | `generations.tasks`, `primary_variant_id`, and variants as output records. | **Disable until rewritten.** Replace with `attempts` by `task_id` and slot-first output/clip records. |
| `scripts/debug/commands/context.py:269-307` | Live DB client | Fetches child, parent, based-on, and sibling rows from `generations`. | Legacy parent/child generation tree and `pair_shot_generation_id`. | **Disable until rewritten.** Rebuild only if M4 can express the same diagnostics through attempts and slots. |
| `scripts/debug/commands/context.py:318-334` | Live DB client | Queries `shot_generations` timeline rows by `shot_id` and parent generation. | Timeline placement stored as generation rows. | **Disable until rewritten.** Replace timeline output with ordered `shot_slots`; do not keep a compatibility read. |
| `scripts/debug/commands/context.py:388-660` | Formatter/support inside live command | Builds mismatch/orphan reports from `pair_shot_generation_id`, `parent_generation_id`, and `shot_generations.id`. | Legacy consistency checks. | **Delete or rewrite with the command.** If the command is not rewritten in M4, this diagnostic logic is removed with it. |
| `scripts/debug/client.py:13-28` | Live DB client | Creates Supabase service-role client from `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. | Shared live debug access. | **Keep with reason.** The client itself survives for task/log/worker debugging, but legacy generation helper methods below must be removed or rewritten. |
| `scripts/debug/client.py:96-123` | Live DB client | `_get_generation_for_task()` reads task `generation_id`, calls `get_generation_by_task_id`, and scans recent `generations`. | Task-to-generation lookup. | **Rewrite in M4.** Replace with `_get_attempt_for_task()` and remove the `get_generation_by_task_id` RPC dependency. |
| `scripts/debug/client.py:135-140` | Live DB client | `_get_variants()` queries `generation_variants` by `generation_id`. | Variants as generation children. | **Rewrite in M4.** Replace with output/clip lookup for an `attempt_id`, or delete if the debug summary no longer needs output details. |
| `scripts/debug/client.py:202-209` | Live DB client | `_get_shot_associations()` queries `shot_generations` by `generation_id`. | Generation-to-shot association table. | **Rewrite in M4.** Replace with slot association lookup through `shot_slots`; no compatibility query remains. |
| `scripts/quality/check-supabase-rls.mjs:1-37` | Static parser | Uses `readdirSync` and `readFileSync` over `supabase/migrations`; no Supabase client or DB connection. | None at runtime. | **Keep with reason.** This is a repository migration-quality guard, not a live stale DB client. |
| `scripts/quality/check-supabase-rls.mjs:7-10` | Static parser | `explicitUserOwnedTables` includes `shot_generations`. | Static allowlist still names removed legacy table. | **Rewrite and keep in M4.** Replace `shot_generations` with the slot-first user-owned tables that require RLS, including `shot_slots` if it remains project-owned through `shots/projects`. |

## Supporting Surfaces

| Surface | Type | Evidence | M4 action |
| --- | --- | --- | --- |
| `scripts/debug/formatters.py:196-197` | Formatter/support code | Renders `parent_generation_id` and `child_order` when a generation is present. | **Rewrite if debug task summaries keep output context; delete with generation helpers otherwise.** |
| `scripts/debug/formatters.py:257` | Formatter/support code | Prioritizes `generation_id` inside task params. | **Rewrite in M4** to prioritize `attempt_id`, `slot_id`, and `clip_id`; do not keep `generation_id` as a compatibility alias. |
| `scripts/debug/commands/query.py:12` | Live generic DB client | Allows arbitrary table queries through `client.supabase.table(table)`. It does not hard-code legacy names. | **Keep with reason, gated by zero-ref scan.** It is operator-directed and has no built-in legacy dependency; M4 still needs sibling/worktree zero-ref scans so copied invocations do not preserve legacy table usage. |
| `scripts/debug/commands/{queue,workers,scaling_audit,why_killed,task_journey,worker_timeline,pipeline}.py` | Live DB clients | Query `tasks`, `workers`, and `system_logs`, with no hard-coded `generations`, `generation_variants`, or `shot_generations` hits in the T7 grep. | **Keep with reason.** These are operational task/log clients and are not slot-first blockers unless later M3 contract changes rename task payload fields they display. |

## M4 Burn-Down Requirements

1. Before cutover, `debug.py context` must either be removed/disabled with a clear message or rewritten to slot-first nouns. It cannot continue querying `generations`, `generation_variants`, or `shot_generations`.
2. `scripts/debug/client.py` keeps task, log, worker, credit, dependency, and browser-session helpers, but the generation-specific helper methods must be replaced or deleted.
3. `scripts/debug/formatters.py` must stop rendering `generation_id`, `parent_generation_id`, and `child_order` as first-class diagnostic fields after slot-first cutover.
4. `scripts/quality/check-supabase-rls.mjs` must remain a static migration parser, but its explicit table list must reference slot-first tables rather than `shot_generations`.
5. M4 validation must include:

```bash
rg -n "generation_id|generation_variants|shot_generations|pair_shot_generation_id|parent_generation_id|child_generation_id|primary_variant_id|auto_create_variant_after_generation_insert|get_generation_by_task_id" scripts/debug scripts/quality/check-supabase-rls.mjs
```

The expected M4 result is zero live-script hits, except for archived audit documentation outside these script paths.
