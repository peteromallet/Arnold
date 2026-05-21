# Variable profiles — tier-route execute by task complexity

## Outcome

Introduce a new family of profiles (`variable`, `variable-claude`, `variable-codex`) that bias toward the cheapest safe model per batch. The planner emits an integer complexity score 1–5 for each task; the executor dispatches each batch on the model mapped to `max(task.complexity)` for that batch. Profiles without `[tier_models.*]` are unchanged.

## Scope IN

1. Add required `complexity: int 1..5` field to every task in `finalize.json`, enforced by the finalize schema.
2. Update three prompts to request/audit the score:
   - `_plan_prompt` (planning.py:156) — embed the 1-5 rubric in the requirements block (~line 255).
   - `_critique_context` (critique.py:116) — add an audit clause: flag inflation and under-rating; flag missing scores.
   - `_finalize_prompt` (finalize.py:24) — list `complexity` as a required task field with the rubric (extends the field list at ~line 106). Missing → default 5.
3. Add `[tier_models.<phase>]` block to profile TOML schema. Each tier entry (1..5) is a normal agent spec (`hermes:deepseek-flash`, `claude:high`, `codex:medium`, etc.).
4. Extend two helpers in `megaplan/profiles/__init__.py`:
   - `_substitute_vendor_in_profile` (line 741) — walk tier entries the same way it walks phase entries, so `_swap_premium_spec` propagates `--vendor` flips into tier 4/5. Cheap tiers (DeepSeek) pass through unchanged.
   - `_validate_named_profile_invariants` (line 890) — also walk tier entries for named-vendor profiles, so `variable-codex` catches drift at tier 4/5 the same way `all-codex` does for phases.
