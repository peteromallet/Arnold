# M2 — Store abstraction integrity

**Rubric:** `premium/thorough/high`
**Position in epic:** milestone 4 of 12. Depends on M0 (extends its store-contract baseline) and runs after M3a (whose visibility fixes de-risk this). The highest-stakes milestone — data-integrity work.

## Outcome
Restore `Store` abstraction integrity so behavior doesn't silently diverge by backend: method parity across `DBStore`/`FileStore`/`MultiStore`, intentional (not accidentally DB-pinned) `MultiStore` routing, and `state.json` persisted through one coherent path.

## Scope (IN)
- **Backend parity for the ticket domain.** DB-only methods (`store/db.py:1988-2200`): `create_ticket`, `load_ticket`, `update_ticket`, `link_ticket_to_epic`, `unlink_ticket_from_epic`, `address_tickets_resolved_by_epic`, `load_codebase_by_associated_epic` — **plus (added per review) `list_tickets` (`db.py:2039`), `list_ticket_epic_links` (`db.py:2163`), and `resolve_codebase_by_root_sha` (`db.py:1988`)** which live in the same block and are equally absent. A create-but-can't-query ticket domain is an incoherent half-port. Add to the `Store` protocol (`store/base.py`) + implement on every backend, or deliberately + loudly document as DB-only with a guarded NotImplemented.
- **Fix `MultiStore` split-brain.** `store/multi.py:645-898` hardcodes 15+ ops to `self.db` though `FileStore` implements them (`insert_pending`, `mark_confirmed/failed/orphaned`, `find_pending_external_requests`, codebase ops, `get_api_cache`, `cleanup_expired_api_cache`, control-message ops, `upsert_resident_conversation`, `events_by_transaction`). Build a documented **entity-ownership map** — but note (per review) some (control messages, resident conversations, API cache) genuinely *should* be DB-only with no file schema; routing them to FileStore would fail at runtime. The map decides per-entity; not a blanket flip.
- **Route `state.json` coherently.** Raw paths bypass the store: `_pipeline/executor.py:252-255,360-363` (`_merge_state_to_disk`, merge semantics via `executor_owned_keys`), `resume.py:73-85` (`ResumeCursor.save` does read-modify-write of one key), `run_cli.py:255-324`. **Per review: this needs a dedicated MERGE-AWARE artifact method** — `write_plan_artifact` is full-file-replace (blob) semantics; a naive redirect **loses the merge logic and breaks resume**. **Per Opus sense-check: there are THREE live writers with three different semantics** — `executor._merge_state_to_disk` (real `executor_owned_keys` read-merge-write), `ResumeCursor.save` (RMW of one key, **non-atomic `path.write_text`**), and `PlanRepository.save_state` (naive atomic *blob* overwrite). `executor.py` does NOT use `PlanRepository` today, and `PlanRepository.save_state` is itself a blob writer that would *break* the executor merge — so do **NOT** "reconcile toward `save_state`". Add the new merge-aware method (below) and route all three writers through it; folding in `ResumeCursor.save` also fixes its non-atomic write (a deliberate, welcome behavior change — note it).
- **Idempotency parity (narrowed per review).** `DBStore.__getattribute__` (`db.py:390-401`) wraps mutations in `_run_idempotent_mutation` and raises on missing key. **FileStore already enforces** on `insert_pending` (`file.py:1669-1678`) and `create_message` (`file.py:1435-1438`) — the real gap is `update_epic` (`file.py:729`, key accepted, never used). Make idempotency consistent where partially present; don't claim/assume a uniform FileStore gap that doesn't exist.
- **Schema-drift on `update_epic`.** `db.py:612` builds SQL from raw `**changes` → hard error on unknown column; `file.py:734-738` does `model_dump`→`update`→`model_validate`, possibly accepting extras. Make unknown-field handling identical (concrete test: pass `bogus_column`, assert both raise the same error class).
- **Tighten the `*Input` write-path gatekeepers (added per gap-hunt — same validation-drift class).** The store's `*Input` models accept bare `str` where the canonical schemas define closed `Literal` sets: `ChecklistItemInput.status: str = "open"` vs `ChecklistStatus = Literal["open","done","skipped","superseded"]` (`schemas/arnold.py:230`); `SprintItemInput.estimated_complexity: str` vs `SprintItemComplexity`; `ControlMessageInput.intent: str` vs `ControlIntent` (all in `store/base.py:74-210`). These are the entry validators for every store mutation — they should reuse the schema Literals. Fix alongside `update_epic`: same "validation present in one layer, absent in another" problem. Add a test per Input model asserting an out-of-set value is rejected.
- **Remove dead branch.** `MultiStore.update_checklist_item` (`multi.py:352-361`) guards on `hasattr(self.file,"load_checklist_item")` which is always `True` → unreachable fallback.

