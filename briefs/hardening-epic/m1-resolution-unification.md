# M1 — Resolution model unification

**Rubric:** `partnered//high +prep`, robustness `full`
**Position in epic:** milestone 1 of 12. Depends on M0 (keep its baselines green). Emits the canonical-semantics decision doc that M3a/M3b and M4 cite.

## Outcome
Collapse the three forked resolution modules (`resolutions.py`, `user_actions.py`, `quality_resolutions.py`) onto shared helpers with one documented scoping contract, used by every caller. Fix the confirmed latent bug where `resolution_applies_to_task` has two contradictory empty-list contracts — **without** silently flipping the behavior of either pipeline.

## Scope (IN)
- **Unify `resolution_applies_to_task`.** Two contradictory definitions:
  - `resolutions.py:190` — reads `applies_to_task_ids`; **empty list = applies to all**. Backs the *disk* pipeline (`user_action_resolutions.json`), called from `cli.py`.
  - `user_actions.py:64` — reads `applies_to_tasks`; **missing = all, empty = none**. Backs the *in-memory* pipeline (`state.meta` events in `state.json`), called from `blocker_recovery.py:431`.
  - The two pipelines use **different field names AND different persistence** — so unification needs a read-time field-name alias layer, decided before any caller moves.
- **De-duplicate the helper triad.** `_event_sort_key` is byte-identical in `quality_resolutions.py:29` and `user_actions.py:24`. The `validate_*_resolution_event`/`build_*_resolution_event` pairs (`user_actions.py:117,152`; `quality_resolutions.py:36,103`) and the latest-by-timestamp aggregators (`effective_resolutions` `user_actions.py:40` vs `latest_quality_resolutions` `quality_resolutions.py:138`) are structurally identical → shared base.
- **The near-duplicate behavior-classifier pair (added per review).** `classify_resolution_behavior` (`user_actions.py:31` → `OMIT`/`FALLBACK`/`HARD_BLOCK`) and `resolution_recommended_action` (`resolutions.py:209` → `retry_execute`/`continue_with_fallback`/`awaiting_human`/`cannot_continue`) encode the same semantics in different vocabularies; both are imported by `blocker_recovery.py` and `cli.py`. They live in the exact files being unified — bring them into scope. Their output mapping must be **behavior-preserved** (load-bearing for blocker-recovery orchestration).
- **Unify duplicated state constants** for the user-action domain (the 5: `SATISFIED`, `ACCEPTED_BLOCKED`, `WAIVED`, `MANUAL_REQUIRED`, `REJECTED`) defined in both `resolutions.py` and `user_actions.py` + its `_VALID_RESOLUTIONS`.
- **Fix `build_resolution_event` field bleed (added per review).** `user_actions.py:152-193` accepts quality-domain params (`phase`, `evidence`, `debt_note`) that belong to `quality_resolutions`. Untangle when consolidating.
- **Update ALL call sites (added per review — blast radius is larger than first stated):** `cli.py` imports resolution symbols at lines 93, 94, 111, 241-246, 1347, 3839, 4231, 4356, 4397 (not just `:245`); `prompts/execute.py:20-24` (used at `:296`); `blocker_recovery.py` (imports `HARD_BLOCK` from *both* modules with aliases); `user_actions.py:103` `action_resolution_status` calls the function internally.

## Locked decisions
- One set of shared helpers owns the common resolution logic; domain differences survive as **thin typed wrappers**, not forked copies.
- The empty-list/missing-scope contract decision is **the** key deliverable — written down with rationale and a per-caller migration-impact table **before** any caller is migrated.
- A read-time field-name alias (`applies_to_task_ids` ⇄ `applies_to_tasks`) is built so the unified function reads both shapes; no silent behavior flip on either pipeline.
- Keep resolution I/O functions as thin pass-throughs — do NOT redesign how persistence is called (that's M2).

## Open questions (for prep + plan to resolve)
- Per caller: which empty-list semantics does it rely on **today**? Prep maps every caller across both field names and both data sources (disk JSON + in-memory `state.meta`).
- Unify field name on disk, or keep both with a read-time alias?
- Is `quality_resolutions` a separate domain? **Yes, partially confirmed:** it has a *different* state set (`accepted_with_debt`, `fixed`, `manual_required`, `rejected` — 4, not the user-action 5) and validates `blocker_id` not `action_id`, with required `phase`/`evidence`/`debt_note` on `accepted_with_debt`. Decide how much to share vs keep domain-specific.

## Constraints
- Resolution semantics decide whether operator decisions apply to specific tasks — a wrong unification mis-routes blocked work.
- Back-compat with existing `user_action_resolutions.json` AND in-memory `state.meta` event lists (two distinct sources — the back-compat test must cover **both**).

## Done criteria
- One `resolution_applies_to_task` with a docstring stating the contract; both old definitions removed (grep-verified).
- A test with **literal JSON fixtures for both field-name variants** (`applies_to_task_ids` and `applies_to_tasks`) asserting the expected interpretation for each, plus an in-memory `state.meta` event fixture (not just disk).
- `classify_resolution_behavior`/`resolution_recommended_action`/`classify_quality_resolution_behavior` produce identical outputs pre/post-unification (characterization test).
- `blocker_recovery.py` no longer imports `HARD_BLOCK` from two modules with aliases.
- A `docs/` note: chosen contract + rationale + per-caller migration-impact table.
- M0 baselines stay green.

## Touchpoints
`megaplan/resolutions.py`, `user_actions.py`, `quality_resolutions.py`, `blocker_recovery.py`, `cli.py` (8+ import sites + `_compute_user_action_blockers`), `prompts/execute.py`, `tests/test_resolutions.py`.

## Step order (per review — the brief's "define then migrate" was backwards)
1. Prep: map every caller + the contract/data-shape it relies on.
2. Decide & document the canonical contract.
3. Add read-time field-name aliasing.
4. Migrate callers one at a time, testing each.
5. Only then remove old definitions.

## Anti-scope
- Do NOT touch the store/persistence abstraction (M2) beyond keeping existing artifacts readable.
- Do NOT **collapse the distinct state-constant sets** — user-action (5) and quality/debt (4) are genuinely different domains; co-locate, don't merge.
- Do NOT change the mapping behavior of the behavior classifiers — identical outputs required.
- Do NOT rename unrelated domain vocabulary (M4) or refactor `cli.py` structure (M5b).