5. Add `variable-codex` to `_NAMED_VENDOR_PROFILES` (line 887). `variable-claude` and `variable` are unlocked (mirrors `all-claude`'s posture today).
6. Defer model resolution to per-batch in execute dispatch:
   - In `handle_execute` (handlers/execute.py:96), if the active profile has `tier_models.execute`, still resolve the fallback `(agent, mode, refreshed, model)` once, but pass the `tier_models.execute` mapping down to the dispatchers.
   - In `handle_execute_auto_loop` (execute/core.py:1249) and `handle_execute_one_batch` (execute/core.py:781), inside the per-batch loop: compute `batch_complexity = max(finalize_data.tasks[tid].complexity for tid in batch_task_ids)`, look up `tier_models.execute[batch_complexity]`, resolve agent/mode/model for that spec, force `refreshed=True` if the resolved model differs from the previous batch.
7. Add three new profile files in `megaplan/profiles/`:
   - `variable.toml` — unlocked, claude as premium base, honors `--vendor codex` to flip tier 4-5.
   - `variable-claude.toml` — `vendor_locked=true`, claude on all premium tiers.
   - `variable-codex.toml` — `vendor_locked=true`, codex on all premium tiers; added to `_NAMED_VENDOR_PROFILES`.
8. Update schema validation in `megaplan/schemas/` so:
   - Finalize task schema requires `complexity: integer, 1..5`.
   - Profile schema accepts optional `tier_models.<phase>` table with integer keys 1..5 mapping to spec strings.

## Scope OUT

- Tier-routing the `review` phase (v1 routes only `execute`).
- Auto-escalation on worker failure (one tier up on retry).
- Cost projection UI (separate feature).
- Migrating existing profiles (`all-codex`, `partnered`, etc.) to variable form.
- Per-task model selection within a batch (batch-level only).

## Locked decisions

- Score is integer 1..5, lives in `finalize.json` per task. Plan markdown may surface it informally; the structured contract is finalize.
- Missing complexity → default 5 (fail-safe: expensive model). Never default to 3.
- Batch complexity = `max(task complexity)`. Don't split batches by tier — dependency graph drives batching, complexity is read-only.
- Critique stays fixed-smart (it audits the scoring; can't be cheap or it rubber-stamps).
- Plan stays fixed (planning produces the scores; chicken-and-egg if it's variable).
- Tier table specs are vendor-neutral when written as `hermes:*`; `_swap_premium_spec` only rewrites the two premium vendors, so DeepSeek tiers naturally stay put under `--vendor` flips.
- Profiles without `[tier_models.*]` keep flat behavior. Pure additive feature.
- `--phase-model` CLI overrides retain top precedence (escape hatch).
- No auto-escalation in v1. Log batch tier in history so calibration drift is observable.
- Tier change between batches forces `refreshed=True` (different model = different session).

## Open questions

1. **DeepSeek granularity.** Are `hermes:deepseek-flash` and `hermes:deepseek-pro` distinct callable specs in the hermes wrapper today? If only one DeepSeek tier exists, tiers 1 and 2 collapse to the same model in v1 — fine, but should be confirmed at planning time so the default tier table reflects reality.
2. **`variable` (unlocked) default premium vendor.** Mirror `all-claude` (claude as base, unlocked, honors `--vendor codex`)? Yes is my assumption; confirm.
3. **Default tier table for `variable-codex`.** Proposal:
   - 1 → `hermes:deepseek-flash`
   - 2 → `hermes:deepseek-pro`
   - 3 → `hermes:deepseek-pro`
   - 4 → `codex:medium`
   - 5 → `codex:high` (codex caps at `high`)
   Confirm or revise.

## Constraints

- **Additive only.** Existing profiles (`all-codex`, `all-claude`, `partnered`, `directed`, `solo`, `apex`, `premium`) must produce byte-identical resolution to today. Critical: a regression here invalidates the recent f679c3b2 `vendor_locked` fix and the `all-codex` guarantee.
- Vendor lock semantics preserved: locked variable profiles refuse `--vendor` flips silently, same as `all-codex`.
- Profile schema validation must reject malformed `tier_models` entries at profile load time, not at dispatch time.
- The auto-driver / chain logic touches profile resolution via `state.config.profile` recovery — must continue to work without changes.

## Done criteria

- `megaplan init <brief> --profile variable-codex --confirm-destructive` runs a real sprint where the execute phase dispatches different codex models per batch based on each batch's max task complexity. Verifiable via history entries (each execute entry records the resolved model) and per-batch artifacts.
- All existing tests pass unchanged.
- New tests cover, at minimum:
  - Tier resolution: given a finalize.json with task complexities `[1, 3, 5]` in three batches, the dispatcher resolves three different model specs in order.
  - Vendor swap propagates into tiers: `--vendor codex --profile variable` rewrites premium tier entries (4, 5) but leaves DeepSeek tier entries (1, 2, 3) unchanged.
  - Named-profile invariants extend to tiers: a `variable-codex` profile with a claude spec accidentally in tier 4 fails resolution with `profile_resolution_mismatch`.
  - Missing-complexity defaults to 5: a task without the field gets the tier-5 model.
  - Profiles without `tier_models` are unchanged: running `partnered` produces byte-identical resolution as today.
  - Locked variable profiles refuse `--vendor` flips: `--profile variable-codex --vendor claude` is silently ignored (lock takes precedence).
- An `all-codex` sprint run shows zero behavioral change (regression smoke test).

## Touchpoints

- `megaplan/_core/io.py:58-109` — `compute_task_batches`, `compute_global_batches` (read complexity; add `compute_batch_complexity` helper).
- `megaplan/execute/core.py:720+` — `handle_execute_one_batch` per-batch resolution at ~line 781.
- `megaplan/execute/core.py:1074+` — `handle_execute_auto_loop`; the per-batch loop at line 1249-1290.
- `megaplan/execute/core.py:527+` — `_run_and_merge_batch` (signature unchanged; just receives different kwargs per batch).
- `megaplan/handlers/execute.py:78, 96` — `apply_profile_expansion` + `resolve_agent_mode` call sites; thread `tier_models` mapping through to dispatchers.
- `megaplan/profiles/__init__.py:724` — `_swap_premium_spec` (unchanged; just gets called more places).
- `megaplan/profiles/__init__.py:741` — `_substitute_vendor_in_profile` (walk tier entries).
- `megaplan/profiles/__init__.py:887` — `_NAMED_VENDOR_PROFILES` (add `variable-codex`).
- `megaplan/profiles/__init__.py:890` — `_validate_named_profile_invariants` (walk tier entries).
- `megaplan/profiles/__init__.py:912+` — `apply_profile_expansion` (thread tier_models through to args / state).
- `megaplan/prompts/planning.py:156` — `_plan_prompt` requirements block.
- `megaplan/prompts/critique.py:116` — `_critique_context` audit checklist.
- `megaplan/prompts/finalize.py:24` — `_finalize_prompt` task field guidance at ~line 106.
- `megaplan/schemas/` — finalize task schema + profile schema.
- `megaplan/profiles/*.toml` — new files: `variable.toml`, `variable-claude.toml`, `variable-codex.toml`.

## Anti-scope

- Don't refactor `apply_profile_expansion` beyond what's needed to support `tier_models`.
- Don't touch the auto-driver / chain logic.
- Don't change any existing profile TOML (no migration to variable form).
- Don't add per-task model selection within a batch.
- Don't add cost projection / preview UI.
- Don't add fallback retry-on-different-tier behavior.
- Don't introduce a new spec format — tier entries use the existing `agent:model` spec syntax.