## Locked decisions
- `store/base.py` is the single source of truth for the method surface; every backend satisfies it or loudly opts out.
- `MultiStore` routing is intentional + documented per-entity, never accidentally DB-pinned.
- **DECIDED (Codex sense-check): add a merge-aware state method** to the protocol/`PlanRepository` (encapsulating the read-modify-write + `executor_owned_keys` merge) and route executor/resume/run_cli through it. Do **NOT** naive-redirect to `write_plan_artifact` (full-file-replace) — that loses merge semantics and breaks resume. (Override at init if you prefer a different seam.)
- **DECIDED: M2 owns `Plan.current_state` enforcement.** M4 makes the naming decision; here, add a `Literal`/validator so an out-of-set state string is rejected at the persistence boundary (`schemas/sprint1.py:221`, against the 18 `STATE_*` constants). This is a behavior change — gate it behind a test + update the M0 golden.
- The MultiStore ownership map is a **prep deliverable** (thorough robustness already runs prep) — researched, not invented mid-plan.
- Extend `tests/contract/store_contract.py` (from M0) — do not fork a new harness.

## Open questions (for plan to resolve)
- Per `MultiStore` op: which backend *should* own it? (entity-ownership map, accounting for DB-only entities)
- Where does the new merge-aware method live — on the `Store` protocol, or as a `PlanRepository` method that all three writers call? (DECIDED that it's a *new merge-aware* method either way — NOT a reuse of the blob `save_state`/`write_plan_artifact`; this question is only about placement.)
- For `update_epic` idempotency: enforce on FileStore to match DB.

## Constraints
- Touches production persistence — wrong routing/migration corrupts run state. Hence `thorough`.
- No data loss on existing plan dirs / DB rows. Resume must still work (state.json merge semantics).

## Done criteria
- Extended store-contract test asserts every protocol method exists + behaves equivalently on DBStore/FileStore (**concretely**: same return shape, same exception class per condition, same side-effect/revision semantics) and routes deterministically under MultiStore.
- `MultiStore` routes by the documented ownership map.
- `state.json` reads/writes go through one merge-aware path; the M0 resume golden still passes.
- Idempotency + `update_epic` unknown-field handling identical across backends.
- Dead `update_checklist_item` branch removed.

## Touchpoints
`megaplan/store/base.py`, `db.py`, `file.py`, `multi.py`, `plan_repository.py`, `megaplan/_pipeline/executor.py`, `resume.py`, `run_cli.py`, `tests/contract/store_contract.py`.

## Step order (per review)
state.json reconciliation (get the artifact/merge semantics right) **before** MultiStore routing — MultiStore's artifact routing may need the new method first; prevents a double refactor.

## Anti-scope
- Do NOT split `db.py`/`file.py` into per-entity modules (M5a) — fix behavior/parity only, not file structure.
- Do NOT restructure the pipeline executor's node-execution flow — only the persistence call within `_merge_state_to_disk`/`ResumeCursor`.
- Do NOT change resolution semantics (M1) or error-raising policy (M3*) except where parity demands it.
- **Guardrail:** do NOT normalize "next-step" resolution or merge the drive engines.
